"""
Repository Layer
================

Encapsulates all ORM queries for deals models.
Views call repository methods instead of Model.objects directly.

Usage:
    from deals.repositories import StoryboardRepository, SavedDealRepository

    shared = StoryboardRepository.create(user=request.user, ...)
    deals = SavedDealRepository.list_for_user(request.user)
"""

from django.utils import timezone

from .models import SharedStoryboard


class StoryboardRepository:
    """Encapsulates SharedStoryboard ORM queries."""

    @staticmethod
    def create(user, title, storyboard_data, expires_at, token):
        """Create a new shared storyboard."""
        return SharedStoryboard.objects.create(
            token=token,
            user=user,
            title=title,
            storyboard_data=storyboard_data,
            expires_at=expires_at,
        )

    @staticmethod
    def get_by_token(token):
        """
        Fetch a shared storyboard by its public token.
        Returns None if not found.
        """
        return SharedStoryboard.objects.filter(token=token).first()

    @staticmethod
    def list_by_user(user):
        """Return all shared storyboards for a user (newest first)."""
        return SharedStoryboard.objects.filter(user=user)

    @staticmethod
    def delete_by_id(user, share_id):
        """
        Delete a shared storyboard owned by user.
        Returns True if deleted, False if not found.
        """
        deleted, _ = SharedStoryboard.objects.filter(
            id=share_id, user=user
        ).delete()
        return deleted > 0

    @staticmethod
    def increment_views(storyboard):
        """Increment the view count on a storyboard."""
        storyboard.increment_views()


class SavedDealRepository:
    """Encapsulates SavedDeal ORM queries."""

    @staticmethod
    def _get_model():
        """Lazy import to avoid circular imports (model lives in users app)."""
        from users.models import SavedDeal
        return SavedDeal

    @classmethod
    def list_for_user(cls, user, limit=100):
        """Return saved deals for a user, newest first."""
        SavedDeal = cls._get_model()
        return SavedDeal.objects.filter(user=user).order_by("-created_at")[:limit]

    @classmethod
    def save_deal(cls, user, deal_id, deal_data=None):
        """
        Save a deal for a user. Returns (instance, created).
        If the deal is already saved, returns the existing one.
        """
        SavedDeal = cls._get_model()
        return SavedDeal.objects.get_or_create(
            user=user,
            deal_id=deal_id,
            defaults={"deal_data": deal_data or {}},
        )

    @classmethod
    def delete_deal(cls, user, deal_id):
        """
        Delete a saved deal by deal_id for a user.
        Returns True if deleted, False if not found.
        """
        SavedDeal = cls._get_model()
        deleted, _ = SavedDeal.objects.filter(
            user=user, deal_id=deal_id
        ).delete()
        return deleted > 0
