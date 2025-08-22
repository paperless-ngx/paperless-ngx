"""
Modèles de données pour le module IMAP Paperless-ngx

Gestion complète des comptes IMAP, e-mails et métadonnées associées.
"""

import uuid
import json
from datetime import datetime, timezone
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _
from documents.models import Document
from cryptography.fernet import Fernet


def default_attachment_extensions():
    """Retourne les extensions par défaut pour les pièces jointes"""
    return ['.pdf', '.doc', '.docx', '.txt', '.jpg', '.png', '.tiff']


def default_empty_list():
    """Retourne une liste vide par défaut"""
    return []


def default_empty_dict():
    """Retourne un dictionnaire vide par défaut"""
    return {}
from django.conf import settings


class IMAPAccount(models.Model):
    """Configuration d'un compte IMAP"""

    # Identification
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(
        max_length=100,
        verbose_name="Nom du compte",
        help_text="Nom descriptif pour identifier le compte"
    )

    # Configuration serveur
    server = models.CharField(
        max_length=255,
        verbose_name="Serveur IMAP",
        help_text="Adresse du serveur IMAP (ex: imap.gmail.com)"
    )
    port = models.IntegerField(
        default=993,
        validators=[MinValueValidator(1), MaxValueValidator(65535)],
        verbose_name="Port",
        help_text="Port de connexion IMAP (993 pour SSL, 143 pour STARTTLS)"
    )
    use_ssl = models.BooleanField(
        default=True,
        verbose_name="Utiliser SSL",
        help_text="Connexion sécurisée via SSL/TLS"
    )
    use_starttls = models.BooleanField(
        default=False,
        verbose_name="Utiliser STARTTLS",
        help_text="Activer STARTTLS pour la sécurisation"
    )

    # Authentification
    AUTH_BASIC = 'basic'
    AUTH_OAUTH2 = 'oauth2'
    AUTH_CHOICES = [
        (AUTH_BASIC, 'Authentification basique'),
        (AUTH_OAUTH2, 'OAuth2'),
    ]

    auth_method = models.CharField(
        max_length=20,
        choices=AUTH_CHOICES,
        default=AUTH_BASIC,
        verbose_name="Méthode d'authentification"
    )

    username = models.CharField(
        max_length=255,
        verbose_name="Nom d'utilisateur",
        help_text="Adresse e-mail ou nom d'utilisateur"
    )

    # Mot de passe chiffré
    encrypted_password = models.TextField(
        blank=True,
        verbose_name="Mot de passe chiffré"
    )

    # OAuth2
    oauth2_client_id = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Client ID OAuth2"
    )
    oauth2_client_secret = models.TextField(
        blank=True,
        verbose_name="Client Secret OAuth2"
    )
    oauth2_refresh_token = models.TextField(
        blank=True,
        verbose_name="Refresh Token OAuth2"
    )
    oauth2_access_token = models.TextField(
        blank=True,
        verbose_name="Access Token OAuth2"
    )
    oauth2_token_expires = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Expiration du token"
    )

    # Configuration de traitement
    folders_to_sync = models.JSONField(
        default=default_empty_list,
        blank=True,
        verbose_name="Dossiers à synchroniser",
        help_text="Liste des dossiers IMAP à surveiller (ex: ['INBOX', 'Sent'])"
    )

    attachment_extensions = models.JSONField(
        default=default_attachment_extensions,
        verbose_name="Extensions de pièces jointes",
        help_text="Extensions de fichiers à extraire automatiquement"
    )

    max_attachment_size = models.IntegerField(
        default=50,  # MB
        validators=[MinValueValidator(1), MaxValueValidator(500)],
        verbose_name="Taille max des pièces jointes (MB)"
    )

    # Règles de filtrage
    sender_whitelist = models.JSONField(
        default=default_empty_list,
        blank=True,
        verbose_name="Liste blanche expéditeurs",
        help_text="Adresses e-mail autorisées (vide = toutes)"
    )

    sender_blacklist = models.JSONField(
        default=default_empty_list,
        blank=True,
        verbose_name="Liste noire expéditeurs",
        help_text="Adresses e-mail à ignorer"
    )

    subject_keywords = models.JSONField(
        default=default_empty_list,
        blank=True,
        verbose_name="Mots-clés dans le sujet",
        help_text="Mots-clés requis dans le sujet pour traitement"
    )

    # Configuration de synchronisation
    sync_interval = models.IntegerField(
        default=15,  # minutes
        validators=[MinValueValidator(1), MaxValueValidator(1440)],
        verbose_name="Intervalle de synchronisation (minutes)"
    )

    auto_process_attachments = models.BooleanField(
        default=True,
        verbose_name="Traitement automatique des pièces jointes"
    )

    auto_extract_events = models.BooleanField(
        default=True,
        verbose_name="Extraction automatique d'événements"
    )

    auto_categorize = models.BooleanField(
        default=True,
        verbose_name="Catégorisation automatique"
    )

    # État et métadonnées
    is_active = models.BooleanField(
        default=True,
        verbose_name="Compte actif"
    )

    last_sync = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Dernière synchronisation"
    )

    last_uid = models.IntegerField(
        default=0,
        verbose_name="Dernier UID traité",
        help_text="UID du dernier e-mail traité pour synchronisation incrémentielle"
    )

    sync_errors = models.JSONField(
        default=default_empty_list,
        blank=True,
        verbose_name="Erreurs de synchronisation"
    )

    created = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")
    updated = models.DateTimeField(auto_now=True, verbose_name="Mis à jour le")

    # Propriétaire
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="imap_accounts",
        verbose_name="Propriétaire"
    )

    class Meta:
        verbose_name = "Compte IMAP"
        verbose_name_plural = "Comptes IMAP"
        ordering = ['name']
        unique_together = ('server', 'username', 'owner')

    def __str__(self):
        return f"{self.name} ({self.username}@{self.server})"

    def set_password(self, password: str):
        """Chiffre et stocke le mot de passe"""
        if not password:
            self.encrypted_password = ""
            return

        # Utilise la clé de chiffrement Django
        key = settings.SECRET_KEY[:32].ljust(32, '0').encode()
        f = Fernet(Fernet.generate_key())  # En production, utiliser une clé fixe
        self.encrypted_password = f.encrypt(password.encode()).decode()

    def get_password(self) -> str:
        """Déchiffre et retourne le mot de passe"""
        if not self.encrypted_password:
            return ""

        try:
            key = settings.SECRET_KEY[:32].ljust(32, '0').encode()
            f = Fernet(Fernet.generate_key())  # En production, utiliser la même clé
            return f.decrypt(self.encrypted_password.encode()).decode()
        except Exception:
            return ""

    def is_oauth2_token_valid(self) -> bool:
        """Vérifie si le token OAuth2 est encore valide"""
        if not self.oauth2_access_token or not self.oauth2_token_expires:
            return False
        return datetime.now(timezone.utc) < self.oauth2_token_expires

    def get_sync_status(self) -> dict:
        """Retourne le statut de synchronisation"""
        if not self.last_sync:
            return {'status': 'never', 'message': 'Jamais synchronisé'}

        if self.sync_errors:
            return {'status': 'error', 'message': f"Erreurs: {len(self.sync_errors)}"}

        return {'status': 'ok', 'message': f"Dernière sync: {self.last_sync}"}


