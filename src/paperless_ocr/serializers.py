from rest_framework import serializers
from .models import OCRResult, OCRQueue, OCRConfiguration
from documents.models import Document
from django.contrib.auth.models import User


class OCRConfigurationSerializer(serializers.ModelSerializer):
    """Sérialiseur pour les configurations OCR"""

    class Meta:
        model = OCRConfiguration
        fields = '__all__'
        read_only_fields = ('created', 'updated')

    def validate(self, data):
        """Validation des données de configuration"""

        # Vérifier les valeurs DPI
        if data.get('dpi', 300) < 150 or data.get('dpi', 300) > 600:
            raise serializers.ValidationError({
                'dpi': 'Le DPI doit être entre 150 et 600'
            })

        # Vérifier la taille max des images
        if data.get('max_image_size', 3000) < 1000 or data.get('max_image_size', 3000) > 8000:
            raise serializers.ValidationError({
                'max_image_size': 'La taille max doit être entre 1000 et 8000 pixels'
            })

        # Vérifier la mémoire max
        if data.get('max_memory_mb', 1024) < 512 or data.get('max_memory_mb', 1024) > 16384:
            raise serializers.ValidationError({
                'max_memory_mb': 'La mémoire max doit être entre 512 MB et 16 GB'
            })

        return data


