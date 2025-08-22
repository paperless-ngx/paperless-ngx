from django.db import models
from django.contrib.auth.models import User
from documents.models import Document
import json


class OCRConfiguration(models.Model):
    """Configuration globale pour les moteurs OCR"""

    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Nom de la configuration"
    )

    # Configuration Tesseract
    tesseract_lang = models.CharField(
        max_length=50,
        default='fra+eng',
        verbose_name="Langues Tesseract"
    )
    tesseract_psm = models.IntegerField(
        default=6,
        verbose_name="Page Segmentation Mode"
    )
    tesseract_oem = models.IntegerField(
        default=3,
        verbose_name="OCR Engine Mode"
    )

    # Configuration Doctr
    doctr_model = models.CharField(
        max_length=50,
        default='db_resnet50',
        verbose_name="Modèle de détection Doctr"
    )
    doctr_recognition_model = models.CharField(
        max_length=50,
        default='crnn_vgg16_bn',
        verbose_name="Modèle de reconnaissance Doctr"
    )

    # Configuration générale
    max_image_size = models.IntegerField(
        default=3000,
        verbose_name="Taille max des images (px)"
    )
    dpi = models.IntegerField(
        default=300,
        verbose_name="DPI pour conversion PDF"
    )
    enhance_image = models.BooleanField(
        default=True,
        verbose_name="Amélioration automatique"
    )
    denoise = models.BooleanField(
        default=True,
        verbose_name="Débruitage"
    )

    # Performance
    max_memory_mb = models.IntegerField(
        default=1024,
        verbose_name="Mémoire max (MB)"
    )
    batch_size = models.IntegerField(
        default=4,
        verbose_name="Taille des lots"
    )

    is_active = models.BooleanField(
        default=False,
        verbose_name="Configuration active"
    )

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuration OCR"
        verbose_name_plural = "Configurations OCR"
        ordering = ['-is_active', 'name']

    def __str__(self):
        return f"{self.name} {'(active)' if self.is_active else ''}"

    def save(self, *args, **kwargs):
        # Assurer qu'une seule configuration est active
        if self.is_active:
            OCRConfiguration.objects.filter(is_active=True).update(is_active=False)
        super().save(*args, **kwargs)


class OCRResult(models.Model):
    """Résultats OCR pour chaque moteur"""

    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name="ocr_results",
        verbose_name="Document"
    )

    ENGINE_TESSERACT = "tesseract"
    ENGINE_DOCTR = "doctr"
    ENGINE_HYBRID = "hybrid"
    ENGINE_CHOICES = [
        (ENGINE_TESSERACT, "Tesseract"),
        (ENGINE_DOCTR, "Doctr"),
        (ENGINE_HYBRID, "Hybrid Fusion"),
    ]

    engine = models.CharField(
        max_length=20,
        choices=ENGINE_CHOICES,
        verbose_name="Moteur OCR",
    )

    text = models.TextField(
        blank=True,
        verbose_name="Texte extrait",
    )

    confidence = models.FloatField(
        null=True,
        blank=True,
        verbose_name="Score de confiance",
        help_text="Score de confiance moyen (0.0 à 1.0)"
    )

    processing_time = models.FloatField(
        null=True,
        blank=True,
        verbose_name="Temps de traitement (s)"
    )

    # Métadonnées détaillées
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Métadonnées"
    )

    # Résultats par page
    page_results = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Résultats par page"
    )

    # Boîtes englobantes (pour analyse avancée)
    bounding_boxes = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Boîtes englobantes"
    )

    # Statut du traitement
    STATUS_PENDING = "pending"
    STATUS_PROCESSING = "processing"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = [
        (STATUS_PENDING, "En attente"),
        (STATUS_PROCESSING, "En cours"),
        (STATUS_COMPLETED, "Terminé"),
        (STATUS_FAILED, "Échec"),
    ]

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        verbose_name="Statut"
    )

    error_message = models.TextField(
        blank=True,
        verbose_name="Message d'erreur"
    )

    configuration = models.ForeignKey(
        OCRConfiguration,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Configuration utilisée"
    )

    created = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Créé le"
    )

    updated = models.DateTimeField(
        auto_now=True,
        verbose_name="Mis à jour le"
    )

    class Meta:
        unique_together = ("document", "engine")
        verbose_name = "Résultat OCR"
        verbose_name_plural = "Résultats OCR"
        ordering = ['-created']
        indexes = [
            models.Index(fields=['document']),
            models.Index(fields=['engine']),
            models.Index(fields=['created']),
            models.Index(fields=['status']),
            models.Index(
                fields=['confidence'],
                condition=models.Q(confidence__isnull=False),
                name='ocr_result_confidence_idx'
            ),
            models.Index(
                fields=['processing_time'],
                condition=models.Q(processing_time__isnull=False),
                name='ocr_result_processing_time_idx'
            ),
        ]

    def __str__(self):
        return f"{self.document.title} - {self.get_engine_display()} ({self.status})"

    @property
    def word_count(self):
        """Nombre de mots extraits"""
        return len(self.text.split()) if self.text else 0

    @property
    def character_count(self):
        """Nombre de caractères extraits"""
        return len(self.text) if self.text else 0

    def get_page_count(self):
        """Nombre de pages traitées"""
        return len(self.page_results) if self.page_results else 0


class OCRQueue(models.Model):
    """File d'attente pour les traitements OCR"""

    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        verbose_name="Document"
    )

    engines = models.JSONField(
        default=list,
        verbose_name="Moteurs à exécuter",
        help_text="Liste des moteurs OCR à exécuter"
    )

    PRIORITY_LOW = 1
    PRIORITY_NORMAL = 5
    PRIORITY_HIGH = 10
    PRIORITY_URGENT = 20

    PRIORITY_CHOICES = [
        (PRIORITY_LOW, "Basse"),
        (PRIORITY_NORMAL, "Normale"),
        (PRIORITY_HIGH, "Haute"),
        (PRIORITY_URGENT, "Urgente"),
    ]

    priority = models.IntegerField(
        choices=PRIORITY_CHOICES,
        default=PRIORITY_NORMAL,
        verbose_name="Priorité"
    )

    scheduled_for = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Programmé pour"
    )

    retries = models.IntegerField(
        default=0,
        verbose_name="Tentatives"
    )

    max_retries = models.IntegerField(
        default=3,
        verbose_name="Tentatives max"
    )

    STATUS_QUEUED = "queued"
    STATUS_PROCESSING = "processing"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (STATUS_QUEUED, "En file"),
        (STATUS_PROCESSING, "En cours"),
        (STATUS_COMPLETED, "Terminé"),
        (STATUS_FAILED, "Échec"),
        (STATUS_CANCELLED, "Annulé"),
    ]

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_QUEUED,
        verbose_name="Statut"
    )

    celery_task_id = models.CharField(
        max_length=36,
        blank=True,
        verbose_name="ID tâche Celery"
    )

    requested_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Demandé par"
    )

    created = models.DateTimeField(auto_now_add=True)
    started = models.DateTimeField(null=True, blank=True)
    completed = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "File OCR"
        verbose_name_plural = "Files OCR"
        ordering = ['-priority', 'created']
        indexes = [
            models.Index(fields=['status', 'priority', 'created']),
            models.Index(fields=['celery_task_id']),
        ]

    def __str__(self):
        return f"{self.document.title} - {self.get_status_display()}"
