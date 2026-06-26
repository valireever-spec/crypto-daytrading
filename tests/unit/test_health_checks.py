"""Comprehensive health check tests for crypto trading system.

Tests verify that the health check system actually detects real failures,
not just whether services "are running."
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
from backend.core.health_checker import (
    HealthChecker,
    HealthStatus,
    init_health_checker,
)


class TestHealthStatus:
    """Test HealthStatus class."""

    def test_health_status_healthy(self):
        """Test healthy status."""
        status = HealthStatus("test", True, "All good", {"detail": "value"})
        assert status.healthy is True
        assert status.name == "test"
        assert status.message == "All good"
        assert "timestamp" in status.to_dict()

    def test_health_status_unhealthy(self):
        """Test unhealthy status."""
        status = HealthStatus("test", False, "Failed")
        assert status.healthy is False


class TestWebSocketHealthCheck:
    """Test WebSocket freshness detection."""

    @pytest.mark.asyncio
    async def test_websocket_healthy_fresh_data(self):
        """WebSocket should be healthy when data is fresh (<2 min old)."""
        checker = HealthChecker()

        # Mock stream client with fresh data
        mock_client = Mock()
        mock_client.get_last_update_time.return_value = datetime.utcnow() - timedelta(
            seconds=30
        )

        with patch(
            "backend.exchange.binance_stream.get_stream_client", return_value=mock_client
        ):
            status = await checker._check_websocket()
            assert status.healthy is True
            assert "30" in status.message  # Should show age

    @pytest.mark.asyncio
    async def test_websocket_unhealthy_stale_data(self):
        """WebSocket should be unhealthy when data is stale (>2 min)."""
        checker = HealthChecker()

        # Mock stream client with stale data
        mock_client = Mock()
        mock_client.get_last_update_time.return_value = datetime.utcnow() - timedelta(
            minutes=3
        )

        with patch(
            "backend.exchange.binance_stream.get_stream_client", return_value=mock_client
        ):
            status = await checker._check_websocket()
            assert status.healthy is False
            assert "STALE" in status.message

    @pytest.mark.asyncio
    async def test_websocket_unhealthy_not_initialized(self):
        """WebSocket should be unhealthy when not initialized."""
        checker = HealthChecker()

        with patch(
            "backend.exchange.binance_stream.get_stream_client", return_value=None
        ):
            status = await checker._check_websocket()
            assert status.healthy is False
            assert "not initialized" in status.message


class TestTradeLogHealthCheck:
    """Test trade log freshness detection."""

    @pytest.mark.asyncio
    async def test_trade_log_healthy_recent_trade(self, tmp_path):
        """Trade log should be healthy when last trade is recent."""
        checker = HealthChecker()

        # Create trade log with recent entry
        log_file = tmp_path / "trades.jsonl"
        recent_ts = (datetime.utcnow() - timedelta(minutes=5)).isoformat() + "Z"
        log_file.write_text(f'{{"timestamp": "{recent_ts}", "symbol": "BTCUSDT"}}\n')

        with patch("pathlib.Path") as mock_path:
            mock_path.return_value = log_file
            mock_path.return_value.exists.return_value = True
            status = await checker._check_trade_log()
            assert status.healthy is True

    @pytest.mark.asyncio
    async def test_trade_log_unhealthy_stale(self, tmp_path):
        """Trade log should be unhealthy when last trade is >1 hour old."""
        checker = HealthChecker()

        # Create trade log with stale entry
        log_file = tmp_path / "trades.jsonl"
        stale_trade = {
            "timestamp": (datetime.utcnow() - timedelta(hours=2)).isoformat() + "Z",
            "symbol": "BTCUSDT",
            "side": "BUY",
        }
        import json

        log_file.write_text(json.dumps(stale_trade))

        with patch("pathlib.Path", return_value=log_file):
            status = await checker._check_trade_log()
            assert status.healthy is False
            assert "STALE" in status.message
            assert "hours" in status.message

    @pytest.mark.asyncio
    async def test_trade_log_unhealthy_not_found(self, tmp_path):
        """Trade log should be unhealthy when file doesn't exist."""
        checker = HealthChecker()

        with patch("pathlib.Path") as mock_path_cls:
            mock_file = Mock()
            mock_file.exists.return_value = False
            mock_path_cls.return_value = mock_file
            status = await checker._check_trade_log()
            assert status.healthy is False


class TestPriceFeedHealthCheck:
    """Test price feed freshness detection."""

    @pytest.mark.asyncio
    async def test_price_feed_healthy_all_symbols_fresh(self):
        """Price feed should be healthy when all symbols have fresh data."""
        checker = HealthChecker()

        mock_client = Mock()
        mock_client.get_price_age_seconds.side_effect = lambda s: 30  # All symbols 30s old

        with patch(
            "backend.exchange.binance_stream.get_stream_client", return_value=mock_client
        ):
            status = await checker._check_price_feed()
            assert status.healthy is True
            assert "All" in status.message

    @pytest.mark.asyncio
    async def test_price_feed_unhealthy_stale_symbol(self):
        """Price feed should be unhealthy when any symbol is stale."""
        checker = HealthChecker()

        mock_client = Mock()
        # BTCUSDT is fresh, ETHUSDT is stale
        def age_side_effect(symbol):
            if symbol == "ETHUSDT":
                return 300  # 5 minutes old = stale
            return 30  # Fresh

        mock_client.get_price_age_seconds.side_effect = age_side_effect

        with patch(
            "backend.exchange.binance_stream.get_stream_client", return_value=mock_client
        ):
            status = await checker._check_price_feed()
            assert status.healthy is False
            assert "Stale prices" in status.message
            assert "ETHUSDT" in status.message


