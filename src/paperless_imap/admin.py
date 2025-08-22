"""
Interface d'administration Django pour le module IMAP Paperless-ngx

Gestion complète des comptes IMAP, e-mails, pièces jointes, événements
et logs de synchronisation via l'interface d'administration Django.
"""

import logging
from datetime import datetime, timedelta

from django.contrib import admin
from django.contrib import messages
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.db.models import Count, Q
from django.urls import reverse
from django.shortcuts import redirect
from django.http import HttpResponseRedirect

from .models import (
    IMAPAccount, EmailMessage, EmailAttachment,
    EmailEvent, SyncLog
)
from .tasks import sync_imap_account, process_email_attachment
from .imap_engine import IMAPProcessor, IMAPConnectionError, IMAPAuthenticationError


logger = logging.getLogger(__name__)


class SyncLogInline(admin.TabularInline):
    """Inline pour les logs de synchronisation dans IMAPAccount"""
    model = SyncLog
    extra = 0
    readonly_fields = [
        'start_time', 'end_time', 'status', 'emails_processed',
        'attachments_processed', 'errors_count', 'duration_display'
    ]
    fields = [
        'start_time', 'end_time', 'status', 'emails_processed',
        'attachments_processed', 'errors_count', 'duration_display'
    ]
    ordering = ['-start_time']
    max_num = 10  # Limite l'affichage aux 10 derniers logs

    def duration_display(self, obj):
        """Affichage formaté de la durée"""
        duration = obj.get_duration()
        if duration:
            total_seconds = int(duration.total_seconds())
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            if hours:
                return f"{hours}h {minutes}m {seconds}s"
            elif minutes:
                return f"{minutes}m {seconds}s"
            else:
                return f"{seconds}s"
        return "-"
    duration_display.short_description = "Durée"


