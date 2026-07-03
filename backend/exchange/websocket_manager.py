"""Robust WebSocket Manager with Automatic Recovery & Fallback

Implements:
- Automatic reconnection with exponential backoff + jitter
- Health monitoring (ping/pong, stale detection)
- REST API fallback when WebSocket fails
- Graceful degradation (don't halt, recover)
- Proper state management (disconnected → connecting → connected)
"""

import asyncio
import json
import logging
import time
import random
from datetime import datetime, timedelta
from typing import Optional, Dict, Callable, List
from dataclasses import dataclass

import websockets
import aiohttp

logger = logging.getLogger(__name__)


@dataclass
class PriceUpdate:
    """A single price update from WebSocket or REST."""
    symbol: str
    price: float
    timestamp: datetime
    source: str  # "websocket" or "rest"
    age_seconds: float = 0.0

    def update_age(self):
        self.age_seconds = (datetime.utcnow() - self.timestamp).total_seconds()


class WebSocketManager:
    """Manage WebSocket connection with automatic recovery and REST fallback."""

    BINANCE_WS = "wss://stream.testnet.binance.vision:9443/ws"
    BINANCE_REST = "https://testnet.binance.vision/api/v3"

    def __init__(self, symbols: List[str] = None, max_reconnect_attempts: int = 10):
        self.symbols = symbols or ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
        self.max_reconnect_attempts = max_reconnect_attempts

        # Connection state
        self.ws = None
        self.connected = False
        self.reconnect_attempts = 0
        self.last_reconnect_time = None

        # Price caching
        self.prices: Dict[str, PriceUpdate] = {}
        self.price_callbacks: List[Callable] = []

        # Health tracking
        self.last_ws_message = None
        self.last_rest_update = None
        self.ws_failures = 0
        self.rest_failures = 0

        # Monitoring
        self.monitoring = False
        self.monitor_task = None

    async def start(self) -> bool:
        """Start WebSocket connection with fallback to REST."""
        logger.info("🚀 Starting WebSocket manager...")

        # Start monitoring in background
        if not self.monitoring:
            self.monitoring = True
            self.monitor_task = asyncio.create_task(self._monitor_loop())

        # Try WebSocket first
        if await self._connect_websocket():
            return True

        # Fallback to REST polling
        logger.warning("⚠️  WebSocket failed, falling back to REST polling...")
        asyncio.create_task(self._rest_polling_loop())
        return True

    async def stop(self) -> None:
        """Stop WebSocket manager."""
        logger.info("⛔ Stopping WebSocket manager...")
        self.monitoring = False

        if self.ws:
            await self.ws.close()
            self.connected = False

        if self.monitor_task:
            self.monitor_task.cancel()

    async def reconnect(self, symbol: str) -> None:
        """Reconnect WebSocket for a specific symbol (called by staleness monitor)."""
        logger.info(f"🔄 Reconnect triggered by staleness monitor for {symbol}")
        # Trigger full WebSocket reconnection
        self.connected = False
        if self.ws:
            try:
                await self.ws.close()
            except:
                pass
        self.reconnect_attempts = 0
        await self._connect_websocket()

    async def _connect_websocket(self) -> bool:
        """Connect to Binance WebSocket with exponential backoff."""
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.error(
                f"❌ Max reconnection attempts ({self.max_reconnect_attempts}) reached"
            )
            return False

        # Exponential backoff with jitter: 1s, 2s, 4s, 8s, 16s... (max 60s)
        backoff = min(2 ** self.reconnect_attempts, 60)
        jitter = random.uniform(0, 0.1 * backoff)
        wait_time = backoff + jitter

        if self.reconnect_attempts > 0:
            logger.info(
                f"⏳ Reconnecting in {wait_time:.1f}s "
                f"(attempt {self.reconnect_attempts}/{self.max_reconnect_attempts})"
            )
            await asyncio.sleep(wait_time)

        try:
            logger.info(f"🔗 Connecting to Binance WebSocket...")
            self.ws = await websockets.connect(self.BINANCE_WS, ping_interval=20)
            self.connected = True
            self.reconnect_attempts = 0
            self.last_reconnect_time = datetime.utcnow()

            logger.info("✅ WebSocket connected!")

            # Subscribe to streams
            await self._subscribe_streams()

            # Start listening in background (don't await - it's an infinite loop)
            asyncio.create_task(self._ws_listen())

            return True

        except Exception as e:
            logger.error(f"❌ WebSocket connection failed: {e}")
            self.connected = False
            self.reconnect_attempts += 1
            self.ws_failures += 1

            # Retry recursively
            return await self._connect_websocket()

    async def _subscribe_streams(self) -> None:
        """Subscribe to @trade streams for all symbols."""
        if not self.ws:
            return

        streams = [f"{sym.lower()}@trade" for sym in self.symbols]

        subscribe_msg = {
            "method": "SUBSCRIBE",
            "params": streams,
            "id": 1,
        }

        try:
            await self.ws.send(json.dumps(subscribe_msg))
            logger.info(f"✅ Subscribed to {len(streams)} streams")
        except Exception as e:
            logger.error(f"❌ Failed to subscribe: {e}")
            self.connected = False

    async def _ws_listen(self) -> None:
        """Listen to WebSocket messages."""
        if not self.ws:
            return

        try:
            async for message in self.ws:
                try:
                    data = json.loads(message)

                    # Skip non-price messages
                    if "stream" not in data or "data" not in data:
                        continue

                    stream_name = data["stream"]
                    payload = data["data"]

                    # Extract symbol and price
                    symbol = stream_name.split("@")[0].upper()
                    price = float(payload.get("p"))

                    # Update cache
                    self.prices[symbol] = PriceUpdate(
                        symbol=symbol,
                        price=price,
                        timestamp=datetime.utcfromtimestamp(payload.get("T", 0) / 1000),
                        source="websocket",
                    )
                    self.last_ws_message = datetime.utcnow()

                    # Call callbacks
                    await self._call_callbacks(symbol, price)

                except (json.JSONDecodeError, KeyError, ValueError) as e:
                    logger.debug(f"Invalid message: {e}")
                    continue

        except asyncio.CancelledError:
            logger.info("WebSocket listen cancelled")
        except Exception as e:
            logger.error(f"❌ WebSocket error: {e}")
            self.connected = False
            await self._connect_websocket()

    async def _rest_polling_loop(self) -> None:
        """Fallback: Poll REST API for prices."""
        logger.info("🔄 Starting REST API polling loop...")

        while self.monitoring:
            try:
                async with aiohttp.ClientSession() as session:
                    for symbol in self.symbols:
                        try:
                            price = await self._fetch_price_rest(session, symbol)

                            if price:
                                self.prices[symbol] = PriceUpdate(
                                    symbol=symbol,
                                    price=price,
                                    timestamp=datetime.utcnow(),
                                    source="rest",
                                )
                                self.last_rest_update = datetime.utcnow()
                                await self._call_callbacks(symbol, price)

                        except Exception as e:
                            logger.debug(f"Failed to fetch {symbol}: {e}")
                            self.rest_failures += 1

                # Poll every 1 second (slower than WebSocket but better than nothing)
                await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"REST polling error: {e}")
                await asyncio.sleep(5)

    async def _fetch_price_rest(self, session: aiohttp.ClientSession, symbol: str) -> Optional[float]:
        """Fetch price from Binance REST API."""
        try:
            url = f"{self.BINANCE_REST}/ticker/price?symbol={symbol}"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return float(data["price"])
        except Exception as e:
            logger.debug(f"REST API error for {symbol}: {e}")

        return None

    async def _monitor_loop(self) -> None:
        """Monitor WebSocket connection health (passive monitoring only).

        NOTE: Staleness detection and reconnection is delegated to
        websocket_staleness_monitor.py (Skill #1) to avoid conflicts.

        This loop only logs health status without triggering reconnects.
        """
        while self.monitoring:
            try:
                # Check every 1 second
                await asyncio.sleep(1)

                # Update age for all prices (passive monitoring only)
                for price in self.prices.values():
                    price.update_age()

                # Passive monitoring: Just log, don't reconnect
                stale_5s = sum(1 for p in self.prices.values() if p.age_seconds > 5)
                total = len(self.symbols)

                if stale_5s > 0 and total > 0:
                    ages = {s: self.prices[s].age_seconds for s in self.symbols if s in self.prices}
                    logger.debug(
                        f"Price staleness detected: {stale_5s}/{total} stale >5s {ages} "
                        f"(WebSocket: {self.connected}) - staleness monitor will handle reconnection"
                    )

            except asyncio.CancelledError:
                logger.info("WebSocket monitor cancelled")
                break
            except Exception as e:
                logger.error(f"Monitoring error: {e}")

    async def _call_callbacks(self, symbol: str, price: float) -> None:
        """Call all registered callbacks."""
        for callback in self.price_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(symbol, price)
                else:
                    callback(symbol, price)
            except Exception as e:
                logger.error(f"Callback error: {e}")

    def register_callback(self, callback: Callable) -> None:
        """Register a callback for price updates."""
        self.price_callbacks.append(callback)

    def get_price(self, symbol: str, max_age_seconds: int = 10) -> Optional[float]:
        """Get current price (from cache)."""
        if symbol not in self.prices:
            return None

        price = self.prices[symbol]
        price.update_age()

        if price.age_seconds > max_age_seconds:
            logger.debug(f"{symbol} price stale: {price.age_seconds:.1f}s > {max_age_seconds}s")
            return None

        return price.price

    def get_prices(self, symbols: List[str], max_age_seconds: int = 10) -> Dict[str, float]:
        """Get multiple prices."""
        result = {}
        for symbol in symbols:
            price = self.get_price(symbol, max_age_seconds)
            if price:
                result[symbol] = price
        return result

    def get_health(self) -> Dict:
        """Get WebSocket manager health status."""
        for price in self.prices.values():
            price.update_age()

        return {
            "websocket": {
                "connected": self.connected,
                "reconnect_attempts": self.reconnect_attempts,
                "failures": self.ws_failures,
                "last_message": self.last_ws_message.isoformat() if self.last_ws_message else None,
            },
            "rest": {
                "active": self.last_rest_update is not None,
                "failures": self.rest_failures,
                "last_update": self.last_rest_update.isoformat() if self.last_rest_update else None,
            },
            "prices": {
                symbol: {
                    "price": price.price,
                    "age_seconds": price.age_seconds,
                    "source": price.source,
                }
                for symbol, price in self.prices.items()
            },
        }


# Global instance
_manager: Optional[WebSocketManager] = None


def get_manager() -> WebSocketManager:
    """Get or create global WebSocket manager."""
    global _manager
    if _manager is None:
        _manager = WebSocketManager()
    return _manager


async def init_manager(symbols: List[str] = None) -> WebSocketManager:
    """Initialize global WebSocket manager."""
    global _manager
    _manager = WebSocketManager(symbols=symbols)
    await _manager.start()
    return _manager
