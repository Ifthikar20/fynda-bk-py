"""
Mobile API Views

Endpoints optimized for mobile:
- Compact payloads
- Offline sync support
- Device registration
- Cursor-based pagination
"""

import time
import logging
from django.utils import timezone
from django.db import transaction
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken

from .models import DeviceToken, SyncState, UserPreferences, PriceAlert, MobileSession
from .serializers import (
    DeviceTokenSerializer,
    DeviceTokenCompactSerializer,
    UserPreferencesSerializer,
    PriceAlertSerializer,
    PriceAlertCompactSerializer,
    SyncStateSerializer,
    MobileDealSerializer,
    MobileDealDetailSerializer,
    MobileSearchSerializer,
    MobileSearchResponseSerializer,
    SyncRequestSerializer,
    SyncResponseSerializer,
    SavedDealMobileSerializer,
    MobileLoginSerializer,
    MobileLoginResponseSerializer,
    MobileRegisterSerializer,
    HealthCheckSerializer,
)

logger = logging.getLogger(__name__)


# ============================================
# Health & Status
# ============================================

class HealthView(APIView):
    """
    Mobile health check endpoint.
    
    GET /api/mobile/health/
    
    Returns server status and app version requirements.
    """
    permission_classes = [AllowAny]
    
    # Minimum supported app versions
    MIN_APP_VERSIONS = {
        "ios": "1.0.0",
        "android": "1.0.0",
    }
    
    def get(self, request):
        platform = request.query_params.get("platform", "ios")
        
        data = {
            "status": "ok",
            "server_time": timezone.now(),
            "min_app_version": self.MIN_APP_VERSIONS.get(platform, "1.0.0"),
            "force_update": False,
            "maintenance": False,
            "message": "",
        }
        
        return Response(HealthCheckSerializer(data).data)


# ============================================
# Authentication
# ============================================

class MobileLoginView(APIView):
    """
    Mobile login with device binding.
    
    POST /api/mobile/auth/login/
    
    Body:
    {
        "email": "user@example.com",
        "password": "xxx",
        "device_id": "unique-device-id",
        "platform": "ios",
        "app_version": "1.0.0",
        "push_token": "fcm-or-apns-token"
    }
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = MobileLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        data = serializer.validated_data
        
        # Authenticate user
        from django.contrib.auth import authenticate
        user = authenticate(
            request,
            username=data["email"],
            password=data["password"]
        )
        
        if not user:
            return Response(
                {"error": "Invalid email or password"},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        if not user.is_active:
            return Response(
                {"error": "Account is disabled"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Generate tokens
        refresh = RefreshToken.for_user(user)
        
        # Register/update device
        device, _ = DeviceToken.objects.update_or_create(
            user=user,
            device_id=data["device_id"],
            defaults={
                "platform": data["platform"],
                "token": data.get("push_token", ""),
                "device_name": data.get("device_name", ""),
                "app_version": data.get("app_version", ""),
                "is_active": True,
            }
        )
        
        # Get or create preferences
        preferences, _ = UserPreferences.objects.get_or_create(user=user)
        
        response_data = {
            "access_token": str(refresh.access_token),
            "refresh_token": str(refresh),
            "expires_in": int(refresh.access_token.lifetime.total_seconds()),
            "user": {
                "id": str(user.id),
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
            },
            "device_id": str(device.id),
            "preferences": UserPreferencesSerializer(preferences).data,
        }
        
        return Response(MobileLoginResponseSerializer(response_data).data)


class MobileRegisterView(APIView):
    """
    Mobile registration with device binding.
    
    POST /api/mobile/auth/register/
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = MobileRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        data = serializer.validated_data
        
        # Create user
        from users.models import User
        user = User.objects.create_user(
            email=data["email"],
            password=data["password"],
            first_name=data.get("first_name", ""),
            last_name=data.get("last_name", ""),
        )
        
        # Generate tokens
        refresh = RefreshToken.for_user(user)
        
        # Register device
        device = DeviceToken.objects.create(
            user=user,
            device_id=data["device_id"],
            platform=data["platform"],
            token=data.get("push_token", ""),
            is_active=True,
        )
        
        # Create default preferences
        preferences = UserPreferences.objects.create(user=user)
        
        response_data = {
            "access_token": str(refresh.access_token),
            "refresh_token": str(refresh),
            "expires_in": int(refresh.access_token.lifetime.total_seconds()),
            "user": {
                "id": str(user.id),
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
            },
            "device_id": str(device.id),
            "preferences": UserPreferencesSerializer(preferences).data,
        }
        
        return Response(
            MobileLoginResponseSerializer(response_data).data,
            status=status.HTTP_201_CREATED
        )


