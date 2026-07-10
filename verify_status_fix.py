#!/usr/bin/env python3
"""Verify that BUY trades are marked CLOSED when corresponding SELL is inserted."""

import sqlite3
from datetime import datetime, timezone
from backend.core.database import TradingDatabase, get_shared_connection

db = TradingDatabase("data/trading.db")

# Find the most recent BUY→SELL pair
conn = sqlite3.connect("data/trading.db")
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

cursor.execute("""
    SELECT
        id, symbol, side, status, price, quantity, trade_time, entry_reason, exit_reason
    FROM trades
    WHERE symbol = 'BTCUSDT'
    ORDER BY trade_time DESC
    LIMIT 4
""")

trades = cursor.fetchall()
conn.close()

print("\n" + "="*100)
print("VERIFICATION: BUY→SELL Status Update")
print("="*100 + "\n")

if len(trades) < 2:
    print("❌ Not enough trades to verify (need at least 2)")
else:
    # Show the most recent trades
    for i, trade in enumerate(trades):
        status_symbol = "✅" if (trade['side'] == 'SELL' or trade['status'] == 'CLOSED') else "❌" if trade['status'] == 'OPEN' else "⚠️"
        print(f"{status_symbol} Trade #{trade['id']:4d} | {trade['side']:4s} @ €{trade['price']:8.2f} | Status: {trade['status']:6s} | {trade['trade_time']}")

    # Check if most recent SELL has a corresponding CLOSED BUY before it
    sell_trade = None
    buy_trade = None

    for trade in trades:
        if trade['side'] == 'SELL' and sell_trade is None:
            sell_trade = trade
        elif trade['side'] == 'BUY' and buy_trade is None and sell_trade is not None:
            buy_trade = trade
            break

    print("\n" + "-"*100)

    if sell_trade and buy_trade:
        print(f"\nMost recent SELL: #{sell_trade['id']} (€{sell_trade['price']:.2f}) - {sell_trade['trade_time']}")
        print(f"Corresponding BUY: #{buy_trade['id']} (€{buy_trade['price']:.2f}) - {buy_trade['trade_time']}")

        if buy_trade['status'] == 'CLOSED':
            print(f"\n✅ BUG FIX WORKING: BUY trade #{buy_trade['id']} is marked as CLOSED ✅")
        else:
            print(f"\n❌ BUG FIX NOT WORKING: BUY trade #{buy_trade['id']} still shows status='{buy_trade['status']}'")

        print(f"\nEntry reason: {buy_trade['entry_reason'][:60] if buy_trade['entry_reason'] else 'NULL'}")
        print(f"Exit reason:  {sell_trade['exit_reason'][:60] if sell_trade['exit_reason'] else 'NULL'}")
    else:
        print("❌ Could not find recent BUY→SELL pair")

print("\n" + "="*100 + "\n")
