"""
Administration du système de classification intelligente

Interface d'administration Django pour la gestion des modèles IA,
classification de documents, métriques et tâches d'entraînement.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from django.db.models import Count, Avg
from django.shortcuts import redirect
from django.contrib import messages

from .models import (
    AIModel, DocumentEmbedding, DocumentClassification,
    SearchQuery, AIMetrics, TrainingJob
)
from .tasks import train_classification_model, classify_document_task


@admin.register(AIModel)
class AIModelAdmin(admin.ModelAdmin):
    """Administration des modèles IA"""

    list_display = [
        'name', 'model_type', 'language', 'status',
        'accuracy_display', 'owner', 'created', 'updated'
    ]
    list_filter = ['model_type', 'language', 'status', 'created']
    search_fields = ['name', 'description', 'owner__username']
    readonly_fields = ['created', 'updated', 'performance_metrics_display']

    fieldsets = (
        ('Informations générales', {
            'fields': ('name', 'description', 'model_type', 'language', 'owner')
        }),
        ('Configuration', {
            'fields': ('config', 'model_path'),
            'classes': ('collapse',)
        }),
        ('État et performance', {
            'fields': ('status', 'accuracy', 'created', 'updated', 'performance_metrics_display'),
            'classes': ('collapse',)
        }),
    )

    actions = ['train_selected_models', 'activate_models', 'deactivate_models']

    def accuracy_display(self, obj):
        """Affiche la précision avec un indicateur coloré"""
        if obj.accuracy is None:
            return "Non évalué"

        color = "green" if obj.accuracy > 0.8 else "orange" if obj.accuracy > 0.6 else "red"
        return format_html(
            '<span style="color: {};">{:.1%}</span>',
            color, obj.accuracy
        )
    accuracy_display.short_description = "Précision"

    def performance_metrics_display(self, obj):
        """Affiche un résumé des métriques de performance"""
        if not obj.id:
            return "Sauvegardez d'abord le modèle"

        recent_metrics = obj.metrics.filter(
            created__gte=timezone.now() - timezone.timedelta(days=7)
        )

        if not recent_metrics.exists():
            return "Aucune métrique récente"

        metrics_summary = recent_metrics.values('metric_type').annotate(
            avg_value=Avg('value'), count=Count('id')
        )

        html_parts = []
        for metric in metrics_summary:
            html_parts.append(
                f"<li><strong>{metric['metric_type']}</strong>: "
                f"{metric['avg_value']:.3f} (sur {metric['count']} mesures)</li>"
            )

        return format_html("<ul>{}</ul>", "".join(html_parts))
    performance_metrics_display.short_description = "Métriques (7 derniers jours)"

    def train_selected_models(self, request, queryset):
        """Lance l'entraînement des modèles sélectionnés"""
        trained_count = 0
        for model in queryset:
            if model.status != 'training':
                # Créer une tâche d'entraînement
                training_job = TrainingJob.objects.create(
                    model=model,
                    training_config={'source': 'admin_bulk_action'},
                    started_by=request.user
                )

                # Lancer l'entraînement
                train_classification_model.delay(str(training_job.id))
                trained_count += 1

        self.message_user(
            request,
            f"{trained_count} modèle(s) mis en formation",
            messages.SUCCESS
        )
    train_selected_models.short_description = "Entraîner les modèles sélectionnés"

    def activate_models(self, request, queryset):
        """Active les modèles sélectionnés"""
        updated = queryset.update(status='active')
        self.message_user(
            request,
            f"{updated} modèle(s) activé(s)",
            messages.SUCCESS
        )
    activate_models.short_description = "Activer les modèles"

    def deactivate_models(self, request, queryset):
        """Désactive les modèles sélectionnés"""
        updated = queryset.update(status='inactive')
        self.message_user(
            request,
            f"{updated} modèle(s) désactivé(s)",
            messages.SUCCESS
        )
    deactivate_models.short_description = "Désactiver les modèles"


