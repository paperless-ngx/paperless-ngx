"""
Vues API pour le système de classification intelligente

API REST pour la recherche sémantique, classification automatique,
gestion des modèles IA et monitoring des performances.
"""

import logging
import time
from typing import Dict, List, Any
from datetime import datetime, timedelta

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from django.utils import timezone
from django.db.models import Q, Count, Avg
from django.core.cache import cache
from django.shortcuts import get_object_or_404

from documents.models import Document, DocumentType, Correspondent, Tag
from .models import (
    AIModel, DocumentEmbedding, DocumentClassification,
    SearchQuery, AIMetrics, TrainingJob
)
from .serializers import (
    AIModelSerializer, DocumentEmbeddingSerializer, DocumentClassificationSerializer,
    SearchQuerySerializer, SemanticSearchSerializer, SearchResultSerializer,
    ClassificationRequestSerializer, BatchOperationSerializer,
    AIMetricsSerializer, TrainingJobSerializer, TrainingRequestSerializer,
    ClassificationValidationSerializer, ModelSuggestionSerializer,
    SuggestionResultSerializer, ModelPerformanceSerializer
)
from .classification import HybridClassificationEngine, VectorSearchEngine
from .tasks import (
    classify_document_task, generate_document_embedding_task,
    batch_classify_documents, batch_generate_embeddings,
    train_classification_model
)


logger = logging.getLogger(__name__)


class StandardResultsSetPagination(PageNumberPagination):
    """Pagination standard pour les résultats"""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class AIModelViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des modèles IA"""

    queryset = AIModel.objects.all()
    serializer_class = AIModelSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        """Filtre par propriétaire si nécessaire"""
        queryset = super().get_queryset()

        # Filtrer par propriétaire si non-admin
        if not self.request.user.is_staff:
            queryset = queryset.filter(owner=self.request.user)

        # Filtres optionnels
        model_type = self.request.query_params.get('model_type')
        if model_type:
            queryset = queryset.filter(model_type=model_type)

        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        return queryset.order_by('-updated')

    def perform_create(self, serializer):
        """Définit le propriétaire lors de la création"""
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=['post'])
    def train(self, request, pk=None):
        """Lance l'entraînement d'un modèle"""
        model = self.get_object()

        # Vérifier les permissions
        if model.owner != request.user and not request.user.is_staff:
            return Response(
                {"error": "Permission refusée"},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = TrainingRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Créer une tâche d'entraînement
            training_job = TrainingJob.objects.create(
                model=model,
                training_config=serializer.validated_data.get('training_config', {}),
                dataset_info={
                    "use_validated_only": serializer.validated_data.get('use_validated_data_only', True),
                    "test_split": serializer.validated_data.get('test_split', 0.2)
                },
                started_by=request.user
            )

            # Lancer la tâche d'entraînement
            task_result = train_classification_model.delay(str(training_job.id))

            return Response({
                "training_job_id": training_job.id,
                "task_id": task_result.id,
                "message": "Entraînement lancé"
            })

        except Exception as e:
            logger.error(f"Erreur lors du lancement de l'entraînement: {e}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'])
    def performance(self, request, pk=None):
        """Récupère les métriques de performance d'un modèle"""
        model = self.get_object()

        serializer = ModelPerformanceSerializer(data=request.query_params)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        period_days = serializer.validated_data.get('period_days', 7)
        metric_types = serializer.validated_data.get('metric_types')

        # Calculer la période
        period_end = timezone.now()
        period_start = period_end - timedelta(days=period_days)

        # Récupérer les métriques
        metrics_query = AIMetrics.objects.filter(
            model=model,
            period_start__gte=period_start
        )

        if metric_types:
            metrics_query = metrics_query.filter(metric_type__in=metric_types)

        metrics = AIMetricsSerializer(metrics_query, many=True).data

        # Calculer des statistiques agrégées
        stats = {
            "model_id": model.id,
            "model_name": model.name,
            "period_days": period_days,
            "metrics": metrics,
            "summary": self._calculate_performance_summary(metrics)
        }

        return Response(stats)

    def _calculate_performance_summary(self, metrics: List[Dict]) -> Dict:
        """Calcule un résumé des performances"""
        summary = {}

        for metric in metrics:
            metric_type = metric['metric_type']
            if metric_type not in summary:
                summary[metric_type] = {
                    "values": [],
                    "avg": 0,
                    "min": float('inf'),
                    "max": float('-inf')
                }

            value = metric['value']
            summary[metric_type]["values"].append(value)
            summary[metric_type]["min"] = min(summary[metric_type]["min"], value)
            summary[metric_type]["max"] = max(summary[metric_type]["max"], value)

        # Calculer les moyennes
        for metric_type in summary:
            values = summary[metric_type]["values"]
            summary[metric_type]["avg"] = sum(values) / len(values) if values else 0

        return summary


class DocumentClassificationViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet pour les classifications de documents"""

    queryset = DocumentClassification.objects.all()
    serializer_class = DocumentClassificationSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        """Filtre les classifications"""
        queryset = super().get_queryset().select_related(
            'document', 'model', 'predicted_document_type',
            'predicted_correspondent', 'validated_by'
        ).prefetch_related('predicted_tags')

        # Filtres
        document_id = self.request.query_params.get('document_id')
        if document_id:
            queryset = queryset.filter(document_id=document_id)

        model_id = self.request.query_params.get('model_id')
        if model_id:
            queryset = queryset.filter(model_id=model_id)

        classification_type = self.request.query_params.get('classification_type')
        if classification_type:
            queryset = queryset.filter(classification_type=classification_type)

        is_validated = self.request.query_params.get('is_validated')
        if is_validated is not None:
            queryset = queryset.filter(is_validated=is_validated.lower() == 'true')

        min_confidence = self.request.query_params.get('min_confidence')
        if min_confidence:
            try:
                queryset = queryset.filter(confidence_score__gte=float(min_confidence))
            except ValueError:
                pass

        return queryset.order_by('-created')

    @action(detail=True, methods=['post'])
    def validate(self, request, pk=None):
        """Valide une classification"""
        classification = self.get_object()

        serializer = ClassificationValidationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Mettre à jour la classification
            classification.is_validated = True
            classification.validation_feedback = serializer.validated_data['feedback']
            classification.validated_at = timezone.now()
            classification.validated_by = request.user
            classification.save()

            # Appliquer au document si demandé
            if serializer.validated_data.get('apply_to_document', False):
                self._apply_classification_to_document(classification)

            return Response({
                "message": "Classification validée",
                "applied_to_document": serializer.validated_data.get('apply_to_document', False)
            })

        except Exception as e:
            logger.error(f"Erreur lors de la validation de classification: {e}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _apply_classification_to_document(self, classification: DocumentClassification):
        """Applique une classification validée au document"""
        document = classification.document

        if classification.predicted_document_type:
            document.document_type = classification.predicted_document_type

        if classification.predicted_correspondent:
            document.correspondent = classification.predicted_correspondent

        # Ajouter les tags prédits
        for tag in classification.predicted_tags.all():
            document.tags.add(tag)

        document.save()

        # Marquer comme appliqué
        classification.is_applied = True
        classification.save()


class SemanticSearchViewSet(viewsets.ViewSet):
    """ViewSet pour la recherche sémantique"""

    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['post'])
    def search(self, request):
        """Recherche sémantique de documents"""
        serializer = SemanticSearchSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Mesurer le temps de réponse
            start_time = time.time()

            # Préparer les filtres
            filters = {}
            if serializer.validated_data.get('document_type'):
                filters['document_type'] = serializer.validated_data['document_type']
            if serializer.validated_data.get('correspondent'):
                filters['correspondent'] = serializer.validated_data['correspondent']
            if serializer.validated_data.get('tags'):
                filters['tags'] = serializer.validated_data['tags']

            # Initialiser le moteur de recherche
            search_engine = VectorSearchEngine()
            search_engine.load_model()
            search_engine.similarity_threshold = serializer.validated_data.get('similarity_threshold', 0.3)

            # Effectuer la recherche
            results = search_engine.search_documents(
                query=serializer.validated_data['query'],
                top_k=serializer.validated_data.get('top_k', 20),
                filters=filters
            )

            response_time = time.time() - start_time

            # Formater les résultats
            formatted_results = []
            for result in results:
                doc = result['document']
                formatted_results.append({
                    "document_id": doc.id,
                    "title": doc.title,
                    "similarity": result['similarity'],
                    "correspondent": doc.correspondent.name if doc.correspondent else None,
                    "document_type": doc.document_type.name if doc.document_type else None,
                    "tags": [tag.name for tag in doc.tags.all()],
                    "created": doc.created,
                    "modified": doc.modified,
                    "original_filename": doc.original_filename
                })

            # Enregistrer la requête pour analytics
            SearchQuery.objects.create(
                user=request.user,
                query_text=serializer.validated_data['query'],
                query_type='semantic',
                results_count=len(formatted_results),
                response_time=response_time,
                filters_applied=filters
            )

            return Response({
                "query": serializer.validated_data['query'],
                "results_count": len(formatted_results),
                "response_time": response_time,
                "results": formatted_results
            })

        except Exception as e:
            logger.error(f"Erreur lors de la recherche sémantique: {e}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'])
    def suggest(self, request):
        """Suggère des documents similaires"""
        serializer = ModelSuggestionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            document_id = serializer.validated_data['document_id']
            document = get_object_or_404(Document, id=document_id)

            # Initialiser le classificateur
            classifier = HybridClassificationEngine()
            classifier.load_models()

            suggestions = {}

            # Extraire le texte du document
            text = classifier._extract_document_text(document)

            if 'correspondent' in serializer.validated_data['suggestion_types']:
                correspondent_suggestions = classifier.distilbert_classifier.suggest_correspondent(
                    text, top_k=serializer.validated_data.get('max_suggestions', 5)
                )
                suggestions['correspondents'] = [
                    {
                        "type": "correspondent",
                        "suggestion": sugg['correspondent'].name,
                        "confidence": sugg['similarity'],
                        "existing_id": sugg['correspondent'].id,
                        "is_new": False,
                        "sample_count": sugg['sample_count']
                    }
                    for sugg in correspondent_suggestions
                    if sugg['similarity'] >= serializer.validated_data.get('min_confidence', 0.3)
                ]

            if 'tags' in serializer.validated_data['suggestion_types']:
                tag_suggestions = classifier.distilbert_classifier.suggest_tags(
                    text, top_k=serializer.validated_data.get('max_suggestions', 5)
                )
                suggestions['tags'] = [
                    {
                        "type": "tag",
                        "suggestion": sugg['tag'].name,
                        "confidence": sugg['similarity'],
                        "existing_id": sugg['tag'].id,
                        "is_new": False,
                        "sample_count": sugg['sample_count']
                    }
                    for sugg in tag_suggestions
                    if sugg['similarity'] >= serializer.validated_data.get('min_confidence', 0.3)
                ]

            return Response(suggestions)

        except Exception as e:
            logger.error(f"Erreur lors de la génération de suggestions: {e}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DocumentProcessingViewSet(viewsets.ViewSet):
    """ViewSet pour le traitement de documents"""

    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['post'])
    def classify(self, request):
        """Lance la classification d'un document"""
        serializer = ClassificationRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            document_id = serializer.validated_data['document_id']

            # Vérifier que le document existe
            if not Document.objects.filter(id=document_id).exists():
                return Response(
                    {"error": "Document non trouvé"},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Lancer la tâche de classification
            task_result = classify_document_task.delay(
                document_id,
                serializer.validated_data.get('force_reclassify', False)
            )

            return Response({
                "document_id": document_id,
                "task_id": task_result.id,
                "message": "Classification lancée"
            })

        except Exception as e:
            logger.error(f"Erreur lors du lancement de classification: {e}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'])
    def generate_embedding(self, request):
        """Génère l'embedding d'un document"""
        document_id = request.data.get('document_id')
        force_regenerate = request.data.get('force_regenerate', False)

        if not document_id:
            return Response(
                {"error": "document_id requis"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Vérifier que le document existe
            if not Document.objects.filter(id=document_id).exists():
                return Response(
                    {"error": "Document non trouvé"},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Lancer la tâche de génération d'embedding
            task_result = generate_document_embedding_task.delay(document_id, force_regenerate)

            return Response({
                "document_id": document_id,
                "task_id": task_result.id,
                "message": "Génération d'embedding lancée"
            })

        except Exception as e:
            logger.error(f"Erreur lors du lancement de génération d'embedding: {e}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'])
    def batch_process(self, request):
        """Traitement par lots de documents"""
        serializer = BatchOperationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            document_ids = serializer.validated_data['document_ids']
            operation = serializer.validated_data['operation']
            force = serializer.validated_data.get('force', False)

            # Vérifier que les documents existent
            existing_ids = list(
                Document.objects.filter(id__in=document_ids).values_list('id', flat=True)
            )

            if len(existing_ids) != len(document_ids):
                missing_ids = set(document_ids) - set(existing_ids)
                return Response(
                    {"error": f"Documents non trouvés: {list(missing_ids)}"},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Lancer l'opération appropriée
            if operation == 'classify':
                task_result = batch_classify_documents.delay(existing_ids, force)
            elif operation == 'generate_embeddings':
                task_result = batch_generate_embeddings.delay(existing_ids, force)
            else:
                return Response(
                    {"error": "Opération non supportée"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            return Response({
                "operation": operation,
                "document_count": len(existing_ids),
                "task_id": task_result.id,
                "message": f"Traitement par lots lancé ({operation})"
            })

        except Exception as e:
            logger.error(f"Erreur lors du traitement par lots: {e}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AIMetricsViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet pour les métriques IA"""

    queryset = AIMetrics.objects.all()
    serializer_class = AIMetricsSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        """Filtre les métriques"""
        queryset = super().get_queryset().select_related('model')

        # Filtres
        model_id = self.request.query_params.get('model_id')
        if model_id:
            queryset = queryset.filter(model_id=model_id)

        metric_type = self.request.query_params.get('metric_type')
        if metric_type:
            queryset = queryset.filter(metric_type=metric_type)

        # Filtre par période
        days = self.request.query_params.get('days', 30)
        try:
            cutoff_date = timezone.now() - timedelta(days=int(days))
            queryset = queryset.filter(created__gte=cutoff_date)
        except ValueError:
            pass

        return queryset.order_by('-created')


class TrainingJobViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet pour les tâches d'entraînement"""

    queryset = TrainingJob.objects.all()
    serializer_class = TrainingJobSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        """Filtre les tâches d'entraînement"""
        queryset = super().get_queryset().select_related('model', 'started_by')

        # Filtrer par propriétaire si non-admin
        if not self.request.user.is_staff:
            queryset = queryset.filter(started_by=self.request.user)

        # Filtres
        model_id = self.request.query_params.get('model_id')
        if model_id:
            queryset = queryset.filter(model_id=model_id)

        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        return queryset.order_by('-created')
