"""HTTP middleware for logging and metrics."""

import logging
import time
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request

logger = logging.getLogger(__name__)


class LogAndMetricsMiddleware(BaseHTTPMiddleware):
    """Log HTTP requests and collect metrics."""

    async def dispatch(self, request: Request, call_next):
        """Process request and log metrics."""
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time

        logger.debug(
            f"{request.method} {request.url.path} - {response.status_code} ({process_time*1000:.0f}ms)"
        )

        response.headers["X-Process-Time"] = str(process_time)
        return response
