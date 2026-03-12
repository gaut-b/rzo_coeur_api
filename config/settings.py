import os
from pathlib import Path

from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve(strict=True).parent.parent

# Load environment variables: .env.local takes precedence over .env
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR / ".env.local", override=True)
BASE_DIR = Path(__file__).resolve(strict=True).parent.parent

# Geospatial libraries — only set when explicitly provided (macOS/custom installs).
# Leave unset inside Docker so that Django auto-discovers the system libraries.
if _gdal_path := os.getenv("GDAL_LIBRARY_PATH"):
    GDAL_LIBRARY_PATH = _gdal_path
if _geos_path := os.getenv("GEOS_LIBRARY_PATH"):
    GEOS_LIBRARY_PATH = _geos_path

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get("SECRET_KEY", "django-insecure-m$k=iw56r4-nqz8c2q5=j1!#8y6g=ajyb^7rkaft&7t98v(q!g")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get("DEBUG", "0").lower() in ("1", "true", "yes")

# Prevent accidental deploy with an insecure default key.
if not DEBUG and SECRET_KEY.startswith("django-insecure-"):
    from django.core.exceptions import ImproperlyConfigured

    raise ImproperlyConfigured(
        "SECRET_KEY must be set to a secure value in production. "
        'Generate one with: python -c "'
        "from django.core.management.utils import get_random_secret_key; "
        'print(get_random_secret_key())"'
    )

ALLOWED_HOSTS = [h.strip() for h in os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")]

# When served under a sub-path (e.g. /rzo-coeur/), set this so Django
# generates correct URLs in redirects, admin, etc.
_script_name = os.environ.get("FORCE_SCRIPT_NAME", "")
if _script_name:
    FORCE_SCRIPT_NAME = _script_name


AUTH_USER_MODEL = "api.CustomUser"

GRAPH_MODELS = {
    "all_applications": True,
    "group_models": True,
}
# Application definition
CSRF_TRUSTED_ORIGINS = [o.strip() for o in os.environ.get("CSRF_TRUSTED_ORIGINS", "http://localhost").split(",")]
INSTALLED_APPS = [
    "api.apps.ApiConfig",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.gis",
    "rest_framework",
    "drf_spectacular",
    "django_extensions",
    "allauth",
    "allauth.account",
    "auth_kit",
    "django_admin_action_forms",
    "storages",
]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "auth_kit.authentication.JWTCookieAuthentication",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
}

# Add BrowsableAPIRenderer only in development
if DEBUG:
    REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"] = [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ]
else:
    REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"] = [
        "rest_framework.renderers.JSONRenderer",
    ]

SPECTACULAR_SETTINGS = {
    "TITLE": "Les réseaux du coeur API",
    "DESCRIPTION": 'API for the "Les réseaux du coeur" application',
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    # OTHER SETTINGS
}

# Configure auth_kit to use our custom serializers
AUTH_KIT = {
    "USER_SERIALIZER": "api.serializers.CustomUserSerializer",
    "REGISTER_SERIALIZER": "api.serializers.CustomRegisterSerializer",
    "USE_AUTH_COOKIE": True,
}

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]

ROOT_URLCONF = "config.urls"

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

WSGI_APPLICATION = "config.wsgi.application"


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases


DATABASES = {
    "default": {
        "ENGINE": os.environ.get("SQL_ENGINE", "django.contrib.gis.db.backends.postgis"),
        "NAME": os.environ.get("SQL_DATABASE", BASE_DIR / "db.sqlite3"),
        "USER": os.environ.get("SQL_USER", "user"),
        "PASSWORD": os.environ.get("SQL_PASSWORD", "password"),
        "HOST": os.environ.get("SQL_HOST", "localhost"),
        "PORT": os.environ.get("SQL_PORT", "5432"),
        # Keep connections open for 60 s instead of closing after every request.
        # CONN_HEALTH_CHECKS avoids reusing stale connections after a DB restart.
        "CONN_MAX_AGE": int(os.environ.get("DB_CONN_MAX_AGE", "60")),
        "CONN_HEALTH_CHECKS": True,
    }
}
# Password hashers
# Use scrypt as the primary hasher (memory-hard, OWASP recommended, built into
# Python 3.9+ stdlib — no extra dependency required). PBKDF2 is kept as a
# fallback so existing password hashes remain valid and are transparently
# upgraded to scrypt on the user's next successful login.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.ScryptPasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
]

# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

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


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = "fr"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

# When deployed under a sub-path (FORCE_SCRIPT_NAME=/rzo-coeur), prefix
# STATIC_URL and MEDIA_URL accordingly so browsers request the right URLs.
_script_name = os.environ.get("FORCE_SCRIPT_NAME", "").rstrip("/")
STATIC_URL = f"{_script_name}/static/" if _script_name else "static/"
MEDIA_URL = f"{_script_name}/media/" if _script_name else "media/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# ---------------------------------------------------------------------------
# Media / Object Storage (MinIO / S3-compatible)
# ---------------------------------------------------------------------------
# When MINIO_ENDPOINT_URL is set (typically in Docker), uploaded files are
# stored in the configured S3-compatible bucket and served publicly as a CDN.
# When the variable is absent (e.g. running tests locally without MinIO), we
# fall back to Django's default local filesystem storage so that tests don't
# require a live MinIO instance.
# ---------------------------------------------------------------------------

