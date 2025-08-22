"""
Sérialiseurs pour les APIs REST du module IMAP Paperless-ngx

Gestion de la sérialisation et validation des données pour les comptes IMAP,
e-mails, pièces jointes et événements.
"""

from rest_framework import serializers
from django.contrib.auth.models import User
from django.utils import timezone
from typing import Dict, Any

from .models import (
    IMAPAccount, EmailMessage, EmailAttachment,
    EmailEvent, SyncLog
)


class IMAPAccountSerializer(serializers.ModelSerializer):
    """Sérialiseur pour les comptes IMAP"""

    # Champs en lecture seule
    sync_status = serializers.SerializerMethodField()
    last_sync_display = serializers.SerializerMethodField()
    email_count = serializers.SerializerMethodField()
    attachment_count = serializers.SerializerMethodField()

    # Mot de passe write-only
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = IMAPAccount
        fields = [
            'id', 'name', 'server', 'port', 'use_ssl', 'use_starttls',
            'auth_method', 'username', 'password',
            'oauth2_client_id', 'oauth2_client_secret',
            'oauth2_refresh_token', 'oauth2_access_token', 'oauth2_token_expires',
            'folders_to_sync', 'attachment_extensions', 'max_attachment_size',
            'sender_whitelist', 'sender_blacklist', 'subject_keywords',
            'sync_interval', 'auto_process_attachments', 'auto_extract_events',
            'auto_categorize', 'is_active', 'last_sync', 'last_uid',
            'sync_errors', 'created', 'updated', 'owner',
            'sync_status', 'last_sync_display', 'email_count', 'attachment_count'
        ]
        read_only_fields = [
            'id', 'last_sync', 'last_uid', 'sync_errors', 'created', 'updated',
            'oauth2_access_token', 'oauth2_token_expires',
            'sync_status', 'last_sync_display', 'email_count', 'attachment_count'
        ]
        extra_kwargs = {
            'oauth2_client_secret': {'write_only': True},
            'oauth2_refresh_token': {'write_only': True},
        }

    def get_sync_status(self, obj: IMAPAccount) -> Dict[str, Any]:
        """Retourne le statut de synchronisation"""
        return obj.get_sync_status()

    def get_last_sync_display(self, obj: IMAPAccount) -> str:
        """Affichage formaté de la dernière synchronisation"""
        if not obj.last_sync:
            return "Jamais synchronisé"

        # Calcul du temps écoulé
        now = timezone.now()
        delta = now - obj.last_sync

        if delta.days > 0:
            return f"Il y a {delta.days} jour(s)"
        elif delta.seconds > 3600:
            hours = delta.seconds // 3600
            return f"Il y a {hours} heure(s)"
        elif delta.seconds > 60:
            minutes = delta.seconds // 60
            return f"Il y a {minutes} minute(s)"
        else:
            return "Il y a quelques secondes"

    def get_email_count(self, obj: IMAPAccount) -> int:
        """Nombre d'e-mails dans le compte"""
        return obj.emails.count()

    def get_attachment_count(self, obj: IMAPAccount) -> int:
        """Nombre total de pièces jointes"""
        return EmailAttachment.objects.filter(email__account=obj).count()

    def create(self, validated_data):
        """Création d'un compte avec gestion du mot de passe"""
        password = validated_data.pop('password', None)

        # Assignation du propriétaire
        if 'owner' not in validated_data:
            validated_data['owner'] = self.context['request'].user

        account = super().create(validated_data)

        # Chiffrement du mot de passe
        if password:
            account.set_password(password)
            account.save(update_fields=['encrypted_password'])

        return account

    def update(self, instance, validated_data):
        """Mise à jour avec gestion du mot de passe"""
        password = validated_data.pop('password', None)

        account = super().update(instance, validated_data)

        # Mise à jour du mot de passe si fourni
        if password is not None:  # Permet de vider le mot de passe avec une chaîne vide
            account.set_password(password)
            account.save(update_fields=['encrypted_password'])

        return account

    def validate(self, data):
        """Validation personnalisée"""
        # Validation OAuth2
        if data.get('auth_method') == IMAPAccount.AUTH_OAUTH2:
            required_oauth_fields = ['oauth2_client_id', 'oauth2_client_secret']
            for field in required_oauth_fields:
                if not data.get(field):
                    raise serializers.ValidationError(
                        f"Le champ '{field}' est requis pour l'authentification OAuth2"
                    )

        # Validation port
        port = data.get('port')
        if port and (port < 1 or port > 65535):
            raise serializers.ValidationError("Le port doit être entre 1 et 65535")

        # Validation intervalle de synchronisation
        sync_interval = data.get('sync_interval')
        if sync_interval and sync_interval < 1:
            raise serializers.ValidationError("L'intervalle de synchronisation doit être d'au moins 1 minute")

        return data


