"""Rate limiting middleware for API endpoints."""

from typing import Optional
from time import time
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """Token bucket rate limiter for per-endpoint rate limiting."""

    def __init__(self, default_rate: int = 1000, default_period: int = 60):
        """
        Initialize rate limiter.

        Args:
            default_rate: Default requests per period
            default_period: Default period in seconds (60 = 1 minute)
        """
        self.default_rate = default_rate
        self.default_period = default_period
        self.buckets = defaultdict(lambda: {"tokens": default_rate, "last_reset": time()})
        self.endpoint_limits = {}

    def set_limit(self, endpoint: str, rate: int, period: int) -> None:
        """Set custom rate limit for specific endpoint."""
        self.endpoint_limits[endpoint] = {"rate": rate, "period": period}

    def is_allowed(self, client_id: str, endpoint: str = "default") -> tuple[bool, dict]:
        """
        Check if request is allowed and return rate limit info.

        Args:
            client_id: Client identifier (IP address, API key, etc.)
            endpoint: API endpoint being accessed

        Returns:
            (is_allowed: bool, info: dict with rate limit details)
        """
        key = f"{client_id}:{endpoint}"
        now = time()

        # Get endpoint-specific limits or use defaults
        if endpoint in self.endpoint_limits:
            rate = self.endpoint_limits[endpoint]["rate"]
            period = self.endpoint_limits[endpoint]["period"]
        else:
            rate = self.default_rate
            period = self.default_period

        bucket = self.buckets[key]
        time_passed = now - bucket["last_reset"]

        # Reset bucket if period has passed
        if time_passed >= period:
            bucket["tokens"] = rate
            bucket["last_reset"] = now
            time_passed = 0

        # Calculate tokens to add (for continuous refill)
        tokens_to_add = (time_passed / period) * rate
        bucket["tokens"] = min(bucket["tokens"] + tokens_to_add, rate)

        # Check if we have tokens
        allowed = bucket["tokens"] >= 1
        if allowed:
            bucket["tokens"] -= 1

        # Calculate reset time
        reset_at = bucket["last_reset"] + period
        reset_in = max(0, int(reset_at - now))

        info = {
            "limit": rate,
            "remaining": max(0, int(bucket["tokens"])),
            "reset_at": reset_at,
            "reset_in_seconds": reset_in,
        }

        return allowed, info


class RateLimitMiddleware:
    """ASGI middleware for rate limiting."""

    def __init__(self, app, limiter: Optional[RateLimiter] = None):
        """
        Initialize middleware.

        Args:
            app: ASGI application
            limiter: RateLimiter instance (creates default if not provided)
        """
        self.app = app
        self.limiter = limiter or RateLimiter()

        # Set rate limits for critical endpoints
        self.limiter.set_limit("/api/trades", 100, 60)  # 100 trades/minute
        self.limiter.set_limit("/api/signals", 1000, 60)  # 1000 signal checks/minute
        self.limiter.set_limit("/api/monitoring/dashboard-metrics", 300, 60)  # 300 dashboard/minute
        self.limiter.set_limit("/api/ha/sync-from-primary", 60, 60)  # 60 syncs/minute (HA)

    async def __call__(self, scope, receive, send):
        """ASGI middleware handler."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Get client IP
        client = scope.get("client", ("unknown", 0))
        client_ip = client[0]

        # Get endpoint path
        path = scope.get("path", "/")

        # Check rate limit
        allowed, info = self.limiter.is_allowed(client_ip, path)

        async def send_with_headers(message):
            """Send response with rate limit headers."""
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))

                # Add rate limit headers
                headers.append((b"X-RateLimit-Limit", str(info["limit"]).encode()))
                headers.append((b"X-RateLimit-Remaining", str(info["remaining"]).encode()))
                headers.append((b"X-RateLimit-Reset", str(int(info["reset_at"])).encode()))

                message["headers"] = headers

                if not allowed:
                    # Override status to 429
                    message["status"] = 429
                    headers.append((b"Retry-After", str(info["reset_in_seconds"]).encode()))

            await send(message)

        if not allowed:
            # Rate limit exceeded - return 429
            logger.warning(
                f"Rate limit exceeded for {client_ip} on {path}. "
                f"Reset in {info['reset_in_seconds']}s"
            )

            # Send 429 response
            await send_with_headers({
                "type": "http.response.start",
                "status": 429,
                "headers": [
                    (b"content-type", b"application/json"),
                ],
            })

            import json
            error_body = json.dumps({
                "error": "rate_limit_exceeded",
                "message": f"Too many requests. Limit: {info['limit']} per minute",
                "limit": info["limit"],
                "remaining": 0,
                "reset_at": info["reset_at"],
                "reset_in_seconds": info["reset_in_seconds"],
            }).encode()

            await send({
                "type": "http.response.body",
                "body": error_body,
            })
            return

        # Request allowed - pass to app with rate limit headers
        await self.app(scope, receive, send_with_headers)


# FastAPI integration helper
def add_rate_limiting_to_app(app, limiter: Optional[RateLimiter] = None):
    """
    Add rate limiting to FastAPI application.

    Args:
        app: FastAPI application instance
        limiter: RateLimiter instance (creates default if not provided)
    """
    middleware_instance = RateLimitMiddleware(app, limiter)

    app.add_middleware(lambda app: middleware_instance)

    logger.info("Rate limiting middleware added to application")

    return limiter

