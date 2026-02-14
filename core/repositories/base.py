"""
Generic Base Repository
=======================

Type-safe, generic repository providing standard CRUD operations.
All app-specific repositories inherit from this.

Usage:
    from core.repositories import BaseRepository
    from myapp.models import MyModel

    class MyRepository(BaseRepository[MyModel]):
        model = MyModel

        @staticmethod
        def get_active():
            return MyModel.objects.filter(is_active=True)
"""

from typing import TypeVar, Generic, Type, Optional, Any
from django.db import models
from django.db.models import QuerySet

T = TypeVar("T", bound=models.Model)


class BaseRepository(Generic[T]):
    """
    Generic repository with standard CRUD operations.

    Subclasses MUST set the `model` class attribute:

        class UserRepository(BaseRepository[User]):
            model = User
    """

    model: Type[T]

    # ── Read ──────────────────────────────────────────────────────────

    @classmethod
    def get_by_id(cls, pk: Any) -> T:
        """
        Get a single instance by primary key.
        Raises model.DoesNotExist if not found.
        """
        return cls.model.objects.get(pk=pk)

    @classmethod
    def get_by_id_or_none(cls, pk: Any) -> Optional[T]:
        """Get a single instance by primary key, or None."""
        return cls.model.objects.filter(pk=pk).first()

    @classmethod
    def get_all(cls) -> QuerySet[T]:
        """Return all instances (respects model's default ordering)."""
        return cls.model.objects.all()

    @classmethod
    def filter(cls, **kwargs) -> QuerySet[T]:
        """Filter instances by keyword arguments."""
        return cls.model.objects.filter(**kwargs)

    @classmethod
    def exists(cls, **kwargs) -> bool:
        """Check if at least one instance matches the given filters."""
        return cls.model.objects.filter(**kwargs).exists()

    @classmethod
    def count(cls, **kwargs) -> int:
        """Count instances matching the given filters (all if no filters)."""
        if kwargs:
            return cls.model.objects.filter(**kwargs).count()
        return cls.model.objects.count()

    # ── Write ─────────────────────────────────────────────────────────

    @classmethod
    def create(cls, **kwargs) -> T:
        """Create and return a new instance."""
        return cls.model.objects.create(**kwargs)

    @classmethod
    def update(cls, instance: T, **kwargs) -> T:
        """Update fields on an existing instance and save."""
        for field, value in kwargs.items():
            setattr(instance, field, value)
        instance.save(update_fields=list(kwargs.keys()))
        return instance

    @classmethod
    def delete(cls, instance: T) -> None:
        """Delete a single instance."""
        instance.delete()

    @classmethod
    def bulk_create(cls, instances: list[T], **kwargs) -> list[T]:
        """Bulk-create instances."""
        return cls.model.objects.bulk_create(instances, **kwargs)

    @classmethod
    def get_or_create(cls, defaults: Optional[dict] = None, **kwargs) -> tuple[T, bool]:
        """Get an existing instance or create a new one."""
        return cls.model.objects.get_or_create(defaults=defaults or {}, **kwargs)
