import json
import math
import multiprocessing
import os
import re

from concurrent_log_handler.queue import setup_logging_queues
from django.utils.translation import gettext_lazy as _
from dotenv import load_dotenv

# Tap paperless.conf if it's available
if os.path.exists("../paperless.conf"):
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


def __get_boolean(key, default="NO"):
    """
    Return a boolean value based on whatever the user has supplied in the
    environment based on whether the value "looks like" it's True or not.
    """
    return bool(os.getenv(key, default).lower() in ("yes", "y", "1", "t", "true"))


# NEVER RUN WITH DEBUG IN PRODUCTION.
DEBUG = __get_boolean("PAPERLESS_DEBUG", "NO")


###############################################################################
# Directories                                                                 #
###############################################################################

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

STATIC_ROOT = os.getenv("PAPERLESS_STATICDIR", os.path.join(BASE_DIR, "..", "static"))

MEDIA_ROOT = os.getenv("PAPERLESS_MEDIA_ROOT", os.path.join(BASE_DIR, "..", "media"))
ORIGINALS_DIR = os.path.join(MEDIA_ROOT, "documents", "originals")
ARCHIVE_DIR = os.path.join(MEDIA_ROOT, "documents", "archive")
THUMBNAIL_DIR = os.path.join(MEDIA_ROOT, "documents", "thumbnails")

DATA_DIR = os.getenv("PAPERLESS_DATA_DIR", os.path.join(BASE_DIR, "..", "data"))

TRASH_DIR = os.getenv("PAPERLESS_TRASH_DIR")

# Lock file for synchronizing changes to the MEDIA directory across multiple
# threads.
MEDIA_LOCK = os.path.join(MEDIA_ROOT, "media.lock")
INDEX_DIR = os.path.join(DATA_DIR, "index")
MODEL_FILE = os.path.join(DATA_DIR, "classification_model.pickle")

LOGGING_DIR = os.getenv("PAPERLESS_LOGGING_DIR", os.path.join(DATA_DIR, "log"))

CONSUMPTION_DIR = os.getenv(
    "PAPERLESS_CONSUMPTION_DIR",
    os.path.join(BASE_DIR, "..", "consume"),
)

# This will be created if it doesn't exist
SCRATCH_DIR = os.getenv("PAPERLESS_SCRATCH_DIR", "/tmp/paperless")

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
    "django_q",
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

ROOT_URLCONF = "paperless.urls"

FORCE_SCRIPT_NAME = os.getenv("PAPERLESS_FORCE_SCRIPT_NAME")
BASE_URL = (FORCE_SCRIPT_NAME or "") + "/"
LOGIN_URL = BASE_URL + "accounts/login/"
LOGOUT_REDIRECT_URL = os.getenv("PAPERLESS_LOGOUT_REDIRECT_URL")

WSGI_APPLICATION = "paperless.wsgi.application"
ASGI_APPLICATION = "paperless.asgi.application"

STATIC_URL = os.getenv("PAPERLESS_STATIC_URL", BASE_URL + "static/")
WHITENOISE_STATIC_PREFIX = "/static/"

# TODO: what is this used for?
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
            "hosts": [os.getenv("PAPERLESS_REDIS", "redis://localhost:6379")],
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

# We allow CORS from localhost:8080
CORS_ALLOWED_ORIGINS = tuple(
    os.getenv("PAPERLESS_CORS_ALLOWED_HOSTS", "http://localhost:8000").split(","),
)

if DEBUG:
    # Allow access from the angular development server during debugging
    CORS_ALLOWED_ORIGINS += ("http://localhost:4200",)

# The secret key has a default that should be fine so long as you're hosting
# Paperless on a closed network.  However, if you're putting this anywhere
# public, you should change the key to something unique and verbose.
SECRET_KEY = os.getenv(
    "PAPERLESS_SECRET_KEY",
    "e11fl1oa-*ytql8p)(06fbj4ukrlo+n7k&q5+$1md7i+mge=ee",
)

