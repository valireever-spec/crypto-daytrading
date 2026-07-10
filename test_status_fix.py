#!/usr/bin/env python3
"""Manually test the status fix by inserting a BUY and SELL."""

import sqlite3
from datetime import datetime, timezone
from backend.core.database import TradingDatabase

db = TradingDatabase("data/trading.db")

# Insert a test BUY trade (simulating entry signal)
buy_time = datetime.now(timezone.utc)
buy_id = db.insert_trade(
    symbol="BTCUSDT",
    side="BUY",
    quantity=1.0,
    price=100.0,
    trade_time=buy_time,
    order_id="test-buy-" + str(datetime.now(timezone.utc).timestamp()),
    slippage_pct=0.1,
    realized_pnl=0.0,
    fee=0.1,
    entry_reason="TEST: Testing status fix",
    exit_reason=None,
)
print(f"✅ Inserted BUY trade #{buy_id}")

# Check initial status
conn = sqlite3.connect("data/trading.db")
conn.row_factory = sqlite3.Row
cursor = conn.cursor()
cursor.execute("SELECT id, status FROM trades WHERE id = ?", (buy_id,))
result = cursor.fetchone()
print(f"   Initial status: {result['status']}")
conn.close()

# Now insert a SELL trade (should trigger UPDATE to mark BUY as CLOSED)
sell_time = datetime.now(timezone.utc)
sell_id = db.insert_trade(
    symbol="BTCUSDT",
    side="SELL",
    quantity=1.0,
    price=101.0,
    trade_time=sell_time,
    order_id="test-sell-" + str(datetime.now(timezone.utc).timestamp()),
    slippage_pct=0.1,
    realized_pnl=1.0,
    fee=0.1,
    entry_reason=None,
    exit_reason="TEST: Profit target",
)
print(f"✅ Inserted SELL trade #{sell_id}")

# Check if BUY was automatically marked as CLOSED
conn = sqlite3.connect("data/trading.db")
conn.row_factory = sqlite3.Row
cursor = conn.cursor()
cursor.execute("SELECT id, status FROM trades WHERE id = ?", (buy_id,))
result = cursor.fetchone()
print(f"   BUY status after SELL: {result['status']}")

if result['status'] == 'CLOSED':
    print(f"\n✅ SUCCESS: BUY trade #{buy_id} was automatically marked CLOSED!")
else:
    print(f"\n❌ FAILURE: BUY trade #{buy_id} is still {result['status']} (expected CLOSED)")

conn.close()
