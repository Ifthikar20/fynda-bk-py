"""
Blog Models - SEO-optimized blog for Fynda
"""

from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.conf import settings


class Category(models.Model):
    """Blog post category for organization."""
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    description = models.TextField(blank=True)
    
    class Meta:
        verbose_name_plural = "Categories"
        ordering = ['name']
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    
    def __str__(self):
        return self.name
    
    def get_absolute_url(self):
        # Return full URL for admin "View on site" to point to outfi.ai
        path = reverse('blog:category_posts', kwargs={'slug': self.slug})
        return f"{settings.SITE_URL}{path}"


class Tag(models.Model):
    """Tags for blog posts."""
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=50, unique=True, blank=True)
    
    class Meta:
        ordering = ['name']
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    
    def __str__(self):
        return self.name


class Post(models.Model):
    """Blog post with full SEO support."""
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('published', 'Published'),
    ]
    
    # Core fields
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='blog_posts'
    )
    
    # Content
    excerpt = models.TextField(
        max_length=300,
        help_text="Short description for SEO meta description (max 300 chars)"
    )
    content = models.TextField()
    featured_image = models.ImageField(
        upload_to='blog/images/',
        blank=True,
        null=True,
        help_text="Featured image for post and social sharing"
    )
    
    # Organization
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='posts'
    )
    tags = models.ManyToManyField(Tag, blank=True, related_name='posts')
    
    # Status and timestamps
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='draft')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)
    
    # SEO fields
    meta_title = models.CharField(
        max_length=60,
        blank=True,
        help_text="SEO title (max 60 chars). Leave blank to use post title."
    )
    meta_description = models.CharField(
        max_length=160,
        blank=True,
        help_text="SEO description (max 160 chars). Leave blank to use excerpt."
    )
    
    class Meta:
        ordering = ['-published_at', '-created_at']
        indexes = [
            models.Index(fields=['-published_at']),
            models.Index(fields=['slug']),
            models.Index(fields=['status']),
        ]
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        if self.status == 'published' and not self.published_at:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)
    
    def __str__(self):
        return self.title
    
    def get_absolute_url(self):
        # Return full URL for admin "View on site" to point to outfi.ai
        path = reverse('blog:post_detail', kwargs={'slug': self.slug})
        return f"{settings.SITE_URL}{path}"
    
    @property
    def seo_title(self):
        """Return SEO title or fallback to post title."""
        return self.meta_title or f"{self.title} | Fynda Blog"
    
    @property
    def seo_description(self):
        """Return SEO description or fallback to excerpt."""
        return self.meta_description or self.excerpt[:160]
    
    @property
    def reading_time(self):
        """Estimate reading time in minutes."""
        word_count = len(self.content.split())
        return max(1, round(word_count / 200))


class ContentSection(models.Model):
    """
    Ordered content sections within a blog post.
    Allows for rich editorial layouts with text, brand showcases, and galleries.
    """
    SECTION_TYPES = [
        ('text', 'Text Block'),
        ('brand_showcase', 'Brand Showcase'),
        ('gallery', 'Image Gallery'),
    ]
    
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name='sections'
    )
    section_type = models.CharField(
        max_length=20,
        choices=SECTION_TYPES,
        default='brand_showcase'
    )
    order = models.PositiveIntegerField(default=0)
    title = models.CharField(
        max_length=200,
        blank=True,
        help_text="Section title, e.g. '01. AURALEE'"
    )
    subtitle = models.CharField(
        max_length=300,
        blank=True,
        help_text="Optional subtitle or description"
    )
    content = models.TextField(
        blank=True,
        help_text="Text content for text sections"
    )
    
    class Meta:
        ordering = ['order']
        verbose_name = "Content Section"
        verbose_name_plural = "Content Sections"
    
    def __str__(self):
        return f"{self.post.title} - {self.title or self.get_section_type_display()}"


class ProductCard(models.Model):
    """
    Product cards within a brand showcase section.
    Displays product image, brand, name, price, and link.
    Links to Fynda search by default.
    """
    section = models.ForeignKey(
        ContentSection,
        on_delete=models.CASCADE,
        related_name='products'
    )
    order = models.PositiveIntegerField(default=0)
    
    # Product info
    brand = models.CharField(max_length=100, help_text="Brand name, e.g. 'AURALEE'")
    product_name = models.CharField(max_length=200, help_text="Product name")
    image = models.ImageField(
        upload_to='blog/products/',
        help_text="Product image"
    )
    
    # Pricing
    price = models.CharField(max_length=50, help_text="Price, e.g. '$1,200'")
    sale_price = models.CharField(
        max_length=50,
        blank=True,
        help_text="Sale price (optional)"
    )
    
    # Retailer info (for "FROM HARRODS" display)
    retailer = models.CharField(
        max_length=100,
        blank=True,
        help_text="Retailer name, e.g. 'HARRODS', 'MR PORTER'"
    )
    
    # Optional external link (if empty, links to Fynda search)
    product_url = models.URLField(
        blank=True,
        help_text="Optional external link. Leave empty to link to Fynda search."
    )
    
    class Meta:
        ordering = ['order']
        verbose_name = "Product Card"
        verbose_name_plural = "Product Cards"
    
    def __str__(self):
        return f"{self.brand} - {self.product_name}"
    
    @property
    def is_on_sale(self):
        return bool(self.sale_price)
    
    @property
    def fynda_url(self):
        """Generate Fynda search URL for this product."""
        from urllib.parse import quote
        search_query = f"{self.brand} {self.product_name}"
        return f"{settings.SITE_URL}/?q={quote(search_query)}"
    
    @property
    def link(self):
        """Return the product URL - either external or Fynda search."""
        return self.product_url if self.product_url else self.fynda_url


