import datetime
import json
import logging
import logging.config
import math
import multiprocessing
import os
import tempfile
from pathlib import Path
from typing import Final
from urllib.parse import urlparse

from celery.schedules import crontab
from compression_middleware.middleware import CompressionMiddleware
from dateparser.languages.loader import LocaleDataLoader
from django.utils.translation import gettext_lazy as _
from dotenv import load_dotenv

from paperless.settings.custom import parse_db_settings
from paperless.settings.parsers import get_bool_from_env
from paperless.settings.parsers import get_float_from_env
from paperless.settings.parsers import get_int_from_env
from paperless.settings.parsers import get_list_from_env
from paperless.settings.parsers import get_path_from_env

logger = logging.getLogger("paperless.settings")

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

# There are multiple levels of concurrency in paperless:
#  - Multiple consumers may be run in parallel.
#  - Each consumer may process multiple pages in parallel.
#  - Each Tesseract OCR run may spawn multiple threads to process a single page
#    slightly faster.
# The performance gains from having tesseract use multiple threads are minimal.
# However, when multiple pages are processed in parallel, the total number of
# OCR threads may exceed the number of available cpu cores, which will
# dramatically slow down the consumption process. This settings limits each
# Tesseract process to one thread.
os.environ["OMP_THREAD_LIMIT"] = "1"


def _parse_redis_url(env_redis: str | None) -> tuple[str, str]:
    """
    Gets the Redis information from the environment or a default and handles
    converting from incompatible django_channels and celery formats.

    Returns a tuple of (celery_url, channels_url)
    """

    # Not set, return a compatible default
    if env_redis is None:
        return ("redis://localhost:6379", "redis://localhost:6379")

    if "unix" in env_redis.lower():
        # channels_redis socket format, looks like:
        # "unix:///path/to/redis.sock"
        _, path = env_redis.split(":")
        # Optionally setting a db number
        if "?db=" in env_redis:
            path, number = path.split("?db=")
            return (f"redis+socket:{path}?virtual_host={number}", env_redis)
        else:
            return (f"redis+socket:{path}", env_redis)

    elif "+socket" in env_redis.lower():
        # celery socket style, looks like:
        # "redis+socket:///path/to/redis.sock"
        _, path = env_redis.split(":")
        if "?virtual_host=" in env_redis:
            # Virtual host (aka db number)
            path, number = path.split("?virtual_host=")
            return (env_redis, f"unix:{path}?db={number}")
        else:
            return (env_redis, f"unix:{path}")

    # Not a socket
    return (env_redis, env_redis)


def _parse_beat_schedule() -> dict:
    """
    Configures the scheduled tasks, according to default or
    environment variables.  Task expiration is configured so the task will
    expire (and not run), shortly before the default frequency will put another
    of the same task into the queue


    https://docs.celeryq.dev/en/stable/userguide/periodic-tasks.html#beat-entries
    https://docs.celeryq.dev/en/latest/userguide/calling.html#expiration
    """
    schedule = {}
    tasks = [
        {
            "name": "Check all e-mail accounts",
            "env_key": "PAPERLESS_EMAIL_TASK_CRON",
            # Default every ten minutes
            "env_default": "*/10 * * * *",
            "task": "paperless_mail.tasks.process_mail_accounts",
            "options": {
                # 1 minute before default schedule sends again
                "expires": 9.0 * 60.0,
            },
        },
        {
            "name": "Train the classifier",
            "env_key": "PAPERLESS_TRAIN_TASK_CRON",
            # Default hourly at 5 minutes past the hour
            "env_default": "5 */1 * * *",
            "task": "documents.tasks.train_classifier",
            "options": {
                # 1 minute before default schedule sends again
                "expires": 59.0 * 60.0,
            },
        },
        {
            "name": "Optimize the index",
            "env_key": "PAPERLESS_INDEX_TASK_CRON",
            # Default daily at midnight
            "env_default": "0 0 * * *",
            "task": "documents.tasks.index_optimize",
            "options": {
                # 1 hour before default schedule sends again
                "expires": 23.0 * 60.0 * 60.0,
            },
        },
        {
            "name": "Perform sanity check",
            "env_key": "PAPERLESS_SANITY_TASK_CRON",
            # Default Sunday at 00:30
            "env_default": "30 0 * * sun",
            "task": "documents.tasks.sanity_check",
            "options": {
                # 1 hour before default schedule sends again
                "expires": ((7.0 * 24.0) - 1.0) * 60.0 * 60.0,
            },
        },
        {
            "name": "Empty trash",
            "env_key": "PAPERLESS_EMPTY_TRASH_TASK_CRON",
            # Default daily at 01:00
            "env_default": "0 1 * * *",
            "task": "documents.tasks.empty_trash",
            "options": {
                # 1 hour before default schedule sends again
                "expires": 23.0 * 60.0 * 60.0,
            },
        },
        {
            "name": "Check and run scheduled workflows",
            "env_key": "PAPERLESS_WORKFLOW_SCHEDULED_TASK_CRON",
            # Default hourly at 5 minutes past the hour
            "env_default": "5 */1 * * *",
            "task": "documents.tasks.check_scheduled_workflows",
            "options": {
                # 1 minute before default schedule sends again
                "expires": 59.0 * 60.0,
            },
        },
        {
            "name": "Rebuild LLM index",
            "env_key": "PAPERLESS_LLM_INDEX_TASK_CRON",
            # Default daily at 02:10
            "env_default": "10 2 * * *",
            "task": "documents.tasks.llmindex_index",
            "options": {
                # 1 hour before default schedule sends again
                "expires": 23.0 * 60.0 * 60.0,
            },
        },
        {
            "name": "Cleanup expired share link bundles",
            "env_key": "PAPERLESS_SHARE_LINK_BUNDLE_CLEANUP_CRON",
            # Default daily at 02:00
            "env_default": "0 2 * * *",
            "task": "documents.tasks.cleanup_expired_share_link_bundles",
            "options": {
                # 1 hour before default schedule sends again
                "expires": 23.0 * 60.0 * 60.0,
            },
        },
    ]
    for task in tasks:
        # Either get the environment setting or use the default
        value = os.getenv(task["env_key"], task["env_default"])
        # Don't add disabled tasks to the schedule
        if value == "disable":
            continue
        # I find https://crontab.guru/ super helpful
        # crontab(5) format
        #   - five time-and-date fields
        #   - separated by at least one blank
        minute, hour, day_month, month, day_week = value.split(" ")

        schedule[task["name"]] = {
            "task": task["task"],
            "schedule": crontab(minute, hour, day_week, day_month, month),
            "options": task["options"],
        }

    return schedule


