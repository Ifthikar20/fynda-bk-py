"""
Email Marketing Models for Fynda
"""

from django.db import models
from django.contrib.auth import get_user_model
import uuid
import hashlib


class Subscriber(models.Model):
    """Email subscriber model"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, db_index=True)
    name = models.CharField(max_length=100, blank=True)
    
    # Subscription status
    is_active = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False)
    verification_token = models.CharField(max_length=64, blank=True)
    unsubscribe_token = models.CharField(max_length=64, unique=True)
    
    # Source tracking
    source = models.CharField(max_length=50, default='coming_soon')  # coming_soon, registration, checkout
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    # Preferences
    preferences = models.JSONField(default=dict)  # {categories: [], frequency: 'daily'}
    
    # Timestamps
    subscribed_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    unsubscribed_at = models.DateTimeField(null=True, blank=True)
    
    # Link to user if registered
    user = models.OneToOneField(
        get_user_model(), 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='email_subscription'
    )
    
    class Meta:
        ordering = ['-subscribed_at']
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['is_active', 'is_verified']),
        ]
    
    def __str__(self):
        return self.email
    
    def save(self, *args, **kwargs):
        if not self.unsubscribe_token:
            self.unsubscribe_token = hashlib.sha256(
                f"{self.email}{uuid.uuid4()}".encode()
            ).hexdigest()[:32]
        if not self.verification_token:
            self.verification_token = hashlib.sha256(
                f"{self.email}{uuid.uuid4()}verify".encode()
            ).hexdigest()[:32]
        super().save(*args, **kwargs)


class Campaign(models.Model):
    """Email campaign model"""
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),
        ('sending', 'Sending'),
        ('sent', 'Sent'),
        ('cancelled', 'Cancelled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    subject = models.CharField(max_length=200)
    
    # Content
    content_html = models.TextField()
    content_text = models.TextField(blank=True)  # Plain text version
    preview_text = models.CharField(max_length=200, blank=True)  # Email preview
    
    # Targeting
    send_to_all = models.BooleanField(default=True)
    target_preferences = models.JSONField(default=dict, blank=True)  # Filter by preferences
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # Scheduling
    scheduled_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    
    # Stats (denormalized for quick access)
    total_sent = models.IntegerField(default=0)
    total_opened = models.IntegerField(default=0)
    total_clicked = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} - {self.status}"
    
    @property
    def open_rate(self):
        if self.total_sent == 0:
            return 0
        return round((self.total_opened / self.total_sent) * 100, 2)
    
    @property
    def click_rate(self):
        if self.total_sent == 0:
            return 0
        return round((self.total_clicked / self.total_sent) * 100, 2)


class CampaignSend(models.Model):
    """Individual email send tracking"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.ForeignKey(
        Campaign, 
        on_delete=models.CASCADE,
        related_name='sends'
    )
    subscriber = models.ForeignKey(
        Subscriber,
        on_delete=models.CASCADE,
        related_name='received_campaigns'
    )
    
    # Tracking
    tracking_id = models.CharField(max_length=64, unique=True)
    sent_at = models.DateTimeField(auto_now_add=True)
    
    # Engagement
    opened = models.BooleanField(default=False)
    opened_at = models.DateTimeField(null=True, blank=True)
    open_count = models.IntegerField(default=0)
    
    clicked = models.BooleanField(default=False)
    clicked_at = models.DateTimeField(null=True, blank=True)
    click_count = models.IntegerField(default=0)
    
    # Delivery status
    delivered = models.BooleanField(default=True)
    bounced = models.BooleanField(default=False)
    bounce_reason = models.TextField(blank=True)
    
    class Meta:
        unique_together = ['campaign', 'subscriber']
        ordering = ['-sent_at']
    
    def __str__(self):
        return f"{self.campaign.name} -> {self.subscriber.email}"
    
    def save(self, *args, **kwargs):
        if not self.tracking_id:
            self.tracking_id = hashlib.sha256(
                f"{self.campaign.id}{self.subscriber.id}{uuid.uuid4()}".encode()
            ).hexdigest()[:32]
        super().save(*args, **kwargs)
