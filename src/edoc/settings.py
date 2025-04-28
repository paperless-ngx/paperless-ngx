import datetime
import json
import math
import multiprocessing
import os
import re
import tempfile
from os import PathLike
from pathlib import Path
from platform import machine
from typing import Final
from typing import Optional
from typing import Union
from urllib.parse import urlparse

from celery.schedules import crontab
from concurrent_log_handler.queue import setup_logging_queues
from django.utils.translation import gettext_lazy as _
from dotenv import load_dotenv
from decouple import config

# Tap edoc.conf if it's available
configuration_path = os.getenv("EDOC_CONFIGURATION_PATH")
if configuration_path and os.path.exists(configuration_path):
    load_dotenv(configuration_path)
elif os.path.exists("../edoc.conf"):
    load_dotenv("../edoc.conf")
elif os.path.exists("/etc/edoc.conf"):
    load_dotenv("/etc/edoc.conf")
elif os.path.exists("/usr/local/etc/edoc.conf"):
    load_dotenv("/usr/local/etc/edoc.conf")

# There are multiple levels of concurrency in edoc:
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


def __get_boolean(key: str, default: str = "NO") -> bool:
    """
    Return a boolean value based on whatever the user has supplied in the
    environment based on whether the value "looks like" it's True or not.
    """
    return bool(
        os.getenv(key, default).lower() in ("yes", "y", "1", "t", "true"))


def __get_int(key: str, default: int) -> int:
    """
    Return an integer value based on the environment variable or a default
    """
    return int(os.getenv(key, default))


def __get_optional_int(key: str) -> Optional[int]:
    """
    Returns None if the environment key is not present, otherwise an integer
    """
    if key in os.environ:
        return __get_int(key, -1)  # pragma: no cover
    return None


def __get_float(key: str, default: float) -> float:
    """
    Return an integer value based on the environment variable or a default
    """
    return float(os.getenv(key, default))


def __get_path(
    key: str,
    default: Union[PathLike, str],
) -> Path:
    """
    Return a normalized, absolute path based on the environment variable or a default,
    if provided
    """
    if key in os.environ:
        return Path(os.environ[key]).resolve()
    return Path(default).resolve()


def __get_optional_path(key: str) -> Optional[Path]:
    """
    Returns None if the environment key is not present, otherwise a fully resolved Path
    """
    if key in os.environ:
        return __get_path(key, "")
    return None


def __get_list(
    key: str,
    default: Optional[list[str]] = None,
    sep: str = ",",
) -> list[str]:
    """
    Return a list of elements from the environment, as separated by the given
    string, or the default if the key does not exist
    """
    if key in os.environ:
        return list(filter(None, os.environ[key].split(sep)))
    elif default is not None:
        return default
    else:
        return []


