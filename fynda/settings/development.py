"""
Development Settings
"""

from .base import *
from dotenv import load_dotenv

load_dotenv()

DEBUG = True
SECRET_KEY = os.getenv("SECRET_KEY", "django-insecure-dev-key-change-in-production")
ALLOWED_HOSTS = ["*"]

# Use SQLite for development (easy setup)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# CORS - Allow all for local development
CORS_ALLOW_ALL_ORIGINS = True

# Cache - Use local memory for development
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

# Disable rate limiting in development
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {
    "anon": "10000/hour",
    "user": "10000/hour",
}
