"""
Blog API Views - REST API endpoints for blog posts
"""

from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.decorators import api_view
from rest_framework.permissions import AllowAny
from django.db.models import Q
from .models import Post, Category
from .serializers import PostListSerializer, PostDetailSerializer, CategorySerializer


class BlogPostListView(generics.ListAPIView):
    """
    List all published blog posts.
    Supports filtering by category and search.
    """
    serializer_class = PostListSerializer
    permission_classes = [AllowAny]
    
    def get_queryset(self):
        queryset = Post.objects.filter(status='published').select_related(
            'category', 'author'
        ).prefetch_related('tags')
        
        # Filter by category
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category__slug=category)
        
        # Search
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) | 
                Q(excerpt__icontains=search) |
                Q(content__icontains=search)
            )
        
        return queryset


class BlogPostDetailView(generics.RetrieveAPIView):
    """
    Get a single blog post by slug.
    """
    serializer_class = PostDetailSerializer
    permission_classes = [AllowAny]
    lookup_field = 'slug'
    
    def get_queryset(self):
        return Post.objects.filter(status='published').select_related(
            'category', 'author'
        ).prefetch_related('tags')


class CategoryListView(generics.ListAPIView):
    """
    List all blog categories.
    """
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]
    queryset = Category.objects.all()


@api_view(['GET'])
def blog_featured(request):
    """
    Get featured/latest blog posts for homepage.
    """
    posts = Post.objects.filter(status='published').select_related(
        'category', 'author'
    ).prefetch_related('tags')[:6]
    
    serializer = PostListSerializer(posts, many=True, context={'request': request})
    return Response(serializer.data)