def _parse_redis_url(env_redis: Optional[str]) -> tuple[str]:
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
            "env_key": "EDOC_EMAIL_TASK_CRON",
            # Default every ten minutes
            "env_default": "*/10 * * * *",
            "task": "edoc_mail.tasks.process_mail_accounts",
            "options": {
                # 1 minute before default schedule sends again
                "expires": 9.0
                           * 60.0,
            },
        },
        # {
        #     "name": "Train the classifier",
        #     "env_key": "EDOC_TRAIN_TASK_CRON",
        #     "env_default": "0 2 * * *",  # 2:00 sáng mỗi ngày
        #     "task": "documents.tasks.train_classifier",
        #     "options": {
        #         "expires": 3600.0,
        #         # Tùy chọn: hết hạn sau 1 tiếng nếu chưa được thực thi
        #     },
        # },

        # {
        #     "name": "Optimize the index",
        #     "env_key": "EDOC_INDEX_TASK_CRON",
        #     # Default daily at midnight
        #     "env_default": "0 0 * * *",
        #     "task": "documents.tasks.index_optimize",
        #     "options": {
        #         # 1 hour before default schedule sends again
        #         "expires": 23.0
        #         * 60.0
        #         * 60.0,
        #     },
        # },
        {
            "name": "Perform sanity check",
            "env_key": "EDOC_SANITY_TASK_CRON",
            # Default Sunday at 00:30
            "env_default": "30 0 * * sun",
            "task": "documents.tasks.sanity_check",
            "options": {
                # 1 hour before default schedule sends again
                "expires": ((7.0 * 24.0) - 1.0)
                           * 60.0
                           * 60.0,
            },
        },
        {
            "name": "Empty trash",
            "env_key": "EDOC_EMPTY_TRASH_TASK_CRON",
            # Default daily at 01:00
            "env_default": "0 1 * * *",
            "task": "documents.tasks.empty_trash",
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
DEBUG = config("EDOC_DEBUG", default=True, cast=bool)

###############################################################################
# Directories                                                                 #
###############################################################################

BASE_DIR: Path = Path(__file__).resolve().parent.parent

STATIC_ROOT = __get_path("EDOC_STATICDIR", BASE_DIR.parent / "static")

MEDIA_ROOT = __get_path("EDOC_MEDIA_ROOT", BASE_DIR.parent / "media")
BACKUP_DIR = MEDIA_ROOT / "backups"
ORIGINALS_DIR = MEDIA_ROOT / "documents" / "originals"
ARCHIVE_DIR = MEDIA_ROOT / "documents" / "archive"
THUMBNAIL_DIR = MEDIA_ROOT / "documents" / "thumbnails"

DATA_DIR = __get_path("EDOC_DATA_DIR", BASE_DIR.parent / "data")

NLTK_DIR = __get_path("EDOC_NLTK_DIR", "/usr/share/nltk_data")

TRASH_DIR = os.getenv("EDOC_TRASH_DIR")

# Lock file for synchronizing changes to the MEDIA directory across multiple
# threads.
MEDIA_LOCK = MEDIA_ROOT / "media.lock"
INDEX_DIR = DATA_DIR / "index"
MODEL_FILE = DATA_DIR / "classification_model.pickle"

LOGGING_DIR = __get_path("EDOC_LOGGING_DIR", DATA_DIR / "log")

CONSUMPTION_DIR = __get_path(
    "EDOC_CONSUMPTION_DIR",
    BASE_DIR.parent / "consume",
)

# This will be created if it doesn't exist
SCRATCH_DIR = __get_path(
    "EDOC_SCRATCH_DIR",
    Path(tempfile.gettempdir()) / "edoc",
)

###############################################################################
# Application Definition                                                      #
###############################################################################

env_apps = __get_list("EDOC_APPS")

INSTALLED_APPS = [
    "whitenoise.runserver_nostatic",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_elasticsearch_dsl",
    "django_elasticsearch_dsl_drf",
    "corsheaders",
    "django_extensions",
    "edoc",
    "documents.apps.DocumentsConfig",
    "edoc_tesseract.apps.EdocTesseractConfig",
    "edoc_ocr_custom.apps.EdocTesseractConfig",
    "edoc_text.apps.EdocTextConfig",
    "edoc_mail.apps.EdocMailConfig",
    "django.contrib.admin",
    "rest_framework",
    "rest_framework.authtoken",
    "django_filters",
    "django_celery_results",
    "guardian",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    # "django_apscheduler",
    "debug_toolbar",
    *env_apps,
]

if DEBUG:
    INSTALLED_APPS.append("channels")

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.BasicAuthentication",
        "rest_framework.authentication.TokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_VERSIONING_CLASS": "rest_framework.versioning.AcceptHeaderVersioning",
    "DEFAULT_VERSION": "1",
    # Make sure these are ordered and that the most recent version appears
    # last
    "ALLOWED_VERSIONS": ["1", "2", "3", "4", "5"],
}

if DEBUG:
    REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"].append(
        "edoc.auth.AngularApiAuthenticationOverride",
    )

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "edoc.middleware.LoginLanguageMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",

    "debug_toolbar.middleware.DebugToolbarMiddleware",

    "edoc.middleware.ApiVersionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]

# Optional to enable compression
if __get_boolean("EDOC_ENABLE_COMPRESSION", "yes"):  # pragma: no cover
    MIDDLEWARE.insert(0,
                      "compression_middleware.middleware.CompressionMiddleware")

ROOT_URLCONF = "edoc.urls"


def _parse_base_paths() -> tuple[str, str, str, str, str]:
    script_name = os.getenv("EDOC_FORCE_SCRIPT_NAME")
    base_url = (script_name or "") + "/"
    login_url = base_url + "accounts/login/"
    login_redirect_url = base_url + "folders/roots"
    logout_redirect_url = os.getenv("EDOC_LOGOUT_REDIRECT_URL", base_url)
    return script_name, base_url, login_url, login_redirect_url, logout_redirect_url


FORCE_SCRIPT_NAME, BASE_URL, LOGIN_URL, LOGIN_REDIRECT_URL, LOGOUT_REDIRECT_URL = (
    _parse_base_paths()
)

WSGI_APPLICATION = "edoc.wsgi.application"
ASGI_APPLICATION = "edoc.asgi.application"

STATIC_URL = os.getenv("EDOC_STATIC_URL", BASE_URL + "static/")
WHITENOISE_STATIC_PREFIX = "/static/"

if machine().lower() == "aarch64":  # pragma: no cover
    _static_backend = "django.contrib.staticfiles.storage.StaticFilesStorage"
else:
    _static_backend = "whitenoise.storage.CompressedStaticFilesStorage"

STORAGES = {
    "staticfiles": {
        "BACKEND": _static_backend,
    },
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
}

_CELERY_REDIS_URL, _CHANNELS_REDIS_URL = _parse_redis_url(
    os.getenv("EDOC_REDIS", ''),
)

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
            "prefix": os.getenv("EDOC_REDIS_PREFIX", ""),
        },
    },
}

