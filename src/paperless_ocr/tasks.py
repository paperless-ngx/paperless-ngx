from celery import shared_task
from celery.utils.log import get_task_logger
from django.utils import timezone
from django.db import transaction
from documents.models import Document
from .models import OCRResult, OCRQueue, OCRConfiguration
from .engines import TesseractEngine, DoctrEngine, HybridEngine, OCRConfig
import time

logger = get_task_logger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_document_ocr(self, document_pk, engines=None, priority=5, user_id=None):
    """
    Tâche principale pour traiter un document avec le pipeline OCR hybride

    Args:
        document_pk: ID du document à traiter
        engines: Liste des moteurs à utiliser ['tesseract', 'doctr', 'hybrid']
        priority: Priorité du traitement
        user_id: ID de l'utilisateur qui a demandé le traitement
    """

    try:
        # Récupération du document
        document = Document.objects.get(pk=document_pk)
        logger.info(f"Début traitement OCR pour document {document.id}: {document.title}")

        # Configuration par défaut
        if engines is None:
            engines = ['tesseract', 'doctr', 'hybrid']

        # Récupération de la configuration active
        config_model = OCRConfiguration.objects.filter(is_active=True).first()
        if not config_model:
            logger.error("Aucune configuration OCR active trouvée")
            return {"error": "Aucune configuration OCR active"}

        # Conversion en objet de configuration
        ocr_config = OCRConfig(
            tesseract_lang=config_model.tesseract_lang,
            tesseract_psm=config_model.tesseract_psm,
            tesseract_oem=config_model.tesseract_oem,
            doctr_model=config_model.doctr_model,
            doctr_recognition_model=config_model.doctr_recognition_model,
            max_image_size=config_model.max_image_size,
            dpi=config_model.dpi,
            enhance_image=config_model.enhance_image,
            denoise=config_model.denoise,
            max_memory_mb=config_model.max_memory_mb,
            batch_size=config_model.batch_size
        )

        results = {}

        # Traitement avec Tesseract (rapide)
        if 'tesseract' in engines:
            logger.info(f"Démarrage Tesseract pour document {document.id}")
            tesseract_result = run_tesseract_ocr.delay(document_pk, config_model.id)
            results['tesseract_task_id'] = tesseract_result.id

        # Traitement avec Doctr (précis, en arrière-plan)
        if 'doctr' in engines:
            logger.info(f"Démarrage Doctr pour document {document.id}")
            doctr_result = run_doctr_ocr.delay(document_pk, config_model.id)
            results['doctr_task_id'] = doctr_result.id

        # Attente et fusion si demandé
        if 'hybrid' in engines and 'tesseract' in engines and 'doctr' in engines:
            logger.info(f"Démarrage fusion hybride pour document {document.id}")
            hybrid_result = run_hybrid_fusion.delay(document_pk, config_model.id)
            results['hybrid_task_id'] = hybrid_result.id

        return {
            "status": "success",
            "document_id": document_pk,
            "engines_started": engines,
            "task_results": results
        }

    except Document.DoesNotExist:
        logger.error(f"Document {document_pk} non trouvé")
        return {"error": f"Document {document_pk} non trouvé"}

    except Exception as exc:
        logger.error(f"Erreur traitement OCR document {document_pk}: {exc}")
        # Retry avec backoff exponentiel
        countdown = 2 ** self.request.retries * 60
        raise self.retry(exc=exc, countdown=countdown, max_retries=3)


@shared_task(bind=True, max_retries=2)
def run_tesseract_ocr(self, document_pk, config_id):
    """Tâche pour exécuter Tesseract OCR"""

    try:
        document = Document.objects.get(pk=document_pk)
        config_model = OCRConfiguration.objects.get(pk=config_id)

        # Conversion en objet de configuration
        ocr_config = OCRConfig(
            tesseract_lang=config_model.tesseract_lang,
            tesseract_psm=config_model.tesseract_psm,
            tesseract_oem=config_model.tesseract_oem,
            max_image_size=config_model.max_image_size,
            dpi=config_model.dpi,
            enhance_image=config_model.enhance_image,
            denoise=config_model.denoise
        )

        # Marquer comme en cours
        ocr_result, created = OCRResult.objects.get_or_create(
            document=document,
            engine=OCRResult.ENGINE_TESSERACT,
            defaults={'configuration': config_model}
        )
        ocr_result.status = OCRResult.STATUS_PROCESSING
        ocr_result.save()

        # Exécution Tesseract
        engine = TesseractEngine(ocr_config)
        result = engine.process(document)

        # Sauvegarde des résultats
        with transaction.atomic():
            ocr_result.text = result.text
            ocr_result.confidence = result.confidence
            ocr_result.processing_time = result.processing_time
            ocr_result.metadata = result.metadata or {}
            ocr_result.page_results = result.page_results or []
            ocr_result.bounding_boxes = result.bounding_boxes or []
            ocr_result.status = OCRResult.STATUS_COMPLETED
            ocr_result.error_message = ""
            ocr_result.save()

        logger.info(f"Tesseract terminé pour document {document.id}: {result.confidence:.2f} confiance")

        return {
            "status": "success",
            "confidence": result.confidence,
            "processing_time": result.processing_time,
            "word_count": len(result.text.split()) if result.text else 0
        }

    except Exception as exc:
        logger.error(f"Erreur Tesseract document {document_pk}: {exc}")

        # Marquer comme échec
        try:
            ocr_result = OCRResult.objects.get(
                document_id=document_pk,
                engine=OCRResult.ENGINE_TESSERACT
            )
            ocr_result.status = OCRResult.STATUS_FAILED
            ocr_result.error_message = str(exc)
            ocr_result.save()
        except OCRResult.DoesNotExist:
            pass

        raise self.retry(exc=exc, countdown=60, max_retries=2)


