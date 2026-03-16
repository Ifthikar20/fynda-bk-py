"""
Management command to submit all published blog URLs to search engines.
Usage: python manage.py submit_urls_for_indexing
"""

from django.core.management.base import BaseCommand
from blog.services.indexing import bulk_submit_all_published


class Command(BaseCommand):
    help = "Submit all published blog post URLs to Google, Bing, and IndexNow for indexing"

    def handle(self, *args, **options):
        self.stdout.write("Submitting all published blog URLs for indexing...")
        count = bulk_submit_all_published()
        self.stdout.write(
            self.style.SUCCESS(f"Done! Submitted {count} URLs for indexing.")
        )