# EDOC_OCR_CUSTOM
TCGROUP_OCR_CUSTOM = {
    "URL": {
        "URL_UPLOAD_FILE": os.getenv("URL_UPLOAD_FILE",
                                     "https://ocr-core-api.tcgroup.vn/api/v1/file/upload"),
        "URL_OCR_BY_FILEID": os.getenv("URL_OCR_BY_FILEID",
                                       "https://ocr-core-api.tcgroup.vn/api/v1/ocr/general"),
        "URL_OCR_CUSTOM_FIELD_BY_FILEID": os.getenv(
            "URL_OCR_CUSTOM_FIELD_BY_FILEID",
            "https://ocr-general-api.tcgroup.vn/home/api/v1/extract-by-rule"),
    }
}

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
    "EDOC_ACCOUNT_DEFAULT_HTTP_PROTOCOL",
    "https",
)

ACCOUNT_ADAPTER = "edoc.adapter.CustomAccountAdapter"
ACCOUNT_ALLOW_SIGNUPS = __get_boolean("EDOC_ACCOUNT_ALLOW_SIGNUPS")

SOCIALACCOUNT_ADAPTER = "edoc.adapter.CustomSocialAccountAdapter"
SOCIALACCOUNT_ALLOW_SIGNUPS = __get_boolean(
    "EDOC_SOCIALACCOUNT_ALLOW_SIGNUPS",
    "yes",
)
SOCIALACCOUNT_AUTO_SIGNUP = __get_boolean("EDOC_SOCIAL_AUTO_SIGNUP")
SOCIALACCOUNT_PROVIDERS = json.loads(
    os.getenv("EDOC_SOCIALACCOUNT_PROVIDERS", "{}"),
)

ACCOUNT_EMAIL_SUBJECT_PREFIX = "[Edoc] "

DISABLE_REGULAR_LOGIN = __get_boolean("EDOC_DISABLE_REGULAR_LOGIN")

AUTO_LOGIN_USERNAME = os.getenv("EDOC_AUTO_LOGIN_USERNAME")

ACCOUNT_EMAIL_VERIFICATION = os.getenv(
    "EDOC_ACCOUNT_EMAIL_VERIFICATION",
    "optional",
)

ACCOUNT_SESSION_REMEMBER = __get_boolean("EDOC_ACCOUNT_SESSION_REMEMBER")

if AUTO_LOGIN_USERNAME:
    _index = MIDDLEWARE.index(
        "django.contrib.auth.middleware.AuthenticationMiddleware")
    # This overrides everything the auth middleware is doing but still allows
    # regular login in case the provided user does not exist.
    MIDDLEWARE.insert(_index + 1, "edoc.auth.AutoLoginMiddleware")


def _parse_remote_user_settings() -> str:
    global MIDDLEWARE, AUTHENTICATION_BACKENDS, REST_FRAMEWORK
    enable = __get_boolean("EDOC_ENABLE_HTTP_REMOTE_USER")
    enable_api = __get_boolean("EDOC_ENABLE_HTTP_REMOTE_USER_API")
    if enable or enable_api:
        MIDDLEWARE.append("edoc.auth.HttpRemoteUserMiddleware")
        AUTHENTICATION_BACKENDS.insert(
            0,
            "django.contrib.auth.backends.RemoteUserBackend",
        )

    if enable_api:
        REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"].insert(
            0,
            "edoc.auth.EdocRemoteUserAuthentication",
        )

    header_name = os.getenv(
        "EDOC_HTTP_REMOTE_USER_HEADER_NAME",
        "HTTP_REMOTE_USER",
    )

    return header_name


HTTP_REMOTE_USER_HEADER_NAME = _parse_remote_user_settings()

# X-Frame options for embedded PDF display:
X_FRAME_OPTIONS = "ANY" if DEBUG else "SAMEORIGIN"

# The next 3 settings can also be set using just EDOC_URL
CSRF_TRUSTED_ORIGINS = __get_list("EDOC_CSRF_TRUSTED_ORIGINS")

# We allow CORS from localhost:8000
CORS_ALLOWED_ORIGINS = __get_list(
    "EDOC_CORS_ALLOWED_HOSTS",
    ["http://localhost:8000"],
)

if DEBUG:
    # Allow access from the angular development server during debugging
    CORS_ALLOWED_ORIGINS.append("http://localhost:4200")

ALLOWED_HOSTS = __get_list("EDOC_ALLOWED_HOSTS", ["*"])
if ["*"] != ALLOWED_HOSTS:
    # always allow localhost. Necessary e.g. for healthcheck in docker.
    ALLOWED_HOSTS.append("localhost")


