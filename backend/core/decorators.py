"""Reusable decorators for common error handling patterns.

These decorators encapsulate common try/except patterns to reduce boilerplate
and ensure consistent error handling across the codebase.
"""

import asyncio
import functools
import logging
from typing import Any, Callable, Optional, Type, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


def handle_exceptions(
    default_return: Any = None,
    log_level: str = "error",
    reraise: bool = False,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
) -> Callable:
    """Decorator to handle exceptions with consistent logging.

    Args:
        default_return: Value to return if exception occurs (if not reraising)
        log_level: Logging level for the exception ("debug", "info", "warning", "error", "critical")
        reraise: If True, re-raise the exception after logging
        exceptions: Tuple of exception types to catch

    Usage:
        @handle_exceptions(default_return=None, log_level="warning")
        def risky_function():
            ...
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except exceptions as e:
                log_fn = getattr(logger, log_level.lower(), logger.error)
                log_fn(f"Error in {func.__name__}: {e}", exc_info=log_level == "debug")
                if reraise:
                    raise
                return default_return

        return wrapper

    return decorator


def handle_exceptions_async(
    default_return: Any = None,
    log_level: str = "error",
    reraise: bool = False,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
) -> Callable:
    """Async version of handle_exceptions decorator.

    Args:
        default_return: Value to return if exception occurs
        log_level: Logging level for the exception
        reraise: If True, re-raise the exception after logging
        exceptions: Tuple of exception types to catch

    Usage:
        @handle_exceptions_async(default_return=False, log_level="warning")
        async def risky_async_function():
            ...
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except exceptions as e:
                log_fn = getattr(logger, log_level.lower(), logger.error)
                log_fn(f"Error in {func.__name__}: {e}", exc_info=log_level == "debug")
                if reraise:
                    raise
                return default_return

        return wrapper

    return decorator


def retry_on_exception(
    max_retries: int = 3,
    delay_seconds: float = 1.0,
    backoff_multiplier: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
) -> Callable:
    """Decorator to retry function with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        delay_seconds: Initial delay between retries (in seconds)
        backoff_multiplier: Multiply delay by this after each retry
        exceptions: Tuple of exception types that trigger retry

    Usage:
        @retry_on_exception(max_retries=3, delay_seconds=0.5)
        def unstable_network_call():
            ...
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            delay = delay_seconds
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        logger.warning(
                            f"{func.__name__} attempt {attempt + 1}/{max_retries + 1} failed: {e}. "
                            f"Retrying in {delay:.1f}s..."
                        )
                        asyncio.run(asyncio.sleep(delay)) if asyncio.iscoroutinefunction(func) else __import__("time").sleep(delay)
                        delay *= backoff_multiplier
                    else:
                        logger.error(f"{func.__name__} failed after {max_retries + 1} attempts")

            raise last_exception

        return wrapper

    return decorator


def retry_on_exception_async(
    max_retries: int = 3,
    delay_seconds: float = 1.0,
    backoff_multiplier: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
) -> Callable:
    """Async version of retry_on_exception decorator.

    Args:
        max_retries: Maximum number of retry attempts
        delay_seconds: Initial delay between retries (in seconds)
        backoff_multiplier: Multiply delay by this after each retry
        exceptions: Tuple of exception types that trigger retry

    Usage:
        @retry_on_exception_async(max_retries=3, delay_seconds=0.5)
        async def unstable_api_call():
            ...
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            delay = delay_seconds
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        logger.warning(
                            f"{func.__name__} attempt {attempt + 1}/{max_retries + 1} failed: {e}. "
                            f"Retrying in {delay:.1f}s..."
                        )
                        await asyncio.sleep(delay)
                        delay *= backoff_multiplier
                    else:
                        logger.error(f"{func.__name__} failed after {max_retries + 1} attempts")

            raise last_exception

        return wrapper

    return decorator


def log_execution_time(log_level: str = "debug") -> Callable:
    """Decorator to log function execution time.

    Args:
        log_level: Logging level for the execution time message

    Usage:
        @log_execution_time(log_level="info")
        def slow_function():
            ...
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = datetime.utcnow()
            try:
                result = func(*args, **kwargs)
                elapsed = (datetime.utcnow() - start_time).total_seconds()
                log_fn = getattr(logger, log_level.lower(), logger.debug)
                log_fn(f"{func.__name__} completed in {elapsed:.3f}s")
                return result
            except Exception as e:
                elapsed = (datetime.utcnow() - start_time).total_seconds()
                logger.error(f"{func.__name__} failed after {elapsed:.3f}s: {e}")
                raise

        return wrapper

    return decorator


def log_execution_time_async(log_level: str = "debug") -> Callable:
    """Async version of log_execution_time decorator.

    Args:
        log_level: Logging level for the execution time message

    Usage:
        @log_execution_time_async(log_level="info")
        async def slow_async_function():
            ...
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = datetime.utcnow()
            try:
                result = await func(*args, **kwargs)
                elapsed = (datetime.utcnow() - start_time).total_seconds()
                log_fn = getattr(logger, log_level.lower(), logger.debug)
                log_fn(f"{func.__name__} completed in {elapsed:.3f}s")
                return result
            except Exception as e:
                elapsed = (datetime.utcnow() - start_time).total_seconds()
                logger.error(f"{func.__name__} failed after {elapsed:.3f}s: {e}")
                raise

        return wrapper

    return decorator


def validate_inputs(**validators) -> Callable:
    """Decorator to validate function inputs.

    Args:
        **validators: Keyword arguments mapping parameter names to validator functions

    Usage:
        @validate_inputs(
            amount=lambda x: x > 0,
            symbol=lambda x: len(x) == 6
        )
        def place_order(amount, symbol):
            ...
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Validate kwargs
            for param, validator in validators.items():
                if param in kwargs:
                    if not validator(kwargs[param]):
                        raise ValueError(
                            f"Validation failed for parameter '{param}': "
                            f"value={kwargs[param]}, validator={validator.__name__}"
                        )

            return func(*args, **kwargs)

        return wrapper

    return decorator


def validate_inputs_async(**validators) -> Callable:
    """Async version of validate_inputs decorator."""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Validate kwargs
            for param, validator in validators.items():
                if param in kwargs:
                    if not validator(kwargs[param]):
                        raise ValueError(
                            f"Validation failed for parameter '{param}': "
                            f"value={kwargs[param]}, validator={validator.__name__}"
                        )

            return await func(*args, **kwargs)

        return wrapper

    return decorator
