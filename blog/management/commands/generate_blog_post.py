"""
Management command to generate AI-powered blog posts.

Usage:
    python manage.py generate_blog_post                          # Random topic
    python manage.py generate_blog_post --topic "summer dresses" # Specific topic
    python manage.py generate_blog_post --count 3                # Multiple posts
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from blog.services.blog_generator import generate_blog_post, save_blog_post

User = get_user_model()


class Command(BaseCommand):
    help = "Generate AI-powered fashion blog posts (saved as drafts)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--topic",
            type=str,
            default=None,
            help="Specific topic to write about. If omitted, a random topic is chosen.",
        )
        parser.add_argument(
            "--count",
            type=int,
            default=1,
            help="Number of posts to generate (default: 1)",
        )

    def handle(self, *args, **options):
        topic = options["topic"]
        count = options["count"]

        # Get first superuser as author (fallback to None)
        author = User.objects.filter(is_superuser=True).first()

        self.stdout.write(
            self.style.NOTICE(f"Generating {count} blog post(s)...")
        )

        success = 0
        for i in range(count):
            self.stdout.write(f"\n--- Post {i + 1}/{count} ---")

            # Generate content
            data = generate_blog_post(topic=topic)
            if not data:
                self.stdout.write(self.style.ERROR("Failed to generate content"))
                continue

            self.stdout.write(f"  Title: {data['title']}")
            self.stdout.write(f"  Category: {data.get('category', 'N/A')}")
            self.stdout.write(f"  Tags: {', '.join(data.get('tags', []))}")

            # Save to database
            post = save_blog_post(data, author=author)
            if post:
                self.stdout.write(
                    self.style.SUCCESS(f"  ✓ Saved as draft (id={post.id})")
                )
                success += 1
            else:
                self.stdout.write(self.style.ERROR("  ✗ Failed to save"))

        self.stdout.write(
            self.style.SUCCESS(f"\nDone! {success}/{count} posts generated as drafts.")
        )
        self.stdout.write("Review and publish them in Django Admin → Blog → Posts")
