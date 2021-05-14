import os
from uvicorn.workers import UvicornWorker
from django.conf import settings

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "paperless.settings")


class ConfigurableWorker(UvicornWorker):
    CONFIG_KWARGS = {
        "root_path": settings.FORCE_SCRIPT_NAME or "",
    }
