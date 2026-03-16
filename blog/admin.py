"""
Blog Admin - Easy-to-use interface with nested sections and products
"""

from django.contrib import admin
from django.utils import timezone
from django.utils.html import mark_safe
from django.contrib import messages
from django.urls import reverse
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
    extra = 1
    fields = ['order', 'section_type', 'title', 'subtitle', 'content']
    ordering = ['order']
    inlines = [ProductCardInline]
    verbose_name = "Content Section"
    verbose_name_plural = "Content Sections (with Products)"


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
    # List view
    list_display = [
        'title', 'status_badge', 'category', 'published_at',
        'has_image', 'section_count', 'post_actions'
    ]
    list_filter = ['status', 'category', 'created_at']
    search_fields = ['title', 'content']
    prepopulated_fields = {'slug': ('title',)}
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    filter_horizontal = ['tags']
    inlines = [ContentSectionInline]
    
    # Bulk actions
    actions = ['publish_posts', 'unpublish_posts']
    
    # Form layout
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
    
    # ── Custom columns ──
    
    def status_badge(self, obj):
        if obj.status == 'published':
            return mark_safe(
                '<span style="background:#10b981;color:#fff;padding:3px 10px;'
                'border-radius:12px;font-size:11px;font-weight:600;">Published</span>'
            )
        return mark_safe(
            '<span style="background:#f59e0b;color:#fff;padding:3px 10px;'
            'border-radius:12px;font-size:11px;font-weight:600;">Draft</span>'
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'
    
    def has_image(self, obj):
        return '✅' if obj.featured_image else '—'
    has_image.short_description = 'Image'
    
    def section_count(self, obj):
        count = obj.sections.count()
        return f'{count} section(s)' if count else '—'
    section_count.short_description = 'Sections'
    
    def post_actions(self, obj):
        """Action links: Preview, View on Site, Publish/Unpublish"""
        buttons = []
        
        # Preview button — on outfi.ai (public blog domain)
        preview_url = f'https://outfi.ai/blog/preview/{obj.slug}/'
        buttons.append(
            f'<a href="{preview_url}" target="_blank" '
            f'style="background:#6366f1;color:#fff;padding:3px 8px;'
            f'border-radius:6px;font-size:11px;text-decoration:none;'
            f'margin-right:4px;" title="Preview post">👁 Preview</a>'
        )
        
        if obj.status == 'published':
            # View on site — public blog URL
            view_url = f'https://outfi.ai/blog/post/{obj.slug}/'
            buttons.append(
                f'<a href="{view_url}" target="_blank" '
                f'style="background:#10b981;color:#fff;padding:3px 8px;'
                f'border-radius:6px;font-size:11px;text-decoration:none;'
                f'margin-right:4px;" title="View on site">🌐 View</a>'
            )
            # Unpublish
            unpublish_url = reverse('admin:blog_post_unpublish', args=[obj.pk])
            buttons.append(
                f'<a href="{unpublish_url}" '
                f'style="background:#ef4444;color:#fff;padding:3px 8px;'
                f'border-radius:6px;font-size:11px;text-decoration:none;" '
                f'title="Unpublish">⏸ Unpublish</a>'
            )
        else:
            # Publish
            publish_url = reverse('admin:blog_post_publish', args=[obj.pk])
            buttons.append(
                f'<a href="{publish_url}" '
                f'style="background:#10b981;color:#fff;padding:3px 8px;'
                f'border-radius:6px;font-size:11px;text-decoration:none;" '
                f'title="Publish now">✅ Publish</a>'
            )
        
        return mark_safe(' '.join(buttons))
    post_actions.short_description = 'Actions'
    
    # ── Custom admin URLs for publish/unpublish ──
    
    def get_urls(self):
        from django.urls import path
        custom_urls = [
            path(
                '<int:post_id>/publish/',
                self.admin_site.admin_view(self.publish_single_post),
                name='blog_post_publish',
            ),
            path(
                '<int:post_id>/unpublish/',
                self.admin_site.admin_view(self.unpublish_single_post),
                name='blog_post_unpublish',
            ),
        ]
        return custom_urls + super().get_urls()
    
    def publish_single_post(self, request, post_id):
        from django.http import HttpResponseRedirect
        post = Post.objects.get(pk=post_id)
        post.status = 'published'
        if not post.published_at:
            post.published_at = timezone.now()
        if not post.author:
            post.author = request.user
        post.save()
        self.message_user(
            request,
            f'✅ "{post.title}" has been published!',
            messages.SUCCESS,
        )
        return HttpResponseRedirect(reverse('admin:blog_post_changelist'))
    
    def unpublish_single_post(self, request, post_id):
        from django.http import HttpResponseRedirect
        post = Post.objects.get(pk=post_id)
        post.status = 'draft'
        post.save()
        self.message_user(
            request,
            f'📝 "{post.title}" has been set to draft.',
            messages.WARNING,
        )
        return HttpResponseRedirect(reverse('admin:blog_post_changelist'))
    
    # ── Save model ──
    
    def save_model(self, request, obj, form, change):
        """Auto-assign author and set published_at when publishing"""
        if not obj.author:
            obj.author = request.user
        if obj.status == 'published' and not obj.published_at:
            obj.published_at = timezone.now()
        super().save_model(request, obj, form, change)
    
    # ── Bulk actions ──
    
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
