"""Tests for entry/exit signal generation and execution."""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch, Mock

from backend.trading.autonomous_trader import entry, exit as exit_mod, validation
from backend.trading.autonomous_trader.core import TradeSignal, AutonomousTrader
from backend.core.runtime_config import TradingConfig


@pytest.fixture
def mock_config():
    """Create mock trading config."""
    config = TradingConfig()
    config.enabled = True
    config.entry_threshold = 50
    config.exit_profit_target = 0.025  # 2.5%
    config.exit_stop_loss = 0.015  # 1.5%
    config.max_positions = 5
    config.position_size_pct = 1.0
    config.max_daily_loss_pct = 5.0
    config.symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
    return config


@pytest.fixture
def mock_trader(mock_config):
    """Create mock trader."""
    trader = MagicMock(spec=AutonomousTrader)
    trader.config = mock_config
    return trader


@pytest.fixture
def mock_paper_trading():
    """Create mock paper trading engine."""
    engine = AsyncMock()
    engine.get_positions.return_value = []
    engine.get_account_state.return_value = {
        "cash": 1000.0,
        "total_equity": 1000.0,
        "daily_pnl": 0.0,
        "positions": 0,
    }
    engine.place_order = AsyncMock(return_value={"success": True, "realized_pnl": 0.0})
    return engine


@pytest.fixture
def mock_stream_client():
    """Create mock stream client."""
    client = MagicMock()
    client.is_connected = True
    client.price_cache = {
        "BTCUSDT": 62000.0,
        "ETHUSDT": 1750.0,
        "BNBUSDT": 565.0,
    }
    return client


# ============================================================================
# ENTRY TESTS
# ============================================================================


class TestCheckSymbolImpl:
    """Test entry signal generation."""

    @pytest.mark.asyncio
    async def test_disabled_trading_returns_none(self, mock_trader, mock_paper_trading):
        """Disabled trading should not generate signals."""
        mock_trader.config.enabled = False

        with patch('backend.trading.autonomous_trader.entry.get_paper_trading', return_value=mock_paper_trading):
            result = await entry._check_symbol_impl(mock_trader, "BTCUSDT")

        assert result is None

    @pytest.mark.asyncio
    async def test_already_has_position_returns_none(self, mock_trader, mock_paper_trading):
        """Should not enter if already have position."""
        mock_paper_trading.get_positions.return_value = [
            {"symbol": "BTCUSDT", "quantity": 0.5, "entry_price": 60000}
        ]

        with patch('backend.trading.autonomous_trader.entry.get_paper_trading', return_value=mock_paper_trading):
            with patch('backend.trading.autonomous_trader.entry._calculate_signal_impl', return_value=(75, "Strong signal")):
                result = await entry._check_symbol_impl(mock_trader, "BTCUSDT")

        assert result is None

    @pytest.mark.asyncio
    async def test_max_positions_reached_returns_none(self, mock_trader, mock_paper_trading):
        """Should not enter if at max positions."""
        mock_trader.config.max_positions = 2
        mock_paper_trading.get_positions.return_value = [
            {"symbol": "ETHUSDT", "quantity": 1, "entry_price": 1700},
            {"symbol": "BNBUSDT", "quantity": 10, "entry_price": 560},
        ]

        with patch('backend.trading.autonomous_trader.entry.get_paper_trading', return_value=mock_paper_trading):
            with patch('backend.trading.autonomous_trader.entry._calculate_signal_impl', return_value=(75, "Strong signal")):
                result = await entry._check_symbol_impl(mock_trader, "BTCUSDT")

        assert result is None

    @pytest.mark.asyncio
    async def test_weak_signal_returns_none(self, mock_trader, mock_paper_trading):
        """Should not enter if signal below threshold."""
        mock_trader.config.entry_threshold = 70

        with patch('backend.trading.autonomous_trader.entry.get_paper_trading', return_value=mock_paper_trading):
            with patch('backend.trading.autonomous_trader.entry._calculate_signal_impl', return_value=(40, "Weak signal")):
                result = await entry._check_symbol_impl(mock_trader, "BTCUSDT")

        assert result is None

    @pytest.mark.asyncio
    async def test_strong_signal_returns_trade_signal(self, mock_trader, mock_paper_trading):
        """Should return TradeSignal when all conditions met."""
        with patch('backend.trading.autonomous_trader.entry.get_paper_trading', return_value=mock_paper_trading):
            with patch('backend.trading.autonomous_trader.entry._calculate_signal_impl', return_value=(85, "Strong momentum")):
                with patch('backend.trading.autonomous_trader.entry._get_adaptive_entry_threshold_impl', return_value=50):
                    result = await entry._check_symbol_impl(mock_trader, "BTCUSDT")

        assert result is not None
        assert isinstance(result, TradeSignal)
        assert result.symbol == "BTCUSDT"
        assert result.side == "BUY"
        assert result.strength == 85

    @pytest.mark.asyncio
    async def test_exception_handling_returns_none(self, mock_trader):
        """Should return None on exception."""
        with patch('backend.trading.autonomous_trader.entry.get_paper_trading', side_effect=Exception("Test error")):
            result = await entry._check_symbol_impl(mock_trader, "BTCUSDT")

        assert result is None


