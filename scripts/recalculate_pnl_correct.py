#!/usr/bin/env python3
"""Correct P&L Calculation — Proper BUY/SELL Pairing & Metrics

This script implements the CORRECT P&L calculation by:
1. Matching each SELL to its corresponding BUY (FIFO per symbol)
2. Calculating round-trip P&L: (SELL_price - BUY_price) * qty - BUY_fee - SELL_fee
3. Recalculating all performance metrics from correct P&L
4. Updating database with corrected values

Output: Real metrics to determine strategy viability
"""

import sqlite3
import sys
from pathlib import Path
from datetime import datetime
from collections import defaultdict

DB_PATH = Path("/home/vali/projects/crypto-daytrading/data/trading.db")
if not DB_PATH.exists():
    print(f"❌ Database not found at {DB_PATH}")
    sys.exit(1)

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

print("=" * 80)
print("🔧 CORRECT P&L CALCULATION — BUY/SELL PAIRING")
print("=" * 80)

# Step 1: Load all trades
print("\n📥 Loading all trades from database...")
cursor.execute("""
    SELECT id, symbol, side, quantity, price, fee, trade_time
    FROM trades
    ORDER BY trade_time
""")
all_trades = cursor.fetchall()
print(f"✅ Loaded {len(all_trades)} trades")

# Step 2: Organize trades by symbol and side
trades_by_symbol = defaultdict(lambda: {'BUY': [], 'SELL': []})
for trade_id, symbol, side, qty, price, fee, trade_time in all_trades:
    trades_by_symbol[symbol][side].append({
        'id': trade_id,
        'qty': qty,
        'price': price,
        'fee': fee,
        'time': trade_time
    })

print(f"✅ Organized by {len(trades_by_symbol)} symbols")

# Step 3: Calculate correct P&L by matching BUY/SELL pairs (FIFO)
print("\n🔍 Calculating correct P&L (FIFO pairing)...")

pnl_records = {}  # sell_id -> correct_pnl
total_correct_pnl = 0.0
total_fees = 0.0
winners = 0
losers = 0
trade_pairs = 0

for symbol in sorted(trades_by_symbol.keys()):
    buys = trades_by_symbol[symbol]['BUY']
    sells = trades_by_symbol[symbol]['SELL']

    buy_queue = list(buys)  # FIFO queue

    for sell in sells:
        if not buy_queue:
            print(f"⚠️  {symbol}: SELL with no matching BUY (orphaned)")
            continue

        # Match to first (oldest) unmatched BUY
        buy = buy_queue.pop(0)

        # Verify quantities match (FIFO assumption)
        if abs(buy['qty'] - sell['qty']) > 0.0001:
            print(f"⚠️  {symbol}: Quantity mismatch BUY {buy['qty']} vs SELL {sell['qty']}")
            # Still pair them (could be partial fills)

        # Calculate correct round-trip P&L
        price_delta = sell['price'] - buy['price']
        quantity = min(buy['qty'], sell['qty'])  # Use actual matched quantity
        realized_pnl = (price_delta * quantity) - buy['fee'] - sell['fee']

        pnl_records[sell['id']] = realized_pnl
        total_correct_pnl += realized_pnl
        total_fees += (buy['fee'] + sell['fee'])

        if realized_pnl > 0:
            winners += 1
        else:
            losers += 1

        trade_pairs += 1

        # Show sample trades
        if trade_pairs <= 5:
            print(f"  ✅ {symbol}: BUY@{buy['price']:.2f} → SELL@{sell['price']:.2f} = "
                  f"{realized_pnl:+.4f}€ (Q:{quantity:.4f})")

print(f"\n✅ Paired {trade_pairs} BUY/SELL trades")
print(f"   Winners: {winners} | Losers: {losers}")

# Step 4: Compare to old calculation
cursor.execute("SELECT SUM(realized_pnl) FROM trades WHERE side='SELL'")
old_pnl_sum = cursor.fetchone()[0] or 0.0

print(f"\n📊 P&L Comparison:")
print(f"   Old (broken) calculation: €{old_pnl_sum:.2f}")
print(f"   New (correct) calculation: €{total_correct_pnl:.2f}")
print(f"   Difference: {total_correct_pnl - old_pnl_sum:+.2f}€")

# Step 5: Calculate performance metrics
print(f"\n📈 Performance Metrics (from correct P&L):")

win_rate = (winners / (winners + losers) * 100) if (winners + losers) > 0 else 0
avg_win = 0
avg_loss = 0

cursor.execute("""
    SELECT realized_pnl FROM trades WHERE side='SELL'
""")
all_sell_pnl = [pnl_records.get(row[0], 0) for row in cursor.fetchall()]

winning_pnl = [p for p in all_sell_pnl if p > 0]
losing_pnl = [p for p in all_sell_pnl if p <= 0]

if winning_pnl:
    avg_win = sum(winning_pnl) / len(winning_pnl)
if losing_pnl:
    avg_loss = sum(losing_pnl) / len(losing_pnl)

profit_factor = abs(sum(winning_pnl) / sum(losing_pnl)) if losing_pnl and sum(losing_pnl) != 0 else 0
risk_reward = abs(avg_win / avg_loss) if avg_loss != 0 else 0

print(f"   Win Rate: {win_rate:.1f}% ({winners}/{winners+losers})")
print(f"   Avg Win: €{avg_win:.4f}")
print(f"   Avg Loss: €{avg_loss:.4f}")
print(f"   Risk/Reward: {risk_reward:.2f}")
print(f"   Profit Factor: {profit_factor:.2f}")
print(f"   Total P&L: €{total_correct_pnl:.2f}")
print(f"   Total Fees: €{total_fees:.2f}")

# Step 6: Calculate account equity
starting_capital = 10000.0
expected_equity = starting_capital + total_correct_pnl

print(f"\n💰 Account Reconciliation:")
print(f"   Starting Capital: €{starting_capital:.2f}")
print(f"   Correct Total P&L: €{total_correct_pnl:.2f}")
print(f"   Expected Equity: €{expected_equity:.2f}")

# Get actual account state
cursor.execute("SELECT cash, total_pnl FROM account_state ORDER BY id DESC LIMIT 1")
result = cursor.fetchone()
if result:
    actual_cash, actual_pnl = result
    print(f"   Actual Cash: €{actual_cash:.2f}")
    print(f"   Actual P&L: €{actual_pnl:.2f}")
    print(f"   Match: {'✅ YES' if abs(actual_pnl - total_correct_pnl) < 1.0 else '⚠️  NO (discrepancy: ' + f'{abs(actual_pnl - total_correct_pnl):.2f}€)' }")

# Step 7: Viability assessment
print(f"\n🎯 Strategy Viability:")
if win_rate < 30:
    print(f"   ❌ Win rate {win_rate:.1f}% is too low (need ≥40%)")
elif profit_factor < 1.5:
    print(f"   ❌ Profit factor {profit_factor:.2f} is too low (need ≥1.5)")
elif total_correct_pnl < 0:
    print(f"   ❌ Losing money overall (€{total_correct_pnl:.2f})")
else:
    print(f"   ✅ Potentially viable: {win_rate:.1f}% WR, PF {profit_factor:.2f}, +€{total_correct_pnl:.2f}")

# Step 8: Update database with correct P&L (optional - comment out if unsure)
print(f"\n⚠️  Database update: SKIPPED (review results first)")
print(f"   To update database, run: python3 scripts/update_pnl_in_db.py")

conn.close()

print("\n" + "=" * 80)
print("✅ Analysis complete!")
print("=" * 80)
