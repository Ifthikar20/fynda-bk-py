"""
Internal analytics dashboard.

Three endpoints, all staff-only, sharing one data builder:

  GET /internal/analytics/         → HTML dashboard (Django session auth)
  GET /internal/analytics/data/    → JSON for the HTML page (Django session auth)
  GET /api/auth/analytics/data/    → JSON for the Vue SPA (JWT bearer auth)

The HTML pair is mounted outside /api/ on purpose: APIGuardMiddleware treats
/api/internal/ as a honeypot path (see fynda/middleware/api_guard.py).
"""

from datetime import timedelta

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET

from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

User = get_user_model()


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


# ─── JWT-authenticated view (used by the Vue SPA) ─────────────────────────

class AnalyticsDataAPIView(APIView):
    """
    Staff-only analytics JSON for the Vue SPA.

    Auth: JWT bearer (DEFAULT_AUTHENTICATION_CLASSES in REST_FRAMEWORK).
    Permission: IsAdminUser ⇒ requires user.is_staff.
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        return Response(build_analytics_payload())