class TestCalculateSignalImpl:
    """Test signal calculation."""

    @pytest.mark.asyncio
    async def test_signal_above_threshold(self, mock_trader):
        """Should return signal when above threshold."""
        mock_trader.config.entry_threshold = 50

        # Run multiple times to handle randomness
        for _ in range(10):
            result = await entry._calculate_signal_impl(mock_trader, "BTCUSDT")
            if result is not None:
                strength, reason = result
                assert 40 <= strength <= 100
                assert "Momentum" in reason
                break
        else:
            pytest.fail("No signal generated in 10 attempts")

    @pytest.mark.asyncio
    async def test_exception_handling(self, mock_trader):
        """Should return None on exception."""
        with patch('backend.trading.autonomous_trader.entry.get_stream_client', side_effect=Exception("Test error")):
            result = await entry._calculate_signal_impl(mock_trader, "BTCUSDT")

        assert result is None


class TestExecuteEntryImpl:
    """Test entry execution."""

    @pytest.mark.asyncio
    async def test_no_engine_returns_false(self, mock_trader):
        """Should fail if no paper trading engine."""
        signal = TradeSignal(
            symbol="BTCUSDT",
            side="BUY",
            strength=85,
            reason="Test signal",
            timestamp=datetime.utcnow(),
        )

        with patch('backend.trading.autonomous_trader.entry.get_paper_trading', return_value=None):
            result = await entry._execute_entry_impl(mock_trader, signal)

        assert result is False

    @pytest.mark.asyncio
    async def test_no_price_returns_false(self, mock_trader, mock_paper_trading):
        """Should fail if no current price."""
        signal = TradeSignal(
            symbol="BTCUSDT",
            side="BUY",
            strength=85,
            reason="Test signal",
            timestamp=datetime.utcnow(),
        )

        mock_stream_client = MagicMock()
        mock_stream_client.price_cache = {}

        with patch('backend.trading.autonomous_trader.entry.get_paper_trading', return_value=mock_paper_trading):
            with patch('backend.trading.autonomous_trader.entry.get_stream_client', return_value=mock_stream_client):
                result = await entry._execute_entry_impl(mock_trader, signal)

        assert result is False

    @pytest.mark.asyncio
    async def test_insufficient_cash_returns_false(self, mock_trader, mock_paper_trading):
        """Should fail if insufficient cash."""
        signal = TradeSignal(
            symbol="BTCUSDT",
            side="BUY",
            strength=85,
            reason="Test signal",
            timestamp=datetime.utcnow(),
        )

        mock_paper_trading.get_account_state.return_value = {
            "cash": 1.0,  # Very low cash
            "total_equity": 1000.0,
            "daily_pnl": 0.0,
        }

        mock_stream_client = MagicMock()
        mock_stream_client.price_cache = {"BTCUSDT": 62000.0}

        with patch('backend.trading.autonomous_trader.entry.get_paper_trading', return_value=mock_paper_trading):
            with patch('backend.trading.autonomous_trader.entry.get_stream_client', return_value=mock_stream_client):
                with patch('backend.trading.autonomous_trader.entry.validation._validate_risk_before_order_impl', return_value=(False, "Insufficient cash")):
                    result = await entry._execute_entry_impl(mock_trader, signal)

        assert result is False

    @pytest.mark.asyncio
    async def test_successful_entry_returns_true(self, mock_trader, mock_paper_trading):
        """Should successfully execute entry."""
        signal = TradeSignal(
            symbol="BTCUSDT",
            side="BUY",
            strength=85,
            reason="Test signal",
            timestamp=datetime.utcnow(),
        )

        mock_stream_client = MagicMock()
        mock_stream_client.price_cache = {"BTCUSDT": 62000.0}

        with patch('backend.trading.autonomous_trader.entry.get_paper_trading', return_value=mock_paper_trading):
            with patch('backend.trading.autonomous_trader.entry.get_stream_client', return_value=mock_stream_client):
                with patch('backend.trading.autonomous_trader.entry.get_smart_executor', return_value=MagicMock()):
                    with patch('backend.trading.autonomous_trader.entry.validation._validate_risk_before_order_impl', return_value=(True, "OK")):
                        result = await entry._execute_entry_impl(mock_trader, signal)

        assert result is True
        mock_paper_trading.place_order.assert_called_once()


