from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.conf import settings
from documents.models import Document
from documents.signals import document_consumer_declaration
from .models import OCRQueue, OCRConfiguration, OCRResult
from .tasks import process_document_ocr
import logging

logger = logging.getLogger(__name__)


@receiver(document_consumer_declaration)
def trigger_ocr_on_document_import(sender, document, **kwargs):
    """
    Déclenche automatiquement le pipeline OCR quand un nouveau document est importé
    """

    try:
        # Vérifier si l'OCR automatique est activé
        auto_ocr_enabled = getattr(settings, 'PAPERLESS_OCR_AUTO_PROCESS', True)
        if not auto_ocr_enabled:
            logger.info(f"OCR automatique désactivé, document {document.id} ignoré")
            return

        # Vérifier qu'une configuration OCR est active
        active_config = OCRConfiguration.objects.filter(is_active=True).first()
        if not active_config:
            logger.warning(f"Aucune configuration OCR active, document {document.id} ignoré")
            return

        # Types de documents supportés
        supported_types = [
            'application/pdf',
            'image/jpeg',
            'image/png',
            'image/tiff',
            'image/bmp',
            'image/webp'
        ]

        if document.mime_type not in supported_types:
            logger.info(f"Type de document non supporté {document.mime_type}, document {document.id} ignoré")
            return

        # Déterminer les moteurs à utiliser selon la configuration
        engines = getattr(settings, 'PAPERLESS_OCR_DEFAULT_ENGINES', ['tesseract', 'doctr', 'hybrid'])
        priority = OCRQueue.PRIORITY_NORMAL

        # Priorité plus haute pour les nouveaux documents
        if kwargs.get('is_new', True):
            priority = OCRQueue.PRIORITY_HIGH

        # Vérifier si le document n'est pas déjà en cours de traitement
        existing_queue = OCRQueue.objects.filter(
            document=document,
            status__in=['queued', 'processing']
        ).exists()

        if existing_queue:
            logger.info(f"Document {document.id} déjà en file d'attente OCR")
            return

        # Créer l'entrée dans la file d'attente
        queue_item = OCRQueue.objects.create(
            document=document,
            engines=engines,
            priority=priority,
            requested_by=None  # Traitement automatique
        )

        # Lancer immédiatement pour les nouveaux documents
        if priority >= OCRQueue.PRIORITY_HIGH:
            task = process_document_ocr.delay(
                document_pk=document.pk,
                engines=engines,
                priority=priority
            )

            queue_item.celery_task_id = task.id
            queue_item.status = OCRQueue.STATUS_PROCESSING
            queue_item.save()

            logger.info(f"OCR lancé automatiquement pour document {document.id}: {task.id}")
        else:
            logger.info(f"Document {document.id} ajouté à la file d'attente OCR")

    except Exception as e:
        logger.error(f"Erreur déclenchement OCR automatique pour document {document.id}: {e}")


@receiver(post_save, sender=Document)
def handle_document_update(sender, instance, created, **kwargs):
    """
    Gère les mises à jour de documents pour re-déclencher l'OCR si nécessaire
    """

    if created:
        # Nouveau document - déjà géré par document_consumer_declaration
        return

    # Document existant modifié
    try:
        # Vérifier si le contenu du fichier a changé
        if hasattr(instance, 'content') and instance.content:
            # Vérifier si il y a des résultats OCR obsolètes
            results = OCRResult.objects.filter(document=instance)

            # Si pas de résultats ou résultats anciens, relancer l'OCR
            auto_reprocess = getattr(settings, 'PAPERLESS_OCR_AUTO_REPROCESS', False)
            if auto_reprocess and not results.exists():

                active_config = OCRConfiguration.objects.filter(is_active=True).first()
                if active_config:
                    queue_item = OCRQueue.objects.create(
                        document=instance,
                        engines=['tesseract', 'doctr', 'hybrid'],
                        priority=OCRQueue.PRIORITY_LOW,  # Priorité basse pour retraitement
                        requested_by=None
                    )

                    logger.info(f"Document {instance.id} ajouté pour retraitement OCR")

    except Exception as e:
        logger.error(f"Erreur gestion mise à jour document {instance.id}: {e}")