@admin.register(IMAPAccount)
class IMAPAccountAdmin(admin.ModelAdmin):
    """Administration des comptes IMAP"""

    list_display = [
        'name', 'server', 'username', 'is_active', 'auth_method',
        'last_sync', 'emails_count', 'connection_status', 'sync_action'
    ]
    list_filter = [
        'is_active', 'auth_method', 'use_ssl', 'use_starttls',
        'created', 'last_sync'
    ]
    search_fields = ['name', 'server', 'username', 'description']
    readonly_fields = (
        'id', 'created', 'updated', 'last_sync',
        'sync_errors'
    )

    fieldsets = (
        (_('Informations générales'), {
            'fields': ('name', 'description', 'owner', 'is_active')
        }),
        (_('Configuration serveur'), {
            'fields': (
                'server', 'port', 'use_ssl', 'use_starttls',
                'auth_method', 'username'
            )
        }),
        (_('Authentification'), {
            'fields': ('password', 'oauth2_client_id', 'oauth2_client_secret'),
            'classes': ('collapse',)
        }),
        (_('Configuration synchronisation'), {
            'fields': (
                'folders_to_sync', 'auto_sync_enabled', 'sync_interval',
                'max_emails_per_sync', 'keep_read_emails'
            )
        }),
        (_('Configuration avancée'), {
            'fields': (
                'extract_events', 'event_extraction_keywords',
                'email_processing_enabled', 'attachment_processing_enabled'
            ),
            'classes': ('collapse',)
        }),
        (_('Informations système'), {
            'fields': (
                'id', 'created', 'updated', 'last_sync',
                'sync_errors'
            ),
            'classes': ('collapse',)
        }),
    )

    inlines = [SyncLogInline]
    actions = [
        'sync_selected_accounts', 'test_connections',
        'enable_accounts', 'disable_accounts'
    ]

    def get_queryset(self, request):
        """Ajout des statistiques dans la requête"""
        queryset = super().get_queryset(request)
        return queryset.annotate(
            emails_count=Count('emails', distinct=True)
        )

    def emails_count(self, obj):
        """Nombre d'e-mails du compte"""
        return obj.emails_count
    emails_count.short_description = "E-mails"
    emails_count.admin_order_field = 'emails_count'

    def connection_status(self, obj):
        """Statut de la connexion avec icône"""
        if obj.last_sync_status == 'success':
            color = 'green'
            icon = '✓'
            title = 'Connexion OK'
        elif obj.last_sync_status == 'error':
            color = 'red'
            icon = '✗'
            title = 'Erreur de connexion'
        else:
            color = 'orange'
            icon = '?'
            title = 'Non testé'

        return format_html(
            '<span style="color: {};" title="{}">{}</span>',
            color, title, icon
        )
    connection_status.short_description = "Connexion"

    def sync_action(self, obj):
        """Bouton d'action de synchronisation"""
        if obj.is_active:
            url = reverse('admin:paperless_imap_imapaccount_sync', args=[obj.pk])
            return format_html(
                '<a class="button" href="{}">Synchroniser</a>',
                url
            )
        return "-"
    sync_action.short_description = "Action"

    def connection_test_result(self, obj):
        """Affichage du résultat du test de connexion"""
        return "Utilisez l'action 'Tester les connexions' pour vérifier"
    connection_test_result.short_description = "Test de connexion"

    def get_urls(self):
        """Ajout d'URLs personnalisées"""
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:account_id>/sync/',
                self.admin_site.admin_view(self.sync_account_view),
                name='paperless_imap_imapaccount_sync'
            ),
            path(
                '<int:account_id>/test/',
                self.admin_site.admin_view(self.test_connection_view),
                name='paperless_imap_imapaccount_test'
            ),
        ]
        return custom_urls + urls

    def sync_account_view(self, request, account_id):
        """Vue pour synchroniser un compte spécifique"""
        try:
            account = IMAPAccount.objects.get(pk=account_id)
            task = sync_imap_account.delay(str(account.id))

            messages.success(
                request,
                f"Synchronisation lancée pour le compte '{account.name}' (Tâche: {task.id})"
            )
        except IMAPAccount.DoesNotExist:
            messages.error(request, "Compte IMAP introuvable")
        except Exception as e:
            messages.error(request, f"Erreur lors du lancement de la synchronisation: {e}")

        return HttpResponseRedirect(
            reverse('admin:paperless_imap_imapaccount_changelist')
        )

    def test_connection_view(self, request, account_id):
        """Vue pour tester la connexion d'un compte"""
        try:
            account = IMAPAccount.objects.get(pk=account_id)
            processor = IMAPProcessor(account)

            if processor.connect():
                processor.disconnect()
                messages.success(
                    request,
                    f"Connexion réussie pour le compte '{account.name}'"
                )
            else:
                messages.error(
                    request,
                    f"Échec de connexion pour le compte '{account.name}'"
                )

        except IMAPAccount.DoesNotExist:
            messages.error(request, "Compte IMAP introuvable")
        except IMAPAuthenticationError as e:
            messages.error(request, f"Erreur d'authentification: {e}")
        except IMAPConnectionError as e:
            messages.error(request, f"Erreur de connexion: {e}")
        except Exception as e:
            messages.error(request, f"Erreur inattendue: {e}")

        return HttpResponseRedirect(
            reverse('admin:paperless_imap_imapaccount_change', args=[account_id])
        )

    def sync_selected_accounts(self, request, queryset):
        """Action pour synchroniser les comptes sélectionnés"""
        active_accounts = queryset.filter(is_active=True)
        task_count = 0

        for account in active_accounts:
            try:
                sync_imap_account.delay(str(account.id))
                task_count += 1
            except Exception as e:
                logger.error(f"Erreur lancement sync {account.name}: {e}")

        if task_count > 0:
            messages.success(
                request,
                f"Synchronisation lancée pour {task_count} compte(s)"
            )
        else:
            messages.warning(request, "Aucune synchronisation lancée")

    sync_selected_accounts.short_description = "Synchroniser les comptes sélectionnés"

    def test_connections(self, request, queryset):
        """Action pour tester les connexions des comptes sélectionnés"""
        success_count = 0
        error_count = 0

        for account in queryset:
            try:
                processor = IMAPProcessor(account)
                if processor.connect():
                    processor.disconnect()
                    success_count += 1
                else:
                    error_count += 1
            except Exception:
                error_count += 1

        if success_count > 0:
            messages.success(request, f"{success_count} connexion(s) réussie(s)")
        if error_count > 0:
            messages.error(request, f"{error_count} connexion(s) échouée(s)")

    test_connections.short_description = "Tester les connexions"

    def enable_accounts(self, request, queryset):
        """Active les comptes sélectionnés"""
        updated = queryset.update(is_active=True)
        messages.success(request, f"{updated} compte(s) activé(s)")

    enable_accounts.short_description = "Activer les comptes"

    def disable_accounts(self, request, queryset):
        """Désactive les comptes sélectionnés"""
        updated = queryset.update(is_active=False)
        messages.success(request, f"{updated} compte(s) désactivé(s)")

    disable_accounts.short_description = "Désactiver les comptes"


