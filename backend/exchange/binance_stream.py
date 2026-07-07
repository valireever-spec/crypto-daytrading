"""Unified Binance WebSocket stream with integrated health tracking & resilience.

Consolidates:
- Price streaming from WebSocket
- Health tracking & stale detection
- Circuit breaker & reconnection logic
- All in ONE system (no more parallel implementations)
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from datetime import timezone, datetime
from typing import Callable, Dict, Optional
import websockets

logger = logging.getLogger(__name__)

BINANCE_WS_URL = "wss://stream.binance.com:9443/ws"


@dataclass
class StreamHealth:
    """Track health of a single price stream."""
    symbol: str
    last_update: Optional[float] = None
    age_seconds: float = 0.0
    is_healthy: bool = False
    consecutive_failures: int = 0
    last_failure_time: Optional[float] = None

    def update(self) -> None:
        """Update age and health status."""
        if self.last_update is None:
            self.age_seconds = float('inf')
            self.is_healthy = False
        else:
            self.age_seconds = time.time() - self.last_update
            self.is_healthy = self.age_seconds < 5.0

    def mark_failure(self) -> None:
        """Record a stream failure."""
        self.consecutive_failures += 1
        self.last_failure_time = time.time()

    def reset_failures(self) -> None:
        """Reset failure counter on successful reconnection."""
        self.consecutive_failures = 0


class CircuitBreaker:
    """Circuit breaker pattern: Open → Half-Open → Closed"""

    def __init__(self, failure_threshold: int = 3, timeout_seconds: int = 30):
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = "CLOSED"

    def record_failure(self) -> bool:
        """Record a failure, return True if circuit should open."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            logger.critical(
                f"🔴 Circuit breaker OPEN after {self.failure_count} failures"
            )
            return True
        return False

    def check_health(self) -> bool:
        """Check if circuit breaker is closed (healthy)."""
        if self.state == "CLOSED":
            return True

        if self.state == "OPEN":
            if (
                self.last_failure_time
                and time.time() - self.last_failure_time > self.timeout_seconds
            ):
                self.state = "HALF_OPEN"
                self.failure_count = 0
                logger.info("🟡 Circuit breaker HALF_OPEN (attempting recovery)")
                return True
            return False

        return True

    def record_success(self) -> None:
        """Record a successful operation."""
        if self.state == "HALF_OPEN":
            self.state = "CLOSED"
            self.failure_count = 0
            logger.info("🟢 Circuit breaker CLOSED (recovered)")

    def get_state(self) -> str:
        """Get current circuit breaker state."""
        return self.state


