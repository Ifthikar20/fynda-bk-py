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
    "jazzmin",  # Modern admin UI - must be before django.contrib.admin
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sitemaps",
    # Third-party apps
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "nested_admin",  # For nested inlines in admin
    "storages",  # django-storages for S3
    # Local apps
    "core.apps.CoreConfig",
    "deals",
    "users",
    "emails",
    "blog",
    "mobile",
    "feed",
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
    # API versioning deprecation headers
    "core.middleware.deprecation.APIDeprecationMiddleware",
]

ROOT_URLCONF = "fynda.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "blog" / "templates"],
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

# ─── AWS S3 Storage ───────────────────────────────
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")
AWS_STORAGE_BUCKET_NAME = os.getenv("AWS_STORAGE_BUCKET_NAME", "outfi-media")
AWS_S3_REGION_NAME = os.getenv("AWS_S3_REGION_NAME", "us-east-1")
AWS_S3_FILE_OVERWRITE = False
AWS_DEFAULT_ACL = None  # Use bucket policy
AWS_S3_OBJECT_PARAMETERS = {
    "CacheControl": "max-age=86400",
}
AWS_QUERYSTRING_EXPIRE = 3600  # Signed URL expiry: 1 hour

# Use S3 for media uploads when credentials are configured
if AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY:
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
            "OPTIONS": {
                "bucket_name": AWS_STORAGE_BUCKET_NAME,
                "region_name": AWS_S3_REGION_NAME,
                "default_acl": None,
                "querystring_auth": True,  # Signed URLs for security
                "file_overwrite": False,
                "object_parameters": AWS_S3_OBJECT_PARAMETERS,
            },
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }
    MEDIA_URL = f"https://{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/"

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
        # Image/OCR endpoint limits (dev — more generous for testing)
        "image_upload_anon": "20/hour",
        "image_upload_user": "60/hour",
        "remove_bg_anon": "10/hour",
        "remove_bg_user": "30/hour",
        "image_burst": "5/minute",
    },
    "EXCEPTION_HANDLER": "core.exceptions.handlers.fynda_exception_handler",
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

# Celery Beat Schedule — automated blog generation every 2 hours
from celery.schedules import crontab
CELERY_BEAT_SCHEDULE = {
    # "generate-blog-post": {
    #     "task": "blog.generate_blog_post",
    #     "schedule": crontab(minute=0),  # Disabled — re-enable when ready
    # },
}

# Cache Configuration
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

# IndexNow Key for automated search engine indexing (Bing, Yandex, DuckDuckGo)
INDEXNOW_KEY = os.environ.get("INDEXNOW_KEY", "546739fd9e48406791555cb49282bb77")

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
        "mobile": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
        "image_search": {
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
GEMINI_API_KEY = config.apis.gemini_api_key
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
# EMAIL CONFIGURATION - AWS SES (from config)
# =============================================================================
EMAIL_BACKEND = config.email.backend
EMAIL_HOST = config.email.host
EMAIL_PORT = config.email.port
EMAIL_USE_TLS = config.email.use_tls
EMAIL_HOST_USER = config.email.user
EMAIL_HOST_PASSWORD = config.email.password
DEFAULT_FROM_EMAIL = config.email.from_email
SITE_URL = config.email.site_url

# =============================================================================
# JAZZMIN - MODERN ADMIN UI
# =============================================================================
JAZZMIN_SETTINGS = {
    # Title on the login screen
    "site_title": "Outfi Editorial",

    # Title on the brand (top left)
    "site_header": "Outfi",

    # Title on the browser tab
    "site_brand": "Outfi",

    # Welcome text on the login page
    "welcome_sign": "Welcome to Outfi Editorial",

    # Copyright on the footer
    "copyright": "Outfi",

    # Search models
    "search_model": ["blog.Post", "users.User"],

    # Field name on user model for avatar
    "user_avatar": None,

    ############
    # Top Menu #
    ############
    "topmenu_links": [
        {"name": "Dashboard", "url": "admin:index", "permissions": ["auth.view_user"]},
        {"name": "View Blog", "url": "/blog/", "new_window": True},
        {"name": "Visit Outfi", "url": config.email.site_url, "new_window": True},
    ],

    #############
    # Side Menu #
    #############
    "show_sidebar": True,
    "navigation_expanded": True,
    "hide_apps": [
        "auth",              # Groups — not needed for editorial
        "deals",             # Backend-only
        "feed",              # Managed via API
        "token_blacklist",   # JWT internals
        "mobile",            # Mobile API
    ],
    "hide_models": [
        "blog.ContentSection",  # Managed inline on Post
        "blog.ProductCard",     # Managed inline on Post
    ],

    # Ordered side menu
    "order_with_respect_to": [
        "blog",
        "blog.Post",
        "blog.Category",
        "blog.Tag",
        "emails",
        "emails.Campaign",
        "emails.CampaignSend",
        "emails.Subscriber",
        "users",
        "users.User",
    ],

    # Custom icons
    "icons": {
        "auth": "fas fa-users-cog",
        "auth.user": "fas fa-user",
        "auth.Group": "fas fa-users",
        "blog": "fas fa-feather-alt",
        "blog.Post": "fas fa-newspaper",
        "blog.Category": "fas fa-folder-open",
        "blog.Tag": "fas fa-tag",
        "blog.ContentSection": "fas fa-layer-group",
        "blog.ProductCard": "fas fa-shopping-bag",
        "users": "fas fa-users",
        "users.User": "fas fa-user-circle",
        "emails": "fas fa-envelope-open-text",
        "emails.Subscriber": "fas fa-at",
        "emails.Campaign": "fas fa-paper-plane",
        "emails.CampaignSend": "fas fa-chart-bar",
        "deals": "fas fa-percent",
    },

    # Default icon for apps not specified above
    "default_icon_parents": "fas fa-folder",
    "default_icon_children": "fas fa-circle",

    #################
    # Related Modal #
    #################
    "related_modal_active": True,

    #############
    # UI Tweaks #
    #############
    "custom_css": "admin/css/outfi_admin.css",
    "custom_js": None,
    "use_google_fonts_cdn": True,
    "show_ui_builder": False,

    # Change view — collapsible is best for long blog post forms
    "changeform_format": "collapsible",
    "changeform_format_overrides": {
        "blog.post": "collapsible",
        "emails.campaign": "horizontal_tabs",
    },
}

# Jazzmin UI tweaks — dark Outfi theme with pink accent
JAZZMIN_UI_TWEAKS = {
    "navbar_small_text": False,
    "footer_small_text": True,
    "body_small_text": False,
    "brand_small_text": False,
    "brand_colour": "navbar-dark",
    "accent": "accent-pink",
    "navbar": "navbar-dark",
    "no_navbar_border": True,
    "navbar_fixed": True,
    "layout_boxed": False,
    "footer_fixed": False,
    "sidebar_fixed": True,
    "sidebar": "sidebar-dark-pink",
    "sidebar_nav_small_text": False,
    "sidebar_disable_expand": False,
    "sidebar_nav_child_indent": True,
    "sidebar_nav_compact_style": False,
    "sidebar_nav_legacy_style": False,
    "sidebar_nav_flat_style": False,
    "theme": "darkly",
    "dark_mode_theme": "darkly",
    "button_classes": {
        "primary": "btn-outline-primary",
        "secondary": "btn-outline-secondary",
        "info": "btn-outline-info",
        "warning": "btn-warning",
        "danger": "btn-danger",
        "success": "btn-success",
    },
}

# Log configuration status on startup
config.log_status()

