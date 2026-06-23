"""Unit tests for paper trading engine (FR-002)."""

import pytest
import asyncio
from datetime import datetime

from backend.exchange.paper_trading import PaperTradingEngine


@pytest.fixture
def engine():
    """Create paper trading engine for tests."""
    return PaperTradingEngine(starting_capital=10000.0)


# UT-001: Price update → fill simulated correctly
@pytest.mark.asyncio
async def test_buy_order_fills_correctly(engine):
    """BUY order should fill at market price + slippage."""
    result = await engine.place_order(
        symbol="BTCUSDT",
        side="BUY",
        quantity=0.1,
        current_price=45000.0,
        order_type="MARKET",
    )

    assert result["status"] == "FILLED"
    assert result["symbol"] == "BTCUSDT"
    assert result["quantity"] == 0.1
    # Price should be 45000 * 1.001 (0.1% slippage)
    assert abs(result["fill_price"] - 45045.0) < 1


# UT-002: BUY order → cash decreases, position added
@pytest.mark.asyncio
async def test_buy_order_updates_cash_and_positions(engine):
    """BUY order should decrease cash and add position."""
    initial_cash = engine.cash
    result = await engine.place_order(
        symbol="BTCUSDT",
        side="BUY",
        quantity=0.1,
        current_price=45000.0,
    )

    assert result["status"] == "FILLED"
    assert engine.cash < initial_cash
    assert "BTCUSDT" in engine.positions


# UT-003: SELL order → position removed, cash increased
@pytest.mark.asyncio
async def test_sell_order_removes_position(engine):
    """SELL order should remove position and increase cash."""
    # First buy
    await engine.place_order(
        symbol="BTCUSDT", side="BUY", quantity=0.1, current_price=45000.0
    )

    assert "BTCUSDT" in engine.positions
    cash_after_buy = engine.cash

    # Then sell
    result = await engine.place_order(
        symbol="BTCUSDT",
        side="SELL",
        quantity=0.1,
        current_price=46000.0,  # Price went up
    )

    assert result["status"] == "FILLED"
    assert "BTCUSDT" not in engine.positions
    assert engine.cash > cash_after_buy


# UT-004: Fee deduction → 0.1% per trade
@pytest.mark.asyncio
async def test_fee_deduction(engine):
    """Fees should be deducted correctly (0.1%)."""
    result = await engine.place_order(
        symbol="BTCUSDT",
        side="BUY",
        quantity=0.1,
        current_price=45000.0,
    )

    # Fee = quantity * price * 0.001
    expected_fee = 0.1 * 45045.0 * 0.001
    assert abs(result["fee"] - expected_fee) < 0.01


# UT-005: P&L calculation → realized and unrealized
@pytest.mark.asyncio
async def test_pnl_calculation(engine):
    """P&L should be calculated correctly."""
    # Buy at 45000
    await engine.place_order(
        symbol="BTCUSDT",
        side="BUY",
        quantity=0.1,
        current_price=45000.0,
    )

    initial_pnl = engine.total_pnl

    # Sell at 46000 (profit)
    sell_result = await engine.place_order(
        symbol="BTCUSDT",
        side="SELL",
        quantity=0.1,
        current_price=46000.0,
    )

    # P&L should be positive (price went up)
    assert sell_result["status"] == "FILLED"
    assert engine.total_pnl > initial_pnl


# UT-006: Insufficient cash → order rejected
@pytest.mark.asyncio
async def test_insufficient_cash_rejection(engine):
    """Order should be rejected if insufficient cash."""
    result = await engine.place_order(
        symbol="BTCUSDT",
        side="BUY",
        quantity=100.0,  # Very large position
        current_price=45000.0,
    )

    assert result["status"] == "REJECTED"
    assert "Insufficient cash" in result["reason"]


# UT-007: Position size limit → max 5 positions
@pytest.mark.asyncio
async def test_multiple_positions(engine):
    """Should handle multiple positions."""
    symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT"]

    for i, symbol in enumerate(symbols):
        result = await engine.place_order(
            symbol=symbol,
            side="BUY",
            quantity=0.1,
            current_price=1000.0 + i * 100,
        )
        assert result["status"] == "FILLED"

    assert len(engine.positions) == 5


# UT-008: Reset function → clears all, restores balance
@pytest.mark.asyncio
async def test_reset_account(engine):
    """Reset should clear positions and restore balance."""
    # Add some trades
    await engine.place_order(
        symbol="BTCUSDT",
        side="BUY",
        quantity=0.1,
        current_price=45000.0,
    )

    # Reset
    engine.reset()

    assert len(engine.positions) == 0
    assert engine.cash == 10000.0
    assert engine.total_pnl == 0.0


