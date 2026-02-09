"""
Response Interceptors - Post-processing of API responses

Provides response-level protections:
1. Error message standardization (hide internal details)
2. Response timing normalization
3. Sensitive data masking
4. Response header hardening
"""

import json
import re
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


class ResponseInterceptor:
    """
    Intercept and sanitize API responses before sending to client.
    
    - Standardizes error messages
    - Masks sensitive data in responses
    - Adds security headers
    - Normalizes response timing
    """
    
    # Patterns to mask in responses
    SENSITIVE_PATTERNS = [
        # API keys
        (r'["\']?api[_-]?key["\']?\s*[:=]\s*["\']?([a-zA-Z0-9_-]{20,})["\']?', 'api_key', '***REDACTED***'),
        # Tokens
        (r'["\']?token["\']?\s*[:=]\s*["\']?([a-zA-Z0-9._-]{20,})["\']?', 'token', '***REDACTED***'),
        # Passwords
        (r'["\']?password["\']?\s*[:=]\s*["\']?([^"\']+)["\']?', 'password', '***REDACTED***'),
        # Email partial masking  
        (r'([a-zA-Z0-9._%+-]+)@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', None, None),  # Special handling
        # Credit card-like patterns (require separators to avoid matching JSON floats)
        (r'(?<![.\d])(\d{4})[- ](\d{4})[- ](\d{4})[- ](\d{4})(?!\d)', 'card', '****-****-****-\\4'),
    ]
    
    # Error messages to sanitize (map internal -> external)
    ERROR_MESSAGES = {
        "no such column": "Database error",
        "syntax error": "Invalid request",
        "connection refused": "Service temporarily unavailable",
        "timeout": "Request timed out",
        "permission denied": "Access denied",
        "does not exist": "Resource not found",
        "integrity error": "Invalid data",
        "duplicate key": "Resource already exists",
    }
    
    # Paths that must return sensitive data intact (auth tokens, etc.)
    EXEMPT_PATHS = [
        '/api/mobile/auth/login/',
        '/api/mobile/auth/register/',
        '/api/mobile/auth/oauth/',
        '/api/auth/token/refresh/',
    ]
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.patterns = [
            (re.compile(p[0], re.IGNORECASE), p[1], p[2]) 
            for p in self.SENSITIVE_PATTERNS
        ]
    
    def __call__(self, request):
        response = self.get_response(request)
        
        # Only process API responses
        if not request.path.startswith("/api/"):
            return response
        
        # Process error responses
        if response.status_code >= 400:
            response = self._sanitize_error(response)
        
        # Mask sensitive data in successful responses (skip auth endpoints)
        if response.status_code < 400 and request.path not in self.EXEMPT_PATHS:
            response = self._mask_sensitive_data(response)
        
        # Add anti-enumeration headers
        self._add_security_headers(response)
        
        return response
    
    def _sanitize_error(self, response):
        """Replace internal error details with safe messages."""
        if not settings.DEBUG:
            try:
                # Try to parse JSON response
                if hasattr(response, 'content'):
                    content = response.content.decode('utf-8')
                    data = json.loads(content)
                    
                    # Sanitize error messages
                    if 'error' in data:
                        data['error'] = self._sanitize_message(str(data['error']))
                    if 'detail' in data:
                        data['detail'] = self._sanitize_message(str(data['detail']))
                    if 'message' in data:
                        data['message'] = self._sanitize_message(str(data['message']))
                    
                    # Remove stack traces
                    data.pop('traceback', None)
                    data.pop('stack', None)
                    data.pop('exception', None)
                    
                    # Rebuild response
                    response.content = json.dumps(data).encode('utf-8')
                    
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass
        
        return response
    
    def _sanitize_message(self, message):
        """Replace internal error details with generic messages."""
        message_lower = message.lower()
        
        for internal, external in self.ERROR_MESSAGES.items():
            if internal in message_lower:
                return external
        
        # For unrecognized errors, return generic message
        if len(message) > 100 or any(word in message_lower for word in ['sql', 'exception', 'error at', 'file']):
            return "An error occurred"
        
        return message
    
    def _mask_sensitive_data(self, response):
        """Mask sensitive data patterns in response body."""
        try:
            if hasattr(response, 'content') and response.content:
                content = response.content.decode('utf-8')
                
                for pattern, field_type, replacement in self.patterns:
                    if field_type is None:
                        # Email special handling - partial mask
                        content = pattern.sub(
                            lambda m: f"{m.group(1)[:2]}***@{m.group(2)}",
                            content
                        )
                    elif replacement:
                        content = pattern.sub(replacement, content)
                
                response.content = content.encode('utf-8')
                
        except (UnicodeDecodeError, AttributeError):
            pass
        
        return response
    
    def _add_security_headers(self, response):
        """Add headers to help prevent enumeration."""
        # Don't leak server info
        response['Server'] = 'Fynda'
        
        # Prevent caching of API responses with sensitive data
        if not response.get('Cache-Control'):
            response['Cache-Control'] = 'no-store, no-cache, must-revalidate, private'
        
        # Remove headers that leak info
        for header in ['X-Powered-By', 'Via']:
            if header in response:
                del response[header]


class NotFoundNormalizerMiddleware:
    """
    Return consistent 404 responses for all "not found" cases.
    
    Prevents endpoint enumeration by returning identical responses
    for non-existent endpoints AND unauthorized access.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        
        # Only for API endpoints in production
        if not request.path.startswith("/api/") or settings.DEBUG:
            return response
        
        # Normalize 404 responses
        if response.status_code == 404:
            from django.http import JsonResponse
            return JsonResponse(
                {"error": "Not found"},
                status=404
            )
        
        return response


class ResponseTimingMiddleware:
    """
    ⚠️  WARNING: DO NOT ADD THIS TO MIDDLEWARE LIST — it sleeps 50-150ms per request!
    
    This was designed to normalize response timing for anti-enumeration, but the
    performance cost is unacceptable. Anti-enumeration is better handled by
    APIGuardMiddleware's honeypots and rate limiting.
    
    Kept here only as a reference. If timing normalization is truly needed,
    implement it only for specific sensitive endpoints (e.g. login).
    """
    
    import time
    
    # Target response time range (seconds)
    MIN_RESPONSE_TIME = 0.05  # 50ms minimum
    MAX_RESPONSE_TIME = 0.15  # 150ms maximum
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        import time
        import random
        
        if not request.path.startswith("/api/"):
            return self.get_response(request)
        
        start_time = time.time()
        response = self.get_response(request)
        elapsed = time.time() - start_time
        
        # Add delay to normalize timing
        target_time = random.uniform(self.MIN_RESPONSE_TIME, self.MAX_RESPONSE_TIME)
        if elapsed < target_time:
            time.sleep(target_time - elapsed)
        
        return response
