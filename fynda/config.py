"""
Configuration Layer
===================

Centralized, type-safe configuration management for all environment variables.
This replaces scattered os.getenv() calls throughout the codebase.

Usage:
    from fynda.config import config
    
    # Access API keys
    api_key = config.apis.rapidapi_key
    
    # Access database settings
    db_url = config.database.url
    
    # Check if in production
    if config.is_production:
        ...

Future-Proofing:
    This module is designed to be extended with:
    - AWS Secrets Manager / HashiCorp Vault integration
    - Configuration hot-reloading
    - Encrypted at-rest secrets
"""

import os
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration Classes
# =============================================================================

@dataclass(frozen=True)
class DatabaseConfig:
    """Database connection settings."""
    url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///db.sqlite3"))
    name: str = field(default_factory=lambda: os.getenv("DB_NAME", "db.sqlite3"))
    host: str = field(default_factory=lambda: os.getenv("DB_HOST", "localhost"))
    port: int = field(default_factory=lambda: int(os.getenv("DB_PORT", "5432")))
    user: str = field(default_factory=lambda: os.getenv("DB_USER", ""))
    password: str = field(default_factory=lambda: os.getenv("DB_PASSWORD", ""))
    
    @property
    def is_sqlite(self) -> bool:
        return "sqlite" in self.url.lower()


