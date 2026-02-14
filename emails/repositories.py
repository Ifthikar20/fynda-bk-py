"""
Emails Repositories
===================

Data-access layer for Subscriber, Campaign, and CampaignSend models.
"""

from django.db.models import QuerySet
from django.utils import timezone

from core.repositories import BaseRepository
from .models import Subscriber, Campaign, CampaignSend


class SubscriberRepository(BaseRepository[Subscriber]):
    """Email subscriber data access."""

    model = Subscriber

    @classmethod
    def get_by_email(cls, email: str):
        """Get subscriber by email (case-insensitive), or None."""
        return cls.model.objects.filter(email__iexact=email).first()

    @classmethod
    def get_active_verified(cls) -> QuerySet:
        """Return all active and verified subscribers."""
        return cls.model.objects.filter(is_active=True, is_verified=True)

    @classmethod
    def get_by_unsubscribe_token(cls, token: str):
        """Look up subscriber by unsubscribe token."""
        return cls.model.objects.filter(unsubscribe_token=token).first()

    @classmethod
    def get_by_verification_token(cls, token: str):
        """Look up subscriber by verification token."""
        return cls.model.objects.filter(verification_token=token).first()

    @classmethod
    def unsubscribe(cls, subscriber) -> None:
        """Mark subscriber as inactive."""
        subscriber.is_active = False
        subscriber.unsubscribed_at = timezone.now()
        subscriber.save(update_fields=["is_active", "unsubscribed_at"])

    @classmethod
    def verify(cls, subscriber) -> None:
        """Mark subscriber as verified."""
        subscriber.is_verified = True
        subscriber.verified_at = timezone.now()
        subscriber.save(update_fields=["is_verified", "verified_at"])


class CampaignRepository(BaseRepository[Campaign]):
    """Email campaign data access."""

    model = Campaign

    @classmethod
    def get_drafts(cls) -> QuerySet:
        """Return draft campaigns."""
        return cls.model.objects.filter(status="draft")

    @classmethod
    def get_scheduled(cls) -> QuerySet:
        """Return campaigns scheduled for sending."""
        return cls.model.objects.filter(
            status="scheduled",
            scheduled_at__lte=timezone.now(),
        )

    @classmethod
    def get_sent(cls) -> QuerySet:
        """Return sent campaigns with stats."""
        return cls.model.objects.filter(status="sent")


class CampaignSendRepository(BaseRepository[CampaignSend]):
    """Individual email send tracking data access."""

    model = CampaignSend

    @classmethod
    def get_by_tracking_id(cls, tracking_id: str):
        """Get a send record by its tracking ID."""
        return cls.model.objects.filter(tracking_id=tracking_id).first()

    @classmethod
    def mark_opened(cls, send) -> None:
        """Record an email open event."""
        send.opened = True
        send.opened_at = timezone.now()
        send.open_count += 1
        send.save(update_fields=["opened", "opened_at", "open_count"])

    @classmethod
    def mark_clicked(cls, send) -> None:
        """Record an email click event."""
        send.clicked = True
        send.clicked_at = timezone.now()
        send.click_count += 1
        send.save(update_fields=["clicked", "clicked_at", "click_count"])


# Singletons
subscriber_repo = SubscriberRepository()
campaign_repo = CampaignRepository()
campaign_send_repo = CampaignSendRepository()
