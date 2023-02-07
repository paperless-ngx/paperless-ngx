import datetime
import json
import math
import multiprocessing
import os
import re
import tempfile
from typing import Dict
from typing import Final
from typing import Optional
from typing import Set
from typing import Tuple
from urllib.parse import urlparse

from celery.schedules import crontab
from concurrent_log_handler.queue import setup_logging_queues
from django.utils.translation import gettext_lazy as _
from dotenv import load_dotenv

# Tap paperless.conf if it's available
configuration_path = os.getenv("PAPERLESS_CONFIGURATION_PATH")
if configuration_path and os.path.exists(configuration_path):
    load_dotenv(configuration_path)
elif os.path.exists("../paperless.conf"):
    load_dotenv("../paperless.conf")
elif os.path.exists("/etc/paperless.conf"):
    load_dotenv("/etc/paperless.conf")
elif os.path.exists("/usr/local/etc/paperless.conf"):
    load_dotenv("/usr/local/etc/paperless.conf")

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


def __get_boolean(key: str, default: str = "NO") -> bool:
    """
    Return a boolean value based on whatever the user has supplied in the
    environment based on whether the value "looks like" it's True or not.
    """
    return bool(os.getenv(key, default).lower() in ("yes", "y", "1", "t", "true"))


def __get_int(key: str, default: int) -> int:
    """
    Return an integer value based on the environment variable or a default
    """
    return int(os.getenv(key, default))


def __get_float(key: str, default: float) -> float:
    """
    Return an integer value based on the environment variable or a default
    """
    return float(os.getenv(key, default))


def __get_path(key: str, default: str) -> str:
    """
    Return a normalized, absolute path based on the environment variable or a default
    """
    return os.path.abspath(os.path.normpath(os.environ.get(key, default)))


def _parse_redis_url(env_redis: Optional[str]) -> Tuple[str]:
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


def _parse_beat_schedule() -> Dict:
    schedule = {}
    tasks = [
        {
            "name": "Check all e-mail accounts",
            "env_key": "PAPERLESS_EMAIL_TASK_CRON",
            # Default every ten minutes
            "env_default": "*/10 * * * *",
            "task": "paperless_mail.tasks.process_mail_accounts",
        },
        {
            "name": "Train the classifier",
            "env_key": "PAPERLESS_TRAIN_TASK_CRON",
            # Default hourly at 5 minutes past the hour
            "env_default": "5 */1 * * *",
            "task": "documents.tasks.train_classifier",
        },
        {
            "name": "Optimize the index",
            "env_key": "PAPERLESS_INDEX_TASK_CRON",
            # Default daily at midnight
            "env_default": "0 0 * * *",
            "task": "documents.tasks.index_optimize",
        },
        {
            "name": "Perform sanity check",
            "env_key": "PAPERLESS_SANITY_TASK_CRON",
            # Default Sunday at 00:30
            "env_default": "30 0 * * sun",
            "task": "documents.tasks.sanity_check",
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
        }

    return schedule


# NEVER RUN WITH DEBUG IN PRODUCTION.
DEBUG = __get_boolean("PAPERLESS_DEBUG", "NO")


###############################################################################
# Directories                                                                 #
###############################################################################

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

STATIC_ROOT = __get_path("PAPERLESS_STATICDIR", os.path.join(BASE_DIR, "..", "static"))

MEDIA_ROOT = __get_path("PAPERLESS_MEDIA_ROOT", os.path.join(BASE_DIR, "..", "media"))
ORIGINALS_DIR = os.path.join(MEDIA_ROOT, "documents", "originals")
ARCHIVE_DIR = os.path.join(MEDIA_ROOT, "documents", "archive")
THUMBNAIL_DIR = os.path.join(MEDIA_ROOT, "documents", "thumbnails")

DATA_DIR = __get_path("PAPERLESS_DATA_DIR", os.path.join(BASE_DIR, "..", "data"))

NLTK_DIR = __get_path("PAPERLESS_NLTK_DIR", "/usr/share/nltk_data")

TRASH_DIR = os.getenv("PAPERLESS_TRASH_DIR")

# Lock file for synchronizing changes to the MEDIA directory across multiple
# threads.
MEDIA_LOCK = os.path.join(MEDIA_ROOT, "media.lock")
INDEX_DIR = os.path.join(DATA_DIR, "index")
MODEL_FILE = os.path.join(DATA_DIR, "classification_model.pickle")

LOGGING_DIR = __get_path("PAPERLESS_LOGGING_DIR", os.path.join(DATA_DIR, "log"))

CONSUMPTION_DIR = __get_path(
    "PAPERLESS_CONSUMPTION_DIR",
    os.path.join(BASE_DIR, "..", "consume"),
)

# This will be created if it doesn't exist
SCRATCH_DIR = __get_path(
    "PAPERLESS_SCRATCH_DIR",
    os.path.join(tempfile.gettempdir(), "paperless"),
)

###############################################################################
# Application Definition                                                      #
###############################################################################

env_apps = os.getenv("PAPERLESS_APPS").split(",") if os.getenv("PAPERLESS_APPS") else []

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
    "django.contrib.admin",
    "rest_framework",
    "rest_framework.authtoken",
    "django_filters",
    "django_celery_results",
] + env_apps

