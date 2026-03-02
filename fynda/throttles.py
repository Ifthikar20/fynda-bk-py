"""
Custom DRF Throttle Classes for Image/OCR Endpoints

Provides hard per-endpoint rate limiting for expensive image processing
operations (ML inference, background removal, etc.).

Throttle scopes are configured in settings via DEFAULT_THROTTLE_RATES:
    "image_upload_anon": "5/hour"
    "image_upload_user": "20/hour"
    "remove_bg_anon": "3/hour"
    "remove_bg_user": "15/hour"
    "image_burst": "2/minute"
"""

from rest_framework.throttling import SimpleRateThrottle


class ImageUploadAnonThrottle(SimpleRateThrottle):
    """
    Hourly limit for anonymous users uploading images for visual search.
    Uses client IP as the cache key.
    """
    scope = "image_upload_anon"

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            return None  # Skip — let ImageUploadUserThrottle handle auth users
        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }


class ImageUploadUserThrottle(SimpleRateThrottle):
    """
    Hourly limit for authenticated users uploading images for visual search.
    Uses user ID as the cache key.
    """
    scope = "image_upload_user"

    def get_cache_key(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return None  # Skip — let ImageUploadAnonThrottle handle anon users
        return self.cache_format % {
            "scope": self.scope,
            "ident": request.user.pk,
        }


class RemoveBgAnonThrottle(SimpleRateThrottle):
    """
    Hourly limit for anonymous users requesting background removal.
    Tighter than image upload because rembg is very CPU-intensive.
    """
    scope = "remove_bg_anon"

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            return None
        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }


class RemoveBgUserThrottle(SimpleRateThrottle):
    """
    Hourly limit for authenticated users requesting background removal.
    """
    scope = "remove_bg_user"

    def get_cache_key(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return None
        return self.cache_format % {
            "scope": self.scope,
            "ident": request.user.pk,
        }


class ImageBurstThrottle(SimpleRateThrottle):
    """
    Per-minute burst protection for ALL image endpoints.
    Prevents rapid-fire uploads regardless of auth status.
    Uses IP for anon, user ID for authenticated.
    """
    scope = "image_burst"

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)
        return self.cache_format % {
            "scope": self.scope,
            "ident": ident,
        }

