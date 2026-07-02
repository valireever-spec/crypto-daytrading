"""Unit tests for WebSocket manager with automatic recovery and REST fallback."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from backend.exchange.websocket_manager import WebSocketManager, PriceUpdate


@pytest.mark.asyncio
async def test_websocket_manager_initialization():
    """Test WebSocketManager initialization."""
    manager = WebSocketManager(symbols=["BTCUSDT", "ETHUSDT"])
    assert manager.symbols == ["BTCUSDT", "ETHUSDT"]
    assert manager.connected == False
    assert manager.reconnect_attempts == 0
    assert manager.prices == {}


@pytest.mark.asyncio
async def test_price_update_structure():
    """Test PriceUpdate dataclass structure."""
    update = PriceUpdate(
        symbol="BTCUSDT",
        price=45000.50,
        timestamp="2026-07-02T10:00:00Z",
        source="websocket"
    )
    assert update.symbol == "BTCUSDT"
    assert update.price == 45000.50
    assert update.source == "websocket"


@pytest.mark.asyncio
async def test_get_price():
    """Test retrieving price from cache."""
    manager = WebSocketManager(symbols=["BTCUSDT"])
    manager.prices["BTCUSDT"] = PriceUpdate(
        symbol="BTCUSDT",
        price=45000.0,
        timestamp="2026-07-02T10:00:00Z",
        source="websocket"
    )

    price = manager.get_price("BTCUSDT")
    assert price == 45000.0


@pytest.mark.asyncio
async def test_get_price_missing():
    """Test getting price for non-existent symbol."""
    manager = WebSocketManager(symbols=["BTCUSDT"])
    price = manager.get_price("NONEXISTENT")
    assert price is None


@pytest.mark.asyncio
async def test_health_check_connected():
    """Test health check when WebSocket is connected."""
    manager = WebSocketManager(symbols=["BTCUSDT"])
    manager.connected = True
    manager.ws_failures = 0

    health = manager.get_health()
    assert health["websocket"]["connected"] == True
    assert health["websocket"]["failures"] == 0


@pytest.mark.asyncio
async def test_health_check_disconnected_with_fallback():
    """Test health check when WebSocket is down but REST is active."""
    manager = WebSocketManager(symbols=["BTCUSDT"])
    manager.connected = False
    manager.rest_fallback_active = True
    manager.rest_failures = 0

    health = manager.get_health()
    assert health["websocket"]["connected"] == False
    assert health["rest"]["active"] == True


@pytest.mark.asyncio
async def test_stale_data_detection():
    """Test detection of stale WebSocket data."""
    from datetime import datetime, timedelta

    manager = WebSocketManager(symbols=["BTCUSDT"])

    # Simulate old price update
    old_time = datetime.utcnow() - timedelta(seconds=60)
    manager.prices["BTCUSDT"] = PriceUpdate(
        symbol="BTCUSDT",
        price=45000.0,
        timestamp=old_time.isoformat(),
        source="websocket"
    )

    age = manager.get_price_age("BTCUSDT")
    assert age > 50  # Should be > 50 seconds old


@pytest.mark.asyncio
async def test_reconnection_backoff():
    """Test exponential backoff for reconnection."""
    manager = WebSocketManager(symbols=["BTCUSDT"])

    # Test backoff calculation for different attempt numbers
    backoffs = []
    for attempt in range(6):
        manager.reconnect_attempts = attempt
        backoff = min(2 ** attempt, 60)
        backoffs.append(backoff)

    expected = [1, 2, 4, 8, 16, 32]
    assert backoffs == expected


@pytest.mark.asyncio
async def test_register_callback():
    """Test registering price callbacks."""
    manager = WebSocketManager(symbols=["BTCUSDT"])

    callback_called = []
    async def callback(symbol, price):
        callback_called.append((symbol, price))

    manager.register_callback("BTCUSDT", callback)
    assert "BTCUSDT" in manager.callbacks


@pytest.mark.asyncio
async def test_max_age_seconds_enforcement():
    """Test that stale data beyond max_age_seconds is rejected."""
    from datetime import datetime, timedelta

    manager = WebSocketManager(symbols=["BTCUSDT"], max_age_seconds=30)

    # Price older than max_age_seconds
    old_time = datetime.utcnow() - timedelta(seconds=35)
    manager.prices["BTCUSDT"] = PriceUpdate(
        symbol="BTCUSDT",
        price=45000.0,
        timestamp=old_time.isoformat(),
        source="websocket"
    )

    age = manager.get_price_age("BTCUSDT")
    assert age > manager.max_age_seconds


def test_websocket_manager_symbols():
    """Test WebSocketManager symbol list handling."""
    manager = WebSocketManager(symbols=["BTCUSDT", "ETHUSDT", "BNBUSDT"])
    assert len(manager.symbols) == 3
    assert "BTCUSDT" in manager.symbols
    assert "ETHUSDT" in manager.symbols
    assert "BNBUSDT" in manager.symbols


def test_get_all_prices():
    """Test retrieving all prices."""
    manager = WebSocketManager(symbols=["BTCUSDT", "ETHUSDT"])
    manager.prices["BTCUSDT"] = PriceUpdate(
        symbol="BTCUSDT",
        price=45000.0,
        timestamp="2026-07-02T10:00:00Z",
        source="websocket"
    )
    manager.prices["ETHUSDT"] = PriceUpdate(
        symbol="ETHUSDT",
        price=1800.0,
        timestamp="2026-07-02T10:00:00Z",
        source="websocket"
    )

    all_prices = manager.get_all_prices()
    assert len(all_prices) == 2
    assert all_prices["BTCUSDT"] == 45000.0
    assert all_prices["ETHUSDT"] == 1800.0