if DEBUG:
    INSTALLED_APPS.append("channels")

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.BasicAuthentication",
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.TokenAuthentication",
    ],
    "DEFAULT_VERSIONING_CLASS": "rest_framework.versioning.AcceptHeaderVersioning",
    "DEFAULT_VERSION": "1",
    # Make sure these are ordered and that the most recent version appears
    # last
    "ALLOWED_VERSIONS": ["1", "2"],
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
]

# Optional to enable compression
if __get_boolean("PAPERLESS_ENABLE_COMPRESSION", "yes"):  # pragma: nocover
    MIDDLEWARE.insert(0, "compression_middleware.middleware.CompressionMiddleware")

ROOT_URLCONF = "paperless.urls"

FORCE_SCRIPT_NAME = os.getenv("PAPERLESS_FORCE_SCRIPT_NAME")
BASE_URL = (FORCE_SCRIPT_NAME or "") + "/"
LOGIN_URL = BASE_URL + "accounts/login/"
LOGOUT_REDIRECT_URL = os.getenv("PAPERLESS_LOGOUT_REDIRECT_URL")

WSGI_APPLICATION = "paperless.wsgi.application"
ASGI_APPLICATION = "paperless.asgi.application"

STATIC_URL = os.getenv("PAPERLESS_STATIC_URL", BASE_URL + "static/")
WHITENOISE_STATIC_PREFIX = "/static/"

_CELERY_REDIS_URL, _CHANNELS_REDIS_URL = _parse_redis_url(
    os.getenv("PAPERLESS_REDIS", None),
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
            ],
        },
    },
]

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [_CHANNELS_REDIS_URL],
            "capacity": 2000,  # default 100
            "expiry": 15,  # default 60
        },
    },
}

###############################################################################
# Security                                                                    #
###############################################################################

AUTO_LOGIN_USERNAME = os.getenv("PAPERLESS_AUTO_LOGIN_USERNAME")

if AUTO_LOGIN_USERNAME:
    _index = MIDDLEWARE.index("django.contrib.auth.middleware.AuthenticationMiddleware")
    # This overrides everything the auth middleware is doing but still allows
    # regular login in case the provided user does not exist.
    MIDDLEWARE.insert(_index + 1, "paperless.auth.AutoLoginMiddleware")

ENABLE_HTTP_REMOTE_USER = __get_boolean("PAPERLESS_ENABLE_HTTP_REMOTE_USER")
HTTP_REMOTE_USER_HEADER_NAME = os.getenv(
    "PAPERLESS_HTTP_REMOTE_USER_HEADER_NAME",
    "HTTP_REMOTE_USER",
)

if ENABLE_HTTP_REMOTE_USER:
    MIDDLEWARE.append("paperless.auth.HttpRemoteUserMiddleware")
    AUTHENTICATION_BACKENDS = [
        "django.contrib.auth.backends.RemoteUserBackend",
        "django.contrib.auth.backends.ModelBackend",
    ]
    REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"].append(
        "rest_framework.authentication.RemoteUserAuthentication",
    )

# X-Frame options for embedded PDF display:
if DEBUG:
    X_FRAME_OPTIONS = "ANY"
else:
    X_FRAME_OPTIONS = "SAMEORIGIN"


