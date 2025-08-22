from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q, Avg, Count
from django.http import JsonResponse

from documents.models import Document
from .models import OCRResult, OCRQueue, OCRConfiguration
from .serializers import (
    OCRResultSerializer,
    OCRQueueSerializer,
    OCRConfigurationSerializer,
    OCRStatsSerializer
)
from .tasks import process_document_ocr


class OCRResultPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class OCRResultViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet pour consulter les résultats OCR"""

    queryset = OCRResult.objects.all().select_related('document', 'configuration')
    serializer_class = OCRResultSerializer
    pagination_class = OCRResultPagination
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filtres
        document_id = self.request.query_params.get('document_id')
        engine = self.request.query_params.get('engine')
        status_filter = self.request.query_params.get('status')
        min_confidence = self.request.query_params.get('min_confidence')

        if document_id:
            queryset = queryset.filter(document_id=document_id)

        if engine:
            queryset = queryset.filter(engine=engine)

        if status_filter:
            queryset = queryset.filter(status=status_filter)

        if min_confidence:
            try:
                min_conf = float(min_confidence)
                queryset = queryset.filter(confidence__gte=min_conf)
            except ValueError:
                pass

        return queryset.order_by('-created')

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Statistiques globales des résultats OCR"""

        stats = OCRResult.objects.aggregate(
            total_results=Count('id'),
            avg_confidence_tesseract=Avg('confidence', filter=Q(engine='tesseract')),
            avg_confidence_doctr=Avg('confidence', filter=Q(engine='doctr')),
            avg_confidence_hybrid=Avg('confidence', filter=Q(engine='hybrid')),
            avg_processing_time=Avg('processing_time'),
            completed_count=Count('id', filter=Q(status='completed')),
            failed_count=Count('id', filter=Q(status='failed')),
            processing_count=Count('id', filter=Q(status='processing')),
        )

        # Statistiques par moteur
        engine_stats = {}
        for engine in ['tesseract', 'doctr', 'hybrid']:
            engine_results = OCRResult.objects.filter(engine=engine)
            engine_stats[engine] = {
                'count': engine_results.count(),
                'avg_confidence': engine_results.aggregate(avg=Avg('confidence'))['avg'],
                'avg_processing_time': engine_results.aggregate(avg=Avg('processing_time'))['avg'],
                'success_rate': engine_results.filter(status='completed').count() / max(engine_results.count(), 1)
            }

        stats['by_engine'] = engine_stats

        serializer = OCRStatsSerializer(stats)
        return Response(serializer.data)


