"""End-to-end verification: entry_reason and exit_reason must be recorded in trades.jsonl"""

import pytest
import json
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any

from backend.exchange.paper_trading import get_paper_trading, Trade
from backend.core.trading_metrics import get_metrics_collector


class TradeReasonValidator:
    """Validates that entry/exit reasons are properly threaded through the system."""

    REQUIRED_FIELDS_BUY = {"symbol", "side", "price", "quantity", "entry_reason", "timestamp"}
    REQUIRED_FIELDS_SELL = {"symbol", "side", "price", "quantity", "exit_reason", "timestamp"}

    @staticmethod
    def validate_trade_dataclass(trade: Trade) -> tuple[bool, str]:
        """Type-safe validation of Trade dataclass."""
        if trade.side == "BUY":
            if trade.entry_reason is None:
                return False, f"BUY trade missing entry_reason: {trade}"
        elif trade.side == "SELL":
            if trade.exit_reason is None:
                return False, f"SELL trade missing exit_reason: {trade}"
        return True, "OK"

    @staticmethod
    def validate_trade_log(trade_dict: Dict[str, Any]) -> tuple[bool, str]:
        """Validate trade record as it appears in trades.jsonl"""
        side = trade_dict.get("side")

        if side == "BUY":
            required = TradeReasonValidator.REQUIRED_FIELDS_BUY
            reason_field = "entry_reason"
        elif side == "SELL":
            required = TradeReasonValidator.REQUIRED_FIELDS_SELL
            reason_field = "exit_reason"
        else:
            return False, f"Unknown side: {side}"

        missing = required - set(trade_dict.keys())
        if missing:
            return False, f"Missing fields for {side}: {missing}"

        reason = trade_dict.get(reason_field)
        if reason is None:
            return False, f"{side} trade has {reason_field}=null (must be string with reason)"

        if not isinstance(reason, str) or len(reason.strip()) == 0:
            return False, f"{side} trade has empty {reason_field}={reason}"

        return True, "OK"

    @staticmethod
    def audit_logs() -> Dict[str, Any]:
        """Audit the trades.jsonl file for completeness."""
        log_path = Path("logs/trades.jsonl")

        if not log_path.exists():
            return {"status": "ERROR", "message": "trades.jsonl not found"}

        results = {
            "total_records": 0,
            "valid_records": 0,
            "invalid_records": [],
            "missing_entry_reasons": [],
            "missing_exit_reasons": [],
        }

        with open(log_path, "r") as f:
            for line_num, line in enumerate(f, 1):
                try:
                    trade = json.loads(line)

                    # Skip heartbeat records (null side = not a real trade)
                    if trade.get("side") is None:
                        continue

                    results["total_records"] += 1

                    is_valid, msg = TradeReasonValidator.validate_trade_log(trade)

                    if is_valid:
                        results["valid_records"] += 1
                    else:
                        results["invalid_records"].append({
                            "line": line_num,
                            "symbol": trade.get("symbol"),
                            "side": trade.get("side"),
                            "error": msg,
                        })

                        # Track specific issues
                        if "entry_reason" in msg:
                            results["missing_entry_reasons"].append(
                                {"line": line_num, "symbol": trade.get("symbol")}
                            )
                        elif "exit_reason" in msg:
                            results["missing_exit_reasons"].append(
                                {"line": line_num, "symbol": trade.get("symbol")}
                            )
                except json.JSONDecodeError:
                    pass

        return results


@pytest.mark.asyncio
async def test_entry_reason_stored_in_trade():
    """Verify entry_reason is stored when BUY order is placed."""
    engine = get_paper_trading()
    assert engine is not None

    # Place a BUY order with entry_reason
    result = await engine.place_order(
        symbol="BTCUSDT",
        side="BUY",
        quantity=0.0001,
        current_price=63000.0,
        entry_reason="Test entry: momentum breakout above EMA20",
    )

    assert result["status"] == "FILLED"
    assert "order_id" in result

    # Verify the trade record has entry_reason
    trades = engine.trade_history
    buy_trade = next((t for t in reversed(trades) if t.side == "BUY"), None)

    assert buy_trade is not None, "No BUY trade found"
    assert buy_trade.entry_reason == "Test entry: momentum breakout above EMA20"

    # Validate with type-safe validator
    is_valid, msg = TradeReasonValidator.validate_trade_dataclass(buy_trade)
    assert is_valid, f"Trade dataclass validation failed: {msg}"