@admin.register(DocumentEmbedding)
class DocumentEmbeddingAdmin(admin.ModelAdmin):
    """Administration des embeddings de documents"""

    list_display = [
        'document_link', 'model_name', 'vector_dimension',
        'text_length', 'created', 'updated'
    ]
    list_filter = ['model__name', 'created', 'updated']
    search_fields = ['document__title', 'document__original_filename', 'model__name']
    readonly_fields = ['created', 'updated', 'vector_dimension', 'embedding_preview']

    fieldsets = (
        ('Document et modèle', {
            'fields': ('document', 'model')
        }),
        ('Embedding', {
            'fields': ('vector_dimension', 'text_length', 'embedding_preview'),
            'classes': ('collapse',)
        }),
        ('Métadonnées', {
            'fields': ('extraction_method', 'created', 'updated'),
            'classes': ('collapse',)
        }),
    )

    def document_link(self, obj):
        """Lien vers le document"""
        if obj.document:
            url = reverse('admin:documents_document_change', args=[obj.document.id])
            return format_html('<a href="{}">{}</a>', url, obj.document.title)
        return "Aucun document"
    document_link.short_description = "Document"

    def model_name(self, obj):
        """Nom du modèle"""
        return obj.model.name if obj.model else "Aucun modèle"
    model_name.short_description = "Modèle"

    def embedding_dimension(self, obj):
        """Dimension de l'embedding"""
        return obj.vector_dimension
    embedding_dimension.short_description = "Dimension"

    def embedding_preview(self, obj):
        """Aperçu de l'embedding"""
        if not obj.embedding_vector:
            return "Aucun embedding"

        preview = obj.embedding_vector[:5] + ["..."] if len(obj.embedding_vector) > 5 else obj.embedding_vector
        return format_html(
            "<code>[{}]</code>",
            ", ".join(f"{x:.3f}" if isinstance(x, (int, float)) else str(x) for x in preview)
        )
    embedding_preview.short_description = "Aperçu embedding"


@admin.register(DocumentClassification)
class DocumentClassificationAdmin(admin.ModelAdmin):
    """Administration des classifications de documents"""

    list_display = [
        'document_link', 'classification_type', 'model_name',
        'confidence_display', 'is_validated', 'validated_by', 'created'
    ]
    list_filter = [
        'classification_type', 'is_validated', 'is_applied',
        'model__name', 'created'
    ]
    search_fields = [
        'document__title', 'document__original_filename',
        'predicted_correspondent__name', 'predicted_document_type__name'
    ]
    readonly_fields = [
        'created', 'validated_at', 'prediction_details_display'
    ]

    fieldsets = (
        ('Document et modèle', {
            'fields': ('document', 'model', 'classification_type')
        }),
        ('Prédictions', {
            'fields': (
                'predicted_document_type', 'predicted_correspondent',
                'predicted_tags', 'confidence_score', 'prediction_details_display'
            )
        }),
        ('Validation', {
            'fields': (
                'is_validated', 'validation_feedback', 'validated_by',
                'validated_at', 'is_applied'
            ),
            'classes': ('collapse',)
        }),
        ('Métadonnées', {
            'fields': ('processing_time', 'features_used', 'created'),
            'classes': ('collapse',)
        }),
    )

    actions = ['validate_classifications', 'apply_to_documents']

    def document_link(self, obj):
        """Lien vers le document"""
        if obj.document:
            url = reverse('admin:documents_document_change', args=[obj.document.id])
            return format_html('<a href="{}">{}</a>', url, obj.document.title)
        return "Aucun document"
    document_link.short_description = "Document"

    def model_name(self, obj):
        """Nom du modèle"""
        return obj.model.name if obj.model else "Aucun modèle"
    model_name.short_description = "Modèle"

    def confidence_display(self, obj):
        """Affiche la confiance avec un indicateur coloré"""
        if obj.confidence_score is None:
            return "Non défini"

        color = "green" if obj.confidence_score > 0.8 else "orange" if obj.confidence_score > 0.5 else "red"
        return format_html(
            '<span style="color: {};">{:.1%}</span>',
            color, obj.confidence_score
        )
    confidence_display.short_description = "Confiance"

    def prediction_details_display(self, obj):
        """Affiche les détails des prédictions"""
        details = []

        if obj.predicted_document_type:
            details.append(f"<li><strong>Type:</strong> {obj.predicted_document_type.name}</li>")

        if obj.predicted_correspondent:
            details.append(f"<li><strong>Correspondant:</strong> {obj.predicted_correspondent.name}</li>")

        if obj.predicted_tags.exists():
            tags = ", ".join(tag.name for tag in obj.predicted_tags.all())
            details.append(f"<li><strong>Tags:</strong> {tags}</li>")

        if not details:
            return "Aucune prédiction"

        return format_html("<ul>{}</ul>", "".join(details))
    prediction_details_display.short_description = "Détails des prédictions"

    def validate_classifications(self, request, queryset):
        """Valide les classifications sélectionnées"""
        updated = queryset.filter(is_validated=False).update(
            is_validated=True,
            validated_by=request.user,
            validated_at=timezone.now()
        )
        self.message_user(
            request,
            f"{updated} classification(s) validée(s)",
            messages.SUCCESS
        )
    validate_classifications.short_description = "Valider les classifications"

    def apply_to_documents(self, request, queryset):
        """Applique les classifications aux documents"""
        applied_count = 0
        for classification in queryset.filter(is_validated=True, is_applied=False):
            document = classification.document

            if classification.predicted_document_type:
                document.document_type = classification.predicted_document_type

            if classification.predicted_correspondent:
                document.correspondent = classification.predicted_correspondent

            # Ajouter les tags
            for tag in classification.predicted_tags.all():
                document.tags.add(tag)

            document.save()

            # Marquer comme appliqué
            classification.is_applied = True
            classification.save()
            applied_count += 1

        self.message_user(
            request,
            f"{applied_count} classification(s) appliquée(s) aux documents",
            messages.SUCCESS
        )
    apply_to_documents.short_description = "Appliquer aux documents"


