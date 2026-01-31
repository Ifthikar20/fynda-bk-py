"""
Request Filters - Pre-processing and validation before API handlers

Provides stateless validation that happens before any business logic:
1. Content-type validation
2. Request size limits
3. JSON schema validation
4. Parameter sanitization
5. Path traversal prevention
"""

import json
import re
import logging
from django.http import JsonResponse
from django.conf import settings

logger = logging.getLogger(__name__)


class ContentTypeFilter:
    """
    Validate Content-Type header matches request body.
    
    Prevents attacks that send malicious payloads with wrong content-type.
    """
    
    # Methods that should have content-type for body
    BODY_METHODS = ["POST", "PUT", "PATCH"]
    
    # Allowed content types for API requests
    ALLOWED_CONTENT_TYPES = [
        "application/json",
        "multipart/form-data",
        "application/x-www-form-urlencoded",
    ]
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        if not request.path.startswith("/api/"):
            return self.get_response(request)
        
        if request.method in self.BODY_METHODS:
            content_type = request.content_type.split(";")[0].strip().lower()
            
            # Must have content-type for body requests
            if not content_type:
                return JsonResponse(
                    {"error": "Content-Type header required"},
                    status=400
                )
            
            # Must be allowed content type
            if content_type not in self.ALLOWED_CONTENT_TYPES:
                return JsonResponse(
                    {"error": "Unsupported Content-Type"},
                    status=415
                )
        
        return self.get_response(request)


class RequestSizeFilter:
    """
    Enforce strict request size limits.
    
    Different limits for different content types.
    """
    
    # Size limits in bytes
    SIZE_LIMITS = {
        "application/json": 1 * 1024 * 1024,      # 1MB for JSON
        "multipart/form-data": 10 * 1024 * 1024,  # 10MB for file uploads
        "default": 512 * 1024,                     # 512KB default
    }
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        if not request.path.startswith("/api/"):
            return self.get_response(request)
        
        content_length = request.META.get("CONTENT_LENGTH")
        if content_length:
            try:
                size = int(content_length)
            except ValueError:
                return JsonResponse({"error": "Invalid Content-Length"}, status=400)
            
            content_type = request.content_type.split(";")[0].strip().lower()
            limit = self.SIZE_LIMITS.get(content_type, self.SIZE_LIMITS["default"])
            
            if size > limit:
                logger.warning(f"Request too large: {size} bytes from {request.META.get('REMOTE_ADDR')}")
                return JsonResponse(
                    {"error": f"Request too large. Maximum size: {limit // 1024}KB"},
                    status=413
                )
        
        return self.get_response(request)


class PathTraversalFilter:
    """
    Prevent path traversal attacks in URLs and parameters.
    
    Blocks attempts to access files outside intended scope.
    """
    
    # Dangerous patterns
    DANGEROUS_PATTERNS = [
        r"\.\./",           # Parent directory
        r"\.\.\\",          # Windows parent directory
        r"%2e%2e/",         # URL encoded ..
        r"%2e%2e\\",        # URL encoded ..
        r"\.\.%2f",         # Mixed encoding
        r"%252e%252e",      # Double encoded
        r"/etc/",           # Linux system paths
        r"/proc/",
        r"/var/",
        r"c:\\",            # Windows paths
        r"\\\\",            # UNC paths
    ]
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.patterns = [re.compile(p, re.IGNORECASE) for p in self.DANGEROUS_PATTERNS]
    
    def __call__(self, request):
        # Check path
        full_path = request.get_full_path()
        
        for pattern in self.patterns:
            if pattern.search(full_path):
                logger.warning(f"Path traversal attempt: {full_path[:100]}")
                return JsonResponse({"error": "Invalid request"}, status=400)
        
        return self.get_response(request)


class ParameterValidationFilter:
    """
    Validate and sanitize common parameters.
    
    Enforces safe values for pagination, IDs, and filters.
    """
    
    # Maximum values for common parameters
    PARAM_LIMITS = {
        "limit": 100,
        "offset": 10000,
        "page": 1000,
        "per_page": 100,
        "size": 100,
    }
    
    # UUID pattern for ID validation
    UUID_PATTERN = re.compile(
        r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
        re.IGNORECASE
    )
    
    # Safe ID pattern (alphanumeric, hyphens, underscores)
    SAFE_ID_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        if not request.path.startswith("/api/"):
            return self.get_response(request)
        
        # Validate numeric parameters
        for param, max_val in self.PARAM_LIMITS.items():
            value = request.GET.get(param)
            if value:
                try:
                    num_val = int(value)
                    if num_val < 0 or num_val > max_val:
                        return JsonResponse(
                            {"error": f"Invalid {param}: must be 0-{max_val}"},
                            status=400
                        )
                except ValueError:
                    return JsonResponse(
                        {"error": f"Invalid {param}: must be a number"},
                        status=400
                    )
        
        # Validate ID parameters in path
        path_parts = request.path.split("/")
        for i, part in enumerate(path_parts):
            # If previous part looks like a resource name and this part is an ID
            if i > 0 and path_parts[i-1] in ["products", "users", "deals", "orders"]:
                if part and not self._is_valid_id(part):
                    return JsonResponse({"error": "Invalid ID format"}, status=400)
        
        return self.get_response(request)
    
    def _is_valid_id(self, value):
        """Check if value is a valid ID format."""
        # Allow UUIDs
        if self.UUID_PATTERN.match(value):
            return True
        
        # Allow safe alphanumeric IDs (max 64 chars)
        if len(value) <= 64 and self.SAFE_ID_PATTERN.match(value):
            return True
        
        # Allow numeric IDs
        try:
            int(value)
            return True
        except ValueError:
            pass
        
        return False


class JSONValidationFilter:
    """
    Validate JSON request bodies for common issues.
    
    Prevents:
    - Malformed JSON
    - Deeply nested structures (DoS)
    - Extremely long strings
    """
    
    MAX_NESTING_DEPTH = 10
    MAX_STRING_LENGTH = 10000
    MAX_ARRAY_LENGTH = 1000
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        if not request.path.startswith("/api/"):
            return self.get_response(request)
        
        if request.content_type.startswith("application/json"):
            if request.body:
                try:
                    data = json.loads(request.body)
                    
                    # Validate structure
                    issues = self._validate_structure(data)
                    if issues:
                        return JsonResponse({"error": issues[0]}, status=400)
                        
                except json.JSONDecodeError as e:
                    return JsonResponse(
                        {"error": f"Invalid JSON: {str(e)[:50]}"},
                        status=400
                    )
        
        return self.get_response(request)
    
    def _validate_structure(self, data, depth=0):
        """Recursively validate JSON structure."""
        issues = []
        
        if depth > self.MAX_NESTING_DEPTH:
            return ["JSON structure too deeply nested"]
        
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(key, str) and len(key) > 100:
                    issues.append("JSON key too long")
                    break
                issues.extend(self._validate_structure(value, depth + 1))
                if issues:
                    break
                    
        elif isinstance(data, list):
            if len(data) > self.MAX_ARRAY_LENGTH:
                return ["JSON array too large"]
            for item in data[:100]:  # Only check first 100 items
                issues.extend(self._validate_structure(item, depth + 1))
                if issues:
                    break
                    
        elif isinstance(data, str):
            if len(data) > self.MAX_STRING_LENGTH:
                issues.append("JSON string value too long")
        
        return issues