class EmailMessage(models.Model):
    """E-mail récupéré depuis IMAP"""

    # Identification
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(
        IMAPAccount,
        on_delete=models.CASCADE,
        related_name="emails",
        verbose_name="Compte IMAP"
    )

    # Identifiants IMAP
    message_id = models.CharField(
        max_length=255,
        verbose_name="Message ID",
        help_text="ID unique du message e-mail"
    )
    uid = models.IntegerField(
        verbose_name="UID IMAP",
        help_text="UID unique dans le serveur IMAP"
    )
    folder = models.CharField(
        max_length=255,
        default="INBOX",
        verbose_name="Dossier IMAP"
    )

    # En-têtes e-mail
    subject = models.CharField(
        max_length=998,  # RFC 2822 limite
        verbose_name="Sujet"
    )
    sender = models.EmailField(
        verbose_name="Expéditeur"
    )
    recipients = models.JSONField(
        default=default_empty_list,
        verbose_name="Destinataires",
        help_text="Liste des adresses destinataires"
    )
    cc_recipients = models.JSONField(
        default=default_empty_list,
        blank=True,
        verbose_name="Destinataires en copie"
    )
    bcc_recipients = models.JSONField(
        default=default_empty_list,
        blank=True,
        verbose_name="Destinataires en copie cachée"
    )

    # Dates
    date_sent = models.DateTimeField(
        verbose_name="Date d'envoi"
    )
    date_received = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date de réception"
    )

    # Contenu
    body_text = models.TextField(
        blank=True,
        verbose_name="Corps du message (texte)"
    )
    body_html = models.TextField(
        blank=True,
        verbose_name="Corps du message (HTML)"
    )

    # Métadonnées
    is_read = models.BooleanField(
        default=False,
        verbose_name="Lu"
    )
    is_flagged = models.BooleanField(
        default=False,
        verbose_name="Marqué"
    )

    priority = models.CharField(
        max_length=20,
        default="normal",
        choices=[
            ('low', 'Basse'),
            ('normal', 'Normale'),
            ('high', 'Haute'),
            ('urgent', 'Urgente'),
        ],
        verbose_name="Priorité"
    )

    # Catégorisation automatique
    CATEGORY_PERSONAL = 'personal'
    CATEGORY_PROFESSIONAL = 'professional'
    CATEGORY_PROMOTIONAL = 'promotional'
    CATEGORY_SOCIAL = 'social'
    CATEGORY_UPDATES = 'updates'
    CATEGORY_FORUMS = 'forums'
    CATEGORY_OTHER = 'other'

    CATEGORY_CHOICES = [
        (CATEGORY_PERSONAL, 'Personnel'),
        (CATEGORY_PROFESSIONAL, 'Professionnel'),
        (CATEGORY_PROMOTIONAL, 'Promotionnel'),
        (CATEGORY_SOCIAL, 'Social'),
        (CATEGORY_UPDATES, 'Mises à jour'),
        (CATEGORY_FORUMS, 'Forums'),
        (CATEGORY_OTHER, 'Autre'),
    ]

    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        default=CATEGORY_OTHER,
        verbose_name="Catégorie"
    )

    confidence_score = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        verbose_name="Score de confiance catégorisation"
    )

    # Analyse de contenu
    extracted_keywords = models.JSONField(
        default=default_empty_list,
        blank=True,
        verbose_name="Mots-clés extraits"
    )

    detected_language = models.CharField(
        max_length=10,
        blank=True,
        verbose_name="Langue détectée"
    )

    # État de traitement
    is_processed = models.BooleanField(
        default=False,
        verbose_name="Traité"
    )

    processing_errors = models.JSONField(
        default=default_empty_list,
        blank=True,
        verbose_name="Erreurs de traitement"
    )

    # Timestamps
    created = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")
    updated = models.DateTimeField(auto_now=True, verbose_name="Mis à jour le")

    class Meta:
        verbose_name = "E-mail"
        verbose_name_plural = "E-mails"
        ordering = ['-date_sent']
        unique_together = ('account', 'message_id')
        indexes = [
            models.Index(fields=['account', 'uid']),
            models.Index(fields=['sender']),
            models.Index(fields=['date_sent']),
            models.Index(fields=['category']),
            models.Index(fields=['is_processed']),
        ]

    def __str__(self):
        return f"{self.subject} (de {self.sender})"

    def has_attachments(self) -> bool:
        """Vérifie si l'e-mail a des pièces jointes"""
        return self.attachments.exists()

    def get_attachment_count(self) -> int:
        """Retourne le nombre de pièces jointes"""
        return self.attachments.count()

    def get_processed_attachments(self) -> int:
        """Retourne le nombre de pièces jointes traitées"""
        return self.attachments.filter(is_processed=True).count()


