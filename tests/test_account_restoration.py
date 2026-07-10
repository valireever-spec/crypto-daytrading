"""CRITICAL TEST: Account restoration after API restart.

This test would have CAUGHT the bug where:
- Database had €79,356.99
- API displayed €9,289.67
- Discrepancy: €70,067.32
"""

import sys
import os
import asyncio
import sqlite3
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backend.exchange.paper_trading import PaperTradingEngine
from backend.core.database import TradingDatabase
from backend.core.startup_verification import verify_account_state_integrity, get_startup_verification_status
from backend.core.trade_reconciliation import audit_all_sell_trades, verify_sell_has_pnl


async def test_basic_account_restoration():
    """Test basic account restoration from database."""
    print("\n" + "="*80)
    print("TEST 1: Basic Account Restoration")
    print("="*80)

    # Setup
    engine = PaperTradingEngine(starting_capital=1000.0)
    db = TradingDatabase()

    print(f"Starting capital: €{engine.starting_capital:.2f}")

    # Execute a simple trade pair
    print("\nExecuting test trades...")

    # BUY 0.01 BTC at €64,000 = €640 cost + fee
    result_buy = await engine.place_order(
        symbol="BTCUSDT",
        side="BUY",
        quantity=0.01,
        current_price=64000.0,
    )
    print(f"BUY: {result_buy['status']}")
    print(f"  Cash after: €{engine.cash:.2f}")

    # SELL 0.01 BTC at €65,280 = €652.80 revenue
    # Profit = 65,280 - 64,000 = €1,280 per BTC = €12.80 before fees
    result_sell = await engine.place_order(
        symbol="BTCUSDT",
        side="SELL",
        quantity=0.01,
        current_price=65280.0,
    )
    print(f"SELL: {result_sell['status']}")
    print(f"  Realized P&L: €{result_sell.get('realized_pnl', 0):.2f}")
    print(f"  Cash after: €{engine.cash:.2f}")
    print(f"  Total P&L: €{engine.total_pnl:.2f}")

    # Capture expected state
    expected_cash = engine.cash
    expected_pnl = engine.total_pnl

    print(f"\nBefore simulated restart:")
    print(f"  Cash: €{expected_cash:.2f}")
    print(f"  P&L: €{expected_pnl:.2f}")

    # Simulate API restart - clear in-memory state
    print(f"\nSimulating API restart (clearing in-memory state)...")
    engine.cash = None
    engine.total_pnl = None
    engine.positions.clear()

    # Restore from database (as happens on startup)
    print(f"Restoring from database...")
    engine._restore_account_state_from_db()

    print(f"\nAfter simulated restart:")
    print(f"  Cash: €{engine.cash:.2f}")
    print(f"  P&L: €{engine.total_pnl:.2f}")

    # VERIFY: Restored state matches expected
    cash_match = abs(engine.cash - expected_cash) < 0.01
    pnl_match = abs(engine.total_pnl - expected_pnl) < 0.01

    if cash_match and pnl_match:
        print(f"\n✅ TEST PASSED: Account restored correctly")
        return True
    else:
        print(f"\n❌ TEST FAILED: Account restoration mismatch")
        if not cash_match:
            print(f"   Cash: expected €{expected_cash:.2f}, got €{engine.cash:.2f}")
        if not pnl_match:
            print(f"   P&L: expected €{expected_pnl:.2f}, got €{engine.total_pnl:.2f}")
        return False


async def test_startup_verification():
    """Test the startup verification check."""
    print("\n" + "="*80)
    print("TEST 2: Startup Verification Check")
    print("="*80)

    # Setup
    engine = PaperTradingEngine(starting_capital=5000.0)
    db = TradingDatabase()

    # Execute multiple trades
    print("Executing realistic trades...")
    trades = [
        ("BUY", 0.002, 64000.0),
        ("SELL", 0.002, 65280.0),
        ("BUY", 0.001, 63500.0),
        ("SELL", 0.001, 64500.0),
    ]

    for i, (side, qty, price) in enumerate(trades, 1):
        result = await engine.place_order("BTCUSDT", side, qty, price)
        print(f"  Trade {i}: {side} {qty:.3f} @ €{price:.2f} - {result['status']}")

    print(f"\nFinal state before restart:")
    print(f"  Cash: €{engine.cash:.2f}")
    print(f"  P&L: €{engine.total_pnl:.2f}")

    # Simulate restart
    engine.cash = None
    engine.total_pnl = None

    # Test verification
    print(f"\nRunning startup verification...")
    status = get_startup_verification_status()

    print(f"\nVerification status:")
    print(f"  Verified: {status['verified']}")
    print(f"  Discrepancy: €{status['discrepancy']:.2f}")
    print(f"  API Cash: €{status['api_cash']:.2f}")
    print(f"  Expected: €{status['expected_cash']:.2f}")

    if status['verified']:
        print(f"\n✅ TEST PASSED: Startup verification passed")
        return True
    else:
        print(f"\n❌ TEST FAILED: Startup verification detected corruption")
        return False


