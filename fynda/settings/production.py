"""
Production Settings - Security Hardened
"""

from .base import *
from fynda.config import config, get_database_config

DEBUG = False
SECRET_KEY = config.security.secret_key
ALLOWED_HOSTS = config.security.allowed_hosts

# PostgreSQL for production (from config, with production overrides)
DATABASES = get_database_config()
DATABASES["default"]["CONN_MAX_AGE"] = 60  # Persistent connections
DATABASES["default"]["OPTIONS"] = {
    "sslmode": os.getenv("DB_SSL_MODE", "prefer"),
}

# Redis cache for production (from config)
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": config.redis.url,
    }
}

# =============================================================================
# SECURITY SETTINGS - PRODUCTION
# =============================================================================

# HTTPS/SSL Security
SECURE_SSL_REDIRECT = True  # Force HTTPS
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# HSTS (HTTP Strict Transport Security)
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Cookie Security
SESSION_COOKIE_SECURE = True  # Only send cookies over HTTPS
SESSION_COOKIE_HTTPONLY = True  # Prevent JavaScript access
SESSION_COOKIE_SAMESITE = "Lax"  # CSRF protection
SESSION_COOKIE_AGE = 86400  # 24 hours

CSRF_COOKIE_SECURE = True  # Only send CSRF over HTTPS
CSRF_COOKIE_HTTPONLY = True  # Prevent JavaScript access
CSRF_COOKIE_SAMESITE = "Lax"

# XSS and Content Security
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"  # Prevent clickjacking

# Content Security Policy (via middleware)
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = ("'self'", "'unsafe-inline'", "https://cdn.jsdelivr.net")
CSP_STYLE_SRC = ("'self'", "'unsafe-inline'", "https://fonts.googleapis.com")
CSP_FONT_SRC = ("'self'", "https://fonts.gstatic.com")
CSP_IMG_SRC = ("'self'", "data:", "https:", "blob:")

# Referrer Policy
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

# =============================================================================
# CORS - Strict Production Settings (from config + hardcoded essentials)
# =============================================================================
CORS_ALLOW_ALL_ORIGINS = False

# Always allow our own domains + any extras from config
_HARDCODED_ORIGINS = [
    "https://fynda.shop",
    "https://www.fynda.shop",
    "https://api.fynda.shop",
]
CORS_ALLOWED_ORIGINS = list(set(_HARDCODED_ORIGINS + config.security.cors_origins))
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
]

# =============================================================================
# RATE LIMITING - Stricter for Production
# =============================================================================
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {
    "anon": "60/minute",  # 60 requests per minute for anonymous
    "user": "300/minute",  # 300 requests per minute for authenticated
    "burst": "10/second",  # Burst protection
}

# =============================================================================
# LOGGING - Production (Console-only for Docker)
# =============================================================================
# In Docker, logs are captured from stdout/stderr by the container runtime
LOGGING["root"]["handlers"] = ["console"]
LOGGING["root"]["level"] = "WARNING"
LOGGING["handlers"]["console"]["level"] = "WARNING"

# =============================================================================
# JWT - Shorter Tokens for Security (from config)
# =============================================================================
from datetime import timedelta
SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"] = timedelta(minutes=30)
SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"] = timedelta(days=1)
SIMPLE_JWT["SIGNING_KEY"] = config.security.secret_key

# =============================================================================
# STATIC/MEDIA - Production CDN
# =============================================================================
STATIC_ROOT = os.getenv("STATIC_ROOT", BASE_DIR / "staticfiles")
STATICFILES_STORAGE = "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"

# If using S3/CloudFront:
# AWS_STORAGE_BUCKET_NAME = os.getenv("AWS_STORAGE_BUCKET_NAME")
# AWS_S3_CUSTOM_DOMAIN = os.getenv("AWS_CLOUDFRONT_DOMAIN")
# STATICFILES_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"

