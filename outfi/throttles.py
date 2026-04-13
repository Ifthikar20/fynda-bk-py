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


class AuthLoginThrottle(SimpleRateThrottle):
    """
    Rate limit login/register attempts to prevent brute-force attacks.
    Uses client IP as the cache key. Configured via DEFAULT_THROTTLE_RATES['auth'].
    """
    scope = "auth"

    def get_cache_key(self, request, view):
        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }


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
    Per-user daily + monthly quota for Gemini image search.

    Limits (daily is the binding constraint; monthly is a safety net):
        Free users:    3/day,   45/month   (enough to try, not enough to abuse)
        Premium users: 25/day,  500/month  ($10/mo → $0.02/search budget)

    Gemini 2.5 Flash costs ~$0.001–$0.0025/call.
    Premium monthly revenue: $10 → budget 500 calls ($1.25 worst-case cost, 87% margin).
    Free users get enough to try the feature but must upgrade for regular use.
    """
    scope = "image_daily"
    rate = "100/day"  # Placeholder — actual limits enforced in allow_request

    # Daily caps
    FREE_DAILY_LIMIT = 3
    PREMIUM_DAILY_LIMIT = 25

    # Monthly caps (safety net — daily limit is the real constraint)
    # Free:    3/day × 15 days = 45 (generous buffer)
    # Premium: 25/day × 20 days = 500 (allows heavy use without exceeding $1.25 AI cost)
    FREE_MONTHLY_LIMIT = 45
    PREMIUM_MONTHLY_LIMIT = 500

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
        monthly_limit = self.PREMIUM_MONTHLY_LIMIT if is_premium else self.FREE_MONTHLY_LIMIT

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

        # Check monthly count (safety net for cost control)
        period_stats = APIUsageLog.get_period_stats(
            request.user, days=30, endpoint="image_search"
        )
        monthly_count = period_stats["count"]

        if monthly_count >= monthly_limit:
            self.message = (
                f"Monthly limit reached ({monthly_limit} searches/month). "
                "Your quota resets soon."
            )
            logger.warning(
                f"QUOTA BLOCK (monthly): user={request.user.email} "
                f"count={monthly_count}/{monthly_limit} "
                f"cost=${period_stats['total_cost']}"
            )
            return False

        # Attach quota status to request so the view can include it in the response
        daily_remaining = daily_limit - daily_count
        monthly_remaining = monthly_limit - monthly_count
        request._quota_status = {
            "daily_used": daily_count,
            "daily_limit": daily_limit,
            "daily_remaining": daily_remaining,
            "monthly_used": monthly_count,
            "monthly_limit": monthly_limit,
            "monthly_remaining": monthly_remaining,
            "is_premium": is_premium,
        }

        # Log when quota is running low
        if daily_remaining <= 1 or monthly_remaining <= 10:
            logger.info(
                f"QUOTA LOW: user={request.user.email} "
                f"daily={daily_count}/{daily_limit} "
                f"monthly={monthly_count}/{monthly_limit} "
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
