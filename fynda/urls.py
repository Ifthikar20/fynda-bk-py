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
            }
        },
        "example": "/api/search/?q=sony+camera+$1200+with+lens",
    })


urlpatterns = [
    path('', api_root, name='api_root'),
    path('admin/', admin.site.urls),
    path('api/', include('deals.urls')),
    path('api/', include('emails.urls')),
    path('api/auth/', include('users.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