@admin.register(SearchQuery)
class SearchQueryAdmin(admin.ModelAdmin):
    """Administration des requêtes de recherche"""

    list_display = [
        'query_text_preview', 'query_type', 'user', 'results_count',
        'response_time_display', 'created'
    ]
    list_filter = ['query_type', 'created', 'user']
    search_fields = ['query_text', 'user__username']
    readonly_fields = ['created', 'filters_applied_display']

    fieldsets = (
        ('Requête', {
            'fields': ('user', 'query_text', 'query_type')
        }),
        ('Résultats', {
            'fields': ('results_count', 'response_time', 'filters_applied_display')
        }),
        ('Métadonnées', {
            'fields': ('metadata', 'created'),
            'classes': ('collapse',)
        }),
    )

    def query_text_preview(self, obj):
        """Aperçu du texte de la requête"""
        if len(obj.query_text) > 50:
            return obj.query_text[:47] + "..."
        return obj.query_text
    query_text_preview.short_description = "Requête"

    def response_time_display(self, obj):
        """Affiche le temps de réponse formaté"""
        if obj.response_time is None:
            return "Non mesuré"

        if obj.response_time < 1:
            return f"{obj.response_time*1000:.0f}ms"
        return f"{obj.response_time:.2f}s"
    response_time_display.short_description = "Temps réponse"

    def filters_applied_display(self, obj):
        """Affiche les filtres appliqués"""
        if not obj.filters_applied:
            return "Aucun filtre"

        filters = []
        for key, value in obj.filters_applied.items():
            if isinstance(value, list):
                value = ", ".join(str(v) for v in value)
            filters.append(f"<li><strong>{key}:</strong> {value}</li>")

        return format_html("<ul>{}</ul>", "".join(filters))
    filters_applied_display.short_description = "Filtres appliqués"


@admin.register(AIMetrics)
class AIMetricsAdmin(admin.ModelAdmin):
    """Administration des métriques IA"""

    list_display = [
        'model_name', 'metric_type', 'value_display',
        'period_start', 'period_end', 'created'
    ]
    list_filter = ['metric_type', 'model__name', 'created']
    search_fields = ['model__name', 'metric_type']
    readonly_fields = ['created', 'details_display']

    fieldsets = (
        ('Modèle et métrique', {
            'fields': ('model', 'metric_type', 'value')
        }),
        ('Période', {
            'fields': ('period_start', 'period_end')
        }),
        ('Détails', {
            'fields': ('details_display', 'metadata', 'created'),
            'classes': ('collapse',)
        }),
    )

    def model_name(self, obj):
        """Nom du modèle"""
        return obj.model.name if obj.model else "Aucun modèle"
    model_name.short_description = "Modèle"

    def value_display(self, obj):
        """Affiche la valeur formatée"""
        if obj.metric_type in ['accuracy', 'precision', 'recall', 'f1_score']:
            return f"{obj.value:.1%}"
        elif obj.metric_type == 'response_time':
            return f"{obj.value:.3f}s"
        else:
            return f"{obj.value:.3f}"
    value_display.short_description = "Valeur"

    def details_display(self, obj):
        """Affiche les détails de la métrique"""
        if not obj.metadata:
            return "Aucun détail"

        details = []
        for key, value in obj.metadata.items():
            details.append(f"<li><strong>{key}:</strong> {value}</li>")

        return format_html("<ul>{}</ul>", "".join(details))
    details_display.short_description = "Détails"


