"""
Blog Admin - Easy-to-use interface with SEO flexibility
"""

from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html
from django.contrib import messages
from .models import Post, Category, Tag


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
class PostAdmin(admin.ModelAdmin):
    # List view configuration
    list_display = ['title', 'status_badge', 'category', 'published_at', 'featured_image_preview']
    list_filter = ['status', 'category', 'created_at']
    search_fields = ['title', 'content', 'excerpt']
    prepopulated_fields = {'slug': ('title',)}
    date_hierarchy = 'published_at'
    ordering = ['-created_at']
    filter_horizontal = ['tags']
    
    # Bulk actions
    actions = ['publish_posts', 'unpublish_posts']
    
    # Form layout - organized for ease of use
    fieldsets = (
        ('📝 Content', {
            'fields': ('title', 'slug', 'content', 'featured_image'),
            'description': 'Write your blog post here. Use HTML for formatting.'
        }),
        ('📂 Organization', {
            'fields': ('category', 'tags'),
            'description': 'Categorize your post for better organization.'
        }),
        ('🔍 SEO Settings', {
            'fields': ('meta_title', 'meta_description'),
            'description': 'Customize how your post appears in search engines. Leave blank to use defaults (title and first 160 chars).'
        }),
        ('⚙️ Publishing', {
            'fields': ('status', 'author', 'published_at'),
            'description': 'Control when and how your post is published.',
            'classes': ('collapse',),
        }),
    )
    
    def status_badge(self, obj):
        """Display status as colored badge"""
        if obj.status == 'published':
            return format_html(
                '<span style="background: #28a745; color: white; padding: 4px 12px; '
                'border-radius: 4px; font-size: 11px; font-weight: bold;">🟢 LIVE</span>'
            )
        else:
            return format_html(
                '<span style="background: #6c757d; color: white; padding: 4px 12px; '
                'border-radius: 4px; font-size: 11px; font-weight: bold;">📝 DRAFT</span>'
            )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'
    
    def featured_image_preview(self, obj):
        if obj.featured_image:
            return format_html(
                '<img src="{}" style="max-height: 40px; max-width: 60px; border-radius: 4px;" />',
                obj.featured_image.url
            )
        return format_html('<span style="color: #999;">No image</span>')
    featured_image_preview.short_description = 'Image'
    
    def save_model(self, request, obj, form, change):
        """Auto-assign author if not set"""
        if not obj.author:
            obj.author = request.user
        super().save_model(request, obj, form, change)
    
    # Bulk actions
    @admin.action(description='✅ Publish selected posts')
    def publish_posts(self, request, queryset):
        now = timezone.now()
        count = 0
        for post in queryset:
            post.status = 'published'
            if not post.published_at:
                post.published_at = now
            post.save()
            count += 1
        self.message_user(request, f'{count} post(s) published!', messages.SUCCESS)
    
    @admin.action(description='📝 Unpublish selected posts')
    def unpublish_posts(self, request, queryset):
        count = queryset.update(status='draft')
        self.message_user(request, f'{count} post(s) set to draft.', messages.WARNING)
    
    class Media:
        css = {
            'all': ['admin/css/blog_admin.css'] if False else []
        }
