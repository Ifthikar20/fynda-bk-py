"""
Custom Security Middleware for Fetch Bot

Provides additional security headers and request validation.
"""

import logging
import re
from django.http import JsonResponse
from django.conf import settings

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware:
    """
    Add security headers to all responses.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        
        # Content Security Policy
        if not settings.DEBUG:
            response["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "font-src 'self' https://fonts.gstatic.com; "
                "img-src 'self' data: https: blob:; "
                "connect-src 'self' https:; "
                "frame-ancestors 'none';"
            )
        
        # Additional security headers
        response["X-Content-Type-Options"] = "nosniff"
        response["X-Frame-Options"] = "DENY"
        response["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        
        return response


class RateLimitMiddleware:
    """
    Additional rate limiting based on IP address.
    Uses Django's cache for tracking.
    """
    
    # Limits per minute
    RATE_LIMITS = {
        "search": 30,  # 30 searches per minute
        "api": 60,     # 60 API calls per minute
    }
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Only apply to API endpoints
        if not request.path.startswith("/api/"):
            return self.get_response(request)
        
        ip = self.get_client_ip(request)
        
        # Check rate limit for search endpoint
        if "/search" in request.path:
            if self.is_rate_limited(ip, "search", self.RATE_LIMITS["search"]):
                return JsonResponse(
                    {"error": "Rate limit exceeded. Please try again later."},
                    status=429
                )
        
        return self.get_response(request)
    
    def get_client_ip(self, request):
        """Get the real client IP, handling proxies."""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0].strip()
        else:
            ip = request.META.get("REMOTE_ADDR", "unknown")
        return ip
    
    def is_rate_limited(self, ip: str, endpoint: str, limit: int) -> bool:
        """Check if IP has exceeded rate limit."""
        from django.core.cache import cache
        
        cache_key = f"ratelimit:{endpoint}:{ip}"
        current = cache.get(cache_key, 0)
        
        if current >= limit:
            logger.warning(f"Rate limit exceeded for {ip} on {endpoint}")
            return True
        
        # Increment counter (expires in 60 seconds)
        cache.set(cache_key, current + 1, 60)
        return False


class InputSanitizationMiddleware:
    """
    Sanitize and validate incoming requests.
    """
    
    # Patterns that might indicate SQL injection or XSS
    SUSPICIOUS_PATTERNS = [
        r"<script",
        r"javascript:",
        r"on\w+\s*=",
        r"SELECT.*FROM",
        r"INSERT\s+INTO",
        r"DELETE\s+FROM",
        r"DROP\s+TABLE",
        r"UNION\s+SELECT",
    ]
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.patterns = [re.compile(p, re.IGNORECASE) for p in self.SUSPICIOUS_PATTERNS]
    
    def __call__(self, request):
        # Check query parameters
        query_string = request.META.get("QUERY_STRING", "")
        
        for pattern in self.patterns:
            if pattern.search(query_string):
                logger.warning(f"Suspicious request blocked: {request.path}?{query_string[:100]}")
                return JsonResponse(
                    {"error": "Invalid request"},
                    status=400
                )
        
        return self.get_response(request)


class RequestLoggingMiddleware:
    """
    Log all API requests for security auditing.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Log the request
        if request.path.startswith("/api/"):
            ip = self.get_client_ip(request)
            logger.info(f"API Request: {request.method} {request.path} from {ip}")
        
        response = self.get_response(request)
        
        # Log errors
        if response.status_code >= 400:
            logger.warning(f"API Error {response.status_code}: {request.method} {request.path}")
        
        return response
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "unknown")