class EmailAttachment(models.Model):
    """Pièce jointe d'un e-mail"""

    # Identification
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.ForeignKey(
        EmailMessage,
        on_delete=models.CASCADE,
        related_name="attachments",
        verbose_name="E-mail"
    )

    # Métadonnées de fichier
    filename = models.CharField(
        max_length=255,
        verbose_name="Nom du fichier"
    )
    content_type = models.CharField(
        max_length=255,
        verbose_name="Type MIME"
    )
    size = models.BigIntegerField(
        verbose_name="Taille (bytes)"
    )

    # Contenu (optionnel, pour petits fichiers)
    content = models.BinaryField(
        blank=True,
        null=True,
        verbose_name="Contenu binaire"
    )

    # Fichier temporaire (pour gros fichiers)
    temp_file_path = models.CharField(
        max_length=500,
        blank=True,
        verbose_name="Chemin fichier temporaire"
    )

    # Lien vers document Paperless
    document = models.OneToOneField(
        Document,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="email_attachment",
        verbose_name="Document Paperless"
    )

    # État de traitement
    is_processed = models.BooleanField(
        default=False,
        verbose_name="Traité"
    )

    is_supported_format = models.BooleanField(
        default=True,
        verbose_name="Format supporté"
    )

    processing_error = models.TextField(
        blank=True,
        verbose_name="Erreur de traitement"
    )

    # Métadonnées extraites
    extracted_text = models.TextField(
        blank=True,
        verbose_name="Texte extrait"
    )

    detected_language = models.CharField(
        max_length=10,
        blank=True,
        verbose_name="Langue détectée"
    )

    # Timestamps
    created = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")
    updated = models.DateTimeField(auto_now=True, verbose_name="Mis à jour le")

    class Meta:
        verbose_name = "Pièce jointe"
        verbose_name_plural = "Pièces jointes"
        ordering = ['filename']
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['content_type']),
            models.Index(fields=['is_processed']),
        ]

    def __str__(self):
        return f"{self.filename} ({self.get_size_display()})"

    def get_size_display(self) -> str:
        """Affichage formaté de la taille"""
        if self.size < 1024:
            return f"{self.size} B"
        elif self.size < 1024 * 1024:
            return f"{self.size / 1024:.1f} KB"
        else:
            return f"{self.size / (1024 * 1024):.1f} MB"

    def get_extension(self) -> str:
        """Retourne l'extension du fichier"""
        return self.filename.split('.')[-1].lower() if '.' in self.filename else ''

    def is_image(self) -> bool:
        """Vérifie si c'est une image"""
        return self.content_type.startswith('image/')

    def is_document(self) -> bool:
        """Vérifie si c'est un document"""
        doc_types = ['application/pdf', 'application/msword', 'application/vnd.openxmlformats-officedocument']
        return any(self.content_type.startswith(doc_type) for doc_type in doc_types)


