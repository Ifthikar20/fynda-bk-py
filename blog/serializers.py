"""
Blog API Serializers - REST API for blog posts
"""

from rest_framework import serializers
from .models import Post, Category, Tag


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ['id', 'name', 'slug']


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'description']


class PostListSerializer(serializers.ModelSerializer):
    """Serializer for blog post list (minimal data)."""
    category = CategorySerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    featured_image_url = serializers.SerializerMethodField()
    author_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Post
        fields = [
            'id', 'title', 'slug', 'excerpt', 
            'featured_image_url', 'category', 'tags',
            'author_name', 'published_at', 'reading_time'
        ]
    
    def get_featured_image_url(self, obj):
        if obj.featured_image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.featured_image.url)
            return obj.featured_image.url
        return None
    
    def get_author_name(self, obj):
        if obj.author:
            return obj.author.get_full_name() or obj.author.email
        return 'Fynda Team'


class PostDetailSerializer(serializers.ModelSerializer):
    """Serializer for blog post detail (full data)."""
    category = CategorySerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    featured_image_url = serializers.SerializerMethodField()
    author_name = serializers.SerializerMethodField()
    seo_title = serializers.CharField(read_only=True)
    seo_description = serializers.CharField(read_only=True)
    
    class Meta:
        model = Post
        fields = [
            'id', 'title', 'slug', 'excerpt', 'content',
            'featured_image_url', 'category', 'tags',
            'author_name', 'published_at', 'updated_at',
            'reading_time', 'seo_title', 'seo_description'
        ]
    
    def get_featured_image_url(self, obj):
        if obj.featured_image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.featured_image.url)
            return obj.featured_image.url
        return None
    
    def get_author_name(self, obj):
        if obj.author:
            return obj.author.get_full_name() or obj.author.email
        return 'Fynda Team'
