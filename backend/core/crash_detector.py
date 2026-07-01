"""Emergency Market Crash Detection and Response for FR-017.

Monitors market conditions and triggers emergency close-all if crash detected.
"""

import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from decimal import Decimal

logger = logging.getLogger(__name__)

_crash_detected = False
_last_crash_check: Optional[datetime] = None
_price_history: Dict[str, List[Dict[str, Any]]] = {}
_crash_threshold_percent = 5.0  # Default: close all if market down >5% in 5 minutes
_state_lock = threading.Lock()  # Protect global state from concurrent access


class CrashDetectionConfig:
    """Configuration for crash detection."""

    def __init__(
        self,
        threshold_percent: float = 5.0,
        lookback_minutes: int = 5,
        min_candles: int = 3
    ):
        """
        Args:
            threshold_percent: Close all if market down >X% (default 5%)
            lookback_minutes: Time window for price movement (default 5 min)
            min_candles: Minimum candles needed before detection (default 3)
        """
        self.threshold_percent = threshold_percent
        self.lookback_minutes = lookback_minutes
        self.min_candles = min_candles


def set_crash_threshold(percent: float) -> None:
    """
    Set crash detection threshold (% drop to trigger close-all).

    Args:
        percent: Percentage drop (e.g., 5.0 for 5%)
    """
    global _crash_threshold_percent
    _crash_threshold_percent = percent
    logger.info(f"🎚️  Crash threshold set to {percent}%")


def get_crash_detection_status() -> Dict[str, Any]:
    """Get current crash detection status."""
    return {
        'crashed': _crash_detected,
        'threshold_percent': _crash_threshold_percent,
        'last_check': _last_crash_check.isoformat() if _last_crash_check else None,
        'tracked_symbols': list(_price_history.keys())
    }


def record_price(symbol: str, price: float, timestamp: Optional[datetime] = None) -> None:
    """
    Record price for crash detection analysis (thread-safe).

    Args:
        symbol: Trading symbol (e.g., 'BTCUSDT')
        price: Current price
        timestamp: When price was recorded (default: now)
    """
    if timestamp is None:
        timestamp = datetime.utcnow()

    with _state_lock:
        if symbol not in _price_history:
            _price_history[symbol] = []

        _price_history[symbol].append({
            'price': float(price),
            'timestamp': timestamp
        })

        # Keep only last 100 candles to avoid memory bloat
        if len(_price_history[symbol]) > 100:
            _price_history[symbol] = _price_history[symbol][-100:]


def detect_crash(config: Optional[CrashDetectionConfig] = None) -> Dict[str, Any]:
    """
    Analyze prices and detect if market crashed (thread-safe).

    Checks all tracked symbols:
    - If ANY symbol down >threshold% in lookback period → crash detected
    - Returns detailed breakdown

    Args:
        config: Detection configuration (uses defaults if None)

    Returns:
        {
            'crash_detected': bool,
            'triggered_at': datetime,
            'symbols_analyzed': [str, ...],
            'largest_drop_symbol': str,
            'largest_drop_percent': float,
            'details': {
                'symbol': {'current_price': float, 'high': float, 'drop_percent': float}
            }
        }
    """
    global _last_crash_check, _crash_detected

    if config is None:
        config = CrashDetectionConfig()

    with _state_lock:
        _last_crash_check = datetime.utcnow()

        if not _price_history:
            return {
                'crash_detected': False,
                'triggered_at': _last_crash_check,
                'symbols_analyzed': [],
                'largest_drop_symbol': None,
                'largest_drop_percent': 0,
                'details': {},
                'error': 'No price history recorded'
            }

        # Analyze each symbol
        crash_detected = False
        largest_drop = 0.0
        largest_drop_symbol = None
        details = {}

        lookback_time = _last_crash_check - timedelta(minutes=config.lookback_minutes)

        for symbol, prices in _price_history.items():
            # Filter prices within lookback window
            recent_prices = [
                p for p in prices
                if p['timestamp'] >= lookback_time
            ]

            if len(recent_prices) < config.min_candles:
                logger.debug(f"⏭️  {symbol}: not enough candles ({len(recent_prices)}/{config.min_candles})")
                continue

            # Find highest price in window and current price
            high_price = max(p['price'] for p in recent_prices)
            current_price = recent_prices[-1]['price']

            # Calculate drop percentage
            if high_price > 0:
                drop_percent = ((high_price - current_price) / high_price) * 100
            else:
                drop_percent = 0

            details[symbol] = {
                'current_price': current_price,
                'high': high_price,
                'drop_percent': round(drop_percent, 2)
            }

            logger.debug(
                f"📊 {symbol}: high=${high_price:.2f}, current=${current_price:.2f}, "
                f"drop={drop_percent:.2f}%"
            )

            # Check if exceeds threshold
            if drop_percent >= config.threshold_percent:
                logger.warning(
                    f"🚨 {symbol} crashed: down {drop_percent:.2f}% (threshold={config.threshold_percent}%)"
                )
                crash_detected = True

            # Track largest drop
            if drop_percent > largest_drop:
                largest_drop = drop_percent
                largest_drop_symbol = symbol

        if crash_detected:
            _crash_detected = True
            logger.critical(
                f"💥 MARKET CRASH DETECTED: {largest_drop_symbol} down {largest_drop:.2f}%"
            )

        return {
            'crash_detected': crash_detected,
            'triggered_at': _last_crash_check,
            'symbols_analyzed': list(_price_history.keys()),
            'largest_drop_symbol': largest_drop_symbol,
            'largest_drop_percent': round(largest_drop, 2),
            'details': details
        }


def reset_crash_detection() -> bool:
    """
    Reset crash detection flag (for testing or after manual recovery, thread-safe).

    **WARNING:** Only call after:
    - Confirming market stabilized
    - All positions properly closed
    - Explicit user confirmation

    Returns:
        True if reset successful
    """
    global _crash_detected

    logger.warning("⚠️  RESETTING CRASH DETECTION - MONITORING WILL RESUME")

    with _state_lock:
        _crash_detected = False

    return True


def clear_price_history() -> None:
    """Clear all recorded price history (useful for testing, thread-safe)."""
    global _price_history

    logger.info("🗑️  Clearing price history")
    with _state_lock:
        _price_history.clear()
