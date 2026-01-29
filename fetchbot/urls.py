"""
Fetchbot URL Configuration
"""

from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse
from django.conf import settings
from django.conf.urls.static import static


def api_root(request):
    """API root with documentation."""
    return JsonResponse({
        "service": "Fetch Bot API",
        "version": "1.0.0",
        "description": "Search for the best deals across multiple marketplaces",
        "endpoints": {
            "search": {
                "url": "/api/search/?q=<query>",
                "method": "GET",
                "description": "Search for deals using natural language"
            },
            "upload": {
                "url": "/api/upload/",
                "method": "POST",
                "description": "Upload product screenshot for extraction"
            },
            "health": {
                "url": "/api/health/",
                "method": "GET",
                "description": "Health check"
            },
            "auth": {
                "register": "/api/auth/register/",
                "login": "/api/auth/login/",
                "logout": "/api/auth/logout/",
                "profile": "/api/auth/profile/",
                "refresh": "/api/auth/token/refresh/"
            }
        },
        "example": "/api/search/?q=sony+camera+$1200+with+lens",
    })


urlpatterns = [
    path('', api_root, name='api_root'),
    path('admin/', admin.site.urls),
    path('api/', include('deals.urls')),
    path('api/auth/', include('users.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