class EmailAttachmentInline(admin.TabularInline):
    """Inline pour les pièces jointes dans EmailMessage"""
    model = EmailAttachment
    extra = 0
    readonly_fields = [
        'filename', 'size', 'content_type', 'is_supported_format',
        'is_processed', 'document_link', 'created'
    ]
    fields = [
        'filename', 'size', 'content_type', 'is_supported_format',
        'is_processed', 'document_link'
    ]

    def document_link(self, obj):
        """Lien vers le document créé"""
        if obj.document:
            url = reverse('admin:documents_document_change', args=[obj.document.pk])
            return format_html('<a href="{}" target="_blank">Document #{}</a>', url, obj.document.pk)
        return "-"
    document_link.short_description = "Document"


class EmailEventInline(admin.TabularInline):
    """Inline pour les événements dans EmailMessage"""
    model = EmailEvent
    extra = 0
    readonly_fields = [
        'event_type', 'title', 'start_date', 'confidence_score',
        'is_validated', 'created'
    ]
    fields = [
        'event_type', 'title', 'start_date', 'confidence_score',
        'is_validated'
    ]


@admin.register(EmailMessage)
class EmailMessageAdmin(admin.ModelAdmin):
    """Administration des e-mails"""

    list_display = [
        'subject', 'sender', 'account', 'folder', 'date_sent',
        'category', 'priority', 'is_read', 'is_flagged',
        'attachments_count', 'events_count'
    ]
    list_filter = [
        'account', 'folder', 'category', 'priority',
        'is_read', 'is_flagged', 'is_processed',
        'date_sent', 'date_received'
    ]
    search_fields = ['subject', 'sender', 'body_text', 'message_id']
    readonly_fields = [
        'id', 'message_id', 'date_sent', 'date_received',
        'created', 'updated', 'body_html_preview'
    ]
    date_hierarchy = 'date_sent'

    fieldsets = (
        (_('Informations e-mail'), {
            'fields': (
                'subject', 'sender', 'recipient', 'account',
                'folder', 'message_id'
            )
        }),
        (_('Dates'), {
            'fields': ('date_sent', 'date_received', 'created', 'updated')
        }),
        (_('Classification'), {
            'fields': ('category', 'priority', 'is_read', 'is_flagged', 'is_processed')
        }),
        (_('Contenu'), {
            'fields': ('body_text', 'body_html_preview'),
            'classes': ('collapse',)
        }),
        (_('Métadonnées'), {
            'fields': ('headers', 'size', 'id'),
            'classes': ('collapse',)
        }),
    )

    inlines = [EmailAttachmentInline, EmailEventInline]
    actions = [
        'mark_as_read', 'mark_as_unread', 'categorize_professional',
        'categorize_personal', 'process_attachments'
    ]

    def get_queryset(self, request):
        """Ajout des statistiques dans la requête"""
        queryset = super().get_queryset(request)
        return queryset.annotate(
            attachments_count=Count('attachments', distinct=True),
            events_count=Count('events', distinct=True)
        )

    def attachments_count(self, obj):
        """Nombre de pièces jointes"""
        return obj.attachments_count
    attachments_count.short_description = "PJ"
    attachments_count.admin_order_field = 'attachments_count'

    def events_count(self, obj):
        """Nombre d'événements extraits"""
        return obj.events_count
    events_count.short_description = "Événements"
    events_count.admin_order_field = 'events_count'

    def body_html_preview(self, obj):
        """Aperçu du contenu HTML"""
        if obj.body_html:
            # Limitation à 500 caractères et nettoyage basique
            preview = obj.body_html[:500]
            if len(obj.body_html) > 500:
                preview += "..."
            return format_html('<div style="max-height: 200px; overflow: auto; border: 1px solid #ccc; padding: 10px;">{}</div>', preview)
        return "Aucun contenu HTML"
    body_html_preview.short_description = "Aperçu HTML"

    def mark_as_read(self, request, queryset):
        """Marque les e-mails comme lus"""
        updated = queryset.update(is_read=True)
        messages.success(request, f"{updated} e-mail(s) marqué(s) comme lu(s)")

    mark_as_read.short_description = "Marquer comme lu"

    def mark_as_unread(self, request, queryset):
        """Marque les e-mails comme non lus"""
        updated = queryset.update(is_read=False)
        messages.success(request, f"{updated} e-mail(s) marqué(s) comme non lu(s)")

    mark_as_unread.short_description = "Marquer comme non lu"

    def categorize_professional(self, request, queryset):
        """Catégorise les e-mails comme professionnels"""
        updated = queryset.update(category='professional')
        messages.success(request, f"{updated} e-mail(s) catégorisé(s) comme professionnels")

    categorize_professional.short_description = "Catégoriser comme professionnel"

    def categorize_personal(self, request, queryset):
        """Catégorise les e-mails comme personnels"""
        updated = queryset.update(category='personal')
        messages.success(request, f"{updated} e-mail(s) catégorisé(s) comme personnels")

    categorize_personal.short_description = "Catégoriser comme personnel"

    def process_attachments(self, request, queryset):
        """Lance le traitement des pièces jointes"""
        task_count = 0

        for email in queryset:
            attachments = email.attachments.filter(
                is_processed=False,
                is_supported_format=True
            )
            for attachment in attachments:
                try:
                    process_email_attachment.delay(str(attachment.id))
                    task_count += 1
                except Exception as e:
                    logger.error(f"Erreur lancement traitement PJ {attachment.filename}: {e}")

        if task_count > 0:
            messages.success(
                request,
                f"Traitement lancé pour {task_count} pièce(s) jointe(s)"
            )
        else:
            messages.warning(request, "Aucune pièce jointe à traiter")

    process_attachments.short_description = "Traiter les pièces jointes"