# NEVER RUN WITH DEBUG IN PRODUCTION.
DEBUG = get_bool_from_env("PAPERLESS_DEBUG", "NO")


###############################################################################
# Directories                                                                 #
###############################################################################

BASE_DIR: Path = Path(__file__).resolve().parent.parent

STATIC_ROOT = get_path_from_env("PAPERLESS_STATICDIR", BASE_DIR.parent / "static")

MEDIA_ROOT = get_path_from_env("PAPERLESS_MEDIA_ROOT", BASE_DIR.parent / "media")
ORIGINALS_DIR = MEDIA_ROOT / "documents" / "originals"
ARCHIVE_DIR = MEDIA_ROOT / "documents" / "archive"
THUMBNAIL_DIR = MEDIA_ROOT / "documents" / "thumbnails"
SHARE_LINK_BUNDLE_DIR = MEDIA_ROOT / "documents" / "share_link_bundles"

DATA_DIR = get_path_from_env("PAPERLESS_DATA_DIR", BASE_DIR.parent / "data")

NLTK_DIR = get_path_from_env("PAPERLESS_NLTK_DIR", "/usr/share/nltk_data")

# Check deprecated setting first
EMPTY_TRASH_DIR = (
    get_path_from_env("PAPERLESS_TRASH_DIR", os.getenv("PAPERLESS_EMPTY_TRASH_DIR"))
    if os.getenv("PAPERLESS_TRASH_DIR") or os.getenv("PAPERLESS_EMPTY_TRASH_DIR")
    else None
)

# Lock file for synchronizing changes to the MEDIA directory across multiple
# threads.
MEDIA_LOCK = MEDIA_ROOT / "media.lock"
INDEX_DIR = DATA_DIR / "index"
MODEL_FILE = get_path_from_env(
    "PAPERLESS_MODEL_FILE",
    DATA_DIR / "classification_model.pickle",
)
LLM_INDEX_DIR = DATA_DIR / "llm_index"

LOGGING_DIR = get_path_from_env("PAPERLESS_LOGGING_DIR", DATA_DIR / "log")

CONSUMPTION_DIR = get_path_from_env(
    "PAPERLESS_CONSUMPTION_DIR",
    BASE_DIR.parent / "consume",
)

# This will be created if it doesn't exist
SCRATCH_DIR = get_path_from_env(
    "PAPERLESS_SCRATCH_DIR",
    Path(tempfile.gettempdir()) / "paperless",
)

###############################################################################
# Application Definition                                                      #
###############################################################################

env_apps = get_list_from_env("PAPERLESS_APPS")

INSTALLED_APPS = [
    "whitenoise.runserver_nostatic",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "django_extensions",
    "paperless",
    "documents.apps.DocumentsConfig",
    "paperless_tesseract.apps.PaperlessTesseractConfig",
    "paperless_text.apps.PaperlessTextConfig",
    "paperless_mail.apps.PaperlessMailConfig",
    "paperless_remote.apps.PaperlessRemoteParserConfig",
    "django.contrib.admin",
    "rest_framework",
    "rest_framework.authtoken",
    "django_filters",
    "django_celery_results",
    "guardian",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.mfa",
    "allauth.headless",
    "drf_spectacular",
    "drf_spectacular_sidecar",
    "treenode",
    *env_apps,
]

if DEBUG:
    INSTALLED_APPS.append("channels")

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "paperless.auth.PaperlessBasicAuthentication",
        "rest_framework.authentication.TokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_VERSIONING_CLASS": "rest_framework.versioning.AcceptHeaderVersioning",
    "DEFAULT_VERSION": "9",  # match src-ui/src/environments/environment.prod.ts
    # Make sure these are ordered and that the most recent version appears
    # last. See api.md#api-versioning when adding new versions.
    "ALLOWED_VERSIONS": ["1", "2", "3", "4", "5", "6", "7", "8", "9"],
    # DRF Spectacular default schema
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

if DEBUG:
    REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"].append(
        "paperless.auth.AngularApiAuthenticationOverride",
    )

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "paperless.middleware.ApiVersionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]

# Optional to enable compression
if get_bool_from_env("PAPERLESS_ENABLE_COMPRESSION", "yes"):  # pragma: no cover
    MIDDLEWARE.insert(0, "compression_middleware.middleware.CompressionMiddleware")

# Workaround to not compress streaming responses (e.g. chat).
# See https://github.com/friedelwolff/django-compression-middleware/pull/7
original_process_response = CompressionMiddleware.process_response


def patched_process_response(self, request, response):
    if getattr(request, "compress_exempt", False):
        return response
    return original_process_response(self, request, response)


CompressionMiddleware.process_response = patched_process_response

ROOT_URLCONF = "paperless.urls"


def _parse_base_paths() -> tuple[str, str, str, str, str]:
    script_name = os.getenv("PAPERLESS_FORCE_SCRIPT_NAME")
    base_url = (script_name or "") + "/"
    login_url = base_url + "accounts/login/"
    login_redirect_url = base_url + "dashboard"
    logout_redirect_url = os.getenv(
        "PAPERLESS_LOGOUT_REDIRECT_URL",
        login_url + "?loggedout=1",
    )
    return script_name, base_url, login_url, login_redirect_url, logout_redirect_url


FORCE_SCRIPT_NAME, BASE_URL, LOGIN_URL, LOGIN_REDIRECT_URL, LOGOUT_REDIRECT_URL = (
    _parse_base_paths()
)

# DRF Spectacular settings
SPECTACULAR_SETTINGS = {
    "TITLE": "Paperless-ngx REST API",
    "DESCRIPTION": "OpenAPI Spec for Paperless-ngx",
    "VERSION": "6.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SWAGGER_UI_DIST": "SIDECAR",
    "COMPONENT_SPLIT_REQUEST": True,
    "EXTERNAL_DOCS": {
        "description": "Paperless-ngx API Documentation",
        "url": "https://docs.paperless-ngx.com/api/",
    },
    "ENUM_NAME_OVERRIDES": {
        "MatchingAlgorithm": "documents.models.MatchingModel.MATCHING_ALGORITHMS",
    },
    "SCHEMA_PATH_PREFIX_INSERT": FORCE_SCRIPT_NAME or "",
}