class DocumentOCRViewSet(viewsets.GenericViewSet):
    """ViewSet pour les actions OCR sur les documents"""

    queryset = Document.objects.all()
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=True, methods=['post'])
    def re_ocr(self, request, pk=None):
        """Relancer l'OCR pour un document"""

        document = self.get_object()

        # Paramètres
        engines = request.data.get('engines', ['tesseract', 'doctr', 'hybrid'])
        priority = request.data.get('priority', OCRQueue.PRIORITY_NORMAL)
        force = request.data.get('force', False)

        # Validation des moteurs
        valid_engines = ['tesseract', 'doctr', 'hybrid']
        engines = [eng for eng in engines if eng in valid_engines]

        if not engines:
            return Response(
                {"error": "Aucun moteur valide spécifié"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Vérifier si un traitement est déjà en cours
        if not force:
            existing_processing = OCRResult.objects.filter(
                document=document,
                status__in=['pending', 'processing']
            ).exists()

            if existing_processing:
                return Response(
                    {"error": "Un traitement OCR est déjà en cours pour ce document"},
                    status=status.HTTP_409_CONFLICT
                )

        # Créer l'entrée dans la file d'attente
        queue_item = OCRQueue.objects.create(
            document=document,
            engines=engines,
            priority=priority,
            requested_by=request.user
        )

        # Lancer immédiatement si priorité haute
        if priority >= OCRQueue.PRIORITY_HIGH:
            task = process_document_ocr.delay(
                document_pk=document.pk,
                engines=engines,
                priority=priority,
                user_id=request.user.pk
            )
            queue_item.celery_task_id = task.id
            queue_item.status = OCRQueue.STATUS_PROCESSING
            queue_item.started = timezone.now()
            queue_item.save()

            return Response({
                "status": "started",
                "task_id": task.id,
                "queue_id": queue_item.id,
                "engines": engines
            })
        else:
            return Response({
                "status": "queued",
                "queue_id": queue_item.id,
                "position": OCRQueue.objects.filter(
                    priority__gte=priority,
                    created__lt=queue_item.created,
                    status=OCRQueue.STATUS_QUEUED
                ).count() + 1,
                "engines": engines
            })

    @action(detail=True, methods=['get'])
    def ocr_status(self, request, pk=None):
        """Statut OCR d'un document"""

        document = self.get_object()

        # Résultats OCR existants
        results = OCRResult.objects.filter(document=document).order_by('-created')

        # Éléments en file d'attente
        queue_items = OCRQueue.objects.filter(
            document=document,
            status__in=['queued', 'processing']
        ).order_by('-priority', 'created')

        # Statut global
        overall_status = "unknown"
        if queue_items.filter(status='processing').exists():
            overall_status = "processing"
        elif queue_items.filter(status='queued').exists():
            overall_status = "queued"
        elif results.filter(status='completed').exists():
            overall_status = "completed"
        elif results.filter(status='failed').exists():
            overall_status = "failed"

        data = {
            "document_id": document.id,
            "overall_status": overall_status,
            "results": OCRResultSerializer(results, many=True).data,
            "queue_items": OCRQueueSerializer(queue_items, many=True).data,
            "last_processed": results.first().created if results.exists() else None,
            "total_results": results.count(),
            "successful_results": results.filter(status='completed').count(),
        }

        return Response(data)

    @action(detail=True, methods=['get'])
    def ocr_comparison(self, request, pk=None):
        """Comparaison des résultats OCR entre les différents moteurs"""

        document = self.get_object()

        # Récupérer les résultats des différents moteurs
        results = {}
        for engine in ['tesseract', 'doctr', 'hybrid']:
            result = OCRResult.objects.filter(
                document=document,
                engine=engine,
                status='completed'
            ).first()

            if result:
                results[engine] = {
                    'text': result.text,
                    'confidence': result.confidence,
                    'processing_time': result.processing_time,
                    'word_count': result.word_count,
                    'character_count': result.character_count,
                    'created': result.created
                }

        # Comparaisons
        comparison = {}
        if 'tesseract' in results and 'doctr' in results:
            from difflib import SequenceMatcher

            tess_text = results['tesseract']['text']
            doctr_text = results['doctr']['text']

            similarity = SequenceMatcher(None, tess_text, doctr_text).ratio()

            comparison = {
                'text_similarity': similarity,
                'length_difference': abs(len(tess_text) - len(doctr_text)),
                'confidence_difference': abs(
                    results['tesseract']['confidence'] - results['doctr']['confidence']
                ),
                'processing_time_ratio': (
                    results['doctr']['processing_time'] / results['tesseract']['processing_time']
                    if results['tesseract']['processing_time'] > 0 else 0
                )
            }

        return Response({
            'document_id': document.id,
            'results': results,
            'comparison': comparison
        })


class OCRConfigurationViewSet(viewsets.ModelViewSet):
    """ViewSet pour gérer les configurations OCR"""

    queryset = OCRConfiguration.objects.all()
    serializer_class = OCRConfigurationSerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activer une configuration"""

        config = self.get_object()

        # Désactiver les autres configurations
        OCRConfiguration.objects.filter(is_active=True).update(is_active=False)

        # Activer celle-ci
        config.is_active = True
        config.save()

        return Response({
            "status": "success",
            "message": f"Configuration '{config.name}' activée"
        })

    @action(detail=False, methods=['get'])
    def active(self, request):
        """Récupérer la configuration active"""

        active_config = OCRConfiguration.objects.filter(is_active=True).first()

        if active_config:
            serializer = self.get_serializer(active_config)
            return Response(serializer.data)
        else:
            return Response(
                {"error": "Aucune configuration active"},
                status=status.HTTP_404_NOT_FOUND
            )


class OCRQueueViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet pour monitorer la file d'attente OCR"""

    queryset = OCRQueue.objects.all().select_related('document', 'requested_by')
    serializer_class = OCRQueueSerializer
    pagination_class = OCRResultPagination
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filtres
        status_filter = self.request.query_params.get('status')
        priority = self.request.query_params.get('priority')

        if status_filter:
            queryset = queryset.filter(status=status_filter)

        if priority:
            try:
                priority_val = int(priority)
                queryset = queryset.filter(priority=priority_val)
            except ValueError:
                pass

        return queryset.order_by('-priority', 'created')

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Statistiques de la file d'attente"""

        stats = OCRQueue.objects.aggregate(
            total_items=Count('id'),
            queued_items=Count('id', filter=Q(status='queued')),
            processing_items=Count('id', filter=Q(status='processing')),
            completed_items=Count('id', filter=Q(status='completed')),
            failed_items=Count('id', filter=Q(status='failed')),
        )

        # Items par priorité
        priority_stats = {}
        for priority_val, priority_name in OCRQueue.PRIORITY_CHOICES:
            priority_stats[priority_name.lower()] = OCRQueue.objects.filter(
                priority=priority_val,
                status='queued'
            ).count()

        stats['by_priority'] = priority_stats

        return Response(stats)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Annuler un élément de la file d'attente"""

        queue_item = self.get_object()

        if queue_item.status not in ['queued', 'processing']:
            return Response(
                {"error": "Cet élément ne peut pas être annulé"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Annuler la tâche Celery si elle existe
        if queue_item.celery_task_id:
            from celery import current_app
            current_app.control.revoke(queue_item.celery_task_id, terminate=True)

        # Marquer comme annulé
        queue_item.status = OCRQueue.STATUS_CANCELLED
        queue_item.completed = timezone.now()
        queue_item.save()

        return Response({
            "status": "success",
            "message": "Élément annulé"
        })


# Vue simple pour le monitoring système
def ocr_health_check(request):
    """Point de contrôle de santé du système OCR"""

    # Vérifications de base
    health_data = {
        "status": "ok",
        "timestamp": timezone.now().isoformat(),
        "components": {}
    }

    try:
        # Configuration active
        active_config = OCRConfiguration.objects.filter(is_active=True).exists()
        health_data["components"]["configuration"] = "ok" if active_config else "warning"

        # File d'attente
        queue_size = OCRQueue.objects.filter(status='queued').count()
        processing_items = OCRQueue.objects.filter(status='processing').count()

        health_data["components"]["queue"] = {
            "status": "ok" if queue_size < 100 else "warning",
            "queued_items": queue_size,
            "processing_items": processing_items
        }

        # Résultats récents
        recent_failures = OCRResult.objects.filter(
            status='failed',
            created__gte=timezone.now() - timezone.timedelta(hours=1)
        ).count()

        health_data["components"]["recent_results"] = {
            "status": "ok" if recent_failures < 10 else "error",
            "recent_failures": recent_failures
        }

    except Exception as e:
        health_data["status"] = "error"
        health_data["error"] = str(e)

    return JsonResponse(health_data)
