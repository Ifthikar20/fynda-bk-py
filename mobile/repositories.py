"""
Mobile Repositories
===================

Data-access layer for DeviceToken, SyncState, UserPreferences, and PriceAlert models.
"""

from django.db.models import QuerySet
from django.utils import timezone

from core.repositories import BaseRepository
from .models import DeviceToken, SyncState, UserPreferences, PriceAlert


class DeviceTokenRepository(BaseRepository[DeviceToken]):
    """Device token / push notification data access."""

    model = DeviceToken

    @classmethod
    def get_active_for_user(cls, user) -> QuerySet:
        """Return active device tokens for a user."""
        return cls.model.objects.filter(user=user, is_active=True)

    @classmethod
    def get_by_device_id(cls, user, device_id: str):
        """Get a device token by user + device ID, or None."""
        return cls.model.objects.filter(user=user, device_id=device_id).first()

    @classmethod
    def register_or_update(cls, user, device_id: str, token: str, platform: str, **kwargs):
        """Register a new device or update existing token."""
        obj, created = cls.model.objects.update_or_create(
            user=user,
            device_id=device_id,
            defaults={"token": token, "platform": platform, **kwargs},
        )
        return obj, created

    @classmethod
    def deactivate(cls, user, device_id: str) -> bool:
        """Mark a device token as inactive. Returns True if found."""
        updated = cls.model.objects.filter(
            user=user, device_id=device_id
        ).update(is_active=False)
        return updated > 0


class SyncStateRepository(BaseRepository[SyncState]):
    """Offline sync state data access."""

    model = SyncState

    @classmethod
    def get_for_user(cls, user, entity_type: str):
        """Get sync state for a given entity type, or None."""
        return cls.model.objects.filter(user=user, entity_type=entity_type).first()

    @classmethod
    def get_or_create_for_user(cls, user, entity_type: str):
        """Get or create sync state for a given entity type."""
        return cls.model.objects.get_or_create(
            user=user,
            entity_type=entity_type,
        )

    @classmethod
    def bump_version(cls, sync_state) -> None:
        """Increment server version and generate new sync token."""
        sync_state.server_version += 1
        sync_state.generate_sync_token()


class UserPreferencesRepository(BaseRepository[UserPreferences]):
    """Mobile user preferences data access."""

    model = UserPreferences

    @classmethod
    def get_for_user(cls, user):
        """Get preferences for user, or None."""
        return cls.model.objects.filter(user=user).first()

    @classmethod
    def get_or_create_for_user(cls, user):
        """Get or create preferences for a user."""
        return cls.model.objects.get_or_create(user=user)


class PriceAlertRepository(BaseRepository[PriceAlert]):
    """Price alert data access."""

    model = PriceAlert

    @classmethod
    def get_active_for_user(cls, user) -> QuerySet:
        """Return active price alerts for a user."""
        return cls.model.objects.filter(user=user, is_active=True, status="active")

    @classmethod
    def get_triggered(cls) -> QuerySet:
        """Return recently triggered alerts."""
        return cls.model.objects.filter(status="triggered")

    @classmethod
    def get_checkable(cls) -> QuerySet:
        """Return active alerts that should be checked for price drops."""
        return cls.model.objects.filter(is_active=True, status="active")


# Singletons
device_token_repo = DeviceTokenRepository()
sync_state_repo = SyncStateRepository()
user_preferences_repo = UserPreferencesRepository()
price_alert_repo = PriceAlertRepository()
