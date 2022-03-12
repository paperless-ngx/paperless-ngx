import os

from django.conf import settings
from uvicorn.workers import UvicornWorker

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "paperless.settings")


class ConfigurableWorker(UvicornWorker):
    CONFIG_KWARGS = {
        "root_path": settings.FORCE_SCRIPT_NAME or "",
    }
