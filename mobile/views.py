"""
Mobile API Views

Endpoints optimized for mobile:
- Compact payloads
- Offline sync support
- Device registration
- Cursor-based pagination
"""

import time
import io
import base64
import logging
from django.utils import timezone
from django.db import transaction
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.parsers import MultiPartParser, FormParser
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
        from mobile.services import MobileDeviceService
        device, _ = MobileDeviceService.register_device(
            user=user,
            device_id=data["device_id"],
            platform=data["platform"],
            push_token=data.get("push_token", ""),
            device_name=data.get("device_name", ""),
            app_version=data.get("app_version", ""),
        )
        
        # Get or create preferences
        preferences, _ = MobileDeviceService.get_or_create_preferences(user)
        
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
        from mobile.services import MobileDeviceService
        device, _ = MobileDeviceService.register_device(
            user=user,
            device_id=data["device_id"],
            platform=data["platform"],
            push_token=data.get("push_token", ""),
        )
        
        # Create default preferences
        preferences, _ = MobileDeviceService.get_or_create_preferences(user)
        
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
            from mobile.services import MobileDeviceService
            MobileDeviceService.deactivate_device(request.user, device_id)
        
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
    - limit: Items per page (max 50)
    - sort: relevance, price_low, price_high, rating
    """
    permission_classes = [AllowAny]
    
    def get(self, request):
        from deals.services.orchestrator import orchestrator
        
        limit = min(int(request.query_params.get("limit", 20)), 50)
        sort = request.query_params.get("sort", "relevance")
        
        start_time = time.time()
        
        # Get featured/trending deals
        result = orchestrator.search("trending deals")
        result_dict = result.to_dict()
        
        deals = result_dict.get("deals", [])
        
        # Apply sorting
        if sort == "price_low":
            deals.sort(key=lambda x: x.get("price", float("inf")))
        elif sort == "price_high":
            deals.sort(key=lambda x: x.get("price", 0), reverse=True)
        elif sort == "rating":
            deals.sort(key=lambda x: x.get("rating") or 0, reverse=True)
        
        deals = deals[:limit]
        
        # Mark saved deals if authenticated
        saved_ids = set()
        if request.user.is_authenticated:
            from users.models import SavedDeal
            saved_ids = set(
                SavedDeal.objects.filter(user=request.user)
                .values_list("deal_id", flat=True)
            )
        
        for deal in deals:
            deal["is_saved"] = deal.get("id", "") in saved_ids
        
        search_time = int((time.time() - start_time) * 1000)
        
        response = {
            "deals": deals,  # Raw dicts — MobileSearchResponseSerializer handles serialization
            "total": len(deals),
            "cursor": None,
            "has_more": False,
            "query": "trending",
            "search_time_ms": search_time,
            "sources_searched": result_dict.get("meta", {}).get("sources_with_results", []),
        }
        
        # Propagate quota warning
        if result_dict.get("quota_warning"):
            response["quota_warning"] = result_dict["quota_warning"]
        
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
        "sort": "price_low",
        "limit": 20
    }
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = MobileSearchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        data = serializer.validated_data
        
        from deals.services.orchestrator import orchestrator
        
        start_time = time.time()
        
        # Build query with budget embedded (orchestrator parses it)
        query = data["query"]  # already sanitised by serializer
        if data.get("max_price"):
            query = f"{query} under ${data['max_price']}"
        
        # Embed gender in query so the parser picks it up
        gender = data.get("gender")
        if gender and gender not in query.lower():
            query = f"{gender}'s {query}"
        
        result = orchestrator.search(query)
        result_dict = result.to_dict()
        
        deals = result_dict.get("deals", [])
        
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
        
        # Filter by source/brand
        sources = data.get("sources")
        if sources:
            sources_lower = [s.lower() for s in sources]
            deals = [d for d in deals if d.get("source", "").lower() in sources_lower]
        
        # ── Pagination ────────────────────────────────
        total_deals = len(deals)
        offset = data.get("offset", 0)
        limit = data["limit"]
        deals = deals[offset:offset + limit]
        has_more = (offset + limit) < total_deals
        
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
            try:
                from users.models import SearchHistory
                SearchHistory.objects.create(
                    user=request.user,
                    query=data["query"],
                    parsed_product=result_dict.get("query", {}).get("product", ""),
                    parsed_budget=data.get("max_price"),
                    results_count=total_deals,
                )
            except Exception:
                pass  # Never let history saving break search
        
        search_time = int((time.time() - start_time) * 1000)
        
        response = {
            "deals": deals,  # Raw dicts — MobileSearchResponseSerializer handles serialization
            "total": total_deals,
            "offset": offset,
            "limit": limit,
            "cursor": None,
            "has_more": has_more,
            "query": data["query"],
            "search_time_ms": search_time,
            "sources_searched": result_dict.get("meta", {}).get("sources_with_results", []),
        }
        
        # Propagate quota warning
        if result_dict.get("quota_warning"):
            response["quota_warning"] = result_dict["quota_warning"]
        
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
        
        items = []
        for f in favorites[:100]:
            data = f.deal_data or {}
            items.append({
                "id": str(f.id),
                "deal_id": f.deal_id,
                "title": data.get("title", ""),
                "price": data.get("price"),
                "image": data.get("image_url") or data.get("image") or data.get("thumbnail") or "",
                "source": data.get("source", ""),
                "url": data.get("url", ""),
                "saved_at": f.created_at,
            })
        
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


# ============================================
# Image Upload (Core Flutter Feature)
# ============================================

class MobileImageUploadView(APIView):
    """
    Upload a photo to find matching deals.
    
    POST /api/mobile/deals/image-search/
    
    Request: multipart/form-data with 'image' field
    
    Response:
    {
        "extracted": { "caption": "...", "colors": {...}, ... },
        "search_queries": ["blue denim jacket", ...],
        "deals": [...],
        "total": 15,
        "search_time_ms": 2340,
        "quota_warning": "..." (optional)
    }
    """
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]
    
    def post(self, request):
        import requests as http_requests
        from deals.services.orchestrator import orchestrator
        
        from django.conf import settings
        
        if 'image' not in request.FILES:
            return Response(
                {"error": "No image file provided. Use 'image' field."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        image_file = request.FILES['image']
        
        # Validate file type
        allowed_types = ['image/jpeg', 'image/png', 'image/webp', 'image/gif']
        if image_file.content_type not in allowed_types:
            return Response(
                {"error": f"Invalid file type. Allowed: {', '.join(allowed_types)}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate file size (max 10MB)
        if image_file.size > 10 * 1024 * 1024:
            return Response(
                {"error": "File too large. Maximum size is 10MB."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        start_time = time.time()
        
        try:
            # Read and resize image
            image_data = image_file.read()
            
            from PIL import Image as PILImage
            pil_img = PILImage.open(io.BytesIO(image_data))
            if max(pil_img.size) > 800:
                pil_img.thumbnail((800, 800), PILImage.LANCZOS)
                logger.info(f"Resized upload to {pil_img.size}")
            # Convert RGBA/P to RGB (JPEG doesn't support transparency)
            if pil_img.mode in ('RGBA', 'P', 'LA'):
                background = PILImage.new('RGB', pil_img.size, (255, 255, 255))
                if pil_img.mode == 'P':
                    pil_img = pil_img.convert('RGBA')
                background.paste(pil_img, mask=pil_img.split()[-1])
                pil_img = background
            elif pil_img.mode != 'RGB':
                pil_img = pil_img.convert('RGB')
            buf = io.BytesIO()
            pil_img.save(buf, format='JPEG', quality=85)
            image_data = buf.getvalue()
            
            image_base64 = base64.b64encode(image_data).decode('utf-8')
            
            # Step 1: Identify the product
            extracted = None
            search_queries = []
            
            # Primary: Own ML service (BLIP)
            try:
                ml_url = getattr(settings, 'ML_SERVICE_URL', 'http://localhost:8001')
                ml_url = f"{ml_url}/analyze"
                logger.info(f"Calling ML service at {ml_url}")
                ml_response = http_requests.post(
                    ml_url,
                    json={"image_base64": image_base64},
                    timeout=30
                )
                if ml_response.status_code == 200:
                    ml_data = ml_response.json()
                    if ml_data.get("success"):
                        extracted = {
                            "caption": ml_data.get("caption", ""),
                            "colors": ml_data.get("colors", {}),
                            "textures": ml_data.get("textures", []),
                            "category": ml_data.get("category", ""),
                        }
                        search_queries = ml_data.get("search_queries", [])
                        logger.info(f"ML service identified: {search_queries}")
            except http_requests.RequestException as e:
                logger.warning(f"ML service unavailable: {e}")
            
            
            # If ML service returned no queries, return graceful empty
            if not search_queries:
                return Response({
                    "extracted": extracted or {},
                    "search_queries": [],
                    "deals": [],
                    "total": 0,
                    "search_time_ms": int((time.time() - start_time) * 1000),
                    "message": "Could not identify product. Try a clearer image."
                })
            
            # Step 2: Search for deals using generated queries (parallel)
            from concurrent.futures import ThreadPoolExecutor, as_completed
            all_deals = []
            quota_warning = None
            
            def search_query(q):
                try:
                    result = orchestrator.search(q)
                    result_dict = result.to_dict()
                    if result_dict.get("quota_warning"):
                        return result_dict["deals"], result_dict["quota_warning"]
                    return result_dict["deals"], None
                except Exception as e:
                    logger.warning(f"Search failed for '{q}': {e}")
                    return [], None
            
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = {executor.submit(search_query, q): q for q in search_queries[:3]}
                for future in as_completed(futures):
                    deals, warning = future.result()
                    if warning:
                        quota_warning = warning
                    for deal in deals:
                        if not any(d.get("id") == deal.get("id") for d in all_deals):
                            all_deals.append(deal)
            
            # Mark saved deals
            saved_ids = set()
            if request.user.is_authenticated:
                from users.models import SavedDeal
                saved_ids = set(
                    SavedDeal.objects.filter(user=request.user)
                    .values_list("deal_id", flat=True)
                )
            
            for deal in all_deals:
                deal["is_saved"] = deal.get("id", "") in saved_ids
            
            search_time = int((time.time() - start_time) * 1000)
            
            response = {
                "extracted": extracted or {},
                "search_queries": search_queries,
                "deals": MobileDealSerializer(all_deals, many=True).data,
                "total": len(all_deals),
                "search_time_ms": search_time,
            }
            
            if quota_warning:
                response["quota_warning"] = quota_warning
            
            return Response(response)
        
        except Exception as e:
            logger.exception(f"Image upload error: {e}")
            return Response(
                {"error": "Failed to process image. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# ============================================
# OAuth (Google/Apple with Device Binding)
# ============================================

class MobileOAuthView(APIView):
    """
    OAuth login for mobile with device binding.
    
    POST /api/mobile/auth/oauth/
    
    Body:
    {
        "provider": "google" | "apple",
        "code": "authorization_code",
        "redirect_uri": "callback_url",
        "device_id": "unique-device-id",
        "platform": "ios" | "android",
        "id_token": "apple_id_token" (Apple only),
        "user": {"name": {...}} (Apple first login only),
        "push_token": "fcm-or-apns-token" (optional)
    }
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        provider = request.data.get('provider', '').lower()
        code = request.data.get('code')
        redirect_uri = request.data.get('redirect_uri')
        device_id = request.data.get('device_id')
        platform = request.data.get('platform', 'ios')
        
        if not provider or not code:
            return Response(
                {"error": "Missing provider or code"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not device_id:
            return Response(
                {"error": "Missing device_id"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if provider not in ['google', 'apple']:
            return Response(
                {"error": "Invalid provider. Use 'google' or 'apple'"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from users.services import UserService
            from mobile.services import MobileDeviceService
            from core.exceptions import ValidationError as FyndaValidation, AuthenticationError
            
            # Build extra params for Apple
            extra_params = {}
            if provider == 'apple':
                extra_params['id_token'] = request.data.get('id_token')
                extra_params['user'] = request.data.get('user', {})
            
            # Exchange code for user info
            user_info = UserService.get_oauth_user_info(
                provider, code, redirect_uri, **extra_params
            )
            
            # Authenticate or create user
            user, created = UserService.authenticate_oauth(provider, user_info)
            
            # Generate tokens
            refresh = RefreshToken.for_user(user)
            
            # Register/update device
            device, _ = MobileDeviceService.register_device(
                user=user,
                device_id=device_id,
                platform=platform,
                push_token=request.data.get("push_token", ""),
            )
            
            # Get or create preferences
            preferences, _ = MobileDeviceService.get_or_create_preferences(user)
            
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
        
        except (FyndaValidation, ValueError) as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except AuthenticationError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_403_FORBIDDEN
            )
        except Exception:
            logger.exception("Mobile OAuth error")
            return Response(
                {"error": "OAuth authentication failed"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# ============================================
# Storyboard
# ============================================

class MobileStoryboardView(APIView):
    """
    Fashion storyboard management for mobile.
    
    GET /api/mobile/storyboard/ - List my shared storyboards
    POST /api/mobile/storyboard/ - Create a shared storyboard
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        from deals.models import SharedStoryboard
        
        boards = SharedStoryboard.objects.filter(
            user=request.user
        ).order_by("-created_at")[:50]
        
        items = [
            {
                "token": b.token,
                "title": b.title or "Untitled",
                "share_url": f"https://fynda.shop/storyboard/{b.token}",
                "storyboard_data": b.storyboard_data or {},
                "view_count": b.view_count,
                "created_at": b.created_at.isoformat(),
                "expires_at": b.expires_at.isoformat() if b.expires_at else None,
            }
            for b in boards
        ]
        
        return Response({"storyboards": items, "count": len(items)})
    
    def post(self, request):
        from deals.models import SharedStoryboard
        from datetime import timedelta
        import secrets
        
        storyboard_data = request.data.get("storyboard_data")
        if not storyboard_data:
            return Response(
                {"error": "storyboard_data is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        title = request.data.get("title", "")
        expires_in_days = int(request.data.get("expires_in_days", 30))
        
        board = SharedStoryboard.objects.create(
            user=request.user,
            token=secrets.token_urlsafe(16),
            title=title,
            storyboard_data=storyboard_data,
            expires_at=timezone.now() + timedelta(days=expires_in_days),
        )
        
        return Response(
            {
                "token": board.token,
                "share_url": f"https://fynda.shop/storyboard/{board.token}",
                "expires_at": board.expires_at.isoformat(),
            },
            status=status.HTTP_201_CREATED
        )


class MobileStoryboardDetailView(APIView):
    """
    Get or delete a shared storyboard by token.
    
    GET /api/mobile/storyboard/<token>/  (public)
    DELETE /api/mobile/storyboard/<token>/  (owner only)
    """
    permission_classes = [AllowAny]
    
    def get(self, request, token):
        from deals.models import SharedStoryboard
        
        try:
            board = SharedStoryboard.objects.get(token=token)
        except SharedStoryboard.DoesNotExist:
            return Response(
                {"error": "Storyboard not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check expiry
        if board.expires_at and board.expires_at < timezone.now():
            return Response(
                {"error": "This storyboard has expired"},
                status=status.HTTP_410_GONE
            )
        
        # Increment view count
        board.view_count += 1
        board.save(update_fields=["view_count"])
        
        return Response({
            "token": board.token,
            "title": board.title or "Untitled",
            "storyboard_data": board.storyboard_data,
            "view_count": board.view_count,
            "created_at": board.created_at.isoformat(),
        })

    def delete(self, request, token):
        from deals.models import SharedStoryboard
        
        if not request.user or not request.user.is_authenticated:
            return Response(
                {"error": "Authentication required"},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        try:
            board = SharedStoryboard.objects.get(token=token, user=request.user)
        except SharedStoryboard.DoesNotExist:
            return Response(
                {"error": "Storyboard not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        board.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ================================================================
# Favorites / Saved Deals
# ================================================================

class FavoritesView(APIView):
    """
    Mobile saved deals / favorites.
    
    GET  /api/mobile/favorites/     — list user's saved deals
    POST /api/mobile/favorites/     — save a deal
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        from users.models import SavedDeal
        
        favorites = SavedDeal.objects.filter(
            user=request.user
        ).order_by("-created_at")[:200]
        
        items = []
        for fav in favorites:
            data = fav.deal_data or {}
            items.append({
                "id": fav.deal_id,
                "deal_id": fav.deal_id,
                "title": data.get("title", ""),
                "description": data.get("description", ""),
                "price": data.get("price"),
                "original_price": data.get("original_price"),
                "discount": data.get("discount_percent", 0),
                "currency": data.get("currency", "USD"),
                "image": data.get("image_url") or data.get("image") or "",
                "source": data.get("source", ""),
                "seller": data.get("seller", ""),
                "url": data.get("url", ""),
                "rating": data.get("rating"),
                "reviews_count": data.get("reviews_count"),
                "in_stock": data.get("in_stock", True),
                "is_saved": True,
                "shipping": data.get("shipping", ""),
                "condition": data.get("condition", ""),
                "features": data.get("features", []),
                "saved_at": fav.created_at.isoformat() if fav.created_at else None,
            })
        
        return Response({
            "favorites": items,
            "count": len(items),
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
        
        # Update deal_data if re-saving
        if not created and deal_data:
            favorite.deal_data = deal_data
            favorite.save(update_fields=["deal_data"])
        
        return Response(
            {"id": str(favorite.id), "deal_id": deal_id, "created": created},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )


class FavoriteDetailView(APIView):
    """
    Single favorite management for mobile.
    
    DELETE /api/mobile/favorites/<deal_id>/  — unsave a deal
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
            {"error": "Saved deal not found"},
            status=status.HTTP_404_NOT_FOUND
        )

