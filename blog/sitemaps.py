"""
Blog Sitemaps - Auto-generated XML sitemap for SEO
"""

from django.contrib.sitemaps import Sitemap
from .models import Post, Category


class PostSitemap(Sitemap):
    """Sitemap for blog posts."""
    changefreq = 'weekly'
    priority = 0.8
    protocol = 'https'
    
    def items(self):
        return Post.objects.filter(status='published')
    
    def lastmod(self, obj):
        return obj.updated_at
    
    def location(self, obj):
        return f'/blog/post/{obj.slug}/'


class CategorySitemap(Sitemap):
    """Sitemap for categories."""
    changefreq = 'weekly'
    priority = 0.6
    protocol = 'https'
    
    def items(self):
        return Category.objects.all()
    
    def location(self, obj):
        return f'/blog/category/{obj.slug}/'


class StaticBlogSitemap(Sitemap):
    """Sitemap for static blog pages."""
    changefreq = 'daily'
    priority = 0.9
    protocol = 'https'
    
    def items(self):
        return ['blog_home']
    
    def location(self, item):
        return '/blog/'