@receiver(pre_delete, sender=Document)
def cleanup_ocr_data_on_document_delete(sender, instance, **kwargs):
    """
    Nettoie les données OCR quand un document est supprimé
    """

    try:
        # Annuler les tâches en cours
        queue_items = OCRQueue.objects.filter(
            document=instance,
            status__in=['queued', 'processing']
        )

        for item in queue_items:
            if item.celery_task_id:
                from celery import current_app
                current_app.control.revoke(item.celery_task_id, terminate=True)
                logger.info(f"Tâche Celery {item.celery_task_id} annulée pour document {instance.id}")

        # Marquer comme annulées
        queue_items.update(status=OCRQueue.STATUS_CANCELLED)

        # Les résultats OCR seront supprimés automatiquement par CASCADE

        logger.info(f"Nettoyage OCR terminé pour document {instance.id}")

    except Exception as e:
        logger.error(f"Erreur nettoyage OCR pour document {instance.id}: {e}")


@receiver(post_save, sender=OCRConfiguration)
def handle_ocr_configuration_change(sender, instance, created, **kwargs):
    """
    Gère les changements de configuration OCR
    """

    try:
        if instance.is_active:
            # Désactiver les autres configurations
            OCRConfiguration.objects.exclude(pk=instance.pk).update(is_active=False)
            logger.info(f"Configuration OCR '{instance.name}' activée")

            # Optionnellement, redémarrer les workers Celery pour prendre en compte la nouvelle config
            restart_workers = getattr(settings, 'PAPERLESS_OCR_RESTART_WORKERS_ON_CONFIG_CHANGE', False)
            if restart_workers:
                try:
                    from celery import current_app
                    current_app.control.broadcast('pool_restart')
                    logger.info("Redémarrage des workers Celery demandé")
                except:
                    pass

    except Exception as e:
        logger.error(f"Erreur gestion changement configuration OCR: {e}")


@receiver(post_save, sender=OCRResult)
def handle_ocr_result_completion(sender, instance, created, **kwargs):
    """
    Gère la finalisation des résultats OCR
    """

    if not created:
        return

    try:
        # Si c'est un résultat hybride terminé avec succès, mettre à jour le document
        if (instance.engine == OCRResult.ENGINE_HYBRID and
            instance.status == OCRResult.STATUS_COMPLETED and
            instance.text):

            # Mettre à jour le contenu du document avec le résultat hybride
            document = instance.document
            if not document.content or len(instance.text) > len(document.content):
                document.content = instance.text
                document.save(update_fields=['content'])

                logger.info(f"Contenu du document {document.id} mis à jour avec résultat OCR hybride")

        # Marquer l'élément de la file comme terminé
        queue_items = OCRQueue.objects.filter(
            document=instance.document,
            status=OCRQueue.STATUS_PROCESSING
        )

        # Vérifier si tous les moteurs ont terminé
        requested_engines = set()
        completed_engines = set()

        for queue_item in queue_items:
            requested_engines.update(queue_item.engines)

        completed_results = OCRResult.objects.filter(
            document=instance.document,
            status=OCRResult.STATUS_COMPLETED
        )

        for result in completed_results:
            completed_engines.add(result.engine)

        # Si tous les moteurs demandés ont terminé
        if requested_engines.issubset(completed_engines):
            from django.utils import timezone
            queue_items.update(
                status=OCRQueue.STATUS_COMPLETED,
                completed=timezone.now()
            )
            logger.info(f"File d'attente OCR terminée pour document {instance.document.id}")

    except Exception as e:
        logger.error(f"Erreur finalisation résultat OCR {instance.id}: {e}")
