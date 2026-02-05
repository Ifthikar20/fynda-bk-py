"""
Blog API URL Configuration
"""

from django.urls import path
from . import api_views

app_name = 'blog_api'

urlpatterns = [
    path('posts/', api_views.BlogPostListView.as_view(), name='post_list'),
    path('posts/featured/', api_views.blog_featured, name='featured'),
    path('posts/<slug:slug>/', api_views.BlogPostDetailView.as_view(), name='post_detail'),
    path('categories/', api_views.CategoryListView.as_view(), name='category_list'),
]