@admin.register(EmailAttachment)
class EmailAttachmentAdmin(admin.ModelAdmin):
    """Administration des pièces jointes"""

    list_display = [
        'filename', 'email_subject', 'size_display', 'content_type',
        'is_supported_format', 'is_processed', 'document_link',
        'created'
    ]
    list_filter = [
        'is_processed', 'is_supported_format', 'content_type',
        'created', 'email__account'
    ]
    search_fields = ['filename', 'email__subject', 'email__sender']
    readonly_fields = [
        'id', 'size', 'content_type',
        'is_supported_format', 'created', 'updated'
    ]

    fieldsets = (
        (_('Informations fichier'), {
            'fields': ('filename', 'size', 'content_type')
        }),
        (_('E-mail source'), {
            'fields': ('email',)
        }),
        (_('Traitement'), {
            'fields': ('is_processed', 'document', 'processing_error')
        }),
        (_('Métadonnées'), {
            'fields': ('is_supported_format', 'id', 'created', 'updated'),
            'classes': ('collapse',)
        }),
    )

    actions = ['process_selected_attachments', 'mark_as_processed']

    def email_subject(self, obj):
        """Sujet de l'e-mail source"""
        return obj.email.subject[:50] + ("..." if len(obj.email.subject) > 50 else "")
    email_subject.short_description = "Sujet e-mail"

    def size_display(self, obj):
        """Affichage formaté de la taille"""
        if obj.size < 1024:
            return f"{obj.size} B"
        elif obj.size < 1024 * 1024:
            return f"{obj.size / 1024:.1f} KB"
        else:
            return f"{obj.size / (1024 * 1024):.1f} MB"
    size_display.short_description = "Taille"
    size_display.admin_order_field = 'size'

    def document_link(self, obj):
        """Lien vers le document créé"""
        if obj.document:
            url = reverse('admin:documents_document_change', args=[obj.document.pk])
            return format_html('<a href="{}" target="_blank">Document #{}</a>', url, obj.document.pk)
        return "-"
    document_link.short_description = "Document"

    def process_selected_attachments(self, request, queryset):
        """Traite les pièces jointes sélectionnées"""
        processable = queryset.filter(
            is_processed=False,
            is_supported_format=True
        )

        task_count = 0
        for attachment in processable:
            try:
                process_email_attachment.delay(str(attachment.id))
                task_count += 1
            except Exception as e:
                logger.error(f"Erreur lancement traitement {attachment.filename}: {e}")

        if task_count > 0:
            messages.success(
                request,
                f"Traitement lancé pour {task_count} pièce(s) jointe(s)"
            )
        else:
            messages.warning(request, "Aucune pièce jointe à traiter")

    process_selected_attachments.short_description = "Traiter les pièces jointes"

    def mark_as_processed(self, request, queryset):
        """Marque les pièces jointes comme traitées"""
        updated = queryset.update(is_processed=True)
        messages.success(request, f"{updated} pièce(s) jointe(s) marquée(s) comme traitée(s)")

    mark_as_processed.short_description = "Marquer comme traitées"


