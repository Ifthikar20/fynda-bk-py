"""
Mobile API Serializers

Optimized serializers for mobile with:
- Compact payloads (only essential fields)
- Nested includes to reduce API calls
- Pagination cursors for infinite scroll
- Sync metadata for offline support
"""

from rest_framework import serializers
from django.utils import timezone
from .models import DeviceToken, SyncState, UserPreferences, PriceAlert, MobileSession


class DeviceTokenSerializer(serializers.ModelSerializer):
    """Serializer for device registration."""
    
    class Meta:
        model = DeviceToken
        fields = [
            "id",
            "platform",
            "token",
            "device_id",
            "device_name",
            "app_version",
            "os_version",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["id", "is_active", "created_at"]
    
    def create(self, validated_data):
        """Create or update device token."""
        user = self.context["request"].user
        device_id = validated_data.get("device_id")
        
        # Update existing or create new
        device, created = DeviceToken.objects.update_or_create(
            user=user,
            device_id=device_id,
            defaults={
                **validated_data,
                "is_active": True,
            }
        )
        return device


class DeviceTokenCompactSerializer(serializers.ModelSerializer):
    """Compact device info for lists."""
    
    class Meta:
        model = DeviceToken
        fields = ["id", "platform", "device_name", "last_used_at"]


class UserPreferencesSerializer(serializers.ModelSerializer):
    """Full user preferences for sync."""
    
    class Meta:
        model = UserPreferences
        fields = [
            "push_enabled",
            "push_deals",
            "push_price_alerts",
            "push_weekly_digest",
            "theme",
            "currency",
            "language",
            "default_sort",
            "show_sold_items",
            "preferred_sources",
            "save_search_history",
            "anonymous_analytics",
            "updated_at",
        ]
        read_only_fields = ["updated_at"]
    
    def update(self, instance, validated_data):
        """Update preferences."""
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        return instance


class PriceAlertSerializer(serializers.ModelSerializer):
    """Full price alert details."""
    
    price_drop_percent = serializers.SerializerMethodField()
    
    class Meta:
        model = PriceAlert
        fields = [
            "id",
            "product_query",
            "product_name",
            "product_image",
            "product_url",
            "target_price",
            "original_price",
            "current_price",
            "lowest_price",
            "currency",
            "status",
            "is_active",
            "last_checked_at",
            "triggered_at",
            "price_drop_percent",
            "created_at",
        ]
        read_only_fields = [
            "id", "current_price", "lowest_price", "status",
            "last_checked_at", "triggered_at", "created_at"
        ]
    
    def get_price_drop_percent(self, obj):
        """Calculate percentage drop from original price."""
        if obj.original_price and obj.current_price:
            drop = ((obj.original_price - obj.current_price) / obj.original_price) * 100
            return round(drop, 1)
        return None
    
    def create(self, validated_data):
        """Create price alert for current user."""
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)


class PriceAlertCompactSerializer(serializers.ModelSerializer):
    """Compact price alert for lists."""
    
    class Meta:
        model = PriceAlert
        fields = [
            "id",
            "product_name",
            "product_image",
            "target_price",
            "current_price",
            "status",
        ]


class SyncStateSerializer(serializers.ModelSerializer):
    """Sync state for offline support."""
    
    class Meta:
        model = SyncState
        fields = [
            "entity_type",
            "last_sync_at",
            "sync_token",
            "server_version",
        ]


# ============================================
# Mobile-Optimized Deal Serializers
# ============================================

class MobileDealSerializer(serializers.Serializer):
    """
    Optimized deal serializer for mobile.
    
    - Smaller payload than web version
    - Only essential display fields
    - Pre-computed values (no client calculation)
    """
    
    id = serializers.CharField()
    title = serializers.CharField(max_length=100)  # Truncated for mobile
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
    original_price = serializers.DecimalField(max_digits=10, decimal_places=2, allow_null=True)
    discount = serializers.IntegerField(default=0)  # Pre-computed percent
    currency = serializers.CharField(default="USD")
    image = serializers.URLField(source="image_url")
    source = serializers.CharField()
    url = serializers.URLField()
    rating = serializers.FloatField(allow_null=True)
    in_stock = serializers.BooleanField(default=True)
    is_saved = serializers.BooleanField(default=False)  # User's saved status
    
    def to_representation(self, instance):
        """Optimize the output."""
        data = super().to_representation(instance)
        
        # Truncate title for mobile
        if data.get("title") and len(data["title"]) > 80:
            data["title"] = data["title"][:77] + "..."
        
        # Remove null values to reduce payload
        return {k: v for k, v in data.items() if v is not None}


