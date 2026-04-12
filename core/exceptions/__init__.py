"""
core.exceptions — Re-exports for convenient imports.

Usage::

    from core.exceptions import ValidationError, NotFoundError, ConflictError
    from core.exceptions import outfi_exception_handler
"""

from .base import (
    OutfiError,
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

from .handlers import outfi_exception_handler

__all__ = [
    # Base
    "OutfiError",
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
    "outfi_exception_handler",
]