def _parse_edoc_url():
    global CSRF_TRUSTED_ORIGINS, CORS_ALLOWED_ORIGINS, ALLOWED_HOSTS
    url = os.getenv("EDOC_URL")
    if url:
        CSRF_TRUSTED_ORIGINS.append(url)
        CORS_ALLOWED_ORIGINS.append(url)
        ALLOWED_HOSTS.append(urlparse(url).hostname)

    return url


EDOC_URL = _parse_edoc_url()

# For use with trusted proxies
TRUSTED_PROXIES = __get_list("EDOC_TRUSTED_PROXIES")

USE_X_FORWARDED_HOST = __get_boolean("EDOC_USE_X_FORWARD_HOST", "false")
USE_X_FORWARDED_PORT = __get_boolean("EDOC_USE_X_FORWARD_PORT", "false")
SECURE_PROXY_SSL_HEADER = (
    tuple(json.loads(os.environ["EDOC_PROXY_SSL_HEADER"]))
    if "EDOC_PROXY_SSL_HEADER" in os.environ
    else None
)

# The secret key has a default that should be fine so long as you're hosting
# Edoc on a closed network.  However, if you're putting this anywhere
# public, you should change the key to something unique and verbose.
SECRET_KEY = os.getenv(
    "EDOC_SECRET_KEY",
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

COOKIE_PREFIX = os.getenv("EDOC_COOKIE_PREFIX", "")

CSRF_COOKIE_NAME = f"{COOKIE_PREFIX}csrftoken"
SESSION_COOKIE_NAME = f"{COOKIE_PREFIX}sessionid"
LANGUAGE_COOKIE_NAME = f"{COOKIE_PREFIX}django_language"

EMAIL_CERTIFICATE_FILE = __get_optional_path("EDOC_EMAIL_CERTIFICATE_LOCATION")


###############################################################################
# Database                                                                    #
###############################################################################
def _parse_db_settings() -> dict:
    databases = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": os.path.join(DATA_DIR, "db.sqlite3"),
            "OPTIONS": {},
        },
    }
    if os.getenv("EDOC_DBHOST"):
        # Have sqlite available as a second option for management commands
        # This is important when migrating to/from sqlite
        databases["sqlite"] = databases["default"].copy()

        databases["default"] = {
            "HOST": os.getenv("EDOC_DBHOST"),
            "NAME": os.getenv("EDOC_DBNAME", "edoc"),
            "USER": os.getenv("EDOC_DBUSER", "edoc"),
            "PASSWORD": os.getenv("EDOC_DBPASS", "edoc"),
            "OPTIONS": {},
        }
        if os.getenv("EDOC_DBPORT"):
            databases["default"]["PORT"] = os.getenv("EDOC_DBPORT")

        # Leave room for future extensibility
        if os.getenv("EDOC_DBENGINE") == "mariadb":
            engine = "django.db.backends.mysql"
            options = {
                "read_default_file": "/etc/mysql/my.cnf",
                "charset": "utf8mb4",
                "ssl_mode": os.getenv("EDOC_DBSSLMODE", "PREFERRED"),
                "ssl": {
                    "ca": os.getenv("EDOC_DBSSLROOTCERT", None),
                    "cert": os.getenv("EDOC_DBSSLCERT", None),
                    "key": os.getenv("EDOC_DBSSLKEY", None),
                },
            }

        else:  # Default to PostgresDB
            engine = "django.db.backends.postgresql_psycopg2"
            options = {
                "sslmode": os.getenv("EDOC_DBSSLMODE", "prefer"),
                "sslrootcert": os.getenv("EDOC_DBSSLROOTCERT", None),
                "sslcert": os.getenv("EDOC_DBSSLCERT", None),
                "sslkey": os.getenv("EDOC_DBSSLKEY", None),
            }

        databases["default"]["ENGINE"] = engine
        databases["default"]["OPTIONS"].update(options)

    if os.getenv("EDOC_DB_TIMEOUT") is not None:
        if databases["default"]["ENGINE"] == "django.db.backends.sqlite3":
            databases["default"]["OPTIONS"].update(
                {"timeout": int(os.getenv("EDOC_DB_TIMEOUT"))},
            )
        else:
            databases["default"]["OPTIONS"].update(
                {"connect_timeout": int(os.getenv("EDOC_DB_TIMEOUT"))},
            )
            databases["sqlite"]["OPTIONS"].update(
                {"timeout": int(os.getenv("EDOC_DB_TIMEOUT"))},
            )
    return databases


DATABASES = _parse_db_settings()

if os.getenv("EDOC_DBENGINE") == "mariadb":
    # Silence Django error on old MariaDB versions.
    # VARCHAR can support > 255 in modern versions
    # https://docs.djangoproject.com/en/4.1/ref/checks/#database
    # https://mariadb.com/kb/en/innodb-system-variables/#innodb_large_prefix
    SILENCED_SYSTEM_CHECKS = ["mysql.W003"]

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