class MobileDealDetailSerializer(serializers.Serializer):
    """
    Full deal details for product page.
    
    Includes more fields than list view.
    """
    
    id = serializers.CharField()
    title = serializers.CharField()
    description = serializers.CharField(allow_blank=True)
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
    original_price = serializers.DecimalField(max_digits=10, decimal_places=2, allow_null=True)
    discount = serializers.IntegerField(default=0)
    currency = serializers.CharField(default="USD")
    
    # Images
    images = serializers.ListField(child=serializers.URLField(), default=list)
    image = serializers.URLField(source="image_url")
    
    # Source info
    source = serializers.CharField()
    source_logo = serializers.URLField(allow_null=True)
    seller = serializers.CharField(allow_blank=True)
    seller_rating = serializers.FloatField(allow_null=True)
    url = serializers.URLField()
    
    # Product details
    rating = serializers.FloatField(allow_null=True)
    reviews_count = serializers.IntegerField(allow_null=True)
    in_stock = serializers.BooleanField(default=True)
    condition = serializers.CharField(allow_blank=True)
    shipping = serializers.CharField(allow_blank=True)
    
    # User context
    is_saved = serializers.BooleanField(default=False)
    
    # Related
    similar_count = serializers.IntegerField(default=0)


class MobileSearchSerializer(serializers.Serializer):
    """Optimized search request for mobile."""
    
    query = serializers.CharField(max_length=500)
    min_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    max_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    sources = serializers.ListField(child=serializers.CharField(), required=False)
    sort = serializers.ChoiceField(
        choices=["relevance", "price_low", "price_high", "rating", "newest"],
        default="relevance"
    )
    cursor = serializers.CharField(required=False, allow_blank=True)
    limit = serializers.IntegerField(min_value=1, max_value=50, default=20)


class MobileSearchResponseSerializer(serializers.Serializer):
    """Optimized search response for mobile."""
    
    deals = MobileDealSerializer(many=True)
    total = serializers.IntegerField()
    cursor = serializers.CharField(allow_null=True)
    has_more = serializers.BooleanField()
    
    # Search context
    query = serializers.CharField()
    search_time_ms = serializers.IntegerField()
    sources_searched = serializers.ListField(child=serializers.CharField())


# ============================================
# Sync Serializers
# ============================================

class SyncRequestSerializer(serializers.Serializer):
    """Request for sync pull."""
    
    entity_types = serializers.ListField(
        child=serializers.CharField(),
        default=["favorites", "alerts", "preferences"]
    )
    sync_tokens = serializers.DictField(
        child=serializers.CharField(),
        required=False,
        help_text="Map of entity_type -> last sync token"
    )
    full_sync = serializers.BooleanField(default=False)


class SyncResponseSerializer(serializers.Serializer):
    """Response for sync pull."""
    
    favorites = serializers.DictField(required=False)
    alerts = serializers.DictField(required=False)
    preferences = serializers.DictField(required=False)
    
    # New sync tokens for next request
    sync_tokens = serializers.DictField(child=serializers.CharField())
    
    # Sync metadata
    synced_at = serializers.DateTimeField()
    has_conflicts = serializers.BooleanField(default=False)


class SavedDealMobileSerializer(serializers.Serializer):
    """Saved deal for mobile sync."""
    
    id = serializers.CharField()
    deal_id = serializers.CharField()
    title = serializers.CharField()
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
    image = serializers.URLField()
    source = serializers.CharField()
    url = serializers.URLField()
    saved_at = serializers.DateTimeField()
    
    # Sync metadata
    local_id = serializers.CharField(required=False, allow_blank=True)
    deleted = serializers.BooleanField(default=False)


# ============================================
# Auth Serializers
# ============================================

class MobileLoginSerializer(serializers.Serializer):
    """Mobile login request."""
    
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    
    # Device info for binding
    device_id = serializers.CharField()
    device_name = serializers.CharField(required=False, allow_blank=True)
    platform = serializers.ChoiceField(choices=["ios", "android"])
    app_version = serializers.CharField(required=False, allow_blank=True)
    push_token = serializers.CharField(required=False, allow_blank=True)


class MobileLoginResponseSerializer(serializers.Serializer):
    """Mobile login response."""
    
    access_token = serializers.CharField()
    refresh_token = serializers.CharField()
    expires_in = serializers.IntegerField()
    
    # User info
    user = serializers.DictField()
    
    # Device binding
    device_id = serializers.CharField()
    
    # Preferences for initial sync
    preferences = UserPreferencesSerializer()


class MobileRegisterSerializer(serializers.Serializer):
    """Mobile registration request."""
    
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)
    
    # Device info
    device_id = serializers.CharField()
    platform = serializers.ChoiceField(choices=["ios", "android"])
    push_token = serializers.CharField(required=False, allow_blank=True)
    
    def validate_email(self, value):
        """Check email is not already registered."""
        from users.models import User
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already registered")
        return value


class HealthCheckSerializer(serializers.Serializer):
    """Mobile health check response."""
    
    status = serializers.CharField()
    server_time = serializers.DateTimeField()
    min_app_version = serializers.CharField()
    force_update = serializers.BooleanField()
    maintenance = serializers.BooleanField()
    message = serializers.CharField(required=False, allow_blank=True)
