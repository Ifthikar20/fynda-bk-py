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
