from django.contrib import admin
from .models import Post, Like, Comment


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ["short_caption", "author", "likes_count", "comments_count", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["caption", "author__email"]
    readonly_fields = ["id", "likes_count", "comments_count", "created_at", "updated_at"]

    def short_caption(self, obj):
        return obj.caption[:60] or "—"
    short_caption.short_description = "Caption"


@admin.register(Like)
class LikeAdmin(admin.ModelAdmin):
    list_display = ["user", "post", "created_at"]
    list_filter = ["created_at"]


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ["user", "short_text", "post", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["text", "user__email"]

    def short_text(self, obj):
        return obj.text[:60]
    short_text.short_description = "Comment"
