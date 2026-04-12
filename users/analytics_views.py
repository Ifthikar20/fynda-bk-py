"""
Internal analytics dashboard.

Three endpoints, all staff-only, sharing one data builder:

  GET /internal/analytics/         → HTML dashboard (Django session auth)
  GET /internal/analytics/data/    → JSON for the HTML page (Django session auth)
  GET /api/auth/analytics/data/    → JSON for the Vue SPA (JWT bearer auth + analytics token)
  POST /api/auth/analytics/verify-pin/ → PIN verification, returns analytics session token

The HTML pair is mounted outside /api/ on purpose: APIGuardMiddleware treats
/api/internal/ as a honeypot path (see outfi/middleware/api_guard.py).

Security layers for the SPA analytics:
  1. JWT authentication (user must be logged in)
  2. IsAdminUser (user.is_staff must be True)
  3. Analytics session token (issued after PIN verification, 15-min TTL in Redis)
  4. Rate limiting on PIN attempts (5 per hour per user)
"""

import hashlib
import logging
import secrets
from datetime import timedelta

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET

from rest_framework import status
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)
User = get_user_model()

# Analytics session token TTL (seconds)
ANALYTICS_TOKEN_TTL = 900  # 15 minutes

# PIN attempt rate limiting
MAX_PIN_ATTEMPTS = 5
PIN_ATTEMPT_WINDOW = 3600  # 1 hour


def _hash_pin(pin):
    """Hash a PIN using SHA-256 with a static salt. Not bcrypt because
    the PIN space is small and we rate-limit attempts instead."""
    return hashlib.sha256(f"outfi_analytics_{pin}".encode()).hexdigest()


def _safe_count(qs):
    """Return .count() or 0 if the table doesn't exist yet (pre-migrate)."""
    try:
        return qs.count()
    except Exception:
        return 0


