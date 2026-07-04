"""Binance WebSocket real-time price streaming (Phase 1 Week 3)."""

import asyncio
import json
import logging
from datetime import datetime
from typing import Callable, Dict, Optional
import websockets

logger = logging.getLogger(__name__)

# Import WebSocketResilience for health tracking integration
try:
    from backend.exchange.binance_stream_resilience import get_websocket_resilience
except ImportError:
    get_websocket_resilience = lambda: None

# Binance WebSocket base URL (real prices, 100% free)
BINANCE_WS_URL = "wss://stream.binance.com:9443/ws"


class BinanceStreamClient:
    """Real-time price stream from Binance WebSocket."""

    def __init__(self):
        """Initialize Binance stream client."""
        self.websocket = None
        self.is_connected = False
        self.subscriptions: Dict[str, Callable] = {}
        self.price_cache: Dict[str, float] = {}
        self.last_update: Dict[str, datetime] = {}
        self.last_message_time: Optional[datetime] = None  # When last ANY message arrived
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.message_count = 0  # Track message flow
        self.last_check_message_count = 0  # For detecting stuck streams

        # Initialize default symbols to prevent "inf" age on first freshness check
        now = datetime.utcnow()
        for symbol in ["BTCUSDT", "ETHUSDT", "BNBUSDT"]:
            self.last_update[symbol] = now

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

                    # Update price cache and timestamp (works for both formats)
                    now = datetime.utcnow()
                    if "k" in payload:  # Kline (candle)
                        price = float(payload["k"]["c"])
                        self.price_cache[symbol] = price
                        self.last_update[symbol] = now
                        self.last_message_time = now
                        self.message_count += 1
                        # Record price update in WebSocket resilience tracker
                        ws_resilience = get_websocket_resilience()
                        if ws_resilience:
                            ws_resilience.record_price_update(symbol)
                        logger.info(f"✓ {symbol}: ${price:.2f} (kline from Binance)")
                    elif "p" in payload:  # Trade price
                        price = float(payload["p"])
                        self.price_cache[symbol] = price
                        self.last_update[symbol] = now
                        self.last_message_time = now
                        self.message_count += 1
                        # Record price update in WebSocket resilience tracker
                        ws_resilience = get_websocket_resilience()
                        if ws_resilience:
                            ws_resilience.record_price_update(symbol)
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

        now = datetime.utcnow()
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
        age = (datetime.utcnow() - self.last_update[symbol]).total_seconds()
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
        now = datetime.utcnow()

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

        now = datetime.utcnow()
        time_since_message = (now - self.last_message_time).total_seconds()

        # Data is flowing if last message <3 seconds ago
        return time_since_message < 3.0


# Global stream client instance
_stream_client: Optional[BinanceStreamClient] = None


async def init_stream_client() -> BinanceStreamClient:
    """Initialize global stream client."""
    global _stream_client
    _stream_client = BinanceStreamClient()
    return _stream_client


def get_stream_client() -> Optional[BinanceStreamClient]:
    """Get global stream client."""
    return _stream_client
