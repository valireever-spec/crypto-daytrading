#!/usr/bin/env python3
"""Calculate P&L from Actual Cash Flow

The realized_pnl field in database is garbage. Instead:
1. Calculate cash flow from each BUY and SELL
2. Final cash = starting capital + sum of all cash flows
3. P&L = final cash - starting capital
4. This is the ONLY reliable source of truth
"""

import sqlite3
from pathlib import Path

DB_PATH = Path("/home/vali/projects/crypto-daytrading/data/trading.db")
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

print("=" * 80)
print("💰 CORRECT P&L FROM CASH FLOW ANALYSIS")
print("=" * 80)

# Get all trades in chronological order
cursor.execute("""
    SELECT id, symbol, side, quantity, price, fee, trade_time
    FROM trades
    ORDER BY trade_time
""")

trades = cursor.fetchall()
print(f"\n📥 Loaded {len(trades)} trades")

# Simulate cash account
starting_capital = 10000.0
simulated_cash = starting_capital

# Track by side
buy_total = 0.0
sell_total = 0.0
buy_fees = 0.0
sell_fees = 0.0

for trade_id, symbol, side, qty, price, fee, trade_time in trades:
    if side == 'BUY':
        # Cash out: price + fee
        cost = (qty * price) + fee
        simulated_cash -= cost
        buy_total += (qty * price)
        buy_fees += fee
    else:  # SELL
        # Cash in: price - fee
        proceeds = (qty * price) - fee
        simulated_cash += proceeds
        sell_total += (qty * price)
        sell_fees += fee

print(f"\n🔄 Cash Flow Breakdown:")
print(f"   Starting Capital: €{starting_capital:.2f}")
print(f"   Total BUY value: €{buy_total:.2f}")
print(f"   Total SELL value: €{sell_total:.2f}")
print(f"   Total BUY fees: €{buy_fees:.2f}")
print(f"   Total SELL fees: €{sell_fees:.2f}")
print(f"   Simulated cash: €{simulated_cash:.2f}")

# P&L from simulated cash
simulated_pnl = simulated_cash - starting_capital

# Get actual account state
cursor.execute("""
    SELECT cash, total_pnl FROM account_state ORDER BY updated_at DESC LIMIT 1
""")
result = cursor.fetchone()
actual_cash = result[0] if result else 0
actual_pnl = result[1] if result else 0

print(f"\n📊 Reconciliation:")
print(f"   Simulated cash: €{simulated_cash:.2f}")
print(f"   Actual cash: €{actual_cash:.2f}")
print(f"   Difference: €{simulated_cash - actual_cash:.2f}")
print(f"\n   Simulated P&L: €{simulated_pnl:.2f}")
print(f"   Actual P&L: €{actual_pnl:.2f}")
print(f"   Difference: €{simulated_pnl - actual_pnl:.2f}")

if abs(simulated_cash - actual_cash) < 1.0:
    print(f"\n   ✅ Cash flow matches actual account!")
else:
    print(f"\n   ⚠️  Cash flow mismatch of €{abs(simulated_cash - actual_cash):.2f}")
    print(f"      This could indicate:")
    print(f"      1. Missing trades in database")
    print(f"      2. Trades loaded from DB don't match engine state")
    print(f"      3. Account state was manually adjusted")

# Now calculate win/loss properly
print(f"\n📈 Trade Analysis:")

cursor.execute("""
    SELECT id, symbol, side, quantity, price, fee, trade_time
    FROM trades
    ORDER BY symbol, trade_time
""")

trades_by_symbol = {}
for trade_id, symbol, side, qty, price, fee, trade_time in cursor.fetchall():
    if symbol not in trades_by_symbol:
        trades_by_symbol[symbol] = {'BUY': [], 'SELL': []}
    trades_by_symbol[symbol][side].append({
        'id': trade_id, 'qty': qty, 'price': price, 'fee': fee, 'time': trade_time
    })

total_wins = 0
total_losses = 0
total_win_value = 0.0
total_loss_value = 0.0

for symbol in sorted(trades_by_symbol.keys()):
    buys = trades_by_symbol[symbol]['BUY']
    sells = trades_by_symbol[symbol]['SELL']

    print(f"\n   {symbol}: {len(buys)} buys, {len(sells)} sells")

    # FIFO pairing
    buy_idx = 0
    for sell in sells:
        if buy_idx >= len(buys):
            print(f"      ⚠️  SELL without matching BUY (orphaned position)")
            break

        buy = buys[buy_idx]
        matched_qty = min(buy['qty'], sell['qty'])

        # Calculate P&L for this round-trip
        pnl = (sell['price'] - buy['price']) * matched_qty - buy['fee'] - sell['fee']

        if pnl > 0:
            total_wins += 1
            total_win_value += pnl
        else:
            total_losses += 1
            total_loss_value += pnl

        # Update buy quantity
        buy['qty'] -= matched_qty
        if buy['qty'] < 0.0001:
            buy_idx += 1

    # Remaining buys are open positions
    if buy_idx < len(buys):
        open_qty = sum(b['qty'] for b in buys[buy_idx:])
        if open_qty > 0.0001:
            print(f"      📍 Open position: {open_qty:.4f} units")

win_rate = (total_wins / (total_wins + total_losses) * 100) if (total_wins + total_losses) > 0 else 0
avg_win = total_win_value / total_wins if total_wins > 0 else 0
avg_loss = total_loss_value / total_losses if total_losses > 0 else 0
profit_factor = abs(total_win_value / total_loss_value) if total_loss_value != 0 else 0

print(f"\n📊 Final Metrics:")
print(f"   Total trades: {len(trades)}")
print(f"   Closed trades: {total_wins + total_losses}")
print(f"   Winning trades: {total_wins}")
print(f"   Losing trades: {total_losses}")
print(f"   Win Rate: {win_rate:.1f}%")
print(f"   Avg Win: €{avg_win:.4f}")
print(f"   Avg Loss: €{avg_loss:.4f}")
print(f"   Profit Factor: {profit_factor:.2f}")
print(f"   Total Win Value: €{total_win_value:.2f}")
print(f"   Total Loss Value: €{total_loss_value:.2f}")

print(f"\n🎯 Strategy Assessment:")
if win_rate < 35:
    print(f"   ❌ Win rate {win_rate:.1f}% is critically low")
    print(f"      Need at least 35-40% to be viable")
if profit_factor < 1.5 and total_losses < 0:
    print(f"   ❌ Profit factor {profit_factor:.2f} insufficient")
    print(f"      Need at least 1.5x to cover losses")
if total_loss_value < -5.0:
    print(f"   ❌ Losing money: €{total_loss_value:.2f} in losses")

if win_rate >= 35 and profit_factor >= 1.5:
    print(f"   ✅ Strategy shows promise!")
else:
    print(f"   ⚠️  Strategy needs significant redesign")

conn.close()

print("\n" + "=" * 80)
print("✅ Analysis complete!")
print("=" * 80)