class MobileLogoutView(APIView):
    """
    Mobile logout - deactivate device.
    
    POST /api/mobile/auth/logout/
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        device_id = request.data.get("device_id")
        
        if device_id:
            DeviceToken.objects.filter(
                user=request.user,
                device_id=device_id
            ).update(is_active=False)
        
        return Response({"status": "logged_out"})


# ============================================
# Device Management
# ============================================

class DeviceListView(APIView):
    """
    List and register devices.
    
    GET /api/mobile/devices/ - List user's devices
    POST /api/mobile/devices/ - Register push token
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        devices = DeviceToken.objects.filter(
            user=request.user,
            is_active=True
        ).order_by("-last_used_at")
        
        return Response({
            "devices": DeviceTokenCompactSerializer(devices, many=True).data,
            "count": devices.count(),
        })
    
    def post(self, request):
        serializer = DeviceTokenSerializer(
            data=request.data,
            context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        device = serializer.save()
        
        return Response(
            DeviceTokenSerializer(device).data,
            status=status.HTTP_201_CREATED
        )


class DeviceDetailView(APIView):
    """
    Manage a specific device.
    
    PATCH /api/mobile/devices/{id}/ - Update device
    DELETE /api/mobile/devices/{id}/ - Unregister device
    """
    permission_classes = [IsAuthenticated]
    
    def get_device(self, device_id, user):
        try:
            return DeviceToken.objects.get(id=device_id, user=user)
        except DeviceToken.DoesNotExist:
            return None
    
    def patch(self, request, device_id):
        device = self.get_device(device_id, request.user)
        if not device:
            return Response(
                {"error": "Device not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Update push token
        if "token" in request.data:
            device.token = request.data["token"]
        if "app_version" in request.data:
            device.app_version = request.data["app_version"]
        
        device.save()
        
        return Response(DeviceTokenSerializer(device).data)
    
    def delete(self, request, device_id):
        device = self.get_device(device_id, request.user)
        if not device:
            return Response(
                {"error": "Device not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        device.is_active = False
        device.save()
        
        return Response(status=status.HTTP_204_NO_CONTENT)


# ============================================
# Preferences
# ============================================

class PreferencesView(APIView):
    """
    User preferences for mobile.
    
    GET /api/mobile/preferences/ - Get preferences
    PATCH /api/mobile/preferences/ - Update preferences
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        preferences, _ = UserPreferences.objects.get_or_create(user=request.user)
        return Response(UserPreferencesSerializer(preferences).data)
    
    def patch(self, request):
        preferences, _ = UserPreferences.objects.get_or_create(user=request.user)
        
        serializer = UserPreferencesSerializer(
            preferences,
            data=request.data,
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response(serializer.data)


# ============================================
# Sync
# ============================================

class SyncView(APIView):
    """
    Offline sync endpoint.
    
    GET /api/mobile/sync/ - Get sync state
    POST /api/mobile/sync/ - Pull changes since last sync
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get current sync state for all entities."""
        states = SyncState.objects.filter(user=request.user)
        
        return Response({
            "sync_states": SyncStateSerializer(states, many=True).data,
            "server_time": timezone.now(),
        })
    
    def post(self, request):
        """
        Pull changes since last sync.
        
        Body:
        {
            "entity_types": ["favorites", "alerts", "preferences"],
            "sync_tokens": {
                "favorites": "abc123",
                "alerts": "def456"
            },
            "full_sync": false
        }
        """
        serializer = SyncRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        data = serializer.validated_data
        user = request.user
        entity_types = data["entity_types"]
        sync_tokens = data.get("sync_tokens", {})
        full_sync = data.get("full_sync", False)
        
        response = {
            "sync_tokens": {},
            "synced_at": timezone.now(),
            "has_conflicts": False,
        }
        
        # Sync favorites
        if "favorites" in entity_types:
            response["favorites"] = self._sync_favorites(user, sync_tokens.get("favorites"), full_sync)
            response["sync_tokens"]["favorites"] = response["favorites"].get("sync_token", "")
        
        # Sync alerts
        if "alerts" in entity_types:
            response["alerts"] = self._sync_alerts(user, sync_tokens.get("alerts"), full_sync)
            response["sync_tokens"]["alerts"] = response["alerts"].get("sync_token", "")
        
        # Sync preferences
        if "preferences" in entity_types:
            response["preferences"] = self._sync_preferences(user)
            response["sync_tokens"]["preferences"] = str(user.mobile_preferences.updated_at.timestamp() if hasattr(user, "mobile_preferences") else "")
        
        return Response(SyncResponseSerializer(response).data)
    
    def _sync_favorites(self, user, last_token, full_sync):
        """Sync saved deals."""
        from users.models import SavedDeal
        
        # Get or create sync state
        state, _ = SyncState.objects.get_or_create(
            user=user,
            entity_type="favorites"
        )
        
        # Determine what to fetch
        if full_sync or not last_token:
            deals = SavedDeal.objects.filter(user=user)
        else:
            # Incremental sync - only items updated since last sync
            deals = SavedDeal.objects.filter(
                user=user,
                created_at__gt=state.last_sync_at or timezone.now()
            )
        
        # Update sync state
        state.last_sync_at = timezone.now()
        state.sync_token = state.generate_sync_token()
        state.server_version += 1
        state.save()
        
        return {
            "items": [
                {
                    "id": str(d.id),
                    "deal_id": d.deal_id,
                    "title": d.deal_data.get("title", ""),
                    "price": d.deal_data.get("price"),
                    "image": d.deal_data.get("image_url", ""),
                    "source": d.deal_data.get("source", ""),
                    "url": d.deal_data.get("url", ""),
                    "saved_at": d.created_at.isoformat(),
                }
                for d in deals[:100]  # Limit to 100 items per sync
            ],
            "total": deals.count(),
            "sync_token": state.sync_token,
        }
    
    def _sync_alerts(self, user, last_token, full_sync):
        """Sync price alerts."""
        alerts = PriceAlert.objects.filter(user=user, is_active=True)
        
        state, _ = SyncState.objects.get_or_create(
            user=user,
            entity_type="alerts"
        )
        
        state.last_sync_at = timezone.now()
        state.sync_token = state.generate_sync_token()
        state.save()
        
        return {
            "items": PriceAlertCompactSerializer(alerts, many=True).data,
            "total": alerts.count(),
            "sync_token": state.sync_token,
        }
    
    def _sync_preferences(self, user):
        """Sync user preferences."""
        preferences, _ = UserPreferences.objects.get_or_create(user=user)
        return UserPreferencesSerializer(preferences).data


# ============================================
# Deals
# ============================================

class MobileDealListView(APIView):
    """
    Optimized deal list for mobile.
    
    GET /api/mobile/deals/
    
    Query params:
    - cursor: Pagination cursor
    - limit: Items per page (max 50)
    - sort: relevance, price_low, price_high, rating
    """
    permission_classes = [AllowAny]
    
    def get(self, request):
        # Parse parameters
        cursor = request.query_params.get("cursor", "")
        limit = min(int(request.query_params.get("limit", 20)), 50)
        sort = request.query_params.get("sort", "relevance")
        
        # Get deals from service
        from deals.services.orchestrator import deal_orchestrator
        
        start_time = time.time()
        
        # Get featured/trending deals
        results = deal_orchestrator.search(
            query="trending deals",
            budget=None,
            limit=limit,
        )
        
        deals = results.get("deals", [])
        
        # Mark saved deals if authenticated
        saved_ids = set()
        if request.user.is_authenticated:
            from users.models import SavedDeal
            saved_ids = set(
                SavedDeal.objects.filter(user=request.user)
                .values_list("deal_id", flat=True)
            )
        
        # Add is_saved flag
        for deal in deals:
            deal["is_saved"] = deal.get("id", "") in saved_ids
        
        search_time = int((time.time() - start_time) * 1000)
        
        response = {
            "deals": MobileDealSerializer(deals, many=True).data,
            "total": len(deals),
            "cursor": None,  # TODO: Implement cursor pagination
            "has_more": False,
            "query": "trending",
            "search_time_ms": search_time,
            "sources_searched": results.get("sources_searched", []),
        }
        
        return Response(MobileSearchResponseSerializer(response).data)


class MobileDealSearchView(APIView):
    """
    Mobile-optimized search.
    
    POST /api/mobile/deals/search/
    
    Body:
    {
        "query": "sony camera",
        "min_price": 100,
        "max_price": 1000,
        "sources": ["amazon", "ebay"],
        "sort": "price_low",
        "cursor": "",
        "limit": 20
    }
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = MobileSearchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        data = serializer.validated_data
        
        from deals.services.orchestrator import deal_orchestrator
        
        start_time = time.time()
        
        # Build budget string if prices provided
        budget = None
        if data.get("max_price"):
            budget = f"under ${data['max_price']}"
        
        results = deal_orchestrator.search(
            query=data["query"],
            budget=budget,
            limit=data["limit"],
        )
        
        deals = results.get("deals", [])
        
        # Apply sorting
        sort = data.get("sort", "relevance")
        if sort == "price_low":
            deals.sort(key=lambda x: x.get("price", float("inf")))
        elif sort == "price_high":
            deals.sort(key=lambda x: x.get("price", 0), reverse=True)
        elif sort == "rating":
            deals.sort(key=lambda x: x.get("rating") or 0, reverse=True)
        
        # Filter by min price
        min_price = data.get("min_price")
        if min_price:
            deals = [d for d in deals if d.get("price", 0) >= float(min_price)]
        
        # Mark saved deals
        saved_ids = set()
        if request.user.is_authenticated:
            from users.models import SavedDeal
            saved_ids = set(
                SavedDeal.objects.filter(user=request.user)
                .values_list("deal_id", flat=True)
            )
        
        for deal in deals:
            deal["is_saved"] = deal.get("id", "") in saved_ids
        
        # Save search if authenticated
        if request.user.is_authenticated:
            from users.models import SearchHistory
            SearchHistory.objects.create(
                user=request.user,
                query=data["query"],
                parsed_product=results.get("parsed", {}).get("product", ""),
                parsed_budget=data.get("max_price"),
                results_count=len(deals),
            )
        
        search_time = int((time.time() - start_time) * 1000)
        
        response = {
            "deals": MobileDealSerializer(deals, many=True).data,
            "total": len(deals),
            "cursor": None,
            "has_more": False,
            "query": data["query"],
            "search_time_ms": search_time,
            "sources_searched": results.get("sources_searched", []),
        }
        
        return Response(MobileSearchResponseSerializer(response).data)


# ============================================
# Price Alerts
# ============================================

class PriceAlertListView(APIView):
    """
    Price alerts CRUD.
    
    GET /api/mobile/alerts/ - List alerts
    POST /api/mobile/alerts/ - Create alert
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        alerts = PriceAlert.objects.filter(
            user=request.user
        ).order_by("-created_at")
        
        # Filter by status
        status_filter = request.query_params.get("status")
        if status_filter:
            alerts = alerts.filter(status=status_filter)
        
        return Response({
            "alerts": PriceAlertSerializer(alerts, many=True).data,
            "count": alerts.count(),
        })
    
    def post(self, request):
        serializer = PriceAlertSerializer(
            data=request.data,
            context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        alert = serializer.save()
        
        return Response(
            PriceAlertSerializer(alert).data,
            status=status.HTTP_201_CREATED
        )


class PriceAlertDetailView(APIView):
    """
    Single price alert management.
    
    GET /api/mobile/alerts/{id}/
    PATCH /api/mobile/alerts/{id}/
    DELETE /api/mobile/alerts/{id}/
    """
    permission_classes = [IsAuthenticated]
    
    def get_alert(self, alert_id, user):
        try:
            return PriceAlert.objects.get(id=alert_id, user=user)
        except PriceAlert.DoesNotExist:
            return None
    
    def get(self, request, alert_id):
        alert = self.get_alert(alert_id, request.user)
        if not alert:
            return Response(
                {"error": "Alert not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        return Response(PriceAlertSerializer(alert).data)
    
    def patch(self, request, alert_id):
        alert = self.get_alert(alert_id, request.user)
        if not alert:
            return Response(
                {"error": "Alert not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = PriceAlertSerializer(
            alert,
            data=request.data,
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response(serializer.data)
    
    def delete(self, request, alert_id):
        alert = self.get_alert(alert_id, request.user)
        if not alert:
            return Response(
                {"error": "Alert not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        alert.delete()
        
        return Response(status=status.HTTP_204_NO_CONTENT)


# ============================================
# Favorites
# ============================================

class FavoritesView(APIView):
    """
    Saved deals / favorites.
    
    GET /api/mobile/favorites/
    POST /api/mobile/favorites/
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        from users.models import SavedDeal
        
        favorites = SavedDeal.objects.filter(
            user=request.user
        ).order_by("-created_at")
        
        items = [
            {
                "id": str(f.id),
                "deal_id": f.deal_id,
                "title": f.deal_data.get("title", ""),
                "price": f.deal_data.get("price"),
                "image": f.deal_data.get("image_url", ""),
                "source": f.deal_data.get("source", ""),
                "url": f.deal_data.get("url", ""),
                "saved_at": f.created_at,
            }
            for f in favorites[:100]
        ]
        
        return Response({
            "favorites": SavedDealMobileSerializer(items, many=True).data,
            "count": favorites.count(),
        })
    
    def post(self, request):
        from users.models import SavedDeal
        
        deal_id = request.data.get("deal_id")
        deal_data = request.data.get("deal_data", {})
        
        if not deal_id:
            return Response(
                {"error": "deal_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        favorite, created = SavedDeal.objects.get_or_create(
            user=request.user,
            deal_id=deal_id,
            defaults={"deal_data": deal_data}
        )
        
        return Response(
            {"id": str(favorite.id), "created": created},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )


class FavoriteDetailView(APIView):
    """
    Single favorite management.
    
    DELETE /api/mobile/favorites/{deal_id}/
    """
    permission_classes = [IsAuthenticated]
    
    def delete(self, request, deal_id):
        from users.models import SavedDeal
        
        deleted, _ = SavedDeal.objects.filter(
            user=request.user,
            deal_id=deal_id
        ).delete()
        
        if deleted:
            return Response(status=status.HTTP_204_NO_CONTENT)
        
        return Response(
            {"error": "Favorite not found"},
            status=status.HTTP_404_NOT_FOUND
        )