###############################################################################
# Internationalization                                                        #
###############################################################################

LANGUAGE_CODE = "vi-vn"

LANGUAGES = [
    ("en-us", _("English (US)")),
    # needs to be first to act as fallback language
    ("en-gb", _("English (GB)")),
    ("vi-vn", _("Vietnamese")),
]

LOCALE_PATHS = [os.path.join(BASE_DIR, "locale")]

TIME_ZONE = os.getenv("EDOC_TIME_ZONE", "UTC")

USE_I18N = True

USE_L10N = True

USE_TZ = True

###############################################################################
# Logging                                                                     #
###############################################################################

setup_logging_queues()

LOGGING_DIR.mkdir(parents=True, exist_ok=True)

LOGROTATE_MAX_SIZE = os.getenv("EDOC_LOGROTATE_MAX_SIZE", 1024 * 1024)
LOGROTATE_MAX_BACKUPS = os.getenv("EDOC_LOGROTATE_MAX_BACKUPS", 20)

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
        "file_edoc": {
            "class": "concurrent_log_handler.ConcurrentRotatingFileHandler",
            "formatter": "verbose",
            "filename": os.path.join(LOGGING_DIR, "edoc.log"),
            "maxBytes": LOGROTATE_MAX_SIZE,
            "backupCount": LOGROTATE_MAX_BACKUPS,
        },
        "file_mail": {
            "class": "concurrent_log_handler.ConcurrentRotatingFileHandler",
            "formatter": "verbose",
            "filename": os.path.join(LOGGING_DIR, "mail.log"),
            "maxBytes": LOGROTATE_MAX_SIZE,
            "backupCount": LOGROTATE_MAX_BACKUPS,
        },
        "file_celery": {
            "class": "concurrent_log_handler.ConcurrentRotatingFileHandler",
            "formatter": "verbose",
            "filename": os.path.join(LOGGING_DIR, "celery.log"),
            "maxBytes": LOGROTATE_MAX_SIZE,
            "backupCount": LOGROTATE_MAX_BACKUPS,
        },
    },
    "root": {"handlers": ["console"]},
    "loggers": {
        "edoc": {"handlers": ["file_edoc"], "level": "DEBUG"},
        "edoc_mail": {"handlers": ["file_mail"], "level": "DEBUG"},
        "ocrmypdf": {"handlers": ["file_edoc"], "level": "INFO"},
        "celery": {"handlers": ["file_celery"], "level": "DEBUG"},
        "kombu": {"handlers": ["file_celery"], "level": "DEBUG"},
    },
}

###############################################################################
# Task queue                                                                  #
###############################################################################

# https://docs.celeryq.dev/en/stable/userguide/configuration.html

CELERY_BROKER_URL = _CELERY_REDIS_URL
CELERY_TIMEZONE = TIME_ZONE

CELERY_WORKER_HIJACK_ROOT_LOGGER = False
CELERY_WORKER_CONCURRENCY: Final[int] = __get_int("EDOC_TASK_WORKERS", 1)
TASK_WORKERS = CELERY_WORKER_CONCURRENCY
CELERY_WORKER_MAX_TASKS_PER_CHILD = 1
CELERY_WORKER_SEND_TASK_EVENTS = True
CELERY_TASK_SEND_SENT_EVENT = True
CELERY_SEND_TASK_SENT_EVENT = True
CELERY_BROKER_CONNECTION_RETRY = True
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_BROKER_TRANSPORT_OPTIONS = {
    "global_keyprefix": os.getenv("EDOC_REDIS_PREFIX", ""),
}

CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT: Final[int] = __get_int("EDOC_WORKER_TIMEOUT", 1800)

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
CELERY_BEAT_SCHEDULE_FILENAME = os.path.join(DATA_DIR,
                                             "celerybeat-schedule.db")

# django setting.
CACHES = {
    "default": {
        "BACKEND": os.environ.get(
            "EDOC_CACHE_BACKEND",
            "django.core.cache.backends.redis.RedisCache",
        ),
        "LOCATION": _CHANNELS_REDIS_URL,
        "KEY_PREFIX": os.getenv("EDOC_REDIS_PREFIX", ""),
    },
}


if DEBUG and os.getenv("EDOC_CACHE_BACKEND") is None:
    CACHES["default"][
        "BACKEND"
    ] = "django.core.cache.backends.locmem.LocMemCache"  # pragma: no cover

# Use cached session engine
SESSION_ENGINE = "django.contrib.sessions.backends.cache"

def default_threads_per_worker(task_workers) -> int:
    # always leave one core open
    available_cores = max(multiprocessing.cpu_count(), 1)
    try:
        return max(math.floor(available_cores / task_workers), 1)
    except NotImplementedError:
        return 1


THREADS_PER_WORKER = os.getenv(
    "EDOC_THREADS_PER_WORKER",
    default_threads_per_worker(CELERY_WORKER_CONCURRENCY),
)

