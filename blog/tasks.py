"""
Celery tasks for automated blog post generation.

Scheduled via CELERY_BEAT_SCHEDULE in settings.
"""

import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=300,  # 5 min between retries
    name="blog.generate_blog_post",
)
def generate_blog_post_task(self):
    """
    Generate a new AI-powered blog post and save it as a draft.
    
    This task is scheduled to run 3x/week via Celery Beat.
    Posts are saved as drafts — an editor must review and publish them.
    """
    from blog.services.blog_generator import generate_blog_post, save_blog_post
    from django.contrib.auth import get_user_model

    User = get_user_model()

    try:
        logger.info("Starting automated blog post generation...")

        # Generate content
        data = generate_blog_post()
        if not data:
            logger.error("Blog generation returned None — retrying")
            raise self.retry(exc=Exception("Generation failed"))

        # Save as draft
        author = User.objects.filter(is_superuser=True).first()
        post = save_blog_post(data, author=author)

        if post:
            logger.info(
                f"Blog post generated and saved as draft: "
                f"'{post.title}' (id={post.id})"
            )
            return {
                "status": "success",
                "post_id": post.id,
                "title": post.title,
            }
        else:
            logger.error("Failed to save blog post — retrying")
            raise self.retry(exc=Exception("Save failed"))

    except self.MaxRetriesExceededError:
        logger.error("Blog generation failed after 3 retries")
        return {"status": "failed", "error": "Max retries exceeded"}

    except Exception as exc:
        logger.error(f"Blog generation error: {exc}")
        raise self.retry(exc=exc)