@dataclass(frozen=True)
class RedisConfig:
    """Redis/Celery broker settings."""
    url: str = field(default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    broker_url: str = field(default_factory=lambda: os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"))
    result_backend: str = field(default_factory=lambda: os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0"))


@dataclass(frozen=True)
class APIKeysConfig:
    """All external API keys - single source of truth."""
    
    # RapidAPI (Pinterest, Instagram, TikTok, Facebook)
    rapidapi_key: str = field(default_factory=lambda: os.getenv("RAPIDAPI_KEY", ""))
    
    # eBay
    ebay_app_id: str = field(default_factory=lambda: os.getenv("EBAY_APP_ID", ""))
    ebay_cert_id: str = field(default_factory=lambda: os.getenv("EBAY_CERT_ID", ""))
    
    # Best Buy
    bestbuy_api_key: str = field(default_factory=lambda: os.getenv("BESTBUY_API_KEY", ""))
    
    # OpenAI
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    
    # CJ Affiliate
    cj_api_token: str = field(default_factory=lambda: os.getenv("CJ_AFFILIATE_API_TOKEN", ""))
    cj_website_id: str = field(default_factory=lambda: os.getenv("CJ_WEBSITE_ID", ""))
    
    # Rakuten
    rakuten_api_token: str = field(default_factory=lambda: os.getenv("RAKUTEN_API_TOKEN", ""))
    rakuten_site_id: str = field(default_factory=lambda: os.getenv("RAKUTEN_SITE_ID", ""))
    
    # ShareASale
    shareasale_affiliate_id: str = field(default_factory=lambda: os.getenv("SHAREASALE_AFFILIATE_ID", ""))
    shareasale_api_token: str = field(default_factory=lambda: os.getenv("SHAREASALE_API_TOKEN", ""))
    shareasale_api_secret: str = field(default_factory=lambda: os.getenv("SHAREASALE_API_SECRET", ""))
    
    def is_configured(self, service: str) -> bool:
        """Check if a service has its API keys configured."""
        checks = {
            "rapidapi": bool(self.rapidapi_key),
            "ebay": bool(self.ebay_app_id and self.ebay_cert_id),
            "bestbuy": bool(self.bestbuy_api_key),
            "openai": bool(self.openai_api_key),
            "cj": bool(self.cj_api_token and self.cj_website_id),
            "rakuten": bool(self.rakuten_api_token and self.rakuten_site_id),
            "shareasale": bool(self.shareasale_affiliate_id and self.shareasale_api_token),
        }
        return checks.get(service.lower(), False)
    
    @property
    def configured_services(self) -> List[str]:
        """Return list of services with valid API keys."""
        services = ["rapidapi", "ebay", "bestbuy", "openai", "cj", "rakuten", "shareasale"]
        return [s for s in services if self.is_configured(s)]


@dataclass(frozen=True)
class SecurityConfig:
    """Security-related settings."""
    secret_key: str = field(default_factory=lambda: os.getenv("SECRET_KEY", "django-insecure-dev-key-change-in-production"))
    allowed_hosts: List[str] = field(default_factory=lambda: os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(","))
    cors_origins: List[str] = field(default_factory=lambda: os.getenv(
        "CORS_ORIGINS", 
        "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173"
    ).split(","))
    csrf_trusted_origins: List[str] = field(default_factory=lambda: os.getenv(
        "CSRF_TRUSTED_ORIGINS",
        "http://localhost:3000,http://localhost:5173"
    ).split(","))
    
    # Mobile API key for Flutter app authentication
    mobile_api_key: str = field(default_factory=lambda: os.getenv("FYNDA_MOBILE_API_KEY", ""))
    
    @property
    def is_secure_key(self) -> bool:
        """Check if using a proper secret key."""
        return "insecure" not in self.secret_key.lower() and len(self.secret_key) >= 50


@dataclass(frozen=True)
class MLServiceConfig:
    """ML Service connection settings."""
    url: str = field(default_factory=lambda: os.getenv("ML_SERVICE_URL", "http://127.0.0.1:8001"))
    timeout: int = field(default_factory=lambda: int(os.getenv("ML_SERVICE_TIMEOUT", "30")))
    
    @property
    def visual_search_endpoint(self) -> str:
        return f"{self.url}/api/visual-search"
    
    @property
    def index_product_endpoint(self) -> str:
        return f"{self.url}/api/index-product"


@dataclass(frozen=True)
class AppConfig:
    """Main application configuration - aggregates all config sections."""
    
    # Environment
    environment: str = field(default_factory=lambda: os.getenv("DJANGO_ENV", "development"))
    debug: bool = field(default_factory=lambda: os.getenv("DEBUG", "True").lower() == "true")
    
    # Sub-configurations
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    redis: RedisConfig = field(default_factory=RedisConfig)
    apis: APIKeysConfig = field(default_factory=APIKeysConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    ml_service: MLServiceConfig = field(default_factory=MLServiceConfig)
    
    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"
    
    @property
    def is_development(self) -> bool:
        return self.environment.lower() == "development"
    
    def validate(self) -> List[str]:
        """
        Validate configuration and return list of warnings/errors.
        Call this on startup to catch misconfigurations early.
        """
        issues = []
        
        if self.is_production:
            if not self.security.is_secure_key:
                issues.append("CRITICAL: Using insecure SECRET_KEY in production!")
            if self.debug:
                issues.append("WARNING: DEBUG=True in production!")
            if not self.apis.configured_services:
                issues.append("WARNING: No external API services configured")
        
        if not self.apis.rapidapi_key:
            issues.append("INFO: RapidAPI key not configured (Pinterest, TikTok, Instagram disabled)")
        
        return issues
    
    def log_status(self) -> None:
        """Log configuration status on startup."""
        logger.info(f"Environment: {self.environment}")
        logger.info(f"Debug: {self.debug}")
        logger.info(f"Configured APIs: {', '.join(self.apis.configured_services) or 'None'}")
        
        for issue in self.validate():
            if issue.startswith("CRITICAL"):
                logger.critical(issue)
            elif issue.startswith("WARNING"):
                logger.warning(issue)
            else:
                logger.info(issue)


# =============================================================================
# Singleton Instance
# =============================================================================

@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    """
    Get the singleton configuration instance.
    Uses lru_cache to ensure single instance across the application.
    """
    return AppConfig()


# Convenience alias
config = get_config()


# =============================================================================
# Django Settings Helpers
# =============================================================================

def get_secret_key() -> str:
    """Get Django SECRET_KEY from config."""
    return config.security.secret_key


def get_allowed_hosts() -> List[str]:
    """Get ALLOWED_HOSTS from config."""
    return config.security.allowed_hosts


def get_debug() -> bool:
    """Get DEBUG setting from config."""
    return config.debug


def get_database_config() -> dict:
    """
    Get database configuration in Django format.
    Returns dict suitable for DATABASES setting.
    """
    if config.database.is_sqlite:
        return {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": config.database.name,
        }
    
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config.database.name,
        "HOST": config.database.host,
        "PORT": config.database.port,
        "USER": config.database.user,
        "PASSWORD": config.database.password,
    }
