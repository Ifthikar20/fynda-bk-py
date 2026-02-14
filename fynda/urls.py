"""
Fetchbot URL Configuration
"""

from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.sitemaps.views import sitemap

from fynda.config import config

from blog.sitemaps import PostSitemap, CategorySitemap, StaticBlogSitemap
from blog.feeds import LatestPostsFeed

# Sitemap configuration
sitemaps = {
    'posts': PostSitemap,
    'categories': CategorySitemap,
    'blog': StaticBlogSitemap,
}


def api_root(request):
    """API root with documentation."""
    return JsonResponse({
        "service": "Fynda API",
        "version": "1.0.0",
        "description": "Search for the best deals across multiple marketplaces",
        "notice": "Use /api/v1/ prefix. Unversioned /api/ is deprecated.",
        "endpoints": {
            "web": {
                "search": "/api/v1/search/?q=<query>",
                "upload": "/api/v1/upload/",
                "health": "/api/v1/health/",
                "auth": "/api/v1/auth/",
            },
            "mobile": {
                "base": "/api/v1/mobile/",
                "health": "/api/v1/mobile/health/",
                "auth": {
                    "login": "/api/v1/mobile/auth/login/",
                    "register": "/api/v1/mobile/auth/register/",
                    "logout": "/api/v1/mobile/auth/logout/",
                },
                "devices": "/api/v1/mobile/devices/",
                "preferences": "/api/v1/mobile/preferences/",
                "sync": "/api/v1/mobile/sync/",
                "deals": "/api/v1/mobile/deals/",
                "search": "/api/v1/mobile/deals/search/",
                "alerts": "/api/v1/mobile/alerts/",
                "favorites": "/api/v1/mobile/favorites/",
            },
            "blog": {
                "home": "/blog/",
                "post": "/blog/post/<slug>/",
                "search": "/blog/search/",
                "api": "/api/v1/blog/",
                "sitemap": "/sitemap.xml",
                "feed": "/blog/feed/",
            }
        },
        "example": "/api/v1/search/?q=sony+camera+$1200+with+lens",
    })


urlpatterns = [
    path('', api_root, name='api_root'),
    path(f'{config.security.admin_url}/', admin.site.urls),  # Dynamic admin URL from ADMIN_URL env var
    path('_nested_admin/', include('nested_admin.urls')),  # Nested admin assets

    # ── Versioned API (canonical) ─────────────────────────────────────
    path('api/v1/', include('deals.urls')),
    path('api/v1/', include('emails.urls')),
    path('api/v1/auth/', include('users.urls')),
    path('api/v1/mobile/', include('mobile.urls')),
    path('api/v1/blog/', include('blog.api_urls')),

    # ── Legacy unversioned API (deprecated, kept for backward compat) ─
    path('api/', include('deals.urls')),
    path('api/', include('emails.urls')),
    path('api/auth/', include('users.urls')),
    path('api/mobile/', include(('mobile.urls', 'mobile'), namespace='mobile-legacy')),
    path('api/blog/', include(('blog.api_urls', 'blog_api'), namespace='blog_api-legacy')),

    # Blog SSR (for SEO) — not versioned
    path('blog/', include('blog.urls')),
    path('blog/feed/', LatestPostsFeed(), name='blog_feed'),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Custom 404 handler
handler404 = 'blog.views.custom_404'
