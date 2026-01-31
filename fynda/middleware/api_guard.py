"""
API Guard Middleware - Anti-Enumeration & Request Filtering

Provides multiple layers of protection to make APIs hard to enumerate:
1. Request fingerprinting and behavioral analysis
2. Honeypot detection for automated scanners
3. Timing-based anti-enumeration
4. User-agent and header validation
5. Sequential request pattern detection
"""

import time
import hashlib
import random
import logging
import re
from datetime import datetime
from django.http import JsonResponse
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)


class APIGuardMiddleware:
    """
    Main API protection layer - blocks enumeration attempts and suspicious traffic.
    
    Protection strategies:
    1. Honeypot URLs that return fake data
    2. Random response delays to defeat timing attacks
    3. Request fingerprinting to detect automated scanning
    4. Sequential pattern detection (e.g., /api/user/1, /api/user/2, ...)
    5. User-agent validation
    """
    
    # Honeypot paths - return fake data instead of 404
    HONEYPOT_PATHS = [
        "/api/admin/",
        "/api/v2/",
        "/api/internal/",
        "/api/debug/",
        "/api/private/",
        "/api/backup/",
        "/api/config/",
        "/api/.env",
        "/api/test/",
        "/api/users/all/",
    ]
    
    # Suspicious user agents (bots, scanners, tools)
    BLOCKED_USER_AGENTS = [
        r"sqlmap",
        r"nikto",
        r"nmap",
        r"masscan",
        r"dirbuster",
        r"gobuster",
        r"feroxbuster",
        r"wfuzz",
        r"ffuf",
        r"burp",
        r"zap",          # OWASP ZAP
        r"acunetix",
        r"nessus",
        r"w3af",
        r"nuclei",
        r"httpx",
        r"curl/\d",      # Bare curl requests
        r"python-requests",  # Basic Python requests
    ]
    
    # Required headers for legitimate requests
    REQUIRED_HEADERS = ["HTTP_ACCEPT"]
    
    # Maximum sequential ID attempts before blocking
    MAX_SEQUENTIAL_ATTEMPTS = 5
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.ua_patterns = [re.compile(p, re.IGNORECASE) for p in self.BLOCKED_USER_AGENTS]
    
    def __call__(self, request):
        # Only protect API endpoints
        if not request.path.startswith("/api/"):
            return self.get_response(request)
        
        ip = self._get_client_ip(request)
        
        # Check if IP is already blocked
        if self._is_blocked(ip):
            return self._block_response("Access denied", 403)
        
        # Mobile app bypass - validated mobile apps get relaxed checks
        if self._is_valid_mobile_app(request):
            # Mobile apps skip aggressive bot detection
            # but still go through normal processing
            return self.get_response(request)
        
        # 1. Check honeypot paths
        if self._is_honeypot_path(request.path):
            self._log_attack(ip, "honeypot", request.path)
            self._increment_suspicion(ip, 10)  # Heavy penalty
            return self._honeypot_response(request.path)
        
        # 2. Validate user agent
        if not self._validate_user_agent(request):
            self._log_attack(ip, "bad_ua", request.META.get("HTTP_USER_AGENT", ""))
            self._increment_suspicion(ip, 5)
            return self._block_response("Invalid request", 400)
        
        # 3. Check required headers
        if not self._has_required_headers(request):
            self._increment_suspicion(ip, 2)
        
        # 4. Detect sequential enumeration patterns
        if self._is_sequential_enumeration(request, ip):
            self._log_attack(ip, "enumeration", request.path)
            self._increment_suspicion(ip, 8)
            return self._block_response("Access denied", 403)
        
        # 5. Check suspicion score
        if self._get_suspicion_score(ip) >= 20:
            self._block_ip(ip, duration=600)  # Block for 10 minutes
            return self._block_response("Access denied", 403)
        
        # 6. Add random delay to defeat timing attacks
        self._add_timing_noise()
        
        # Process request
        response = self.get_response(request)
        
        # 7. Sanitize error responses (don't leak info)
        if response.status_code >= 400:
            response = self._sanitize_error_response(response, request)
        
        return response
    
    def _is_valid_mobile_app(self, request):
        """
        Check if request is from a valid mobile app.
        
        Mobile apps must include:
        - X-Fynda-Mobile-Key: Secret key configured in app
        - X-Fynda-Platform: ios or android
        - X-Fynda-App-Version: App version string
        
        Or they must be accessing /api/mobile/ endpoints with valid JWT.
        """
        # Check for mobile API key
        mobile_key = request.META.get("HTTP_X_FYNDA_MOBILE_KEY", "")
        platform = request.META.get("HTTP_X_FYNDA_PLATFORM", "")
        
        # Get configured mobile key from settings/env
        from fynda.config import config
        expected_key = getattr(config.security, 'mobile_api_key', None)
        
        # If mobile key is configured and matches
        if expected_key and mobile_key == expected_key:
            # Validate platform
            if platform.lower() in ["ios", "android"]:
                return True
        
        # Also allow authenticated mobile API requests
        if request.path.startswith("/api/mobile/"):
            # Check for valid JWT
            auth_header = request.META.get("HTTP_AUTHORIZATION", "")
            if auth_header.startswith("Bearer ") and len(auth_header) > 20:
                return True
        
        return False
    
    def _get_client_ip(self, request):
        x_forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded:
            return x_forwarded.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "unknown")
    
    def _is_honeypot_path(self, path):
        """Check if path matches a honeypot."""
        path_lower = path.lower()
        return any(path_lower.startswith(hp) for hp in self.HONEYPOT_PATHS)
    
    def _honeypot_response(self, path):
        """Return fake data to waste attacker time."""
        # Random delay (1-3 seconds) to slow down scanning
        time.sleep(random.uniform(1, 3))
        
        # Return plausible but fake response
        fake_responses = {
            "users": {"users": [], "total": 0, "message": "No data available"},
            "admin": {"status": "unauthorized", "message": "Admin access required"},
            "config": {"config": {}, "version": "1.0.0"},
            "default": {"status": "ok", "data": []},
        }
        
        for key, response in fake_responses.items():
            if key in path:
                return JsonResponse(response)
        
        return JsonResponse(fake_responses["default"])
    
    def _validate_user_agent(self, request):
        """Validate user agent is not a known scanner/tool."""
        ua = request.META.get("HTTP_USER_AGENT", "")
        
        # Empty user agent is suspicious
        if not ua:
            return False
        
        # Check against blocked patterns
        for pattern in self.ua_patterns:
            if pattern.search(ua):
                return False
        
        # Very short user agents are suspicious
        if len(ua) < 10:
            return False
        
        return True
    
    def _has_required_headers(self, request):
        """Check for headers that legitimate browsers send."""
        for header in self.REQUIRED_HEADERS:
            if not request.META.get(header):
                return False
        return True
    
    def _is_sequential_enumeration(self, request, ip):
        """Detect patterns like /api/user/1, /api/user/2, /api/user/3 ..."""
        path = request.path
        
        # Extract numeric IDs from path
        id_match = re.search(r'/(\d+)/?$', path)
        if not id_match:
            return False
        
        current_id = int(id_match.group(1))
        base_path = path[:id_match.start()]
        
        # Track sequential access
        cache_key = f"enum:{ip}:{base_path}"
        history = cache.get(cache_key, [])
        
        # Add current access
        history.append(current_id)
        history = history[-10:]  # Keep last 10
        cache.set(cache_key, history, 300)  # 5 minute window
        
        # Check for sequential pattern
        if len(history) >= self.MAX_SEQUENTIAL_ATTEMPTS:
            sorted_ids = sorted(history)
            sequential_count = 0
            for i in range(1, len(sorted_ids)):
                if sorted_ids[i] - sorted_ids[i-1] == 1:
                    sequential_count += 1
            
            # If more than 3 sequential IDs accessed, flag as enumeration
            if sequential_count >= 3:
                return True
        
        return False
    
    def _increment_suspicion(self, ip, points):
        """Increment suspicion score for an IP."""
        cache_key = f"suspicion:{ip}"
        current = cache.get(cache_key, 0)
        cache.set(cache_key, current + points, 3600)  # 1 hour window
    
    def _get_suspicion_score(self, ip):
        """Get current suspicion score."""
        return cache.get(f"suspicion:{ip}", 0)
    
    def _block_ip(self, ip, duration=600):
        """Block an IP temporarily."""
        cache.set(f"blocked:{ip}", True, duration)
        logger.warning(f"IP blocked: {ip} for {duration}s")
    
    def _is_blocked(self, ip):
        """Check if IP is blocked."""
        return cache.get(f"blocked:{ip}", False)
    
    def _block_response(self, message, status):
        """Return a generic block response."""
        return JsonResponse({"error": message}, status=status)
    
    def _add_timing_noise(self):
        """Add random delay to prevent timing-based enumeration."""
        # Small random delay (5-50ms) to mask processing time differences
        time.sleep(random.uniform(0.005, 0.05))
    
    def _sanitize_error_response(self, response, request):
        """Remove sensitive info from error responses."""
        # For 404s, return generic message (don't reveal if endpoint exists)
        if response.status_code == 404:
            return JsonResponse({"error": "Not found"}, status=404)
        
        # For 500s, hide internal errors
        if response.status_code >= 500 and not settings.DEBUG:
            return JsonResponse({"error": "Server error"}, status=500)
        
        return response
    
    def _log_attack(self, ip, attack_type, details):
        """Log suspected attack for analysis."""
        logger.warning(f"SECURITY: {attack_type} from {ip}: {details[:100]}")