APSCHEDULER_DATETIME_FORMAT = "N j, Y, f:s a"  # Default

SCHEDULER_DEFAULT = True

###############################################################################
# Edoc Specific Settings                                                 #
###############################################################################

CONSUMER_POLLING = int(os.getenv("EDOC_CONSUMER_POLLING", 1))

CONSUMER_POLLING_DELAY = int(os.getenv("EDOC_CONSUMER_POLLING_DELAY", 5))

CONSUMER_POLLING_RETRY_COUNT = int(
    os.getenv("EDOC_CONSUMER_POLLING_RETRY_COUNT", 5),
)

CONSUMER_INOTIFY_DELAY: Final[float] = __get_float(
    "EDOC_CONSUMER_INOTIFY_DELAY",
    0.5,
)

CONSUMER_DELETE_DUPLICATES = __get_boolean("EDOC_CONSUMER_DELETE_DUPLICATES")

CONSUMER_RECURSIVE = __get_boolean("EDOC_CONSUMER_RECURSIVE")

# Ignore glob patterns, relative to EDOC_CONSUMPTION_DIR
CONSUMER_IGNORE_PATTERNS = list(
    json.loads(
        os.getenv(
            "EDOC_CONSUMER_IGNORE_PATTERNS",
            '[".DS_Store", ".DS_STORE", "._*", ".stfolder/*", ".stversions/*", ".localized/*", "desktop.ini", "@eaDir/*", "Thumbs.db"]',
        ),
    ),
)

CONSUMER_SUBDIRS_AS_TAGS = __get_boolean("EDOC_CONSUMER_SUBDIRS_AS_TAGS")

CONSUMER_ENABLE_BARCODES: Final[bool] = __get_boolean(
    "EDOC_CONSUMER_ENABLE_BARCODES",
)

CONSUMER_BARCODE_TIFF_SUPPORT: Final[bool] = __get_boolean(
    "EDOC_CONSUMER_BARCODE_TIFF_SUPPORT",
)

CONSUMER_BARCODE_STRING: Final[str] = os.getenv(
    "EDOC_CONSUMER_BARCODE_STRING",
    "PATCHT",
)

CONSUMER_BARCODE_SCANNER: Final[str] = os.getenv(
    "EDOC_CONSUMER_BARCODE_SCANNER",
    "PYZBAR",
).upper()

CONSUMER_ENABLE_ASN_BARCODE: Final[bool] = __get_boolean(
    "EDOC_CONSUMER_ENABLE_ASN_BARCODE",
)

CONSUMER_ASN_BARCODE_PREFIX: Final[str] = os.getenv(
    "EDOC_CONSUMER_ASN_BARCODE_PREFIX",
    "ASN",
)

CONSUMER_BARCODE_UPSCALE: Final[float] = __get_float(
    "EDOC_CONSUMER_BARCODE_UPSCALE",
    0.0,
)

CONSUMER_BARCODE_DPI: Final[int] = __get_int("EDOC_CONSUMER_BARCODE_DPI", 300)

CONSUMER_ENABLE_TAG_BARCODE: Final[bool] = __get_boolean(
    "EDOC_CONSUMER_ENABLE_TAG_BARCODE",
)

CONSUMER_TAG_BARCODE_MAPPING = dict(
    json.loads(
        os.getenv(
            "EDOC_CONSUMER_TAG_BARCODE_MAPPING",
            '{"TAG:(.*)": "\\\\g<1>"}',
        ),
    ),
)

CONSUMER_ENABLE_COLLATE_DOUBLE_SIDED: Final[bool] = __get_boolean(
    "EDOC_CONSUMER_ENABLE_COLLATE_DOUBLE_SIDED",
)

CONSUMER_COLLATE_DOUBLE_SIDED_SUBDIR_NAME: Final[str] = os.getenv(
    "EDOC_CONSUMER_COLLATE_DOUBLE_SIDED_SUBDIR_NAME",
    "double-sided",
)

CONSUMER_COLLATE_DOUBLE_SIDED_TIFF_SUPPORT: Final[bool] = __get_boolean(
    "EDOC_CONSUMER_COLLATE_DOUBLE_SIDED_TIFF_SUPPORT",
)

OCR_PAGES = __get_optional_int("EDOC_OCR_PAGES")

# The default language that tesseract will attempt to use when parsing
# documents.  It should be a 3-letter language code consistent with ISO 639.
OCR_LANGUAGE = os.getenv("EDOC_OCR_LANGUAGE", "vie")

# OCRmyPDF --output-type options are available.
OCR_OUTPUT_TYPE = os.getenv("EDOC_OCR_OUTPUT_TYPE", "pdfa")

# skip. redo, force
OCR_MODE = os.getenv("EDOC_OCR_MODE", "skip")