WSGI_APPLICATION = "paperless.wsgi.application"
ASGI_APPLICATION = "paperless.asgi.application"

STATIC_URL = os.getenv("PAPERLESS_STATIC_URL", BASE_URL + "static/")
WHITENOISE_STATIC_PREFIX = "/static/"

STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
}

_CELERY_REDIS_URL, _CHANNELS_REDIS_URL = _parse_redis_url(
    os.getenv("PAPERLESS_REDIS", None),
)
_REDIS_KEY_PREFIX = os.getenv("PAPERLESS_REDIS_PREFIX", "")

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "documents.context_processors.settings",
            ],
        },
    },
]

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.pubsub.RedisPubSubChannelLayer",
        "CONFIG": {
            "hosts": [_CHANNELS_REDIS_URL],
            "capacity": 2000,  # default 100
            "expiry": 15,  # default 60
            "prefix": _REDIS_KEY_PREFIX,
        },
    },
}

###############################################################################
# Email (SMTP) Backend                                                        #
###############################################################################

EMAIL_HOST: Final[str] = os.getenv("PAPERLESS_EMAIL_HOST", "localhost")
EMAIL_PORT: Final[int] = int(os.getenv("PAPERLESS_EMAIL_PORT", 25))
EMAIL_HOST_USER: Final[str] = os.getenv("PAPERLESS_EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD: Final[str] = os.getenv("PAPERLESS_EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL: Final[str] = os.getenv("PAPERLESS_EMAIL_FROM", EMAIL_HOST_USER)
EMAIL_USE_TLS: Final[bool] = get_bool_from_env("PAPERLESS_EMAIL_USE_TLS")
EMAIL_USE_SSL: Final[bool] = get_bool_from_env("PAPERLESS_EMAIL_USE_SSL")
EMAIL_SUBJECT_PREFIX: Final[str] = "[Paperless-ngx] "
EMAIL_TIMEOUT = 30.0
EMAIL_ENABLED = EMAIL_HOST != "localhost" or EMAIL_HOST_USER != ""
if DEBUG:  # pragma: no cover
    EMAIL_BACKEND = "django.core.mail.backends.filebased.EmailBackend"
    EMAIL_FILE_PATH = BASE_DIR / "sent_emails"

###############################################################################
# Security                                                                    #
###############################################################################

AUTHENTICATION_BACKENDS = [
    "guardian.backends.ObjectPermissionBackend",
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

ACCOUNT_LOGOUT_ON_GET = True
ACCOUNT_DEFAULT_HTTP_PROTOCOL = os.getenv(
    "PAPERLESS_ACCOUNT_DEFAULT_HTTP_PROTOCOL",
    "https",
)

ACCOUNT_ADAPTER = "paperless.adapter.CustomAccountAdapter"
ACCOUNT_ALLOW_SIGNUPS = get_bool_from_env("PAPERLESS_ACCOUNT_ALLOW_SIGNUPS")
ACCOUNT_DEFAULT_GROUPS = get_list_from_env("PAPERLESS_ACCOUNT_DEFAULT_GROUPS")

SOCIALACCOUNT_ADAPTER = "paperless.adapter.CustomSocialAccountAdapter"
SOCIALACCOUNT_ALLOW_SIGNUPS = get_bool_from_env(
    "PAPERLESS_SOCIALACCOUNT_ALLOW_SIGNUPS",
    "yes",
)
SOCIALACCOUNT_AUTO_SIGNUP = get_bool_from_env("PAPERLESS_SOCIAL_AUTO_SIGNUP")
SOCIALACCOUNT_PROVIDERS = json.loads(
    os.getenv("PAPERLESS_SOCIALACCOUNT_PROVIDERS", "{}"),
)
SOCIAL_ACCOUNT_DEFAULT_GROUPS = get_list_from_env(
    "PAPERLESS_SOCIAL_ACCOUNT_DEFAULT_GROUPS",
)
SOCIAL_ACCOUNT_SYNC_GROUPS = get_bool_from_env("PAPERLESS_SOCIAL_ACCOUNT_SYNC_GROUPS")
SOCIAL_ACCOUNT_SYNC_GROUPS_CLAIM: Final[str] = os.getenv(
    "PAPERLESS_SOCIAL_ACCOUNT_SYNC_GROUPS_CLAIM",
    "groups",
)

HEADLESS_TOKEN_STRATEGY = "paperless.adapter.DrfTokenStrategy"

MFA_TOTP_ISSUER = "Paperless-ngx"

ACCOUNT_EMAIL_SUBJECT_PREFIX = "[Paperless-ngx] "

DISABLE_REGULAR_LOGIN = get_bool_from_env("PAPERLESS_DISABLE_REGULAR_LOGIN")
REDIRECT_LOGIN_TO_SSO = get_bool_from_env("PAPERLESS_REDIRECT_LOGIN_TO_SSO")

AUTO_LOGIN_USERNAME = os.getenv("PAPERLESS_AUTO_LOGIN_USERNAME")

ACCOUNT_EMAIL_VERIFICATION = (
    "none"
    if not EMAIL_ENABLED
    else os.getenv(
        "PAPERLESS_ACCOUNT_EMAIL_VERIFICATION",
        "optional",
    )
)

ACCOUNT_EMAIL_UNKNOWN_ACCOUNTS = get_bool_from_env(
    "PAPERLESS_ACCOUNT_EMAIL_UNKNOWN_ACCOUNTS",
    "True",
)

ACCOUNT_SESSION_REMEMBER = get_bool_from_env(
    "PAPERLESS_ACCOUNT_SESSION_REMEMBER",
    "True",
)
SESSION_EXPIRE_AT_BROWSER_CLOSE = not ACCOUNT_SESSION_REMEMBER
SESSION_COOKIE_AGE = int(
    os.getenv("PAPERLESS_SESSION_COOKIE_AGE", 60 * 60 * 24 * 7 * 3),
)
# https://docs.djangoproject.com/en/5.1/ref/settings/#std-setting-SESSION_ENGINE
SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"

if AUTO_LOGIN_USERNAME:
    _index = MIDDLEWARE.index("django.contrib.auth.middleware.AuthenticationMiddleware")
    # This overrides everything the auth middleware is doing but still allows
    # regular login in case the provided user does not exist.
    MIDDLEWARE.insert(_index + 1, "paperless.auth.AutoLoginMiddleware")


def _parse_remote_user_settings() -> str:
    global MIDDLEWARE, AUTHENTICATION_BACKENDS, REST_FRAMEWORK
    enable = get_bool_from_env("PAPERLESS_ENABLE_HTTP_REMOTE_USER")
    enable_api = get_bool_from_env("PAPERLESS_ENABLE_HTTP_REMOTE_USER_API")
    if enable or enable_api:
        MIDDLEWARE.append("paperless.auth.HttpRemoteUserMiddleware")
        AUTHENTICATION_BACKENDS.insert(
            0,
            "django.contrib.auth.backends.RemoteUserBackend",
        )

    if enable_api:
        REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"].insert(
            0,
            "paperless.auth.PaperlessRemoteUserAuthentication",
        )

    header_name = os.getenv(
        "PAPERLESS_HTTP_REMOTE_USER_HEADER_NAME",
        "HTTP_REMOTE_USER",
    )

    return header_name


HTTP_REMOTE_USER_HEADER_NAME = _parse_remote_user_settings()

# X-Frame options for embedded PDF display:
X_FRAME_OPTIONS = "SAMEORIGIN"

# The next 3 settings can also be set using just PAPERLESS_URL
CSRF_TRUSTED_ORIGINS = get_list_from_env("PAPERLESS_CSRF_TRUSTED_ORIGINS")

if DEBUG:
    # Allow access from the angular development server during debugging
    CSRF_TRUSTED_ORIGINS.append("http://localhost:4200")

# We allow CORS from localhost:8000
CORS_ALLOWED_ORIGINS = get_list_from_env(
    "PAPERLESS_CORS_ALLOWED_HOSTS",
    default=["http://localhost:8000"],
)

if DEBUG:
    # Allow access from the angular development server during debugging
    CORS_ALLOWED_ORIGINS.append("http://localhost:4200")

CORS_ALLOW_CREDENTIALS = True

CORS_EXPOSE_HEADERS = [
    "Content-Disposition",
]

ALLOWED_HOSTS = get_list_from_env("PAPERLESS_ALLOWED_HOSTS", default=["*"])
if ALLOWED_HOSTS != ["*"]:
    # always allow localhost. Necessary e.g. for healthcheck in docker.
    ALLOWED_HOSTS.append("localhost")


def _parse_paperless_url():
    global CSRF_TRUSTED_ORIGINS, CORS_ALLOWED_ORIGINS, ALLOWED_HOSTS
    url = os.getenv("PAPERLESS_URL")
    if url:
        CSRF_TRUSTED_ORIGINS.append(url)
        CORS_ALLOWED_ORIGINS.append(url)
        ALLOWED_HOSTS.append(urlparse(url).hostname)

    return url


PAPERLESS_URL = _parse_paperless_url()

# For use with trusted proxies
TRUSTED_PROXIES = get_list_from_env("PAPERLESS_TRUSTED_PROXIES")

USE_X_FORWARDED_HOST = get_bool_from_env("PAPERLESS_USE_X_FORWARD_HOST", "false")
USE_X_FORWARDED_PORT = get_bool_from_env("PAPERLESS_USE_X_FORWARD_PORT", "false")
SECURE_PROXY_SSL_HEADER = (
    tuple(json.loads(os.environ["PAPERLESS_PROXY_SSL_HEADER"]))
    if "PAPERLESS_PROXY_SSL_HEADER" in os.environ
    else None
)

# The secret key has a default that should be fine so long as you're hosting
# Paperless on a closed network.  However, if you're putting this anywhere
# public, you should change the key to something unique and verbose.
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

# Disable Django's artificial limit on the number of form fields to submit at
# once. This is a protection against overloading the server, but since this is
# a self-hosted sort of gig, the benefits of being able to mass-delete a ton
# of log entries outweigh the benefits of such a safeguard.

DATA_UPLOAD_MAX_NUMBER_FIELDS = None

COOKIE_PREFIX = os.getenv("PAPERLESS_COOKIE_PREFIX", "")

CSRF_COOKIE_NAME = f"{COOKIE_PREFIX}csrftoken"
SESSION_COOKIE_NAME = f"{COOKIE_PREFIX}sessionid"
LANGUAGE_COOKIE_NAME = f"{COOKIE_PREFIX}django_language"

EMAIL_CERTIFICATE_FILE = get_path_from_env("PAPERLESS_EMAIL_CERTIFICATE_LOCATION", None)


###############################################################################
# Database                                                                    #
###############################################################################
DATABASES = parse_db_settings(DATA_DIR)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

###############################################################################
# Internationalization                                                        #
###############################################################################

LANGUAGE_CODE = "en-us"

LANGUAGES = [
    ("en-us", _("English (US)")),  # needs to be first to act as fallback language
    ("ar-ar", _("Arabic")),
    ("af-za", _("Afrikaans")),
    ("be-by", _("Belarusian")),
    ("bg-bg", _("Bulgarian")),
    ("ca-es", _("Catalan")),
    ("cs-cz", _("Czech")),
    ("da-dk", _("Danish")),
    ("de-de", _("German")),
    ("el-gr", _("Greek")),
    ("en-gb", _("English (GB)")),
    ("es-es", _("Spanish")),
    ("fa-ir", _("Persian")),
    ("fi-fi", _("Finnish")),
    ("fr-fr", _("French")),
    ("hu-hu", _("Hungarian")),
    ("id-id", _("Indonesian")),
    ("it-it", _("Italian")),
    ("ja-jp", _("Japanese")),
    ("ko-kr", _("Korean")),
    ("lb-lu", _("Luxembourgish")),
    ("no-no", _("Norwegian")),
    ("nl-nl", _("Dutch")),
    ("pl-pl", _("Polish")),
    ("pt-br", _("Portuguese (Brazil)")),
    ("pt-pt", _("Portuguese")),
    ("ro-ro", _("Romanian")),
    ("ru-ru", _("Russian")),
    ("sk-sk", _("Slovak")),
    ("sl-si", _("Slovenian")),
    ("sr-cs", _("Serbian")),
    ("sv-se", _("Swedish")),
    ("tr-tr", _("Turkish")),
    ("uk-ua", _("Ukrainian")),
    ("vi-vn", _("Vietnamese")),
    ("zh-cn", _("Chinese Simplified")),
    ("zh-tw", _("Chinese Traditional")),
]

LOCALE_PATHS = [BASE_DIR / "locale"]

TIME_ZONE = os.getenv("PAPERLESS_TIME_ZONE", "UTC")

USE_I18N = True

USE_L10N = True

USE_TZ = True

###############################################################################
# Logging                                                                     #
###############################################################################

LOGGING_DIR.mkdir(parents=True, exist_ok=True)

LOGROTATE_MAX_SIZE = os.getenv("PAPERLESS_LOGROTATE_MAX_SIZE", 1024 * 1024)
LOGROTATE_MAX_BACKUPS = os.getenv("PAPERLESS_LOGROTATE_MAX_BACKUPS", 20)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] [{levelname}] [{name}] {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "level": "DEBUG" if DEBUG else "INFO",
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "file_paperless": {
            "class": "concurrent_log_handler.ConcurrentRotatingFileHandler",
            "formatter": "verbose",
            "filename": LOGGING_DIR / "paperless.log",
            "maxBytes": LOGROTATE_MAX_SIZE,
            "backupCount": LOGROTATE_MAX_BACKUPS,
        },
        "file_mail": {
            "class": "concurrent_log_handler.ConcurrentRotatingFileHandler",
            "formatter": "verbose",
            "filename": LOGGING_DIR / "mail.log",
            "maxBytes": LOGROTATE_MAX_SIZE,
            "backupCount": LOGROTATE_MAX_BACKUPS,
        },
        "file_celery": {
            "class": "concurrent_log_handler.ConcurrentRotatingFileHandler",
            "formatter": "verbose",
            "filename": LOGGING_DIR / "celery.log",
            "maxBytes": LOGROTATE_MAX_SIZE,
            "backupCount": LOGROTATE_MAX_BACKUPS,
        },
    },
    "root": {"handlers": ["console"]},
    "loggers": {
        "paperless": {"handlers": ["file_paperless"], "level": "DEBUG"},
        "paperless_mail": {"handlers": ["file_mail"], "level": "DEBUG"},
        "paperless_ai": {"handlers": ["file_paperless"], "level": "DEBUG"},
        "ocrmypdf": {"handlers": ["file_paperless"], "level": "INFO"},
        "celery": {"handlers": ["file_celery"], "level": "DEBUG"},
        "kombu": {"handlers": ["file_celery"], "level": "DEBUG"},
        "_granian": {"handlers": ["file_paperless"], "level": "DEBUG"},
        "granian.access": {"handlers": ["file_paperless"], "level": "DEBUG"},
    },
}

