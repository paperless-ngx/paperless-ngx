import json
import multiprocessing
import os
import re

from dotenv import load_dotenv

# Tap paperless.conf if it's available
if os.path.exists("../paperless.conf"):
    load_dotenv("../paperless.conf")
elif os.path.exists("/etc/paperless.conf"):
    load_dotenv("/etc/paperless.conf")
elif os.path.exists("/usr/local/etc/paperless.conf"):
    load_dotenv("/usr/local/etc/paperless.conf")


def __get_boolean(key, default="NO"):
    """
    Return a boolean value based on whatever the user has supplied in the
    environment based on whether the value "looks like" it's True or not.
    """
    return bool(os.getenv(key, default).lower() in ("yes", "y", "1", "t", "true"))

###############################################################################
# Directories                                                                 #
###############################################################################

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

STATIC_ROOT = os.getenv("PAPERLESS_STATICDIR", os.path.join(BASE_DIR, "..", "static"))

MEDIA_ROOT = os.getenv('PAPERLESS_MEDIA_ROOT', os.path.join(BASE_DIR, "..", "media"))
ORIGINALS_DIR = os.path.join(MEDIA_ROOT, "documents", "originals")
THUMBNAIL_DIR = os.path.join(MEDIA_ROOT, "documents", "thumbnails")

DATA_DIR = os.getenv('PAPERLESS_DATA_DIR', os.path.join(BASE_DIR, "..", "data"))
INDEX_DIR = os.path.join(DATA_DIR, "index")
MODEL_FILE = os.path.join(DATA_DIR, "classification_model.pickle")
###############################################################################
# Application Definition                                                      #
###############################################################################

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

    "django.contrib.admin",

    "rest_framework",
    "rest_framework.authtoken",
    "django_filters",

]

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.BasicAuthentication',
        'rest_framework.authentication.TokenAuthentication',
        'paperless.auth.QueryTokenAuthentication'
    ]
}

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'paperless.urls'

LOGIN_URL = "admin:login"

FORCE_SCRIPT_NAME = os.getenv("PAPERLESS_FORCE_SCRIPT_NAME")

WSGI_APPLICATION = 'paperless.wsgi.application'

STATIC_URL = os.getenv("PAPERLESS_STATIC_URL", "/static/")

# what is this used for?
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

###############################################################################
# Security                                                                    #
###############################################################################

# NEVER RUN WITH DEBUG IN PRODUCTION.
DEBUG = __get_boolean("PAPERLESS_DEBUG", "NO")

X_FRAME_OPTIONS = 'SAMEORIGIN'

# We allow CORS from localhost:8080
CORS_ORIGIN_WHITELIST = tuple(os.getenv("PAPERLESS_CORS_ALLOWED_HOSTS", "http://localhost:8080,https://localhost:8080").split(","))

if DEBUG:
    # Allow access from the angular development server during debugging
    CORS_ORIGIN_WHITELIST += ('http://localhost:4200',)

# If auth is disabled, we just use our "bypass" authentication middleware
if bool(os.getenv("PAPERLESS_DISABLE_LOGIN", "false").lower() in ("yes", "y", "1", "t", "true")):
    _index = MIDDLEWARE.index("django.contrib.auth.middleware.AuthenticationMiddleware")
    MIDDLEWARE[_index] = "paperless.middleware.Middleware"

# The secret key has a default that should be fine so long as you're hosting
# Paperless on a closed network.  However, if you're putting this anywhere
# public, you should change the key to something unique and verbose.
SECRET_KEY = os.getenv(
    "PAPERLESS_SECRET_KEY",
    "e11fl1oa-*ytql8p)(06fbj4ukrlo+n7k&q5+$1md7i+mge=ee"
)

_allowed_hosts = os.getenv("PAPERLESS_ALLOWED_HOSTS")
if _allowed_hosts:
    ALLOWED_HOSTS = _allowed_hosts.split(",")