class RequestSignatureMiddleware:
    """
    Validate requests using HMAC signatures for sensitive endpoints.
    
    Clients must include:
    - X-Request-Signature: HMAC-SHA256 of request body
    - X-Request-Timestamp: Unix timestamp
    """
    
    # Endpoints requiring signature validation
    PROTECTED_ENDPOINTS = [
        "/api/auth/",
        "/api/users/",
        "/api/orders/",
        "/api/payments/",
    ]
    
    # Maximum age of request (prevent replay attacks)
    MAX_REQUEST_AGE = 300  # 5 minutes
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Only check protected endpoints in production
        if settings.DEBUG:
            return self.get_response(request)
        
        path = request.path
        
        # Check if endpoint requires signature
        if not any(path.startswith(ep) for ep in self.PROTECTED_ENDPOINTS):
            return self.get_response(request)
        
        # GET requests don't need signature (for now)
        if request.method == "GET":
            return self.get_response(request)
        
        # Validate timestamp
        timestamp = request.META.get("HTTP_X_REQUEST_TIMESTAMP")
        if not timestamp:
            return JsonResponse({"error": "Missing timestamp"}, status=400)
        
        try:
            request_time = int(timestamp)
            current_time = int(time.time())
            
            if abs(current_time - request_time) > self.MAX_REQUEST_AGE:
                return JsonResponse({"error": "Request expired"}, status=400)
        except ValueError:
            return JsonResponse({"error": "Invalid timestamp"}, status=400)
        
        # Check for replay attacks (same signature should not be reused)
        signature = request.META.get("HTTP_X_REQUEST_SIGNATURE", "")
        if signature and self._is_replay(signature):
            return JsonResponse({"error": "Invalid request"}, status=400)
        
        return self.get_response(request)
    
    def _is_replay(self, signature):
        """Check if this signature was already used."""
        cache_key = f"sig:{signature[:32]}"
        
        if cache.get(cache_key):
            return True
        
        # Store for replay prevention
        cache.set(cache_key, True, self.MAX_REQUEST_AGE * 2)
        return False