# Configure logging before calling any logger in settings.py so it will respect the log format, even if Django has not parsed the settings yet.
logging.config.dictConfig(LOGGING)


###############################################################################
# Task queue                                                                  #
###############################################################################

# https://docs.celeryq.dev/en/stable/userguide/configuration.html

CELERY_BROKER_URL = _CELERY_REDIS_URL
CELERY_TIMEZONE = TIME_ZONE

CELERY_WORKER_HIJACK_ROOT_LOGGER = False
CELERY_WORKER_CONCURRENCY: Final[int] = get_int_from_env("PAPERLESS_TASK_WORKERS", 1)
TASK_WORKERS = CELERY_WORKER_CONCURRENCY
CELERY_WORKER_MAX_TASKS_PER_CHILD = 1
CELERY_WORKER_SEND_TASK_EVENTS = True
CELERY_TASK_SEND_SENT_EVENT = True
CELERY_SEND_TASK_SENT_EVENT = True
CELERY_BROKER_CONNECTION_RETRY = True
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_BROKER_TRANSPORT_OPTIONS = {
    "global_keyprefix": _REDIS_KEY_PREFIX,
}

CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT: Final[int] = get_int_from_env("PAPERLESS_WORKER_TIMEOUT", 1800)

CELERY_RESULT_EXTENDED = True
CELERY_RESULT_BACKEND = "django-db"
CELERY_CACHE_BACKEND = "default"

