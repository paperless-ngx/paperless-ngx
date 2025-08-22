"""
Modèles de données pour le système de classification intelligente Paperless-ngx

Gestion des modèles IA, embeddings, classifications et métriques.
"""

import uuid
import numpy as np
from datetime import datetime, timezone
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _
from documents.models import Document, DocumentType, Correspondent, Tag


def default_empty_list():
    """Retourne une liste vide par défaut"""
    return []


def default_empty_dict():
    """Retourne un dictionnaire vide par défaut"""
    return {}


def default_model_config():
    """Configuration par défaut pour les modèles IA"""
    return {
        "model_name": "distilbert-base-multilingual-cased",
        "max_length": 512,
        "confidence_threshold": 0.8,
        "batch_size": 16,
        "learning_rate": 2e-5,
        "num_epochs": 3
    }


class AIModel(models.Model):
    """Configuration et métadonnées des modèles IA"""

    MODEL_TYPES = [
        ('classification', 'Classification de documents'),
        ('correspondent', 'Prédiction de correspondant'),
        ('tagging', 'Suggestion de tags'),
        ('embedding', 'Génération d\'embeddings'),
        ('search', 'Recherche sémantique'),
    ]

    STATUS_CHOICES = [
        ('training', 'En formation'),
        ('ready', 'Prêt'),
        ('updating', 'Mise à jour'),
        ('error', 'Erreur'),
        ('disabled', 'Désactivé'),
    ]

    # Identification
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Nom du modèle",
        help_text="Nom descriptif unique du modèle"
    )
    model_type = models.CharField(
        max_length=20,
        choices=MODEL_TYPES,
        verbose_name="Type de modèle"
    )
    language = models.CharField(
        max_length=20,
        default='multilingual',
        verbose_name="Langue",
        help_text="Langue principale du modèle"
    )

    # Configuration
    model_path = models.CharField(
        max_length=500,
        verbose_name="Chemin du modèle",
        help_text="Chemin vers les fichiers du modèle entraîné"
    )
    config = models.JSONField(
        default=default_model_config,
        verbose_name="Configuration",
        help_text="Paramètres de configuration du modèle"
    )

    # État et métadonnées
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='training',
        verbose_name="Statut"
    )
    version = models.CharField(
        max_length=20,
        default="1.0.0",
        verbose_name="Version"
    )

    # Métriques de performance
    accuracy = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        verbose_name="Précision"
    )
    f1_score = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        verbose_name="Score F1"
    )
    training_samples = models.IntegerField(
        default=0,
        verbose_name="Échantillons d'entraînement"
    )

    # Gestion des dates
    created = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")
    updated = models.DateTimeField(auto_now=True, verbose_name="Mis à jour le")
    last_trained = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Dernier entraînement"
    )

    # Propriétaire
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="ai_models",
        verbose_name="Propriétaire"
    )

    class Meta:
        verbose_name = "Modèle IA"
        verbose_name_plural = "Modèles IA"
        ordering = ['-updated']

    def __str__(self):
        return f"{self.name} ({self.get_model_type_display()})"


class DocumentEmbedding(models.Model):
    """Embeddings vectoriels des documents pour la recherche sémantique"""

    # Relations
    document = models.OneToOneField(
        Document,
        on_delete=models.CASCADE,
        related_name="embedding",
        verbose_name="Document"
    )
    model = models.ForeignKey(
        AIModel,
        on_delete=models.CASCADE,
        related_name="document_embeddings",
        verbose_name="Modèle utilisé"
    )

    # Données vectorielles
    embedding_vector = models.JSONField(
        verbose_name="Vecteur d'embedding",
        help_text="Représentation vectorielle du document"
    )
    vector_dimension = models.IntegerField(
        verbose_name="Dimension du vecteur"
    )

    # Métadonnées
    text_length = models.IntegerField(
        verbose_name="Longueur du texte traité"
    )
    extraction_method = models.CharField(
        max_length=50,
        default="full_text",
        verbose_name="Méthode d'extraction",
        help_text="Méthode utilisée pour extraire le texte"
    )

    # Gestion des dates
    created = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")
    updated = models.DateTimeField(auto_now=True, verbose_name="Mis à jour le")

    class Meta:
        verbose_name = "Embedding de document"
        verbose_name_plural = "Embeddings de documents"
        unique_together = ('document', 'model')
        indexes = [
            models.Index(fields=['model', 'vector_dimension']),
            models.Index(fields=['created']),
        ]

    def __str__(self):
        return f"Embedding: {self.document.title} ({self.model.name})"

    def get_vector_array(self):
        """Retourne le vecteur sous forme de numpy array"""
        return np.array(self.embedding_vector)


