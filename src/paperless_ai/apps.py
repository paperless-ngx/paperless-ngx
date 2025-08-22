"""
Configuration de l'application Django pour le module AI de Paperless-ngx

Système de classification intelligente et recherche sémantique.
"""

from django.apps import AppConfig


class PaperlessAiConfig(AppConfig):
    """Configuration de l'application Paperless AI"""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'paperless_ai'
    verbose_name = 'Paperless AI Classification'

    def ready(self):
        """Initialisation de l'application"""
        # Import des signaux
        from . import signals
