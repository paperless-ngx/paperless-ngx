"""
Tâches Celery pour le module IMAP Paperless-ngx

Gestion asynchrone des opérations IMAP :
- Synchronisation des comptes
- Traitement des pièces jointes
- Extraction d'événements
- Maintenance et statistiques
"""

import logging
import traceback
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from celery import shared_task
from django.utils import timezone
from django.db import transaction
from django.conf import settings
from django.core.files.base import ContentFile

from .models import (
    IMAPAccount, EmailMessage, EmailAttachment,
    EmailEvent, SyncLog
)
from .imap_engine import IMAPProcessor, IMAPConnectionError, IMAPAuthenticationError

# Import sécurisé des modèles de documents
try:
    from documents.models import Document
    from documents.tasks import consume_file
except ImportError:
    logger = logging.getLogger(__name__)
    logger.warning("Module documents non disponible - traitement des PJ désactivé")
    Document = None
    consume_file = None


logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def sync_imap_account(self, account_id: str, force_full_sync: bool = False) -> Dict[str, Any]:
    """
    Synchronise un compte IMAP spécifique

    Args:
        account_id: UUID du compte IMAP
        force_full_sync: Force une synchronisation complète (ignore last_uid)

    Returns:
        Dict avec les statistiques de synchronisation
    """
    try:
        account = IMAPAccount.objects.get(id=account_id, is_active=True)
        logger.info(f"Début synchronisation compte: {account.name}")

        # Reset du dernier UID si synchronisation complète forcée
        if force_full_sync:
            original_uid = account.last_uid
            account.last_uid = 0
            account.save(update_fields=['last_uid'])
            logger.info(f"Synchronisation complète forcée pour {account.name}")

        # Traitement
        processor = IMAPProcessor(account)
        sync_log = processor.sync_emails()

        # Restoration du UID si échec et sync forcée
        if force_full_sync and sync_log.status == SyncLog.STATUS_ERROR:
            account.last_uid = original_uid
            account.save(update_fields=['last_uid'])

        # Statistiques de retour
        result = {
            'account_id': str(account.id),
            'account_name': account.name,
            'status': sync_log.status,
            'emails_processed': sync_log.emails_processed,
            'attachments_processed': sync_log.attachments_processed,
            'events_extracted': sync_log.events_extracted,
            'errors_count': sync_log.errors_count,
            'duration': sync_log.get_duration().total_seconds() if sync_log.get_duration() else 0,
            'sync_log_id': str(sync_log.id)
        }

        logger.info(f"Synchronisation terminée pour {account.name}: {result}")
        return result

    except IMAPAccount.DoesNotExist:
        error_msg = f"Compte IMAP {account_id} non trouvé ou inactif"
        logger.error(error_msg)
        return {'error': error_msg, 'account_id': account_id}

    except (IMAPConnectionError, IMAPAuthenticationError) as e:
        error_msg = f"Erreur connexion IMAP pour {account_id}: {e}"
        logger.error(error_msg)

        # Retry avec délai exponentiel pour les erreurs de connexion
        if self.request.retries < self.max_retries:
            retry_delay = min(300 * (2 ** self.request.retries), 3600)  # Max 1h
            logger.info(f"Retry {self.request.retries + 1}/{self.max_retries} dans {retry_delay}s")
            raise self.retry(countdown=retry_delay, exc=e)

        return {'error': error_msg, 'account_id': account_id, 'retries_exhausted': True}

    except Exception as e:
        error_msg = f"Erreur inattendue synchronisation {account_id}: {e}"
        logger.error(error_msg, exc_info=True)

        # Retry pour les erreurs inattendues avec moins de tentatives
        if self.request.retries < 1:  # Maximum 1 retry pour erreurs génériques
            logger.info(f"Retry pour erreur inattendue")
            raise self.retry(countdown=600, exc=e)  # 10 minutes

        return {'error': error_msg, 'account_id': account_id, 'retries_exhausted': True}


