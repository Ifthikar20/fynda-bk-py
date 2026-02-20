"""
Brand API Views

GET  /api/v1/brands/                — list brands (sort=trending|most_liked|newest, category=<slug>)
POST /api/v1/brands/<slug>/like/    — like a brand (auth required)
DELETE /api/v1/brands/<slug>/like/  — unlike a brand (auth required)
"""

import logging
from datetime import timedelta

from django.db.models import Count, Q, F
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from deals.models import Brand, BrandLike

logger = logging.getLogger(__name__)


class BrandListView(APIView):
    """
    List active brands with sorting and optional category filter.

    GET /api/v1/brands/?sort=trending&category=womens

    Query params:
        sort     — trending | most_liked | newest  (default: trending)
        category — filter by brand category slug
    """
    permission_classes = [AllowAny]

    def get(self, request):
        sort = request.query_params.get("sort", "trending")
        category = request.query_params.get("category")

        qs = Brand.objects.filter(is_active=True)

        if category:
            qs = qs.filter(category=category)

        # ── Sorting ──────────────────────────────────
        if sort == "most_liked":
            qs = qs.order_by("-likes_count", "-created_at")

        elif sort == "newest":
            qs = qs.order_by("-created_at")

        else:  # trending (default)
            week_ago = timezone.now() - timedelta(days=7)
            qs = qs.annotate(
                recent_likes=Count(
                    "likes",
                    filter=Q(likes__created_at__gte=week_ago),
                )
            ).order_by("-recent_likes", "-likes_count", "-created_at")

        # ── Annotate is_liked for authenticated users ─
        user = request.user
        brands_data = []
        liked_set = set()

        if user and user.is_authenticated:
            liked_set = set(
                BrandLike.objects.filter(user=user)
                .values_list("brand_id", flat=True)
            )

        for b in qs[:50]:
            brands_data.append({
                "id": str(b.id),
                "name": b.name,
                "slug": b.slug,
                "initial": b.name[0].upper() if b.name else "",
                "category": b.get_category_display(),
                "category_slug": b.category,
                "logo_url": b.logo_url,
                "cover_image_url": b.cover_image_url,
                "description": b.description,
                "website_url": b.website_url,
                "is_featured": b.is_featured,
                "likes_count": b.likes_count,
                "is_liked": b.id in liked_set,
            })

        return Response({
            "brands": brands_data,
            "total": len(brands_data),
            "sort": sort,
        })


class BrandLikeView(APIView):
    """
    Like or unlike a brand.

    POST   /api/v1/brands/<slug>/like/   — like
    DELETE /api/v1/brands/<slug>/like/   — unlike

    Response: { "liked": true/false, "likes_count": N }
    """
    permission_classes = [IsAuthenticated]

    def _get_brand(self, slug):
        try:
            return Brand.objects.get(slug=slug, is_active=True)
        except Brand.DoesNotExist:
            return None

    def post(self, request, slug):
        brand = self._get_brand(slug)
        if not brand:
            return Response(
                {"error": "Brand not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        _, created = BrandLike.objects.get_or_create(
            user=request.user, brand=brand,
        )

        if created:
            # Increment denormalized counter
            Brand.objects.filter(pk=brand.pk).update(
                likes_count=F("likes_count") + 1
            )
            brand.refresh_from_db(fields=["likes_count"])

        return Response({
            "liked": True,
            "likes_count": brand.likes_count,
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    def delete(self, request, slug):
        brand = self._get_brand(slug)
        if not brand:
            return Response(
                {"error": "Brand not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        deleted, _ = BrandLike.objects.filter(
            user=request.user, brand=brand,
        ).delete()

        if deleted:
            Brand.objects.filter(pk=brand.pk).update(
                likes_count=F("likes_count") - 1
            )
            brand.refresh_from_db(fields=["likes_count"])

        return Response({
            "liked": False,
            "likes_count": max(0, brand.likes_count),
        })