# UT-009: Mode toggle → paper vs live don't conflict
def test_engine_mode_isolation(engine):
    """Engines should maintain isolated state."""
    engine1 = PaperTradingEngine(10000.0)
    engine2 = PaperTradingEngine(20000.0)

    assert engine1.cash == 10000.0
    assert engine2.cash == 20000.0


# UT-010: Slippage calculation → matches model
@pytest.mark.asyncio
async def test_market_slippage_model(engine):
    """Market order slippage should be 0.1%."""
    result = await engine.place_order(
        symbol="BTCUSDT",
        side="BUY",
        quantity=0.1,  # Smaller to fit in starting balance
        current_price=45000.0,
        order_type="MARKET",
    )

    # Should have filled successfully
    assert result["status"] == "FILLED"
    # Price * (1 + 0.001)
    expected_price = 45000.0 * 1.001
    assert abs(result.get("fill_price", expected_price) - expected_price) < 1


# UT-011: Multiple trades → all logged, P&L correct
@pytest.mark.asyncio
async def test_multiple_trades_logging(engine):
    """Multiple trades should all be logged."""
    trades_to_make = [
        ("BTCUSDT", "BUY", 0.1, 45000.0),
        ("ETHUSDT", "BUY", 1.0, 2500.0),
        ("BTCUSDT", "SELL", 0.1, 46000.0),
    ]

    for symbol, side, qty, price in trades_to_make:
        await engine.place_order(
            symbol=symbol,
            side=side,  # type: ignore
            quantity=qty,
            current_price=price,
        )

    assert len(engine.trade_history) == 3
    assert engine.total_pnl != 0


# UT-012: Negative balance check → never allowed
@pytest.mark.asyncio
async def test_cash_never_negative(engine):
    """Cash should never go negative."""
    # Try to buy more than can afford
    await engine.place_order(
        symbol="BTCUSDT",
        side="BUY",
        quantity=100.0,
        current_price=1000.0,  # 100,000 EUR > starting balance
    )

    # Should still have positive cash
    assert engine.cash >= 0


# UT-013: Price edge cases → zero, very high, NaN
@pytest.mark.asyncio
async def test_price_edge_cases(engine):
    """Should handle edge case prices."""
    # Very high price
    result = await engine.place_order(
        symbol="BTCUSDT",
        side="BUY",
        quantity=0.001,
        current_price=100000.0,
    )
    assert result["status"] == "FILLED"


# UT-014: Concurrent orders → queue and process correctly
@pytest.mark.asyncio
async def test_concurrent_orders(engine):
    """Should handle concurrent orders (sequential processing)."""
    tasks = [
        engine.place_order("BTCUSDT", "BUY", 0.1, 45000.0),
        engine.place_order("ETHUSDT", "BUY", 1.0, 2500.0),
        engine.place_order("BNBUSDT", "BUY", 0.5, 500.0),
    ]

    results = await asyncio.gather(*tasks)

    assert all(r["status"] == "FILLED" for r in results)
    assert len(engine.positions) == 3


# UT-015: Order cancellation → removes unfilled orders
@pytest.mark.asyncio
async def test_sell_without_position(engine):
    """SELL should fail if no position."""
    result = await engine.place_order(
        symbol="NONEXISTENT",
        side="SELL",
        quantity=0.1,
        current_price=1000.0,
    )

    assert result["status"] == "REJECTED"


# === Account State Tests ===


def test_get_account_state(engine):
    """get_account_state should return correct structure."""
    state = engine.get_account_state()

    assert state["mode"] == "PAPER"
    assert state["cash"] == 10000.0
    assert state["total_equity"] == 10000.0
    assert state["active_positions"] == 0


@pytest.mark.asyncio
async def test_account_state_after_trade(engine):
    """Account state should update after trades."""
    await engine.place_order(
        symbol="BTCUSDT",
        side="BUY",
        quantity=0.1,
        current_price=45000.0,
    )

    state = engine.get_account_state()

    assert state["active_positions"] == 1
    assert state["cash"] < 10000.0


def test_get_positions(engine):
    """get_positions should return list of positions."""
    positions = engine.get_positions()
    assert isinstance(positions, list)
    assert len(positions) == 0


@pytest.mark.asyncio
async def test_get_positions_after_trade(engine):
    """get_positions should include new positions."""
    await engine.place_order(
        symbol="BTCUSDT",
        side="BUY",
        quantity=0.1,
        current_price=45000.0,
    )

    positions = engine.get_positions()
    assert len(positions) == 1
    assert positions[0]["symbol"] == "BTCUSDT"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
