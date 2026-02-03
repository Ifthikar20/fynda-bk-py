"""
Base Django Settings - Shared across all environments
"""

from pathlib import Path
import os
from datetime import timedelta

# Import centralized config
from fynda.config import config, get_database_config

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party apps
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    # Local apps
    "deals",
    "users",
    "emails",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Request filters (run first - stateless validation)
    "fynda.middleware.PathTraversalFilter",
    "fynda.middleware.RequestSizeFilter",
    "fynda.middleware.ContentTypeFilter",
    "fynda.middleware.ParameterValidationFilter",
    "fynda.middleware.JSONValidationFilter",
    # API protection (anti-enumeration, bot detection)
    "fynda.middleware.APIGuardMiddleware",
    "fynda.middleware.BotDetectionMiddleware",
    # Core security middleware
    "fynda.middleware.SecurityHeadersMiddleware",
    "fynda.middleware.RateLimitMiddleware",
    "fynda.middleware.InputSanitizationMiddleware",
    "fynda.middleware.RequestLoggingMiddleware",
    # Response interceptors (run last - sanitize output)
    "fynda.middleware.ResponseInterceptor",
    "fynda.middleware.NotFoundNormalizerMiddleware",
]

ROOT_URLCONF = "fynda.urls"

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

WSGI_APPLICATION = "fynda.wsgi.application"

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Custom User Model
AUTH_USER_MODEL = "users.User"

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Media files (for image uploads)
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# REST Framework settings
REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",
        "rest_framework.parsers.FormParser",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "100/hour",
        "user": "1000/hour",
    },
}

# JWT Settings
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=1),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# CORS Settings (from config)
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = config.security.cors_origins
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = [
    "DELETE",
    "GET",
    "OPTIONS",
    "PATCH",
    "POST",
    "PUT",
]
CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
]

# CSRF Settings
CSRF_TRUSTED_ORIGINS = config.security.csrf_trusted_origins

# Celery Configuration (from config)
CELERY_BROKER_URL = config.redis.broker_url
CELERY_RESULT_BACKEND = config.redis.result_backend
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "UTC"

# Cache Configuration
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

# Logging Configuration
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "deals": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
        "fynda.config": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# =============================================================================
# API Keys - Now accessed via config module
# =============================================================================
# Usage: from fynda.config import config
#        api_key = config.apis.rapidapi_key

OPENAI_API_KEY = config.apis.openai_api_key
EBAY_APP_ID = config.apis.ebay_app_id
EBAY_CERT_ID = config.apis.ebay_cert_id
BESTBUY_API_KEY = config.apis.bestbuy_api_key
RAPIDAPI_KEY = config.apis.rapidapi_key

# Affiliate Networks
CJ_API_TOKEN = config.apis.cj_api_token
CJ_WEBSITE_ID = config.apis.cj_website_id
RAKUTEN_API_TOKEN = config.apis.rakuten_api_token
RAKUTEN_SITE_ID = config.apis.rakuten_site_id
SHAREASALE_AFFILIATE_ID = config.apis.shareasale_affiliate_id
SHAREASALE_API_TOKEN = config.apis.shareasale_api_token
SHAREASALE_API_SECRET = config.apis.shareasale_api_secret

# ML Service
ML_SERVICE_URL = config.ml_service.url
ML_SERVICE_TIMEOUT = config.ml_service.timeout

# File upload settings
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10 MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10 MB

# =============================================================================
# EMAIL CONFIGURATION - AWS SES
# =============================================================================
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.getenv('EMAIL_HOST', 'email-smtp.us-east-1.amazonaws.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', 587))
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.getenv('AWS_SES_ACCESS_KEY', '')
EMAIL_HOST_PASSWORD = os.getenv('AWS_SES_SECRET_KEY', '')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'Fynda <noreply@fynda.shop>')
SITE_URL = os.getenv('SITE_URL', 'https://fynda.shop')

# Log configuration status on startup
config.log_status()