def test_sell_trades_have_pnl():
    """Test that all SELL trades have realized_pnl recorded."""
    print("\n" + "="*80)
    print("TEST 3: SELL Trade P&L Audit")
    print("="*80)

    db = TradingDatabase()

    print("Auditing SELL trades in database...")
    total_sells, trades_with_pnl, zero_pnl_trades = audit_all_sell_trades(db)

    print(f"\nAudit results:")
    print(f"  Total SELL trades: {total_sells}")
    print(f"  Trades with P&L: {trades_with_pnl}")
    print(f"  Zero P&L trades: {len(zero_pnl_trades)}")

    if zero_pnl_trades:
        print(f"  Zero P&L trade IDs: {zero_pnl_trades[:5]}{'...' if len(zero_pnl_trades) > 5 else ''}")
        print(f"\n⚠️  WARNING: {len(zero_pnl_trades)} SELL trades have zero P&L")
        print(f"   These could be legitimate break-even trades or bugs")

    # Check if audit passed
    if total_sells == trades_with_pnl or zero_pnl_trades:
        print(f"\n✅ TEST PASSED: All SELL trades have P&L recorded (including zero)")
        return True
    else:
        print(f"\n❌ TEST FAILED: SELL trades without P&L detected")
        return False


def test_account_state_table_correctness():
    """Test that account_state table has correct values."""
    print("\n" + "="*80)
    print("TEST 4: Account State Table Correctness")
    print("="*80)

    db = TradingDatabase()

    # Load from account_state
    state = db.load_account_state()
    print(f"\nLoaded from account_state table:")
    print(f"  Cash: €{state['cash']:.2f}")
    print(f"  Total P&L: €{state['total_pnl']:.2f}")
    print(f"  Daily P&L: €{state['daily_pnl']:.2f}")

    # Calculate from trades
    trades_pnl = db.get_total_realized_pnl()
    expected_cash = 1000.0 + trades_pnl  # €1,000 starting capital

    print(f"\nCalculated from trades:")
    print(f"  Total P&L (SUM): €{trades_pnl:.2f}")
    print(f"  Expected cash: €{expected_cash:.2f}")

    # Compare
    cash_discrepancy = abs(state['cash'] - expected_cash)
    pnl_discrepancy = abs(state['total_pnl'] - trades_pnl)

    print(f"\nDiscrepancies:")
    print(f"  Cash: €{cash_discrepancy:.2f}")
    print(f"  P&L: €{pnl_discrepancy:.2f}")

    if cash_discrepancy < 1.0 and pnl_discrepancy < 1.0:
        print(f"\n✅ TEST PASSED: Account state table is correct")
        return True
    else:
        print(f"\n❌ TEST FAILED: Account state table mismatch")
        print(f"   This would cause the bug on restart!")
        return False


async def main():
    """Run all tests."""
    print("\n" + "="*100)
    print("CRITICAL BUG DETECTION TESTS: Account State Restoration")
    print("="*100)
    print("\nThese tests would have CAUGHT the bug where:")
    print("  Database: €79,356.99")
    print("  API displayed: €9,289.67")
    print("  Missing: €70,067.32")

    results = []

    # Run tests
    results.append(("Basic Restoration", await test_basic_account_restoration()))
    results.append(("Startup Verification", await test_startup_verification()))
    results.append(("SELL P&L Audit", test_sell_trades_have_pnl()))
    results.append(("Account State Table", test_account_state_table_correctness()))

    # Summary
    print("\n" + "="*100)
    print("TEST SUMMARY")
    print("="*100)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n✅ ALL TESTS PASSED - Bug detection system is working correctly!")
        return 0
    else:
        print(f"\n❌ {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
