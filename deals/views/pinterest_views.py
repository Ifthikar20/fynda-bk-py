"""
Pinterest Publishing API Views
===============================

Endpoints for connecting a Pinterest account and publishing fashion boards as Pins.

Routes (all prefixed with /api/):
    GET  pinterest/auth/     — Get Pinterest OAuth URL
    GET  pinterest/callback/ — OAuth callback (exchanges code for token)
    GET  pinterest/boards/   — List user's Pinterest boards
    POST pinterest/publish/  — Publish a fashion board as a Pin
    GET  pinterest/status/   — Check Pinterest connection status
    DELETE pinterest/disconnect/ — Disconnect Pinterest account
"""

import logging
import uuid
from datetime import timedelta
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny

from deals.models import PinterestConnection, SharedStoryboard
from deals.services.pinterest_publisher import PinterestPublisher, PinterestPublisherError

logger = logging.getLogger(__name__)


class PinterestStatusView(APIView):
    """
    GET /api/pinterest/status/
    
    Check if Pinterest integration is configured and if the user has connected.
    No auth required — used to show/hide the Pinterest button in the UI.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        is_configured = PinterestPublisher.is_configured()
        
        connected = False
        pinterest_username = ""
        
        if request.user.is_authenticated and is_configured:
            try:
                conn = PinterestConnection.objects.get(user=request.user)
                connected = True
                pinterest_username = conn.pinterest_username
            except PinterestConnection.DoesNotExist:
                pass

        return Response({
            "configured": is_configured,
            "connected": connected,
            "pinterest_username": pinterest_username,
        })


class PinterestAuthView(APIView):
    """
    GET /api/pinterest/auth/
    
    Returns the Pinterest OAuth2 authorization URL.
    The frontend opens this URL in a popup window.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not PinterestPublisher.is_configured():
            return Response(
                {"error": "Pinterest API keys not configured. Add PINTEREST_APP_ID and PINTEREST_APP_SECRET to your environment."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        # Build the callback URL
        callback_url = f"https://api.outfi.ai/api/pinterest/callback/"
        
        # Generate a state parameter for CSRF protection
        state = uuid.uuid4().hex[:16]
        request.session["pinterest_oauth_state"] = state

        try:
            auth_url = PinterestPublisher.get_auth_url(
                redirect_uri=callback_url,
                state=state,
            )
            return Response({"auth_url": auth_url})
        except PinterestPublisherError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class PinterestCallbackView(APIView):
    """
    GET /api/pinterest/callback/?code=...&state=...
    
    Pinterest redirects here after the user grants access.
    Exchanges the code for tokens and stores the connection.
    Returns HTML that closes the popup and notifies the parent window.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        from django.http import HttpResponse
        
        code = request.GET.get("code")
        error = request.GET.get("error")

        if error:
            return HttpResponse(self._close_popup_html("error", error), content_type="text/html")

        if not code:
            return HttpResponse(self._close_popup_html("error", "No authorization code received"), content_type="text/html")

        if not request.user.is_authenticated:
            return HttpResponse(self._close_popup_html("error", "Not authenticated. Please log in first."), content_type="text/html")

        callback_url = f"https://api.outfi.ai/api/pinterest/callback/"

        try:
            # Exchange code for tokens
            token_data = PinterestPublisher.exchange_code(code, callback_url)

            access_token = token_data.get("access_token")
            refresh_token = token_data.get("refresh_token", "")
            expires_in = token_data.get("expires_in", 2592000)  # Default 30 days

            # Get Pinterest user info
            user_info = PinterestPublisher.get_user_account(access_token)

            # Create or update the connection
            conn, created = PinterestConnection.objects.update_or_create(
                user=request.user,
                defaults={
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "token_expires_at": timezone.now() + timedelta(seconds=expires_in),
                    "pinterest_user_id": user_info.get("id", ""),
                    "pinterest_username": user_info.get("username", ""),
                },
            )

            action = "created" if created else "updated"
            logger.info(f"Pinterest connection {action} for user {request.user.id}")

            return HttpResponse(
                self._close_popup_html("success", user_info.get("username", "connected")),
                content_type="text/html",
            )

        except PinterestPublisherError as e:
            logger.error(f"Pinterest callback error: {e}")
            return HttpResponse(self._close_popup_html("error", str(e)), content_type="text/html")
        except Exception as e:
            logger.exception(f"Pinterest callback unexpected error: {e}")
            return HttpResponse(self._close_popup_html("error", "An unexpected error occurred"), content_type="text/html")

    @staticmethod
    def _close_popup_html(status_type: str, message: str) -> str:
        """Generate HTML that closes the popup and sends a message to the parent window."""
        return f"""
        <!DOCTYPE html>
        <html>
        <head><title>Pinterest — Outfi</title></head>
        <body>
            <p>Connecting to Pinterest...</p>
            <script>
                if (window.opener) {{
                    window.opener.postMessage({{
                        type: 'pinterest-oauth-callback',
                        status: '{status_type}',
                        message: '{message}'
                    }}, '*');
                }}
                setTimeout(() => window.close(), 1500);
            </script>
        </body>
        </html>
        """


class PinterestBoardsView(APIView):
    """
    GET /api/pinterest/boards/
    
    List the authenticated user's Pinterest boards.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            conn = PinterestConnection.objects.get(user=request.user)
        except PinterestConnection.DoesNotExist:
            return Response(
                {"error": "Pinterest account not connected"},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            access_token = PinterestPublisher.ensure_valid_token(conn)
            boards = PinterestPublisher.get_boards(access_token)

            return Response({
                "boards": [
                    {
                        "id": b.get("id"),
                        "name": b.get("name"),
                        "description": b.get("description", ""),
                        "pin_count": b.get("pin_count", 0),
                        "image_url": (b.get("media", {}) or {}).get("image_cover_url", ""),
                    }
                    for b in boards
                ]
            })
        except PinterestPublisherError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class PinterestPublishView(APIView):
    """
    POST /api/pinterest/publish/
    
    Publish a fashion board as a Pinterest Pin.
    
    Request body:
        - storyboard_token: str (required) — the shared storyboard token
        - board_id: str (required) — Pinterest board ID to pin to
        - title: str (optional) — Pin title
        - description: str (optional) — Pin description
        - image_url: str (optional) — Custom image URL (if not provided, uses first item's image)
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        storyboard_token = request.data.get("storyboard_token")
        board_id = request.data.get("board_id")
        title = request.data.get("title", "")
        description = request.data.get("description", "")
        image_url = request.data.get("image_url", "")

        if not storyboard_token:
            return Response(
                {"error": "storyboard_token is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not board_id:
            return Response(
                {"error": "board_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get the Pinterest connection
        try:
            conn = PinterestConnection.objects.get(user=request.user)
        except PinterestConnection.DoesNotExist:
            return Response(
                {"error": "Pinterest account not connected"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Get the shared storyboard
        try:
            storyboard = SharedStoryboard.objects.get(token=storyboard_token)
        except SharedStoryboard.DoesNotExist:
            return Response(
                {"error": "Storyboard not found. Please share your board first."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Use the first item's image if no custom image provided
        if not image_url:
            items = storyboard.storyboard_data.get("items", [])
            if items:
                image_url = items[0].get("image_url", "")

        if not image_url:
            return Response(
                {"error": "No image available. Add at least one image to your board."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Build defaults
        if not title:
            title = storyboard.title or "Fashion Board"
        if not description:
            description = f"Fashion board curated on outfi.ai — discover and share outfit inspiration."

        # Link back to the shared board on outfi.ai
        share_link = f"https://outfi.ai/share/{storyboard_token}"

        try:
            access_token = PinterestPublisher.ensure_valid_token(conn)
            pin = PinterestPublisher.create_pin(
                access_token=access_token,
                board_id=board_id,
                title=title,
                description=description,
                image_url=image_url,
                link=share_link,
            )

            return Response({
                "success": True,
                "pin_id": pin.get("id"),
                "pin_url": f"https://pinterest.com/pin/{pin.get('id')}",
                "message": "Pin published successfully!",
            }, status=status.HTTP_201_CREATED)

        except PinterestPublisherError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception(f"Pinterest publish error: {e}")
            return Response(
                {"error": "Failed to publish pin. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class PinterestDisconnectView(APIView):
    """
    DELETE /api/pinterest/disconnect/
    
    Remove the user's Pinterest connection.
    """
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        deleted, _ = PinterestConnection.objects.filter(user=request.user).delete()
        if deleted:
            return Response({"message": "Pinterest account disconnected"})
        return Response(
            {"error": "No Pinterest account connected"},
            status=status.HTTP_404_NOT_FOUND,
        )
