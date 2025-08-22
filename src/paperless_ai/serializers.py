"""
Sérialiseurs pour l'API REST du système de classification intelligente

Sérialisation des modèles IA, classifications, embeddings et métriques.
"""

from rest_framework import serializers
from django.contrib.auth.models import User
from documents.models import Document, DocumentType, Correspondent, Tag

from .models import (
    AIModel, DocumentEmbedding, DocumentClassification,
    SearchQuery, AIMetrics, TrainingJob
)


class AIModelSerializer(serializers.ModelSerializer):
    """Sérialiseur pour les modèles IA"""

    owner_name = serializers.CharField(source='owner.username', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    model_type_display = serializers.CharField(source='get_model_type_display', read_only=True)

    class Meta:
        model = AIModel
        fields = [
            'id', 'name', 'model_type', 'model_type_display',
            'model_path', 'config', 'status', 'status_display',
            'version', 'accuracy', 'f1_score', 'training_samples',
            'created', 'updated', 'last_trained', 'owner',
            'owner_name'
        ]
        read_only_fields = [
            'id', 'created', 'updated', 'accuracy', 'f1_score',
            'training_samples', 'last_trained'
        ]


class DocumentEmbeddingSerializer(serializers.ModelSerializer):
    """Sérialiseur pour les embeddings de documents"""

    document_title = serializers.CharField(source='document.title', read_only=True)
    model_name = serializers.CharField(source='model.name', read_only=True)

    class Meta:
        model = DocumentEmbedding
        fields = [
            'id', 'document', 'document_title', 'model', 'model_name',
            'vector_dimension', 'text_length', 'extraction_method',
            'created', 'updated'
        ]
        read_only_fields = [
            'id', 'vector_dimension', 'text_length', 'created', 'updated'
        ]


class DocumentClassificationSerializer(serializers.ModelSerializer):
    """Sérialiseur pour les classifications de documents"""

    document_title = serializers.CharField(source='document.title', read_only=True)
    model_name = serializers.CharField(source='model.name', read_only=True)
    classification_type_display = serializers.CharField(
        source='get_classification_type_display', read_only=True
    )
    predicted_document_type_name = serializers.CharField(
        source='predicted_document_type.name', read_only=True
    )
    predicted_correspondent_name = serializers.CharField(
        source='predicted_correspondent.name', read_only=True
    )
    predicted_tags_names = serializers.SerializerMethodField()
    validated_by_name = serializers.CharField(source='validated_by.username', read_only=True)

    class Meta:
        model = DocumentClassification
        fields = [
            'id', 'document', 'document_title', 'model', 'model_name',
            'classification_type', 'classification_type_display',
            'predicted_class', 'confidence_score',
            'predicted_document_type', 'predicted_document_type_name',
            'predicted_correspondent', 'predicted_correspondent_name',
            'predicted_tags_names', 'is_validated', 'is_applied',
            'validation_feedback', 'processing_time', 'features_used',
            'created', 'validated_at', 'validated_by', 'validated_by_name'
        ]
        read_only_fields = [
            'id', 'predicted_class', 'confidence_score', 'processing_time',
            'features_used', 'created'
        ]

    def get_predicted_tags_names(self, obj):
        """Retourne les noms des tags prédits"""
        return [tag.name for tag in obj.predicted_tags.all()]


class ClassificationValidationSerializer(serializers.Serializer):
    """Sérialiseur pour la validation des classifications"""

    classification_id = serializers.UUIDField()
    feedback = serializers.ChoiceField(
        choices=[('correct', 'Correct'), ('incorrect', 'Incorrect'), ('partial', 'Partiellement correct')]
    )
    apply_to_document = serializers.BooleanField(default=False)
    comments = serializers.CharField(max_length=500, required=False, allow_blank=True)


class SearchQuerySerializer(serializers.ModelSerializer):
    """Sérialiseur pour les requêtes de recherche"""

    user_name = serializers.CharField(source='user.username', read_only=True)
    query_type_display = serializers.CharField(source='get_query_type_display', read_only=True)

    class Meta:
        model = SearchQuery
        fields = [
            'id', 'user', 'user_name', 'query_text', 'query_type',
            'query_type_display', 'results_count', 'response_time',
            'clicked_results', 'filters_applied', 'session_id', 'created'
        ]
        read_only_fields = [
            'id', 'results_count', 'response_time', 'created'
        ]


class SemanticSearchSerializer(serializers.Serializer):
    """Sérialiseur pour les requêtes de recherche sémantique"""

    query = serializers.CharField(max_length=1000)
    top_k = serializers.IntegerField(default=20, min_value=1, max_value=100)
    similarity_threshold = serializers.FloatField(default=0.3, min_value=0.0, max_value=1.0)

    # Filtres optionnels
    document_type = serializers.PrimaryKeyRelatedField(
        queryset=DocumentType.objects.all(), required=False
    )
    correspondent = serializers.PrimaryKeyRelatedField(
        queryset=Correspondent.objects.all(), required=False
    )
    tags = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(), many=True, required=False
    )
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)


