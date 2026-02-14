"""
Users Repositories
==================

Data-access layer for User, SavedDeal, and SearchHistory models.
"""

from django.contrib.auth import get_user_model
from django.db.models import QuerySet

from core.repositories import BaseRepository
from .models import SavedDeal, SearchHistory

User = get_user_model()


class UserRepository(BaseRepository[User]):
    """User data access."""

    model = User

    @classmethod
    def get_by_email(cls, email: str):
        """Get user by email (case-insensitive), or None."""
        return cls.model.objects.filter(email__iexact=email).first()

    @classmethod
    def get_by_oauth(cls, provider: str, uid: str):
        """Get user by OAuth provider + UID, or None."""
        return cls.model.objects.filter(
            oauth_provider=provider,
            oauth_uid=uid,
        ).first()

    @classmethod
    def create_user(cls, email: str, password=None, **extra_fields):
        """Create a new user through the custom UserManager."""
        return cls.model.objects.create_user(email, password, **extra_fields)


class SavedDealRepository(BaseRepository[SavedDeal]):
    """Saved-deal data access."""

    model = SavedDeal

    @classmethod
    def get_user_deals(cls, user, limit: int = 100) -> QuerySet:
        """Return saved deals for a user, newest first."""
        return cls.model.objects.filter(user=user).order_by("-created_at")[:limit]

    @classmethod
    def save_deal(cls, user, deal_id: str, deal_data: dict = None) -> tuple:
        """Save a deal; returns (instance, created)."""
        return cls.model.objects.get_or_create(
            user=user,
            deal_id=deal_id,
            defaults={"deal_data": deal_data or {}},
        )

    @classmethod
    def unsave_deal(cls, user, deal_id: str) -> bool:
        """Remove a saved deal. Returns True if deleted."""
        deleted, _ = cls.model.objects.filter(user=user, deal_id=deal_id).delete()
        return deleted > 0


class SearchHistoryRepository(BaseRepository[SearchHistory]):
    """Search-history data access."""

    model = SearchHistory

    @classmethod
    def get_user_history(cls, user, limit: int = 50) -> QuerySet:
        """Return recent search history for a user."""
        return cls.model.objects.filter(user=user)[:limit]

    @classmethod
    def log_search(cls, user, query: str, parsed_product: str = "", parsed_budget=None, results_count: int = 0):
        """Record a search event."""
        return cls.model.objects.create(
            user=user,
            query=query,
            parsed_product=parsed_product,
            parsed_budget=parsed_budget,
            results_count=results_count,
        )


# Singleton instances for convenience
user_repo = UserRepository()
saved_deal_repo = SavedDealRepository()
search_history_repo = SearchHistoryRepository()