class EmailEvent(models.Model):
    """Événement extrait d'un e-mail"""

    # Identification
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.ForeignKey(
        EmailMessage,
        on_delete=models.CASCADE,
        related_name="events",
        verbose_name="E-mail"
    )

    # Type d'événement
    EVENT_MEETING = 'meeting'
    EVENT_APPOINTMENT = 'appointment'
    EVENT_DEADLINE = 'deadline'
    EVENT_REMINDER = 'reminder'
    EVENT_TASK = 'task'
    EVENT_OTHER = 'other'

    EVENT_CHOICES = [
        (EVENT_MEETING, 'Réunion'),
        (EVENT_APPOINTMENT, 'Rendez-vous'),
        (EVENT_DEADLINE, 'Échéance'),
        (EVENT_REMINDER, 'Rappel'),
        (EVENT_TASK, 'Tâche'),
        (EVENT_OTHER, 'Autre'),
    ]

    event_type = models.CharField(
        max_length=20,
        choices=EVENT_CHOICES,
        default=EVENT_OTHER,
        verbose_name="Type d'événement"
    )

    # Détails de l'événement
    title = models.CharField(
        max_length=255,
        verbose_name="Titre"
    )
    description = models.TextField(
        blank=True,
        verbose_name="Description"
    )

    # Données temporelles
    start_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Date de début"
    )
    end_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Date de fin"
    )

    all_day = models.BooleanField(
        default=False,
        verbose_name="Toute la journée"
    )

    # Localisation
    location = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Lieu"
    )

    # Participants
    attendees = models.JSONField(
        default=default_empty_list,
        blank=True,
        verbose_name="Participants"
    )

    # Métadonnées d'extraction
    confidence_score = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        verbose_name="Score de confiance"
    )

    source_text = models.TextField(
        blank=True,
        verbose_name="Texte source"
    )

    extracted_keywords = models.JSONField(
        default=default_empty_list,
        blank=True,
        verbose_name="Mots-clés extraits"
    )

    # État
    is_validated = models.BooleanField(
        default=False,
        verbose_name="Validé"
    )

    # Timestamps
    created = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")
    updated = models.DateTimeField(auto_now=True, verbose_name="Mis à jour le")

    class Meta:
        verbose_name = "Événement"
        verbose_name_plural = "Événements"
        ordering = ['-start_date']
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['event_type']),
            models.Index(fields=['start_date']),
            models.Index(fields=['is_validated']),
        ]

    def __str__(self):
        return f"{self.title} ({self.get_event_type_display()})"

    def get_duration(self):
        """Retourne la durée de l'événement"""
        if self.start_date and self.end_date:
            return self.end_date - self.start_date
        return None


