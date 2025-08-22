from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import OCRConfiguration, OCRResult, OCRQueue


@admin.register(OCRConfiguration)
class OCRConfigurationAdmin(admin.ModelAdmin):
    """Administration des configurations OCR"""

    list_display = [
        'name', 'is_active', 'tesseract_lang', 'doctr_model',
        'max_image_size', 'dpi', 'created'
    ]
    list_filter = ['is_active', 'tesseract_lang', 'enhance_image', 'denoise']
    search_fields = ['name', 'tesseract_lang']
    readonly_fields = ['created', 'updated']

    fieldsets = (
        ('Général', {
            'fields': ('name', 'is_active')
        }),
        ('Configuration Tesseract', {
            'fields': ('tesseract_lang', 'tesseract_psm', 'tesseract_oem'),
            'classes': ('collapse',)
        }),
        ('Configuration Doctr', {
            'fields': ('doctr_model', 'doctr_recognition_model'),
            'classes': ('collapse',)
        }),
        ('Traitement d\'images', {
            'fields': ('max_image_size', 'dpi', 'enhance_image', 'denoise'),
            'classes': ('collapse',)
        }),
        ('Performance', {
            'fields': ('max_memory_mb', 'batch_size'),
            'classes': ('collapse',)
        }),
        ('Métadonnées', {
            'fields': ('created', 'updated'),
            'classes': ('collapse',)
        }),
    )

    actions = ['activate_configuration']

    def activate_configuration(self, request, queryset):
        """Action pour activer une configuration"""
        if queryset.count() != 1:
            self.message_user(request, "Sélectionnez exactement une configuration à activer", level='ERROR')
            return

        # Désactiver toutes les autres
        OCRConfiguration.objects.update(is_active=False)

        # Activer la sélectionnée
        config = queryset.first()
        config.is_active = True
        config.save()

        self.message_user(request, f"Configuration '{config.name}' activée avec succès")

    activate_configuration.short_description = "Activer la configuration sélectionnée"


@admin.register(OCRResult)
class OCRResultAdmin(admin.ModelAdmin):
    """Administration des résultats OCR"""

    list_display = [
        'document_link', 'engine', 'status_badge', 'confidence_badge',
        'word_count', 'processing_time', 'created'
    ]
    list_filter = [
        'engine', 'status', 'confidence', 'created',
        ('configuration', admin.RelatedOnlyFieldListFilter)
    ]
    search_fields = ['document__title', 'document__original_filename', 'text']
    readonly_fields = [
        'document', 'engine', 'text_preview', 'metadata_display',
        'page_results_display', 'created', 'updated'
    ]
    date_hierarchy = 'created'

    fieldsets = (
        ('Général', {
            'fields': ('document', 'engine', 'status', 'configuration')
        }),
        ('Résultats', {
            'fields': ('text_preview', 'confidence', 'processing_time'),
        }),
        ('Détails', {
            'fields': ('metadata_display', 'page_results_display', 'error_message'),
            'classes': ('collapse',)
        }),
        ('Dates', {
            'fields': ('created', 'updated'),
            'classes': ('collapse',)
        }),
    )

    def document_link(self, obj):
        """Lien vers le document"""
        if obj.document:
            url = reverse('admin:documents_document_change', args=[obj.document.pk])
            return format_html('<a href="{}">{}</a>', url, obj.document.title)
        return "-"
    document_link.short_description = "Document"

    def status_badge(self, obj):
        """Badge coloré pour le statut"""
        colors = {
            'pending': 'orange',
            'processing': 'blue',
            'completed': 'green',
            'failed': 'red'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = "Statut"

    def confidence_badge(self, obj):
        """Badge coloré pour la confiance"""
        if obj.confidence is None:
            return "-"

        confidence = float(obj.confidence)
        if confidence >= 0.9:
            color = 'green'
        elif confidence >= 0.7:
            color = 'orange'
        else:
            color = 'red'

        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.2%}</span>',
            color, confidence
        )
    confidence_badge.short_description = "Confiance"

    def text_preview(self, obj):
        """Aperçu du texte extrait"""
        if not obj.text:
            return "-"

        preview = obj.text[:200]
        if len(obj.text) > 200:
            preview += "..."

        return format_html('<div style="max-width: 400px; word-wrap: break-word;">{}</div>', preview)
    text_preview.short_description = "Aperçu du texte"

    def metadata_display(self, obj):
        """Affichage formaté des métadonnées"""
        if not obj.metadata:
            return "-"

        import json
        try:
            formatted = json.dumps(obj.metadata, indent=2, ensure_ascii=False)
            return format_html('<pre style="max-height: 200px; overflow: auto;">{}</pre>', formatted)
        except:
            return str(obj.metadata)
    metadata_display.short_description = "Métadonnées"

    def page_results_display(self, obj):
        """Affichage des résultats par page"""
        if not obj.page_results:
            return "-"

        html = "<table style='width: 100%; border-collapse: collapse;'>"
        html += "<tr style='background: #f0f0f0;'><th>Page</th><th>Mots</th><th>Confiance</th></tr>"

        for page in obj.page_results[:10]:  # Limiter à 10 pages
            html += f"<tr><td>{page.get('page', '?')}</td>"
            html += f"<td>{page.get('word_count', '?')}</td>"
            html += f"<td>{page.get('confidence', 0):.2%}</td></tr>"

        if len(obj.page_results) > 10:
            html += f"<tr><td colspan='3'>... et {len(obj.page_results) - 10} pages de plus</td></tr>"

        html += "</table>"
        return mark_safe(html)
    page_results_display.short_description = "Résultats par page"


