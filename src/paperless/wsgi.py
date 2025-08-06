"""
WSGI config for paperless project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/1.10/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "paperless.settings")

application = get_wsgi_application()

import logging  # noqa: E402

from paperless.version import __full_version_str__  # noqa: E402

logger = logging.getLogger("paperless.wsgi")
logger.info(f"[init] Paperless-ngx version: v{__full_version_str__}")