# https://docs.celeryq.dev/en/stable/userguide/configuration.html#task-serializer
CELERY_TASK_SERIALIZER = "pickle"
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#std-setting-accept_content
CELERY_ACCEPT_CONTENT = ["application/json", "application/x-python-serialize"]

# https://docs.celeryq.dev/en/stable/userguide/configuration.html#beat-schedule
CELERY_BEAT_SCHEDULE = _parse_beat_schedule()

# https://docs.celeryq.dev/en/stable/userguide/configuration.html#beat-schedule-filename
CELERY_BEAT_SCHEDULE_FILENAME = str(DATA_DIR / "celerybeat-schedule.db")


# Cachalot: Database read cache.
def _parse_cachalot_settings():
    ttl = get_int_from_env("PAPERLESS_READ_CACHE_TTL", 3600)
    ttl = min(ttl, 31536000) if ttl > 0 else 3600
    _, redis_url = _parse_redis_url(
        os.getenv("PAPERLESS_READ_CACHE_REDIS_URL", _CHANNELS_REDIS_URL),
    )
    result = {
        "CACHALOT_CACHE": "read-cache",
        "CACHALOT_ENABLED": get_bool_from_env(
            "PAPERLESS_DB_READ_CACHE_ENABLED",
            default="no",
        ),
        "CACHALOT_FINAL_SQL_CHECK": True,
        "CACHALOT_QUERY_KEYGEN": "paperless.db_cache.custom_get_query_cache_key",
        "CACHALOT_TABLE_KEYGEN": "paperless.db_cache.custom_get_table_cache_key",
        "CACHALOT_REDIS_URL": redis_url,
        "CACHALOT_TIMEOUT": ttl,
    }
    return result


cachalot_settings = _parse_cachalot_settings()
CACHALOT_ENABLED = cachalot_settings["CACHALOT_ENABLED"]
if CACHALOT_ENABLED:  # pragma: no cover
    INSTALLED_APPS.append("cachalot")
CACHALOT_CACHE = cachalot_settings["CACHALOT_CACHE"]
CACHALOT_TIMEOUT = cachalot_settings["CACHALOT_TIMEOUT"]
CACHALOT_QUERY_KEYGEN = cachalot_settings["CACHALOT_QUERY_KEYGEN"]
CACHALOT_TABLE_KEYGEN = cachalot_settings["CACHALOT_TABLE_KEYGEN"]
CACHALOT_FINAL_SQL_CHECK = cachalot_settings["CACHALOT_FINAL_SQL_CHECK"]


