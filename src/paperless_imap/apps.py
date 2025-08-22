from django.apps import AppConfig


class PaperlessImapConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'paperless_imap'
    verbose_name = 'Paperless IMAP'

    def ready(self):
        # Import des signaux pour les connecter
        from . import signals