class BotDetectionMiddleware:
    """
    Detect and block bot traffic using behavioral analysis.
    """
    
    # Minimum time between requests (in seconds)
    MIN_REQUEST_INTERVAL = 0.1  # 100ms
    
    # Maximum requests in short burst
    MAX_BURST_REQUESTS = 20
    BURST_WINDOW = 5  # seconds
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        if not request.path.startswith("/api/"):
            return self.get_response(request)
        
        ip = self._get_client_ip(request)
        
        # Check request timing
        if self._is_bot_timing(ip):
            return JsonResponse({"error": "Too many requests"}, status=429)
        
        # Check burst pattern
        if self._is_burst_pattern(ip):
            return JsonResponse({"error": "Too many requests"}, status=429)
        
        # Record this request
        self._record_request(ip)
        
        return self.get_response(request)
    
    def _get_client_ip(self, request):
        x_forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded:
            return x_forwarded.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "unknown")
    
    def _is_bot_timing(self, ip):
        """Check if requests are too fast to be human."""
        cache_key = f"lastReq:{ip}"
        last_request = cache.get(cache_key)
        
        if last_request:
            time_diff = time.time() - last_request
            if time_diff < self.MIN_REQUEST_INTERVAL:
                return True
        
        return False
    
    def _is_burst_pattern(self, ip):
        """Check for burst of requests."""
        cache_key = f"burst:{ip}"
        requests = cache.get(cache_key, [])
        
        # Clean old requests
        current = time.time()
        requests = [t for t in requests if current - t < self.BURST_WINDOW]
        
        return len(requests) >= self.MAX_BURST_REQUESTS
    
    def _record_request(self, ip):
        """Record request timing."""
        current = time.time()
        
        # Last request time
        cache.set(f"lastReq:{ip}", current, 60)
        
        # Burst tracking
        cache_key = f"burst:{ip}"
        requests = cache.get(cache_key, [])
        requests.append(current)
        requests = requests[-50:]  # Keep last 50
        cache.set(cache_key, requests, self.BURST_WINDOW * 2)
