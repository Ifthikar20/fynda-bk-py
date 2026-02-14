"""
Mobile Services
===============

Business logic for mobile-specific operations, extracted from views.
"""

from django.contrib.auth import get_user_model

from core.services import BaseService
from .models import DeviceToken, UserPreferences

User = get_user_model()


class MobileDeviceService(BaseService):
    """
    Device registration and preference management for mobile clients.

    Extracted from MobileLoginView, MobileRegisterView, MobileOAuthView
    to eliminate duplicated device-binding logic.
    """

    @classmethod
    def register_device(cls, user, device_id: str, platform: str, **kwargs) -> tuple:
        """
        Register or update a device token for push notifications.

        Args:
            user: authenticated User instance
            device_id: unique device identifier
            platform: 'ios' or 'android'
            **kwargs: push_token, device_name, app_version

        Returns:
            (device, created) tuple
        """
        device, created = DeviceToken.objects.update_or_create(
            user=user,
            device_id=device_id,
            defaults={
                "platform": platform,
                "token": kwargs.get("push_token", ""),
                "device_name": kwargs.get("device_name", ""),
                "app_version": kwargs.get("app_version", ""),
                "is_active": True,
            },
        )

        action = "Registered new" if created else "Updated"
        cls.logger.info("%s device %s for user %s", action, device_id, user.email)

        return device, created

    @classmethod
    def deactivate_device(cls, user, device_id: str) -> bool:
        """
        Mark a device as inactive (on logout).

        Returns:
            True if a device was deactivated.
        """
        updated = DeviceToken.objects.filter(
            user=user,
            device_id=device_id,
        ).update(is_active=False)

        return updated > 0

    @classmethod
    def get_or_create_preferences(cls, user) -> tuple:
        """
        Get existing preferences or create defaults.

        Returns:
            (preferences, created) tuple
        """
        return UserPreferences.objects.get_or_create(user=user)