# Django default & Cachalot cache configuration
_CACHE_BACKEND = os.environ.get(
    "PAPERLESS_CACHE_BACKEND",
    "django.core.cache.backends.locmem.LocMemCache"
    if DEBUG
    else "django.core.cache.backends.redis.RedisCache",
)


def _parse_caches():
    return {
        "default": {
            "BACKEND": _CACHE_BACKEND,
            "LOCATION": _CHANNELS_REDIS_URL,
            "KEY_PREFIX": _REDIS_KEY_PREFIX,
        },
        "read-cache": {
            "BACKEND": _CACHE_BACKEND,
            "LOCATION": cachalot_settings["CACHALOT_REDIS_URL"],
            "KEY_PREFIX": _REDIS_KEY_PREFIX,
        },
    }


CACHES = _parse_caches()


def default_threads_per_worker(task_workers) -> int:
    # always leave one core open
    available_cores = max(multiprocessing.cpu_count(), 1)
    try:
        return max(math.floor(available_cores / task_workers), 1)
    except NotImplementedError:
        return 1


THREADS_PER_WORKER = os.getenv(
    "PAPERLESS_THREADS_PER_WORKER",
    default_threads_per_worker(CELERY_WORKER_CONCURRENCY),
)

###############################################################################
# Paperless Specific Settings                                                 #
###############################################################################

IGNORABLE_FILES: Final[list[str]] = [
    ".DS_Store",
    ".DS_STORE",
    "._*",
    ".stfolder/*",
    ".stversions/*",
    ".localized/*",
    "desktop.ini",
    "@eaDir/*",
    "Thumbs.db",
]

CONSUMER_POLLING_INTERVAL = float(os.getenv("PAPERLESS_CONSUMER_POLLING_INTERVAL", 0))

CONSUMER_STABILITY_DELAY = float(os.getenv("PAPERLESS_CONSUMER_STABILITY_DELAY", 5))

CONSUMER_DELETE_DUPLICATES = get_bool_from_env("PAPERLESS_CONSUMER_DELETE_DUPLICATES")

CONSUMER_RECURSIVE = get_bool_from_env("PAPERLESS_CONSUMER_RECURSIVE")

# Ignore regex patterns, matched against filename only
CONSUMER_IGNORE_PATTERNS = list(
    json.loads(
        os.getenv(
            "PAPERLESS_CONSUMER_IGNORE_PATTERNS",
            json.dumps([]),
        ),
    ),
)

# Directories to always ignore.  These are matched by directory name, not full path
CONSUMER_IGNORE_DIRS = list(
    json.loads(
        os.getenv(
            "PAPERLESS_CONSUMER_IGNORE_DIRS",
            json.dumps([]),
        ),
    ),
)

CONSUMER_SUBDIRS_AS_TAGS = get_bool_from_env("PAPERLESS_CONSUMER_SUBDIRS_AS_TAGS")

CONSUMER_ENABLE_BARCODES: Final[bool] = get_bool_from_env(
    "PAPERLESS_CONSUMER_ENABLE_BARCODES",
)

CONSUMER_BARCODE_TIFF_SUPPORT: Final[bool] = get_bool_from_env(
    "PAPERLESS_CONSUMER_BARCODE_TIFF_SUPPORT",
)

CONSUMER_BARCODE_STRING: Final[str] = os.getenv(
    "PAPERLESS_CONSUMER_BARCODE_STRING",
    "PATCHT",
)

CONSUMER_ENABLE_ASN_BARCODE: Final[bool] = get_bool_from_env(
    "PAPERLESS_CONSUMER_ENABLE_ASN_BARCODE",
)

CONSUMER_ASN_BARCODE_PREFIX: Final[str] = os.getenv(
    "PAPERLESS_CONSUMER_ASN_BARCODE_PREFIX",
    "ASN",
)

CONSUMER_BARCODE_UPSCALE: Final[float] = get_float_from_env(
    "PAPERLESS_CONSUMER_BARCODE_UPSCALE",
    0.0,
)

CONSUMER_BARCODE_DPI: Final[int] = get_int_from_env(
    "PAPERLESS_CONSUMER_BARCODE_DPI",
    300,
)

CONSUMER_BARCODE_MAX_PAGES: Final[int] = get_int_from_env(
    "PAPERLESS_CONSUMER_BARCODE_MAX_PAGES",
    0,
)

CONSUMER_BARCODE_RETAIN_SPLIT_PAGES = get_bool_from_env(
    "PAPERLESS_CONSUMER_BARCODE_RETAIN_SPLIT_PAGES",
)

CONSUMER_ENABLE_TAG_BARCODE: Final[bool] = get_bool_from_env(
    "PAPERLESS_CONSUMER_ENABLE_TAG_BARCODE",
)

CONSUMER_TAG_BARCODE_MAPPING = dict(
    json.loads(
        os.getenv(
            "PAPERLESS_CONSUMER_TAG_BARCODE_MAPPING",
            '{"TAG:(.*)": "\\\\g<1>"}',
        ),
    ),
)

CONSUMER_TAG_BARCODE_SPLIT: Final[bool] = get_bool_from_env(
    "PAPERLESS_CONSUMER_TAG_BARCODE_SPLIT",
)

CONSUMER_ENABLE_COLLATE_DOUBLE_SIDED: Final[bool] = get_bool_from_env(
    "PAPERLESS_CONSUMER_ENABLE_COLLATE_DOUBLE_SIDED",
)

CONSUMER_COLLATE_DOUBLE_SIDED_SUBDIR_NAME: Final[str] = os.getenv(
    "PAPERLESS_CONSUMER_COLLATE_DOUBLE_SIDED_SUBDIR_NAME",
    "double-sided",
)

CONSUMER_COLLATE_DOUBLE_SIDED_TIFF_SUPPORT: Final[bool] = get_bool_from_env(
    "PAPERLESS_CONSUMER_COLLATE_DOUBLE_SIDED_TIFF_SUPPORT",
)

CONSUMER_PDF_RECOVERABLE_MIME_TYPES = ("application/octet-stream",)

OCR_PAGES = get_int_from_env("PAPERLESS_OCR_PAGES", None)

# The default language that tesseract will attempt to use when parsing
# documents.  It should be a 3-letter language code consistent with ISO 639.
OCR_LANGUAGE = os.getenv("PAPERLESS_OCR_LANGUAGE", "eng")

# OCRmyPDF --output-type options are available.
OCR_OUTPUT_TYPE = os.getenv("PAPERLESS_OCR_OUTPUT_TYPE", "pdfa")

