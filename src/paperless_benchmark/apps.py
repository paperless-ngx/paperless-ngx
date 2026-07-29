from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class PaperlessBenchmarkConfig(AppConfig):
    name = "paperless_benchmark"

    verbose_name = _("Paperless benchmark")
