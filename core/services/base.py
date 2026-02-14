"""
Base Service
=============

Foundation for all service classes. Provides standardised
logger, transaction helper, and request-ID context.
"""

import logging
import uuid
from functools import wraps
from django.db import transaction


class BaseService:
    """
    All service classes inherit from this.

    Subclass example::

        class UserService(BaseService):
            @classmethod
            def authenticate_oauth(cls, provider, user_info):
                ...

    Features:
        - ``cls.logger`` — pre-configured logger using the subclass module name
        - ``cls.atomic()`` — shortcut for ``transaction.atomic()``
        - ``cls.generate_request_id()`` — opaque ID for request tracing
    """

    logger: logging.Logger = logging.getLogger(__name__)

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Each subclass gets its own logger named after its module
        cls.logger = logging.getLogger(cls.__module__)

    @staticmethod
    def atomic():
        """Shortcut for ``django.db.transaction.atomic()``."""
        return transaction.atomic()

    @staticmethod
    def generate_request_id() -> str:
        """Generate a short opaque request ID for tracing."""
        return uuid.uuid4().hex[:12]
