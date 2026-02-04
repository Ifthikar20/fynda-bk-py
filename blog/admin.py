"""
Blog Admin - Rich admin interface with Publish/Unpublish buttons
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
    list_display = ['title', 'author', 'category', 'status_badge', 'published_at', 'featured_image_preview']
    list_filter = ['status', 'category', 'created_at', 'published_at']
    search_fields = ['title', 'content', 'excerpt']
    prepopulated_fields = {'slug': ('title',)}
    date_hierarchy = 'published_at'
    ordering = ['-created_at']
    
    filter_horizontal = ['tags']
    
    # Custom actions for bulk publish/unpublish
    actions = ['publish_posts', 'unpublish_posts']
    
    fieldsets = (
        ('Content', {
            'fields': ('title', 'slug', 'author', 'excerpt', 'content', 'featured_image')
        }),
        ('Organization', {
            'fields': ('category', 'tags')
            # Removed 'status' - will be controlled by buttons only
        }),
        ('SEO Settings', {
            'fields': ('meta_title', 'meta_description'),
            'classes': ('collapse',),
            'description': 'Optional SEO overrides. Leave blank to use defaults.'
        }),
        ('Timestamps', {
            'fields': ('published_at',),
            'classes': ('collapse',),
        }),
    )
    
    # Custom buttons in the change form
    change_form_template = 'admin/blog/post/change_form.html'
    
    def status_badge(self, obj):
        """Display status as colored badge"""
        if obj.status == 'published':
            return format_html(
                '<span style="background: #28a745; color: white; padding: 3px 10px; '
                'border-radius: 3px; font-size: 11px; font-weight: bold;">LIVE</span>'
            )
        else:
            return format_html(
                '<span style="background: #6c757d; color: white; padding: 3px 10px; '
                'border-radius: 3px; font-size: 11px; font-weight: bold;">DRAFT</span>'
            )
    status_badge.short_description = 'Status'
    
    def featured_image_preview(self, obj):
        if obj.featured_image:
            return format_html(
                '<img src="{}" style="max-height: 50px; max-width: 100px;" />',
                obj.featured_image.url
            )
        return '-'
    featured_image_preview.short_description = 'Image'
    
    def save_model(self, request, obj, form, change):
        if not obj.author:
            obj.author = request.user
        super().save_model(request, obj, form, change)
    
    def response_change(self, request, obj):
        """Handle custom Publish/Unpublish button clicks"""
        if "_publish" in request.POST:
            obj.status = 'published'
            if not obj.published_at:
                obj.published_at = timezone.now()
            obj.save()
            self.message_user(request, f'"{obj.title}" has been published!', messages.SUCCESS)
            return self.response_post_save_change(request, obj)
        
        if "_unpublish" in request.POST:
            obj.status = 'draft'
            obj.save()
            self.message_user(request, f'"{obj.title}" has been unpublished.', messages.WARNING)
            return self.response_post_save_change(request, obj)
        
        return super().response_change(request, obj)
    
    def response_add(self, request, obj, post_url_continue=None):
        """Handle custom Publish button on add (new post)"""
        if "_publish" in request.POST:
            obj.status = 'published'
            if not obj.published_at:
                obj.published_at = timezone.now()
            obj.save()
            self.message_user(request, f'"{obj.title}" has been published!', messages.SUCCESS)
            return self.response_post_save_add(request, obj, post_url_continue)
        
        return super().response_add(request, obj, post_url_continue)
    
    # Bulk actions for list view
    @admin.action(description='✅ Publish selected posts')
    def publish_posts(self, request, queryset):
        count = queryset.update(status='published', published_at=timezone.now())
        self.message_user(request, f'{count} post(s) published.', messages.SUCCESS)
    
    @admin.action(description='📝 Unpublish selected posts (set to draft)')
    def unpublish_posts(self, request, queryset):
        count = queryset.update(status='draft')
        self.message_user(request, f'{count} post(s) unpublished.', messages.WARNING)
