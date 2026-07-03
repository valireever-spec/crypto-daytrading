"""Simple tests for entry/exit logic - focus on coverage."""

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

# Import the modules to test
from backend.trading.autonomous_trader import entry, exit as exit_mod, validation


@pytest.fixture
def mock_trader():
    """Mock autonomous trader."""
    trader = MagicMock()
    trader.config = MagicMock()
    trader.config.enabled = True
    trader.config.entry_threshold = 50
    trader.config.exit_profit_target = 0.025
    trader.config.exit_stop_loss = 0.015
    trader.config.max_positions = 5
    trader.config.position_size_pct = 1.0
    trader.config.max_daily_loss_pct = 5.0
    trader.config.symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
    return trader


@pytest.fixture
def mock_engine():
    """Mock paper trading engine."""
    engine = AsyncMock()
    engine.get_positions = MagicMock(return_value=[])
    engine.get_account_state = MagicMock(return_value={
        "cash": 10000.0,
        "total_equity": 10000.0,
        "daily_pnl": 0.0,
        "positions": 0,
    })
    engine.place_order = AsyncMock(return_value={"success": True, "realized_pnl": 0.0})
    return engine


@pytest.fixture
def mock_stream():
    """Mock stream client with prices."""
    stream = MagicMock()
    stream.is_connected = True
    stream.price_cache = {
        "BTCUSDT": 62000.0,
        "ETHUSDT": 1750.0,
        "BNBUSDT": 565.0,
    }
    return stream


# Entry Tests
class TestEntryLogic:
    """Test entry signal generation."""

    @pytest.mark.asyncio
    async def test_check_symbol_disabled_trading(self, mock_trader, mock_engine):
        """Trading disabled should return None."""
        mock_trader.config.enabled = False

        with patch('backend.trading.autonomous_trader.entry.get_paper_trading', return_value=mock_engine):
            result = await entry._check_symbol_impl(mock_trader, "BTCUSDT")

        assert result is None

    @pytest.mark.asyncio
    async def test_check_symbol_already_has_position(self, mock_trader, mock_engine):
        """Already have position should return None."""
        mock_engine.get_positions.return_value = [
            {"symbol": "BTCUSDT", "quantity": 0.5, "entry_price": 60000}
        ]

        with patch('backend.trading.autonomous_trader.entry.get_paper_trading', return_value=mock_engine):
            with patch('backend.trading.autonomous_trader.entry._calculate_signal_impl', return_value=(75, "Strong")):
                result = await entry._check_symbol_impl(mock_trader, "BTCUSDT")

        assert result is None

    @pytest.mark.asyncio
    async def test_check_symbol_max_positions(self, mock_trader, mock_engine):
        """At max positions should return None."""
        mock_trader.config.max_positions = 1
        mock_engine.get_positions.return_value = [
            {"symbol": "ETHUSDT", "quantity": 1, "entry_price": 1700}
        ]

        with patch('backend.trading.autonomous_trader.entry.get_paper_trading', return_value=mock_engine):
            with patch('backend.trading.autonomous_trader.entry._calculate_signal_impl', return_value=(75, "Strong")):
                result = await entry._check_symbol_impl(mock_trader, "BTCUSDT")

        assert result is None

    @pytest.mark.asyncio
    async def test_check_symbol_weak_signal(self, mock_trader, mock_engine):
        """Weak signal should return None."""
        mock_trader.config.entry_threshold = 70

        with patch('backend.trading.autonomous_trader.entry.get_paper_trading', return_value=mock_engine):
            with patch('backend.trading.autonomous_trader.entry._calculate_signal_impl', return_value=(40, "Weak")):
                result = await entry._check_symbol_impl(mock_trader, "BTCUSDT")

        assert result is None

    @pytest.mark.asyncio
    async def test_execute_entry_no_engine(self, mock_trader):
        """No engine should return False."""
        signal = MagicMock(symbol="BTCUSDT", side="BUY", strength=80, reason="Test")

        with patch('backend.trading.autonomous_trader.entry.get_paper_trading', return_value=None):
            result = await entry._execute_entry_impl(mock_trader, signal)

        assert result is False

    @pytest.mark.asyncio
    async def test_execute_entry_no_price(self, mock_trader, mock_engine):
        """No price should return False."""
        signal = MagicMock(symbol="BTCUSDT", side="BUY")

        mock_stream = MagicMock()
        mock_stream.price_cache = {}

        with patch('backend.trading.autonomous_trader.entry.get_paper_trading', return_value=mock_engine):
            with patch('backend.trading.autonomous_trader.entry.get_stream_client', return_value=mock_stream):
                result = await entry._execute_entry_impl(mock_trader, signal)

        assert result is False

    @pytest.mark.asyncio
    async def test_execute_entry_success(self, mock_trader, mock_engine, mock_stream):
        """Should successfully execute entry."""
        signal = MagicMock(symbol="BTCUSDT", side="BUY", reason="Test signal")

        with patch('backend.trading.autonomous_trader.entry.get_paper_trading', return_value=mock_engine):
            with patch('backend.trading.autonomous_trader.entry.get_stream_client', return_value=mock_stream):
                with patch('backend.trading.autonomous_trader.entry.get_smart_executor', return_value=MagicMock()):
                    with patch('backend.trading.autonomous_trader.entry.validation._validate_risk_before_order_impl',
                              return_value=(True, "OK")):
                        result = await entry._execute_entry_impl(mock_trader, signal)

        assert result is True


