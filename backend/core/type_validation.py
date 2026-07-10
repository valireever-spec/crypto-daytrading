"""
Type Validation & Error Prevention

Prevents UnboundLocalError and TypeError issues by:
1. Validating types at function entry
2. Explicit None-checks before operations
3. Clear error messages for type mismatches
"""

import logging
from typing import Any, Optional, Type, Union, Callable
from functools import wraps
from datetime import datetime

logger = logging.getLogger(__name__)


def validate_not_none(value: Any, name: str, context: str = "") -> Any:
    """
    Validate value is not None.

    Args:
        value: Value to check
        name: Variable name (for error messages)
        context: Context (for error messages)

    Returns:
        value if not None

    Raises:
        ValueError: If value is None
    """
    if value is None:
        msg = f"🔴 {name} is None"
        if context:
            msg += f" in {context}"
        raise ValueError(msg)
    return value


def validate_type(value: Any, expected_type: Type, name: str, context: str = "") -> Any:
    """
    Validate value matches expected type.

    Args:
        value: Value to check
        expected_type: Expected type (or tuple of types)
        name: Variable name (for error messages)
        context: Context (for error messages)

    Returns:
        value if type matches

    Raises:
        TypeError: If type doesn't match
    """
    if not isinstance(value, expected_type):
        msg = f"🔴 {name} type mismatch: expected {expected_type}, got {type(value).__name__}"
        if context:
            msg += f" in {context}"
        logger.error(msg)
        raise TypeError(msg)
    return value


def validate_datetime(value: Any, name: str, context: str = "") -> datetime:
    """
    Validate and convert to datetime.

    Args:
        value: Value to check
        name: Variable name
        context: Context

    Returns:
        datetime object

    Raises:
        TypeError: If value cannot be converted to datetime
    """
    if value is None:
        raise ValueError(f"{name} cannot be None in {context}")

    if isinstance(value, datetime):
        return value

    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value)
            if dt.tzinfo is None:
                from datetime import timezone
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError as e:
            raise TypeError(
                f"🔴 {name} is not valid ISO format: '{value}' in {context}"
            )

    raise TypeError(
        f"🔴 {name} cannot be converted to datetime: {type(value).__name__} in {context}"
    )


def validate_number(value: Any, name: str, context: str = "", positive: bool = False) -> float:
    """
    Validate and convert to number.

    Args:
        value: Value to check
        name: Variable name
        context: Context
        positive: If True, number must be > 0

    Returns:
        float

    Raises:
        TypeError: If value is not a number
    """
    if value is None:
        raise ValueError(f"{name} cannot be None in {context}")

    if isinstance(value, (int, float)):
        num = float(value)
    else:
        raise TypeError(
            f"🔴 {name} is not a number: {type(value).__name__} in {context}"
        )

    if positive and num <= 0:
        raise ValueError(f"🔴 {name} must be positive, got {num} in {context}")

    return num


class TypeSafeDict(dict):
    """Dict wrapper with type validation on access"""

    def get_string(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get value as string, with validation"""
        value = self.get(key, default)
        if value is not None and not isinstance(value, str):
            logger.warning(f"Type mismatch for {key}: expected str, got {type(value).__name__}")
        return value

    def get_float(self, key: str, default: Optional[float] = None) -> Optional[float]:
        """Get value as float, with validation"""
        value = self.get(key, default)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                logger.warning(f"Cannot convert {key} to float: {value}")
                return default
        return value

    def get_int(self, key: str, default: Optional[int] = None) -> Optional[int]:
        """Get value as int, with validation"""
        value = self.get(key, default)
        if value is not None:
            try:
                return int(value)
            except (TypeError, ValueError):
                logger.warning(f"Cannot convert {key} to int: {value}")
                return default
        return value

    def get_list(self, key: str, default: Optional[list] = None) -> Optional[list]:
        """Get value as list, with validation"""
        value = self.get(key, default)
        if value is not None and not isinstance(value, list):
            logger.warning(f"Type mismatch for {key}: expected list, got {type(value).__name__}")
        return value if isinstance(value, list) else default


def type_safe(func: Callable) -> Callable:
    """Decorator for type-safe function execution with error handling"""

    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except (TypeError, ValueError) as e:
            logger.error(f"Type error in {func.__name__}: {e}")
            raise

    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (TypeError, ValueError) as e:
            logger.error(f"Type error in {func.__name__}: {e}")
            raise

    # Return appropriate wrapper
    import asyncio
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper


# Common validation patterns for exit.py


def validate_position(position: dict, context: str = "exit check") -> dict:
    """Validate position has all required fields"""
    required_fields = ["symbol", "entry_price", "quantity", "entry_time"]
    missing = [f for f in required_fields if f not in position]
    if missing:
        raise ValueError(f"Position missing fields in {context}: {missing}")
    return TypeSafeDict(position)


def validate_exit_parameters(
    symbol: str,
    entry_price: float,
    current_price: float,
    hold_time: float,
    exit_reason: Optional[str],
) -> dict:
    """Validate all exit parameters before execution"""
    return {
        "symbol": validate_type(symbol, str, "symbol"),
        "entry_price": validate_number(entry_price, "entry_price", positive=True),
        "current_price": validate_number(current_price, "current_price", positive=True),
        "hold_time": validate_number(hold_time, "hold_time"),
        "exit_reason": exit_reason if exit_reason is None or isinstance(exit_reason, str) else None,
    }
