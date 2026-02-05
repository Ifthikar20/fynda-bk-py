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
        "endpoints": {
            "web": {
                "search": "/api/search/?q=<query>",
                "upload": "/api/upload/",
                "health": "/api/health/",
                "auth": "/api/auth/",
            },
            "mobile": {
                "base": "/api/mobile/",
                "health": "/api/mobile/health/",
                "auth": {
                    "login": "/api/mobile/auth/login/",
                    "register": "/api/mobile/auth/register/",
                    "logout": "/api/mobile/auth/logout/",
                },
                "devices": "/api/mobile/devices/",
                "preferences": "/api/mobile/preferences/",
                "sync": "/api/mobile/sync/",
                "deals": "/api/mobile/deals/",
                "search": "/api/mobile/deals/search/",
                "alerts": "/api/mobile/alerts/",
                "favorites": "/api/mobile/favorites/",
            },
            "blog": {
                "home": "/blog/",
                "post": "/blog/post/<slug>/",
                "search": "/blog/search/",
                "sitemap": "/sitemap.xml",
                "feed": "/blog/feed/",
            }
        },
        "example": "/api/search/?q=sony+camera+$1200+with+lens",
    })


urlpatterns = [
    path('', api_root, name='api_root'),
    path(f'{config.security.admin_url}/', admin.site.urls),  # Dynamic admin URL from ADMIN_URL env var
    path('_nested_admin/', include('nested_admin.urls')),  # Nested admin assets
    path('api/', include('deals.urls')),
    path('api/', include('emails.urls')),
    path('api/auth/', include('users.urls')),
    # Blog API (for Vue frontend)
    path('api/blog/', include('blog.api_urls')),
    # Blog SSR (for SEO)
    path('blog/', include('blog.urls')),
    path('blog/feed/', LatestPostsFeed(), name='blog_feed'),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Custom 404 handler
handler404 = 'blog.views.custom_404'