@shared_task(bind=True, max_retries=2)
def run_doctr_ocr(self, document_pk, config_id):
    """Tâche pour exécuter Doctr OCR (plus lent mais plus précis)"""

    try:
        document = Document.objects.get(pk=document_pk)
        config_model = OCRConfiguration.objects.get(pk=config_id)

        # Conversion en objet de configuration
        ocr_config = OCRConfig(
            doctr_model=config_model.doctr_model,
            doctr_recognition_model=config_model.doctr_recognition_model,
            max_image_size=config_model.max_image_size,
            dpi=config_model.dpi,
            enhance_image=config_model.enhance_image,
            denoise=config_model.denoise,
            max_memory_mb=config_model.max_memory_mb
        )

        # Marquer comme en cours
        ocr_result, created = OCRResult.objects.get_or_create(
            document=document,
            engine=OCRResult.ENGINE_DOCTR,
            defaults={'configuration': config_model}
        )
        ocr_result.status = OCRResult.STATUS_PROCESSING
        ocr_result.save()

        # Exécution Doctr
        engine = DoctrEngine(ocr_config)
        result = engine.process(document)

        # Sauvegarde des résultats
        with transaction.atomic():
            ocr_result.text = result.text
            ocr_result.confidence = result.confidence
            ocr_result.processing_time = result.processing_time
            ocr_result.metadata = result.metadata or {}
            ocr_result.page_results = result.page_results or []
            ocr_result.bounding_boxes = result.bounding_boxes or []
            ocr_result.status = OCRResult.STATUS_COMPLETED
            ocr_result.error_message = ""
            ocr_result.save()

        logger.info(f"Doctr terminé pour document {document.id}: {result.confidence:.2f} confiance")

        return {
            "status": "success",
            "confidence": result.confidence,
            "processing_time": result.processing_time,
            "word_count": len(result.text.split()) if result.text else 0
        }

    except Exception as exc:
        logger.error(f"Erreur Doctr document {document_pk}: {exc}")

        # Marquer comme échec
        try:
            ocr_result = OCRResult.objects.get(
                document_id=document_pk,
                engine=OCRResult.ENGINE_DOCTR
            )
            ocr_result.status = OCRResult.STATUS_FAILED
            ocr_result.error_message = str(exc)
            ocr_result.save()
        except OCRResult.DoesNotExist:
            pass

        raise self.retry(exc=exc, countdown=120, max_retries=2)