@admin.register(OCRQueue)
class OCRQueueAdmin(admin.ModelAdmin):
    """Administration de la file d'attente OCR"""

    list_display = [
        'document_link', 'status_badge', 'priority_badge', 'engines_display',
        'requested_by', 'retries', 'created', 'duration_display'
    ]
    list_filter = [
        'status', 'priority', 'engines', 'created',
        ('requested_by', admin.RelatedOnlyFieldListFilter)
    ]
    search_fields = ['document__title', 'celery_task_id']
    readonly_fields = [
        'document', 'celery_task_id', 'duration_display',
        'created', 'started', 'completed'
    ]
    date_hierarchy = 'created'

    fieldsets = (
        ('Général', {
            'fields': ('document', 'engines', 'priority', 'requested_by')
        }),
        ('État', {
            'fields': ('status', 'celery_task_id', 'retries', 'max_retries')
        }),
        ('Planning', {
            'fields': ('scheduled_for', 'duration_display'),
        }),
        ('Dates', {
            'fields': ('created', 'started', 'completed'),
            'classes': ('collapse',)
        }),
    )

    actions = ['cancel_items', 'retry_failed_items']

    def document_link(self, obj):
        """Lien vers le document"""
        if obj.document:
            url = reverse('admin:documents_document_change', args=[obj.document.pk])
            return format_html('<a href="{}">{}</a>', url, obj.document.title)
        return "-"
    document_link.short_description = "Document"

    def status_badge(self, obj):
        """Badge coloré pour le statut"""
        colors = {
            'queued': 'orange',
            'processing': 'blue',
            'completed': 'green',
            'failed': 'red',
            'cancelled': 'gray'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = "Statut"

    def priority_badge(self, obj):
        """Badge pour la priorité"""
        colors = {
            1: 'gray',    # Low
            5: 'blue',    # Normal
            10: 'orange', # High
            20: 'red'     # Urgent
        }
        color = colors.get(obj.priority, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.get_priority_display()
        )
    priority_badge.short_description = "Priorité"

    def engines_display(self, obj):
        """Affichage des moteurs"""
        return ", ".join(obj.engines) if obj.engines else "-"
    engines_display.short_description = "Moteurs"

    def duration_display(self, obj):
        """Affichage de la durée"""
        if obj.started and obj.completed:
            duration = obj.completed - obj.started
            return str(duration).split('.')[0]  # Enlever les microsecondes
        elif obj.started:
            from django.utils import timezone
            duration = timezone.now() - obj.started
            return f"{str(duration).split('.')[0]} (en cours)"
        return "-"
    duration_display.short_description = "Durée"

    def cancel_items(self, request, queryset):
        """Annuler des éléments de la file"""
        cancelled = 0
        for item in queryset.filter(status__in=['queued', 'processing']):
            # Annuler la tâche Celery
            if item.celery_task_id:
                from celery import current_app
                current_app.control.revoke(item.celery_task_id, terminate=True)

            item.status = 'cancelled'
            item.save()
            cancelled += 1

        self.message_user(request, f"{cancelled} élément(s) annulé(s)")
    cancel_items.short_description = "Annuler les éléments sélectionnés"

    def retry_failed_items(self, request, queryset):
        """Relancer les éléments échoués"""
        from .tasks import process_document_ocr

        retried = 0
        for item in queryset.filter(status='failed'):
            # Créer un nouvel élément dans la file
            new_item = OCRQueue.objects.create(
                document=item.document,
                engines=item.engines,
                priority=item.priority,
                requested_by=item.requested_by,
                retries=item.retries + 1
            )
            retried += 1

        self.message_user(request, f"{retried} élément(s) relancé(s)")
    retry_failed_items.short_description = "Relancer les éléments échoués"


# Personnalisation de l'interface admin
admin.site.site_header = "Paperless-ngx OCR Administration"
admin.site.site_title = "OCR Admin"
admin.site.index_title = "Pipeline OCR Hybride"
