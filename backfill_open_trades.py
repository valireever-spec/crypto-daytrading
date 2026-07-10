#!/usr/bin/env python3
"""Backfill old OPEN BUY trades as CLOSED by matching with SELL trades."""

import sqlite3
from datetime import datetime

db = sqlite3.connect('data/trading.db')
db.row_factory = sqlite3.Row
cursor = db.cursor()

# Find all OPEN BUY trades
cursor.execute("""
    SELECT id, symbol, trade_time FROM trades
    WHERE side='BUY' AND status='OPEN'
    ORDER BY trade_time ASC
""")

open_buys = cursor.fetchall()
print(f"Found {len(open_buys)} OPEN BUY trades to backfill\n")

matched = 0
for buy in open_buys:
    # Find the first SELL for this symbol after this BUY
    cursor.execute("""
        SELECT id FROM trades
        WHERE symbol=? AND side='SELL' AND datetime(trade_time) > datetime(?)
        ORDER BY trade_time ASC
        LIMIT 1
    """, (buy['symbol'], buy['trade_time']))

    sell = cursor.fetchone()

    if sell:
        # Mark BUY as CLOSED
        cursor.execute(
            "UPDATE trades SET status='CLOSED' WHERE id=?",
            (buy['id'],)
        )
        print(f"✅ BUY #{buy['id']:4d} ({buy['symbol']}) @ {buy['trade_time']}")
        print(f"   → matched to SELL #{sell['id']:4d}")
        matched += 1
    else:
        print(f"⚠️  BUY #{buy['id']:4d} ({buy['symbol']}) @ {buy['trade_time']} - NO MATCHING SELL FOUND")

db.commit()
db.close()

print(f"\n{'='*60}")
print(f"Backfill Complete: {matched}/{len(open_buys)} trades marked CLOSED")
print(f"{'='*60}")