OCR_SKIP_ARCHIVE_FILE = os.getenv("EDOC_OCR_SKIP_ARCHIVE_FILE", "never")

OCR_IMAGE_DPI = __get_optional_int("EDOC_OCR_IMAGE_DPI")

OCR_CLEAN = os.getenv("EDOC_OCR_CLEAN", "clean")

OCR_DESKEW: Final[bool] = __get_boolean("EDOC_OCR_DESKEW", "true")

OCR_ROTATE_PAGES: Final[bool] = __get_boolean("EDOC_OCR_ROTATE_PAGES", "true")

OCR_ROTATE_PAGES_THRESHOLD: Final[float] = __get_float(
    "EDOC_OCR_ROTATE_PAGES_THRESHOLD",
    12.0,
)

OCR_MAX_IMAGE_PIXELS: Final[Optional[int]] = __get_optional_int(
    "EDOC_OCR_MAX_IMAGE_PIXELS",
)

OCR_COLOR_CONVERSION_STRATEGY = os.getenv(
    "EDOC_OCR_COLOR_CONVERSION_STRATEGY",
    "RGB",
)

OCR_USER_ARGS = os.getenv("EDOC_OCR_USER_ARGS")

MAX_IMAGE_PIXELS: Final[Optional[int]] = __get_optional_int(
    "EDOC_MAX_IMAGE_PIXELS",
)

# GNUPG needs a home directory for some reason
GNUPG_HOME = os.getenv("HOME", "/tmp")

# Convert is part of the ImageMagick package
CONVERT_BINARY = os.getenv("EDOC_CONVERT_BINARY", "convert")
CONVERT_TMPDIR = os.getenv("EDOC_CONVERT_TMPDIR")
CONVERT_MEMORY_LIMIT = os.getenv("EDOC_CONVERT_MEMORY_LIMIT")

GS_BINARY = os.getenv("EDOC_GS_BINARY", "gs")

# Pre-2.x versions of Edoc stored your documents locally with GPG
# encryption, but that is no longer the default.  This behaviour is still
# available, but it must be explicitly enabled by setting
# `EDOC_PASSPHRASE` in your environment or config file.  The default is to
# store these files unencrypted.
#
# Translation:
# * If you're a new user, you can safely ignore this setting.
# * If you're upgrading from 1.x, this must be set, OR you can run
#   `./manage.py change_storage_type gpg unencrypted` to decrypt your files,
#   after which you can unset this value.
PASSPHRASE = os.getenv("EDOC_PASSPHRASE")

# Trigger a script after every successful document consumption?
PRE_CONSUME_SCRIPT = os.getenv("EDOC_PRE_CONSUME_SCRIPT")
POST_CONSUME_SCRIPT = os.getenv("EDOC_POST_CONSUME_SCRIPT")

# Specify the default date order (for autodetected dates)
DATE_ORDER = os.getenv("EDOC_DATE_ORDER", "DMY")
FILENAME_DATE_ORDER = os.getenv("EDOC_FILENAME_DATE_ORDER")

# Maximum number of dates taken from document start to end to show as suggestions for
# `created` date in the frontend. Duplicates are removed, which can result in
# fewer dates shown.
NUMBER_OF_SUGGESTED_DATES = __get_int("EDOC_NUMBER_OF_SUGGESTED_DATES", 3)

# Transformations applied before filename parsing
FILENAME_PARSE_TRANSFORMS = []
for t in json.loads(os.getenv("EDOC_FILENAME_PARSE_TRANSFORMS", "[]")):
    FILENAME_PARSE_TRANSFORMS.append((re.compile(t["pattern"]), t["repl"]))

# Specify the filename format for out files
FILENAME_FORMAT = os.getenv("EDOC_FILENAME_FORMAT")

# If this is enabled, variables in filename format will resolve to
# empty-string instead of 'none'.
# Directories with 'empty names' are omitted, too.
FILENAME_FORMAT_REMOVE_NONE = __get_boolean(
    "EDOC_FILENAME_FORMAT_REMOVE_NONE",
    "NO",
)

THUMBNAIL_FONT_NAME = os.getenv(
    "EDOC_THUMBNAIL_FONT_NAME",
    "/usr/share/fonts/liberation/LiberationSerif-Regular.ttf",
)

# Tika settings
TIKA_ENABLED = __get_boolean("EDOC_TIKA_ENABLED", "NO")
TIKA_ENDPOINT = os.getenv("EDOC_TIKA_ENDPOINT", "http://localhost:9998")
TIKA_GOTENBERG_ENDPOINT = os.getenv(
    "EDOC_TIKA_GOTENBERG_ENDPOINT",
    "http://localhost:3000",
)

if TIKA_ENABLED:
    INSTALLED_APPS.append("edoc_tika.apps.EdocTikaConfig")

