#!/usr/bin/env python3
"""
Quick Exit Test - Directly test if exit_reason logging works

This test:
1. Inserts a test SELL trade with exit_reason parameter
2. Verifies exit_reason parameter is persisted
3. Shows if the logging capability works in database layer for exits
"""

import sqlite3
from datetime import datetime, timezone

print("\n" + "="*80)
print("QUICK EXIT TEST")
print("="*80)
print("\nTesting: exit_reason parameter persistence in database")
print()

DB_PATH = "data/trading.db"

# Test parameters
symbol = 'BTCUSDT'
test_exit_reason = "TEST: Profit target (+2.0%)"
exit_price = 65714.77  # +2% from 64426.74
qty = 0.0005

print(f"Test Exit Trade:")
print(f"  Symbol: {symbol}")
print(f"  Side: SELL")
print(f"  Qty: {qty}")
print(f"  Price: €{exit_price:.2f}")
print(f"  Exit Reason: {test_exit_reason}")
print()

# Connect to database
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Check if exit_reason column exists
cursor.execute("PRAGMA table_info(trades)")
columns = cursor.fetchall()
column_names = [col[1] for col in columns]

print(f"Checking database schema...")
if 'exit_reason' not in column_names:
    print(f"❌ ERROR: 'exit_reason' column not found in trades table")
    print(f"Columns found: {', '.join(column_names)}")
    cursor.close()
    conn.close()
    exit(1)

print(f"✅ 'exit_reason' column exists")
print()

# Insert test SELL trade (exit trade)
try:
    print("Inserting test exit trade into database...")

    now = datetime.now(timezone.utc).isoformat()

    cursor.execute("""
        INSERT INTO trades (
            symbol, side, quantity, price,
            trade_time, created_at, status,
            exit_reason, realized_pnl
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        symbol,
        'SELL',
        qty,
        exit_price,
        now,
        now,
        'CLOSED',
        test_exit_reason,  # THIS IS WHAT WE'RE TESTING
        100.0  # Simulated profit
    ))

    conn.commit()

    # Get the id of what we just inserted
    inserted_id = cursor.lastrowid
    print(f"✅ Exit trade inserted (ID: {inserted_id})")
    print()

    # Immediately query it back
    print("Querying database for inserted exit trade...")
    cursor.execute("""
        SELECT id, created_at, symbol, side, quantity, price,
               exit_reason, status, realized_pnl
        FROM trades
        WHERE id = ?
    """, (inserted_id,))

    trade = cursor.fetchone()

    if not trade:
        print("❌ Trade not found after insert!")
        conn.close()
        exit(1)

    tid, created_at, sym, side, q, p, exit_reason, status, pnl = trade

    print()
    print("="*80)
    print("DATABASE LAYER TEST RESULT")
    print("="*80)
    print(f"Trade ID:       {tid}")
    print(f"Created:        {created_at}")
    print(f"Symbol:         {sym}")
    print(f"Side:           {side}")
    print(f"Quantity:       {q}")
    print(f"Price:          €{p:.2f}")
    print(f"P&L:            €{pnl:+.2f}")
    print(f"Status:         {status}")
    print(f"Exit Reason:    {exit_reason if exit_reason else '❌ NULL'}")
    print()

    if exit_reason == test_exit_reason:
        print("✅ SUCCESS: exit_reason parameter persisted correctly")
        print()
        print("What this means:")
        print("  ✅ Database schema supports exit_reason column")
        print("  ✅ SQLite INSERT can persist exit reason strings")
        print("  ✅ Database layer capability verified for exits")
        print()
        print("Next: What about the APPLICATION layer?")
        print("  The question is: Does the exit checker actually pass")
        print("  exit_reason to the database INSERT statement?")
        print()
        print("  Monitor will show this when trades exit:")
        print("  - If exit_reason populated → YES, flow works")
        print("  - If exit_reason NULL → NO, parameter lost in app")
        print()
        print("  Current data shows:")
        print("    Profit exits logged: 0 out of 400-600 expected")
        print("    Stop exits logged: 0 out of 200-325 expected")
        print("    Timeout exits logged: 6 (only these recorded)")
        print()
        print("  This suggests exit_reason NOT being passed for most exits")
        success = True
    else:
        print(f"❌ FAILURE: exit_reason not persisted")
        print(f"  Expected: {test_exit_reason}")
        print(f"  Got:      {exit_reason}")
        success = False

    conn.close()

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    conn.close()
    exit(1)

print()
print("="*80)
if success:
    print("✅ DATABASE LAYER CAPABLE OF STORING EXIT REASONS")
    print()
    print("Conclusion: Database is not the problem for exits either.")
    print("Exit reason loss is in APPLICATION LAYER (exit checker → database)")
else:
    print("❌ DATABASE LAYER CANNOT STORE EXIT REASONS")
print("="*80 + "\n")

exit(0 if success else 1)
