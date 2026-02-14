"""
Core App Configuration
======================

Runs startup config validation when Django initializes.
"""

from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = "core"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        from core.config import validate_config_on_startup
        validate_config_on_startup()
