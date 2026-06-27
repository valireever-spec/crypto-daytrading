"""Rate Limiting: Respect Binance 1200 req/min limit"""

import logging
import time
from typing import Dict, Optional
from collections import deque

logger = logging.getLogger(__name__)


class RateLimiter:
    """Track and enforce rate limits."""

    def __init__(self, max_requests: int = 1200, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.request_times: deque = deque()

    def can_request(self) -> bool:
        """Check if request is allowed."""
        now = time.time()

        # Remove old requests outside window
        while self.request_times and self.request_times[0] < now - self.window_seconds:
            self.request_times.popleft()

        # Check limit
        if len(self.request_times) >= self.max_requests:
            oldest = self.request_times[0]
            wait_time = self.window_seconds - (now - oldest)
            logger.warning(f"⚠️  Rate limit reached, wait {wait_time:.1f}s")
            return False

        self.request_times.append(now)
        return True

    def record_request(self) -> None:
        """Record a request (called after successful execution)."""
        self.request_times.append(time.time())

    def get_usage(self) -> Dict:
        """Get current rate limit usage."""
        now = time.time()

        # Remove old requests
        while self.request_times and self.request_times[0] < now - self.window_seconds:
            self.request_times.popleft()

        return {
            "requests_used": len(self.request_times),
            "requests_limit": self.max_requests,
            "percent_used": (len(self.request_times) / self.max_requests * 100),
        }


# Global instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter
