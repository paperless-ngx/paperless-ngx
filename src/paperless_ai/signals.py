"""
Signaux pour le système de classification intelligente

Signaux Django pour déclencher automatiquement la classification
et la génération d'embeddings lors d'événements sur les documents.
"""

import logging
from typing import Type, Any

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.conf import settings

from documents.models import Document
from .models import AIModel, DocumentEmbedding, DocumentClassification
from .tasks import classify_document_task, generate_document_embedding_task

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Document)
def document_saved_handler(sender: Type[Document], instance: Document,
                          created: bool, **kwargs: Any) -> None:
    """
    Signal handler déclenché quand un document est sauvegardé

    Lance automatiquement la classification et la génération d'embedding
    pour les nouveaux documents.
    """
    # Ne traiter que les nouveaux documents ou si le contenu a changé
    if not created:
        # Vérifier si le contenu a changé
        if hasattr(instance, '_state') and not instance._state.adding:
            # Pour les documents existants, ne pas relancer automatiquement
            # à moins qu'il y ait une configuration spécifique
            auto_process_updates = getattr(settings, 'PAPERLESS_AI_AUTO_PROCESS_UPDATES', False)
            if not auto_process_updates:
                return

    try:
        # Vérifier qu'il y a des modèles actifs
        active_models = AIModel.objects.filter(status='active')

        if not active_models.exists():
            logger.debug(f"Aucun modèle IA actif pour traiter le document {instance.id}")
            return

        # Lancer la génération d'embedding en arrière-plan
        generate_document_embedding_task.delay(instance.id)
        logger.info(f"Génération d'embedding lancée pour le document {instance.id}")

        # Lancer la classification en arrière-plan
        classify_document_task.delay(instance.id)
        logger.info(f"Classification lancée pour le document {instance.id}")

    except Exception as e:
        logger.error(f"Erreur lors du lancement de traitement IA pour le document {instance.id}: {e}")


@receiver(post_delete, sender=Document)
def document_deleted_handler(sender: Type[Document], instance: Document, **kwargs: Any) -> None:
    """
    Signal handler déclenché quand un document est supprimé

    Nettoie les embeddings et classifications associés.
    """
    try:
        # Supprimer les embeddings associés
        deleted_embeddings = DocumentEmbedding.objects.filter(document=instance).delete()
        if deleted_embeddings[0] > 0:
            logger.info(f"Supprimé {deleted_embeddings[0]} embedding(s) pour le document {instance.id}")

        # Supprimer les classifications associées
        deleted_classifications = DocumentClassification.objects.filter(document=instance).delete()
        if deleted_classifications[0] > 0:
            logger.info(f"Supprimé {deleted_classifications[0]} classification(s) pour le document {instance.id}")

    except Exception as e:
        logger.error(f"Erreur lors du nettoyage IA pour le document supprimé {instance.id}: {e}")


@receiver(post_save, sender=AIModel)
def ai_model_saved_handler(sender: Type[AIModel], instance: AIModel,
                          created: bool, **kwargs: Any) -> None:
    """
    Signal handler déclenché quand un modèle IA est sauvegardé

    Met à jour le cache des modèles actifs et lance le retraitement
    si nécessaire.
    """
    try:
        if created:
            logger.info(f"Nouveau modèle IA créé: {instance.name}")

            # Si le modèle est actif, traiter les documents existants
            if instance.status == 'active':
                _process_existing_documents_for_new_model(instance)

        else:
            # Modèle existant mis à jour
            if instance.status == 'active':
                logger.info(f"Modèle IA activé: {instance.name}")
                _process_existing_documents_for_new_model(instance)

            elif instance.status == 'inactive':
                logger.info(f"Modèle IA désactivé: {instance.name}")
                # Pas besoin d'action particulière, garder les données existantes

    except Exception as e:
        logger.error(f"Erreur lors du traitement du signal pour le modèle {instance.id}: {e}")


def _process_existing_documents_for_new_model(model: AIModel) -> None:
    """
    Lance le traitement des documents existants pour un nouveau modèle actif

    Cette fonction lance le traitement en arrière-plan pour éviter de bloquer
    la sauvegarde du modèle.
    """
    from .tasks import batch_generate_embeddings, batch_classify_documents

    # Obtenir les IDs des documents qui n'ont pas encore été traités par ce modèle
    if model.model_type == 'embedding':
        # Documents sans embedding pour ce modèle
        existing_embeddings = DocumentEmbedding.objects.filter(model=model).values_list('document_id', flat=True)
        documents_to_process = list(
            Document.objects.exclude(id__in=existing_embeddings).values_list('id', flat=True)[:100]  # Limiter à 100 pour commencer
        )

        if documents_to_process:
            logger.info(f"Lancement de génération d'embeddings pour {len(documents_to_process)} documents")
            batch_generate_embeddings.delay(documents_to_process, force=False)

    elif model.model_type == 'classification':
        # Documents sans classification pour ce modèle
        existing_classifications = DocumentClassification.objects.filter(model=model).values_list('document_id', flat=True)
        documents_to_process = list(
            Document.objects.exclude(id__in=existing_classifications).values_list('id', flat=True)[:100]  # Limiter à 100 pour commencer
        )

        if documents_to_process:
            logger.info(f"Lancement de classification pour {len(documents_to_process)} documents")
            batch_classify_documents.delay(documents_to_process, force=False)


# Signal pour nettoyer les données orphelines
@receiver(post_delete, sender=AIModel)
def ai_model_deleted_handler(sender: Type[AIModel], instance: AIModel, **kwargs: Any) -> None:
    """
    Signal handler déclenché quand un modèle IA est supprimé

    Nettoie les embeddings et classifications associés.
    """
    try:
        # Supprimer les embeddings associés
        deleted_embeddings = DocumentEmbedding.objects.filter(model=instance).delete()
        if deleted_embeddings[0] > 0:
            logger.info(f"Supprimé {deleted_embeddings[0]} embedding(s) pour le modèle {instance.name}")

        # Supprimer les classifications associées
        deleted_classifications = DocumentClassification.objects.filter(model=instance).delete()
        if deleted_classifications[0] > 0:
            logger.info(f"Supprimé {deleted_classifications[0]} classification(s) pour le modèle {instance.name}")

        # Supprimer les métriques associées
        from .models import AIMetrics, TrainingJob
        deleted_metrics = AIMetrics.objects.filter(model=instance).delete()
        if deleted_metrics[0] > 0:
            logger.info(f"Supprimé {deleted_metrics[0]} métrique(s) pour le modèle {instance.name}")

        # Supprimer les tâches d'entraînement associées
        deleted_training_jobs = TrainingJob.objects.filter(model=instance).delete()
        if deleted_training_jobs[0] > 0:
            logger.info(f"Supprimé {deleted_training_jobs[0]} tâche(s) d'entraînement pour le modèle {instance.name}")

    except Exception as e:
        logger.error(f"Erreur lors du nettoyage pour le modèle supprimé {instance.name}: {e}")


def enable_ai_auto_processing() -> None:
    """
    Active le traitement automatique des documents par IA

    Cette fonction peut être appelée depuis une commande de gestion
    pour activer le traitement automatique.
    """
    settings.PAPERLESS_AI_AUTO_PROCESS_UPDATES = True
    logger.info("Traitement automatique IA activé")


def disable_ai_auto_processing() -> None:
    """
    Désactive le traitement automatique des documents par IA

    Utile pour les migrations ou la maintenance.
    """
    settings.PAPERLESS_AI_AUTO_PROCESS_UPDATES = False
    logger.info("Traitement automatique IA désactivé")