class SearchResultSerializer(serializers.Serializer):
    """Sérialiseur pour les résultats de recherche"""

    document_id = serializers.IntegerField()
    title = serializers.CharField()
    similarity = serializers.FloatField()
    correspondent = serializers.CharField(allow_null=True)
    document_type = serializers.CharField(allow_null=True)
    tags = serializers.ListField(child=serializers.CharField())
    created = serializers.DateTimeField()
    modified = serializers.DateTimeField()
    original_filename = serializers.CharField(allow_null=True)


class ClassificationRequestSerializer(serializers.Serializer):
    """Sérialiseur pour les demandes de classification"""

    document_id = serializers.IntegerField()
    force_reclassify = serializers.BooleanField(default=False)
    classification_types = serializers.MultipleChoiceField(
        choices=[
            ('document_type', 'Type de document'),
            ('correspondent', 'Correspondant'),
            ('tag', 'Tags'),
        ],
        default=['document_type']
    )
    confidence_threshold = serializers.FloatField(default=0.8, min_value=0.0, max_value=1.0)


class BatchOperationSerializer(serializers.Serializer):
    """Sérialiseur pour les opérations par lots"""

    document_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1,
        max_length=1000
    )
    operation = serializers.ChoiceField(
        choices=[
            ('classify', 'Classifier'),
            ('generate_embeddings', 'Générer embeddings'),
            ('reprocess', 'Retraiter'),
        ]
    )
    force = serializers.BooleanField(default=False)
    async_processing = serializers.BooleanField(default=True)


class AIMetricsSerializer(serializers.ModelSerializer):
    """Sérialiseur pour les métriques IA"""

    model_name = serializers.CharField(source='model.name', read_only=True)
    metric_type_display = serializers.CharField(source='get_metric_type_display', read_only=True)

    class Meta:
        model = AIMetrics
        fields = [
            'id', 'model', 'model_name', 'metric_type', 'metric_type_display',
            'value', 'target_value', 'period_start', 'period_end',
            'sample_size', 'metadata', 'created'
        ]
        read_only_fields = ['id', 'created']


class TrainingJobSerializer(serializers.ModelSerializer):
    """Sérialiseur pour les tâches d'entraînement"""

    model_name = serializers.CharField(source='model.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    started_by_name = serializers.CharField(source='started_by.username', read_only=True)
    duration = serializers.SerializerMethodField()

    class Meta:
        model = TrainingJob
        fields = [
            'id', 'model', 'model_name', 'training_config', 'dataset_info',
            'status', 'status_display', 'progress', 'final_metrics',
            'error_message', 'created', 'started_at', 'completed_at',
            'started_by', 'started_by_name', 'duration'
        ]
        read_only_fields = [
            'id', 'status', 'progress', 'final_metrics', 'error_message',
            'created', 'started_at', 'completed_at', 'duration'
        ]

    def get_duration(self, obj):
        """Retourne la durée formatée"""
        duration = obj.get_duration()
        if duration:
            return str(duration)
        return None


class TrainingRequestSerializer(serializers.Serializer):
    """Sérialiseur pour les demandes d'entraînement"""

    model_id = serializers.UUIDField()
    training_config = serializers.DictField(required=False)
    use_validated_data_only = serializers.BooleanField(default=True)
    test_split = serializers.FloatField(default=0.2, min_value=0.1, max_value=0.5)

    def validate_training_config(self, value):
        """Valide la configuration d'entraînement"""
        if not value:
            return {
                "epochs": 3,
                "batch_size": 16,
                "learning_rate": 2e-5,
                "warmup_steps": 100
            }

        # Validation des paramètres
        if value.get('epochs', 0) < 1 or value.get('epochs', 0) > 10:
            raise serializers.ValidationError("Le nombre d'époques doit être entre 1 et 10")

        if value.get('batch_size', 0) < 1 or value.get('batch_size', 0) > 64:
            raise serializers.ValidationError("La taille de batch doit être entre 1 et 64")

        return value


class ModelSuggestionSerializer(serializers.Serializer):
    """Sérialiseur pour les suggestions de modèles"""

    document_id = serializers.IntegerField()
    suggestion_types = serializers.MultipleChoiceField(
        choices=[
            ('document_type', 'Type de document'),
            ('correspondent', 'Correspondant'),
            ('tags', 'Tags'),
        ],
        default=['document_type', 'correspondent', 'tags']
    )
    max_suggestions = serializers.IntegerField(default=5, min_value=1, max_value=20)
    min_confidence = serializers.FloatField(default=0.3, min_value=0.0, max_value=1.0)


class SuggestionResultSerializer(serializers.Serializer):
    """Sérialiseur pour les résultats de suggestions"""

    type = serializers.CharField()
    suggestion = serializers.CharField()
    confidence = serializers.FloatField()
    existing_id = serializers.IntegerField(allow_null=True)
    is_new = serializers.BooleanField()
    sample_count = serializers.IntegerField()


class ModelPerformanceSerializer(serializers.Serializer):
    """Sérialiseur pour les performances de modèles"""

    model_id = serializers.UUIDField()
    period_days = serializers.IntegerField(default=7, min_value=1, max_value=90)
    metric_types = serializers.MultipleChoiceField(
        choices=[
            ('classification_accuracy', 'Précision classification'),
            ('search_relevance', 'Pertinence recherche'),
            ('processing_speed', 'Vitesse de traitement'),
            ('user_satisfaction', 'Satisfaction utilisateur'),
        ],
        required=False
    )
