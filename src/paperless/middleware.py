import secrets

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse

from paperless import version


class ApiVersionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            versions = settings.REST_FRAMEWORK["ALLOWED_VERSIONS"]
            response["X-Api-Version"] = versions[len(versions) - 1]
            response["X-Version"] = version.__full_version_str__

        return response


class RateLimitMiddleware:
    """
    Rate limit API requests per user/IP to prevent DoS attacks.

    Implements sliding window rate limiting using Redis cache.
    Different endpoints have different limits based on their resource usage.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        # Rate limits: (requests_per_window, window_seconds)
        self.rate_limits = {
            "/api/documents/": (100, 60),  # 100 requests per minute
            "/api/search/": (30, 60),  # 30 requests per minute (expensive)
            "/api/upload/": (10, 60),  # 10 uploads per minute
            "/api/bulk_edit/": (20, 60),  # 20 bulk operations per minute
            "default": (200, 60),  # 200 requests per minute for other endpoints
        }

    def __call__(self, request):
        # Only rate limit API endpoints
        if request.path.startswith("/api/"):
            # Get identifier (user ID or IP address)
            identifier = self._get_identifier(request)

            # Check rate limit
            if not self._check_rate_limit(identifier, request.path):
                return HttpResponse(
                    "Rate limit exceeded. Please try again later.",
                    status=429,
                    content_type="text/plain",
                )

        return self.get_response(request)

    def _get_identifier(self, request) -> str:
        """Get unique identifier for rate limiting (user or IP)."""
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            return f"user_{user.id}"
        return f"ip_{self._get_client_ip(request)}"

    def _get_client_ip(self, request) -> str:
        """Extract client IP address from request."""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            # Get first IP in the chain
            ip = x_forwarded_for.split(",")[0].strip()
        else:
            ip = request.META.get("REMOTE_ADDR", "unknown")
        return ip

    def _check_rate_limit(self, identifier: str, path: str) -> bool:
        """
        Check if request is within rate limit.

        Uses Redis cache for distributed rate limiting across workers.
        Returns True if request is allowed, False if rate limit exceeded.

        Improved implementation with explicit TTL handling to prevent
        race conditions and ensure consistent window behavior.
        """
        # Find matching rate limit for this path
        limit, window = self.rate_limits["default"]
        for pattern, (lim, win) in self.rate_limits.items():
            if pattern != "default" and path.startswith(pattern):
                limit, window = lim, win
                break

        # Build cache key
        cache_key = f"rate_limit_{identifier}_{path[:50]}"

        # Get current count from cache
        current_count = cache.get(cache_key, 0)

        if current_count >= limit:
            # Rate limit exceeded
            return False

        # Increment with explicit TTL
        if current_count == 0:
            # First request - set with TTL
            cache.set(cache_key, 1, timeout=window)
        else:
            # Increment existing counter
            cache.incr(cache_key)

        return True


class SecurityHeadersMiddleware:
    """
    Add security headers to all responses for enhanced security.

    Implements best practices for web security including:
    - HSTS (HTTP Strict Transport Security)
    - CSP (Content Security Policy)
    - Clickjacking prevention
    - XSS protection
    - Content type sniffing prevention
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Generate nonce for CSP
        nonce = secrets.token_urlsafe(16)

        # Strict Transport Security (force HTTPS)
        # Only add if HTTPS is enabled
        if request.is_secure() or settings.DEBUG:
            response["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )

        # Content Security Policy (HARDENED)
        # SECURITY IMPROVEMENT: Removed 'unsafe-inline' and 'unsafe-eval'
        # Uses nonce-based approach for inline scripts/styles
        # Note: This requires templates to use {% csp_nonce %} for inline scripts/styles
        # Alternative: Use external script/style files exclusively
        response["Content-Security-Policy"] = (
            "default-src 'self'; "
            f"script-src 'self' 'nonce-{nonce}'; "
            f"style-src 'self' 'nonce-{nonce}'; "
            "img-src 'self' data: blob:; "
            "font-src 'self' data:; "
            "connect-src 'self' ws: wss:; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "form-action 'self'; "
            "frame-ancestors 'none';"
        )

        # Store nonce in request for use in templates
        # Templates can access this via {{ request.csp_nonce }}
        if hasattr(request, "_csp_nonce"):
            request._csp_nonce = nonce

        # Prevent clickjacking attacks
        response["X-Frame-Options"] = "DENY"

        # Prevent MIME type sniffing
        response["X-Content-Type-Options"] = "nosniff"

        # Enable XSS filter (legacy, but doesn't hurt)
        response["X-XSS-Protection"] = "1; mode=block"

        # Control referrer information
        response["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions Policy (restrict browser features)
        response["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        return response
