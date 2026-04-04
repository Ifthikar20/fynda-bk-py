from django.db import models
from django.conf import settings
import uuid


class SharedStoryboard(models.Model):
    """
    Stores shared storyboard data for public viewing.
    Anyone with the share token can view the storyboard.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    token = models.CharField(max_length=64, unique=True, db_index=True)
    
    # Owner (nullable for anonymous saves from mobile)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='shared_storyboards',
        null=True,
        blank=True,
    )
    device_id = models.CharField(max_length=128, blank=True, default='', db_index=True)
    
    # Storyboard data stored as JSON
    title = models.CharField(max_length=255, default='Fashion Storyboard')
    storyboard_data = models.JSONField(default=dict)

    # S3 snapshot image (permanent path, not signed URL)
    snapshot_path = models.CharField(max_length=500, blank=True, default='',
        help_text='S3 object key e.g. storyboard/abc123.jpg')
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    # View tracking
    view_count = models.PositiveIntegerField(default=0)
    
    # Settings
    is_public = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Shared Storyboard'
        verbose_name_plural = 'Shared Storyboards'
    
    def __str__(self):
        return f"{self.title} - {self.token[:8]}..."
    
    @classmethod
    def generate_token(cls):
        """Generate a unique share token"""
        return uuid.uuid4().hex[:16]
    
    def increment_views(self):
        """Increment view count"""
        self.view_count += 1
        self.save(update_fields=['view_count'])


# ============================================================
# Brand & Brand Likes
# ============================================================

class Brand(models.Model):
    """
    A clothing/fashion brand shown on the Explore page.
    Brands can be liked by users; likes_count is denormalized for fast sorting.
    """

    CATEGORY_CHOICES = [
        ("womens", "Women's Fashion"),
        ("mens", "Men's Fashion"),
        ("unisex", "Unisex"),
        ("shoes", "Shoes"),
        ("jewelry", "Jewelry"),
        ("beauty", "Beauty"),
        ("streetwear", "Streetwear"),
        ("activewear", "Activewear"),
        ("bags", "Bags & Accessories"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=150, unique=True)
    slug = models.SlugField(max_length=160, unique=True, db_index=True)
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default="unisex")

    # Visuals
    logo_url = models.URLField(blank=True)
    cover_image_url = models.URLField(blank=True)

    # Info
    description = models.TextField(blank=True)
    website_url = models.URLField(blank=True)
    shopify_domain = models.CharField(
        max_length=255, blank=True,
        help_text="Shopify store domain, links to ShopifyVendor",
    )

    # Flags
    is_featured = models.BooleanField(default=False, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)

    # Denormalized like counter (updated via signal)
    likes_count = models.PositiveIntegerField(default=0, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "brands"
        ordering = ["-likes_count", "-created_at"]
        indexes = [
            models.Index(fields=["-likes_count"]),
            models.Index(fields=["category", "-likes_count"]),
        ]

    def __str__(self):
        return self.name


class BrandLike(models.Model):
    """A like on a brand — one per user per brand."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="brand_likes",
    )
    brand = models.ForeignKey(
        Brand,
        on_delete=models.CASCADE,
        related_name="likes",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "brand_likes"
        unique_together = ["user", "brand"]

    def __str__(self):
        return f"{self.user} ♥ {self.brand.name}"


# ============================================================
# Pinterest Connection (OAuth token storage)
# ============================================================

class PinterestConnection(models.Model):
    """
    Stores a user's Pinterest OAuth2 tokens for auto-publishing.
    One per user — created when they connect their Pinterest account.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='pinterest_connection'
    )
    
    # OAuth tokens
    access_token = models.TextField()
    refresh_token = models.TextField(blank=True, default='')
    token_expires_at = models.DateTimeField(null=True, blank=True)
    
    # Pinterest user info
    pinterest_user_id = models.CharField(max_length=100, blank=True, default='')
    pinterest_username = models.CharField(max_length=150, blank=True, default='')
    
    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'pinterest_connections'
        verbose_name = 'Pinterest Connection'
        verbose_name_plural = 'Pinterest Connections'
    
    def __str__(self):
        return f"{self.user} → Pinterest ({self.pinterest_username or 'connected'})"
    
    @property
    def is_expired(self):
        """Check if the access token has expired."""
        from django.utils import timezone
        if not self.token_expires_at:
            return False
        return timezone.now() >= self.token_expires_at

