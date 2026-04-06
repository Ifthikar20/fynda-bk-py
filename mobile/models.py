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

    # Location preferences
    default_latitude = models.FloatField(null=True, blank=True, help_text="Saved home latitude")
    default_longitude = models.FloatField(null=True, blank=True, help_text="Saved home longitude")
    default_location_name = models.CharField(max_length=255, blank=True, default="", help_text="e.g. New York, NY")
    max_distance_miles = models.PositiveIntegerField(
        default=25,
        help_text="Max distance in miles for local marketplace results"
    )

    # Style preferences
    preferred_gender = models.CharField(
        max_length=10,
        blank=True,
        default="",
        help_text="men, women, or unisex"
    )
    preferred_sizes = models.JSONField(
        default=list, blank=True,
        help_text='e.g. ["S", "M", "L"] or ["8", "10"]'
    )
    preferred_styles = models.JSONField(
        default=list, blank=True,
        help_text='e.g. ["casual", "streetwear", "modest"]'
    )

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


class FashionTimelineEntry(models.Model):
    """
    A single day's outfit in the Fashion Timeline.

    Users log what they wore each day. The timeline is shareable
    as a weekly or monthly calendar view.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="timeline_entries",
    )
    date = models.DateField(help_text="The day this outfit was worn")
    title = models.CharField(max_length=200, blank=True, default="")
    image_url = models.URLField(max_length=1000, blank=True, default="")
    outfit_data = models.JSONField(
        default=dict, blank=True,
        help_text='{"items": [{"title": "...", "image": "...", "source": "..."}], "notes": "..."}'
    )
    mood = models.CharField(max_length=50, blank=True, default="", help_text="e.g. cozy, bold, minimal")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "mobile_fashion_timeline"
        unique_together = [["user", "date"]]
        ordering = ["-date"]
        indexes = [
            models.Index(fields=["user", "date"]),
        ]

    def __str__(self):
        return f"{self.user.email} — {self.date} — {self.title or 'Outfit'}"


class DealAlert(models.Model):
    """
    Deal alerts — users describe what they want and get notified
    when matching deals are found.
    """

    STATUS_CHOICES = [
        ("active", "Active"),
        ("paused", "Paused"),
        ("disabled", "Disabled"),
    ]

    MAX_ALERTS_PER_USER = 5
    EXPIRY_DAYS = 30

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="deal_alerts",
    )
    description = models.CharField(max_length=500, help_text="e.g. black leather jacket under $100")
    search_query = models.CharField(max_length=500, blank=True, help_text="Normalized query for marketplace search (auto-generated)")
    reference_image = models.URLField(max_length=1000, blank=True, help_text="S3 URL of reference image")
    max_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="active")
    is_active = models.BooleanField(default=True)
    last_checked_at = models.DateTimeField(null=True, blank=True)
    matches_count = models.IntegerField(default=0)
    expires_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "mobile_deal_alerts"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["status"]),
        ]

    def save(self, *args, **kwargs):
        if not self.expires_at:
            from django.utils import timezone
            self.expires_at = timezone.now() + timezone.timedelta(days=self.EXPIRY_DAYS)
        if not self.search_query:
            self.search_query = self.description
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        from django.utils import timezone
        return self.expires_at and timezone.now() > self.expires_at

    def __str__(self):
        return f"{self.description[:50]} ({self.status})"


class DealAlertMatch(models.Model):
    """A deal that matched a user's alert."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    alert = models.ForeignKey(DealAlert, on_delete=models.CASCADE, related_name="matches")
    deal_id = models.CharField(max_length=255)
    title = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    image_url = models.URLField(max_length=1000, blank=True)
    source = models.CharField(max_length=100, blank=True)
    url = models.URLField(max_length=2000, blank=True)
    deal_data = models.JSONField(default=dict)
    is_seen = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "mobile_deal_alert_matches"
        ordering = ["-created_at"]
        unique_together = [["alert", "deal_id"]]
        indexes = [
            models.Index(fields=["alert", "is_seen"]),
        ]

    def __str__(self):
        return f"{self.title[:40]} — ${self.price}"


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


class APIUsageLog(models.Model):
    """
    Tracks API usage per user/IP for cost control and rate limiting.

    Records each expensive API call (image search, OpenAI vision, bg removal)
    to enforce daily quotas and monitor costs.
    """
    ENDPOINT_CHOICES = [
        ("image_search", "Image Search"),
        ("gemini_vision", "Gemini Vision"),
        ("openai_vision", "OpenAI Vision"),
        ("remove_bg", "Background Removal"),
        ("storyboard_upload", "Storyboard Image Upload"),
    ]

    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="api_usage_logs",
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    device_id = models.CharField(max_length=255, blank=True, default="")
    endpoint = models.CharField(max_length=50, choices=ENDPOINT_CHOICES)
    estimated_cost = models.DecimalField(
        max_digits=8, decimal_places=4, default=0,
        help_text="Estimated cost in USD",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "api_usage_logs"
        indexes = [
            models.Index(fields=["user", "endpoint", "created_at"]),
            models.Index(fields=["ip_address", "endpoint", "created_at"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        who = self.user.email if self.user else self.ip_address
        return f"{self.endpoint} by {who} at {self.created_at}"

    @classmethod
    def get_daily_count(cls, user=None, ip_address=None, endpoint=None):
        """Get usage count for today, always per user account."""
        from django.utils import timezone
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        qs = cls.objects.filter(created_at__gte=today_start)
        if user and user.is_authenticated:
            qs = qs.filter(user=user)
        elif ip_address:
            qs = qs.filter(ip_address=ip_address)
        if endpoint:
            qs = qs.filter(endpoint=endpoint)
        return qs.count()

    @classmethod
    def get_period_stats(cls, user, days=14, endpoint=None):
        """
        Get usage stats for a billing period (default: 14 days for biweekly sub).

        Returns: { count, total_cost, daily_avg }
        """
        from django.utils import timezone
        from django.db.models import Sum, Count
        period_start = timezone.now() - timezone.timedelta(days=days)
        qs = cls.objects.filter(user=user, created_at__gte=period_start)
        if endpoint:
            qs = qs.filter(endpoint=endpoint)
        agg = qs.aggregate(
            count=Count("id"),
            total_cost=Sum("estimated_cost"),
        )
        count = agg["count"] or 0
        total_cost = float(agg["total_cost"] or 0)
        return {
            "count": count,
            "total_cost": round(total_cost, 4),
            "daily_avg": round(count / max(days, 1), 1),
        }

    @classmethod
    def get_user_summary(cls, user):
        """Full usage summary for a user — for profile/admin display."""
        from django.utils import timezone
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)

        today_qs = cls.objects.filter(user=user, created_at__gte=today_start)
        today_image = today_qs.filter(endpoint="image_search").count()
        today_gemini = today_qs.filter(endpoint="gemini_vision").count()
        today_bg = today_qs.filter(endpoint="remove_bg").count()

        period_stats = cls.get_period_stats(user, days=14)

        return {
            "today": {
                "image_search": today_image,
                "gemini_vision": today_gemini,
                "remove_bg": today_bg,
            },
            "billing_period": period_stats,
        }

    @classmethod
    def log_usage(cls, request, endpoint, estimated_cost=0):
        """Log an API usage event."""
        user = request.user if request.user and request.user.is_authenticated else None
        ip = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip() or request.META.get("REMOTE_ADDR")
        device_id = request.headers.get("X-Device-Id", "")
        cls.objects.create(
            user=user,
            ip_address=ip,
            device_id=device_id,
            endpoint=endpoint,
            estimated_cost=estimated_cost,
        )
