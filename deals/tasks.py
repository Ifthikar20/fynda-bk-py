"""
Background tasks for the deals app.
"""
import logging
from collections import defaultdict
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=600,
    name="deals.check_deal_alerts",
)
def check_deal_alerts(self):
    """
    Periodic task: check all active deal alerts for new matches.

    Runs every 4 hours via Celery Beat.

    Deduplication: groups alerts by search_query so identical queries
    only hit marketplace APIs once. At 100K users with overlapping
    queries, this reduces API calls from 100K to ~2K per cycle.
    """
    from mobile.models import DealAlert, DealAlertMatch
    from deals.services.orchestrator import DealOrchestrator

    # Expire old alerts
    expired = DealAlert.objects.filter(
        is_active=True, expires_at__lt=timezone.now(),
    ).update(is_active=False, status="disabled")
    if expired:
        logger.info(f"Expired {expired} deal alerts")

    # Get all active alerts
    alerts = list(DealAlert.objects.filter(is_active=True, status="active"))
    if not alerts:
        return {"checked": 0, "new_matches": 0, "queries": 0}

    # Group alerts by normalized search_query to deduplicate
    query_groups = defaultdict(list)
    for alert in alerts:
        key = (alert.search_query or alert.description).strip().lower()
        query_groups[key].append(alert)

    orchestrator = DealOrchestrator()
    total_new = 0

    for query, group_alerts in query_groups.items():
        try:
            # One search per unique query
            result = orchestrator.search(query)
            deals = result.deals

            # Fan out results to each alert in this group
            for alert in group_alerts:
                filtered = deals
                if alert.max_price:
                    filtered = [d for d in deals if d.get("price") and d["price"] <= float(alert.max_price)]

                new_count = 0
                for deal in filtered:
                    deal_id = str(deal.get("id", ""))
                    if not deal_id:
                        continue
                    _, created = DealAlertMatch.objects.get_or_create(
                        alert=alert,
                        deal_id=deal_id,
                        defaults={
                            "title": (deal.get("title") or "")[:255],
                            "price": deal.get("price"),
                            "image_url": deal.get("image_url") or deal.get("image") or "",
                            "source": (deal.get("source") or "")[:100],
                            "url": deal.get("url") or "",
                            "deal_data": deal,
                        },
                    )
                    if created:
                        new_count += 1

                if new_count > 0:
                    alert.matches_count = alert.matches.count()
                alert.last_checked_at = timezone.now()
                alert.save(update_fields=["last_checked_at", "matches_count"])
                total_new += new_count

        except Exception as e:
            logger.warning(f"Deal alert check failed for query '{query[:50]}': {e}")

    logger.info(
        f"Deal alerts: {len(alerts)} alerts, {len(query_groups)} unique queries, "
        f"{total_new} new matches"
    )
    return {
        "checked": len(alerts),
        "new_matches": total_new,
        "queries": len(query_groups),
    }