STORAGES = {
    "default": {
        "BACKEND": (
            "config.storage.MinIOPublicStorage"
            if os.environ.get("MINIO_ENDPOINT_URL")
            else "django.core.files.storage.FileSystemStorage"
        ),
    },
    "staticfiles": {
        # CompressedManifestStaticFilesStorage requires a pre-built manifest
        # (collectstatic). Use it only in production; fall back to the plain
        # Django storage in development and during tests.
        "BACKEND": (
            "whitenoise.storage.CompressedManifestStaticFilesStorage"
            if not DEBUG
            else "django.contrib.staticfiles.storage.StaticFilesStorage"
        ),
    },
}

# S3 / MinIO credentials – ignored when falling back to local storage
AWS_S3_ENDPOINT_URL = os.environ.get("MINIO_ENDPOINT_URL", "")
AWS_ACCESS_KEY_ID = os.environ.get("MINIO_ROOT_USER", "minioadmin")
AWS_SECRET_ACCESS_KEY = os.environ.get("MINIO_ROOT_PASSWORD", "minioadmin")
AWS_STORAGE_BUCKET_NAME = os.environ.get("MINIO_BUCKET_NAME", "articles-photos")
AWS_S3_FILE_OVERWRITE = False
AWS_DEFAULT_ACL = "public-read"
# Disable presigned URL query parameters (AWSAccessKeyId, Signature, Expires).
# The bucket is public-read so no signing is needed, and query params break
# the nginx /storage/ proxy rewrite.
AWS_QUERYSTRING_AUTH = False
# Use path-style URLs (required by MinIO): http://<host>/<bucket>/<key>
AWS_S3_ADDRESSING_STYLE = "path"
# Derive the public MinIO URL from API_URL so a single variable controls all
# public-facing addresses:
#   http://localhost/storage/articles-photos  (dev)
#   https://api.example.com/storage/articles-photos  (prod)
_api_url = os.environ.get("API_URL", "http://localhost").rstrip("/")
MINIO_PUBLIC_URL = f"{_api_url}/storage/{AWS_STORAGE_BUCKET_NAME}"

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Use a custom test runner that disables SECURE_SSL_REDIRECT automatically.
# The test client uses plain HTTP, so the redirect would break all tests.
TEST_RUNNER = "config.test_runner.TestRunner"

# ---------------------------------------------------------------------------
# Logging — structured logging to stdout so Docker captures all output.
# The console handler covers all environments; a file handler is omitted
# because the app runs inside Docker where stdout is the canonical log sink.
# Only active in production; Django's default logging is used in development.
# ---------------------------------------------------------------------------
if not DEBUG:
    LOGGING = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "verbose": {
                "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
                "style": "{",
            },
        },
        "handlers": {
            "console": {
                "level": "INFO",
                "class": "logging.StreamHandler",
                "formatter": "verbose",
            },
        },
        "loggers": {
            "django": {
                "handlers": ["console"],
                "level": "INFO",
                "propagate": False,
            },
            # Django's template engine logs a DEBUG entry for every missing
            # variable, even those handled by |default or {% if %}. This is
            # extremely noisy and does not indicate a real error.
            "django.template": {
                "handlers": ["console"],
                "level": "WARNING",
                "propagate": False,
            },
            "api": {
                "handlers": ["console"],
                "level": "INFO",
                "propagate": False,
            },
        },
    }


# ---------------------------------------------------------------------------
# Production security settings.
# nginx (on the host) terminates TLS and forwards X-Forwarded-Proto: https.
# The inner Docker nginx must pass this header through (not override with
# $scheme which is always 'http' inside Docker), so Django can correctly
# identify HTTPS connections and enforce secure cookies.
# ---------------------------------------------------------------------------
if not DEBUG:
    # Trust X-Forwarded-Proto set by the host-level nginx reverse proxy.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    # Redirect HTTP → HTTPS at the Django level (nginx also does this).
    SECURE_SSL_REDIRECT = True
    # Enable HSTS: browsers will only connect via HTTPS for 1 year.
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    # Prevent cookies from being sent over HTTP.
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

# Email configuration
if DEBUG:
    # Use Mailhog for local development
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    # Use 'mailhog' when running in Docker, 'localhost' when running locally
    EMAIL_HOST = os.environ.get("EMAIL_HOST", "localhost")
    EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "1025"))
    EMAIL_USE_TLS = False
    EMAIL_USE_SSL = False
else:
    # Production email configuration
    # TODO: Configure production email backend (SendGrid, Mailgun, etc.)
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
