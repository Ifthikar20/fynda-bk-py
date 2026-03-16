"""
Blog Signals — Auto-submit to search engines when posts are published.
"""

import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender='blog.Post')
def auto_index_on_publish(sender, instance, created, **kwargs):
    """
    When a Post is saved with status='published', automatically
    notify search engines for indexing.
    """
    if instance.status != 'published':
        return

    # Only submit if the post has a published_at date (confirmed published)
    if not instance.published_at:
        return

    try:
        from blog.services.indexing import notify_search_engines
        post_url = instance.get_absolute_url()
        logger.info(f"[Signal] Post published: {instance.title} -> {post_url}")
        notify_search_engines(post_url, post=instance)
    except Exception as e:
        # Never let indexing errors break the save
        logger.warning(f"[Signal] Auto-indexing failed for {instance.title}: {e}")