class DocumentClassification(models.Model):
    """Classifications automatiques des documents"""

    CLASSIFICATION_TYPES = [
        ('document_type', 'Type de document'),
        ('correspondent', 'Correspondant'),
        ('tag', 'Tag'),
        ('category', 'Catégorie'),
    ]

    # Relations
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name="ai_classifications",
        verbose_name="Document"
    )
    model = models.ForeignKey(
        AIModel,
        on_delete=models.CASCADE,
        related_name="classifications",
        verbose_name="Modèle utilisé"
    )

    # Classification
    classification_type = models.CharField(
        max_length=20,
        choices=CLASSIFICATION_TYPES,
        verbose_name="Type de classification"
    )
    predicted_class = models.CharField(
        max_length=255,
        verbose_name="Classe prédite"
    )
    confidence_score = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        verbose_name="Score de confiance"
    )

    # Relations vers les objets Paperless
    predicted_document_type = models.ForeignKey(
        DocumentType,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name="Type de document prédit"
    )
    predicted_correspondent = models.ForeignKey(
        Correspondent,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name="Correspondant prédit"
    )
    predicted_tags = models.ManyToManyField(
        Tag,
        blank=True,
        verbose_name="Tags prédits"
    )

    # État de validation
    is_validated = models.BooleanField(
        default=False,
        verbose_name="Validé par l'utilisateur"
    )
    is_applied = models.BooleanField(
        default=False,
        verbose_name="Appliqué au document"
    )
    validation_feedback = models.CharField(
        max_length=20,
        choices=[
            ('correct', 'Correct'),
            ('incorrect', 'Incorrect'),
            ('partial', 'Partiellement correct'),
        ],
        null=True,
        blank=True,
        verbose_name="Feedback de validation"
    )

    # Métadonnées
    processing_time = models.FloatField(
        null=True,
        blank=True,
        verbose_name="Temps de traitement (secondes)"
    )
    features_used = models.JSONField(
        default=default_empty_list,
        verbose_name="Caractéristiques utilisées"
    )

    # Gestion des dates
    created = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")
    validated_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Validé le"
    )
    validated_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="validated_classifications",
        verbose_name="Validé par"
    )

    class Meta:
        verbose_name = "Classification de document"
        verbose_name_plural = "Classifications de documents"
        ordering = ['-created']
        indexes = [
            models.Index(fields=['document', 'classification_type']),
            models.Index(fields=['model', 'confidence_score']),
            models.Index(fields=['is_validated', 'is_applied']),
        ]

    def __str__(self):
        return f"{self.document.title}: {self.predicted_class} ({self.confidence_score:.2f})"


class SearchQuery(models.Model):
    """Historique et analytics des requêtes de recherche"""

    QUERY_TYPES = [
        ('text', 'Recherche textuelle'),
        ('semantic', 'Recherche sémantique'),
        ('hybrid', 'Recherche hybride'),
        ('conversational', 'Recherche conversationnelle'),
    ]

    # Identification
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="search_queries",
        verbose_name="Utilisateur"
    )

    # Requête
    query_text = models.TextField(verbose_name="Texte de la requête")
    query_type = models.CharField(
        max_length=20,
        choices=QUERY_TYPES,
        verbose_name="Type de requête"
    )
    query_embedding = models.JSONField(
        null=True,
        blank=True,
        verbose_name="Embedding de la requête"
    )

    # Résultats
    results_count = models.IntegerField(
        default=0,
        verbose_name="Nombre de résultats"
    )
    response_time = models.FloatField(
        verbose_name="Temps de réponse (secondes)"
    )
    clicked_results = models.JSONField(
        default=default_empty_list,
        verbose_name="Résultats cliqués"
    )

    # Métadonnées
    filters_applied = models.JSONField(
        default=default_empty_dict,
        verbose_name="Filtres appliqués"
    )
    session_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="ID de session"
    )

    # Gestion des dates
    created = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")

    class Meta:
        verbose_name = "Requête de recherche"
        verbose_name_plural = "Requêtes de recherche"
        ordering = ['-created']
        indexes = [
            models.Index(fields=['user', 'created']),
            models.Index(fields=['query_type']),
            models.Index(fields=['response_time']),
        ]

    def __str__(self):
        return f"Recherche: {self.query_text[:50]}..."