# skip. redo, force
OCR_MODE = os.getenv("PAPERLESS_OCR_MODE", "skip")

OCR_SKIP_ARCHIVE_FILE = os.getenv("PAPERLESS_OCR_SKIP_ARCHIVE_FILE", "never")

OCR_IMAGE_DPI = get_int_from_env("PAPERLESS_OCR_IMAGE_DPI", None)

OCR_CLEAN = os.getenv("PAPERLESS_OCR_CLEAN", "clean")

OCR_DESKEW: Final[bool] = get_bool_from_env("PAPERLESS_OCR_DESKEW", "true")

OCR_ROTATE_PAGES: Final[bool] = get_bool_from_env("PAPERLESS_OCR_ROTATE_PAGES", "true")

OCR_ROTATE_PAGES_THRESHOLD: Final[float] = get_float_from_env(
    "PAPERLESS_OCR_ROTATE_PAGES_THRESHOLD",
    12.0,
)

OCR_MAX_IMAGE_PIXELS: Final[int | None] = get_int_from_env(
    "PAPERLESS_OCR_MAX_IMAGE_PIXELS",
    None,
)

OCR_COLOR_CONVERSION_STRATEGY = os.getenv(
    "PAPERLESS_OCR_COLOR_CONVERSION_STRATEGY",
    "RGB",
)

OCR_USER_ARGS = os.getenv("PAPERLESS_OCR_USER_ARGS")

MAX_IMAGE_PIXELS: Final[int | None] = get_int_from_env(
    "PAPERLESS_MAX_IMAGE_PIXELS",
    None,
)

# GNUPG needs a home directory for some reason
GNUPG_HOME = os.getenv("HOME", "/tmp")

# Convert is part of the ImageMagick package
CONVERT_BINARY = os.getenv("PAPERLESS_CONVERT_BINARY", "convert")
CONVERT_TMPDIR = os.getenv("PAPERLESS_CONVERT_TMPDIR")
CONVERT_MEMORY_LIMIT = os.getenv("PAPERLESS_CONVERT_MEMORY_LIMIT")

GS_BINARY = os.getenv("PAPERLESS_GS_BINARY", "gs")

# Fallback layout for .eml consumption
EMAIL_PARSE_DEFAULT_LAYOUT = get_int_from_env(
    "PAPERLESS_EMAIL_PARSE_DEFAULT_LAYOUT",
    1,  # MailRule.PdfLayout.TEXT_HTML but that can't be imported here
)

# Trigger a script after every successful document consumption?
PRE_CONSUME_SCRIPT = os.getenv("PAPERLESS_PRE_CONSUME_SCRIPT")
POST_CONSUME_SCRIPT = os.getenv("PAPERLESS_POST_CONSUME_SCRIPT")

# Specify the default date order (for autodetected dates)
DATE_ORDER = os.getenv("PAPERLESS_DATE_ORDER", "DMY")
FILENAME_DATE_ORDER = os.getenv("PAPERLESS_FILENAME_DATE_ORDER")


def _parse_dateparser_languages(languages: str | None):
    language_list = languages.split("+") if languages else []
    # There is an unfixed issue in zh-Hant and zh-Hans locales in the dateparser lib.
    # See: https://github.com/scrapinghub/dateparser/issues/875
    for index, language in enumerate(language_list):
        if language.startswith("zh-") and "zh" not in language_list:
            logger.warning(
                f'Chinese locale detected: {language}. dateparser might fail to parse some dates with this locale, so Chinese ("zh") will be used as a fallback.',
            )
            language_list.append("zh")

    return list(LocaleDataLoader().get_locale_map(locales=language_list))


# If not set, we will infer it at runtime
DATE_PARSER_LANGUAGES = (
    _parse_dateparser_languages(
        os.getenv("PAPERLESS_DATE_PARSER_LANGUAGES"),
    )
    if os.getenv("PAPERLESS_DATE_PARSER_LANGUAGES")
    else None
)


# Maximum number of dates taken from document start to end to show as suggestions for
# `created` date in the frontend. Duplicates are removed, which can result in
# fewer dates shown.
NUMBER_OF_SUGGESTED_DATES = get_int_from_env("PAPERLESS_NUMBER_OF_SUGGESTED_DATES", 3)

# Specify the filename format for out files
FILENAME_FORMAT = os.getenv("PAPERLESS_FILENAME_FORMAT")

# If this is enabled, variables in filename format will resolve to
# empty-string instead of 'none'.
# Directories with 'empty names' are omitted, too.
FILENAME_FORMAT_REMOVE_NONE = get_bool_from_env(
    "PAPERLESS_FILENAME_FORMAT_REMOVE_NONE",
    "NO",
)

THUMBNAIL_FONT_NAME = os.getenv(
    "PAPERLESS_THUMBNAIL_FONT_NAME",
    "/usr/share/fonts/liberation/LiberationSerif-Regular.ttf",
)

# Tika settings
TIKA_ENABLED = get_bool_from_env("PAPERLESS_TIKA_ENABLED", "NO")
TIKA_ENDPOINT = os.getenv("PAPERLESS_TIKA_ENDPOINT", "http://localhost:9998")
TIKA_GOTENBERG_ENDPOINT = os.getenv(
    "PAPERLESS_TIKA_GOTENBERG_ENDPOINT",
    "http://localhost:3000",
)

if TIKA_ENABLED:
    INSTALLED_APPS.append("paperless_tika.apps.PaperlessTikaConfig")

AUDIT_LOG_ENABLED = get_bool_from_env("PAPERLESS_AUDIT_LOG_ENABLED", "true")
if AUDIT_LOG_ENABLED:
    INSTALLED_APPS.append("auditlog")
    MIDDLEWARE.append("auditlog.middleware.AuditlogMiddleware")


def _parse_ignore_dates(
    env_ignore: str,
    date_order: str = DATE_ORDER,
) -> set[datetime.datetime]:
    """
    If the PAPERLESS_IGNORE_DATES environment variable is set, parse the
    user provided string(s) into dates

    Args:
        env_ignore (str): The value of the environment variable, comma separated dates
        date_order (str, optional): The format of the date strings.
                                    Defaults to DATE_ORDER.

    Returns:
        Set[datetime.datetime]: The set of parsed date objects
    """
    import dateparser

    ignored_dates = set()
    for s in env_ignore.split(","):
        d = dateparser.parse(
            s,
            settings={
                "DATE_ORDER": date_order,
            },
        )
        if d:
            ignored_dates.add(d.date())
    return ignored_dates


