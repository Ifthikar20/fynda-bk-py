"""
Backward-compatibility shim.

All exceptions have moved to ``core.exceptions``.
This module re-exports them so existing ``from fynda.exceptions import …``
statements continue to work.

Prefer::

    from core.exceptions import ValidationError, NotFoundError
"""

# Re-export everything from the canonical location
from core.exceptions import (  # noqa: F401
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
    fynda_exception_handler,
)
