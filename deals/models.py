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
    
    # Owner of the storyboard
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='shared_storyboards'
    )
    
    # Storyboard data stored as JSON
    title = models.CharField(max_length=255, default='Fashion Storyboard')
    storyboard_data = models.JSONField(default=dict)
    
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