class EmailMessageSerializer(serializers.ModelSerializer):
    """Sérialiseur pour les e-mails"""

    # Champs calculés
    account_name = serializers.CharField(source='account.name', read_only=True)
    attachment_count = serializers.SerializerMethodField()
    has_events = serializers.SerializerMethodField()
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)

    class Meta:
        model = EmailMessage
        fields = [
            'id', 'account', 'account_name', 'message_id', 'uid', 'folder',
            'subject', 'sender', 'recipients', 'cc_recipients', 'bcc_recipients',
            'date_sent', 'date_received', 'body_text', 'body_html',
            'is_read', 'is_flagged', 'priority', 'priority_display',
            'category', 'category_display', 'confidence_score',
            'extracted_keywords', 'detected_language', 'is_processed',
            'processing_errors', 'created', 'updated',
            'attachment_count', 'has_events'
        ]
        read_only_fields = [
            'id', 'message_id', 'uid', 'date_received', 'detected_language',
            'is_processed', 'processing_errors', 'created', 'updated',
            'account_name', 'category_display', 'priority_display',
            'attachment_count', 'has_events'
        ]

    def get_attachment_count(self, obj: EmailMessage) -> int:
        """Nombre de pièces jointes"""
        return obj.get_attachment_count()

    def get_has_events(self, obj: EmailMessage) -> bool:
        """Vérifie si l'e-mail a des événements extraits"""
        return obj.events.exists()


class EmailMessageDetailSerializer(EmailMessageSerializer):
    """Sérialiseur détaillé pour les e-mails avec pièces jointes et événements"""

    attachments = serializers.SerializerMethodField()
    events = serializers.SerializerMethodField()

    class Meta(EmailMessageSerializer.Meta):
        fields = EmailMessageSerializer.Meta.fields + ['attachments', 'events']

    def get_attachments(self, obj: EmailMessage):
        """Pièces jointes de l'e-mail"""
        attachments = obj.attachments.all()
        return EmailAttachmentSerializer(attachments, many=True, context=self.context).data

    def get_events(self, obj: EmailMessage):
        """Événements extraits de l'e-mail"""
        events = obj.events.all()
        return EmailEventSerializer(events, many=True, context=self.context).data


class EmailAttachmentSerializer(serializers.ModelSerializer):
    """Sérialiseur pour les pièces jointes"""

    # Champs calculés
    size_display = serializers.SerializerMethodField()
    extension = serializers.SerializerMethodField()
    document_title = serializers.CharField(source='document.title', read_only=True)
    is_image = serializers.SerializerMethodField()
    is_document = serializers.SerializerMethodField()

    class Meta:
        model = EmailAttachment
        fields = [
            'id', 'email', 'filename', 'content_type', 'size', 'size_display',
            'extension', 'document', 'document_title', 'is_processed',
            'is_supported_format', 'processing_error', 'extracted_text',
            'detected_language', 'created', 'updated',
            'is_image', 'is_document'
        ]
        read_only_fields = [
            'id', 'size', 'size_display', 'extension', 'document_title',
            'extracted_text', 'detected_language', 'created', 'updated',
            'is_image', 'is_document'
        ]

    def get_size_display(self, obj: EmailAttachment) -> str:
        """Affichage formaté de la taille"""
        return obj.get_size_display()

    def get_extension(self, obj: EmailAttachment) -> str:
        """Extension du fichier"""
        return obj.get_extension()

    def get_is_image(self, obj: EmailAttachment) -> bool:
        """Vérifie si c'est une image"""
        return obj.is_image()

    def get_is_document(self, obj: EmailAttachment) -> bool:
        """Vérifie si c'est un document"""
        return obj.is_document()


