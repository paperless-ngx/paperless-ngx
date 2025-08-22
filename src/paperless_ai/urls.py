"""
URLs pour l'API du système de classification intelligente

Configuration des routes REST pour la recherche sémantique,
classification automatique et gestion des modèles IA.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    AIModelViewSet,
    DocumentClassificationViewSet,
    SemanticSearchViewSet,
    DocumentProcessingViewSet,
    AIMetricsViewSet,
    TrainingJobViewSet
)

# Configuration du routeur DRF
router = DefaultRouter()
router.register(r'models', AIModelViewSet, basename='aimodel')
router.register(r'classifications', DocumentClassificationViewSet, basename='documentclassification')
router.register(r'search', SemanticSearchViewSet, basename='semanticsearch')
router.register(r'processing', DocumentProcessingViewSet, basename='documentprocessing')
router.register(r'metrics', AIMetricsViewSet, basename='aimetrics')
router.register(r'training-jobs', TrainingJobViewSet, basename='trainingjob')

# URLs spécifiques
urlpatterns = [
    # API REST
    path('api/', include(router.urls)),

    # Endpoints supplémentaires pour compatibilité
    path('api/v1/', include(router.urls)),
]

# Alias pour les endpoints principaux
app_name = 'paperless_ai'
