"""Enhanced request logging middleware for debugging, compliance, and observability."""

import time
import logging
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from datetime import datetime, timezone
import uuid

logger = logging.getLogger(__name__)


class EnhancedLoggingMiddleware(BaseHTTPMiddleware):
    """Enhanced HTTP request/response logging with structured output."""

    async def dispatch(self, request: Request, call_next) -> Response:
        """Log request and response with detailed metrics."""
        # Generate request ID for tracing
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        # Capture request details
        start_time = time.time()
        method = request.method
        path = request.url.path
        client_host = request.client.host if request.client else "unknown"

        # Get request body for sensitive endpoint logging
        body = None
        if method in ["POST", "PUT", "PATCH"]:
            try:
                body = await request.body()
                # Replace request body stream so it can be read by the endpoint
                async def receive():
                    return {"type": "http.request", "body": body}
                request._receive = receive
            except Exception as e:
                logger.warning(f"Failed to read request body: {e}")

        # Process request
        try:
            response = await call_next(request)
        except Exception as e:
            # Log exception
            logger.error(
                "Request failed",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "client": client_host,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
                exc_info=True,
            )
            raise

        # Calculate metrics
        duration_ms = (time.time() - start_time) * 1000
        status_code = response.status_code

        # Determine log level based on status code
        if status_code >= 500:
            log_level = logging.ERROR
            severity = "ERROR"
        elif status_code >= 400:
            log_level = logging.WARNING
            severity = "WARNING"
        elif status_code >= 300:
            log_level = logging.INFO
            severity = "INFO"
        else:
            log_level = logging.DEBUG
            severity = "DEBUG"

        # Log structured request/response
        log_msg = f"{method} {path} {status_code}"
        logger.log(
            log_level,
            log_msg,
            extra={
                "request_id": request_id,
                "method": method,
                "path": path,
                "status_code": status_code,
                "duration_ms": round(duration_ms, 2),
                "client": client_host,
                "severity": severity,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

        # Add request ID to response headers for tracing
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = str(round(duration_ms, 2))

        return response
