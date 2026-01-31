"""
Mobile API Models

Models for mobile-specific features:
- Device registration for push notifications
- Sync state for offline support
- User preferences
- Price alerts
"""

import uuid
from django.db import models
from django.conf import settings


class DeviceToken(models.Model):
    """
    Device registration for push notifications.
    
    Stores FCM (Android) and APNs (iOS) tokens.
    """
    
    PLATFORM_CHOICES = [
        ("ios", "iOS"),
        ("android", "Android"),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="devices"
    )
    
    # Push notification token (FCM or APNs)
    token = models.CharField(max_length=500)
    platform = models.CharField(max_length=10, choices=PLATFORM_CHOICES)
    
    # Device identification
    device_id = models.CharField(max_length=255, help_text="Unique device identifier")
    device_name = models.CharField(max_length=255, blank=True, help_text="e.g., iPhone 15 Pro")
    
    # App info
    app_version = models.CharField(max_length=20, blank=True)
    os_version = models.CharField(max_length=20, blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    last_used_at = models.DateTimeField(auto_now=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "mobile_device_tokens"
        unique_together = [["user", "device_id"]]
        indexes = [
            models.Index(fields=["token"]),
            models.Index(fields=["user", "is_active"]),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.platform} ({self.device_name or self.device_id[:8]})"


class SyncState(models.Model):
    """
    Tracks sync state for offline support.
    
    Each entity type (deals, favorites, searches) has its own sync state.
    """
    
    ENTITY_TYPES = [
        ("favorites", "Saved Deals"),
        ("searches", "Search History"),
        ("alerts", "Price Alerts"),
        ("preferences", "User Preferences"),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sync_states"
    )
    
    entity_type = models.CharField(max_length=50, choices=ENTITY_TYPES)
    
    # Sync tracking
    last_sync_at = models.DateTimeField(null=True, blank=True)
    sync_token = models.CharField(
        max_length=255, 
        blank=True,
        help_text="Opaque cursor for incremental sync"
    )
    
    # Conflict resolution
    server_version = models.IntegerField(default=1)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "mobile_sync_states"
        unique_together = [["user", "entity_type"]]
    
    def __str__(self):
        return f"{self.user.email} - {self.entity_type}"
    
    def generate_sync_token(self):
        """Generate a new opaque sync token."""
        import hashlib
        import time
        data = f"{self.user_id}:{self.entity_type}:{time.time()}"
        return hashlib.sha256(data.encode()).hexdigest()[:32]


class UserPreferences(models.Model):
    """
    Mobile-specific user preferences.
    
    Synced between devices for consistent experience.
    """
    
    THEME_CHOICES = [
        ("light", "Light"),
        ("dark", "Dark"),
        ("system", "System Default"),
    ]
    
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="mobile_preferences"
    )
    
    # Push notification settings
    push_enabled = models.BooleanField(default=True)
    push_deals = models.BooleanField(default=True, help_text="New deal notifications")
    push_price_alerts = models.BooleanField(default=True, help_text="Price drop alerts")
    push_weekly_digest = models.BooleanField(default=False, help_text="Weekly summary")
    
    # Display settings
    theme = models.CharField(max_length=10, choices=THEME_CHOICES, default="system")
    currency = models.CharField(max_length=3, default="USD")
    language = models.CharField(max_length=10, default="en")
    
    # Search preferences
    default_sort = models.CharField(max_length=20, default="relevance")
    show_sold_items = models.BooleanField(default=False)
    preferred_sources = models.JSONField(default=list, blank=True)
    
    # Privacy
    save_search_history = models.BooleanField(default=True)
    anonymous_analytics = models.BooleanField(default=True)
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "mobile_user_preferences"
        verbose_name_plural = "User Preferences"
    
    def __str__(self):
        return f"Preferences for {self.user.email}"


class PriceAlert(models.Model):
    """
    Price alerts for product tracking.
    
    Users set target prices and get notified when products drop.
    """
    
    ALERT_STATUS = [
        ("active", "Active"),
        ("triggered", "Triggered"),
        ("expired", "Expired"),
        ("disabled", "Disabled"),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="price_alerts"
    )
    
    # Product info
    product_query = models.CharField(max_length=500)
    product_name = models.CharField(max_length=255, blank=True)
    product_image = models.URLField(max_length=1000, blank=True)
    product_url = models.URLField(max_length=2000, blank=True)
    
    # Pricing
    target_price = models.DecimalField(max_digits=10, decimal_places=2)
    original_price = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    current_price = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    lowest_price = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    currency = models.CharField(max_length=3, default="USD")
    
    # Status
    status = models.CharField(max_length=20, choices=ALERT_STATUS, default="active")
    is_active = models.BooleanField(default=True)
    
    # Tracking
    last_checked_at = models.DateTimeField(null=True, blank=True)
    triggered_at = models.DateTimeField(null=True, blank=True)
    notification_sent = models.BooleanField(default=False)
    
    # History
    price_history = models.JSONField(default=list, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "mobile_price_alerts"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["status"]),
        ]
    
    def __str__(self):
        return f"{self.product_query} @ ${self.target_price} ({self.status})"
    
    def check_price(self, new_price):
        """Check if price meets target and update status."""
        from django.utils import timezone
        
        self.current_price = new_price
        self.last_checked_at = timezone.now()
        
        # Update lowest price
        if self.lowest_price is None or new_price < self.lowest_price:
            self.lowest_price = new_price
        
        # Add to history
        self.price_history.append({
            "price": float(new_price),
            "timestamp": timezone.now().isoformat(),
        })
        # Keep last 30 entries
        self.price_history = self.price_history[-30:]
        
        # Check if triggered
        if new_price <= self.target_price and self.status == "active":
            self.status = "triggered"
            self.triggered_at = timezone.now()
            return True
        
        return False


class MobileSession(models.Model):
    """
    Track mobile app sessions for analytics and security.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="mobile_sessions",
        null=True,
        blank=True
    )
    device = models.ForeignKey(
        DeviceToken,
        on_delete=models.CASCADE,
        related_name="sessions",
        null=True,
        blank=True
    )
    
    # Session info
    session_token = models.CharField(max_length=255, unique=True)
    is_active = models.BooleanField(default=True)
    
    # Device context
    ip_address = models.GenericIPAddressField(null=True)
    user_agent = models.TextField(blank=True)
    
    # Timestamps
    started_at = models.DateTimeField(auto_now_add=True)
    last_activity_at = models.DateTimeField(auto_now=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = "mobile_sessions"
        indexes = [
            models.Index(fields=["session_token"]),
            models.Index(fields=["user", "is_active"]),
        ]
    
    def __str__(self):
        return f"Session {self.session_token[:8]}... ({self.user.email if self.user else 'anonymous'})"