# The next 3 settings can also be set using just PAPERLESS_URL
_csrf_origins = os.getenv("PAPERLESS_CSRF_TRUSTED_ORIGINS")
if _csrf_origins:
    CSRF_TRUSTED_ORIGINS = _csrf_origins.split(",")
else:
    CSRF_TRUSTED_ORIGINS = []

# We allow CORS from localhost:8000
CORS_ALLOWED_ORIGINS = tuple(
    os.getenv("PAPERLESS_CORS_ALLOWED_HOSTS", "http://localhost:8000").split(","),
)

if DEBUG:
    # Allow access from the angular development server during debugging
    CORS_ALLOWED_ORIGINS += ("http://localhost:4200",)

_allowed_hosts = os.getenv("PAPERLESS_ALLOWED_HOSTS")
if _allowed_hosts:
    ALLOWED_HOSTS = _allowed_hosts.split(",")
else:
    ALLOWED_HOSTS = ["*"]

_paperless_url = os.getenv("PAPERLESS_URL")
if _paperless_url:
    _paperless_uri = urlparse(_paperless_url)
    CSRF_TRUSTED_ORIGINS.append(_paperless_url)
    CORS_ALLOWED_ORIGINS += (_paperless_url,)
    if _allowed_hosts:
        ALLOWED_HOSTS.append(_paperless_uri.hostname)
    else:
        # always allow localhost. Necessary e.g. for healthcheck in docker.
        ALLOWED_HOSTS = [_paperless_uri.hostname] + ["localhost"]

# The secret key has a default that should be fine so long as you're hosting
# Paperless on a closed network.  However, if you're putting this anywhere
# public, you should change the key to something unique and verbose.
SECRET_KEY = os.getenv(
    "PAPERLESS_SECRET_KEY",
    "e11fl1oa-*ytql8p)(06fbj4ukrlo+n7k&q5+$1md7i+mge=ee",
)

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",  # noqa: E501
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
# a self-hosted sort of gig, the benefits of being able to mass-delete a tonne
# of log entries outweight the benefits of such a safeguard.

DATA_UPLOAD_MAX_NUMBER_FIELDS = None

COOKIE_PREFIX = os.getenv("PAPERLESS_COOKIE_PREFIX", "")

CSRF_COOKIE_NAME = f"{COOKIE_PREFIX}csrftoken"
SESSION_COOKIE_NAME = f"{COOKIE_PREFIX}sessionid"
LANGUAGE_COOKIE_NAME = f"{COOKIE_PREFIX}django_language"

###############################################################################
# Database                                                                    #
###############################################################################

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.path.join(DATA_DIR, "db.sqlite3"),
        "OPTIONS": {},
    },
}

if os.getenv("PAPERLESS_DBHOST"):
    # Have sqlite available as a second option for management commands
    # This is important when migrating to/from sqlite
    DATABASES["sqlite"] = DATABASES["default"].copy()

    DATABASES["default"] = {
        "HOST": os.getenv("PAPERLESS_DBHOST"),
        "NAME": os.getenv("PAPERLESS_DBNAME", "paperless"),
        "USER": os.getenv("PAPERLESS_DBUSER", "paperless"),
        "PASSWORD": os.getenv("PAPERLESS_DBPASS", "paperless"),
        "OPTIONS": {},
    }
    if os.getenv("PAPERLESS_DBPORT"):
        DATABASES["default"]["PORT"] = os.getenv("PAPERLESS_DBPORT")

    # Leave room for future extensibility
    if os.getenv("PAPERLESS_DBENGINE") == "mariadb":
        engine = "django.db.backends.mysql"
        options = {"read_default_file": "/etc/mysql/my.cnf", "charset": "utf8mb4"}

        # Silence Django error on old MariaDB versions.
        # VARCHAR can support > 255 in modern versions
        # https://docs.djangoproject.com/en/4.1/ref/checks/#database
        # https://mariadb.com/kb/en/innodb-system-variables/#innodb_large_prefix
        SILENCED_SYSTEM_CHECKS = ["mysql.W003"]

    else:  # Default to PostgresDB
        engine = "django.db.backends.postgresql_psycopg2"
        options = {"sslmode": os.getenv("PAPERLESS_DBSSLMODE", "prefer")}

    DATABASES["default"]["ENGINE"] = engine
    DATABASES["default"]["OPTIONS"].update(options)