# Exit Tests
class TestExitLogic:
    """Test exit signal generation."""

    @pytest.mark.asyncio
    async def test_check_exits_no_positions(self, mock_trader, mock_engine, mock_stream):
        """No positions should do nothing."""
        mock_engine.get_positions.return_value = []

        with patch('backend.trading.autonomous_trader.exit.get_paper_trading', return_value=mock_engine):
            with patch('backend.trading.autonomous_trader.exit.get_stream_client', return_value=mock_stream):
                result = await exit_mod._check_exits_impl(mock_trader)

        assert result is None

    @pytest.mark.asyncio
    async def test_check_exits_profit_target(self, mock_trader, mock_engine, mock_stream):
        """Should exit on profit target."""
        mock_engine.get_positions.return_value = [
            {"symbol": "BTCUSDT", "quantity": 0.5, "entry_price": 60000}
        ]
        mock_stream.price_cache = {"BTCUSDT": 61500}  # 2.5% profit

        with patch('backend.trading.autonomous_trader.exit.get_paper_trading', return_value=mock_engine):
            with patch('backend.trading.autonomous_trader.exit.get_stream_client', return_value=mock_stream):
                with patch('backend.trading.autonomous_trader.exit._execute_exit_impl', new_callable=AsyncMock) as mock_execute:
                    with patch('backend.trading.autonomous_trader.exit.get_alert_manager', return_value=AsyncMock()):
                        await exit_mod._check_exits_impl(mock_trader)

        assert mock_execute.called

    @pytest.mark.asyncio
    async def test_check_exits_stop_loss(self, mock_trader, mock_engine, mock_stream):
        """Should exit on stop loss."""
        mock_engine.get_positions.return_value = [
            {"symbol": "BTCUSDT", "quantity": 0.5, "entry_price": 60000}
        ]
        mock_stream.price_cache = {"BTCUSDT": 59100}  # -1.5% loss

        with patch('backend.trading.autonomous_trader.exit.get_paper_trading', return_value=mock_engine):
            with patch('backend.trading.autonomous_trader.exit.get_stream_client', return_value=mock_stream):
                with patch('backend.trading.autonomous_trader.exit._execute_exit_impl', new_callable=AsyncMock) as mock_execute:
                    with patch('backend.trading.autonomous_trader.exit.get_alert_manager', return_value=AsyncMock()):
                        await exit_mod._check_exits_impl(mock_trader)

        assert mock_execute.called

    @pytest.mark.asyncio
    async def test_execute_exit_no_engine(self, mock_trader):
        """No engine should return False."""
        position = {"symbol": "BTCUSDT", "quantity": 0.5}

        with patch('backend.trading.autonomous_trader.exit.get_paper_trading', return_value=None):
            result = await exit_mod._execute_exit_impl(mock_trader, position, 62000, "Profit")

        assert result is False

    @pytest.mark.asyncio
    async def test_execute_exit_success(self, mock_trader, mock_engine):
        """Should successfully execute exit."""
        position = {"symbol": "BTCUSDT", "quantity": 0.5}

        with patch('backend.trading.autonomous_trader.exit.get_paper_trading', return_value=mock_engine):
            with patch('backend.trading.autonomous_trader.exit.get_smart_executor', return_value=MagicMock()):
                result = await exit_mod._execute_exit_impl(mock_trader, position, 62000, "Profit")

        assert result is True


