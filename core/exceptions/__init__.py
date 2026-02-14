"""
core.exceptions — Re-exports for convenient imports.

Usage::

    from core.exceptions import ValidationError, NotFoundError, ConflictError
    from core.exceptions import fynda_exception_handler
"""

from .base import (
    FyndaError,
    ServiceError,
    VendorAPIError,
    VendorTimeoutError,
    VendorRateLimitError,
    MLServiceError,
    ValidationError,
    NotFoundError,
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    RateLimitError,
    ConfigurationError,
    PermissionError,
)

from .handlers import fynda_exception_handler

__all__ = [
    # Base
    "FyndaError",
    # Service / vendor
    "ServiceError",
    "VendorAPIError",
    "VendorTimeoutError",
    "VendorRateLimitError",
    "MLServiceError",
    # Client
    "ValidationError",
    "NotFoundError",
    "AuthenticationError",
    "AuthorizationError",
    "ConflictError",
    "RateLimitError",
    # Config
    "ConfigurationError",
    # Aliases
    "PermissionError",
    # Handler
    "fynda_exception_handler",
]
