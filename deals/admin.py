from django.contrib import admin
from .models import Brand, BrandLike


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ["name", "category", "likes_count", "is_featured", "is_active", "created_at"]
    list_filter = ["category", "is_featured", "is_active"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ["likes_count", "created_at", "updated_at"]


@admin.register(BrandLike)
class BrandLikeAdmin(admin.ModelAdmin):
    list_display = ["user", "brand", "created_at"]
    list_filter = ["created_at"]
    raw_id_fields = ["user", "brand"]