class EmailEventSerializer(serializers.ModelSerializer):
    """Sérialiseur pour les événements extraits"""

    # Champs calculés
    event_type_display = serializers.CharField(source='get_event_type_display', read_only=True)
    duration = serializers.SerializerMethodField()
    duration_display = serializers.SerializerMethodField()

    class Meta:
        model = EmailEvent
        fields = [
            'id', 'email', 'event_type', 'event_type_display', 'title',
            'description', 'start_date', 'end_date', 'all_day', 'location',
            'attendees', 'confidence_score', 'source_text', 'extracted_keywords',
            'is_validated', 'created', 'updated',
            'duration', 'duration_display'
        ]
        read_only_fields = [
            'id', 'confidence_score', 'source_text', 'extracted_keywords',
            'created', 'updated', 'event_type_display',
            'duration', 'duration_display'
        ]

    def get_duration(self, obj: EmailEvent):
        """Durée de l'événement en secondes"""
        duration = obj.get_duration()
        return duration.total_seconds() if duration else None

    def get_duration_display(self, obj: EmailEvent) -> str:
        """Affichage formaté de la durée"""
        duration = obj.get_duration()
        if not duration:
            return ""

        total_seconds = int(duration.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60

        if hours > 0:
            return f"{hours}h {minutes}min"
        else:
            return f"{minutes}min"


class SyncLogSerializer(serializers.ModelSerializer):
    """Sérialiseur pour les logs de synchronisation"""

    # Champs calculés
    account_name = serializers.CharField(source='account.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    duration = serializers.SerializerMethodField()
    duration_display = serializers.SerializerMethodField()

    class Meta:
        model = SyncLog
        fields = [
            'id', 'account', 'account_name', 'start_time', 'end_time',
            'status', 'status_display', 'emails_processed', 'attachments_processed',
            'events_extracted', 'errors_count', 'error_message', 'details',
            'duration', 'duration_display'
        ]
        read_only_fields = '__all__'

    def get_duration(self, obj: SyncLog):
        """Durée de synchronisation en secondes"""
        duration = obj.get_duration()
        return duration.total_seconds() if duration else None

    def get_duration_display(self, obj: SyncLog) -> str:
        """Affichage formaté de la durée"""
        duration = obj.get_duration()
        if not duration:
            return "En cours..." if obj.status == SyncLog.STATUS_RUNNING else ""

        total_seconds = int(duration.total_seconds())
        minutes = total_seconds // 60
        seconds = total_seconds % 60

        if minutes > 0:
            return f"{minutes}min {seconds}s"
        else:
            return f"{seconds}s"


class EmailStatisticsSerializer(serializers.Serializer):
    """Sérialiseur pour les statistiques d'e-mails"""

    total_emails = serializers.IntegerField()
    total_attachments = serializers.IntegerField()
    processed_attachments = serializers.IntegerField()
    processing_rate = serializers.FloatField()
    recent_errors = serializers.IntegerField()
    account_statistics = serializers.ListField()
    category_statistics = serializers.DictField()
    period_days = serializers.IntegerField()
    period_start = serializers.DateTimeField()
    generated_at = serializers.DateTimeField()


class IMAPTestConnectionSerializer(serializers.Serializer):
    """Sérialiseur pour tester une connexion IMAP"""

    server = serializers.CharField(max_length=255)
    port = serializers.IntegerField(min_value=1, max_value=65535)
    use_ssl = serializers.BooleanField(default=True)
    use_starttls = serializers.BooleanField(default=False)
    auth_method = serializers.ChoiceField(choices=IMAPAccount.AUTH_CHOICES)
    username = serializers.CharField(max_length=255)
    password = serializers.CharField(required=False, allow_blank=True)

    # OAuth2 (optionnel)
    oauth2_client_id = serializers.CharField(required=False, allow_blank=True)
    oauth2_client_secret = serializers.CharField(required=False, allow_blank=True)
    oauth2_access_token = serializers.CharField(required=False, allow_blank=True)

    def validate(self, data):
        """Validation des données de connexion"""
        auth_method = data.get('auth_method')

        if auth_method == IMAPAccount.AUTH_BASIC:
            if not data.get('password'):
                raise serializers.ValidationError("Le mot de passe est requis pour l'authentification basique")

        elif auth_method == IMAPAccount.AUTH_OAUTH2:
            required_fields = ['oauth2_client_id', 'oauth2_client_secret', 'oauth2_access_token']
            for field in required_fields:
                if not data.get(field):
                    raise serializers.ValidationError(f"Le champ '{field}' est requis pour OAuth2")

        return data


class BulkEmailActionSerializer(serializers.Serializer):
    """Sérialiseur pour les actions en lot sur les e-mails"""

    ACTION_MARK_READ = 'mark_read'
    ACTION_MARK_UNREAD = 'mark_unread'
    ACTION_CATEGORIZE = 'categorize'
    ACTION_DELETE = 'delete'
    ACTION_PROCESS_ATTACHMENTS = 'process_attachments'

    ACTION_CHOICES = [
        (ACTION_MARK_READ, 'Marquer comme lu'),
        (ACTION_MARK_UNREAD, 'Marquer comme non lu'),
        (ACTION_CATEGORIZE, 'Catégoriser'),
        (ACTION_DELETE, 'Supprimer'),
        (ACTION_PROCESS_ATTACHMENTS, 'Traiter les pièces jointes'),
    ]

    action = serializers.ChoiceField(choices=ACTION_CHOICES)
    email_ids = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1,
        max_length=100  # Limite pour éviter les opérations trop lourdes
    )

    # Paramètres optionnels selon l'action
    category = serializers.ChoiceField(
        choices=EmailMessage.CATEGORY_CHOICES,
        required=False
    )

    def validate(self, data):
        """Validation selon l'action"""
        action = data.get('action')

        if action == self.ACTION_CATEGORIZE and not data.get('category'):
            raise serializers.ValidationError("La catégorie est requise pour l'action de catégorisation")

        return data
