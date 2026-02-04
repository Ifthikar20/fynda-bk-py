"""
Blog Admin - Easy-to-use interface with SEO flexibility
"""

from django.contrib import admin
from django.utils import timezone
from django.utils.html import mark_safe
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
    # List view - simple and clear
    list_display = ['title', 'status', 'category', 'published_at', 'has_image']
    list_filter = ['status', 'category', 'created_at']
    list_editable = ['status']  # Allows quick publish/unpublish from list
    search_fields = ['title', 'content']
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
