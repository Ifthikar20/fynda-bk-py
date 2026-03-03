"""
Pinterest Publisher — OAuth2 + Pin Creation
============================================

Handles direct Pinterest OAuth2 authentication and pin publishing
via the official Pinterest API v5.

Requires PINTEREST_APP_ID and PINTEREST_APP_SECRET in environment.

Pinterest API docs: https://developers.pinterest.com/docs/api/v5/
"""

import requests
import logging
from urllib.parse import urlencode
from datetime import timedelta
from django.utils import timezone
from fynda.config import config

logger = logging.getLogger(__name__)

PINTEREST_API_BASE = "https://api.pinterest.com/v5"
PINTEREST_OAUTH_URL = "https://www.pinterest.com/oauth"
PINTEREST_TOKEN_URL = "https://api.pinterest.com/v5/oauth/token"

# Scopes needed for publishing pins and reading boards
PINTEREST_SCOPES = "boards:read,boards:write,pins:read,pins:write,user_accounts:read"


class PinterestPublisherError(Exception):
    """Raised when a Pinterest API call fails."""
    pass


class PinterestPublisher:
    """
    Pinterest API v5 client for OAuth and pin management.
    Separate from the existing PinterestService (RapidAPI scraper).
    """

    @staticmethod
    def is_configured():
        """Check if Pinterest API keys are present."""
        return config.apis.is_configured("pinterest")

    @staticmethod
    def get_auth_url(redirect_uri: str, state: str = "") -> str:
        """
        Generate the Pinterest OAuth2 authorization URL.
        The user will be redirected here to grant access.
        """
        if not PinterestPublisher.is_configured():
            raise PinterestPublisherError("Pinterest API keys not configured")

        params = {
            "client_id": config.apis.pinterest_app_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": PINTEREST_SCOPES,
            "state": state,
        }
        return f"{PINTEREST_OAUTH_URL}/?{urlencode(params)}"

    @staticmethod
    def exchange_code(code: str, redirect_uri: str) -> dict:
        """
        Exchange an OAuth authorization code for access + refresh tokens.

        Returns: {
            'access_token': str,
            'refresh_token': str,
            'expires_in': int (seconds),
            'token_type': 'bearer',
        }
        """
        if not PinterestPublisher.is_configured():
            raise PinterestPublisherError("Pinterest API keys not configured")

        response = requests.post(
            PINTEREST_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
            },
            auth=(config.apis.pinterest_app_id, config.apis.pinterest_app_secret),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15,
        )

        if response.status_code != 200:
            logger.error(f"Pinterest token exchange failed: {response.status_code} {response.text}")
            raise PinterestPublisherError(f"Token exchange failed: {response.text}")

        return response.json()

    @staticmethod
    def refresh_access_token(refresh_token: str) -> dict:
        """Refresh an expired access token using the refresh token."""
        if not PinterestPublisher.is_configured():
            raise PinterestPublisherError("Pinterest API keys not configured")

        response = requests.post(
            PINTEREST_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
            auth=(config.apis.pinterest_app_id, config.apis.pinterest_app_secret),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15,
        )

        if response.status_code != 200:
            logger.error(f"Pinterest token refresh failed: {response.status_code} {response.text}")
            raise PinterestPublisherError(f"Token refresh failed: {response.text}")

        return response.json()

    @staticmethod
    def get_user_account(access_token: str) -> dict:
        """Get the authenticated user's Pinterest account info."""
        response = requests.get(
            f"{PINTEREST_API_BASE}/user_account",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )

        if response.status_code != 200:
            raise PinterestPublisherError("Failed to get Pinterest user info")

        return response.json()

    @staticmethod
    def get_boards(access_token: str) -> list:
        """List the authenticated user's Pinterest boards."""
        boards = []
        bookmark = None

        for _ in range(10):  # Safety: max 250 boards
            params = {"page_size": 25}
            if bookmark:
                params["bookmark"] = bookmark

            response = requests.get(
                f"{PINTEREST_API_BASE}/boards",
                headers={"Authorization": f"Bearer {access_token}"},
                params=params,
                timeout=10,
            )

            if response.status_code != 200:
                raise PinterestPublisherError("Failed to list Pinterest boards")

            data = response.json()
            boards.extend(data.get("items", []))

            bookmark = data.get("bookmark")
            if not bookmark:
                break

        return boards

    @staticmethod
    def create_pin(
        access_token: str,
        board_id: str,
        title: str,
        description: str,
        image_url: str,
        link: str = "",
    ) -> dict:
        """
        Create a new Pin on Pinterest.

        Args:
            access_token: User's Pinterest access token
            board_id: ID of the Pinterest board to pin to
            title: Pin title (max 100 chars)
            description: Pin description (max 500 chars)
            image_url: Public URL of the image to pin
            link: Destination URL when the pin is clicked

        Returns: Created pin object from Pinterest API
        """
        payload = {
            "board_id": board_id,
            "title": title[:100],
            "description": description[:500],
            "media_source": {
                "source_type": "image_url",
                "url": image_url,
            },
        }

        if link:
            payload["link"] = link

        response = requests.post(
            f"{PINTEREST_API_BASE}/pins",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30,
        )

        if response.status_code not in (200, 201):
            logger.error(f"Pinterest create pin failed: {response.status_code} {response.text}")
            raise PinterestPublisherError(f"Failed to create pin: {response.text}")

        logger.info(f"Pinterest pin created successfully: {response.json().get('id')}")
        return response.json()

    @staticmethod
    def ensure_valid_token(connection) -> str:
        """
        Ensure the PinterestConnection has a valid (non-expired) access token.
        Refreshes automatically if expired.

        Args:
            connection: PinterestConnection model instance

        Returns: Valid access token string
        """
        if not connection.is_expired:
            return connection.access_token

        if not connection.refresh_token:
            raise PinterestPublisherError(
                "Token expired and no refresh token available. Please reconnect."
            )

        try:
            token_data = PinterestPublisher.refresh_access_token(connection.refresh_token)
            connection.access_token = token_data["access_token"]
            connection.refresh_token = token_data.get("refresh_token", connection.refresh_token)
            connection.token_expires_at = timezone.now() + timedelta(
                seconds=token_data.get("expires_in", 2592000)
            )
            connection.save(
                update_fields=["access_token", "refresh_token", "token_expires_at", "updated_at"]
            )
            logger.info(f"Pinterest token refreshed for user {connection.user_id}")
            return connection.access_token
        except Exception as e:
            logger.error(f"Pinterest token refresh failed for user {connection.user_id}: {e}")
            raise PinterestPublisherError(
                "Failed to refresh token. Please reconnect your Pinterest account."
            )