@shared_task
def sync_all_active_accounts(force_full_sync: bool = False) -> Dict[str, Any]:
    """
    Lance la synchronisation de tous les comptes IMAP actifs

    Args:
        force_full_sync: Force une synchronisation complète pour tous les comptes

    Returns:
        Dict avec les statistiques globales
    """
    logger.info("Début synchronisation de tous les comptes actifs")

    # Récupération des comptes actifs
    accounts = IMAPAccount.objects.filter(is_active=True)

    if not accounts.exists():
        logger.info("Aucun compte IMAP actif trouvé")
        return {
            'total_accounts': 0,
            'synced_accounts': 0,
            'failed_accounts': 0,
            'results': []
        }

    # Lancement des tâches de synchronisation
    results = []
    successful = 0
    failed = 0

    for account in accounts:
        try:
            # Vérification de la planification
            if not force_full_sync and not _should_sync_account(account):
                logger.debug(f"Synchronisation ignorée pour {account.name} (pas encore l'heure)")
                continue

            # Lancement de la tâche
            result = sync_imap_account.delay(str(account.id), force_full_sync)

            # Attente du résultat avec timeout
            try:
                task_result = result.get(timeout=300)  # 5 minutes max
                results.append(task_result)

                if 'error' not in task_result:
                    successful += 1
                else:
                    failed += 1

            except Exception as e:
                logger.error(f"Timeout ou erreur tâche {account.name}: {e}")
                failed += 1
                results.append({
                    'account_id': str(account.id),
                    'account_name': account.name,
                    'error': f"Timeout tâche: {e}"
                })

        except Exception as e:
            logger.error(f"Erreur lancement synchronisation {account.name}: {e}")
            failed += 1
            results.append({
                'account_id': str(account.id),
                'account_name': account.name,
                'error': f"Erreur lancement: {e}"
            })

    summary = {
        'total_accounts': accounts.count(),
        'synced_accounts': successful,
        'failed_accounts': failed,
        'timestamp': timezone.now().isoformat(),
        'results': results
    }

    logger.info(f"Synchronisation globale terminée: {summary}")
    return summary


@shared_task
def process_email_attachment(attachment_id: str) -> Dict[str, Any]:
    """
    Traite une pièce jointe spécifique

    Args:
        attachment_id: UUID de la pièce jointe

    Returns:
        Dict avec le résultat du traitement
    """
    try:
        attachment = EmailAttachment.objects.get(id=attachment_id)
        logger.info(f"Traitement pièce jointe: {attachment.filename}")

        # Vérification si déjà traitée
        if attachment.is_processed and attachment.document:
            logger.info(f"Pièce jointe déjà traitée: {attachment.filename}")
            return {
                'attachment_id': str(attachment.id),
                'filename': attachment.filename,
                'status': 'already_processed',
                'document_id': attachment.document.id if attachment.document else None
            }

        # Traitement avec le processeur IMAP
        processor = IMAPProcessor(attachment.email.account)
        processor._process_attachment_content(attachment)

        # Rafraîchissement depuis la base
        attachment.refresh_from_db()

        result = {
            'attachment_id': str(attachment.id),
            'filename': attachment.filename,
            'status': 'processed' if attachment.is_processed else 'failed',
            'document_id': attachment.document.id if attachment.document else None,
            'error': attachment.processing_error if attachment.processing_error else None
        }

        logger.info(f"Traitement terminé pour {attachment.filename}: {result['status']}")
        return result

    except EmailAttachment.DoesNotExist:
        error_msg = f"Pièce jointe {attachment_id} non trouvée"
        logger.error(error_msg)
        return {'error': error_msg, 'attachment_id': attachment_id}

    except Exception as e:
        error_msg = f"Erreur traitement pièce jointe {attachment_id}: {e}"
        logger.error(error_msg, exc_info=True)

        # Mise à jour de l'erreur dans l'objet
        try:
            attachment = EmailAttachment.objects.get(id=attachment_id)
            attachment.processing_error = str(e)
            attachment.save(update_fields=['processing_error'])
        except:
            pass

        return {'error': error_msg, 'attachment_id': attachment_id}


@shared_task
def process_pending_attachments(limit: int = 50) -> Dict[str, Any]:
    """
    Traite les pièces jointes en attente

    Args:
        limit: Nombre maximum de pièces jointes à traiter

    Returns:
        Dict avec les statistiques de traitement
    """
    logger.info(f"Traitement des pièces jointes en attente (limite: {limit})")

    # Récupération des pièces jointes non traitées
    pending_attachments = EmailAttachment.objects.filter(
        is_processed=False,
        is_supported_format=True,
        processing_error__isnull=True
    ).order_by('created')[:limit]

    if not pending_attachments:
        logger.info("Aucune pièce jointe en attente")
        return {
            'total_processed': 0,
            'successful': 0,
            'failed': 0,
            'results': []
        }

    # Traitement de chaque pièce jointe
    results = []
    successful = 0
    failed = 0

    for attachment in pending_attachments:
        try:
            result = process_email_attachment.delay(str(attachment.id))
            task_result = result.get(timeout=120)  # 2 minutes max par pièce jointe

            results.append(task_result)

            if 'error' not in task_result:
                successful += 1
            else:
                failed += 1

        except Exception as e:
            logger.error(f"Erreur traitement {attachment.filename}: {e}")
            failed += 1
            results.append({
                'attachment_id': str(attachment.id),
                'filename': attachment.filename,
                'error': str(e)
            })

    summary = {
        'total_processed': len(pending_attachments),
        'successful': successful,
        'failed': failed,
        'timestamp': timezone.now().isoformat(),
        'results': results
    }

    logger.info(f"Traitement pièces jointes terminé: {summary}")
    return summary