_allowed_hosts = os.getenv("PAPERLESS_ALLOWED_HOSTS")
if _allowed_hosts:
    ALLOWED_HOSTS = _allowed_hosts.split(",")
else:
    ALLOWED_HOSTS = ["*"]

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
    },
}

if os.getenv("PAPERLESS_DBHOST"):
    # Have sqlite available as a second option for management commands
    # This is important when migrating to/from sqlite
    DATABASES["sqlite"] = DATABASES["default"].copy()

    DATABASES["default"] = {
        "ENGINE": "django.db.backends.postgresql_psycopg2",
        "HOST": os.getenv("PAPERLESS_DBHOST"),
        "NAME": os.getenv("PAPERLESS_DBNAME", "paperless"),
        "USER": os.getenv("PAPERLESS_DBUSER", "paperless"),
        "PASSWORD": os.getenv("PAPERLESS_DBPASS", "paperless"),
        "OPTIONS": {"sslmode": os.getenv("PAPERLESS_DBSSLMODE", "prefer")},
    }
    if os.getenv("PAPERLESS_DBPORT"):
        DATABASES["default"]["PORT"] = os.getenv("PAPERLESS_DBPORT")

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

###############################################################################
# Internationalization                                                        #
###############################################################################

LANGUAGE_CODE = "en-us"