@admin.register(TrainingJob)
class TrainingJobAdmin(admin.ModelAdmin):
    """Administration des tâches d'entraînement"""

    list_display = [
        'model_name', 'status_display', 'progress_display',
        'started_by', 'created', 'completed_at', 'duration_display'
    ]
    list_filter = ['status', 'model__name', 'created', 'started_by']
    search_fields = ['model__name', 'started_by__username']
    readonly_fields = [
        'created', 'completed_at', 'duration_display',
        'training_logs_display', 'results_display'
    ]

    fieldsets = (
        ('Tâche', {
            'fields': ('model', 'status', 'started_by')
        }),
        ('Configuration', {
            'fields': ('training_config', 'dataset_info'),
            'classes': ('collapse',)
        }),
        ('Progression', {
            'fields': ('progress', 'current_step', 'total_steps')
        }),
        ('Résultats', {
            'fields': (
                'final_accuracy', 'training_time_seconds',
                'created', 'completed_at', 'duration_display'
            ),
            'classes': ('collapse',)
        }),
        ('Détails', {
            'fields': ('training_logs_display', 'results_display', 'metadata'),
            'classes': ('collapse',)
        }),
    )

    actions = ['cancel_training_jobs']

    def model_name(self, obj):
        """Nom du modèle"""
        return obj.model.name if obj.model else "Aucun modèle"
    model_name.short_description = "Modèle"

    def status_display(self, obj):
        """Affiche le statut avec une couleur"""
        colors = {
            'pending': 'orange',
            'running': 'blue',
            'completed': 'green',
            'failed': 'red',
            'cancelled': 'gray'
        }
        color = colors.get(obj.status, 'black')
        return format_html(
            '<span style="color: {};">{}</span>',
            color, obj.get_status_display()
        )
    status_display.short_description = "Statut"

    def progress_display(self, obj):
        """Affiche la progression"""
        if obj.progress is None:
            return "Non démarré"

        if obj.total_steps and obj.current_step:
            return f"{obj.progress:.1%} ({obj.current_step}/{obj.total_steps})"
        return f"{obj.progress:.1%}"
    progress_display.short_description = "Progression"

    def duration_display(self, obj):
        """Affiche la durée d'entraînement"""
        if obj.training_time_seconds:
            hours = obj.training_time_seconds // 3600
            minutes = (obj.training_time_seconds % 3600) // 60
            seconds = obj.training_time_seconds % 60

            if hours > 0:
                return f"{hours}h {minutes}m {seconds}s"
            elif minutes > 0:
                return f"{minutes}m {seconds}s"
            else:
                return f"{seconds}s"

        if obj.created and obj.completed_at:
            duration = obj.completed_at - obj.created
            return str(duration).split('.')[0]  # Enlever les microsecondes

        return "En cours..." if obj.status == 'running' else "Non calculé"
    duration_display.short_description = "Durée"

    def training_logs_display(self, obj):
        """Affiche les logs d'entraînement"""
        if not obj.training_logs:
            return "Aucun log"

        # Afficher les dernières lignes des logs
        logs = obj.training_logs.split('\n')[-10:]  # 10 dernières lignes
        return format_html(
            "<pre style='background: #f5f5f5; padding: 10px; font-size: 12px;'>{}</pre>",
            '\n'.join(logs)
        )
    training_logs_display.short_description = "Logs d'entraînement"

    def results_display(self, obj):
        """Affiche les résultats d'entraînement"""
        if not obj.training_results:
            return "Aucun résultat"

        results = []
        for key, value in obj.training_results.items():
            if isinstance(value, float):
                if key in ['accuracy', 'precision', 'recall', 'f1_score']:
                    value = f"{value:.1%}"
                else:
                    value = f"{value:.3f}"
            results.append(f"<li><strong>{key}:</strong> {value}</li>")

        return format_html("<ul>{}</ul>", "".join(results))
    results_display.short_description = "Résultats"

    def cancel_training_jobs(self, request, queryset):
        """Annule les tâches d'entraînement sélectionnées"""
        cancelled_count = queryset.filter(status__in=['pending', 'running']).update(
            status='cancelled',
            completed_at=timezone.now()
        )
        self.message_user(
            request,
            f"{cancelled_count} tâche(s) d'entraînement annulée(s)",
            messages.SUCCESS
        )
    cancel_training_jobs.short_description = "Annuler les tâches d'entraînement"