# ============================================================================
# EXIT TESTS
# ============================================================================


class TestCheckExitsImpl:
    """Test exit signal generation."""

    @pytest.mark.asyncio
    async def test_no_positions_returns_none(self, mock_trader, mock_paper_trading):
        """Should do nothing if no open positions."""
        mock_paper_trading.get_positions.return_value = []

        with patch('backend.trading.autonomous_trader.exit.get_paper_trading', return_value=mock_paper_trading):
            with patch('backend.trading.autonomous_trader.exit.get_stream_client', return_value=MagicMock()):
                result = await exit_mod._check_exits_impl(mock_trader)

        assert result is None

    @pytest.mark.asyncio
    async def test_profit_target_exit(self, mock_trader, mock_paper_trading):
        """Should exit when profit target reached."""
        mock_paper_trading.get_positions.return_value = [
            {
                "symbol": "BTCUSDT",
                "quantity": 0.5,
                "entry_price": 60000,
            }
        ]

        mock_stream_client = MagicMock()
        mock_stream_client.price_cache = {"BTCUSDT": 61500}  # 2.5% profit

        with patch('backend.trading.autonomous_trader.exit.get_paper_trading', return_value=mock_paper_trading):
            with patch('backend.trading.autonomous_trader.exit.get_stream_client', return_value=mock_stream_client):
                with patch('backend.trading.autonomous_trader.exit._execute_exit_impl', new_callable=AsyncMock) as mock_execute:
                    with patch('backend.trading.autonomous_trader.exit.get_alert_manager', return_value=AsyncMock()):
                        await exit_mod._check_exits_impl(mock_trader)

        mock_execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_loss_exit(self, mock_trader, mock_paper_trading):
        """Should exit when stop loss hit."""
        mock_paper_trading.get_positions.return_value = [
            {
                "symbol": "BTCUSDT",
                "quantity": 0.5,
                "entry_price": 60000,
            }
        ]

        mock_stream_client = MagicMock()
        mock_stream_client.price_cache = {"BTCUSDT": 59100}  # -1.5% loss

        with patch('backend.trading.autonomous_trader.exit.get_paper_trading', return_value=mock_paper_trading):
            with patch('backend.trading.autonomous_trader.exit.get_stream_client', return_value=mock_stream_client):
                with patch('backend.trading.autonomous_trader.exit._execute_exit_impl', new_callable=AsyncMock) as mock_execute:
                    with patch('backend.trading.autonomous_trader.exit.get_alert_manager', return_value=AsyncMock()):
                        await exit_mod._check_exits_impl(mock_trader)

        mock_execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_exit_between_limits(self, mock_trader, mock_paper_trading):
        """Should not exit when P&L between limits."""
        mock_paper_trading.get_positions.return_value = [
            {
                "symbol": "BTCUSDT",
                "quantity": 0.5,
                "entry_price": 60000,
            }
        ]

        mock_stream_client = MagicMock()
        mock_stream_client.price_cache = {"BTCUSDT": 60500}  # 0.83% - between stop loss and profit target

        with patch('backend.trading.autonomous_trader.exit.get_paper_trading', return_value=mock_paper_trading):
            with patch('backend.trading.autonomous_trader.exit.get_stream_client', return_value=mock_stream_client):
                with patch('backend.trading.autonomous_trader.exit._execute_exit_impl', new_callable=AsyncMock) as mock_execute:
                    await exit_mod._check_exits_impl(mock_trader)

        mock_execute.assert_not_called()