@admin.register(EmailEvent)
class EmailEventAdmin(admin.ModelAdmin):
    """Administration des événements extraits"""

    list_display = [
        'title', 'event_type', 'start_date', 'email_subject',
        'confidence_score', 'is_validated', 'created'
    ]
    list_filter = [
        'event_type', 'is_validated', 'all_day',
        'start_date', 'created', 'email__account'
    ]
    search_fields = ['title', 'description', 'location', 'email__subject']
    readonly_fields = [
        'id', 'confidence_score', 'source_text',
        'created', 'updated'
    ]
    date_hierarchy = 'start_date'

    fieldsets = (
        (_('Informations événement'), {
            'fields': (
                'title', 'description', 'event_type',
                'start_date', 'end_date', 'all_day', 'location'
            )
        }),
        (_('E-mail source'), {
            'fields': ('email',)
        }),
        (_('Validation'), {
            'fields': ('is_validated', 'confidence_score')
        }),
        (_('Données techniques'), {
            'fields': ('source_text', 'id', 'created', 'updated'),
            'classes': ('collapse',)
        }),
    )

    actions = ['validate_events', 'invalidate_events']

    def email_subject(self, obj):
        """Sujet de l'e-mail source"""
        return obj.email.subject[:50] + ("..." if len(obj.email.subject) > 50 else "")
    email_subject.short_description = "Sujet e-mail"

    def validate_events(self, request, queryset):
        """Valide les événements sélectionnés"""
        updated = queryset.update(is_validated=True)
        messages.success(request, f"{updated} événement(s) validé(s)")

    validate_events.short_description = "Valider les événements"

    def invalidate_events(self, request, queryset):
        """Invalide les événements sélectionnés"""
        updated = queryset.update(is_validated=False)
        messages.success(request, f"{updated} événement(s) invalidé(s)")

    invalidate_events.short_description = "Invalider les événements"


@admin.register(SyncLog)
class SyncLogAdmin(admin.ModelAdmin):
    """Administration des logs de synchronisation"""

    list_display = [
        'account', 'start_time', 'end_time', 'status',
        'emails_processed', 'attachments_processed',
        'errors_count', 'duration_display'
    ]
    list_filter = [
        'status', 'account', 'start_time'
    ]
    search_fields = ['account__name', 'error_message']
    readonly_fields = [
        'id', 'account', 'start_time', 'end_time', 'status',
        'emails_processed', 'attachments_processed',
        'errors_count', 'error_message', 'duration_display'
    ]
    date_hierarchy = 'start_time'

    fieldsets = (
        (_('Synchronisation'), {
            'fields': ('account', 'start_time', 'end_time', 'status')
        }),
        (_('Résultats'), {
            'fields': (
                'emails_processed', 'attachments_processed',
                'errors_count', 'duration_display'
            )
        }),
        (_('Erreurs'), {
            'fields': ('error_message',),
            'classes': ('collapse',)
        }),
        (_('Métadonnées'), {
            'fields': ('id',),
            'classes': ('collapse',)
        }),
    )

    def duration_display(self, obj):
        """Affichage formaté de la durée"""
        duration = obj.get_duration()
        if duration:
            total_seconds = int(duration.total_seconds())
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            if hours:
                return f"{hours}h {minutes}m {seconds}s"
            elif minutes:
                return f"{minutes}m {seconds}s"
            else:
                return f"{seconds}s"
        return "-"
    duration_display.short_description = "Durée"

    def has_add_permission(self, request):
        """Empêche la création manuelle de logs"""
        return False

    def has_change_permission(self, request, obj=None):
        """Empêche la modification des logs"""
        return False


# Configuration globale de l'admin
admin.site.site_header = "Paperless-ngx Administration"
admin.site.site_title = "Paperless-ngx"
admin.site.index_title = "Administration Paperless-ngx"
