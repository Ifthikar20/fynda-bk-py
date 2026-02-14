"""
API Deprecation Middleware
==========================

Adds a ``Deprecation: true`` header and a ``Sunset`` header to responses
for non-versioned ``/api/`` requests, nudging clients toward ``/api/v1/``.

Enable in MIDDLEWARE after all other middleware.
"""

from django.utils.deprecation import MiddlewareMixin


class APIDeprecationMiddleware(MiddlewareMixin):
    """
    For any request matching /api/* that does NOT already have a version
    prefix (/api/v1/, /api/v2/, etc.), inject deprecation headers.

    Headers added:
        Deprecation: true
        Sunset: 2026-06-01T00:00:00Z
        X-API-Warn: Use /api/v1/ prefix. Unversioned /api/ will be removed.
    """

    # Paths that are versioned (skip these)
    VERSION_PREFIXES = ("/api/v1/", "/api/v2/")

    # Sunset date — adjust when you plan to drop unversioned routes
    SUNSET_DATE = "2026-06-01T00:00:00Z"

    def process_response(self, request, response):
        path = request.path

        # Only target /api/ routes that aren't already versioned
        if path.startswith("/api/") and not any(path.startswith(p) for p in self.VERSION_PREFIXES):
            response["Deprecation"] = "true"
            response["Sunset"] = self.SUNSET_DATE
            response["X-API-Warn"] = (
                "Use /api/v1/ prefix. "
                "Unversioned /api/ endpoints are deprecated and will be removed."
            )

        return response
