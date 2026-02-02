"""
Django Admin for Email Marketing
"""

from django.contrib import admin
from django.utils.html import format_html
from .models import Subscriber, Campaign, CampaignSend


@admin.register(Subscriber)
class SubscriberAdmin(admin.ModelAdmin):
    list_display = [
        'email', 
        'name', 
        'is_active', 
        'is_verified', 
        'source',
        'subscribed_at'
    ]
    list_filter = ['is_active', 'is_verified', 'source', 'subscribed_at']
    search_fields = ['email', 'name']
    readonly_fields = [
        'id', 
        'verification_token', 
        'unsubscribe_token',
        'subscribed_at',
        'verified_at',
        'unsubscribed_at'
    ]
    date_hierarchy = 'subscribed_at'
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('email', 'name', 'user')
        }),
        ('Status', {
            'fields': ('is_active', 'is_verified', 'source')
        }),
        ('Preferences', {
            'fields': ('preferences',),
            'classes': ('collapse',)
        }),
        ('Tracking', {
            'fields': (
                'ip_address',
                'verification_token', 
                'unsubscribe_token'
            ),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': (
                'subscribed_at',
                'verified_at',
                'unsubscribed_at'
            ),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_active', 'mark_inactive']
    
    def mark_active(self, request, queryset):
        queryset.update(is_active=True)
    mark_active.short_description = "Mark selected subscribers as active"
    
    def mark_inactive(self, request, queryset):
        queryset.update(is_active=False)
    mark_inactive.short_description = "Mark selected subscribers as inactive"


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = [
        'name',
        'subject',
        'status',
        'total_sent',
        'open_rate_display',
        'click_rate_display',
        'created_at',
        'sent_at'
    ]
    list_filter = ['status', 'created_at', 'sent_at']
    search_fields = ['name', 'subject']
    readonly_fields = [
        'id',
        'created_at',
        'updated_at',
        'sent_at',
        'total_sent',
        'total_opened',
        'total_clicked'
    ]
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Campaign Info', {
            'fields': ('name', 'subject', 'preview_text')
        }),
        ('Content', {
            'fields': ('content_html', 'content_text')
        }),
        ('Targeting', {
            'fields': ('send_to_all', 'target_preferences'),
            'classes': ('collapse',)
        }),
        ('Scheduling', {
            'fields': ('status', 'scheduled_at')
        }),
        ('Statistics', {
            'fields': (
                'total_sent',
                'total_opened',
                'total_clicked'
            ),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'sent_at'),
            'classes': ('collapse',)
        }),
    )
    
    def open_rate_display(self, obj):
        rate = obj.open_rate
        color = 'green' if rate > 20 else 'orange' if rate > 10 else 'red'
        return format_html(
            '<span style="color: {};">{:.1f}%</span>',
            color, rate
        )
    open_rate_display.short_description = 'Open Rate'
    
    def click_rate_display(self, obj):
        rate = obj.click_rate
        color = 'green' if rate > 5 else 'orange' if rate > 2 else 'red'
        return format_html(
            '<span style="color: {};">{:.1f}%</span>',
            color, rate
        )
    click_rate_display.short_description = 'Click Rate'


@admin.register(CampaignSend)
class CampaignSendAdmin(admin.ModelAdmin):
    list_display = [
        'campaign',
        'subscriber',
        'delivered',
        'opened',
        'clicked',
        'sent_at'
    ]
    list_filter = ['delivered', 'opened', 'clicked', 'bounced', 'sent_at']
    search_fields = ['subscriber__email', 'campaign__name']
    readonly_fields = [
        'id',
        'tracking_id',
        'sent_at',
        'opened_at',
        'clicked_at',
        'open_count',
        'click_count'
    ]
    date_hierarchy = 'sent_at'
    
    fieldsets = (
        ('Send Info', {
            'fields': ('campaign', 'subscriber', 'tracking_id')
        }),
        ('Delivery', {
            'fields': ('delivered', 'bounced', 'bounce_reason')
        }),
        ('Engagement', {
            'fields': (
                'opened',
                'opened_at',
                'open_count',
                'clicked',
                'clicked_at',
                'click_count'
            )
        }),
    )