class TestAutonomousTraderHealthCheck:
    """Test autonomous trader status detection."""

    @pytest.mark.asyncio
    async def test_trader_healthy_running_with_positions(self):
        """Trader should be healthy when running with active positions."""
        checker = HealthChecker()

        mock_trader = Mock()
        mock_trader.is_running.return_value = True
        mock_trader.get_status.return_value = {
            "active_positions": 3,
            "total_trades": 10,
            "daily_pnl": 50.0,
        }

        with patch(
            "backend.trading.autonomous_trader.get_autonomous_trader",
            return_value=mock_trader,
        ):
            status = await checker._check_autonomous_trader()
            assert status.healthy is True
            assert "3 positions" in status.message

    @pytest.mark.asyncio
    async def test_trader_unhealthy_not_running(self):
        """Trader should be unhealthy when stopped."""
        checker = HealthChecker()

        mock_trader = Mock()
        mock_trader.is_running.return_value = False

        with patch(
            "backend.trading.autonomous_trader.get_autonomous_trader",
            return_value=mock_trader,
        ):
            status = await checker._check_autonomous_trader()
            assert status.healthy is False
            assert "stopped" in status.message

    @pytest.mark.asyncio
    async def test_trader_unhealthy_not_initialized(self):
        """Trader should be unhealthy when not initialized."""
        checker = HealthChecker()

        with patch(
            "backend.trading.autonomous_trader.get_autonomous_trader", return_value=None
        ):
            status = await checker._check_autonomous_trader()
            assert status.healthy is False
            assert "not initialized" in status.message


class TestDatabaseHealthCheck:
    """Test database connectivity."""

    @pytest.mark.asyncio
    async def test_database_healthy(self):
        """Database should be healthy when accessible."""
        checker = HealthChecker()

        with patch("backend.core.database.Database") as mock_db_cls:
            mock_db = Mock()
            mock_db.get_open_positions.return_value = [
                {"symbol": "BTCUSDT", "quantity": 0.1}
            ]
            mock_db_cls.return_value = mock_db
            status = await checker._check_database()
            assert status.healthy is True

    @pytest.mark.asyncio
    async def test_database_unhealthy_not_responding(self):
        """Database should be unhealthy when query fails."""
        checker = HealthChecker()

        with patch("backend.core.database.Database") as mock_db_cls:
            mock_db = Mock()
            mock_db.get_open_positions.side_effect = Exception("Connection refused")
            mock_db_cls.return_value = mock_db
            status = await checker._check_database()
            assert status.healthy is False


class TestOverallHealthCheck:
    """Test overall health determination."""

    @pytest.mark.asyncio
    async def test_overall_healthy_all_green(self):
        """Overall health should be HEALTHY when all checks pass."""
        checker = HealthChecker()

        # Mock all checks to pass
        async def mock_healthy(*args, **kwargs):
            return HealthStatus("test", True, "OK")

        with patch.multiple(
            checker,
            _check_websocket=AsyncMock(return_value=HealthStatus("ws", True, "OK")),
            _check_trade_log=AsyncMock(return_value=HealthStatus("log", True, "OK")),
            _check_price_feed=AsyncMock(return_value=HealthStatus("price", True, "OK")),
            _check_autonomous_trader=AsyncMock(return_value=HealthStatus("trader", True, "OK")),
            _check_database=AsyncMock(return_value=HealthStatus("db", True, "OK")),
            _check_memory=AsyncMock(return_value=HealthStatus("mem", True, "OK")),
            _check_disk=AsyncMock(return_value=HealthStatus("disk", True, "OK")),
        ):
            result = await checker.check_all()
            assert result["overall_healthy"] is True
            assert result["summary"]["status"] == "HEALTHY"

    @pytest.mark.asyncio
    async def test_overall_critical_when_websocket_dead(self):
        """Overall health should be CRITICAL when WebSocket is dead."""
        checker = HealthChecker()

        with patch.multiple(
            checker,
            _check_websocket=AsyncMock(
                return_value=HealthStatus("ws", False, "WebSocket dead")
            ),
            _check_trade_log=AsyncMock(return_value=HealthStatus("log", True, "OK")),
            _check_price_feed=AsyncMock(return_value=HealthStatus("price", True, "OK")),
            _check_autonomous_trader=AsyncMock(return_value=HealthStatus("trader", True, "OK")),
            _check_database=AsyncMock(return_value=HealthStatus("db", True, "OK")),
            _check_memory=AsyncMock(return_value=HealthStatus("mem", True, "OK")),
            _check_disk=AsyncMock(return_value=HealthStatus("disk", True, "OK")),
        ):
            result = await checker.check_all()
            assert result["overall_healthy"] is False
            # WebSocket is critical
            assert "websocket" in result["summary"]["unhealthy_services"]


class TestHealthCheckHistory:
    """Test health check history tracking."""

    @pytest.mark.asyncio
    async def test_health_history_stored(self):
        """Health check results should be stored in history."""
        checker = HealthChecker()

        with patch.multiple(
            checker,
            _check_websocket=AsyncMock(return_value=HealthStatus("ws", True, "OK")),
            _check_trade_log=AsyncMock(return_value=HealthStatus("log", True, "OK")),
            _check_price_feed=AsyncMock(return_value=HealthStatus("price", True, "OK")),
            _check_autonomous_trader=AsyncMock(return_value=HealthStatus("trader", True, "OK")),
            _check_database=AsyncMock(return_value=HealthStatus("db", True, "OK")),
            _check_memory=AsyncMock(return_value=HealthStatus("mem", True, "OK")),
            _check_disk=AsyncMock(return_value=HealthStatus("disk", True, "OK")),
        ):
            await checker.check_all()

            # Verify history was recorded
            history = checker.get_history("websocket")
            assert len(history) > 0
            assert history[0]["name"] in ["websocket", "ws"]