class SyncLog(models.Model):
    """Journal de synchronisation IMAP"""

    # Identification
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(
        IMAPAccount,
        on_delete=models.CASCADE,
        related_name="sync_logs",
        verbose_name="Compte IMAP"
    )

    # Détails de synchronisation
    start_time = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Début"
    )
    end_time = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Fin"
    )

    STATUS_RUNNING = 'running'
    STATUS_SUCCESS = 'success'
    STATUS_ERROR = 'error'
    STATUS_CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (STATUS_RUNNING, 'En cours'),
        (STATUS_SUCCESS, 'Succès'),
        (STATUS_ERROR, 'Erreur'),
        (STATUS_CANCELLED, 'Annulé'),
    ]

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_RUNNING,
        verbose_name="Statut"
    )

    # Statistiques
    emails_processed = models.IntegerField(
        default=0,
        verbose_name="E-mails traités"
    )
    attachments_processed = models.IntegerField(
        default=0,
        verbose_name="Pièces jointes traitées"
    )
    events_extracted = models.IntegerField(
        default=0,
        verbose_name="Événements extraits"
    )
    errors_count = models.IntegerField(
        default=0,
        verbose_name="Nombre d'erreurs"
    )

    # Détails
    error_message = models.TextField(
        blank=True,
        verbose_name="Message d'erreur"
    )
    details = models.JSONField(
        default=default_empty_dict,
        blank=True,
        verbose_name="Détails"
    )

    class Meta:
        verbose_name = "Log de synchronisation"
        verbose_name_plural = "Logs de synchronisation"
        ordering = ['-start_time']
        indexes = [
            models.Index(fields=['account', 'start_time']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"Sync {self.account.name} - {self.start_time} ({self.status})"

    def get_duration(self):
        """Retourne la durée de synchronisation"""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return None