@shared_task
def cleanup_old_sync_logs(days_to_keep: int = 30) -> Dict[str, Any]:
    """
    Nettoie les anciens logs de synchronisation

    Args:
        days_to_keep: Nombre de jours de logs à conserver

    Returns:
        Dict avec les statistiques de nettoyage
    """
    logger.info(f"Nettoyage des logs de synchronisation (> {days_to_keep} jours)")

    cutoff_date = timezone.now() - timedelta(days=days_to_keep)

    # Suppression des anciens logs
    old_logs = SyncLog.objects.filter(start_time__lt=cutoff_date)
    count = old_logs.count()

    with transaction.atomic():
        old_logs.delete()

    result = {
        'logs_deleted': count,
        'cutoff_date': cutoff_date.isoformat(),
        'timestamp': timezone.now().isoformat()
    }

    logger.info(f"Nettoyage terminé: {count} logs supprimés")
    return result


@shared_task
def cleanup_orphaned_attachments() -> Dict[str, Any]:
    """
    Nettoie les pièces jointes orphelines (sans e-mail parent)

    Returns:
        Dict avec les statistiques de nettoyage
    """
    logger.info("Nettoyage des pièces jointes orphelines")

    # Recherche des pièces jointes orphelines
    orphaned = EmailAttachment.objects.filter(email__isnull=True)
    count = orphaned.count()

    # Suppression des fichiers temporaires
    temp_files_deleted = 0
    for attachment in orphaned:
        if attachment.temp_file_path:
            try:
                import os
                if os.path.exists(attachment.temp_file_path):
                    os.remove(attachment.temp_file_path)
                    temp_files_deleted += 1
            except Exception as e:
                logger.warning(f"Erreur suppression fichier temporaire {attachment.temp_file_path}: {e}")

    # Suppression des objets
    with transaction.atomic():
        orphaned.delete()

    result = {
        'attachments_deleted': count,
        'temp_files_deleted': temp_files_deleted,
        'timestamp': timezone.now().isoformat()
    }

    logger.info(f"Nettoyage orphelins terminé: {result}")
    return result


@shared_task
def refresh_oauth2_tokens() -> Dict[str, Any]:
    """
    Actualise les tokens OAuth2 expirés

    Returns:
        Dict avec les statistiques d'actualisation
    """
    logger.info("Actualisation des tokens OAuth2 expirés")

    # Recherche des comptes OAuth2 avec tokens expirés
    now = timezone.now()
    expired_accounts = IMAPAccount.objects.filter(
        auth_method=IMAPAccount.AUTH_OAUTH2,
        is_active=True,
        oauth2_token_expires__lt=now
    )

    if not expired_accounts.exists():
        logger.info("Aucun token OAuth2 expiré trouvé")
        return {
            'total_accounts': 0,
            'refreshed': 0,
            'failed': 0,
            'results': []
        }

    # Actualisation de chaque compte
    results = []
    refreshed = 0
    failed = 0

    for account in expired_accounts:
        try:
            from .imap_engine import OAuth2Handler

            oauth_handler = OAuth2Handler(account)
            success = oauth_handler.refresh_access_token()

            if success:
                refreshed += 1
                logger.info(f"Token OAuth2 actualisé pour {account.name}")
                results.append({
                    'account_id': str(account.id),
                    'account_name': account.name,
                    'status': 'refreshed'
                })
            else:
                failed += 1
                logger.error(f"Échec actualisation token pour {account.name}")
                results.append({
                    'account_id': str(account.id),
                    'account_name': account.name,
                    'status': 'failed',
                    'error': 'Refresh token failed'
                })

        except Exception as e:
            failed += 1
            logger.error(f"Erreur actualisation token {account.name}: {e}")
            results.append({
                'account_id': str(account.id),
                'account_name': account.name,
                'status': 'error',
                'error': str(e)
            })

    summary = {
        'total_accounts': expired_accounts.count(),
        'refreshed': refreshed,
        'failed': failed,
        'timestamp': timezone.now().isoformat(),
        'results': results
    }

    logger.info(f"Actualisation tokens terminée: {summary}")
    return summary


