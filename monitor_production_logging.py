#!/usr/bin/env python3
"""
Production Logging Verification Monitor

PURPOSE: Monitor real production trades and verify entry_reason/exit_reason are logged.
This is the ONLY way to know if the bug fixes actually work.

USAGE:
    python3 monitor_production_logging.py

BEHAVIOR:
    - Runs continuously in background
    - Detects NEW trades since last API restart (08:20:21 UTC 2026-07-10)
    - Alerts when new trade detected
    - Shows if entry_reason/exit_reason are populated
    - RED flags if logging fails on real production trade
"""

import sqlite3
from datetime import datetime, timezone, timedelta
import time
import sys

# Configuration
DB_PATH = "data/trading.db"
API_RESTART_TIME = "2026-07-10T08:20:21"  # When API restarted with fixes
CHECK_INTERVAL_SECONDS = 10
LAST_KNOWN_TRADE = "2026-07-10T07:47:32"  # Last trade before restart

def get_latest_trades(limit=10):
    """Get latest trades from database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
    SELECT id, created_at, symbol, side, quantity, price,
           entry_reason, exit_reason, realized_pnl, status
    FROM trades
    WHERE created_at > ?
    ORDER BY created_at DESC
    LIMIT ?
    """, (API_RESTART_TIME, limit))

    trades = cursor.fetchall()
    conn.close()
    return trades

def format_trade(trade):
    """Format trade for display"""
    tid, created_at, symbol, side, qty, price, entry_reason, exit_reason, pnl, status = trade

    entry_status = "✅" if entry_reason else "❌"
    exit_status = "✅" if exit_reason else "❌"

    print(f"\n{'='*100}")
    print(f"🚨 NEW PRODUCTION TRADE DETECTED")
    print(f"{'='*100}")
    print(f"Time:        {created_at}")
    print(f"Symbol:      {symbol}")
    print(f"Side:        {side}")
    print(f"Qty:         {qty:.6f} @ €{price:.2f}")
    print(f"P&L:         €{pnl:+.2f}" if pnl else "OPEN")
    print(f"Status:      {status}")
    print()
    print(f"LOGGING VERIFICATION:")
    print(f"  Entry Reason: {entry_status} {entry_reason if entry_reason else 'NULL ❌ BUG NOT FIXED'}")
    print(f"  Exit Reason:  {exit_status} {exit_reason if exit_reason else 'NULL (N/A if open)' if side == 'BUY' else 'NULL ❌ BUG NOT FIXED'}")
    print()

    # Verdict
    if side == "BUY":
        if entry_reason:
            print("✅ VERDICT: Entry logging WORKING - Bug appears FIXED")
        else:
            print("🔴 VERDICT: Entry logging FAILED - Bug NOT fixed")
    elif side == "SELL":
        if exit_reason:
            print("✅ VERDICT: Exit logging WORKING - Bug appears FIXED")
        else:
            print("🔴 VERDICT: Exit logging FAILED - Bug NOT fixed")

    print(f"{'='*100}\n")

def main():
    """Monitor production trades continuously"""
    print("Starting Production Logging Verification Monitor")
    print(f"Watching for trades since API restart: {API_RESTART_TIME}")
    print(f"Check interval: {CHECK_INTERVAL_SECONDS} seconds")
    print(f"Current time: {datetime.now(timezone.utc).isoformat()}")
    print()

    seen_trades = set()

    while True:
        try:
            trades = get_latest_trades(limit=20)

            for trade in trades:
                tid = trade[0]

                # Only alert on new trades we haven't seen before
                if tid not in seen_trades:
                    seen_trades.add(tid)
                    format_trade(trade)

            # Show status
            current_time = datetime.now(timezone.utc).isoformat()
            trades_since_restart = len(seen_trades)

            if trades_since_restart == 0:
                status_msg = f"⏳ Waiting for first production trade... [{current_time}]"
            else:
                status_msg = f"✓ Monitoring active. Trades since restart: {trades_since_restart} [{current_time}]"

            # Clear previous status and print new one
            sys.stdout.write(f"\r{status_msg}")
            sys.stdout.flush()

            time.sleep(CHECK_INTERVAL_SECONDS)

        except KeyboardInterrupt:
            print("\n\nMonitor stopped by user")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
