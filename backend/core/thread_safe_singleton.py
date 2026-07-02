"""Thread-safe singleton pattern for global state (CSF Pillar 4: Safe Delivery)."""

import threading
from typing import Any, Callable, Dict, Optional, TypeVar

T = TypeVar("T")

# Global lock for singleton initialization
_SINGLETON_LOCK = threading.Lock()
_SINGLETONS: Dict[str, Any] = {}


def get_singleton(key: str, factory: Callable[[], T]) -> T:
    """Get or create a thread-safe singleton instance.

    Args:
        key: Unique identifier for this singleton
        factory: Function that creates the instance (called once)

    Returns:
        The singleton instance, created only once across all threads
    """
    # Fast path: check if already exists (avoid lock contention)
    if key in _SINGLETONS:
        return _SINGLETONS[key]

    # Slow path: acquire lock and create
    with _SINGLETON_LOCK:
        # Double-check pattern: another thread may have created it
        if key in _SINGLETONS:
            return _SINGLETONS[key]

        instance = factory()
        _SINGLETONS[key] = instance
        return instance


class ThreadSafeValue:
    """Thread-safe wrapper for a mutable value (e.g., global singleton)."""

    def __init__(self, initial: Optional[T] = None):
        """Initialize with optional initial value."""
        self._value: Optional[T] = initial
        self._lock = threading.Lock()

    def set(self, value: T) -> None:
        """Set the value thread-safely."""
        with self._lock:
            self._value = value

    def get(self) -> Optional[T]:
        """Get the value thread-safely."""
        with self._lock:
            return self._value

    def get_or_create(self, factory: Callable[[], T]) -> T:
        """Get existing value or create new one thread-safely."""
        with self._lock:
            if self._value is None:
                self._value = factory()
            return self._value