if os.getenv("PAPERLESS_DB_TIMEOUT") is not None:
    DATABASES["default"]["OPTIONS"].update(
        {"timeout": float(os.getenv("PAPERLESS_DB_TIMEOUT"))},
    )

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

###############################################################################
# Internationalization                                                        #
###############################################################################

LANGUAGE_CODE = "en-us"

LANGUAGES = [
    ("en-us", _("English (US)")),  # needs to be first to act as fallback language
    ("ar-ar", _("Arabic")),
    ("be-by", _("Belarusian")),
    ("cs-cz", _("Czech")),
    ("da-dk", _("Danish")),
    ("de-de", _("German")),
    ("en-gb", _("English (GB)")),
    ("es-es", _("Spanish")),
    ("fr-fr", _("French")),
    ("it-it", _("Italian")),
    ("lb-lu", _("Luxembourgish")),
    ("nl-nl", _("Dutch")),
    ("pl-pl", _("Polish")),
    ("pt-br", _("Portuguese (Brazil)")),
    ("pt-pt", _("Portuguese")),
    ("ro-ro", _("Romanian")),
    ("ru-ru", _("Russian")),
    ("sl-si", _("Slovenian")),
    ("sr-cs", _("Serbian")),
    ("sv-se", _("Swedish")),
    ("tr-tr", _("Turkish")),
    ("zh-cn", _("Chinese Simplified")),
]

LOCALE_PATHS = [os.path.join(BASE_DIR, "locale")]

TIME_ZONE = os.getenv("PAPERLESS_TIME_ZONE", "UTC")

USE_I18N = True

USE_L10N = True

USE_TZ = True

###############################################################################
# Logging                                                                     #
###############################################################################

setup_logging_queues()

os.makedirs(LOGGING_DIR, exist_ok=True)

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
            "filename": os.path.join(LOGGING_DIR, "paperless.log"),
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
    },
    "root": {"handlers": ["console"]},
    "loggers": {
        "paperless": {"handlers": ["file_paperless"], "level": "DEBUG"},
        "paperless_mail": {"handlers": ["file_mail"], "level": "DEBUG"},
    },
}

###############################################################################
# Task queue                                                                  #
###############################################################################

TASK_WORKERS = __get_int("PAPERLESS_TASK_WORKERS", 1)

WORKER_TIMEOUT: Final[int] = __get_int("PAPERLESS_WORKER_TIMEOUT", 1800)

CELERY_BROKER_URL = _CELERY_REDIS_URL
CELERY_TIMEZONE = TIME_ZONE

CELERY_WORKER_HIJACK_ROOT_LOGGER = False
CELERY_WORKER_CONCURRENCY = TASK_WORKERS
CELERY_WORKER_MAX_TASKS_PER_CHILD = 1
CELERY_WORKER_SEND_TASK_EVENTS = True

CELERY_SEND_TASK_SENT_EVENT = True

CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = WORKER_TIMEOUT

CELERY_RESULT_EXTENDED = True
CELERY_RESULT_BACKEND = "django-db"
CELERY_CACHE_BACKEND = "default"

# https://docs.celeryq.dev/en/stable/userguide/configuration.html#beat-schedule
CELERY_BEAT_SCHEDULE = _parse_beat_schedule()

# https://docs.celeryq.dev/en/stable/userguide/configuration.html#beat-schedule-filename
CELERY_BEAT_SCHEDULE_FILENAME = os.path.join(DATA_DIR, "celerybeat-schedule.db")

# django setting.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": _CHANNELS_REDIS_URL,
    },
}


def default_threads_per_worker(task_workers) -> int:
    # always leave one core open
    available_cores = max(multiprocessing.cpu_count(), 1)
    try:
        return max(math.floor(available_cores / task_workers), 1)
    except NotImplementedError:
        return 1


THREADS_PER_WORKER = os.getenv(
    "PAPERLESS_THREADS_PER_WORKER",
    default_threads_per_worker(TASK_WORKERS),
)

###############################################################################
# Paperless Specific Settings                                                 #
###############################################################################

CONSUMER_POLLING = int(os.getenv("PAPERLESS_CONSUMER_POLLING", 0))

CONSUMER_POLLING_DELAY = int(os.getenv("PAPERLESS_CONSUMER_POLLING_DELAY", 5))

CONSUMER_POLLING_RETRY_COUNT = int(
    os.getenv("PAPERLESS_CONSUMER_POLLING_RETRY_COUNT", 5),
)

