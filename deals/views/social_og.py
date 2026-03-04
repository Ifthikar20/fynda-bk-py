"""
Social Crawler OG Meta Handler

Serves pre-rendered HTML with Open Graph meta tags when social media
crawlers (Pinterest, Facebook, Twitter) hit /share/<token>.

Regular browsers get the normal Vue SPA response.
Renders fashion board content for social previews with Outfi branding.
"""

import re
from django.http import HttpResponse
from django.views import View
from deals.repositories import SharedStoryboardRepository
from django.utils import timezone
from fynda.config import config


# Match user-agents from social media crawlers
CRAWLER_REGEX = re.compile(
    r"(Pinterestbot|facebookexternalhit|Facebot|Twitterbot|LinkedInBot"
    r"|Slackbot|WhatsApp|TelegramBot|Discordbot|vkShare|Googlebot"
    r"|bingbot|Applebot)",
    re.IGNORECASE,
)


class SharedStoryboardOGView(View):
    """
    When a social crawler requests /share/<token>, return a minimal HTML
    page with OG meta tags so the pin/card shows the storyboard content
    and Outfi branding.

    Regular browsers are served the normal SPA (handled by Nginx/Vue).
    """

    def get(self, request, token):
        ua = request.META.get("HTTP_USER_AGENT", "")

        # Only intercept social crawlers
        if not CRAWLER_REGEX.search(ua):
            # Let Nginx / Vue SPA handle it
            # Return a redirect to the SPA URL
            from django.shortcuts import redirect
            return redirect(f"/share/{token}")

        # Fetch storyboard data
        shared = SharedStoryboardRepository.get_by_token(token)

        if not shared:
            return HttpResponse(
                "<html><head><title>Not Found — outfi.</title></head>"
                "<body><p>Fashion board not found</p></body></html>",
                status=404,
            )

        if shared.expires_at and shared.expires_at < timezone.now():
            return HttpResponse(
                "<html><head><title>Expired — outfi.</title></head>"
                "<body><p>This fashion board has expired</p></body></html>",
                status=410,
            )

        # Extract hero image from the storyboard's first canvas item
        items = (shared.storyboard_data or {}).get("items", [])
        hero_image = items[0].get("image_url", "") if items else ""
        fallback_image = f"{config.email.site_url}/assets/outfi-og-banner.png"
        og_image = hero_image or fallback_image

        title = shared.title or "Fashion Board"
        owner_name = shared.user.first_name or "a creator"
        description = (
            f"Fashion board by {owner_name} on outfi.ai "
            f"— discover and share outfit inspiration."
        )
        share_url = f"{config.email.site_url}/share/{token}"

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{title} — outfi.</title>

    <!-- Open Graph -->
    <meta property="og:title" content="{title} — outfi." />
    <meta property="og:description" content="{description}" />
    <meta property="og:image" content="{og_image}" />
    <meta property="og:image:width" content="600" />
    <meta property="og:image:height" content="900" />
    <meta property="og:url" content="{share_url}" />
    <meta property="og:type" content="article" />
    <meta property="og:site_name" content="Outfi" />

    <!-- Pinterest -->
    <meta name="pinterest-rich-pin" content="true" />

    <!-- Twitter Card -->
    <meta name="twitter:card" content="summary_large_image" />
    <meta name="twitter:site" content="@outfi_ai" />
    <meta name="twitter:title" content="{title} — outfi." />
    <meta name="twitter:description" content="{description}" />
    <meta name="twitter:image" content="{og_image}" />

    <!-- Redirect real browsers to SPA -->
    <meta http-equiv="refresh" content="0; url={share_url}" />
</head>
<body>
    <h1>{title}</h1>
    <p>{description}</p>
    <img src="{og_image}" alt="{title}" />
    <p><a href="{config.email.site_url}">Explore more on outfi.ai</a></p>
</body>
</html>"""

        return HttpResponse(html, content_type="text/html; charset=utf-8")