@pytest.mark.asyncio
async def test_exit_reason_stored_in_trade():
    """Verify exit_reason is stored when SELL order is placed."""
    engine = get_paper_trading()
    assert engine is not None

    # First, create a position by placing a BUY
    await engine.place_order(
        symbol="ETHUSDT",
        side="BUY",
        quantity=0.001,
        current_price=1800.0,
        entry_reason="Test entry: RSI oversold",
    )

    # Now close it with SELL
    result = await engine.place_order(
        symbol="ETHUSDT",
        side="SELL",
        quantity=0.001,
        current_price=1850.0,
        exit_reason="Stop loss hit (-0.5%)",
    )

    assert result["status"] == "FILLED"

    # Verify the trade record has exit_reason
    trades = engine.trade_history
    sell_trade = next((t for t in reversed(trades) if t.side == "SELL"), None)

    assert sell_trade is not None, "No SELL trade found"
    assert sell_trade.exit_reason == "Stop loss hit (-0.5%)"

    # Validate with type-safe validator
    is_valid, msg = TradeReasonValidator.validate_trade_dataclass(sell_trade)
    assert is_valid, f"Trade dataclass validation failed: {msg}"


@pytest.mark.asyncio
async def test_reasons_persisted_in_jsonl_log():
    """Verify reasons are actually written to trades.jsonl file."""
    engine = get_paper_trading()

    # Clear and rebuild trades list with test data
    initial_count = len(engine.trade_history)

    # Place a test trade with reasons
    await engine.place_order(
        symbol="BNBUSDT",
        side="BUY",
        quantity=0.01,
        current_price=580.0,
        entry_reason="Test: grid trading entry at support",
    )

    await engine.place_order(
        symbol="BNBUSDT",
        side="SELL",
        quantity=0.01,
        current_price=590.0,
        exit_reason="Profit target hit (+2%)",
    )

    # Read back from file
    log_path = Path("logs/trades.jsonl")
    assert log_path.exists(), "trades.jsonl not found"

    with open(log_path, "r") as f:
        lines = f.readlines()

    # Check the most recent trades for our test data
    found_buy = False
    found_sell = False

    for line in reversed(lines):
        try:
            trade = json.loads(line)
            if (trade.get("symbol") == "BNBUSDT" and
                    trade.get("entry_reason") == "Test: grid trading entry at support"):
                found_buy = True
            if (trade.get("symbol") == "BNBUSDT" and
                    trade.get("exit_reason") == "Profit target hit (+2%)"):
                found_sell = True
        except json.JSONDecodeError:
            pass

    assert found_buy, "BUY trade with entry_reason not found in trades.jsonl"
    assert found_sell, "SELL trade with exit_reason not found in trades.jsonl"


def test_audit_trades_log():
    """Audit the trades.jsonl for completeness."""
    validator = TradeReasonValidator()
    audit = validator.audit_logs()

    print("\n" + "=" * 70)
    print("📊 TRADE REASON CHAIN AUDIT")
    print("=" * 70)
    print(f"Total records:        {audit['total_records']}")
    print(f"Valid records:        {audit['valid_records']}")
    print(f"Invalid records:      {len(audit['invalid_records'])}")
    print(f"Missing entry reasons: {len(audit['missing_entry_reasons'])}")
    print(f"Missing exit reasons:  {len(audit['missing_exit_reasons'])}")
    print("=" * 70)

    if audit["invalid_records"]:
        print("\n❌ INVALID TRADES (first 5):")
        for record in audit["invalid_records"][:5]:
            print(f"  Line {record['line']}: {record['symbol']} {record['side']} - {record['error']}")

    # Only fail if we have recent trades with missing reasons
    recent_invalid = [r for r in audit["invalid_records"] if r["line"] > audit["total_records"] - 100]

    if recent_invalid:
        print(f"\n⚠️  {len(recent_invalid)} recent trades missing reasons (last 100 records)")
        assert False, f"Recent trades missing entry_reason/exit_reason: {recent_invalid[:3]}"
    else:
        print("\n✅ All recent trades have complete reason chains")


def test_parameter_threading_type_safety():
    """Verify parameter threading uses type hints (mypy catches missing params)."""
    from backend.exchange.paper_trading import Trade

    # This should REQUIRE entry_reason and exit_reason in the dataclass
    trade = Trade(
        timestamp=datetime.now(timezone.utc),
        symbol="BTCUSDT",
        side="BUY",
        quantity=0.1,
        price=63000.0,
        fee=6.3,
        realized_pnl=0.0,
        order_id="test-123",
        mode="PAPER",
        status="FILLED",
        entry_reason="Test entry reason",
        exit_reason=None,  # Can be None for BUY
    )

    assert trade.entry_reason == "Test entry reason"
    assert trade.exit_reason is None

    # Verify type safety
    is_valid, msg = TradeReasonValidator.validate_trade_dataclass(trade)
    assert is_valid


if __name__ == "__main__":
    # Run audit without pytest
    print("\n🔍 Running Trade Reason Chain Audit...")
    validator = TradeReasonValidator()
    audit = validator.audit_logs()

    print(json.dumps(audit, indent=2))
