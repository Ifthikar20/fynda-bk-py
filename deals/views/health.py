"""
Health check endpoint for deployment platforms.
"""

from django.http import JsonResponse
from django.views import View


class HealthCheckView(View):
    """
    Simple health check endpoint for load balancers and deployment platforms.
    Returns 200 OK if the service is running.
    """
    
    def get(self, request):
        return JsonResponse({
            "status": "healthy",
            "service": "fetchbot-api",
            "version": "1.0.0",
        })