@shared_task(bind=True, max_retries=1)
def run_hybrid_fusion(self, document_pk, config_id):
    """Tâche pour fusionner les résultats Tesseract et Doctr"""

    try:
        document = Document.objects.get(pk=document_pk)
        config_model = OCRConfiguration.objects.get(pk=config_id)

        # Attendre que les deux moteurs aient terminé
        max_wait = 600  # 10 minutes max
        wait_time = 0

        while wait_time < max_wait:
            tesseract_result = OCRResult.objects.filter(
                document=document,
                engine=OCRResult.ENGINE_TESSERACT,
                status=OCRResult.STATUS_COMPLETED
            ).first()

            doctr_result = OCRResult.objects.filter(
                document=document,
                engine=OCRResult.ENGINE_DOCTR,
                status=OCRResult.STATUS_COMPLETED
            ).first()

            if tesseract_result and doctr_result:
                break

            time.sleep(10)
            wait_time += 10

        if not (tesseract_result and doctr_result):
            raise Exception("Timeout: les moteurs OCR n'ont pas terminé à temps")

        # Conversion des résultats en format moteur
        from .engines import OCRResult as EngineOCRResult

        tess_engine_result = EngineOCRResult(
            text=tesseract_result.text,
            confidence=tesseract_result.confidence,
            processing_time=tesseract_result.processing_time,
            metadata=tesseract_result.metadata,
            page_results=tesseract_result.page_results
        )

        doctr_engine_result = EngineOCRResult(
            text=doctr_result.text,
            confidence=doctr_result.confidence,
            processing_time=doctr_result.processing_time,
            metadata=doctr_result.metadata,
            page_results=doctr_result.page_results
        )

        # Fusion hybride
        hybrid_engine = HybridEngine()
        fused_result = hybrid_engine.fuse(tess_engine_result, doctr_engine_result)

        # Sauvegarde du résultat fusionné
        with transaction.atomic():
            hybrid_ocr_result, created = OCRResult.objects.get_or_create(
                document=document,
                engine=OCRResult.ENGINE_HYBRID,
                defaults={'configuration': config_model}
            )

            hybrid_ocr_result.text = fused_result.text
            hybrid_ocr_result.confidence = fused_result.confidence
            hybrid_ocr_result.processing_time = fused_result.processing_time
            hybrid_ocr_result.metadata = fused_result.metadata or {}
            hybrid_ocr_result.page_results = fused_result.page_results or []
            hybrid_ocr_result.status = OCRResult.STATUS_COMPLETED
            hybrid_ocr_result.error_message = ""
            hybrid_ocr_result.save()

            # Mise à jour du contenu du document avec le meilleur résultat
            document.content = fused_result.text
            document.save()

        logger.info(f"Fusion hybride terminée pour document {document.id}: {fused_result.confidence:.2f} confiance")

        return {
            "status": "success",
            "confidence": fused_result.confidence,
            "processing_time": fused_result.processing_time,
            "fusion_method": fused_result.metadata.get('fusion_method', 'unknown'),
            "final_word_count": len(fused_result.text.split()) if fused_result.text else 0
        }

    except Exception as exc:
        logger.error(f"Erreur fusion hybride document {document_pk}: {exc}")

        # Marquer comme échec
        try:
            hybrid_result = OCRResult.objects.get(
                document_id=document_pk,
                engine=OCRResult.ENGINE_HYBRID
            )
            hybrid_result.status = OCRResult.STATUS_FAILED
            hybrid_result.error_message = str(exc)
            hybrid_result.save()
        except OCRResult.DoesNotExist:
            pass

        raise


@shared_task
def process_ocr_queue():
    """Tâche périodique pour traiter la file d'attente OCR"""

    # Récupérer les éléments en attente par priorité
    queued_items = OCRQueue.objects.filter(
        status=OCRQueue.STATUS_QUEUED
    ).order_by('-priority', 'created')[:10]  # Traiter 10 éléments max

    for item in queued_items:
        try:
            # Marquer comme en cours
            item.status = OCRQueue.STATUS_PROCESSING
            item.started = timezone.now()
            item.save()

            # Lancer le traitement
            task = process_document_ocr.delay(
                document_pk=item.document.pk,
                engines=item.engines,
                priority=item.priority,
                user_id=item.requested_by.pk if item.requested_by else None
            )

            # Sauvegarder l'ID de tâche
            item.celery_task_id = task.id
            item.save()

            logger.info(f"Tâche OCR lancée pour document {item.document.id}: {task.id}")

        except Exception as e:
            logger.error(f"Erreur lancement tâche OCR pour item {item.id}: {e}")
            item.status = OCRQueue.STATUS_FAILED
            item.save()


@shared_task
def cleanup_old_ocr_results():
    """Tâche de nettoyage des anciens résultats OCR"""

    from datetime import timedelta
    cutoff_date = timezone.now() - timedelta(days=90)

    # Supprimer les anciens résultats d'échec
    old_failed_results = OCRResult.objects.filter(
        status=OCRResult.STATUS_FAILED,
        created__lt=cutoff_date
    )

    count = old_failed_results.count()
    old_failed_results.delete()

    logger.info(f"Supprimé {count} anciens résultats OCR en échec")

    # Nettoyer la file d'attente
    old_queue_items = OCRQueue.objects.filter(
        status__in=[OCRQueue.STATUS_COMPLETED, OCRQueue.STATUS_FAILED],
        created__lt=cutoff_date
    )

    queue_count = old_queue_items.count()
    old_queue_items.delete()

    logger.info(f"Supprimé {queue_count} anciens éléments de la file OCR")

    return {"cleaned_results": count, "cleaned_queue": queue_count}
