"""
Deals Repositories
==================

Data-access layer for SharedStoryboard.
SavedDeal repository lives in users/repositories.py (co-located with the model).
"""

from django.db.models import QuerySet
from django.utils import timezone

from core.repositories import BaseRepository
from .models import SharedStoryboard


class SharedStoryboardRepository(BaseRepository[SharedStoryboard]):
    """SharedStoryboard data access."""

    model = SharedStoryboard

    @classmethod
    def get_by_token(cls, token: str):
        """Get a storyboard by its public share token, or None."""
        return cls.model.objects.filter(token=token).first()

    @classmethod
    def get_user_storyboards(cls, user) -> QuerySet:
        """Return all storyboards owned by user (newest first)."""
        return cls.model.objects.filter(user=user)

    @classmethod
    def get_public_active(cls) -> QuerySet:
        """Return all non-expired, public storyboards."""
        return cls.model.objects.filter(
            is_public=True,
            expires_at__gt=timezone.now(),
        )

    @classmethod
    def create_shared(cls, user, title, storyboard_data, expires_at, token):
        """Create a new shared storyboard."""
        return cls.model.objects.create(
            token=token,
            user=user,
            title=title,
            storyboard_data=storyboard_data,
            expires_at=expires_at,
        )

    @classmethod
    def delete_by_id(cls, user, share_id) -> bool:
        """Delete a storyboard owned by user. Returns True if deleted."""
        deleted, _ = cls.model.objects.filter(id=share_id, user=user).delete()
        return deleted > 0

    @classmethod
    def increment_views(cls, storyboard):
        """Increment view count on a storyboard."""
        storyboard.increment_views()


# Singleton
storyboard_repo = SharedStoryboardRepository()
