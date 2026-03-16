"""
Blog Admin - Easy-to-use interface with nested sections and products
"""

from django.contrib import admin
from django.utils import timezone
from django.utils.html import mark_safe
from django.contrib import messages
from django.urls import reverse
import nested_admin
from .models import Post, Category, Tag, ContentSection, ProductCard, IndexingLog


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


class IndexingLogInline(admin.TabularInline):
    """Show indexing history inline on the post detail page."""
    model = IndexingLog
    extra = 0
    readonly_fields = [
        'submitted_at', 'status_display',
        'google_badge', 'bing_badge', 'indexnow_badge', 'google_api_badge',
    ]
    fields = [
        'submitted_at', 'status_display',
        'google_badge', 'bing_badge', 'indexnow_badge', 'google_api_badge',
    ]
    ordering = ['-submitted_at']
    max_num = 5
    can_delete = False
    verbose_name = "Indexing Submission"
    verbose_name_plural = "🔍 Indexing History"

    def has_add_permission(self, request, obj=None):
        return False

    def status_display(self, obj):
        colors = {
            'submitted': '#10b981',
            'indexed': '#3b82f6',
            'failed': '#ef4444',
            'pending': '#f59e0b',
        }
        color = colors.get(obj.status, '#6b7280')
        return mark_safe(
            f'<span style="background:{color};color:#fff;padding:2px 8px;'
            f'border-radius:10px;font-size:11px;font-weight:600;">'
            f'{obj.get_status_display()}</span>'
        )
    status_display.short_description = 'Status'

    def _badge(self, val, label):
        icon = '✅' if val else '❌'
        return mark_safe(f'{icon}')

    def google_badge(self, obj):
        return self._badge(obj.google_ping, 'Google')
    google_badge.short_description = 'Google'

    def bing_badge(self, obj):
        return self._badge(obj.bing_ping, 'Bing')
    bing_badge.short_description = 'Bing'

    def indexnow_badge(self, obj):
        return self._badge(obj.indexnow, 'IndexNow')
    indexnow_badge.short_description = 'IndexNow'

    def google_api_badge(self, obj):
        return self._badge(obj.google_api, 'API')
    google_api_badge.short_description = 'Google API'


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
        'has_image', 'section_count', 'indexing_status', 'post_actions'
    ]
    list_filter = ['status', 'category', 'created_at']
    search_fields = ['title', 'content']
    prepopulated_fields = {'slug': ('title',)}
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    filter_horizontal = ['tags']
    inlines = [ContentSectionInline, IndexingLogInline]
    
    # Bulk actions
    actions = ['publish_posts', 'unpublish_posts', 'resubmit_indexing']
    
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

    def indexing_status(self, obj):
        """Show Google/Bing indexing status with colored badges."""
        latest = obj.indexing_logs.first()  # ordered by -submitted_at
        if not latest:
            if obj.status == 'published':
                return mark_safe(
                    '<span style="background:#6b7280;color:#fff;padding:2px 8px;'
                    'border-radius:10px;font-size:10px;">Not submitted</span>'
                )
            return '—'

        # Build service icons
        g = '✅' if latest.google_ping else '❌'
        b = '✅' if latest.bing_ping else '❌'
        i = '✅' if latest.indexnow else '❌'

        # Status badge color
        colors = {
            'submitted': '#10b981',
            'indexed': '#3b82f6',
            'failed': '#ef4444',
            'pending': '#f59e0b',
        }
        color = colors.get(latest.status, '#6b7280')
        status_label = latest.get_status_display()

        time_str = latest.submitted_at.strftime('%b %d, %H:%M')

        return mark_safe(
            f'<div style="line-height:1.4;">'
            f'<span style="background:{color};color:#fff;padding:2px 8px;'
            f'border-radius:10px;font-size:10px;font-weight:600;">{status_label}</span>'
            f'<br><span style="font-size:10px;color:#888;">'
            f'G{g} B{b} IN{i} · {time_str}</span></div>'
        )
    indexing_status.short_description = 'SEO Index'
    
    def post_actions(self, obj):
        """Action links: View, Publish/Unpublish"""
        buttons = []
        
        # View button — clean URL on public domain
        view_url = f'https://outfi.ai/blog/post/{obj.slug}/'
        buttons.append(
            f'<a href="{view_url}" target="_blank" '
            f'style="background:#6366f1;color:#fff;padding:3px 8px;'
            f'border-radius:6px;font-size:11px;text-decoration:none;'
            f'margin-right:4px;" title="View post">👁 View</a>'
        )
        
        if obj.status == 'published':
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

    @admin.action(description='🔍 Re-submit for indexing')
    def resubmit_indexing(self, request, queryset):
        from blog.services.indexing import notify_search_engines
        count = 0
        for post in queryset.filter(status='published'):
            post_url = post.get_absolute_url()
            notify_search_engines(post_url, post=post)
            count += 1
        self.message_user(
            request,
            f'🔍 Submitted {count} post(s) for indexing.',
            messages.SUCCESS,
        )


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


@admin.register(IndexingLog)
class IndexingLogAdmin(admin.ModelAdmin):
    """Admin for viewing indexing submission logs."""
    list_display = [
        'post_title', 'status_display', 'google_badge', 'bing_badge',
        'indexnow_badge', 'google_api_badge', 'submitted_at',
    ]
    list_filter = ['status', 'google_ping', 'bing_ping', 'indexnow']
    ordering = ['-submitted_at']
    readonly_fields = [
        'post', 'submitted_at', 'google_ping', 'bing_ping',
        'indexnow', 'google_api', 'status', 'details',
    ]
    search_fields = ['post__title']

    def post_title(self, obj):
        return obj.post.title[:60]
    post_title.short_description = 'Post'
    post_title.admin_order_field = 'post__title'

    def status_display(self, obj):
        colors = {
            'submitted': '#10b981',
            'indexed': '#3b82f6',
            'failed': '#ef4444',
            'pending': '#f59e0b',
        }
        color = colors.get(obj.status, '#6b7280')
        return mark_safe(
            f'<span style="background:{color};color:#fff;padding:2px 10px;'
            f'border-radius:10px;font-size:11px;font-weight:600;">'
            f'{obj.get_status_display()}</span>'
        )
    status_display.short_description = 'Status'

    def _badge(self, val):
        return '✅' if val else '❌'

    def google_badge(self, obj):
        return self._badge(obj.google_ping)
    google_badge.short_description = 'Google'

    def bing_badge(self, obj):
        return self._badge(obj.bing_ping)
    bing_badge.short_description = 'Bing'

    def indexnow_badge(self, obj):
        return self._badge(obj.indexnow)
    indexnow_badge.short_description = 'IndexNow'

    def google_api_badge(self, obj):
        return self._badge(obj.google_api)
    google_api_badge.short_description = 'Google API'

    def has_add_permission(self, request):
        return False