class TestExecuteExitImpl:
    """Test exit execution."""

    @pytest.mark.asyncio
    async def test_no_engine_returns_false(self, mock_trader):
        """Should fail if no paper trading engine."""
        position = {
            "symbol": "BTCUSDT",
            "quantity": 0.5,
            "entry_price": 60000,
        }

        with patch('backend.trading.autonomous_trader.exit.get_paper_trading', return_value=None):
            result = await exit_mod._execute_exit_impl(mock_trader, position, 62000, "Profit target")

        assert result is False

    @pytest.mark.asyncio
    async def test_successful_exit_returns_true(self, mock_trader, mock_paper_trading):
        """Should successfully execute exit."""
        position = {
            "symbol": "BTCUSDT",
            "quantity": 0.5,
            "entry_price": 60000,
        }

        with patch('backend.trading.autonomous_trader.exit.get_paper_trading', return_value=mock_paper_trading):
            with patch('backend.trading.autonomous_trader.exit.get_smart_executor', return_value=MagicMock()):
                result = await exit_mod._execute_exit_impl(mock_trader, position, 62000, "Profit target")

        assert result is True
        mock_paper_trading.place_order.assert_called_once()

    @pytest.mark.asyncio
    async def test_exit_with_order_failure(self, mock_trader, mock_paper_trading):
        """Should handle order failure."""
        position = {
            "symbol": "BTCUSDT",
            "quantity": 0.5,
            "entry_price": 60000,
        }

        mock_paper_trading.place_order.return_value = {"success": False, "error": "Order rejected"}

        with patch('backend.trading.autonomous_trader.exit.get_paper_trading', return_value=mock_paper_trading):
            with patch('backend.trading.autonomous_trader.exit.get_smart_executor', return_value=MagicMock()):
                result = await exit_mod._execute_exit_impl(mock_trader, position, 62000, "Profit target")

        assert result is False


# ============================================================================
# VALIDATION TESTS
# ============================================================================


class TestGetCurrentPricesImpl:
    """Test getting current prices."""

    @pytest.mark.asyncio
    async def test_no_stream_client_returns_empty(self, mock_trader):
        """Should return empty dict if no stream client."""
        with patch('backend.trading.autonomous_trader.validation.get_stream_client', return_value=None):
            result = await validation._get_current_prices_impl(mock_trader)

        assert result == {}

    @pytest.mark.asyncio
    async def test_disconnected_stream_returns_empty(self, mock_trader):
        """Should return empty dict if stream disconnected."""
        mock_stream_client = MagicMock()
        mock_stream_client.is_connected = False

        with patch('backend.trading.autonomous_trader.validation.get_stream_client', return_value=mock_stream_client):
            result = await validation._get_current_prices_impl(mock_trader)

        assert result == {}

    @pytest.mark.asyncio
    async def test_returns_available_prices(self, mock_trader, mock_stream_client):
        """Should return available prices."""
        with patch('backend.trading.autonomous_trader.validation.get_stream_client', return_value=mock_stream_client):
            result = await validation._get_current_prices_impl(mock_trader)

        assert "BTCUSDT" in result
        assert result["BTCUSDT"] == 62000.0


class TestCheckDailyLossLimitImpl:
    """Test daily loss limit checking."""

    @pytest.mark.asyncio
    async def test_no_loss_returns_false(self, mock_trader, mock_paper_trading):
        """Should return False when no loss."""
        mock_paper_trading.get_account_state.return_value = {
            "daily_pnl": 50.0,
            "total_equity": 1000.0,
        }

        with patch('backend.trading.autonomous_trader.validation.get_paper_trading', return_value=mock_paper_trading):
            result = await validation._check_daily_loss_limit_impl(mock_trader)

        assert result is False

    @pytest.mark.asyncio
    async def test_loss_below_limit_returns_false(self, mock_trader, mock_paper_trading):
        """Should return False when loss below limit."""
        mock_paper_trading.get_account_state.return_value = {
            "daily_pnl": -30.0,  # 3% loss, limit is 5%
            "total_equity": 1000.0,
        }

        with patch('backend.trading.autonomous_trader.validation.get_paper_trading', return_value=mock_paper_trading):
            result = await validation._check_daily_loss_limit_impl(mock_trader)

        assert result is False

    @pytest.mark.asyncio
    async def test_loss_exceeds_limit_returns_true(self, mock_trader, mock_paper_trading):
        """Should return True when loss exceeds limit."""
        mock_paper_trading.get_account_state.return_value = {
            "daily_pnl": -60.0,  # 6% loss, limit is 5%
            "total_equity": 1000.0,
        }

        with patch('backend.trading.autonomous_trader.validation.get_paper_trading', return_value=mock_paper_trading):
            result = await validation._check_daily_loss_limit_impl(mock_trader)

        assert result is True


