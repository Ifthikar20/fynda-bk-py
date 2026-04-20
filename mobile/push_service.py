"""
APNs Push Notification Service — direct HTTP/2 integration with Apple.

Uses httpx (already in the Docker image) for HTTP/2 and PyJWT for
token-based auth (.p8 key). No third-party APNs library needed.

Requires:
  1. An APNs .p8 key from developer.apple.com
  2. Environment variables:
     - APNS_KEY_ID: The 10-char Key ID from Apple
     - APNS_TEAM_ID: Your Apple Developer Team ID
     - APNS_KEY_PATH: Path to the .p8 file (default: /app/certs/apns_key.p8)
     - APNS_BUNDLE_ID: Your app's bundle ID
     - APNS_USE_SANDBOX: "true" for dev, "false" for production
"""

import json
import logging
import os
import time

from django.conf import settings

logger = logging.getLogger(__name__)

# APNs config from settings (centralized config layer)
APNS_KEY_ID = settings.APNS_KEY_ID
APNS_TEAM_ID = settings.APNS_TEAM_ID
APNS_KEY_PATH = settings.APNS_KEY_PATH
APNS_BUNDLE_ID = settings.APNS_BUNDLE_ID
APNS_USE_SANDBOX = settings.APNS_USE_SANDBOX

APNS_HOST_SANDBOX = "https://api.sandbox.push.apple.com"
APNS_HOST_PRODUCTION = "https://api.push.apple.com"

# Token cache — APNs tokens are valid for 60 minutes, refresh at 50 min.
_cached_token = None
_cached_token_time = 0
TOKEN_REFRESH_INTERVAL = 50 * 60  # 50 minutes


def _is_configured():
    """Check if APNs is configured."""
    if not APNS_KEY_ID or not APNS_TEAM_ID:
        return False
    if not os.path.exists(APNS_KEY_PATH):
        logger.warning(f"APNs key file not found: {APNS_KEY_PATH}")
        return False
    return True


def _get_apns_token():
    """Generate a JWT token for APNs authentication.

    Uses ES256 algorithm with the .p8 private key. Tokens are cached
    for 50 minutes (Apple allows up to 60 minutes).
    """
    global _cached_token, _cached_token_time

    now = time.time()
    if _cached_token and (now - _cached_token_time) < TOKEN_REFRESH_INTERVAL:
        return _cached_token

    try:
        import jwt  # PyJWT
    except ImportError:
        logger.error("PyJWT not installed — cannot generate APNs token")
        return None

    try:
        with open(APNS_KEY_PATH, "r") as f:
            private_key = f.read()

        payload = {
            "iss": APNS_TEAM_ID,
            "iat": int(now),
        }
        headers = {
            "alg": "ES256",
            "kid": APNS_KEY_ID,
        }
        token = jwt.encode(payload, private_key, algorithm="ES256", headers=headers)
        _cached_token = token
        _cached_token_time = now
        return token
    except Exception as e:
        logger.error(f"Failed to generate APNs token: {e}")
        return None


def send_push(device_token: str, title: str, body: str, data: dict = None):
    """
    Send a single push notification to an iOS device via APNs HTTP/2.

    Args:
        device_token: The APNs hex token string
        title: Notification title
        body: Notification body text
        data: Optional custom data payload

    Returns:
        True if sent successfully, False otherwise
    """
    if not _is_configured():
        logger.info(f"APNs not configured — would have sent: '{title}' to {device_token[:16]}...")
        return False

    token = _get_apns_token()
    if not token:
        return False

    host = APNS_HOST_SANDBOX if APNS_USE_SANDBOX else APNS_HOST_PRODUCTION
    url = f"{host}/3/device/{device_token}"

    payload = {
        "aps": {
            "alert": {"title": title, "body": body},
            "sound": "default",
            "badge": 1,
        },
    }
    if data:
        payload.update(data)

    headers = {
        "authorization": f"bearer {token}",
        "apns-topic": APNS_BUNDLE_ID,
        "apns-push-type": "alert",
        "apns-priority": "10",
    }

    try:
        import httpx

        with httpx.Client(http2=True, timeout=10.0) as client:
            response = client.post(
                url,
                headers=headers,
                content=json.dumps(payload),
            )

        if response.status_code == 200:
            logger.info(f"Push sent to {device_token[:16]}...")
            return True
        else:
            reason = "unknown"
            try:
                reason = response.json().get("reason", reason)
            except Exception:
                pass
            logger.warning(f"Push failed ({response.status_code}): {reason} for {device_token[:16]}...")

            # Deactivate invalid tokens
            if reason in ("BadDeviceToken", "Unregistered", "ExpiredToken"):
                _deactivate_token(device_token)
            return False

    except ImportError:
        logger.error("httpx not installed — cannot send push notifications")
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
