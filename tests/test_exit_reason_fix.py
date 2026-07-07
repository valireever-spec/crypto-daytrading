"""Test exit_reason data is correctly passed through and stored (CRITICAL #1 FIX)."""

import asyncio
import pytest
from datetime import datetime, timezone
import tempfile
import shutil
import os

from backend.execution.exit_manager import (
    ExitManager, Position, ExitSignal, ExitReason
)
from backend.exchange.paper_trading import get_paper_trading, init_paper_trading


@pytest.fixture
def setup_trading():
    """Initialize paper trading engine with clean state."""
    # Create temporary database to avoid conflicts with live system
    temp_dir = tempfile.mkdtemp()
    original_db_path = os.environ.get("DATABASE_PATH")

    try:
        os.environ["DATABASE_PATH"] = os.path.join(temp_dir, "test.db")

        init_paper_trading()
        engine = get_paper_trading()

        # Clear any existing positions/trades from restoration
        engine.positions.clear()
        engine.trade_history.clear()
        engine.cash = 10000.0
        engine.total_pnl = 0.0
        engine.daily_pnl = 0.0

        yield engine
    finally:
        # Restore original DB path
        if original_db_path:
            os.environ["DATABASE_PATH"] = original_db_path
        else:
            os.environ.pop("DATABASE_PATH", None)
        # Clean up temp directory
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_exit_reason_profit_target(setup_trading):
    """Verify exit_reason PROFIT_TARGET is stored in Trade record."""
    engine = setup_trading

    # Create a position
    order_result = asyncio.run(
        engine.place_order(
            symbol="BTCUSDT",
            side="BUY",
            quantity=0.5,
            current_price=50000.0,
        )
    )
    assert order_result.get("status") == "FILLED", f"BUY order failed: {order_result}"

    # Execute exit with PROFIT_TARGET reason
    exit_result = asyncio.run(
        engine.place_order(
            symbol="BTCUSDT",
            side="SELL",
            quantity=0.5,
            current_price=51000.0,
            exit_reason="profit_target",  # ← This should be stored
        )
    )
    assert exit_result.get("status") == "FILLED", f"SELL order failed: {exit_result}"

    # Verify exit_reason is in the Trade record
    trades = engine.get_trades()
    assert len(trades) >= 2, f"Expected ≥2 trades, got {len(trades)}"

    exit_trade = trades[-1]  # Last trade is the exit
    assert exit_trade.exit_reason == "profit_target", (
        f"Expected exit_reason='profit_target', got '{exit_trade.exit_reason}'"
    )


def test_exit_reason_stop_loss(setup_trading):
    """Verify exit_reason STOP_LOSS is stored in Trade record."""
    engine = setup_trading

    # Create a position
    order_result = asyncio.run(
        engine.place_order(
            symbol="ETHUSDT",
            side="BUY",
            quantity=1.0,
            current_price=3000.0,
        )
    )
    assert order_result.get("status") == "FILLED"

    # Execute exit with STOP_LOSS reason
    exit_result = asyncio.run(
        engine.place_order(
            symbol="ETHUSDT",
            side="SELL",
            quantity=1.0,
            current_price=2970.0,  # Down 1%
            exit_reason="stop_loss",  # ← This should be stored
        )
    )
    assert exit_result.get("status") == "FILLED"

    # Verify exit_reason is in the Trade record
    trades = engine.get_trades()
    assert len(trades) >= 2

    exit_trade = trades[-1]
    assert exit_trade.exit_reason == "stop_loss", (
        f"Expected exit_reason='stop_loss', got '{exit_trade.exit_reason}'"
    )


def test_exit_reason_timeout(setup_trading):
    """Verify exit_reason TIME_STOP is stored in Trade record."""
    engine = setup_trading

    # Create a position
    order_result = asyncio.run(
        engine.place_order(
            symbol="BNBUSDT",
            side="BUY",
            quantity=2.0,
            current_price=600.0,
        )
    )
    assert order_result.get("status") == "FILLED"

    # Execute exit with TIME_STOP reason
    exit_result = asyncio.run(
        engine.place_order(
            symbol="BNBUSDT",
            side="SELL",
            quantity=2.0,
            current_price=600.5,
            exit_reason="10-minute timeout",  # ← This should be stored
        )
    )
    assert exit_result.get("status") == "FILLED"

    # Verify exit_reason is in the Trade record
    trades = engine.get_trades()
    assert len(trades) >= 2

    exit_trade = trades[-1]
    assert exit_trade.exit_reason == "10-minute timeout", (
        f"Expected exit_reason='10-minute timeout', got '{exit_trade.exit_reason}'"
    )


def test_exit_signal_enum_value_conversion():
    """Verify ExitReason enum values convert correctly to strings."""
    assert ExitReason.PROFIT_TARGET.value == "profit_target"
    assert ExitReason.STOP_LOSS.value == "stop_loss"
    assert ExitReason.TRAILING_STOP.value == "trailing_stop"
    assert ExitReason.TIME_STOP.value == "time_stop"

    # Verify signal reason is stored
    signal = ExitSignal(
        symbol="BTCUSDT",
        quantity=0.5,
        reason=ExitReason.PROFIT_TARGET,
        exit_price=51000.0,
    )
    assert signal.reason.value == "profit_target"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