class AIMetrics(models.Model):
    """Métriques et statistiques de performance du système IA"""

    METRIC_TYPES = [
        ('classification_accuracy', 'Précision classification'),
        ('search_relevance', 'Pertinence recherche'),
        ('user_satisfaction', 'Satisfaction utilisateur'),
        ('processing_speed', 'Vitesse de traitement'),
        ('model_confidence', 'Confiance du modèle'),
    ]

    # Identification
    model = models.ForeignKey(
        AIModel,
        on_delete=models.CASCADE,
        related_name="metrics",
        verbose_name="Modèle"
    )
    metric_type = models.CharField(
        max_length=30,
        choices=METRIC_TYPES,
        verbose_name="Type de métrique"
    )

    # Valeurs
    value = models.FloatField(verbose_name="Valeur")
    target_value = models.FloatField(
        null=True,
        blank=True,
        verbose_name="Valeur cible"
    )

    # Contexte
    period_start = models.DateTimeField(verbose_name="Début de période")
    period_end = models.DateTimeField(verbose_name="Fin de période")
    sample_size = models.IntegerField(
        default=0,
        verbose_name="Taille de l'échantillon"
    )

    # Métadonnées
    metadata = models.JSONField(
        default=default_empty_dict,
        verbose_name="Métadonnées additionnelles"
    )

    # Gestion des dates
    created = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")

    class Meta:
        verbose_name = "Métrique IA"
        verbose_name_plural = "Métriques IA"
        ordering = ['-created']
        indexes = [
            models.Index(fields=['model', 'metric_type']),
            models.Index(fields=['period_start', 'period_end']),
        ]

    def __str__(self):
        return f"{self.model.name}: {self.get_metric_type_display()} = {self.value}"


class TrainingJob(models.Model):
    """Suivi des tâches d'entraînement des modèles"""

    STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('running', 'En cours'),
        ('completed', 'Terminé'),
        ('failed', 'Échec'),
        ('cancelled', 'Annulé'),
    ]

    # Identification
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    model = models.ForeignKey(
        AIModel,
        on_delete=models.CASCADE,
        related_name="training_jobs",
        verbose_name="Modèle"
    )

    # Configuration
    training_config = models.JSONField(
        default=default_empty_dict,
        verbose_name="Configuration d'entraînement"
    )
    dataset_info = models.JSONField(
        default=default_empty_dict,
        verbose_name="Informations sur le dataset"
    )

    # État
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name="Statut"
    )
    progress = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
        verbose_name="Progression (%)"
    )

    # Résultats
    final_metrics = models.JSONField(
        default=default_empty_dict,
        verbose_name="Métriques finales"
    )
    error_message = models.TextField(
        blank=True,
        verbose_name="Message d'erreur"
    )

    # Gestion des dates
    created = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")
    started_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Démarré le"
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Terminé le"
    )

    # Propriétaire
    started_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="training_jobs",
        verbose_name="Démarré par"
    )

    class Meta:
        verbose_name = "Tâche d'entraînement"
        verbose_name_plural = "Tâches d'entraînement"
        ordering = ['-created']

    def __str__(self):
        return f"Entraînement {self.model.name}: {self.get_status_display()}"

    def get_duration(self):
        """Retourne la durée d'entraînement"""
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return None
