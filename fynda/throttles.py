"""
Custom DRF Throttle Classes for Image/OCR Endpoints

Provides hard per-endpoint rate limiting for expensive image processing
operations (ML inference, background removal, etc.).

Throttle scopes are configured in settings via DEFAULT_THROTTLE_RATES:
    "image_upload_anon": "20/hour"
    "image_upload_user": "60/hour"
    "remove_bg_anon": "10/hour"
    "remove_bg_user": "30/hour"
    "image_burst": "5/minute"

Daily quotas enforced via DailyImageQuotaThrottle:
    - Anonymous: 30 image searches/day
    - Authenticated: 100 image searches/day
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


class DailyImageQuotaThrottle(SimpleRateThrottle):
    """
    Daily quota for image search endpoints — per USER ACCOUNT.

    We pay per usage regardless of IP, so tracking must be per login.
    Anonymous users are blocked entirely from expensive endpoints —
    they must sign in first.

    Limits:
        - Anonymous: BLOCKED (must login)
        - Authenticated: 100 image searches/day per account
    """
    scope = "image_daily"

    USER_DAILY_LIMIT = 100

    def allow_request(self, request, view):
        from mobile.models import APIUsageLog

        # Anonymous users cannot use image search — require login
        if not request.user or not request.user.is_authenticated:
            self.message = "Please sign in to use image search."
            return False

        # Count all usage for THIS USER today, regardless of IP
        count = APIUsageLog.get_daily_count(
            user=request.user, endpoint="image_search"
        )

        if count >= self.USER_DAILY_LIMIT:
            self.message = (
                f"Daily image search limit reached ({self.USER_DAILY_LIMIT}/day). "
                "Try again tomorrow."
            )
            return False
        return True

    def get_cache_key(self, request, view):
        return None  # Not used — we check the database directly

    def wait(self):
        """Seconds until midnight UTC."""
        from django.utils import timezone
        import datetime
        now = timezone.now()
        midnight = (now + datetime.timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        return (midnight - now).total_seconds()