# List dates that should be ignored when trying to parse date from document text
IGNORE_DATES: set[datetime.date] = set()

if os.getenv("PAPERLESS_IGNORE_DATES") is not None:
    IGNORE_DATES = _parse_ignore_dates(os.getenv("PAPERLESS_IGNORE_DATES"))

ENABLE_UPDATE_CHECK = os.getenv("PAPERLESS_ENABLE_UPDATE_CHECK", "default")
if ENABLE_UPDATE_CHECK != "default":
    ENABLE_UPDATE_CHECK = get_bool_from_env("PAPERLESS_ENABLE_UPDATE_CHECK")

APP_TITLE = os.getenv("PAPERLESS_APP_TITLE", None)
APP_LOGO = os.getenv("PAPERLESS_APP_LOGO", None)

###############################################################################
# Machine Learning                                                            #
###############################################################################


def _get_nltk_language_setting(ocr_lang: str) -> str | None:
    """
    Maps an ISO-639-1 language code supported by Tesseract into
    an optional NLTK language name.  This is the set of common supported
    languages for all the NLTK data used.

    Assumption: The primary language is first

    NLTK Languages:
      - https://www.nltk.org/api/nltk.stem.snowball.html#nltk.stem.snowball.SnowballStemmer
      - https://raw.githubusercontent.com/nltk/nltk_data/gh-pages/packages/tokenizers/punkt.zip
      - https://raw.githubusercontent.com/nltk/nltk_data/gh-pages/packages/corpora/stopwords.zip

    The common intersection between all languages in those 3 is handled here

    """
    ocr_lang = ocr_lang.split("+", maxsplit=1)[0]
    iso_code_to_nltk = {
        "dan": "danish",
        "nld": "dutch",
        "eng": "english",
        "fin": "finnish",
        "fra": "french",
        "deu": "german",
        "ita": "italian",
        "nor": "norwegian",
        "por": "portuguese",
        "rus": "russian",
        "spa": "spanish",
        "swe": "swedish",
    }

    return iso_code_to_nltk.get(ocr_lang)


NLTK_ENABLED: Final[bool] = get_bool_from_env("PAPERLESS_ENABLE_NLTK", "yes")

NLTK_LANGUAGE: str | None = _get_nltk_language_setting(OCR_LANGUAGE)

###############################################################################
# Email Preprocessors                                                         #
###############################################################################

EMAIL_GNUPG_HOME: Final[str | None] = os.getenv("PAPERLESS_EMAIL_GNUPG_HOME")
EMAIL_ENABLE_GPG_DECRYPTOR: Final[bool] = get_bool_from_env(
    "PAPERLESS_ENABLE_GPG_DECRYPTOR",
)


###############################################################################
# Soft Delete                                                                 #
###############################################################################
EMPTY_TRASH_DELAY = max(get_int_from_env("PAPERLESS_EMPTY_TRASH_DELAY", 30), 1)


###############################################################################
# Oauth Email                                                                 #
###############################################################################
OAUTH_CALLBACK_BASE_URL = os.getenv("PAPERLESS_OAUTH_CALLBACK_BASE_URL")
GMAIL_OAUTH_CLIENT_ID = os.getenv("PAPERLESS_GMAIL_OAUTH_CLIENT_ID")
GMAIL_OAUTH_CLIENT_SECRET = os.getenv("PAPERLESS_GMAIL_OAUTH_CLIENT_SECRET")
GMAIL_OAUTH_ENABLED = bool(
    (OAUTH_CALLBACK_BASE_URL or PAPERLESS_URL)
    and GMAIL_OAUTH_CLIENT_ID
    and GMAIL_OAUTH_CLIENT_SECRET,
)
OUTLOOK_OAUTH_CLIENT_ID = os.getenv("PAPERLESS_OUTLOOK_OAUTH_CLIENT_ID")
OUTLOOK_OAUTH_CLIENT_SECRET = os.getenv("PAPERLESS_OUTLOOK_OAUTH_CLIENT_SECRET")
OUTLOOK_OAUTH_ENABLED = bool(
    (OAUTH_CALLBACK_BASE_URL or PAPERLESS_URL)
    and OUTLOOK_OAUTH_CLIENT_ID
    and OUTLOOK_OAUTH_CLIENT_SECRET,
)

###############################################################################
# Webhooks
###############################################################################
WEBHOOKS_ALLOWED_SCHEMES = set(
    s.lower()
    for s in get_list_from_env(
        "PAPERLESS_WEBHOOKS_ALLOWED_SCHEMES",
        default=["http", "https"],
    )
)
WEBHOOKS_ALLOWED_PORTS = set(
    int(p)
    for p in get_list_from_env(
        "PAPERLESS_WEBHOOKS_ALLOWED_PORTS",
        default=[],
    )
)
WEBHOOKS_ALLOW_INTERNAL_REQUESTS = get_bool_from_env(
    "PAPERLESS_WEBHOOKS_ALLOW_INTERNAL_REQUESTS",
    "true",
)

###############################################################################
# Remote Parser                                                               #
###############################################################################
REMOTE_OCR_ENGINE = os.getenv("PAPERLESS_REMOTE_OCR_ENGINE")
REMOTE_OCR_API_KEY = os.getenv("PAPERLESS_REMOTE_OCR_API_KEY")
REMOTE_OCR_ENDPOINT = os.getenv("PAPERLESS_REMOTE_OCR_ENDPOINT")

################################################################################
# AI Settings                                                                  #
################################################################################
AI_ENABLED = get_bool_from_env("PAPERLESS_AI_ENABLED", "NO")
LLM_EMBEDDING_BACKEND = os.getenv(
    "PAPERLESS_AI_LLM_EMBEDDING_BACKEND",
)  # "huggingface" or "openai"
LLM_EMBEDDING_MODEL = os.getenv("PAPERLESS_AI_LLM_EMBEDDING_MODEL")
LLM_BACKEND = os.getenv("PAPERLESS_AI_LLM_BACKEND")  # "ollama" or "openai"
LLM_MODEL = os.getenv("PAPERLESS_AI_LLM_MODEL")
LLM_API_KEY = os.getenv("PAPERLESS_AI_LLM_API_KEY")
LLM_ENDPOINT = os.getenv("PAPERLESS_AI_LLM_ENDPOINT")
