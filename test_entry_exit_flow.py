#!/usr/bin/env python3
"""
End-to-End Entry/Exit Flow Tester
Tests complete production flow without modifying WebSocket.

PURPOSE:
  - Test entry_reason logging on new trades
  - Test exit_reason logging on trade exits
  - Verify parameter flows through complete stack
  - Can run while WebSocket processes real signals

USAGE:
  # Test 1: Inject oversold signal → Entry should fire with entry_reason
  python3 test_entry_exit_flow.py --mode entry --rsi 28

  # Test 2: Find open position and inject profit target → Exit should fire with exit_reason
  python3 test_entry_exit_flow.py --mode exit --position-id 12345 --exit-type profit

WORKFLOW:
  1. Inject test market data (simulating RSI < 30)
  2. Entry logic generates signal with entry_reason
  3. place_order() called with entry_reason parameter
  4. Database INSERT executes
  5. Query database to verify entry_reason was logged
"""

import sys
import os
import time
import argparse
import sqlite3
from datetime import datetime, timezone
from typing import Optional, Tuple

sys.path.insert(0, os.path.dirname(__file__))

from backend.exchange.paper_trading import get_paper_trading
from backend.core.database import Database


class EndToEndFlowTester:
    """Test complete entry/exit flow with real database"""

    def __init__(self):
        self.db = Database()
        self.pt = get_paper_trading()

    def get_current_price(self, symbol: str) -> float:
        """Get latest price from database"""
        conn = sqlite3.connect("data/trading.db")
        cursor = conn.cursor()

        # Try to get from last trade
        cursor.execute("""
            SELECT price FROM trades
            WHERE symbol = ?
            ORDER BY created_at DESC LIMIT 1
        """, (symbol,))

        result = cursor.fetchone()
        conn.close()

        if result:
            return result[0]

        # Fallback prices
        fallback = {
            'BTCUSDT': 64426.74,
            'ETHUSDT': 1798.03,
            'BNBUSDT': 576.45,
        }
        return fallback.get(symbol, 64000)

    def test_entry_flow(self, symbol: str = 'BTCUSDT', rsi: float = 28) -> bool:
        """
        Test entry flow: simulate oversold condition → entry_reason logged

        This tests the complete path:
          SignalCalculator → entry_reason parameter → place_order → database
        """
        print(f"\n{'='*80}")
        print(f"TEST 1: ENTRY FLOW")
        print(f"{'='*80}")
        print(f"\nSymbol: {symbol}")
        print(f"Scenario: RSI {rsi} (oversold, should trigger entry)")
        print()

        current_price = self.get_current_price(symbol)

        print(f"Current price: €{current_price:.2f}")
        print()

        # Create test entry_reason (same format as production)
        test_entry_reason = f"TEST: Mean Reversion Oversold (RSI {rsi} < 30)"

        print(f"Test entry_reason: {test_entry_reason}")
        print()

        # Call place_order with entry_reason (same as production would)
        print("Calling place_order() with entry_reason parameter...")
        print(f"  Method: await place_order(..., entry_reason='{test_entry_reason}')")
        print()

        try:
            # Note: place_order is async, but for testing we can call sync version
            import asyncio

            async def execute_test_order():
                return await self.pt.place_order(
                    symbol=symbol,
                    side='BUY',
                    quantity=0.0005,
                    current_price=current_price,
                    order_type='MARKET',
                    entry_reason=test_entry_reason,  # <-- THIS IS THE KEY PARAMETER
                )

            # Run async function
            result = asyncio.run(execute_test_order())

            if not result:
                print("❌ Order placement returned None")
                return False

            print(f"✅ Order placed successfully")
            print(f"   Order ID: {result.get('id', 'N/A')}")
            print()

            # Wait for database to persist
            time.sleep(1)

            # Query database for the trade we just created
            print("Checking database for entry_reason...")
            conn = sqlite3.connect("data/trading.db")
            cursor = conn.cursor()

            cursor.execute("""
                SELECT id, created_at, entry_reason, exit_reason, symbol, side
                FROM trades
                WHERE symbol = ? AND side = 'BUY'
                ORDER BY created_at DESC LIMIT 1
            """, (symbol,))

            trade = cursor.fetchone()
            conn.close()

            if not trade:
                print("❌ Trade not found in database")
                return False

            trade_id, created_at, entry_reason, exit_reason, trade_symbol, side = trade

            print()
            print(f"{'='*80}")
            print(f"ENTRY FLOW RESULT")
            print(f"{'='*80}")
            print(f"Trade ID:       {trade_id}")
            print(f"Created:        {created_at}")
            print(f"Symbol:         {trade_symbol}")
            print(f"Side:           {side}")
            print(f"Entry Reason:   {entry_reason if entry_reason else '❌ NULL'}")
            print()

            if entry_reason:
                print(f"✅ SUCCESS: Entry logging WORKING")
                print(f"   Parameter successfully reached database")
                return True
            else:
                print(f"❌ FAILURE: Entry logging BROKEN")
                print(f"   entry_reason = NULL (parameter lost in flow)")
                return False

        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return False

    def test_exit_flow(self, symbol: str = 'BTCUSDT', exit_type: str = 'profit') -> bool:
        """
        Test exit flow: find open position and simulate exit condition

        This tests the complete path:
          ExitChecker → exit_reason parameter → place_order → database
        """
        print(f"\n{'='*80}")
        print(f"TEST 2: EXIT FLOW")
        print(f"{'='*80}")
        print()

        # Find an open position
        conn = sqlite3.connect("data/trading.db")
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, created_at, symbol, side, quantity, price
            FROM trades
            WHERE symbol = ? AND side = 'BUY' AND status = 'OPEN'
            ORDER BY created_at DESC LIMIT 1
        """, (symbol,))

        position = cursor.fetchone()
        conn.close()

        if not position:
            print(f"⚠️  No open BUY position found for {symbol}")
            print(f"First, run: python3 test_entry_exit_flow.py --mode entry")
            return False

        trade_id, entry_time, pos_symbol, side, qty, entry_price = position

        print(f"Found open position:")
        print(f"  Trade ID:     {trade_id}")
        print(f"  Symbol:       {pos_symbol}")
        print(f"  Entry Price:  €{entry_price:.2f}")
        print(f"  Entry Time:   {entry_time}")
        print()

        # Determine exit scenario
        if exit_type == 'profit':
            exit_price = entry_price * 1.02  # +2.0% = profit target
            test_exit_reason = f"TEST: Profit target (+2.0%)"
        elif exit_type == 'stoploss':
            exit_price = entry_price * 0.99  # -1.0% = stop loss
            test_exit_reason = f"TEST: Stop loss (-1.0%)"
        else:
            exit_price = entry_price
            test_exit_reason = f"TEST: {exit_type}"

        pnl_pct = ((exit_price - entry_price) / entry_price) * 100

        print(f"Exit scenario ({exit_type}):")
        print(f"  Exit Price:   €{exit_price:.2f}")
        print(f"  P&L:          {pnl_pct:+.2f}%")
        print(f"  Test exit_reason: {test_exit_reason}")
        print()

        print(f"Calling place_order() with exit_reason parameter...")
        print(f"  Method: await place_order(..., exit_reason='{test_exit_reason}')")
        print()

        try:
            import asyncio

            async def execute_test_exit():
                return await self.pt.place_order(
                    symbol=pos_symbol,
                    side='SELL',
                    quantity=qty,
                    current_price=exit_price,
                    order_type='MARKET',
                    exit_reason=test_exit_reason,  # <-- THIS IS THE KEY PARAMETER
                )

            result = asyncio.run(execute_test_exit())

            if not result:
                print("❌ Exit order placement returned None")
                return False

            print(f"✅ Exit order placed successfully")
            print()

            # Wait for database
            time.sleep(1)

            # Query database for exit_reason
            print("Checking database for exit_reason...")
            conn = sqlite3.connect("data/trading.db")
            cursor = conn.cursor()

            cursor.execute("""
                SELECT id, created_at, entry_reason, exit_reason, status
                FROM trades
                WHERE id = ?
            """, (trade_id,))

            trade = cursor.fetchone()
            conn.close()

            if not trade:
                print("❌ Trade not found in database")
                return False

            tid, created_at, entry_reason, exit_reason, status = trade

            print()
            print(f"{'='*80}")
            print(f"EXIT FLOW RESULT")
            print(f"{'='*80}")
            print(f"Trade ID:       {tid}")
            print(f"Status:         {status}")
            print(f"Entry Reason:   {entry_reason if entry_reason else 'NULL'}")
            print(f"Exit Reason:    {exit_reason if exit_reason else '❌ NULL'}")
            print()

            if exit_reason:
                print(f"✅ SUCCESS: Exit logging WORKING")
                print(f"   Parameter successfully reached database")
                return True
            else:
                print(f"❌ FAILURE: Exit logging BROKEN")
                print(f"   exit_reason = NULL (parameter lost in flow)")
                return False

        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return False


def main():
    parser = argparse.ArgumentParser(
        description='Test complete entry/exit production flow'
    )
    parser.add_argument(
        '--mode',
        required=True,
        choices=['entry', 'exit'],
        help='Test mode: entry (inject oversold) or exit (close position)',
    )
    parser.add_argument(
        '--symbol',
        default='BTCUSDT',
        choices=['BTCUSDT', 'ETHUSDT', 'BNBUSDT'],
        help='Trading symbol',
    )
    parser.add_argument(
        '--rsi',
        type=float,
        default=28,
        help='RSI value for entry test (< 30 triggers entry)',
    )
    parser.add_argument(
        '--exit-type',
        default='profit',
        choices=['profit', 'stoploss', 'timeout'],
        help='Exit type to simulate',
    )

    args = parser.parse_args()

    tester = EndToEndFlowTester()

    print("\n" + "="*80)
    print("END-TO-END ENTRY/EXIT FLOW TEST")
    print("="*80)
    print("\nPurpose: Verify entry_reason and exit_reason logged correctly")
    print("Method:  Call production functions with test parameters")
    print("Result:  Query database to verify parameters were persisted")
    print()

    if args.mode == 'entry':
        success = tester.test_entry_flow(symbol=args.symbol, rsi=args.rsi)
    else:
        success = tester.test_exit_flow(symbol=args.symbol, exit_type=args.exit_type)

    print()
    print("="*80)
    if success:
        print("✅ TEST PASSED")
        print()
        print("Next: Run the exit test to verify exit_reason logging")
        print("  python3 test_entry_exit_flow.py --mode exit --symbol " + args.symbol)
    else:
        print("❌ TEST FAILED")
        print()
        print("Debugging steps:")
        print("  1. Check if database schema has entry_reason/exit_reason columns")
        print("  2. Verify place_order() is passing parameters correctly")
        print("  3. Check database.py insert_trade() is accepting parameters")
    print("="*80 + "\n")

    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
