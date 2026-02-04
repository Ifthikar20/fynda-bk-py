"""
Blog RSS/Atom Feeds
"""

from django.contrib.syndication.views import Feed
from django.urls import reverse
from .models import Post


class LatestPostsFeed(Feed):
    """RSS feed for latest blog posts."""
    title = "Fynda Fashion Blog"
    link = "/blog/"
    description = "Latest fashion deals, style tips, and shopping inspiration from Fynda."
    
    def items(self):
        return Post.objects.filter(status='published')[:10]
    
    def item_title(self, item):
        return item.title
    
    def item_description(self, item):
        return item.excerpt
    
    def item_pubdate(self, item):
        return item.published_at
    
    def item_author_name(self, item):
        if item.author:
            return item.author.get_full_name() or item.author.username
        return "Fynda Team"
    
    def item_categories(self, item):
        return [tag.name for tag in item.tags.all()]