CONSUMER_INOTIFY_DELAY: Final[float] = __get_float(
    "PAPERLESS_CONSUMER_INOTIFY_DELAY",
    0.5,
)

CONSUMER_DELETE_DUPLICATES = __get_boolean("PAPERLESS_CONSUMER_DELETE_DUPLICATES")

CONSUMER_RECURSIVE = __get_boolean("PAPERLESS_CONSUMER_RECURSIVE")

# Ignore glob patterns, relative to PAPERLESS_CONSUMPTION_DIR
CONSUMER_IGNORE_PATTERNS = list(
    json.loads(
        os.getenv(
            "PAPERLESS_CONSUMER_IGNORE_PATTERNS",
            '[".DS_STORE/*", "._*", ".stfolder/*", ".stversions/*", ".localized/*", "desktop.ini"]',  # noqa: E501
        ),
    ),
)

CONSUMER_SUBDIRS_AS_TAGS = __get_boolean("PAPERLESS_CONSUMER_SUBDIRS_AS_TAGS")

CONSUMER_ENABLE_BARCODES: Final[bool] = __get_boolean(
    "PAPERLESS_CONSUMER_ENABLE_BARCODES",
)

CONSUMER_BARCODE_TIFF_SUPPORT: Final[bool] = __get_boolean(
    "PAPERLESS_CONSUMER_BARCODE_TIFF_SUPPORT",
)

CONSUMER_BARCODE_STRING: Final[str] = os.getenv(
    "PAPERLESS_CONSUMER_BARCODE_STRING",
    "PATCHT",
)

CONSUMER_ENABLE_ASN_BARCODE: Final[bool] = __get_boolean(
    "PAPERLESS_CONSUMER_ENABLE_ASN_BARCODE",
)

CONSUMER_ASN_BARCODE_PREFIX: Final[str] = os.getenv(
    "PAPERLESS_CONSUMER_ASN_BARCODE_PREFIX",
    "ASN",
)


OCR_PAGES = int(os.getenv("PAPERLESS_OCR_PAGES", 0))

# The default language that tesseract will attempt to use when parsing
# documents.  It should be a 3-letter language code consistent with ISO 639.
OCR_LANGUAGE = os.getenv("PAPERLESS_OCR_LANGUAGE", "eng")

# OCRmyPDF --output-type options are available.
OCR_OUTPUT_TYPE = os.getenv("PAPERLESS_OCR_OUTPUT_TYPE", "pdfa")

# skip. redo, force
OCR_MODE = os.getenv("PAPERLESS_OCR_MODE", "skip")

OCR_IMAGE_DPI = os.getenv("PAPERLESS_OCR_IMAGE_DPI")

OCR_CLEAN = os.getenv("PAPERLESS_OCR_CLEAN", "clean")

OCR_DESKEW = __get_boolean("PAPERLESS_OCR_DESKEW", "true")

OCR_ROTATE_PAGES = __get_boolean("PAPERLESS_OCR_ROTATE_PAGES", "true")

OCR_ROTATE_PAGES_THRESHOLD = float(
    os.getenv("PAPERLESS_OCR_ROTATE_PAGES_THRESHOLD", 12.0),
)

OCR_MAX_IMAGE_PIXELS: Optional[int] = None
if os.environ.get("PAPERLESS_OCR_MAX_IMAGE_PIXELS") is not None:
    OCR_MAX_IMAGE_PIXELS: int = int(os.environ.get("PAPERLESS_OCR_MAX_IMAGE_PIXELS"))

OCR_USER_ARGS = os.getenv("PAPERLESS_OCR_USER_ARGS", "{}")

# GNUPG needs a home directory for some reason
GNUPG_HOME = os.getenv("HOME", "/tmp")

# Convert is part of the ImageMagick package
CONVERT_BINARY = os.getenv("PAPERLESS_CONVERT_BINARY", "convert")
CONVERT_TMPDIR = os.getenv("PAPERLESS_CONVERT_TMPDIR")
CONVERT_MEMORY_LIMIT = os.getenv("PAPERLESS_CONVERT_MEMORY_LIMIT")

GS_BINARY = os.getenv("PAPERLESS_GS_BINARY", "gs")


