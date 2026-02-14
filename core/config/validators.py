"""
Configuration Validators
========================

Startup validation for the Fynda configuration layer.
Raises ImproperlyConfigured for critical issues in production,
logs warnings in development.

Called automatically via core.apps.CoreConfig.ready().
"""

import logging
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger(__name__)


def validate_config_on_startup():
    """
    Validate all configuration on application startup.

    Production:
        CRITICAL issues raise ImproperlyConfigured (hard failure).
        WARNING issues are logged but don't block startup.

    Development:
        All issues are logged as warnings/info.
    """
    from fynda.config import config

    issues = config.validate()

    if not issues:
        logger.info("Configuration validated — no issues found")
        config.log_status()
        return

    critical_issues = [i for i in issues if i.startswith("CRITICAL")]
    warning_issues = [i for i in issues if i.startswith("WARNING")]
    info_issues = [i for i in issues if i.startswith("INFO")]

    # Log everything regardless of environment
    for issue in info_issues:
        logger.info(issue)
    for issue in warning_issues:
        logger.warning(issue)
    for issue in critical_issues:
        logger.critical(issue)

    # In production, critical issues are fatal
    if config.is_production and critical_issues:
        raise ImproperlyConfigured(
            "Configuration validation failed in production:\n"
            + "\n".join(f"  • {i}" for i in critical_issues)
        )

    config.log_status()
