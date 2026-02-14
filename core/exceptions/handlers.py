"""
DRF Exception Handler
=====================

Custom exception handler that catches FyndaError subtypes and returns
consistent ``{error, message, details}`` JSON responses.

Registered in ``REST_FRAMEWORK["EXCEPTION_HANDLER"]``.
"""

import logging
from rest_framework.views import exception_handler as drf_exception_handler
from rest_framework.response import Response

from .base import FyndaError

logger = logging.getLogger(__name__)


def fynda_exception_handler(exc, context):
    """
    Custom DRF exception handler.

    - Catches any ``FyndaError`` subtype → structured JSON response.
    - Falls back to DRF's default handler for standard DRF exceptions.
    - Logs unhandled exceptions that slip through both layers.
    """

    # Handle our custom exceptions
    if isinstance(exc, FyndaError):
        logger.warning(
            "FyndaError [%s]: %s %s",
            exc.error_code,
            exc.message,
            exc.details or "",
        )
        return Response(
            exc.to_dict(),
            status=exc.status_code,
        )

    # Fall back to DRF default for everything else
    response = drf_exception_handler(exc, context)

    # If DRF didn't handle it (unexpected server error), log it
    if response is None:
        logger.exception("Unhandled exception in %s", context.get("view", "unknown"))

    return response
