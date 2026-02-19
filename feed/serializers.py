from rest_framework import serializers
from .models import Post, Comment


class AuthorSerializer(serializers.Serializer):
    """Lightweight user info for feed display."""
    id = serializers.UUIDField()
    name = serializers.SerializerMethodField()

    def get_name(self, user):
        return user.get_short_name()


class CommentSerializer(serializers.ModelSerializer):
    author = AuthorSerializer(source="user", read_only=True)

    class Meta:
        model = Comment
        fields = ["id", "author", "text", "created_at"]
        read_only_fields = ["id", "author", "created_at"]


class PostSerializer(serializers.ModelSerializer):
    author = AuthorSerializer(read_only=True)
    is_liked = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = [
            "id", "author", "image_url", "caption", "tags",
            "likes_count", "comments_count", "is_liked", "created_at",
        ]

    def get_is_liked(self, post):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return post.likes.filter(user=request.user).exists()
        return False

    def get_image_url(self, post):
        request = self.context.get("request")
        if post.image and request:
            return request.build_absolute_uri(post.image.url)
        return None


class PostCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Post
        fields = ["image", "caption", "tags"]

    def create(self, validated_data):
        validated_data["author"] = self.context["request"].user
        return super().create(validated_data)
