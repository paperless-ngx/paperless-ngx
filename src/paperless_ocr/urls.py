from django.urls import path, include
from rest_framework import routers

from . import views

# Router principal pour les APIs REST
router = routers.DefaultRouter()

# ViewSets OCR
router.register(r"results", views.OCRResultViewSet, basename="ocr-results")
router.register(r"queue", views.OCRQueueViewSet, basename="ocr-queue")
router.register(r"configurations", views.OCRConfigurationViewSet, basename="ocr-configurations")
router.register(r"documents", views.DocumentOCRViewSet, basename="ocr-documents")

urlpatterns = [
    # APIs REST
    path("", include(router.urls)),

    # Points de contrôle système
    path("health/", views.ocr_health_check, name="ocr-health-check"),
]
