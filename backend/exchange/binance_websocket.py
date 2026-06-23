"""Binance WebSocket client for real-time price data (FR-002)."""

import asyncio
import json
import logging
from typing import Callable, Dict, List, Optional
from datetime import datetime

import websockets

logger = logging.getLogger(__name__)


class BinanceWebSocketClient:
    """Subscribe to Binance WebSocket streams for real-time prices."""

    BASE_URL = "wss://stream.binance.com:9443"
    TESTNET_URL = "wss://stream.testnet.binance.vision:9443"

    def __init__(self, testnet: bool = True):
        """Initialize WebSocket client.

        Args:
            testnet: Use Binance testnet or mainnet
        """
        self.base_url = self.TESTNET_URL if testnet else self.BASE_URL
        self.websocket = None
        self.subscribed_streams: List[str] = []
        self.callbacks: Dict[str, Callable] = {}
        self.running = False
        self.last_price_update: Optional[datetime] = None

    def subscribe(self, stream: str, callback: Callable) -> None:
        """Subscribe to a WebSocket stream.

        Args:
            stream: Stream name (e.g., "btcusdt@kline_1m", "btcusdt@trade")
            callback: Function to call when data arrives
                     Signature: callback(symbol: str, data: dict)
        """
        if stream not in self.subscribed_streams:
            self.subscribed_streams.append(stream)
            self.callbacks[stream] = callback
            logger.info(f"Subscribed to {stream}")

    def unsubscribe(self, stream: str) -> None:
        """Unsubscribe from a stream."""
        if stream in self.subscribed_streams:
            self.subscribed_streams.remove(stream)
            del self.callbacks[stream]
            logger.info(f"Unsubscribed from {stream}")

    async def connect(self) -> None:
        """Connect to Binance WebSocket and start listening."""
        if not self.subscribed_streams:
            logger.warning("No streams subscribed before connect()")
            return

        try:
            # Build URL with multiple streams
            streams_str = "/".join(self.subscribed_streams)
            url = f"{self.base_url}/stream?streams={streams_str}"

            logger.info(f"Connecting to {url}")
            self.websocket = await websockets.connect(url)
            self.running = True

            logger.info("Connected to Binance WebSocket")
            await self._listen()

        except Exception as e:
            logger.error(f"WebSocket connection failed: {e}")
            self.running = False
            # Attempt reconnect after delay
            await asyncio.sleep(5)
            await self.connect()

    async def _listen(self) -> None:
        """Listen for messages on WebSocket."""
        try:
            async for message in self.websocket:
                await self._handle_message(message)
        except Exception as e:
            logger.error(f"WebSocket listen error: {e}")
            self.running = False

    async def _handle_message(self, message: str) -> None:
        """Handle incoming WebSocket message.

        Args:
            message: JSON string from Binance
        """
        try:
            data = json.loads(message)
            self.last_price_update = datetime.utcnow()

            # Extract stream name
            stream = data.get("stream")
            if not stream:
                logger.warning(f"No stream in message: {data}")
                return

            # Get callback for this stream
            callback = self.callbacks.get(stream)
            if not callback:
                logger.debug(f"No callback for stream: {stream}")
                return

            # Extract symbol (e.g., "btcusdt" from "btcusdt@kline_1m")
            symbol = stream.split("@")[0].upper()

            # Call callback with parsed data
            await callback(symbol, data.get("data", data))

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse WebSocket message: {e}")
        except Exception as e:
            logger.error(f"Error handling message: {e}")

    async def disconnect(self) -> None:
        """Disconnect from WebSocket."""
        self.running = False
        if self.websocket:
            await self.websocket.close()
            logger.info("Disconnected from Binance WebSocket")

    async def get_connection_status(self) -> Dict:
        """Get current connection status."""
        return {
            "connected": self.running,
            "subscribed_streams": len(self.subscribed_streams),
            "streams": self.subscribed_streams,
            "last_price_update": (
                self.last_price_update.isoformat()
                if self.last_price_update
                else None
            ),
        }


# Global WebSocket client instance
_ws_client: Optional[BinanceWebSocketClient] = None


async def init_websocket(testnet: bool = True) -> BinanceWebSocketClient:
    """Initialize global WebSocket client."""
    global _ws_client
    _ws_client = BinanceWebSocketClient(testnet=testnet)
    return _ws_client


def get_websocket() -> Optional[BinanceWebSocketClient]:
    """Get global WebSocket client."""
    return _ws_client
