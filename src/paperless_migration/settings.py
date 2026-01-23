"""Settings for migration-mode Django instance."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

DEBUG = os.getenv("PAPERLESS_DEBUG", "false").lower() == "true"

ALLOWED_HOSTS = ["*"]

# Tap paperless.conf if it's available
for path in [
    os.getenv("PAPERLESS_CONFIGURATION_PATH"),
    "../paperless.conf",
    "/etc/paperless.conf",
    "/usr/local/etc/paperless.conf",
]:
    if path and Path(path).exists():
        load_dotenv(path)
        break


def __get_path(
    key: str,
    default: str | Path,
) -> Path:
    if key in os.environ:
        return Path(os.environ[key]).resolve()
    return Path(default).resolve()


DATA_DIR = __get_path("PAPERLESS_DATA_DIR", BASE_DIR.parent / "data")


def _parse_db_settings() -> dict[str, dict[str, Any]]:
    databases: dict[str, dict[str, Any]] = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": DATA_DIR / "db.sqlite3",
            "OPTIONS": {},
        },
    }
    if os.getenv("PAPERLESS_DBHOST"):
        databases["sqlite"] = databases["default"].copy()
        databases["default"] = {
            "HOST": os.getenv("PAPERLESS_DBHOST"),
            "NAME": os.getenv("PAPERLESS_DBNAME", "paperless"),
            "USER": os.getenv("PAPERLESS_DBUSER", "paperless"),
            "PASSWORD": os.getenv("PAPERLESS_DBPASS", "paperless"),
            "OPTIONS": {},
        }
        if os.getenv("PAPERLESS_DBPORT"):
            databases["default"]["PORT"] = os.getenv("PAPERLESS_DBPORT")

        if os.getenv("PAPERLESS_DBENGINE") == "mariadb":
            engine = "django.db.backends.mysql"
            options = {
                "read_default_file": "/etc/mysql/my.cnf",
                "charset": "utf8mb4",
                "ssl_mode": os.getenv("PAPERLESS_DBSSLMODE", "PREFERRED"),
                "ssl": {
                    "ca": os.getenv("PAPERLESS_DBSSLROOTCERT"),
                    "cert": os.getenv("PAPERLESS_DBSSLCERT"),
                    "key": os.getenv("PAPERLESS_DBSSLKEY"),
                },
            }
        else:
            engine = "django.db.backends.postgresql"
            options = {
                "sslmode": os.getenv("PAPERLESS_DBSSLMODE", "prefer"),
                "sslrootcert": os.getenv("PAPERLESS_DBSSLROOTCERT"),
                "sslcert": os.getenv("PAPERLESS_DBSSLCERT"),
                "sslkey": os.getenv("PAPERLESS_DBSSLKEY"),
            }

        databases["default"]["ENGINE"] = engine
        databases["default"]["OPTIONS"].update(options)

    if os.getenv("PAPERLESS_DB_TIMEOUT") is not None:
        timeout = int(os.getenv("PAPERLESS_DB_TIMEOUT"))
        if databases["default"]["ENGINE"] == "django.db.backends.sqlite3":
            databases["default"]["OPTIONS"].update({"timeout": timeout})
        else:
            databases["default"]["OPTIONS"].update({"connect_timeout": timeout})
            databases["sqlite"]["OPTIONS"].update({"timeout": timeout})
    return databases


DATABASES = _parse_db_settings()

SECRET_KEY = os.getenv(
    "PAPERLESS_SECRET_KEY",
    "e11fl1oa-*ytql8p)(06fbj4ukrlo+n7k&q5+$1md7i+mge=ee",
)

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
CSRF_TRUSTED_ORIGINS: list[str] = []

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.mfa",
    "paperless_migration",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]

ROOT_URLCONF = "paperless_migration.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "paperless_migration.wsgi.application"

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / ".." / "static", BASE_DIR / "static"]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/migration/"
LOGOUT_REDIRECT_URL = "/accounts/login/?loggedout=1"

ACCOUNT_ADAPTER = "allauth.account.adapter.DefaultAccountAdapter"
ACCOUNT_AUTHENTICATED_LOGIN_REDIRECTS = False
SOCIALACCOUNT_ADAPTER = "allauth.socialaccount.adapter.DefaultSocialAccountAdapter"
SOCIALACCOUNT_ENABLED = False

SESSION_ENGINE = "django.contrib.sessions.backends.db"

MIGRATION_EXPORT_PATH = os.getenv(
    "PAPERLESS_MIGRATION_EXPORT_PATH",
    "/data/export.json",
)
MIGRATION_TRANSFORMED_PATH = os.getenv(
    "PAPERLESS_MIGRATION_TRANSFORMED_PATH",
    "/data/export.v3.json",
)
