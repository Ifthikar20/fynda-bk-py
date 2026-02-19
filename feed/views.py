from rest_framework import status, generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.pagination import CursorPagination
from django.shortcuts import get_object_or_404
from django.db.models import F, Count
from django.conf import settings

from .models import Post, Like, Comment
from .serializers import PostSerializer, PostCreateSerializer, CommentSerializer


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------

class FeedCursorPagination(CursorPagination):
    page_size = 20
    ordering = "-created_at"
    cursor_query_param = "cursor"


# ---------------------------------------------------------------------------
# Feed list + create
# ---------------------------------------------------------------------------

class FeedListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/v1/feed/        → paginated feed (public)
    POST /api/v1/feed/        → create a post (auth required)
    """
    pagination_class = FeedCursorPagination

    def get_serializer_class(self):
        if self.request.method == "POST":
            return PostCreateSerializer
        return PostSerializer

    def get_permissions(self):
        if self.request.method == "POST":
            return [permissions.IsAuthenticated()]
        return [permissions.AllowAny()]

    def get_queryset(self):
        qs = Post.objects.select_related("author").all()
        # Optional tag filter: /api/v1/feed/?tag=streetwear
        tag = self.request.query_params.get("tag")
        if tag:
            qs = qs.filter(tags__contains=[tag])
        return qs


# ---------------------------------------------------------------------------
# Single post detail + delete
# ---------------------------------------------------------------------------

class PostDetailView(generics.RetrieveDestroyAPIView):
    """
    GET    /api/v1/feed/<id>/   → post detail
    DELETE /api/v1/feed/<id>/   → delete own post
    """
    queryset = Post.objects.select_related("author").all()
    serializer_class = PostSerializer
    lookup_field = "id"

    def get_permissions(self):
        if self.request.method == "DELETE":
            return [permissions.IsAuthenticated()]
        return [permissions.AllowAny()]

    def perform_destroy(self, instance):
        if instance.author != self.request.user:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You can only delete your own posts.")
        instance.delete()


# ---------------------------------------------------------------------------
# Like toggle
# ---------------------------------------------------------------------------

@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def toggle_like(request, id):
    """Toggle like on a post. Returns new likes_count."""
    post = get_object_or_404(Post, id=id)
    like, created = Like.objects.get_or_create(user=request.user, post=post)

    if created:
        Post.objects.filter(id=id).update(likes_count=F("likes_count") + 1)
        liked = True
    else:
        like.delete()
        Post.objects.filter(id=id).update(likes_count=F("likes_count") - 1)
        liked = False

    post.refresh_from_db()
    return Response({"liked": liked, "likes_count": post.likes_count})


# ---------------------------------------------------------------------------
# Comments list + create
# ---------------------------------------------------------------------------

class CommentListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/v1/feed/<id>/comments/   → list comments
    POST /api/v1/feed/<id>/comments/   → add comment (auth required)
    """
    serializer_class = CommentSerializer

    def get_permissions(self):
        if self.request.method == "POST":
            return [permissions.IsAuthenticated()]
        return [permissions.AllowAny()]

    def get_queryset(self):
        return Comment.objects.filter(
            post_id=self.kwargs["id"]
        ).select_related("user")

    def perform_create(self, serializer):
        post = get_object_or_404(Post, id=self.kwargs["id"])
        serializer.save(user=self.request.user, post=post)
        Post.objects.filter(id=post.id).update(comments_count=F("comments_count") + 1)


# ---------------------------------------------------------------------------
# Current user's posts
# ---------------------------------------------------------------------------

class MyPostsView(generics.ListAPIView):
    """GET /api/v1/feed/me/ → current user's posts."""
    serializer_class = PostSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = FeedCursorPagination

    def get_queryset(self):
        return Post.objects.filter(author=self.request.user).select_related("author")


# ---------------------------------------------------------------------------
# Public user profile + their posts
# ---------------------------------------------------------------------------

class UserProfileView(APIView):
    """GET /api/v1/feed/user/<uuid>/ → public profile + posts."""
    permission_classes = [permissions.AllowAny]

    def get(self, request, user_id):
        User = __import__('django.conf', fromlist=['settings']).settings.AUTH_USER_MODEL
        from django.contrib.auth import get_user_model
        UserModel = get_user_model()
        user = get_object_or_404(UserModel, id=user_id)

        posts = Post.objects.filter(author=user).select_related("author").order_by("-created_at")
        post_count = posts.count()
        total_likes = posts.aggregate(total=Count('likes'))['total'] or 0

        serializer = PostSerializer(posts[:50], many=True, context={"request": request})

        return Response({
            "user": {
                "id": str(user.id),
                "name": user.get_short_name(),
                "email": user.email,
                "date_joined": user.date_joined,
            },
            "stats": {
                "posts": post_count,
                "total_likes": total_likes,
            },
            "posts": serializer.data,
        })
