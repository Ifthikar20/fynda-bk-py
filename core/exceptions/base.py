"""
Fynda Exception Hierarchy
=========================

Domain-specific exceptions for structured error handling across the platform.
Replaces bare ``except Exception`` with semantically meaningful error types.

Usage::

    from core.exceptions import ServiceError, ValidationError, NotFoundError

    # In a service:
    raise ServiceError("Amazon API timed out", vendor="amazon")

    # In a view:
    raise NotFoundError("Storyboard not found", resource="storyboard")
"""

from rest_framework import status


# =============================================================================
# Base Exception
# =============================================================================

class FyndaError(Exception):
    """Base exception for all Fynda application errors."""

    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code = "server_error"

    def __init__(self, message="An unexpected error occurred", **kwargs):
        self.message = message
        self.details = kwargs
        super().__init__(message)

    def to_dict(self):
        result = {
            "error": self.error_code,
            "message": self.message,
        }
        if self.details:
            result["detail"] = self.details
        return result


# =============================================================================
# Service Errors (external dependencies)
# =============================================================================

class ServiceError(FyndaError):
    """External service or API call failed."""

    status_code = status.HTTP_502_BAD_GATEWAY
    error_code = "service_error"

    def __init__(self, message="External service unavailable", vendor=None, **kwargs):
        if vendor:
            kwargs["vendor"] = vendor
        super().__init__(message, **kwargs)


class VendorAPIError(ServiceError):
    """Vendor-specific API error (timeout, auth, rate limit)."""

    error_code = "vendor_api_error"

    def __init__(self, message, vendor, **kwargs):
        super().__init__(message, vendor=vendor, **kwargs)


class VendorTimeoutError(VendorAPIError):
    """Vendor API timed out."""

    status_code = status.HTTP_504_GATEWAY_TIMEOUT
    error_code = "vendor_timeout"


class VendorRateLimitError(VendorAPIError):
    """Vendor API rate limit exceeded."""

    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    error_code = "vendor_rate_limit"


class MLServiceError(ServiceError):
    """ML service unreachable or returned an error."""

    error_code = "ml_service_error"

    def __init__(self, message="ML service unavailable", **kwargs):
        super().__init__(message, vendor="ml_service", **kwargs)


# =============================================================================
# Client Errors
# =============================================================================

class ValidationError(FyndaError):
    """Invalid input from the client."""

    status_code = status.HTTP_400_BAD_REQUEST
    error_code = "validation_error"

    def __init__(self, message="Invalid request data", field=None, **kwargs):
        if field:
            kwargs["field"] = field
        super().__init__(message, **kwargs)


class NotFoundError(FyndaError):
    """Requested resource does not exist."""

    status_code = status.HTTP_404_NOT_FOUND
    error_code = "not_found"

    def __init__(self, message="Resource not found", resource=None, **kwargs):
        if resource:
            kwargs["resource"] = resource
        super().__init__(message, **kwargs)


class AuthenticationError(FyndaError):
    """Authentication failed."""

    status_code = status.HTTP_401_UNAUTHORIZED
    error_code = "authentication_error"

    def __init__(self, message="Authentication required", **kwargs):
        super().__init__(message, **kwargs)


class AuthorizationError(FyndaError):
    """User lacks permission for this action."""

    status_code = status.HTTP_403_FORBIDDEN
    error_code = "permission_denied"

    def __init__(self, message="You do not have permission", **kwargs):
        super().__init__(message, **kwargs)


class ConflictError(FyndaError):
    """Resource conflict (duplicate, version mismatch, etc.)."""

    status_code = status.HTTP_409_CONFLICT
    error_code = "conflict"

    def __init__(self, message="Resource conflict", resource=None, **kwargs):
        if resource:
            kwargs["resource"] = resource
        super().__init__(message, **kwargs)


class RateLimitError(FyndaError):
    """Client-side rate limit exceeded."""

    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    error_code = "rate_limit"

    def __init__(self, message="Rate limit exceeded", **kwargs):
        super().__init__(message, **kwargs)


# =============================================================================
# Configuration Errors
# =============================================================================

class ConfigurationError(FyndaError):
    """Missing or invalid configuration (env vars, settings)."""

    error_code = "configuration_error"

    def __init__(self, message="Configuration error", setting=None, **kwargs):
        if setting:
            kwargs["setting"] = setting
        super().__init__(message, **kwargs)


# Backward-compatible alias
PermissionError = AuthorizationError