def build_analytics_payload():
    """
    Aggregate signup + engagement metrics. Pure function so it can be reused
    by the session-based JSON view and the DRF/JWT view.
    """
    now = timezone.now()
    day_ago = now - timedelta(days=1)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    users_qs = User.objects.all()

    total_users = _safe_count(users_qs)
    active_users = _safe_count(users_qs.filter(is_active=True))
    staff_users = _safe_count(users_qs.filter(is_staff=True))
    signups_24h = _safe_count(users_qs.filter(created_at__gte=day_ago))
    signups_7d = _safe_count(users_qs.filter(created_at__gte=week_ago))
    signups_30d = _safe_count(users_qs.filter(created_at__gte=month_ago))

    provider_rows = (
        users_qs.values("oauth_provider")
        .annotate(n=Count("id"))
        .order_by("-n")
    )
    by_provider = [
        {"provider": (row["oauth_provider"] or "email"), "count": row["n"]}
        for row in provider_rows
    ]

    daily_rows = (
        users_qs.filter(created_at__gte=month_ago)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(n=Count("id"))
        .order_by("day")
    )
    daily_map = {row["day"].isoformat(): row["n"] for row in daily_rows}
    daily_signups = []
    for i in range(30):
        d = (month_ago + timedelta(days=i)).date().isoformat()
        daily_signups.append({"date": d, "count": daily_map.get(d, 0)})

    engagement = {}
    try:
        from users.models import SearchHistory, SavedDeal
        engagement["searches_total"] = _safe_count(SearchHistory.objects.all())
        engagement["searches_7d"] = _safe_count(
            SearchHistory.objects.filter(created_at__gte=week_ago)
        )
        engagement["saved_deals_total"] = _safe_count(SavedDeal.objects.all())
    except Exception:
        pass

    try:
        from mobile.models import PriceAlert, DealAlert
        engagement["price_alerts_total"] = _safe_count(PriceAlert.objects.all())
        engagement["price_alerts_active"] = _safe_count(
            PriceAlert.objects.filter(is_active=True)
        )
        engagement["deal_alerts_total"] = _safe_count(DealAlert.objects.all())
    except Exception:
        pass

    # Individual user list for the dashboard table.
    # Capped at 500 to bound payload size. Staff-only + PIN-gated, so
    # emails are fine to return — but we still exclude sensitive fields
    # (password hash, analytics_pin hash, oauth_uid).
    try:
        user_rows = (
            users_qs.order_by("-created_at")
            .values(
                "id",
                "email",
                "first_name",
                "last_name",
                "oauth_provider",
                "is_active",
                "is_staff",
                "created_at",
                "last_login",
            )[:500]
        )
        users_list = [
            {
                "id": str(row["id"]),
                "email": row["email"],
                "name": f"{row['first_name']} {row['last_name']}".strip(),
                "provider": row["oauth_provider"] or "email",
                "is_active": row["is_active"],
                "is_staff": row["is_staff"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                "last_login": row["last_login"].isoformat() if row["last_login"] else None,
            }
            for row in user_rows
        ]
    except Exception:
        users_list = []

    return {
        "generated_at": now.isoformat(),
        "users": {
            "total": total_users,
            "active": active_users,
            "staff": staff_users,
            "signups_24h": signups_24h,
            "signups_7d": signups_7d,
            "signups_30d": signups_30d,
            "by_provider": by_provider,
            "list": users_list,
        },
        "daily_signups": daily_signups,
        "engagement": engagement,
    }


# ─── Session-authenticated views (used by the Django HTML dashboard) ──────

@staff_member_required
@require_GET
def analytics_dashboard(request):
    """Render the dashboard shell. All numbers come from the JSON endpoint."""
    return render(request, "users/analytics.html")


@staff_member_required
@require_GET
def analytics_data(request):
    return JsonResponse(build_analytics_payload())


# ─── JWT-authenticated views (used by the Vue SPA) ─────────────────────────

class VerifyAnalyticsPinView(APIView):
    """
    Verify a staff user's analytics PIN and issue a short-lived session token.

    POST /api/auth/analytics/verify-pin/
    Body: { "pin": "123456" }
    Returns: { "analytics_token": "...", "expires_in": 900 }

    Rate limited to MAX_PIN_ATTEMPTS per hour per user.
    """
    permission_classes = [IsAdminUser]

    def post(self, request):
        user = request.user
        pin = request.data.get("pin", "").strip()

        if not pin:
            return Response(
                {"error": "PIN is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Rate-limit check
        attempt_key = f"analytics_pin_attempts:{user.id}"
        attempts = cache.get(attempt_key, 0)
        if attempts >= MAX_PIN_ATTEMPTS:
            logger.warning(f"Analytics PIN rate limit reached for user {user.email}")
            return Response(
                {"error": "Too many attempts. Try again later."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        # Check if user has a PIN set
        if not user.analytics_pin:
            return Response(
                {"error": "No analytics PIN configured. Contact an admin."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Verify PIN
        if _hash_pin(pin) != user.analytics_pin:
            cache.set(attempt_key, attempts + 1, PIN_ATTEMPT_WINDOW)
            remaining = MAX_PIN_ATTEMPTS - attempts - 1
            logger.warning(
                f"Failed analytics PIN attempt for {user.email} "
                f"({remaining} attempts remaining)"
            )
            return Response(
                {"error": f"Invalid PIN. {remaining} attempts remaining."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # PIN correct — issue analytics session token
        token = secrets.token_urlsafe(32)
        cache_key = f"analytics_session:{token}"
        cache.set(cache_key, str(user.id), ANALYTICS_TOKEN_TTL)

        # Reset attempt counter on success
        cache.delete(attempt_key)

        logger.info(f"Analytics PIN verified for {user.email}")

        return Response({
            "analytics_token": token,
            "expires_in": ANALYTICS_TOKEN_TTL,
        })


class AnalyticsDataAPIView(APIView):
    """
    Staff-only analytics JSON for the Vue SPA.

    Auth: JWT bearer (DEFAULT_AUTHENTICATION_CLASSES in REST_FRAMEWORK).
    Permission: IsAdminUser ⇒ requires user.is_staff.
    Second factor: X-Analytics-Token header (issued by VerifyAnalyticsPinView).
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        # Verify analytics session token
        analytics_token = request.META.get("HTTP_X_ANALYTICS_TOKEN", "")
        if not analytics_token:
            return Response(
                {"error": "Analytics session required. Please verify your PIN."},
                status=status.HTTP_403_FORBIDDEN,
            )

        cache_key = f"analytics_session:{analytics_token}"
        session_user_id = cache.get(cache_key)

        if not session_user_id:
            return Response(
                {"error": "Analytics session expired. Please re-verify your PIN."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Ensure the analytics token belongs to the requesting user
        if session_user_id != str(request.user.id):
            logger.warning(
                f"Analytics token mismatch: token user={session_user_id}, "
                f"request user={request.user.id}"
            )
            return Response(
                {"error": "Invalid analytics session."},
                status=status.HTTP_403_FORBIDDEN,
            )

        return Response(build_analytics_payload())