AUDIT_LOG_ENABLED = __get_boolean("EDOC_AUDIT_LOG_ENABLED", "true")
if AUDIT_LOG_ENABLED:
    INSTALLED_APPS.append("auditlog")
    MIDDLEWARE.append("auditlog.middleware.AuditlogMiddleware")


def _parse_ignore_dates(
    env_ignore: str,
    date_order: str = DATE_ORDER,
) -> set[datetime.datetime]:
    """
    If the EDOC_IGNORE_DATES environment variable is set, parse the
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

if os.getenv("EDOC_IGNORE_DATES") is not None:
    IGNORE_DATES = _parse_ignore_dates(os.getenv("EDOC_IGNORE_DATES"))

ENABLE_UPDATE_CHECK = os.getenv("EDOC_ENABLE_UPDATE_CHECK", "default")
if ENABLE_UPDATE_CHECK != "default":
    ENABLE_UPDATE_CHECK = __get_boolean("EDOC_ENABLE_UPDATE_CHECK")

APP_TITLE = os.getenv("EDOC_APP_TITLE", None)
APP_LOGO = os.getenv("EDOC_APP_LOGO", None)


###############################################################################
# Machine Learning                                                            #
###############################################################################


def _get_nltk_language_setting(ocr_lang: str) -> Optional[str]:
    """
    Maps an ISO-639-1 language code supported by Tesseract into
    an optional NLTK language name.  This is the set of common supported
    languages for all the NLTK data used.

    Assumption: The primary language is first

    NLTK Languages:
      - https://www.nltk.org/api/nltk.stem.snowball.html#nltk.stem.snowball.SnowballStemmer

    """
    ocr_lang = ocr_lang.split("+")[0]
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
        "tur": "turkish",
    }

    return iso_code_to_nltk.get(ocr_lang)


NLTK_ENABLED: Final[bool] = __get_boolean("EDOC_ENABLE_NLTK", "yes")

NLTK_LANGUAGE: Optional[str] = _get_nltk_language_setting(OCR_LANGUAGE)

###############################################################################
# Email (SMTP) Backend                                                        #
###############################################################################

EMAIL_HOST: Final[str] = os.getenv("EDOC_EMAIL_HOST", "localhost")
EMAIL_PORT: Final[int] = int(os.getenv("EDOC_EMAIL_PORT", 25))
EMAIL_HOST_USER: Final[str] = os.getenv("EDOC_EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD: Final[str] = os.getenv("EDOC_EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL: Final[str] = os.getenv("EDOC_EMAIL_FROM", EMAIL_HOST_USER)
EMAIL_USE_TLS: Final[bool] = __get_boolean("EDOC_EMAIL_USE_TLS")
EMAIL_USE_SSL: Final[bool] = __get_boolean("EDOC_EMAIL_USE_SSL")
EMAIL_SUBJECT_PREFIX: Final[str] = "[Edoc] "
if DEBUG:  # pragma: no cover
    EMAIL_BACKEND = "django.core.mail.backends.filebased.EmailBackend"
    EMAIL_FILE_PATH = BASE_DIR / "sent_emails"

###############################################################################
# Soft Delete                                                                 #
###############################################################################
EMPTY_TRASH_DELAY = max(__get_int("EDOC_EMPTY_TRASH_DELAY", 30), 1)

###############################################################################
# Ocr config                                                                 #
###############################################################################
API_LOGIN_OCR = os.getenv("API_LOGIN_OCR", "")
API_REFRESH_OCR = os.getenv("API_REFRESH_OCR", "")
API_OCR_BY_FILE_ID = os.getenv("API_OCR_BY_FILE_ID", "")
API_UPLOAD_FILE_OCR = os.getenv("API_UPLOAD_FILE_OCR", "")
FOLDER_UPLOAD = os.getenv("FOLDER_UPLOAD", "")
DELAY_OCR = os.getenv("DELAY_OCR", 1)

###############################################################################
# Elastic search                                                              #
###############################################################################
ELASTIC_SEARCH_DOCUMENT_INDEX = os.getenv("ELASTIC_SEARCH_DOCUMENT_INDEX",
                                          "edoc")
ELASTIC_SEARCH_HOST = os.getenv("ELASTIC_SEARCH_HOST", "")
ELASTICSEARCH_DSL = {
    'default': {
        'hosts': ELASTIC_SEARCH_HOST,
        # Địa chỉ của Elasticsearch
        'http_auth': (os.getenv("ELASTIC_SEARCH_USERNAME", ""),
                      os.getenv("ELASTIC_SEARCH_PASSWORD", "")),
        # Thông tin xác thực (nếu có)
        'use_ssl': False,  # Nếu sử dụng SSL
        'verify_certs': False,  # Kiểm tra chứng chỉ
        'ca_certs': os.getenv("ELASTIC_SEARCH_CA", ""),
        # Đường dẫn đến chứng chỉ CA
    },
}

INTERNAL_IPS = [
    # ...
    "127.0.0.1",
    # ...
]