@shared_task
def generate_email_statistics(days: int = 30) -> Dict[str, Any]:
    """
    Génère des statistiques sur les e-mails traités

    Args:
        days: Période d'analyse en jours

    Returns:
        Dict avec les statistiques détaillées
    """
    logger.info(f"Génération statistiques e-mails ({days} derniers jours)")

    cutoff_date = timezone.now() - timedelta(days=days)

    # Statistiques générales
    total_emails = EmailMessage.objects.filter(created__gte=cutoff_date).count()
    total_attachments = EmailAttachment.objects.filter(
        email__created__gte=cutoff_date
    ).count()
    processed_attachments = EmailAttachment.objects.filter(
        email__created__gte=cutoff_date,
        is_processed=True
    ).count()

    # Statistiques par compte
    account_stats = []
    for account in IMAPAccount.objects.filter(is_active=True):
        emails_count = EmailMessage.objects.filter(
            account=account,
            created__gte=cutoff_date
        ).count()

        attachments_count = EmailAttachment.objects.filter(
            email__account=account,
            email__created__gte=cutoff_date
        ).count()

        account_stats.append({
            'account_id': str(account.id),
            'account_name': account.name,
            'emails_count': emails_count,
            'attachments_count': attachments_count,
            'last_sync': account.last_sync.isoformat() if account.last_sync else None
        })

    # Statistiques par catégorie
    category_stats = {}
    for category, label in EmailMessage.CATEGORY_CHOICES:
        count = EmailMessage.objects.filter(
            category=category,
            created__gte=cutoff_date
        ).count()
        category_stats[category] = {
            'label': label,
            'count': count
        }

    # Erreurs récentes
    recent_errors = SyncLog.objects.filter(
        status=SyncLog.STATUS_ERROR,
        start_time__gte=cutoff_date
    ).count()

    statistics = {
        'period_days': days,
        'period_start': cutoff_date.isoformat(),
        'total_emails': total_emails,
        'total_attachments': total_attachments,
        'processed_attachments': processed_attachments,
        'processing_rate': (processed_attachments / total_attachments * 100) if total_attachments > 0 else 0,
        'recent_errors': recent_errors,
        'account_statistics': account_stats,
        'category_statistics': category_stats,
        'generated_at': timezone.now().isoformat()
    }

    logger.info(f"Statistiques générées: {total_emails} e-mails, {total_attachments} pièces jointes")
    return statistics


# Fonctions utilitaires privées

def _should_sync_account(account: IMAPAccount) -> bool:
    """
    Vérifie si un compte doit être synchronisé selon son intervalle

    Args:
        account: Compte IMAP à vérifier

    Returns:
        True si la synchronisation est due
    """
    if not account.last_sync:
        return True  # Première synchronisation

    next_sync = account.last_sync + timedelta(minutes=account.sync_interval)
    return timezone.now() >= next_sync


# Configuration des tâches périodiques (à ajouter dans settings.py)
"""
Exemple de configuration Celery Beat dans settings.py :

CELERY_BEAT_SCHEDULE = {
    'sync-all-imap-accounts': {
        'task': 'paperless_imap.tasks.sync_all_active_accounts',
        'schedule': crontab(minute='*/15'),  # Toutes les 15 minutes
    },
    'process-pending-attachments': {
        'task': 'paperless_imap.tasks.process_pending_attachments',
        'schedule': crontab(minute='*/5'),  # Toutes les 5 minutes
        'kwargs': {'limit': 20}
    },
    'refresh-oauth2-tokens': {
        'task': 'paperless_imap.tasks.refresh_oauth2_tokens',
        'schedule': crontab(minute=0, hour='*/6'),  # Toutes les 6 heures
    },
    'cleanup-old-sync-logs': {
        'task': 'paperless_imap.tasks.cleanup_old_sync_logs',
        'schedule': crontab(minute=0, hour=2),  # Tous les jours à 2h du matin
        'kwargs': {'days_to_keep': 30}
    },
    'cleanup-orphaned-attachments': {
        'task': 'paperless_imap.tasks.cleanup_orphaned_attachments',
        'schedule': crontab(minute=0, hour=3, day_of_week=0),  # Dimanche à 3h
    },
    'generate-email-statistics': {
        'task': 'paperless_imap.tasks.generate_email_statistics',
        'schedule': crontab(minute=0, hour=1),  # Tous les jours à 1h du matin
        'kwargs': {'days': 30}
    }
}
"""