# Validation Tests
class TestValidationLogic:
    """Test validation logic."""

    @pytest.mark.asyncio
    async def test_get_current_prices_no_stream(self, mock_trader):
        """No stream should return empty dict."""
        with patch('backend.trading.autonomous_trader.validation.get_stream_client', return_value=None):
            result = await validation._get_current_prices_impl(mock_trader)

        assert result == {}

    @pytest.mark.asyncio
    async def test_get_current_prices_disconnected(self, mock_trader, mock_stream):
        """Disconnected stream should return empty dict."""
        mock_stream.is_connected = False

        with patch('backend.trading.autonomous_trader.validation.get_stream_client', return_value=mock_stream):
            result = await validation._get_current_prices_impl(mock_trader)

        assert result == {}

    @pytest.mark.asyncio
    async def test_get_current_prices_returns_prices(self, mock_trader, mock_stream):
        """Should return available prices."""
        with patch('backend.trading.autonomous_trader.validation.get_stream_client', return_value=mock_stream):
            result = await validation._get_current_prices_impl(mock_trader)

        assert "BTCUSDT" in result
        assert result["BTCUSDT"] == 62000.0

    @pytest.mark.asyncio
    async def test_check_daily_loss_limit_no_loss(self, mock_trader, mock_engine):
        """No loss should return False."""
        mock_engine.get_account_state.return_value = {
            "daily_pnl": 50.0,
            "total_equity": 1000.0,
        }

        with patch('backend.trading.autonomous_trader.validation.get_paper_trading', return_value=mock_engine):
            result = await validation._check_daily_loss_limit_impl(mock_trader)

        assert result is False

    @pytest.mark.asyncio
    async def test_check_daily_loss_limit_below_limit(self, mock_trader, mock_engine):
        """Loss below limit should return False."""
        mock_engine.get_account_state.return_value = {
            "daily_pnl": -30.0,  # 3% < 5% limit
            "total_equity": 1000.0,
        }

        with patch('backend.trading.autonomous_trader.validation.get_paper_trading', return_value=mock_engine):
            result = await validation._check_daily_loss_limit_impl(mock_trader)

        assert result is False

    @pytest.mark.asyncio
    async def test_check_daily_loss_limit_exceeded(self, mock_trader, mock_engine):
        """Loss exceeding limit should return True."""
        mock_engine.get_account_state.return_value = {
            "daily_pnl": -60.0,  # 6% > 5% limit
            "total_equity": 1000.0,
        }

        with patch('backend.trading.autonomous_trader.validation.get_paper_trading', return_value=mock_engine):
            result = await validation._check_daily_loss_limit_impl(mock_trader)

        assert result is True

    @pytest.mark.asyncio
    async def test_validate_risk_no_engine(self, mock_trader):
        """No engine should fail validation."""
        with patch('backend.trading.autonomous_trader.validation.get_paper_trading', return_value=None):
            is_valid, reason = await validation._validate_risk_before_order_impl(
                mock_trader, "BTCUSDT", "BUY", 0.5, 62000
            )

        assert is_valid is False

    @pytest.mark.asyncio
    async def test_validate_risk_insufficient_cash(self, mock_trader, mock_engine):
        """Insufficient cash should fail."""
        mock_engine.get_account_state.return_value = {
            "cash": 100.0,
            "total_equity": 1000.0,
            "daily_pnl": 0.0,
        }

        with patch('backend.trading.autonomous_trader.validation.get_paper_trading', return_value=mock_engine):
            is_valid, reason = await validation._validate_risk_before_order_impl(
                mock_trader, "BTCUSDT", "BUY", 0.5, 62000
            )

        assert is_valid is False
        assert "Insufficient cash" in reason

    @pytest.mark.asyncio
    async def test_validate_risk_valid_order(self, mock_trader, mock_engine):
        """Valid order should pass."""
        mock_engine.get_account_state.return_value = {
            "cash": 10000.0,
            "total_equity": 10000.0,
            "daily_pnl": 0.0,
        }

        with patch('backend.trading.autonomous_trader.validation.get_paper_trading', return_value=mock_engine):
            is_valid, reason = await validation._validate_risk_before_order_impl(
                mock_trader, "BTCUSDT", "BUY", 0.1, 62000
            )

        assert is_valid is True

    @pytest.mark.asyncio
    async def test_validate_risk_sell_no_cash_check(self, mock_trader, mock_engine):
        """SELL orders shouldn't require cash."""
        mock_engine.get_account_state.return_value = {
            "cash": 0.0,
            "total_equity": 1000.0,
            "daily_pnl": 0.0,
        }

        with patch('backend.trading.autonomous_trader.validation.get_paper_trading', return_value=mock_engine):
            is_valid, reason = await validation._validate_risk_before_order_impl(
                mock_trader, "BTCUSDT", "SELL", 0.5, 62000
            )

        assert is_valid is True