class OCRResultSerializer(serializers.ModelSerializer):
    """Sérialiseur pour les résultats OCR"""

    document_title = serializers.CharField(source='document.title', read_only=True)
    document_filename = serializers.CharField(source='document.original_filename', read_only=True)
    engine_display = serializers.CharField(source='get_engine_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    word_count = serializers.ReadOnlyField()
    character_count = serializers.ReadOnlyField()
    page_count = serializers.SerializerMethodField()

    class Meta:
        model = OCRResult
        fields = [
            'id', 'document', 'document_title', 'document_filename',
            'engine', 'engine_display', 'text', 'confidence',
            'processing_time', 'metadata', 'page_results', 'bounding_boxes',
            'status', 'status_display', 'error_message', 'configuration',
            'word_count', 'character_count', 'page_count', 'created', 'updated'
        ]
        read_only_fields = ('created', 'updated')

    def get_page_count(self, obj):
        """Nombre de pages traitées"""
        return obj.get_page_count()

    def to_representation(self, instance):
        """Personnaliser la représentation selon le contexte"""
        representation = super().to_representation(instance)

        # Tronquer le texte dans les listes
        request = self.context.get('request')
        if request and request.resolver_match.view_name.endswith('-list'):
            if representation['text'] and len(representation['text']) > 200:
                representation['text'] = representation['text'][:200] + '...'

        # Masquer les métadonnées sensibles
        if representation['metadata']:
            representation['metadata'] = {
                k: v for k, v in representation['metadata'].items()
                if not k.startswith('_')
            }

        return representation


class OCRQueueSerializer(serializers.ModelSerializer):
    """Sérialiseur pour la file d'attente OCR"""

    document_title = serializers.CharField(source='document.title', read_only=True)
    document_filename = serializers.CharField(source='document.original_filename', read_only=True)
    requested_by_username = serializers.CharField(source='requested_by.username', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    duration = serializers.SerializerMethodField()
    estimated_completion = serializers.SerializerMethodField()

    class Meta:
        model = OCRQueue
        fields = [
            'id', 'document', 'document_title', 'document_filename',
            'engines', 'priority', 'priority_display', 'scheduled_for',
            'retries', 'max_retries', 'status', 'status_display',
            'celery_task_id', 'requested_by', 'requested_by_username',
            'duration', 'estimated_completion', 'created', 'started', 'completed'
        ]
        read_only_fields = ('created', 'started', 'completed', 'celery_task_id')

    def get_duration(self, obj):
        """Durée du traitement"""
        if obj.started and obj.completed:
            return (obj.completed - obj.started).total_seconds()
        elif obj.started:
            from django.utils import timezone
            return (timezone.now() - obj.started).total_seconds()
        return None

    def get_estimated_completion(self, obj):
        """Estimation du temps de fin basée sur la position dans la file"""
        if obj.status != OCRQueue.STATUS_QUEUED:
            return None

        # Calculer la position dans la file
        position = OCRQueue.objects.filter(
            priority__gte=obj.priority,
            created__lt=obj.created,
            status=OCRQueue.STATUS_QUEUED
        ).count() + 1

        # Temps moyen de traitement des derniers éléments
        from django.db.models import Avg
        from django.utils import timezone
        from datetime import timedelta

        recent_completed = OCRQueue.objects.filter(
            status=OCRQueue.STATUS_COMPLETED,
            completed__gte=timezone.now() - timedelta(days=7)
        )

        avg_duration = recent_completed.aggregate(
            avg_time=Avg(
                timezone.now() - timezone.F('started'),
                output_field=serializers.DurationField()
            )
        )['avg_time']

        if avg_duration:
            estimated_seconds = avg_duration.total_seconds() * position
            return timezone.now() + timedelta(seconds=estimated_seconds)

        return None


class OCRStatsSerializer(serializers.Serializer):
    """Sérialiseur pour les statistiques OCR"""

    total_results = serializers.IntegerField()
    avg_confidence_tesseract = serializers.FloatField()
    avg_confidence_doctr = serializers.FloatField()
    avg_confidence_hybrid = serializers.FloatField()
    avg_processing_time = serializers.FloatField()
    completed_count = serializers.IntegerField()
    failed_count = serializers.IntegerField()
    processing_count = serializers.IntegerField()
    by_engine = serializers.DictField()


class DocumentOCRRequestSerializer(serializers.Serializer):
    """Sérialiseur pour les requêtes d'OCR de documents"""

    engines = serializers.ListField(
        child=serializers.ChoiceField(choices=['tesseract', 'doctr', 'hybrid']),
        default=['tesseract', 'doctr', 'hybrid'],
        help_text="Liste des moteurs OCR à utiliser"
    )

    priority = serializers.ChoiceField(
        choices=OCRQueue.PRIORITY_CHOICES,
        default=OCRQueue.PRIORITY_NORMAL,
        help_text="Priorité du traitement"
    )

    force = serializers.BooleanField(
        default=False,
        help_text="Forcer le retraitement même si déjà en cours"
    )

    def validate_engines(self, value):
        """Valider la liste des moteurs"""
        if not value:
            raise serializers.ValidationError("Au moins un moteur doit être spécifié")

        valid_engines = ['tesseract', 'doctr', 'hybrid']
        invalid_engines = [eng for eng in value if eng not in valid_engines]

        if invalid_engines:
            raise serializers.ValidationError(
                f"Moteurs invalides: {', '.join(invalid_engines)}"
            )

        # 'hybrid' nécessite les deux autres moteurs
        if 'hybrid' in value and not all(eng in value for eng in ['tesseract', 'doctr']):
            raise serializers.ValidationError(
                "Le moteur 'hybrid' nécessite 'tesseract' et 'doctr'"
            )

        return value


class OCRComparisonSerializer(serializers.Serializer):
    """Sérialiseur pour la comparaison des résultats OCR"""

    document_id = serializers.IntegerField()

    results = serializers.DictField(
        child=serializers.DictField(),
        help_text="Résultats par moteur"
    )

    comparison = serializers.DictField(
        help_text="Métriques de comparaison"
    )


class OCRStatusSerializer(serializers.Serializer):
    """Sérialiseur pour le statut OCR d'un document"""

    document_id = serializers.IntegerField()
    overall_status = serializers.CharField()
    results = OCRResultSerializer(many=True)
    queue_items = OCRQueueSerializer(many=True)
    last_processed = serializers.DateTimeField(allow_null=True)
    total_results = serializers.IntegerField()
    successful_results = serializers.IntegerField()


class BulkOCRRequestSerializer(serializers.Serializer):
    """Sérialiseur pour les requêtes OCR en lot"""

    document_ids = serializers.ListField(
        child=serializers.IntegerField(),
        help_text="Liste des IDs de documents à traiter"
    )

    engines = serializers.ListField(
        child=serializers.ChoiceField(choices=['tesseract', 'doctr', 'hybrid']),
        default=['tesseract', 'doctr', 'hybrid']
    )

    priority = serializers.ChoiceField(
        choices=OCRQueue.PRIORITY_CHOICES,
        default=OCRQueue.PRIORITY_NORMAL
    )

    force = serializers.BooleanField(default=False)

    def validate_document_ids(self, value):
        """Valider que les documents existent"""
        if len(value) > 100:
            raise serializers.ValidationError("Maximum 100 documents par lot")

        existing_ids = set(Document.objects.filter(id__in=value).values_list('id', flat=True))
        missing_ids = set(value) - existing_ids

        if missing_ids:
            raise serializers.ValidationError(
                f"Documents non trouvés: {', '.join(map(str, missing_ids))}"
            )

        return value
