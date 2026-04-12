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
import json
import base64
import logging
from django.utils import timezone
from django.db import transaction
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
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

    # Feature flags per platform — set to False to hide from that platform
    PLATFORM_FEATURES = {
        "ios": {
            "image_search_enabled": True,
        },
        "android": {
            "image_search_enabled": True,
        },
        "web": {
            "image_search_enabled": False,
        },
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
            "features": self.PLATFORM_FEATURES.get(platform, self.PLATFORM_FEATURES["ios"]),
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


class UsageStatsView(APIView):
    """
    GET /api/mobile/usage/ — per-user API usage stats + remaining quota.

    Returns daily counts, bi-weekly totals, costs, and limits
    so the app can show "X searches remaining today".
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from mobile.models import APIUsageLog
        from payments.models import Subscription

        summary = APIUsageLog.get_user_summary(request.user)

        # Determine limits based on subscription
        is_premium = False
        try:
            is_premium = Subscription.objects.get(user=request.user).is_premium
        except Subscription.DoesNotExist:
            pass

        from outfi.throttles import DailyImageQuotaThrottle as Q
        daily_limit = Q.PREMIUM_DAILY_LIMIT if is_premium else Q.FREE_DAILY_LIMIT
        biweekly_limit = Q.PREMIUM_BIWEEKLY_LIMIT if is_premium else Q.FREE_BIWEEKLY_LIMIT

        today_used = summary["today"]["image_search"]
        biweekly_used = summary["billing_period"]["count"]

        return Response({
            "is_premium": is_premium,
            "today": {
                **summary["today"],
                "image_search_limit": daily_limit,
                "image_search_remaining": max(0, daily_limit - today_used),
            },
            "billing_period": {
                **summary["billing_period"],
                "limit": biweekly_limit,
                "remaining": max(0, biweekly_limit - biweekly_used),
                "period_days": 14,
            },
        })


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
        
        # Get fashion-specific trending deals
        result = orchestrator.search("trending women fashion clothing shoes accessories")
        result_dict = result.to_dict()
        
        deals = result_dict.get("deals", [])
        
        # Extra safety: remove deals without images (useless on mobile)
        deals = [d for d in deals if d.get("image") or d.get("image_url") or d.get("product_photo") or d.get("thumbnail")]
        
        # Remove novelty scenery/nature print items
        _SCENERY_BLOCKLIST = {
            "mountain", "scenery", "waterfall", "forest", "ocean view",
            "galaxy print", "aurora", "nebula", "sunset print", "sunrise print",
            "nature print", "landscape print", "wildlife", "3d print",
        }
        deals = [
            d for d in deals
            if not any(kw in (d.get("title") or "").lower() for kw in _SCENERY_BLOCKLIST)
        ]
        
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


class MobilePriceCompareView(APIView):
    """
    Compare a product's price against similar items.
    
    POST /api/mobile/deals/compare/
    
    Body: { "title": "...", "price": 29.58, "source": "Amazon" }
    
    Returns price_range, rating, position, compared_products, seller_count.
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        title = request.data.get("title", "")
        price = request.data.get("price")
        
        if not title or price is None:
            return Response(
                {"error": "title and price are required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            price = float(price)
        except (ValueError, TypeError):
            return Response(
                {"error": "price must be a number"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        from deals.services.orchestrator import orchestrator
        import statistics
        
        start_time = time.time()
        
        # Build a clean search query from the product title
        # Strip brand noise, years, size info, HTML entities, and filler words
        import re
        clean = re.sub(r'&#x27;|&amp;|&quot;', ' ', title)
        clean = re.sub(r'\b20\d{2}\b', '', clean)  # remove years like 2026
        clean = re.sub(r'\b[XSML]{1,3}L?\b', '', clean)  # remove sizes like XL, XXL
        clean = re.sub(r'\b(with|for|and|the|from|style|new|pack|set)\b', '', clean, flags=re.IGNORECASE)
        clean = re.sub(r'[-—|,].*', '', clean)  # take only text before dash/pipe/comma
        clean = re.sub(r'\s+', ' ', clean).strip()
        # Take meaningful words (skip very short ones)
        words = [w for w in clean.split() if len(w) > 2][:6]
        query = " ".join(words)
        
        try:
            result = orchestrator.search(query)
            result_dict = result.to_dict()
        except Exception as e:
            logger.warning(f"Price compare search failed: {e}")
            return Response({
                "price_range": {
                    "low": round(price * 0.7, 2),
                    "high": round(price * 1.3, 2),
                    "avg": round(price, 2),
                    "median": round(price, 2),
                },
                "rating": "fair",
                "position": 0.5,
                "compared_products": [],
                "seller_count": 0,
                "search_time_ms": int((time.time() - start_time) * 1000),
            })
        
        raw_deals = result_dict.get("deals", [])
        
        # Filter: must have price and image
        similar = []
        for d in raw_deals:
            d_price = d.get("price")
            if d_price is None:
                continue
            try:
                d_price = float(d_price)
            except (ValueError, TypeError):
                continue
            if d_price <= 0:
                continue
            
            img = (d.get("image") or d.get("image_url")
                   or d.get("product_photo") or d.get("thumbnail") or "")
            
            similar.append({
                "id": d.get("id", ""),
                "title": d.get("title", ""),
                "price": d_price,
                "image": img,
                "image_url": img,
                "original_price": d.get("original_price"),
                "discount": d.get("discount", 0),
                "currency": d.get("currency", "USD"),
                "source": d.get("source", ""),
                "seller": d.get("seller", ""),
                "url": d.get("url", ""),
                "rating": d.get("rating"),
                "reviews_count": d.get("reviews_count"),
                "in_stock": d.get("in_stock", True),
                "shipping": d.get("shipping", ""),
                "condition": d.get("condition", ""),
            })
        
        similar = similar[:10]
        
        # Compute price statistics
        prices = [s["price"] for s in similar]
        if not prices:
            prices = [price]
        
        low = min(prices)
        high = max(prices)
        avg = statistics.mean(prices)
        median = statistics.median(prices)
        
        rng = high - low
        if rng > 0:
            position = round((price - low) / rng, 3)
            position = max(0.0, min(1.0, position))
        else:
            position = 0.5
        
        if position < 0.35:
            rating = "great"
        elif position < 0.65:
            rating = "fair"
        else:
            rating = "high"
        
        search_time = int((time.time() - start_time) * 1000)
        
        return Response({
            "price_range": {
                "low": round(low, 2),
                "high": round(high, 2),
                "avg": round(avg, 2),
                "median": round(median, 2),
            },
            "rating": rating,
            "position": position,
            "compared_products": similar,
            "seller_count": len(similar),
            "search_time_ms": search_time,
        })


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

        # Load user preferences as fallback for location/gender
        prefs = None
        if request.user.is_authenticated:
            prefs = UserPreferences.objects.filter(user=request.user).first()

        # Build query with budget embedded (orchestrator parses it)
        query = data["query"]  # already sanitised by serializer
        if data.get("max_price"):
            query = f"{query} under ${data['max_price']}"

        # Embed gender in query — use preference as fallback
        gender = data.get("gender") or (prefs.preferred_gender if prefs else "")
        if gender and gender not in query.lower():
            query = f"{gender}'s {query}"

        # Set user location from request params or saved preferences
        lat = request.data.get("latitude")
        lng = request.data.get("longitude")
        max_dist = None
        if not lat and prefs and prefs.default_latitude:
            lat = prefs.default_latitude
            lng = prefs.default_longitude
        if prefs:
            max_dist = prefs.max_distance_miles
        if lat and lng:
            try:
                orchestrator.set_user_location(float(lat), float(lng), max_distance=max_dist)
            except (ValueError, TypeError):
                pass

        result = orchestrator.search(query)
        result_dict = result.to_dict()
        
        deals = result_dict.get("deals", [])
        
        # Remove deals without images (useless on mobile cards)
        deals = [d for d in deals if d.get("image") or d.get("image_url") or d.get("product_photo") or d.get("thumbnail")]
        
        # Remove novelty scenery/nature print items (passes fashion filter
        # because they contain "pants"/"jogger" but show mountain/scenery images)
        _SCENERY_BLOCKLIST = {
            "mountain", "scenery", "waterfall", "forest", "ocean view",
            "galaxy print", "aurora", "nebula", "sunset print", "sunrise print",
            "nature print", "landscape print", "wildlife", "3d print",
        }
        deals = [
            d for d in deals
            if not any(kw in (d.get("title") or "").lower() for kw in _SCENERY_BLOCKLIST)
        ]
        
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
# Deal Alerts
# ============================================

class DealAlertListView(APIView):
    """
    List and create deal alerts.

    GET  /api/mobile/deal-alerts/
    POST /api/mobile/deal-alerts/

    POST supports two modes:
    - Text only: {"description": "black jacket", "max_price": 100}
    - With image: multipart with 'image' file + optional 'description' + 'max_price'
      Image is analyzed once via Gemini to generate search_query.
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        from .models import DealAlert
        from .serializers import DealAlertSerializer

        alerts = DealAlert.objects.filter(user=request.user).order_by("-created_at")
        status_filter = request.query_params.get("status")
        if status_filter:
            alerts = alerts.filter(status=status_filter)
        data = DealAlertSerializer(alerts, many=True).data
        return Response({"alerts": data, "count": len(data)})

    def post(self, request):
        from .serializers import DealAlertSerializer
        from .models import APIUsageLog

        description = request.data.get("description", "").strip()
        max_price = request.data.get("max_price")
        search_query = ""
        reference_image_url = ""

        # If image provided, analyze with Gemini to generate search query
        if "image" in request.FILES:
            from core.image_preprocessor import preprocess_image, ImageValidationError
            from deals.services.gemini_vision_service import gemini_vision

            try:
                processed = preprocess_image(request.FILES["image"])
            except ImageValidationError as e:
                return Response({"error": e.message}, status=e.status_code)

            result = gemini_vision.analyze_image(processed.image_base64)
            if result and result.get("search_queries"):
                search_query = result["search_queries"][0]
                if not description:
                    # Use Gemini's description as the user-facing label
                    items = result.get("items", [{}])
                    item = items[0] if items else {}
                    parts = [item.get("color", ""), item.get("type", "")]
                    description = " ".join(p for p in parts if p) or search_query

                APIUsageLog.log_usage(request, "gemini_vision", estimated_cost=0.0025)
            else:
                return Response(
                    {"error": "Could not identify the item in this image. Try a clearer photo."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Store image to S3 if configured
            try:
                from django.core.files.storage import default_storage
                import uuid as _uuid
                ext = request.FILES["image"].name.rsplit(".", 1)[-1] if "." in request.FILES["image"].name else "jpg"
                path = f"deal-alerts/{_uuid.uuid4().hex[:12]}.{ext}"
                saved_path = default_storage.save(path, request.FILES["image"])
                reference_image_url = default_storage.url(saved_path)
            except Exception:
                pass  # Image storage is optional

        if not description:
            return Response(
                {"error": "Provide a description or upload an image."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = {"description": description}
        if max_price:
            data["max_price"] = max_price

        serializer = DealAlertSerializer(data=data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        alert = serializer.save()

        # Set generated fields
        if search_query:
            alert.search_query = search_query
        if reference_image_url:
            alert.reference_image = reference_image_url
        alert.save(update_fields=["search_query", "reference_image"])

        return Response(DealAlertSerializer(alert).data, status=status.HTTP_201_CREATED)


class DealAlertDetailView(APIView):
    """
    Single deal alert management.

    GET    /api/mobile/deal-alerts/{id}/
    PATCH  /api/mobile/deal-alerts/{id}/
    DELETE /api/mobile/deal-alerts/{id}/
    """
    permission_classes = [IsAuthenticated]

    def _get_alert(self, alert_id, user):
        from .models import DealAlert
        try:
            return DealAlert.objects.get(id=alert_id, user=user)
        except DealAlert.DoesNotExist:
            return None

    def get(self, request, alert_id):
        from .serializers import DealAlertDetailSerializer

        alert = self._get_alert(alert_id, request.user)
        if not alert:
            return Response({"error": "Alert not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(DealAlertDetailSerializer(alert).data)

    def patch(self, request, alert_id):
        from .serializers import DealAlertSerializer

        alert = self._get_alert(alert_id, request.user)
        if not alert:
            return Response({"error": "Alert not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = DealAlertSerializer(alert, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        alert = serializer.save()
        # Sync is_active with status
        alert.is_active = alert.status == "active"
        alert.save(update_fields=["is_active"])
        return Response(serializer.data)

    def delete(self, request, alert_id):
        alert = self._get_alert(alert_id, request.user)
        if not alert:
            return Response({"error": "Alert not found"}, status=status.HTTP_404_NOT_FOUND)
        alert.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class DealAlertMatchesView(APIView):
    """
    Matches for a deal alert.

    GET  /api/mobile/deal-alerts/{id}/matches/
    POST /api/mobile/deal-alerts/{id}/matches/  (mark seen)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, alert_id):
        from .models import DealAlert
        from .serializers import DealAlertMatchSerializer

        try:
            alert = DealAlert.objects.get(id=alert_id, user=request.user)
        except DealAlert.DoesNotExist:
            return Response({"error": "Alert not found"}, status=status.HTTP_404_NOT_FOUND)

        matches = alert.matches.all()
        if request.query_params.get("unseen_only") == "true":
            matches = matches.filter(is_seen=False)
        return Response({
            "matches": DealAlertMatchSerializer(matches[:50], many=True).data,
            "count": matches.count(),
        })

    def post(self, request, alert_id):
        from .models import DealAlert

        try:
            alert = DealAlert.objects.get(id=alert_id, user=request.user)
        except DealAlert.DoesNotExist:
            return Response({"error": "Alert not found"}, status=status.HTTP_404_NOT_FOUND)

        action = request.data.get("action")
        if action == "mark_all_seen":
            alert.matches.filter(is_seen=False).update(is_seen=True)
        elif action == "mark_seen":
            match_ids = request.data.get("match_ids", [])
            alert.matches.filter(id__in=match_ids).update(is_seen=True)
        return Response({"status": "ok"})


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
    
    from outfi.throttles import ImageUploadAnonThrottle, ImageUploadUserThrottle, ImageBurstThrottle, DailyImageQuotaThrottle
    throttle_classes = [ImageUploadAnonThrottle, ImageUploadUserThrottle, ImageBurstThrottle, DailyImageQuotaThrottle]

    def post(self, request):
        import requests as http_requests
        from deals.services.orchestrator import orchestrator
        from core.image_preprocessor import preprocess_image, cache_ml_result, ImageValidationError
        from mobile.models import APIUsageLog

        # Dedicated logger for tracing the full image search pipeline
        img_log = logging.getLogger("image_search")

        from django.conf import settings

        if 'image' not in request.FILES:
            return Response(
                {"error": "No image file provided. Use 'image' field."},
                status=status.HTTP_400_BAD_REQUEST
            )

        img_file = request.FILES['image']
        img_log.info("=" * 70)
        img_log.info("IMAGE SEARCH REQUEST")
        img_log.info(f"  User: {request.user if request.user.is_authenticated else 'anonymous'}")
        img_log.info(f"  File: {img_file.name}, size={img_file.size} bytes, type={img_file.content_type}")
        img_log.info("-" * 70)

        try:
            # Centralized image pre-processing (validate, resize, strip EXIF, hash dedup)
            processed = preprocess_image(img_file)
            image_base64 = processed.image_base64
            img_log.info(f"  Preprocessed: base64_len={len(image_base64)}, cache_key={processed.cache_key[:20]}...")

            # If identical image was recently processed, return cached ML result
            if processed.was_cached and processed.cached_result:
                img_log.info("  CACHE HIT — returning cached result")
                return Response(processed.cached_result)

        except ImageValidationError as e:
            img_log.error(f"  Image validation FAILED: {e.message}")
            return Response(
                {"error": e.message},
                status=e.status_code
            )
        
        start_time = time.time()

        try:

            # Step 1: Identify the product using Gemini Vision (primary)
            extracted = None
            search_queries = []

            # Primary: Google Gemini Vision
            gemini_key = getattr(settings, 'GEMINI_API_KEY', '')
            if gemini_key:
                img_log.info("[STEP 1] GEMINI VISION — analyzing image...")
                # Log Gemini API call (billed ~$0.0025/call for gemini-2.5-flash)
                APIUsageLog.log_usage(request, "gemini_vision", estimated_cost=0.0025)
                # Also log as image_search for daily quota tracking
                APIUsageLog.log_usage(request, "image_search", estimated_cost=0.0025)
                try:
                    from deals.services.gemini_vision_service import gemini_vision
                    result = gemini_vision.analyze_image(image_base64)
                    if result:
                        img_log.info(f"  Gemini RAW response: {json.dumps(result, indent=2, default=str)}")
                        if result.get("search_queries"):
                            items = result.get("items", [{}])
                            main_item = items[0] if items else {}
                            extracted = {
                                "caption": result.get("overall_style", ""),
                                "category": main_item.get("category", ""),
                                "type": main_item.get("type", ""),
                                "color": main_item.get("color", ""),
                                "brand": main_item.get("brand"),
                                "material": main_item.get("material", ""),
                                "pattern": main_item.get("pattern", ""),
                                "style": main_item.get("style", ""),
                            }
                            search_queries = result["search_queries"]
                            img_log.info(f"  Gemini EXTRACTED: {json.dumps(extracted, indent=2, default=str)}")
                            img_log.info(f"  Gemini SEARCH QUERIES: {search_queries}")
                        else:
                            img_log.warning("  Gemini returned data but NO search_queries")
                    else:
                        img_log.warning("  Gemini returned None")
                except Exception as e:
                    img_log.error(f"  Gemini FAILED: {e}", exc_info=True)
            else:
                img_log.warning("[STEP 1] GEMINI SKIPPED — no GEMINI_API_KEY configured")

            # If Gemini couldn't identify the product
            if not search_queries:
                img_log.error("  NO QUERIES GENERATED — returning empty to client")
                img_log.info("=" * 70)
                return Response({
                    "extracted": extracted or {},
                    "search_queries": [],
                    "deals": [],
                    "total": 0,
                    "search_time_ms": int((time.time() - start_time) * 1000),
                    "message": "Could not identify product. Try a clearer image."
                })
            
            # Pass user location to orchestrator for distance calculation
            # Fall back to saved preferences if not provided in request
            user_lat = request.data.get('latitude') or request.POST.get('latitude')
            user_lng = request.data.get('longitude') or request.POST.get('longitude')
            max_dist = None
            if request.user.is_authenticated:
                prefs = UserPreferences.objects.filter(user=request.user).first()
                if prefs:
                    max_dist = prefs.max_distance_miles
                    if not user_lat and prefs.default_latitude:
                        user_lat = prefs.default_latitude
                        user_lng = prefs.default_longitude
                        img_log.info(f"  Using saved location preference: lat={user_lat}, lng={user_lng}")
            if user_lat and user_lng:
                try:
                    orchestrator.set_user_location(float(user_lat), float(user_lng), max_distance=max_dist)
                    img_log.info(f"  User location: lat={user_lat}, lng={user_lng}, max_dist={max_dist}mi")
                except (ValueError, TypeError):
                    img_log.warning(f"  Invalid user location: lat={user_lat}, lng={user_lng}")

            # Step 2: Search for deals using top 2 queries in parallel
            # (skip CLIP reranking — Gemini already provides visual matching)
            queries_to_search = search_queries[:2]
            img_log.info(f"[STEP 2] VENDOR SEARCH — querying marketplaces with {len(queries_to_search)} queries")
            for i, q in enumerate(queries_to_search):
                img_log.info(f"  Query {i+1}: '{q}'")

            from concurrent.futures import ThreadPoolExecutor, as_completed
            all_deals = []
            seen_ids = set()
            quota_warning = None

            def search_query(q):
                try:
                    result = orchestrator.search(q, skip_clip=True)
                    result_dict = result.to_dict()
                    meta = result_dict.get("meta", {})
                    img_log.info(
                        f"  Query '{q}' → {meta.get('total_results', 0)} results "
                        f"from {meta.get('sources_with_results', [])} "
                        f"in {meta.get('search_time_ms', 0)}ms "
                        f"(cache={'HIT' if meta.get('cache_hit') else 'MISS'})"
                    )
                    if result_dict.get("quota_warning"):
                        return result_dict["deals"], result_dict["quota_warning"]
                    return result_dict["deals"], None
                except Exception as e:
                    img_log.error(f"  Query '{q}' FAILED: {e}")
                    return [], None

            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = {executor.submit(search_query, q): q for q in queries_to_search}
                for future in as_completed(futures):
                    deals, warning = future.result()
                    if warning:
                        quota_warning = warning
                    for deal in deals:
                        deal_id = deal.get("id", "")
                        if deal_id not in seen_ids:
                            seen_ids.add(deal_id)
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

            img_log.info(f"[STEP 3] RESPONSE — building final response")
            img_log.info(f"  Total deals found: {len(all_deals)}")
            img_log.info(f"  Total search time: {search_time}ms")
            if all_deals:
                for i, d in enumerate(all_deals[:5]):
                    img_log.info(f"  Deal {i+1}: '{d.get('title', '?')[:60]}' | ${d.get('price', '?')} | {d.get('source', '?')}")
                if len(all_deals) > 5:
                    img_log.info(f"  ... and {len(all_deals) - 5} more")
            if quota_warning:
                img_log.warning(f"  QUOTA WARNING: {quota_warning}")
            img_log.info("=" * 70)

            response = {
                "extracted": extracted or {},
                "search_queries": search_queries,
                "deals": MobileDealSerializer(all_deals, many=True).data,
                "total": len(all_deals),
                "search_time_ms": search_time,
            }

            if quota_warning:
                response["quota_warning"] = quota_warning

            # Cache result against image hash for dedup
            cache_ml_result(processed.cache_key, response)

            return Response(response)

        except Exception as e:
            img_log.exception(f"IMAGE SEARCH FATAL ERROR: {e}")
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
            from core.exceptions import ValidationError as OutfiValidation, AuthenticationError
            
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
        
        except (OutfiValidation, ValueError) as e:
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

    GET /api/mobile/storyboard/ - List my storyboards (auth → user, anon → device_id)
    POST /api/mobile/storyboard/ - Create a storyboard (anyone)
    """
    permission_classes = [AllowAny]

    def get(self, request):
        from deals.models import SharedStoryboard

        if request.user and request.user.is_authenticated:
            boards = SharedStoryboard.objects.filter(user=request.user)
        else:
            device_id = request.headers.get("X-Device-Id", "")
            if not device_id:
                return Response({"storyboards": [], "count": 0})
            # Anonymous users can only see their own boards by device_id
            # This is safe because device_id is a UUID generated on-device
            # and not enumerable (unlike the old IDOR where any header value worked)
            boards = SharedStoryboard.objects.filter(
                device_id=device_id, user__isnull=True
            )
        
        boards = boards.order_by("-created_at")[:50]
        
        items = [
            {
                "token": b.token,
                "title": b.title or "Untitled",
                "share_url": f"https://outfi.ai/storyboard/{b.token}",
                "snapshot_url": self._snapshot_url(b),
                "is_public": b.is_public,
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

        board_log = logging.getLogger("storyboard")
        board_log.info(f"[STORYBOARD CREATE] user={request.user.email if request.user.is_authenticated else 'anonymous'}")
        board_log.info(f"  request keys: {list(request.data.keys())}")

        storyboard_data = request.data.get("storyboard_data")
        if not storyboard_data:
            board_log.warning("  REJECTED: storyboard_data missing")
            return Response(
                {"error": "storyboard_data is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        title = request.data.get("title", "")
        expires_in_days = int(request.data.get("expires_in_days", 30))
        snapshot_path = request.data.get("snapshot_path", "")

        board_log.info(f"  title='{title}' snapshot_path='{snapshot_path}'")
        board_log.info(f"  storyboard_data type={type(storyboard_data).__name__} "
                       f"keys={list(storyboard_data.keys()) if isinstance(storyboard_data, dict) else 'N/A'}")

        try:
            board = SharedStoryboard.objects.create(
                user=request.user if request.user.is_authenticated else None,
                device_id=request.headers.get("X-Device-Id", ""),
                token=secrets.token_urlsafe(16),
                title=title,
                storyboard_data=storyboard_data,
                snapshot_path=snapshot_path,
                expires_at=timezone.now() + timedelta(days=expires_in_days),
            )
            board_log.info(f"  SAVED: token={board.token} id={board.id}")
        except Exception as e:
            board_log.exception(f"  SAVE FAILED: {e}")
            return Response(
                {"error": f"Failed to save storyboard: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {
                "token": board.token,
                "title": board.title,
                "share_url": f"https://outfi.ai/storyboard/{board.token}",
                "snapshot_url": self._snapshot_url(board),
                "storyboard_data": board.storyboard_data,
                "created_at": board.created_at.isoformat(),
                "expires_at": board.expires_at.isoformat(),
            },
            status=status.HTTP_201_CREATED
        )

    @staticmethod
    def _snapshot_url(board):
        if not board.snapshot_path:
            return ""
        from django.conf import settings as s
        bucket = getattr(s, 'AWS_STORAGE_BUCKET_NAME', '')
        region = getattr(s, 'AWS_S3_REGION_NAME', 'us-east-1')
        if bucket:
            return f"https://{bucket}.s3.{region}.amazonaws.com/{board.snapshot_path}"
        # Local storage — build full URL via API host
        path = board.snapshot_path
        if not path.startswith('/media/'):
            path = f"/media/{path}" if not path.startswith('media/') else f"/{path}"
        return f"https://api.outfi.ai{path}"


class MobileStoryboardDetailView(APIView):
    """
    Get, update, or delete a shared storyboard by token.

    GET /api/mobile/storyboard/<token>/     (public — view by share link)
    DELETE /api/mobile/storyboard/<token>/  (owner only — auth required)
    PUT /api/mobile/storyboard/<token>/     (owner only — auth required)
    """
    permission_classes = [AllowAny]

    def get(self, request, token):
        """Public view — anyone with the token can view (if is_public=True)."""
        from deals.models import SharedStoryboard

        try:
            board = SharedStoryboard.objects.get(token=token)
        except SharedStoryboard.DoesNotExist:
            return Response(
                {"error": "Storyboard not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Private boards only visible to the owner
        if not board.is_public:
            if not request.user.is_authenticated or board.user_id != request.user.id:
                return Response(
                    {"error": "Storyboard not found"},
                    status=status.HTTP_404_NOT_FOUND
                )

        if board.expires_at and board.expires_at < timezone.now():
            return Response(
                {"error": "This storyboard has expired"},
                status=status.HTTP_410_GONE
            )

        board.view_count += 1
        board.save(update_fields=["view_count"])

        return Response({
            "token": board.token,
            "title": board.title or "Untitled",
            "share_url": f"https://outfi.ai/storyboard/{board.token}",
            "storyboard_data": board.storyboard_data,
            "view_count": board.view_count,
            "is_public": board.is_public,
            "created_at": board.created_at.isoformat(),
        })

    def _get_owner_board(self, request, token):
        """Get board only if the user owns it (by user account or device_id)."""
        from deals.models import SharedStoryboard

        try:
            board = SharedStoryboard.objects.get(token=token)
        except SharedStoryboard.DoesNotExist:
            return None, Response(
                {"error": "Storyboard not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check ownership: authenticated user OR matching device_id
        if request.user and request.user.is_authenticated and board.user_id == request.user.id:
            return board, None

        device_id = request.headers.get("X-Device-Id", "")
        if device_id and board.device_id == device_id and board.user is None:
            return board, None

        return None, Response(
            {"error": "Storyboard not found"},
            status=status.HTTP_404_NOT_FOUND
        )

    def delete(self, request, token):
        board, err = self._get_owner_board(request, token)
        if err:
            return err
        board.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def put(self, request, token):
        """Update an existing storyboard (owner only)."""
        board_log = logging.getLogger("storyboard")
        board_log.info(f"[STORYBOARD UPDATE] token={token} user={request.user.email if request.user.is_authenticated else 'anonymous'}")
        board_log.info(f"  request keys: {list(request.data.keys())}")

        board, err = self._get_owner_board(request, token)
        if err:
            board_log.warning(f"  REJECTED: board not found or not owner")
            return err

        update_fields = []
        if "title" in request.data:
            board.title = request.data["title"]
            update_fields.append("title")
        if "storyboard_data" in request.data:
            board.storyboard_data = request.data["storyboard_data"]
            update_fields.append("storyboard_data")
        if "snapshot_path" in request.data and request.data["snapshot_path"]:
            board.snapshot_path = request.data["snapshot_path"]
            update_fields.append("snapshot_path")
        if "is_public" in request.data:
            board.is_public = bool(request.data["is_public"])
            update_fields.append("is_public")

        if update_fields:
            board.save(update_fields=update_fields)

        return Response({
            "token": board.token,
            "title": board.title,
            "share_url": f"https://outfi.ai/storyboard/{board.token}",
            "snapshot_url": MobileStoryboardView._snapshot_url(board),
            "storyboard_data": board.storyboard_data,
            "is_public": board.is_public,
        })


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


# ============================================
# Featured Content
# ============================================

class MobileFeaturedView(APIView):
    """
    Featured content for mobile home screen.

    GET /api/mobile/featured/

    Returns curated brands, search prompts, and quick suggestions
    from the same source as the web frontend.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        from deals.featured import FEATURED_BRANDS, SEARCH_PROMPTS, QUICK_SUGGESTIONS

        return Response({
            "featured_brands": FEATURED_BRANDS,
            "search_prompts": SEARCH_PROMPTS,
            "quick_suggestions": QUICK_SUGGESTIONS,
        })


# ============================================
# Fashion Timeline
# ============================================

class FashionTimelineView(APIView):
    """
    GET  /api/mobile/timeline/?month=2026-04  — list entries for month
    POST /api/mobile/timeline/                — add/update a day's outfit
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .models import FashionTimelineEntry
        from datetime import date

        month_str = request.query_params.get("month", "")
        if month_str:
            try:
                year, month = month_str.split("-")
                start = date(int(year), int(month), 1)
                if int(month) == 12:
                    end = date(int(year) + 1, 1, 1)
                else:
                    end = date(int(year), int(month) + 1, 1)
            except (ValueError, IndexError):
                start = date.today().replace(day=1)
                end = (start.replace(month=start.month + 1) if start.month < 12
                       else start.replace(year=start.year + 1, month=1))
        else:
            start = date.today().replace(day=1)
            end = (start.replace(month=start.month + 1) if start.month < 12
                   else start.replace(year=start.year + 1, month=1))

        entries = FashionTimelineEntry.objects.filter(
            user=request.user,
            date__gte=start,
            date__lt=end,
        )

        return Response({
            "month": start.strftime("%Y-%m"),
            "entries": [
                {
                    "id": str(e.id),
                    "date": e.date.isoformat(),
                    "title": e.title,
                    "image_url": e.image_url,
                    "outfit_data": e.outfit_data,
                    "mood": e.mood,
                }
                for e in entries
            ],
        })

    def post(self, request):
        from .models import FashionTimelineEntry
        from datetime import date as date_cls

        date_str = request.data.get("date")
        if not date_str:
            return Response({"error": "date is required (YYYY-MM-DD)"},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            entry_date = date_cls.fromisoformat(date_str)
        except ValueError:
            return Response({"error": "Invalid date format"},
                            status=status.HTTP_400_BAD_REQUEST)

        entry, created = FashionTimelineEntry.objects.update_or_create(
            user=request.user,
            date=entry_date,
            defaults={
                "title": request.data.get("title", ""),
                "image_url": request.data.get("image_url", ""),
                "outfit_data": request.data.get("outfit_data", {}),
                "mood": request.data.get("mood", ""),
            },
        )

        return Response({
            "id": str(entry.id),
            "date": entry.date.isoformat(),
            "title": entry.title,
            "image_url": entry.image_url,
            "outfit_data": entry.outfit_data,
            "mood": entry.mood,
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class FashionTimelineDetailView(APIView):
    """DELETE /api/mobile/timeline/<date>/ — remove an entry."""
    permission_classes = [IsAuthenticated]

    def delete(self, request, date_str):
        from .models import FashionTimelineEntry
        deleted, _ = FashionTimelineEntry.objects.filter(
            user=request.user, date=date_str
        ).delete()
        if not deleted:
            return Response({"error": "Entry not found"},
                            status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


class FashionTimelineShareView(APIView):
    """
    POST /api/mobile/timeline/share/ — generate a shareable storyboard from timeline.

    Takes a date range and creates a SharedStoryboard with the outfit calendar.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from .models import FashionTimelineEntry
        from deals.models import SharedStoryboard
        from datetime import date as date_cls
        import secrets

        start_str = request.data.get("start_date")
        end_str = request.data.get("end_date")
        if not start_str or not end_str:
            return Response({"error": "start_date and end_date required"},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            start = date_cls.fromisoformat(start_str)
            end = date_cls.fromisoformat(end_str)
        except ValueError:
            return Response({"error": "Invalid date format"},
                            status=status.HTTP_400_BAD_REQUEST)

        entries = FashionTimelineEntry.objects.filter(
            user=request.user,
            date__gte=start,
            date__lte=end,
        )

        timeline_data = {
            "type": "fashion_timeline",
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "entries": [
                {
                    "date": e.date.isoformat(),
                    "title": e.title,
                    "image_url": e.image_url,
                    "mood": e.mood,
                    "outfit_data": e.outfit_data,
                }
                for e in entries
            ],
        }

        from datetime import timedelta
        board = SharedStoryboard.objects.create(
            user=request.user,
            token=secrets.token_urlsafe(16),
            title=f"My Fashion Timeline — {start.strftime('%b %d')} to {end.strftime('%b %d, %Y')}",
            storyboard_data=timeline_data,
            expires_at=timezone.now() + timedelta(days=30),
        )

        return Response({
            "token": board.token,
            "share_url": f"https://outfi.ai/storyboard/{board.token}",
            "title": board.title,
            "entries_count": entries.count(),
        }, status=status.HTTP_201_CREATED)


# ============================================
# Storyboard Image Upload (S3)
# ============================================

class StoryboardImageUploadView(APIView):
    """
    Upload images for fashion boards to S3.

    POST /api/mobile/storyboard/upload-image/

    Accepts multipart image upload, validates, resizes,
    saves to S3, and returns a signed URL.

    Rate limited: 30/hour per user, 10/hour anonymous.
    Max file size: 5MB.
    """
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
    ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
    MAX_DIMENSION = 1200  # Resize to max 1200px

    def post(self, request):
        import uuid
        import secrets
        from PIL import Image
        from django.core.files.base import ContentFile
        from django.core.files.storage import default_storage

        image_file = request.FILES.get("image")
        if not image_file:
            return Response(
                {"error": "No image file provided"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate file size
        if image_file.size > self.MAX_FILE_SIZE:
            return Response(
                {"error": f"File too large. Maximum size is {self.MAX_FILE_SIZE // (1024*1024)}MB"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate content type
        content_type = image_file.content_type or ""
        if content_type not in self.ALLOWED_TYPES:
            return Response(
                {"error": f"Invalid file type: {content_type}. Allowed: JPEG, PNG, WebP"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # Open and validate image
            img = Image.open(image_file)
            img.verify()
            image_file.seek(0)
            img = Image.open(image_file)

            # Strip EXIF for privacy
            if img.mode in ("RGBA", "LA"):
                background = Image.new("RGBA", img.size, (255, 255, 255, 255))
                background.paste(img, mask=img.split()[-1])
                img = background.convert("RGB")
            elif img.mode != "RGB":
                img = img.convert("RGB")

            # Resize if too large
            if max(img.size) > self.MAX_DIMENSION:
                img.thumbnail((self.MAX_DIMENSION, self.MAX_DIMENSION), Image.LANCZOS)

            # Save to buffer
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=85, optimize=True)
            buffer.seek(0)

            # Generate unique filename
            unique_id = secrets.token_hex(8)
            filename = f"storyboard/{unique_id}.jpg"

            # Save to storage (S3 or local depending on config)
            content = ContentFile(buffer.read())
            saved_path = default_storage.save(filename, content)

            # Build a permanent (non-signed) URL for shared images.
            # Signed URLs expire after 1 hour — useless for sharing.
            from django.conf import settings as django_settings
            bucket = getattr(django_settings, 'AWS_STORAGE_BUCKET_NAME', '')
            region = getattr(django_settings, 'AWS_S3_REGION_NAME', 'us-east-1')

            if bucket:
                # Permanent S3 URL (requires bucket policy to allow public reads
                # on the storyboard/ prefix)
                image_url = f"https://{bucket}.s3.{region}.amazonaws.com/{saved_path}"
            else:
                # Local dev fallback
                image_url = default_storage.url(saved_path)

            return Response(
                {
                    "url": image_url,
                    "path": saved_path,
                    "size": content.size,
                },
                status=status.HTTP_201_CREATED,
            )

        except Exception as e:
            logger.exception("Storyboard image upload failed")
            return Response(
                {"error": "Image processing failed"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

