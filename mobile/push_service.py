"""
APNs Push Notification Service — direct Apple integration, no Firebase.

Requires:
  1. An APNs .p8 key from developer.apple.com
  2. Environment variables:
     - APNS_KEY_ID: The 10-char Key ID from Apple
     - APNS_TEAM_ID: Your Apple Developer Team ID
     - APNS_KEY_PATH: Path to the .p8 file (default: /app/certs/apns_key.p8)

Generate the key:
  developer.apple.com → Certificates, IDs & Profiles → Keys
  → + → check "Apple Push Notifications service (APNs)"
  → Download the .p8 file
"""

import logging
import os

from django.conf import settings

logger = logging.getLogger(__name__)

# APNs config from environment
APNS_KEY_ID = os.getenv("APNS_KEY_ID", "")
APNS_TEAM_ID = os.getenv("APNS_TEAM_ID", "")
APNS_KEY_PATH = os.getenv("APNS_KEY_PATH", "/app/certs/apns_key.p8")
APNS_BUNDLE_ID = "com.outfi.outfiApp"
APNS_USE_SANDBOX = os.getenv("APNS_USE_SANDBOX", "true").lower() == "true"


def _get_client():
    """Lazy-load the APNs client (only when actually sending)."""
    try:
        from apns2.client import APNsClient
        from apns2.credentials import TokenCredentials

        if not APNS_KEY_ID or not APNS_TEAM_ID:
            logger.warning("APNs not configured: APNS_KEY_ID or APNS_TEAM_ID missing")
            return None

        if not os.path.exists(APNS_KEY_PATH):
            logger.warning(f"APNs key file not found: {APNS_KEY_PATH}")
            return None

        credentials = TokenCredentials(
            auth_key_path=APNS_KEY_PATH,
            auth_key_id=APNS_KEY_ID,
            team_id=APNS_TEAM_ID,
        )
        return APNsClient(credentials=credentials, use_sandbox=APNS_USE_SANDBOX)
    except ImportError:
        logger.warning("PyAPNs2 not installed — push notifications disabled")
        return None
    except Exception as e:
        logger.error(f"Failed to create APNs client: {e}")
        return None


def send_push(device_token: str, title: str, body: str, data: dict = None):
    """
    Send a single push notification to an iOS device.

    Args:
        device_token: The APNs hex token string
        title: Notification title
        body: Notification body text
        data: Optional custom data payload
    """
    client = _get_client()
    if not client:
        logger.info(f"APNs not configured — would have sent: '{title}' to {device_token[:16]}...")
        return False

    try:
        from apns2.payload import Payload

        payload = Payload(
            alert={"title": title, "body": body},
            sound="default",
            badge=1,
            custom=data or {},
        )

        result = client.send_notification(
            token_hex=device_token,
            notification=payload,
            topic=APNS_BUNDLE_ID,
        )

        if result.is_successful:
            logger.info(f"Push sent to {device_token[:16]}...")
            return True
        else:
            logger.warning(f"Push failed: {result.description} for {device_token[:16]}...")
            # Deactivate invalid tokens
            if result.description in ("BadDeviceToken", "Unregistered"):
                _deactivate_token(device_token)
            return False
    except Exception as e:
        logger.error(f"Push send error: {e}")
        return False


def send_push_to_user(user, title: str, body: str, data: dict = None):
    """
    Send a push notification to all active devices of a user.
    """
    from .models import DeviceToken

    tokens = DeviceToken.objects.filter(
        user=user, is_active=True, platform="ios"
    ).values_list("token", flat=True)

    sent = 0
    for token in tokens:
        if send_push(token, title, body, data):
            sent += 1

    return sent


def _deactivate_token(token_hex: str):
    """Mark a token as inactive (device unregistered or token expired)."""
    from .models import DeviceToken
    DeviceToken.objects.filter(token=token_hex).update(is_active=False)
    logger.info(f"Deactivated token: {token_hex[:16]}...")
