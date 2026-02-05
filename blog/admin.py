"""
Blog Admin - Easy-to-use interface with nested sections and products
"""

from django.contrib import admin
from django.utils import timezone
from django.utils.html import mark_safe
from django.contrib import messages
import nested_admin
from .models import Post, Category, Tag, ContentSection, ProductCard


class ProductCardInline(nested_admin.NestedStackedInline):
    """Inline admin for products within a content section."""
    model = ProductCard
    extra = 0
    fields = [
        ('order', 'brand'),
        ('product_name', 'retailer'),
        'image',
        ('price', 'sale_price'),
        'product_url',
    ]
    ordering = ['order']
    classes = ['collapse']
    verbose_name = "Product"
    verbose_name_plural = "Products"


class ContentSectionInline(nested_admin.NestedStackedInline):
    """Inline admin for content sections within a post - includes products."""
    model = ContentSection
    extra = 0
    fields = ['order', 'section_type', 'title', 'subtitle', 'content']
    ordering = ['order']
    classes = ['collapse']
    inlines = [ProductCardInline]  # Nested products within sections


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'post_count']
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ['name']
    
    def post_count(self, obj):
        return obj.posts.count()
    post_count.short_description = 'Posts'


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'post_count']
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ['name']
    
    def post_count(self, obj):
        return obj.posts.count()
    post_count.short_description = 'Posts'


@admin.register(Post)
class PostAdmin(nested_admin.NestedModelAdmin):
    # List view - simple and clear
    list_display = ['title', 'status', 'category', 'published_at', 'has_image', 'section_count']
    list_filter = ['status', 'category', 'created_at']
    list_editable = ['status']  # Allows quick publish/unpublish from list
    search_fields = ['title', 'content']
    prepopulated_fields = {'slug': ('title',)}
    date_hierarchy = 'published_at'
    ordering = ['-created_at']
    filter_horizontal = ['tags']
    inlines = [ContentSectionInline]
    
    # Bulk actions
    actions = ['publish_posts', 'unpublish_posts']
    
    # Form layout - organized for ease of use
    fieldsets = (
        ('📝 Content', {
            'fields': ('title', 'slug', 'content', 'featured_image'),
            'description': 'Write your blog post. Use HTML for formatting.'
        }),
        ('📂 Organization', {
            'fields': ('category', 'tags'),
        }),
        ('🔍 SEO Settings (Optional)', {
            'fields': ('meta_title', 'meta_description'),
            'description': 'Leave blank to auto-generate from title/content.',
            'classes': ('collapse',),
        }),
        ('⚙️ Publishing', {
            'fields': ('status', 'author', 'published_at'),
        }),
    )
    
    def has_image(self, obj):
        return '✅' if obj.featured_image else '—'
    has_image.short_description = 'Image'
    
    def section_count(self, obj):
        count = obj.sections.count()
        return f'{count} section(s)' if count else '—'
    section_count.short_description = 'Sections'
    
    def save_model(self, request, obj, form, change):
        """Auto-assign author and set published_at when publishing"""
        if not obj.author:
            obj.author = request.user
        if obj.status == 'published' and not obj.published_at:
            obj.published_at = timezone.now()
        super().save_model(request, obj, form, change)
    
    # Bulk actions
    @admin.action(description='✅ Publish selected posts')
    def publish_posts(self, request, queryset):
        now = timezone.now()
        for post in queryset:
            post.status = 'published'
            if not post.published_at:
                post.published_at = now
            post.save()
        self.message_user(request, f'{queryset.count()} post(s) published!', messages.SUCCESS)
    
    @admin.action(description='📝 Unpublish selected posts')
    def unpublish_posts(self, request, queryset):
        queryset.update(status='draft')
        self.message_user(request, f'{queryset.count()} post(s) set to draft.', messages.WARNING)


@admin.register(ContentSection)
class ContentSectionAdmin(nested_admin.NestedModelAdmin):
    """Admin for editing content sections with product cards."""
    list_display = ['__str__', 'post', 'section_type', 'order', 'product_count']
    list_filter = ['section_type', 'post']
    ordering = ['post', 'order']
    inlines = [ProductCardInline]
    
    fieldsets = (
        ('Section Info', {
            'fields': ('post', 'section_type', 'order', 'title', 'subtitle', 'content'),
        }),
    )
    
    def product_count(self, obj):
        count = obj.products.count()
        return f'{count} product(s)' if count else '—'
    product_count.short_description = 'Products'