# Pre-2.x versions of Paperless stored your documents locally with GPG
# encryption, but that is no longer the default.  This behaviour is still
# available, but it must be explicitly enabled by setting
# `PAPERLESS_PASSPHRASE` in your environment or config file.  The default is to
# store these files unencrypted.
#
# Translation:
# * If you're a new user, you can safely ignore this setting.
# * If you're upgrading from 1.x, this must be set, OR you can run
#   `./manage.py change_storage_type gpg unencrypted` to decrypt your files,
#   after which you can unset this value.
PASSPHRASE = os.getenv("PAPERLESS_PASSPHRASE")

# Trigger a script after every successful document consumption?
PRE_CONSUME_SCRIPT = os.getenv("PAPERLESS_PRE_CONSUME_SCRIPT")
POST_CONSUME_SCRIPT = os.getenv("PAPERLESS_POST_CONSUME_SCRIPT")

# Specify the default date order (for autodetected dates)
DATE_ORDER = os.getenv("PAPERLESS_DATE_ORDER", "DMY")
FILENAME_DATE_ORDER = os.getenv("PAPERLESS_FILENAME_DATE_ORDER")

# Maximum number of dates taken from document start to end to show as suggestions for
# `created` date in the frontend. Duplicates are removed, which can result in
# fewer dates shown.
NUMBER_OF_SUGGESTED_DATES = __get_int("PAPERLESS_NUMBER_OF_SUGGESTED_DATES", 3)

# Transformations applied before filename parsing
FILENAME_PARSE_TRANSFORMS = []
for t in json.loads(os.getenv("PAPERLESS_FILENAME_PARSE_TRANSFORMS", "[]")):
    FILENAME_PARSE_TRANSFORMS.append((re.compile(t["pattern"]), t["repl"]))

# Specify the filename format for out files
FILENAME_FORMAT = os.getenv("PAPERLESS_FILENAME_FORMAT")

# If this is enabled, variables in filename format will resolve to
# empty-string instead of 'none'.
# Directories with 'empty names' are omitted, too.
FILENAME_FORMAT_REMOVE_NONE = __get_boolean(
    "PAPERLESS_FILENAME_FORMAT_REMOVE_NONE",
    "NO",
)

THUMBNAIL_FONT_NAME = os.getenv(
    "PAPERLESS_THUMBNAIL_FONT_NAME",
    "/usr/share/fonts/liberation/LiberationSerif-Regular.ttf",
)

# Tika settings
TIKA_ENABLED = __get_boolean("PAPERLESS_TIKA_ENABLED", "NO")
TIKA_ENDPOINT = os.getenv("PAPERLESS_TIKA_ENDPOINT", "http://localhost:9998")
TIKA_GOTENBERG_ENDPOINT = os.getenv(
    "PAPERLESS_TIKA_GOTENBERG_ENDPOINT",
    "http://localhost:3000",
)

if TIKA_ENABLED:
    INSTALLED_APPS.append("paperless_tika.apps.PaperlessTikaConfig")


def _parse_ignore_dates(
    env_ignore: str,
    date_order: str = DATE_ORDER,
) -> Set[datetime.datetime]:
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
IGNORE_DATES: Set[datetime.date] = set()

if os.getenv("PAPERLESS_IGNORE_DATES") is not None:
    IGNORE_DATES = _parse_ignore_dates(os.getenv("PAPERLESS_IGNORE_DATES"))

ENABLE_UPDATE_CHECK = os.getenv("PAPERLESS_ENABLE_UPDATE_CHECK", "default")
if ENABLE_UPDATE_CHECK != "default":
    ENABLE_UPDATE_CHECK = __get_boolean("PAPERLESS_ENABLE_UPDATE_CHECK")

###############################################################################
# Machine Learning                                                            #
###############################################################################


def _get_nltk_language_setting(ocr_lang: str) -> Optional[str]:
    """
    Maps an ISO-639-1 language code supported by Tesseract into
    an optional NLTK language name.  This is the set of common supported
    languages for all the NLTK data used.

    Assumption: The primary language is first
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

    return iso_code_to_nltk.get(ocr_lang, None)


NLTK_ENABLED: Final[bool] = __get_boolean("PAPERLESS_ENABLE_NLTK", "yes")

NLTK_LANGUAGE: Optional[str] = _get_nltk_language_setting(OCR_LANGUAGE)
