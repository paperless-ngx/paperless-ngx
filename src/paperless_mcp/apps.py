from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class PaperlessMcpConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'paperless_mcp'
    verbose_name = _("Paperless MCP Tools")

    def ready(self):
        # Import MCP tools when Django starts
        try:
            from . import tools  # noqa: F401
        except ImportError:
            pass
