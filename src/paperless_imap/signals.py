"""
Signaux Django pour le module IMAP Paperless-ngx

Gestion des événements automatiques lors des opérations sur les modèles IMAP :
- Création/modification de comptes
- Réception d'e-mails
- Traitement de pièces jointes
- Extraction d'événements
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any

from django.db.models.signals import (
    post_save, post_delete, pre_save, pre_delete
)
from django.dispatch import receiver
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings

from .models import (
    IMAPAccount, EmailMessage, EmailAttachment,
    EmailEvent, SyncLog
)
from .tasks import (
    sync_imap_account, process_email_attachment,
    generate_email_statistics
)


logger = logging.getLogger(__name__)


@receiver(post_save, sender=IMAPAccount)
def handle_account_created_or_updated(sender, instance, created, **kwargs):
    """
    Signal déclenché lors de la création ou modification d'un compte IMAP
    """
    if created:
        logger.info(f"Nouveau compte IMAP créé: {instance.name} ({instance.username})")

        # Lancement d'une synchronisation initiale pour les comptes actifs
        if instance.is_active and instance.auto_sync_enabled:
            try:
                # Délai de 30 secondes pour laisser le temps à la transaction de se finaliser
                sync_imap_account.apply_async(
                    args=[str(instance.id)],
                    countdown=30
                )
                logger.info(f"Synchronisation initiale programmée pour {instance.name}")
            except Exception as e:
                logger.error(f"Erreur programmation sync initiale {instance.name}: {e}")

        # Notification aux administrateurs (optionnel)
        if hasattr(settings, 'IMAP_NOTIFY_ADMIN_NEW_ACCOUNT') and settings.IMAP_NOTIFY_ADMIN_NEW_ACCOUNT:
            from django.core.mail import mail_admins
            try:
                mail_admins(
                    subject=f"Nouveau compte IMAP: {instance.name}",
                    message=f"Un nouveau compte IMAP a été créé par {instance.owner.username}.\n\n"
                           f"Nom: {instance.name}\n"
                           f"Serveur: {instance.server}:{instance.port}\n"
                           f"Utilisateur: {instance.username}\n"
                           f"Actif: {'Oui' if instance.is_active else 'Non'}",
                    fail_silently=True
                )
            except Exception as e:
                logger.warning(f"Erreur envoi notification admin: {e}")

    else:
        # Gestion des modifications
        logger.debug(f"Compte IMAP modifié: {instance.name}")

        # Invalidation du cache des statistiques
        cache_key = f"imap_account_stats_{instance.id}"
        cache.delete(cache_key)

        # Si le compte devient actif, programmer une synchronisation
        if instance.is_active and instance.auto_sync_enabled:
            try:
                # Vérification qu'il n'y a pas déjà une sync en cours
                recent_logs = SyncLog.objects.filter(
                    account=instance,
                    status=SyncLog.STATUS_RUNNING,
                    start_time__gte=timezone.now() - timedelta(minutes=10)
                )

                if not recent_logs.exists():
                    sync_imap_account.apply_async(
                        args=[str(instance.id)],
                        countdown=10
                    )
                    logger.info(f"Synchronisation programmée pour compte modifié {instance.name}")
            except Exception as e:
                logger.error(f"Erreur programmation sync après modification {instance.name}: {e}")


@receiver(pre_delete, sender=IMAPAccount)
def handle_account_deletion(sender, instance, **kwargs):
    """
    Signal déclenché avant la suppression d'un compte IMAP
    """
    logger.info(f"Suppression du compte IMAP: {instance.name} ({instance.username})")

    # Nettoyage du cache
    cache_keys = [
        f"imap_account_stats_{instance.id}",
        f"imap_account_emails_{instance.id}",
        f"imap_account_folders_{instance.id}"
    ]
    cache.delete_many(cache_keys)

    # Arrêt des tâches en cours (si possible)
    try:
        from celery import current_app
        # Recherche des tâches actives pour ce compte
        inspect = current_app.control.inspect()
        active_tasks = inspect.active()

        if active_tasks:
            for worker, tasks in active_tasks.items():
                for task in tasks:
                    if (task['name'] == 'paperless_imap.tasks.sync_imap_account' and
                        task['args'] and task['args'][0] == str(instance.id)):
                        logger.info(f"Tentative d'arrêt de la tâche de sync {task['id']}")
                        current_app.control.revoke(task['id'], terminate=True)
    except Exception as e:
        logger.warning(f"Erreur lors de l'arrêt des tâches pour {instance.name}: {e}")


@receiver(post_save, sender=EmailMessage)
def handle_email_created_or_updated(sender, instance, created, **kwargs):
    """
    Signal déclenché lors de la création ou modification d'un e-mail
    """
    if created:
        logger.debug(f"Nouvel e-mail reçu: {instance.subject} de {instance.sender}")

        # Mise à jour des statistiques du compte
        try:
            generate_email_statistics.apply_async(
                args=[30],  # 30 jours par défaut
                countdown=5
            )
        except Exception as e:
            logger.error(f"Erreur mise à jour stats compte: {e}")

        # Extraction automatique d'événements si activée
        # TODO: Implémenter extract_events_from_email
        # if instance.account.extract_events:
        #     try:
        #         extract_events_from_email.apply_async(
        #             args=[str(instance.id)],
        #             countdown=10
        #         )
        #         logger.debug(f"Extraction d'événements programmée pour e-mail {instance.id}")
        #     except Exception as e:
        #         logger.error(f"Erreur programmation extraction événements: {e}")

        # Traitement automatique des pièces jointes si activé
        if instance.account.attachment_processing_enabled:
            try:
                # Délai pour laisser le temps aux pièces jointes d'être créées
                from django.db import transaction
                def process_attachments():
                    attachments = instance.attachments.filter(
                        is_processed=False,
                        is_supported_format=True
                    )
                    for attachment in attachments:
                        process_email_attachment.apply_async(
                            args=[str(attachment.id)],
                            countdown=30
                        )

                transaction.on_commit(process_attachments)
            except Exception as e:
                logger.error(f"Erreur programmation traitement PJ: {e}")

        # Invalidation du cache
        cache_key = f"imap_account_emails_{instance.account.id}"
        cache.delete(cache_key)


@receiver(post_save, sender=EmailAttachment)
def handle_attachment_created_or_updated(sender, instance, created, **kwargs):
    """
    Signal déclenché lors de la création ou modification d'une pièce jointe
    """
    if created:
        logger.debug(f"Nouvelle pièce jointe: {instance.filename} ({instance.size} bytes)")

        # Traitement automatique si activé et format supporté
        if (instance.email.account.attachment_processing_enabled and
            instance.is_supported_format and
            not instance.is_processed):

            try:
                process_email_attachment.apply_async(
                    args=[str(instance.id)],
                    countdown=15
                )
                logger.debug(f"Traitement programmé pour PJ {instance.filename}")
            except Exception as e:
                logger.error(f"Erreur programmation traitement PJ {instance.filename}: {e}")

        # Mise à jour des statistiques
        try:
            generate_email_statistics.apply_async(
                args=[30],
                countdown=10
            )
        except Exception as e:
            logger.error(f"Erreur mise à jour stats pour PJ: {e}")

    else:
        # Gestion des modifications (ex: marquage comme traité)
        if instance.is_processed and instance.document:
            logger.info(f"Pièce jointe {instance.filename} traitée -> Document #{instance.document.pk}")

            # Notification de succès (optionnel)
            cache_key = f"attachment_processed_{instance.id}"
            cache.set(cache_key, {
                'processed_at': timezone.now().isoformat(),
                'document_id': instance.document.pk,
                'filename': instance.filename
            }, timeout=3600)  # 1 heure


@receiver(post_save, sender=EmailEvent)
def handle_event_created_or_updated(sender, instance, created, **kwargs):
    """
    Signal déclenché lors de la création ou modification d'un événement
    """
    if created:
        logger.debug(f"Nouvel événement extrait: {instance.title} ({instance.event_type})")

        # Notification pour les événements à haute confiance
        if instance.confidence_score >= 0.8:
            cache_key = f"high_confidence_event_{instance.id}"
            cache.set(cache_key, {
                'title': instance.title,
                'start_date': instance.start_date.isoformat() if instance.start_date else None,
                'confidence': instance.confidence_score,
                'email_subject': instance.email.subject
            }, timeout=86400)  # 24 heures

            logger.info(f"Événement haute confiance détecté: {instance.title}")

        # Mise à jour des statistiques du compte
        try:
            generate_email_statistics.apply_async(
                args=[30],
                countdown=5
            )
        except Exception as e:
            logger.error(f"Erreur mise à jour stats pour événement: {e}")

    else:
        # Gestion de la validation
        if instance.is_validated:
            logger.info(f"Événement validé: {instance.title}")

            # Notification de validation (optionnel)
            cache_key = f"event_validated_{instance.id}"
            cache.set(cache_key, {
                'validated_at': timezone.now().isoformat(),
                'title': instance.title,
                'type': instance.event_type
            }, timeout=3600)


@receiver(post_save, sender=SyncLog)
def handle_sync_log_created_or_updated(sender, instance, created, **kwargs):
    """
    Signal déclenché lors de la création ou modification d'un log de sync
    """
    if created:
        logger.debug(f"Nouveau log de sync créé pour {instance.account.name}")

    else:
        # Gestion de la fin de synchronisation
        if instance.status in [SyncLog.STATUS_SUCCESS, SyncLog.STATUS_ERROR]:
            logger.info(f"Synchronisation terminée pour {instance.account.name}: {instance.status}")

            # Mise à jour du statut du compte
            instance.account.last_sync = instance.end_time or timezone.now()
            instance.account.last_sync_status = instance.status

            if instance.status == SyncLog.STATUS_ERROR and instance.error_messages:
                # Mise à jour des erreurs du compte
                errors = instance.account.sync_errors or []
                errors.append({
                    'timestamp': timezone.now().isoformat(),
                    'message': instance.error_messages[:500],  # Limitation
                    'log_id': str(instance.id)
                })
                # Garde seulement les 10 dernières erreurs
                instance.account.sync_errors = errors[-10:]

            instance.account.save(update_fields=['last_sync', 'last_sync_status', 'sync_errors'])

            # Invalidation du cache
            cache_keys = [
                f"imap_account_stats_{instance.account.id}",
                f"imap_account_emails_{instance.account.id}",
                f"sync_logs_{instance.account.id}"
            ]
            cache.delete_many(cache_keys)

            # Programmation de la prochaine synchronisation si auto_sync activé
            if (instance.account.is_active and
                instance.account.auto_sync_enabled and
                instance.status == SyncLog.STATUS_SUCCESS):

                try:
                    next_sync = timezone.now() + timedelta(minutes=instance.account.sync_interval)
                    sync_imap_account.apply_async(
                        args=[str(instance.account.id)],
                        eta=next_sync
                    )
                    logger.debug(f"Prochaine sync programmée pour {instance.account.name} à {next_sync}")
                except Exception as e:
                    logger.error(f"Erreur programmation prochaine sync: {e}")


@receiver(pre_delete, sender=EmailMessage)
def handle_email_deletion(sender, instance, **kwargs):
    """
    Signal déclenché avant la suppression d'un e-mail
    """
    logger.debug(f"Suppression e-mail: {instance.subject}")

    # Nettoyage du cache
    cache_keys = [
        f"imap_account_emails_{instance.account.id}",
        f"email_content_{instance.id}",
        f"email_attachments_{instance.id}"
    ]
    cache.delete_many(cache_keys)

    # Les pièces jointes et événements associés seront supprimés automatiquement
    # grâce aux relations CASCADE dans les modèles


@receiver(pre_delete, sender=EmailAttachment)
def handle_attachment_deletion(sender, instance, **kwargs):
    """
    Signal déclenché avant la suppression d'une pièce jointe
    """
    logger.debug(f"Suppression pièce jointe: {instance.filename}")

    # Nettoyage du cache
    cache_keys = [
        f"attachment_processed_{instance.id}",
        f"attachment_content_{instance.id}"
    ]
    cache.delete_many(cache_keys)

    # Note: Le document Paperless associé n'est PAS supprimé automatiquement
    # pour préserver les données importées


# Configuration des signaux pour le logging
if hasattr(settings, 'IMAP_ENABLE_SIGNAL_LOGGING') and settings.IMAP_ENABLE_SIGNAL_LOGGING:

    @receiver(post_save)
    def log_model_changes(sender, instance, created, **kwargs):
        """Signal générique pour logger toutes les modifications"""
        if sender._meta.app_label == 'paperless_imap':
            action = "créé" if created else "modifié"
            logger.debug(f"{sender.__name__} {action}: {instance}")

    @receiver(pre_delete)
    def log_model_deletions(sender, instance, **kwargs):
        """Signal générique pour logger toutes les suppressions"""
        if sender._meta.app_label == 'paperless_imap':
            logger.debug(f"{sender.__name__} supprimé: {instance}")


# Utilitaires pour les signaux
def get_cache_key(model_name: str, instance_id: str, suffix: str = "") -> str:
    """Génère une clé de cache standardisée"""
    key = f"imap_{model_name}_{instance_id}"
    if suffix:
        key += f"_{suffix}"
    return key


def invalidate_related_cache(instance, patterns: list) -> None:
    """Invalide le cache selon des motifs"""
    try:
        keys_to_delete = []
        for pattern in patterns:
            formatted_pattern = pattern.format(
                id=getattr(instance, 'id', ''),
                account_id=getattr(instance, 'account_id', '') or getattr(instance.account, 'id', '') if hasattr(instance, 'account') else '',
                email_id=getattr(instance, 'email_id', '') or getattr(instance.email, 'id', '') if hasattr(instance, 'email') else ''
            )
            keys_to_delete.append(formatted_pattern)

        if keys_to_delete:
            cache.delete_many(keys_to_delete)
            logger.debug(f"Cache invalidé: {keys_to_delete}")
    except Exception as e:
        logger.warning(f"Erreur invalidation cache: {e}")


# Export des signaux pour les tests
__all__ = [
    'handle_account_created_or_updated',
    'handle_account_deletion',
    'handle_email_created_or_updated',
    'handle_attachment_created_or_updated',
    'handle_event_created_or_updated',
    'handle_sync_log_created_or_updated',
    'handle_email_deletion',
    'handle_attachment_deletion',
    'get_cache_key',
    'invalidate_related_cache'
]