class TestValidateRiskBeforeOrderImpl:
    """Test pre-order risk validation."""

    @pytest.mark.asyncio
    async def test_no_engine_returns_false(self, mock_trader):
        """Should fail if no engine."""
        with patch('backend.trading.autonomous_trader.validation.get_paper_trading', return_value=None):
            is_valid, reason = await validation._validate_risk_before_order_impl(
                mock_trader, "BTCUSDT", "BUY", 0.5, 62000
            )

        assert is_valid is False

    @pytest.mark.asyncio
    async def test_insufficient_cash_returns_false(self, mock_trader, mock_paper_trading):
        """Should fail if insufficient cash."""
        mock_paper_trading.get_account_state.return_value = {
            "cash": 100.0,  # Insufficient for $31,000 order
            "total_equity": 1000.0,
            "daily_pnl": 0.0,
        }

        with patch('backend.trading.autonomous_trader.validation.get_paper_trading', return_value=mock_paper_trading):
            is_valid, reason = await validation._validate_risk_before_order_impl(
                mock_trader, "BTCUSDT", "BUY", 0.5, 62000
            )

        assert is_valid is False
        assert "Insufficient cash" in reason

    @pytest.mark.asyncio
    async def test_daily_loss_limit_exceeded_returns_false(self, mock_trader, mock_paper_trading):
        """Should fail if daily loss limit already exceeded."""
        mock_paper_trading.get_account_state.return_value = {
            "cash": 1000.0,
            "total_equity": 1000.0,
            "daily_pnl": -60.0,  # 6% loss, limit is 5%
        }

        with patch('backend.trading.autonomous_trader.validation.get_paper_trading', return_value=mock_paper_trading):
            is_valid, reason = await validation._validate_risk_before_order_impl(
                mock_trader, "BTCUSDT", "BUY", 0.5, 62000
            )

        assert is_valid is False
        assert "Daily loss limit" in reason

    @pytest.mark.asyncio
    async def test_order_would_exceed_limit_returns_false(self, mock_trader, mock_paper_trading):
        """Should fail if order would exceed daily loss limit."""
        mock_paper_trading.get_account_state.return_value = {
            "cash": 1000.0,
            "total_equity": 1000.0,
            "daily_pnl": -40.0,  # 4% loss, adding 2% worst-case = 6% total > 5% limit
        }

        with patch('backend.trading.autonomous_trader.validation.get_paper_trading', return_value=mock_paper_trading):
            is_valid, reason = await validation._validate_risk_before_order_impl(
                mock_trader, "BTCUSDT", "BUY", 0.5, 62000
            )

        assert is_valid is False
        assert "exceed daily limit" in reason

    @pytest.mark.asyncio
    async def test_valid_order_returns_true(self, mock_trader, mock_paper_trading):
        """Should pass valid order."""
        mock_paper_trading.get_account_state.return_value = {
            "cash": 10000.0,
            "total_equity": 10000.0,
            "daily_pnl": 0.0,
        }

        with patch('backend.trading.autonomous_trader.validation.get_paper_trading', return_value=mock_paper_trading):
            is_valid, reason = await validation._validate_risk_before_order_impl(
                mock_trader, "BTCUSDT", "BUY", 0.1, 62000
            )

        assert is_valid is True
        assert reason == "OK"

    @pytest.mark.asyncio
    async def test_sell_order_skips_cash_check(self, mock_trader, mock_paper_trading):
        """Should pass SELL orders without cash check."""
        mock_paper_trading.get_account_state.return_value = {
            "cash": 0.0,  # No cash
            "total_equity": 1000.0,
            "daily_pnl": 0.0,
        }

        with patch('backend.trading.autonomous_trader.validation.get_paper_trading', return_value=mock_paper_trading):
            is_valid, reason = await validation._validate_risk_before_order_impl(
                mock_trader, "BTCUSDT", "SELL", 0.5, 62000
            )

        assert is_valid is True
