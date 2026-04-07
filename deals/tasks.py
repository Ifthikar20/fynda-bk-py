"""Background tasks for the deals app."""
import logging
from collections import defaultdict
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, default_retry_delay=600, name="deals.check_deal_alerts")
def check_deal_alerts(self):
    """
    Check active deal alerts every 4 hours.

    Deduplication: groups alerts by search_query so identical queries
    only hit marketplace APIs once.
    """
    from mobile.models import DealAlert, DealAlertMatch
    from deals.services.orchestrator import DealOrchestrator

    now = timezone.now()

    # Expire old alerts in one query
    DealAlert.objects.filter(
        is_active=True, expires_at__lt=now,
    ).update(is_active=False, status="disabled")

    alerts = list(DealAlert.objects.filter(is_active=True, status="active"))
    if not alerts:
        return {"checked": 0, "new_matches": 0, "queries": 0}

    # Group by query
    groups = defaultdict(list)
    for a in alerts:
        groups[(a.search_query or a.description).strip().lower()].append(a)

    orchestrator = DealOrchestrator()
    total_new = 0

    for query, group in groups.items():
        try:
            deals = orchestrator.search(query).deals
        except Exception as e:
            logger.warning(f"Search failed for '{query[:50]}': {e}")
            continue

        for alert in group:
            # Filter by max_price
            filtered = deals
            if alert.max_price:
                cap = float(alert.max_price)
                filtered = [d for d in deals if d.get("price") and d["price"] <= cap]

            # Skip if no deals
            if not filtered:
                alert.last_checked_at = now
                alert.save(update_fields=["last_checked_at"])
                continue

            # Find existing deal_ids to avoid duplicates (one query)
            deal_ids = [str(d.get("id", "")) for d in filtered if d.get("id")]
            existing = set(
                alert.matches.filter(deal_id__in=deal_ids).values_list("deal_id", flat=True)
            )

            # Bulk create new matches
            new_matches = [
                DealAlertMatch(
                    alert=alert,
                    deal_id=str(d["id"]),
                    title=(d.get("title") or "")[:255],
                    price=d.get("price"),
                    image_url=d.get("image_url") or d.get("image") or "",
                    source=(d.get("source") or "")[:100],
                    url=d.get("url") or "",
                    deal_data=d,
                )
                for d in filtered
                if d.get("id") and str(d["id"]) not in existing
            ]

            if new_matches:
                DealAlertMatch.objects.bulk_create(new_matches, ignore_conflicts=True)
                alert.matches_count = alert.matches.count()
                total_new += len(new_matches)

            alert.last_checked_at = now
            alert.save(update_fields=["last_checked_at", "matches_count"])

    logger.info(f"Deal alerts: {len(alerts)} alerts, {len(groups)} queries, {total_new} new matches")
    return {"checked": len(alerts), "new_matches": total_new, "queries": len(groups)}