LANGUAGES = [
    ("en-us", _("English (US)")),  # needs to be first to act as fallback language
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


# Sensible defaults for multitasking:
# use a fair balance between worker processes and threads epr worker so that
# both consuming many documents in parallel and consuming large documents is
# reasonably fast.
# Favors threads per worker on smaller systems and never exceeds cpu_count()
# in total.


def default_task_workers():
    # always leave one core open
    available_cores = max(multiprocessing.cpu_count(), 1)
    try:
        if available_cores < 4:
            return available_cores
        return max(math.floor(math.sqrt(available_cores)), 1)
    except NotImplementedError:
        return 1


TASK_WORKERS = int(os.getenv("PAPERLESS_TASK_WORKERS", default_task_workers()))

Q_CLUSTER = {
    "name": "paperless",
    "catch_up": False,
    "recycle": 1,
    "retry": 1800,
    "timeout": int(os.getenv("PAPERLESS_WORKER_TIMEOUT", 1800)),
    "workers": TASK_WORKERS,
    "redis": os.getenv("PAPERLESS_REDIS", "redis://localhost:6379"),
}


def default_threads_per_worker(task_workers):
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

CONSUMER_DELETE_DUPLICATES = __get_boolean("PAPERLESS_CONSUMER_DELETE_DUPLICATES")

CONSUMER_RECURSIVE = __get_boolean("PAPERLESS_CONSUMER_RECURSIVE")

# Ignore glob patterns, relative to PAPERLESS_CONSUMPTION_DIR
CONSUMER_IGNORE_PATTERNS = list(
    json.loads(
        os.getenv(
            "PAPERLESS_CONSUMER_IGNORE_PATTERNS",
            '[".DS_STORE/*", "._*", ".stfolder/*", ".stversions/*", ".localized/*", "desktop.ini"]',
        ),
    ),
)

CONSUMER_SUBDIRS_AS_TAGS = __get_boolean("PAPERLESS_CONSUMER_SUBDIRS_AS_TAGS")

CONSUMER_ENABLE_BARCODES = __get_boolean(
    "PAPERLESS_CONSUMER_ENABLE_BARCODES",
    default="YES",
)

CONSUMER_BARCODE_STRING = os.getenv("PAPERLESS_CONSUMER_BARCODE_STRING", "PATCHT")

OPTIMIZE_THUMBNAILS = __get_boolean("PAPERLESS_OPTIMIZE_THUMBNAILS", "true")

OCR_PAGES = int(os.getenv("PAPERLESS_OCR_PAGES", 0))

# The default language that tesseract will attempt to use when parsing
# documents.  It should be a 3-letter language code consistent with ISO 639.
OCR_LANGUAGE = os.getenv("PAPERLESS_OCR_LANGUAGE", "eng")

# OCRmyPDF --output-type options are available.
# TODO: validate this setting.
OCR_OUTPUT_TYPE = os.getenv("PAPERLESS_OCR_OUTPUT_TYPE", "pdfa")

# skip. redo, force
# TODO: validate this.
OCR_MODE = os.getenv("PAPERLESS_OCR_MODE", "skip")

OCR_IMAGE_DPI = os.getenv("PAPERLESS_OCR_IMAGE_DPI")

OCR_CLEAN = os.getenv("PAPERLESS_OCR_CLEAN", "clean")

OCR_DESKEW = __get_boolean("PAPERLESS_OCR_DESKEW", "true")

OCR_ROTATE_PAGES = __get_boolean("PAPERLESS_OCR_ROTATE_PAGES", "true")

OCR_ROTATE_PAGES_THRESHOLD = float(
    os.getenv("PAPERLESS_OCR_ROTATE_PAGES_THRESHOLD", 12.0),
)

OCR_MAX_IMAGE_PIXELS = os.environ.get(
    "PAPERLESS_OCR_MAX_IMAGE_PIXELS",
    256000000,
)

OCR_USER_ARGS = os.getenv("PAPERLESS_OCR_USER_ARGS", "{}")

# GNUPG needs a home directory for some reason
GNUPG_HOME = os.getenv("HOME", "/tmp")

# Convert is part of the ImageMagick package
CONVERT_BINARY = os.getenv("PAPERLESS_CONVERT_BINARY", "convert")
CONVERT_TMPDIR = os.getenv("PAPERLESS_CONVERT_TMPDIR")
CONVERT_MEMORY_LIMIT = os.getenv("PAPERLESS_CONVERT_MEMORY_LIMIT")

GS_BINARY = os.getenv("PAPERLESS_GS_BINARY", "gs")

OPTIPNG_BINARY = os.getenv("PAPERLESS_OPTIPNG_BINARY", "optipng")


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

# Transformations applied before filename parsing
FILENAME_PARSE_TRANSFORMS = []
for t in json.loads(os.getenv("PAPERLESS_FILENAME_PARSE_TRANSFORMS", "[]")):
    FILENAME_PARSE_TRANSFORMS.append((re.compile(t["pattern"]), t["repl"]))

# TODO: this should not have a prefix.
# Specify the filename format for out files
PAPERLESS_FILENAME_FORMAT = os.getenv("PAPERLESS_FILENAME_FORMAT")

THUMBNAIL_FONT_NAME = os.getenv(
    "PAPERLESS_THUMBNAIL_FONT_NAME",
    "/usr/share/fonts/liberation/LiberationSerif-Regular.ttf",
)

# Tika settings
PAPERLESS_TIKA_ENABLED = __get_boolean("PAPERLESS_TIKA_ENABLED", "NO")
PAPERLESS_TIKA_ENDPOINT = os.getenv("PAPERLESS_TIKA_ENDPOINT", "http://localhost:9998")
PAPERLESS_TIKA_GOTENBERG_ENDPOINT = os.getenv(
    "PAPERLESS_TIKA_GOTENBERG_ENDPOINT",
    "http://localhost:3000",
)

if PAPERLESS_TIKA_ENABLED:
    INSTALLED_APPS.append("paperless_tika.apps.PaperlessTikaConfig")

# List dates that should be ignored when trying to parse date from document text
IGNORE_DATES = set()

if os.getenv("PAPERLESS_IGNORE_DATES", ""):
    import dateparser

    for s in os.getenv("PAPERLESS_IGNORE_DATES", "").split(","):
        d = dateparser.parse(s)
        if d:
            IGNORE_DATES.add(d.date())

ENABLE_UPDATE_CHECK = os.getenv("PAPERLESS_ENABLE_UPDATE_CHECK", "default")
if ENABLE_UPDATE_CHECK != "default":
    ENABLE_UPDATE_CHECK = __get_boolean("PAPERLESS_ENABLE_UPDATE_CHECK")
