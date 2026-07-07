#!/usr/bin/env python3
"""Fix historical P&L data for all trades in the database.

CRITICAL: This script corrects the entry_fee bug where realized_pnl was missing
the entry fee for BUY orders. All SELL trades need to be recalculated.

Usage:
    python scripts/fix_pnl_historical.py
"""

import sqlite3
import sys
from pathlib import Path
from datetime import datetime

# Find the database
DB_PATH = Path("/home/vali/projects/crypto-daytrading/data/trading.db")
if not DB_PATH.exists():
    print(f"❌ Database not found at {DB_PATH}")
    sys.exit(1)

print(f"📊 Opening database: {DB_PATH}")
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Get schema info
cursor.execute("PRAGMA table_info(trades)")
columns = [row[1] for row in cursor.fetchall()]
print(f"✅ Trades table columns: {columns}")

if 'realized_pnl' not in columns:
    print("❌ realized_pnl column not found in trades table")
    sys.exit(1)

# Step 1: Analyze current data
print("\n📈 Current P&L Analysis:")
cursor.execute("SELECT COUNT(*) FROM trades WHERE side='BUY'")
buy_count = cursor.fetchone()[0]
print(f"  - BUY trades: {buy_count}")

cursor.execute("SELECT COUNT(*) FROM trades WHERE side='SELL'")
sell_count = cursor.fetchone()[0]
print(f"  - SELL trades: {sell_count}")

cursor.execute("SELECT SUM(realized_pnl) FROM trades WHERE side='SELL'")
current_sum = cursor.fetchone()[0] or 0.0
print(f"  - Sum of SELL realized_pnl: €{current_sum:.2f}")

cursor.execute("SELECT SUM(fee) FROM trades WHERE side='BUY'")
total_buy_fees = cursor.fetchone()[0] or 0.0
print(f"  - Total BUY fees: €{total_buy_fees:.2f}")

cursor.execute("SELECT SUM(fee) FROM trades WHERE side='SELL'")
total_sell_fees = cursor.fetchone()[0] or 0.0
print(f"  - Total SELL fees: €{total_sell_fees:.2f}")

# Step 2: Build a map of BUY trades by symbol and trade_time
print("\n🔍 Building BUY fee lookup table...")
cursor.execute("""
    SELECT symbol, trade_time, fee, price, quantity
    FROM trades
    WHERE side='BUY'
    ORDER BY trade_time
""")
buy_trades = {}
for symbol, ts, fee, price, qty in cursor.fetchall():
    if symbol not in buy_trades:
        buy_trades[symbol] = []
    buy_trades[symbol].append({
        'timestamp': ts,
        'fee': fee,
        'price': price,
        'qty': qty
    })
print(f"✅ Loaded {sum(len(v) for v in buy_trades.values())} BUY trades")

# Step 3: For each SELL trade, find the corresponding BUY and recalculate
print("\n🔧 Fixing SELL trades...")
cursor.execute("""
    SELECT id, symbol, trade_time, price, quantity, fee, realized_pnl
    FROM trades
    WHERE side='SELL'
    ORDER BY trade_time
""")
sell_trades = cursor.fetchall()

fixes = 0
total_adjustment = 0.0

for trade_id, symbol, sell_ts, sell_price, qty, sell_fee, old_pnl in sell_trades:
    # Find the most recent BUY before this SELL
    if symbol not in buy_trades:
        print(f"⚠️  SELL {symbol} at {sell_ts} has no matching BUY")
        continue

    # Find the entry that matches this exit (FIFO assumption)
    matching_buy = None
    for i, buy in enumerate(buy_trades[symbol]):
        if buy['qty'] == qty and buy['timestamp'] < sell_ts:
            matching_buy = buy
            break

    if not matching_buy:
        print(f"⚠️  SELL {symbol} qty {qty} at {sell_ts} has no matching BUY with same qty")
        continue

    # Recalculate: (sell_price - buy_price) * qty - buy_fee - sell_fee
    buy_fee = matching_buy['fee']
    buy_price = matching_buy['price']
    new_pnl = (sell_price - buy_price) * qty - buy_fee - sell_fee

    adjustment = new_pnl - old_pnl
    if abs(adjustment) > 0.001:  # Only update if there's a real difference
        cursor.execute(
            "UPDATE trades SET realized_pnl = ? WHERE id = ?",
            (new_pnl, trade_id)
        )
        fixes += 1
        total_adjustment += adjustment
        if fixes <= 10:  # Show first 10 fixes
            print(f"  ✅ {symbol}: {old_pnl:.4f} → {new_pnl:.4f} (adjustment: {adjustment:+.4f})")

print(f"\n✅ Fixed {fixes} SELL trades")
print(f"   Total P&L adjustment: {total_adjustment:+.2f}€")

# Step 4: Verify the fix
conn.commit()

cursor.execute("SELECT SUM(realized_pnl) FROM trades WHERE side='SELL'")
new_sum = cursor.fetchone()[0] or 0.0

print(f"\n📊 After Fix:")
print(f"  - Old sum of SELL realized_pnl: €{current_sum:.2f}")
print(f"  - New sum of SELL realized_pnl: €{new_sum:.2f}")
print(f"  - Net change: {new_sum - current_sum:+.2f}€")

# Calculate what account equity should be
expected_equity = 10000.0 + new_sum
print(f"\n💰 Expected account equity: €{expected_equity:.2f}")
print(f"   (Starting €10,000 + realized P&L €{new_sum:.2f})")

cursor.close()
conn.close()

print(f"\n✅ Database fix complete!")
print(f"   Run /api/monitoring/pnl-reconciliation to verify")
