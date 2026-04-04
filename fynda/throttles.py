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
    Per-user daily + bi-weekly quota for Gemini image search.

    Limits:
        Free users:    3/day,   20/bi-week
        Premium users: 25/day,  250/bi-week ($4.99/2wk ≈ $0.02/search budget)

    Gemini 2.5 Flash costs ~$0.0025/call.
    Premium 2-week revenue: $4.99 → budget ~250 calls ($0.625 cost, 87% margin).
    Free users get enough to try the feature but must upgrade for regular use.
    """
    scope = "image_daily"
    rate = "100/day"  # Placeholder — actual limits enforced in allow_request

    # Daily caps
    FREE_DAILY_LIMIT = 3
    PREMIUM_DAILY_LIMIT = 25

    # Bi-weekly caps (aligned with $4.99/2-week subscription)
    FREE_BIWEEKLY_LIMIT = 20
    PREMIUM_BIWEEKLY_LIMIT = 250

    def allow_request(self, request, view):
        from mobile.models import APIUsageLog
        import logging

        logger = logging.getLogger("image_search")

        # Anonymous users cannot use image search
        if not request.user or not request.user.is_authenticated:
            self.message = "Please sign in to use image search."
            return False

        is_premium = self._is_premium(request.user)
        daily_limit = self.PREMIUM_DAILY_LIMIT if is_premium else self.FREE_DAILY_LIMIT
        biweekly_limit = self.PREMIUM_BIWEEKLY_LIMIT if is_premium else self.FREE_BIWEEKLY_LIMIT

        # Check daily count
        daily_count = APIUsageLog.get_daily_count(
            user=request.user, endpoint="image_search"
        )

        if daily_count >= daily_limit:
            remaining_msg = f" Upgrade to Premium for {self.PREMIUM_DAILY_LIMIT}/day." if not is_premium else ""
            self.message = (
                f"Daily limit reached ({daily_limit}/day).{remaining_msg} "
                "Try again tomorrow."
            )
            logger.warning(
                f"QUOTA BLOCK (daily): user={request.user.email} "
                f"count={daily_count}/{daily_limit} premium={is_premium}"
            )
            return False

        # Check bi-weekly count (cost control aligned with subscription)
        period_stats = APIUsageLog.get_period_stats(
            request.user, days=14, endpoint="image_search"
        )
        biweekly_count = period_stats["count"]

        if biweekly_count >= biweekly_limit:
            self.message = (
                f"Bi-weekly limit reached ({biweekly_limit} searches per 2 weeks). "
                "Your quota resets soon."
            )
            logger.warning(
                f"QUOTA BLOCK (biweekly): user={request.user.email} "
                f"count={biweekly_count}/{biweekly_limit} "
                f"cost=${period_stats['total_cost']}"
            )
            return False

        # Log remaining quota for proactive monitoring
        daily_remaining = daily_limit - daily_count
        biweekly_remaining = biweekly_limit - biweekly_count
        if daily_remaining <= 2 or biweekly_remaining <= 10:
            logger.info(
                f"QUOTA LOW: user={request.user.email} "
                f"daily={daily_count}/{daily_limit} "
                f"biweekly={biweekly_count}/{biweekly_limit} "
                f"cost=${period_stats['total_cost']}"
            )

        return True

    def _is_premium(self, user):
        from payments.models import Subscription
        try:
            return Subscription.objects.get(user=user).is_premium
        except Subscription.DoesNotExist:
            return False

    def get_cache_key(self, request, view):
        return None

    def wait(self):
        """Seconds until midnight UTC."""
        from django.utils import timezone
        import datetime
        now = timezone.now()
        midnight = (now + datetime.timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        return (midnight - now).total_seconds()
