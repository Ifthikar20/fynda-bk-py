"""
Blog Repositories
=================

Data-access layer for Post, Category, and Tag models.
"""

from django.db.models import QuerySet, Q
from django.utils import timezone

from core.repositories import BaseRepository
from .models import Post, Category, Tag


class PostRepository(BaseRepository[Post]):
    """Blog post data access."""

    model = Post

    @classmethod
    def get_published(cls, limit: int = None) -> QuerySet:
        """Return published posts, newest first."""
        qs = cls.model.objects.filter(
            status="published",
            published_at__lte=timezone.now(),
        ).select_related("author", "category").prefetch_related("tags")

        if limit:
            return qs[:limit]
        return qs

    @classmethod
    def get_published_by_slug(cls, slug: str):
        """Get a single published post by slug, or None."""
        return cls.model.objects.filter(
            slug=slug,
            status="published",
        ).select_related("author", "category").prefetch_related("tags", "sections__products").first()

    @classmethod
    def search_published(cls, query: str) -> QuerySet:
        """Full-text search across title, excerpt, and content."""
        return cls.get_published().filter(
            Q(title__icontains=query)
            | Q(excerpt__icontains=query)
            | Q(content__icontains=query)
        )

    @classmethod
    def get_related(cls, post, limit: int = 3) -> QuerySet:
        """Get related posts based on category and tags."""
        tag_ids = post.tags.values_list("id", flat=True)
        return (
            cls.get_published()
            .filter(Q(category=post.category) | Q(tags__in=tag_ids))
            .exclude(pk=post.pk)
            .distinct()[:limit]
        )

    @classmethod
    def get_featured(cls, limit: int = 5) -> QuerySet:
        """Get the most recent published posts (used as featured)."""
        return cls.get_published(limit=limit)

    @classmethod
    def get_by_category(cls, category_slug: str) -> QuerySet:
        """Get published posts filtered by category slug."""
        return cls.get_published().filter(category__slug=category_slug)

    @classmethod
    def get_by_tag(cls, tag_slug: str) -> QuerySet:
        """Get published posts filtered by tag slug."""
        return cls.get_published().filter(tags__slug=tag_slug)


class CategoryRepository(BaseRepository[Category]):
    """Blog category data access."""

    model = Category

    @classmethod
    def get_by_slug(cls, slug: str):
        """Get category by slug, or None."""
        return cls.model.objects.filter(slug=slug).first()

    @classmethod
    def get_with_post_count(cls) -> QuerySet:
        """Return categories annotated with post count."""
        from django.db.models import Count
        return cls.model.objects.annotate(
            post_count=Count("posts", filter=Q(posts__status="published"))
        ).order_by("name")


class TagRepository(BaseRepository[Tag]):
    """Blog tag data access."""

    model = Tag

    @classmethod
    def get_by_slug(cls, slug: str):
        """Get tag by slug, or None."""
        return cls.model.objects.filter(slug=slug).first()

    @classmethod
    def get_popular(cls, limit: int = 20) -> QuerySet:
        """Return tags ordered by post count."""
        from django.db.models import Count
        return cls.model.objects.annotate(
            post_count=Count("posts", filter=Q(posts__status="published"))
        ).order_by("-post_count")[:limit]


# Singletons
post_repo = PostRepository()
category_repo = CategoryRepository()
tag_repo = TagRepository()
