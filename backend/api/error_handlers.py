"""Structured error handling and response formatting for all API endpoints."""

from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


class APIError(Exception):
    """Base class for all API errors with structured responses."""

    def __init__(
        self,
        message: str,
        code: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: dict = None,
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}


class ValidationError(APIError):
    """Raised when input validation fails."""

    def __init__(self, message: str, details: dict = None):
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


class AuthenticationError(APIError):
    """Raised when authentication fails."""

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(
            message=message,
            code="AUTHENTICATION_ERROR",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class AuthorizationError(APIError):
    """Raised when user lacks required permissions."""

    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(
            message=message,
            code="AUTHORIZATION_ERROR",
            status_code=status.HTTP_403_FORBIDDEN,
        )


class NotFoundError(APIError):
    """Raised when requested resource not found."""

    def __init__(self, resource: str = "Resource"):
        super().__init__(
            message=f"{resource} not found",
            code="NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )


class InternalServerError(APIError):
    """Raised for unexpected server errors."""

    def __init__(self, message: str = "Internal server error", details: dict = None):
        super().__init__(
            message=message,
            code="INTERNAL_SERVER_ERROR",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
        )


def format_error_response(
    error: APIError,
    request_id: str = None,
) -> dict:
    """Format error into structured JSON response.

    Args:
        error: APIError instance
        request_id: Unique request identifier for tracing

    Returns:
        Structured error dictionary ready for JSON response
    """
    return {
        "error": {
            "code": error.code,
            "message": error.message,
            "details": error.details,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "request_id": request_id,
        }
    }


async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    """Handle APIError exceptions with structured response."""
    request_id = request.headers.get("X-Request-ID", "unknown")

    logger.warning(
        f"API Error [{exc.code}]: {exc.message}",
        extra={"request_id": request_id, "status_code": exc.status_code},
    )

    return JSONResponse(
        status_code=exc.status_code,
        content=format_error_response(exc, request_id),
    )


async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle Pydantic validation errors with structured response."""
    request_id = request.headers.get("X-Request-ID", "unknown")

    # Extract validation details
    errors = []
    for error in exc.errors():
        errors.append(
            {
                "field": ".".join(str(x) for x in error["loc"][1:]),
                "message": error["msg"],
                "type": error["type"],
            }
        )

    logger.warning(
        f"Validation Error: {len(errors)} validation(s) failed",
        extra={"request_id": request_id, "errors": errors},
    )

    api_error = ValidationError("Request validation failed", {"errors": errors})
    return JSONResponse(
        status_code=api_error.status_code,
        content=format_error_response(api_error, request_id),
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions with structured response."""
    request_id = request.headers.get("X-Request-ID", "unknown")

    # Log full traceback for debugging
    logger.error(
        f"Unhandled Exception: {type(exc).__name__}: {str(exc)}",
        exc_info=True,
        extra={"request_id": request_id},
    )

    # Return generic error to avoid exposing internal details
    api_error = InternalServerError(
        "An unexpected error occurred",
        {"request_id": request_id},
    )

    return JSONResponse(
        status_code=api_error.status_code,
        content=format_error_response(api_error, request_id),
    )
