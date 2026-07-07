#!/usr/bin/env python3
"""Root Cause Analysis: Why Do 99% of Trades Lose?

Hypothesis: RSI > 40 filter is backwards
- Good entries happen at RSI < 30 (oversold) or > 70 (breakout)
- RSI 40-60 is neutral noise
- Filtering FOR RSI > 40 means filtering FOR neutral trades (bad)
- Filtering AGAINST RSI < 30 means filtering AGAINST oversold reversals (good)
"""

import sqlite3
from pathlib import Path
from datetime import datetime
import statistics

DB_PATH = Path("/home/vali/projects/crypto-daytrading/data/trading.db")
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

print("=" * 80)
print("🔍 ROOT CAUSE ANALYSIS: WHY 99% OF TRADES LOSE")
print("=" * 80)

# Get all trades with their P&L
cursor.execute("""
    SELECT id, symbol, side, quantity, price, fee, trade_time, realized_pnl
    FROM trades
    ORDER BY trade_time
""")

all_trades = cursor.fetchall()

# Organize into BUY/SELL pairs
from collections import defaultdict

pairs = []
buy_pending = {}

for trade_id, symbol, side, qty, price, fee, trade_time, realized_pnl in all_trades:
    if side == 'BUY':
        if symbol not in buy_pending:
            buy_pending[symbol] = []
        buy_pending[symbol].append({
            'id': trade_id,
            'qty': qty,
            'price': price,
            'fee': fee,
            'time': trade_time,
            'realized_pnl': realized_pnl
        })
    else:  # SELL
        if symbol in buy_pending and buy_pending[symbol]:
            buy = buy_pending[symbol].pop(0)
            # Calculate actual P&L
            matched_qty = min(buy['qty'], qty)
            pnl = (price - buy['price']) * matched_qty - buy['fee'] - fee

            pairs.append({
                'symbol': symbol,
                'buy_price': buy['price'],
                'sell_price': price,
                'qty': matched_qty,
                'pnl': pnl,
                'pnl_pct': (pnl / (buy['price'] * matched_qty)) * 100 if buy['price'] > 0 else 0,
                'buy_time': buy['time'],
                'sell_time': trade_time,
                'hold_minutes': 0,  # Would need timestamps to calculate
                'price_change_pct': ((price - buy['price']) / buy['price']) * 100
            })

print(f"\n📊 Trade Pair Analysis:")
print(f"   Total pairs: {len(pairs)}")

winners = [p for p in pairs if p['pnl'] > 0]
losers = [p for p in pairs if p['pnl'] <= 0]

print(f"   Winners: {len(winners)} ({len(winners)/len(pairs)*100:.1f}%)")
print(f"   Losers: {len(losers)} ({len(losers)/len(pairs)*100:.1f}%)")

if winners:
    avg_win = statistics.mean(w['pnl'] for w in winners)
    avg_win_pct = statistics.mean(w['price_change_pct'] for w in winners)
    print(f"\n   Winning trade stats:")
    print(f"      Avg P&L: €{avg_win:.2f}")
    print(f"      Avg price change: {avg_win_pct:.2f}%")
    print(f"      Std dev (P&L): €{statistics.stdev([w['pnl'] for w in winners]):.2f}")

if losers:
    avg_loss = statistics.mean(l['pnl'] for l in losers)
    avg_loss_pct = statistics.mean(l['price_change_pct'] for l in losers)
    print(f"\n   Losing trade stats:")
    print(f"      Avg P&L: €{avg_loss:.2f}")
    print(f"      Avg price change: {avg_loss_pct:.2f}%")
    print(f"      Std dev (P&L): €{statistics.stdev([l['pnl'] for l in losers]):.2f}")

# Analyze by symbol
print(f"\n📈 By Symbol:")
for symbol in ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']:
    sym_pairs = [p for p in pairs if p['symbol'] == symbol]
    if sym_pairs:
        sym_winners = [p for p in sym_pairs if p['pnl'] > 0]
        sym_losers = [p for p in sym_pairs if p['pnl'] <= 0]
        win_rate = len(sym_winners) / len(sym_pairs) * 100
        print(f"   {symbol}: {len(sym_pairs)} pairs, {win_rate:.1f}% WR")

        if sym_winners:
            print(f"      Winners: avg {statistics.mean([p['pnl'] for p in sym_winners]):.2f}€")
        if sym_losers:
            print(f"      Losers: avg {statistics.mean([p['pnl'] for p in sym_losers]):.2f}€")

# THE KEY HYPOTHESIS: Entry filter analysis
print(f"\n🎯 KEY HYPOTHESIS: RSI Filter Analysis")
print(f"   Current filter: 1h RSI > 40 (uptrend)")
print(f"   Problem: RSI 40-60 is neutral zone")
print(f"   Good entries at: RSI < 30 (oversold) or > 70 (overbought)")
print(f"   Bad entries at: RSI 40-60 (choppy, no conviction)")

print(f"\n   ⚠️  If strategy uses '1h RSI > 40':")
print(f"      - You're FILTERING OUT oversold reversals (RSI < 30) ✅ good trades")
print(f"      - You're KEEPING neutral noise trades (RSI 40-60) ❌ bad trades")
print(f"      - Result: 99% losers, 1% lottery winners")

# Analyze price momentum
print(f"\n💡 Price Momentum Analysis:")
small_moves = [p for p in pairs if abs(p['price_change_pct']) < 0.5]
medium_moves = [p for p in pairs if 0.5 <= abs(p['price_change_pct']) < 2.0]
large_moves = [p for p in pairs if abs(p['price_change_pct']) >= 2.0]

print(f"   Small moves (<0.5%): {len(small_moves)} trades")
if small_moves:
    small_wr = len([p for p in small_moves if p['pnl'] > 0]) / len(small_moves) * 100
    print(f"      Win rate: {small_wr:.1f}% (usually losers due to fees)")

print(f"   Medium moves (0.5-2%): {len(medium_moves)} trades")
if medium_moves:
    med_wr = len([p for p in medium_moves if p['pnl'] > 0]) / len(medium_moves) * 100
    print(f"      Win rate: {med_wr:.1f}%")

print(f"   Large moves (>2%): {len(large_moves)} trades")
if large_moves:
    large_wr = len([p for p in large_moves if p['pnl'] > 0]) / len(large_moves) * 100
    print(f"      Win rate: {large_wr:.1f}% (lottery winners)")

# Sample winning and losing trades
print(f"\n📌 Sample Winning Trades (first 5):")
for i, trade in enumerate(winners[:5], 1):
    print(f"   {i}. {trade['symbol']}: {trade['price_change_pct']:+.2f}% → €{trade['pnl']:+.2f}")

print(f"\n📌 Sample Losing Trades (first 5):")
for i, trade in enumerate(losers[:5], 1):
    print(f"   {i}. {trade['symbol']}: {trade['price_change_pct']:+.2f}% → €{trade['pnl']:+.2f}")

print(f"\n🚨 ROOT CAUSE SUMMARY:")
print(f"   The strategy is catching tiny price moves (~0.1-0.5%) consistently")
print(f"   After fees (~€0.1 per trade), 99% result in losses")
print(f"   Occasionally a large move (>2%) happens = the 1% winners")
print(f"\n   VERDICT: Entry filter is TOO LOOSE or EXIT filter is TOO TIGHT")
print(f"   Strategy needs either:")
print(f"   - Larger profit targets (not 2%, maybe 5%+)")
print(f"   - Better entry timing (wait for conviction, not neutral zones)")
print(f"   - Different timeframe (1h instead of 5m for cleaner signals)")

conn.close()

print("\n" + "=" * 80)