else:
    ALLOWED_HOSTS = ["*"]

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Disable Django's artificial limit on the number of form fields to submit at
# once. This is a protection against overloading the server, but since this is
# a self-hosted sort of gig, the benefits of being able to mass-delete a tonne
# of log entries outweight the benefits of such a safeguard.

DATA_UPLOAD_MAX_NUMBER_FIELDS = None

###############################################################################
# Database                                                                    #
###############################################################################

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.path.join(
            DATA_DIR,
            "db.sqlite3"
        )
    }
}

# Always have sqlite available as a second option for management commands
# This is important when migrating to/from sqlite
DATABASES['sqlite'] = DATABASES['default'].copy()

if os.getenv("PAPERLESS_DBENGINE"):
    DATABASES["default"] = {
        "ENGINE": os.getenv("PAPERLESS_DBENGINE"),
        "NAME": os.getenv("PAPERLESS_DBNAME", "paperless"),
        "USER": os.getenv("PAPERLESS_DBUSER"),
    }
    if os.getenv("PAPERLESS_DBPASS"):
        DATABASES["default"]["PASSWORD"] = os.getenv("PAPERLESS_DBPASS")
    if os.getenv("PAPERLESS_DBHOST"):
        DATABASES["default"]["HOST"] = os.getenv("PAPERLESS_DBHOST")
    if os.getenv("PAPERLESS_DBPORT"):
        DATABASES["default"]["PORT"] = os.getenv("PAPERLESS_DBPORT")

###############################################################################
# Internationalization                                                        #
###############################################################################

LANGUAGE_CODE = 'en-us'

TIME_ZONE = os.getenv("PAPERLESS_TIME_ZONE", "UTC")

USE_I18N = True

USE_L10N = True

USE_TZ = True

###############################################################################
# Logging                                                                     #
###############################################################################

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "dbhandler": {
            "class": "documents.loggers.PaperlessHandler",
        },
        "streamhandler": {
            "class": "logging.StreamHandler"
        }
    },
    "loggers": {
        "documents": {
            "handlers": ["dbhandler", "streamhandler"],
            "level": "DEBUG"
        },
    },
}

###############################################################################
# Paperless Specific Settings                                                 #
###############################################################################

# The default language that tesseract will attempt to use when parsing
# documents.  It should be a 3-letter language code consistent with ISO 639.
OCR_LANGUAGE = os.getenv("PAPERLESS_OCR_LANGUAGE", "eng")

# The amount of threads to use for OCR
OCR_THREADS = int(os.getenv("PAPERLESS_OCR_THREADS", multiprocessing.cpu_count()))

# OCR all documents?
OCR_ALWAYS = __get_boolean("PAPERLESS_OCR_ALWAYS", "false")

# GNUPG needs a home directory for some reason
GNUPG_HOME = os.getenv("HOME", "/tmp")

# Convert is part of the ImageMagick package
CONVERT_BINARY = os.getenv("PAPERLESS_CONVERT_BINARY", "convert")
CONVERT_TMPDIR = os.getenv("PAPERLESS_CONVERT_TMPDIR")
CONVERT_MEMORY_LIMIT = os.getenv("PAPERLESS_CONVERT_MEMORY_LIMIT")
CONVERT_DENSITY = int(os.getenv("PAPERLESS_CONVERT_DENSITY", 300))

GS_BINARY = os.getenv("PAPERLESS_GS_BINARY", "gs")
OPTIPNG_BINARY = os.getenv("PAPERLESS_OPTIPNG_BINARY", "optipng")
UNPAPER_BINARY = os.getenv("PAPERLESS_UNPAPER_BINARY", "unpaper")

# This will be created if it doesn't exist
SCRATCH_DIR = os.getenv("PAPERLESS_SCRATCH_DIR", "/tmp/paperless")

# This is where Paperless will look for PDFs to index
CONSUMPTION_DIR = os.getenv("PAPERLESS_CONSUMPTION_DIR")

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
