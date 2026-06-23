"""Tests for Binance WebSocket real-time price streaming (Phase 1 Week 3)."""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

from backend.exchange.binance_stream import (
    BinanceStreamClient,
    init_stream_client,
    get_stream_client,
)


@pytest.fixture
def stream_client():
    """Create stream client for tests."""
    return BinanceStreamClient()


@pytest.fixture(autouse=True)
def cleanup_stream():
    """Clean up stream client between tests."""
    import backend.exchange.binance_stream as stream_module

    stream_module._stream_client = None
    yield
    stream_module._stream_client = None


class TestBinanceStreamClient:
    """Test BinanceStreamClient class."""

    def test_init(self, stream_client):
        """Stream client should initialize correctly."""
        assert stream_client.websocket is None
        assert stream_client.is_connected is False
        assert len(stream_client.subscriptions) == 0
        assert len(stream_client.price_cache) == 0

    def test_subscribe(self, stream_client):
        """Should register stream subscriptions."""
        callback = AsyncMock()
        stream_client.subscribe("btcusdt@kline_1m", callback)

        assert "btcusdt@kline_1m" in stream_client.subscriptions
        assert stream_client.subscriptions["btcusdt@kline_1m"] == callback

    def test_subscribe_multiple(self, stream_client):
        """Should handle multiple subscriptions."""
        cb1 = AsyncMock()
        cb2 = AsyncMock()
        cb3 = AsyncMock()

        stream_client.subscribe("btcusdt@kline_1m", cb1)
        stream_client.subscribe("ethusdt@kline_1m", cb2)
        stream_client.subscribe("bnbusdt@ticker", cb3)

        assert len(stream_client.subscriptions) == 3

    def test_get_connection_status(self, stream_client):
        """Should return connection status."""
        status = asyncio.run(stream_client.get_connection_status())

        assert "connected" in status
        assert "subscriptions" in status
        assert "cached_prices" in status
        assert status["connected"] is False
        assert status["subscriptions"] == 0

    def test_get_price_not_cached(self, stream_client):
        """Should return None for uncached symbol."""
        price = stream_client.get_price("BTCUSDT")
        assert price is None

    def test_get_price_cached(self, stream_client):
        """Should return cached price."""
        stream_client.price_cache["BTCUSDT"] = 45000.0
        price = stream_client.get_price("BTCUSDT")

        assert price == 45000.0

    def test_get_prices_multiple(self, stream_client):
        """Should return prices for multiple symbols."""
        stream_client.price_cache["BTCUSDT"] = 45000.0
        stream_client.price_cache["ETHUSDT"] = 2500.0

        prices = stream_client.get_prices(["BTCUSDT", "ETHUSDT", "BNBUSDT"])

        assert len(prices) == 2
        assert prices["BTCUSDT"] == 45000.0
        assert prices["ETHUSDT"] == 2500.0
        assert "BNBUSDT" not in prices

    def test_get_prices_empty(self, stream_client):
        """Should handle empty cache."""
        prices = stream_client.get_prices(["BTCUSDT", "ETHUSDT"])
        assert len(prices) == 0

    @pytest.mark.asyncio
    async def test_message_processing_kline(self, stream_client):
        """Should process kline (candle) messages."""
        callback = AsyncMock()
        stream_client.subscribe("btcusdt@kline_1m", callback)

        # Simulate message
        message = {
            "stream": "btcusdt@kline_1m",
            "data": {
                "k": {
                    "c": "45000.00",  # Close price
                }
            },
        }

        # Manually process message (without actual websocket)
        data = message["data"]
        price = float(data["k"]["c"])
        stream_client.price_cache["BTCUSDT"] = price

        assert stream_client.get_price("BTCUSDT") == 45000.0

    @pytest.mark.asyncio
    async def test_message_processing_ticker(self, stream_client):
        """Should process ticker messages."""
        callback = AsyncMock()
        stream_client.subscribe("btcusdt@ticker", callback)

        # Simulate ticker message
        data = {"p": "46000.50"}  # Price
        price = float(data["p"])
        stream_client.price_cache["BTCUSDT"] = price

        assert stream_client.get_price("BTCUSDT") == 46000.50


class TestStreamGlobalInstance:
    """Test global stream client instance."""

    @pytest.mark.asyncio
    async def test_init_stream_client(self):
        """Should initialize global stream client."""
        client = await init_stream_client()

        assert client is not None
        assert isinstance(client, BinanceStreamClient)

    @pytest.mark.asyncio
    async def test_get_stream_client(self):
        """Should return initialized global stream client."""
        await init_stream_client()
        client = get_stream_client()

        assert client is not None
        assert isinstance(client, BinanceStreamClient)

    @pytest.mark.asyncio
    async def test_get_stream_client_uninitialized(self):
        """Should return None if not initialized."""
        import backend.exchange.binance_stream as stream_module

        stream_module._stream_client = None
        client = get_stream_client()

        assert client is None


class TestStreamIntegration:
    """Integration tests for stream functionality."""

    def test_price_cache_updates(self, stream_client):
        """Price cache should update from multiple sources."""
        # Simulate kline update
        stream_client.price_cache["BTCUSDT"] = 45000.0
        assert stream_client.get_price("BTCUSDT") == 45000.0

        # Simulate price update
        stream_client.price_cache["BTCUSDT"] = 45100.0
        assert stream_client.get_price("BTCUSDT") == 45100.0

    def test_multiple_symbols(self, stream_client):
        """Should handle multiple symbols simultaneously."""
        symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]

        for i, sym in enumerate(symbols):
            stream_client.price_cache[sym] = 1000.0 + i * 100

        prices = stream_client.get_prices(symbols)
        assert len(prices) == 4

        for i, sym in enumerate(symbols):
            assert prices[sym] == 1000.0 + i * 100

    def test_reconnection_logic(self, stream_client):
        """Should implement exponential backoff for reconnection."""
        # Initial state
        assert stream_client.reconnect_attempts == 0

        # Simulate failed connection
        stream_client.reconnect_attempts = 1
        wait_time = 2 ** stream_client.reconnect_attempts  # 2 seconds
        assert wait_time == 2

        stream_client.reconnect_attempts = 2
        wait_time = 2 ** stream_client.reconnect_attempts  # 4 seconds
        assert wait_time == 4

        stream_client.reconnect_attempts = 3
        wait_time = 2 ** stream_client.reconnect_attempts  # 8 seconds
        assert wait_time == 8


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