class BinanceStreamClient:
    """Unified real-time price stream with integrated health tracking & resilience.

    CONSOLIDATED from:
    - Old BinanceStreamClient (price caching, WebSocket connection)
    - WebSocketResilience (health tracking, circuit breaker, stale detection)
    - WebSocketManager (unused, removed)

    Single source of truth for prices + health.
    """

    def __init__(self, symbols: list = None, max_age_seconds: float = 5.0):
        """Initialize unified stream client.

        Args:
            symbols: Symbols to track (default: BTCUSDT, ETHUSDT, BNBUSDT)
            max_age_seconds: Max acceptable price age in seconds (default: 5)
        """
        self.symbols = symbols or ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
        self.max_age_seconds = max_age_seconds

        # Connection state
        self.websocket = None
        self.is_connected = False
        self.subscriptions: Dict[str, Callable] = {}
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5

        # Price caching (single source of truth)
        self.price_cache: Dict[str, float] = {}
        self.last_update: Dict[str, datetime] = {}
        self.last_message_time: Optional[datetime] = None
        self.message_count = 0
        self.last_check_message_count = 0

        # Health tracking (integrated, not separate)
        self.stream_health: Dict[str, StreamHealth] = {
            symbol: StreamHealth(symbol=symbol) for symbol in self.symbols
        }

        # Circuit breaker
        self.circuit_breaker = CircuitBreaker(failure_threshold=3, timeout_seconds=30)

        # Initialize default timestamps
        now = datetime.now(timezone.utc)
        now_timestamp = time.time()
        for symbol in self.symbols:
            self.last_update[symbol] = now
            self.stream_health[symbol].last_update = now_timestamp

    async def connect(self) -> None:
        """Connect to Binance WebSocket and listen for updates."""
        try:
            logger.info("Connecting to Binance WebSocket...")
            self.websocket = await websockets.connect(BINANCE_WS_URL)
            self.is_connected = True
            self.reconnect_attempts = 0
            logger.info("✓ Connected to Binance WebSocket")
            await self._listen()
        except Exception as e:
            logger.error(f"WebSocket connection failed: {e}")
            self.is_connected = False
            await self._reconnect()

    async def _reconnect(self) -> None:
        """Reconnect with exponential backoff."""
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.error(
                f"Max reconnection attempts ({self.max_reconnect_attempts}) reached"
            )
            return

        wait_time = 2**self.reconnect_attempts  # 1, 2, 4, 8, 16 seconds
        self.reconnect_attempts += 1
        logger.info(
            f"Reconnecting in {wait_time} seconds (attempt {self.reconnect_attempts})"
        )
        await asyncio.sleep(wait_time)
        await self.connect()

    def subscribe(self, stream: str, callback: Callable) -> None:
        """Subscribe to a stream.

        Args:
            stream: Stream name (e.g., 'btcusdt@kline_1m', 'ethusdt@ticker')
            callback: Async callback(symbol, data) when data arrives
        """
        self.subscriptions[stream] = callback
        logger.info(f"Subscribed to {stream}")

    async def _subscribe_streams(self) -> None:
        """Subscribe to all registered streams."""
        if not self.subscriptions:
            return

        stream_names = list(self.subscriptions.keys())
        subscribe_msg = {
            "method": "SUBSCRIBE",
            "params": stream_names,
            "id": 1,
        }

        try:
            await self.websocket.send(json.dumps(subscribe_msg))
            logger.info(f"Subscribed to {len(stream_names)} streams")
        except Exception as e:
            logger.error(f"Failed to subscribe to streams: {e}")

    async def _listen(self) -> None:
        """Listen for messages from WebSocket."""
        await self._subscribe_streams()

        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)

                    # Skip subscription confirmations
                    if "result" in data or "id" in data:
                        continue

                    # Handle TWO message formats from Binance:
                    # 1. Wrapped: {"stream": "btcusdt@kline_1m", "data": {...}}
                    # 2. Unwrapped (default): {"e": "kline", "s": "BTCUSDT", "k": {...}}

                    if "stream" in data:
                        # Format 1: Wrapped (individual stream URLs)
                        stream = data.get("stream")
                        if not stream:
                            continue

                        callback = self.subscriptions.get(stream)
                        if not callback:
                            continue

                        symbol = stream.split("@")[0].upper()
                        payload = data.get("data", {})
                    elif "e" in data and "s" in data:
                        # Format 2: Unwrapped (subscription on single connection)
                        symbol = data.get("s", "").upper()

                        # Find matching stream subscription for this symbol
                        stream = None
                        for sub_stream in self.subscriptions:
                            if sub_stream.lower().startswith(symbol.lower()):
                                stream = sub_stream
                                break

                        if not stream:
                            continue

                        callback = self.subscriptions.get(stream)
                        if not callback:
                            continue

                        payload = data  # Unwrapped data IS the payload
                    else:
                        continue

                    # Update price cache and health tracking (unified)
                    now = datetime.now(timezone.utc)
                    now_timestamp = time.time()
                    if "k" in payload:  # Kline (candle)
                        price = float(payload["k"]["c"])
                        self.price_cache[symbol] = price
                        self.last_update[symbol] = now
                        self.last_message_time = now
                        self.message_count += 1
                        # Update health tracking directly (no external dependency)
                        if symbol in self.stream_health:
                            self.stream_health[symbol].last_update = now_timestamp
                            self.stream_health[symbol].reset_failures()
                        logger.info(f"✓ {symbol}: ${price:.2f} (kline from Binance)")
                    elif "p" in payload:  # Trade price
                        price = float(payload["p"])
                        self.price_cache[symbol] = price
                        self.last_update[symbol] = now
                        self.last_message_time = now
                        self.message_count += 1
                        # Update health tracking directly (no external dependency)
                        if symbol in self.stream_health:
                            self.stream_health[symbol].last_update = now_timestamp
                            self.stream_health[symbol].reset_failures()
                        logger.info(f"✓ {symbol}: ${price:.2f} (trade from Binance)")

                    # Call the callback
                    await callback(symbol, data)

                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON: {e}")
                except Exception as e:
                    logger.error(f"Error processing message: {e}")

        except asyncio.CancelledError:
            logger.info("WebSocket listener cancelled")
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            await self._reconnect()

    async def disconnect(self) -> None:
        """Disconnect from WebSocket."""
        if self.websocket:
            self.is_connected = False
            await self.websocket.close()
            logger.info("Disconnected from Binance WebSocket")

    async def get_connection_status(self) -> Dict:
        """Get current connection status.

        Returns:
            Dict with connected status, subscriptions, cache size, last update time
        """
        latest_update = None
        if self.last_update:
            latest_update = max(self.last_update.values()).isoformat()

        return {
            "connected": self.is_connected,
            "subscriptions": len(self.subscriptions),
            "cached_prices": len(self.price_cache),
            "last_update": latest_update,
            "reconnect_attempts": self.reconnect_attempts,
        }

    def get_price(self, symbol: str) -> Optional[float]:
        """Get last cached price for symbol.

        Args:
            symbol: Symbol in uppercase (e.g., 'BTCUSDT')

        Returns:
            Last known price or None if no data yet
        """
        return self.price_cache.get(symbol)

    def get_prices(self, symbols: list) -> Dict[str, float]:
        """Get cached prices for multiple symbols.

        Args:
            symbols: List of symbols in uppercase

        Returns:
            Dict mapping symbol -> price (only for symbols with cached data)
        """
        return {
            sym: self.price_cache[sym] for sym in symbols if sym in self.price_cache
        }

    def get_prices_fresh(
        self, symbols: list, max_age_seconds: int = 5
    ) -> Dict[str, float]:
        """Get cached prices only if fresh (HARDENING: Data freshness gate G-011).

        Args:
            symbols: List of symbols in uppercase
            max_age_seconds: Max acceptable price age in seconds (default 5)

        Returns:
            Dict mapping symbol -> price (only for fresh data)
            Empty dict if any prices too stale
        """
        if not self.is_connected:
            logger.warning("Price freshness check: WebSocket not connected")
            return {}

        now = datetime.now(timezone.utc)
        fresh_prices = {}
        stale_symbols = []

        for sym in symbols:
            if sym not in self.price_cache:
                continue

            last_update = self.last_update.get(sym)
            if not last_update:
                continue

            age_seconds = (now - last_update).total_seconds()
            if age_seconds < max_age_seconds:
                fresh_prices[sym] = self.price_cache[sym]
            else:
                stale_symbols.append(f"{sym}({age_seconds:.1f}s)")

        if stale_symbols:
            logger.warning(
                f"Stale prices rejected: {', '.join(stale_symbols)} max_age={max_age_seconds}s"
            )

        return fresh_prices

    def get_last_update_time(self) -> Optional[datetime]:
        """Get the most recent price update timestamp across all symbols."""
        if not self.last_update:
            return None
        return max(self.last_update.values()) if self.last_update else None

    def get_price_age_seconds(self, symbol: str) -> Optional[float]:
        """Get age in seconds of the most recent price for a symbol."""
        if symbol not in self.last_update:
            return None
        age = (datetime.now(timezone.utc) - self.last_update[symbol]).total_seconds()
        return age

    def check_data_freshness(self, symbols: list, max_age_seconds: float = 5.0) -> dict:
        """Check freshness of each symbol independently (ACCURATE detection).

        Args:
            symbols: List of symbols to check
            max_age_seconds: Max acceptable age (default 5 seconds, not 120!)

        Returns:
            {
                'fresh': [list of fresh symbols],
                'stale': [(symbol, age_seconds), ...],  # Symbols older than threshold
                'missing': [symbols with no data],
                'is_healthy': bool  # True if ALL symbols fresh
            }
        """
        fresh = []
        stale = []
        missing = []
        now = datetime.now(timezone.utc)

        for symbol in symbols:
            if symbol not in self.last_update:
                missing.append(symbol)
            else:
                age = (now - self.last_update[symbol]).total_seconds()
                if age < max_age_seconds:
                    fresh.append(symbol)
                else:
                    stale.append((symbol, age))

        is_healthy = len(stale) == 0 and len(missing) == 0

        return {
            'fresh': fresh,
            'stale': stale,
            'missing': missing,
            'is_healthy': is_healthy,
            'check_time': now.isoformat(),
        }

    def is_data_flowing(self) -> bool:
        """Check if data is actively flowing (messages arriving).

        Returns True only if:
        1. Messages are being received
        2. Message count is increasing (not stuck)
        """
        if not self.is_connected or not self.last_message_time:
            return False

        now = datetime.now(timezone.utc)
        time_since_message = (now - self.last_message_time).total_seconds()

        # Data is flowing if last message <3 seconds ago
        return time_since_message < 3.0

    # ========== HEALTH TRACKING (consolidated from WebSocketResilience) ==========

    def get_stream_health(self) -> Dict[str, Dict]:
        """Get health status of all streams."""
        for stream in self.stream_health.values():
            stream.update()

        return {
            symbol: {
                "symbol": stream.symbol,
                "age_seconds": round(stream.age_seconds, 2),
                "is_healthy": stream.is_healthy,
                "consecutive_failures": stream.consecutive_failures,
            }
            for symbol, stream in self.stream_health.items()
        }

    def get_stale_streams(self) -> list:
        """Get list of streams that are stale (age > max_age)."""
        stale = []
        for symbol, stream in self.stream_health.items():
            stream.update()
            if stream.age_seconds > self.max_age_seconds:
                stale.append(
                    {
                        "symbol": symbol,
                        "age_seconds": round(stream.age_seconds, 2),
                    }
                )
        return stale

    def check_health(self) -> Dict:
        """Check overall WebSocket health.

        Returns dict with:
        - overall_healthy: True if all streams fresh
        - healthy_streams: Count of healthy streams
        - total_streams: Total streams monitored
        - stale_streams: List of stale streams
        - circuit_breaker: Current CB state
        """
        stale = self.get_stale_streams()
        healthy_count = len(self.symbols) - len(stale)

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "overall_healthy": len(stale) == 0,
            "healthy_streams": healthy_count,
            "total_streams": len(self.symbols),
            "stale_streams": stale,
            "circuit_breaker": self.circuit_breaker.get_state(),
        }


# Global stream client instance (single source of truth)
_stream_client: Optional[BinanceStreamClient] = None


async def init_stream_client(
    symbols: list = None, max_age_seconds: float = 5.0
) -> BinanceStreamClient:
    """Initialize global stream client.

    Args:
        symbols: Symbols to track (default: BTCUSDT, ETHUSDT, BNBUSDT)
        max_age_seconds: Max acceptable price age (default: 5 seconds)
    """
    global _stream_client
    _stream_client = BinanceStreamClient(symbols=symbols, max_age_seconds=max_age_seconds)
    return _stream_client


def get_stream_client() -> Optional[BinanceStreamClient]:
    """Get global stream client (single source of truth for prices + health)."""
    return _stream_client
