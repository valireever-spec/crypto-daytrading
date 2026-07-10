"""
End-to-End Test: Entry/Exit Logging Through Production Code Path

This test verifies that entry_reason and exit_reason are logged correctly
when trades flow through the COMPLETE production application logic.

NOT a database-layer test - verifies FULL CODE PATH from signal to database.
"""

import asyncio
import pytest
import sqlite3
from datetime import datetime, timezone, timedelta
from typing import List, Dict


@pytest.mark.asyncio
async def test_entry_reason_logged_in_production_flow():
    """
    Test that entry_reason is correctly saved when:
    1. Entry signal is generated
    2. place_order is called
    3. Trade is created
    4. insert_trade saves to database

    This is NOT a direct database insert test.
    This is a FULL production code path test.
    """
    import sys
    sys.path.insert(0, '/home/vali/projects/crypto-daytrading')

    from backend.exchange.paper_trading import get_paper_trading
    from backend.core.database import get_database

    # Setup
    engine = get_paper_trading()
    db = get_database()
    initial_count = 0

    try:
        # Count initial trades
        conn = sqlite3.connect('/home/vali/projects/crypto-daytrading/data/trading.db')
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM trades WHERE entry_reason IS NOT NULL")
        initial_count = cursor.fetchone()[0]
        conn.close()

        # Simulate entry through FULL production path
        # (Don't use direct INSERT - let the code path handle it)
        current_price = 64000.0
        test_entry_reason = f"TEST_E2E: {datetime.now(timezone.utc).isoformat()}"

        result = await engine.place_order(
            symbol='BTCUSDT',
            side='BUY',
            quantity=0.001,
            current_price=current_price,
            entry_reason=test_entry_reason  # Pass through production path
        )

        # Verify result
        assert result['status'] == 'FILLED', f"Order failed: {result}"

        # Check database for the entry_reason
        conn = sqlite3.connect('/home/vali/projects/crypto-daytrading/data/trading.db')
        cursor = conn.cursor()

        cursor.execute("""
            SELECT entry_reason, exit_reason
            FROM trades
            WHERE order_id = ? AND side = 'BUY'
        """, (result['order_id'],))

        row = cursor.fetchone()
        conn.close()

        assert row is not None, f"Trade not found in database for order {result['order_id']}"

        entry_reason, exit_reason = row

        # THE CRITICAL CHECK: Does production save entry_reason?
        assert entry_reason is not None, \
            f"🔴 FAILURE: entry_reason is NULL in database despite being passed to place_order\n" \
            f"Expected: {test_entry_reason}\n" \
            f"Actual: NULL\n" \
            f"This proves the production code path is NOT saving entry_reason correctly"

        assert test_entry_reason in entry_reason, \
            f"entry_reason mismatch: expected substring '{test_entry_reason}' in '{entry_reason}'"

        print(f"✅ PASS: Entry logging works in production flow")
        print(f"   entry_reason: {entry_reason[:80]}")

    except AssertionError as e:
        print(f"❌ FAIL: {e}")
        raise


@pytest.mark.asyncio
async def test_exit_reason_logged_in_production_flow():
    """
    Test that exit_reason is correctly saved when:
    1. Position is exited via place_order
    2. Trade is created
    3. insert_trade saves to database

    Must verify all 3 exit types:
    - Profit target
    - Stop loss
    - Timeout
    """
    import sys
    sys.path.insert(0, '/home/vali/projects/crypto-daytrading')

    from backend.exchange.paper_trading import get_paper_trading
    import sqlite3

    engine = get_paper_trading()

    try:
        # Setup: Create a position first
        entry_price = 64000.0
        current_price = 64000.0

        buy_result = await engine.place_order(
            symbol='BTCUSDT',
            side='BUY',
            quantity=0.001,
            current_price=current_price,
            entry_reason="TEST_E2E_EXIT"
        )

        assert buy_result['status'] == 'FILLED'

        # Now sell to test exit_reason
        test_exit_reason = "TEST_E2E_EXIT_PROFIT"

        sell_result = await engine.place_order(
            symbol='BTCUSDT',
            side='SELL',
            quantity=0.001,
            current_price=current_price,
            exit_reason=test_exit_reason
        )

        assert sell_result['status'] == 'FILLED'

        # Check database
        conn = sqlite3.connect('/home/vali/projects/crypto-daytrading/data/trading.db')
        cursor = conn.cursor()

        cursor.execute("""
            SELECT exit_reason
            FROM trades
            WHERE order_id = ? AND side = 'SELL'
        """, (sell_result['order_id'],))

        row = cursor.fetchone()
        conn.close()

        assert row is not None, "Sell trade not found in database"

        exit_reason = row[0]

        # THE CRITICAL CHECK: Does production save exit_reason?
        assert exit_reason is not None, \
            f"🔴 FAILURE: exit_reason is NULL in database despite being passed to place_order\n" \
            f"Expected: {test_exit_reason}\n" \
            f"Actual: NULL"

        assert test_exit_reason in exit_reason, \
            f"exit_reason mismatch: expected substring '{test_exit_reason}' in '{exit_reason}'"

        print(f"✅ PASS: Exit logging works in production flow")
        print(f"   exit_reason: {exit_reason}")

    except AssertionError as e:
        print(f"❌ FAIL: {e}")
        raise


if __name__ == '__main__':
    print("Running E2E logging tests...")
    print("This verifies entry/exit reasons are saved in PRODUCTION, not just in tests")
    pytest.main([__file__, '-v'])
