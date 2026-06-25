#!/bin/bash
# Phase 1 Daily Monitoring Script
# Run daily to track autonomous trader progress
# Usage: bash scripts/monitor-phase1.sh

set -e

REPORT_DATE=$(date '+%Y-%m-%d %H:%M:%S')
API_URL="http://localhost:8001/api/autonomous/status"
LOGS_DIR="logs"
REPORT_FILE="$LOGS_DIR/phase1_monitoring.log"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" | tee -a "$REPORT_FILE"
echo "Phase 1 Daily Monitoring Report: $REPORT_DATE" | tee -a "$REPORT_FILE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" | tee -a "$REPORT_FILE"
echo "" | tee -a "$REPORT_FILE"

# 1. Check trader status
echo "1. TRADER STATUS" | tee -a "$REPORT_FILE"
echo "───────────────────────────────────────────────" | tee -a "$REPORT_FILE"
if ! STATUS=$(curl -s -m 5 "$API_URL"); then
    echo "❌ ERROR: API unreachable at $API_URL" | tee -a "$REPORT_FILE"
    exit 1
fi

RUNNING=$(echo "$STATUS" | jq -r '.running // "unknown"')
ENABLED=$(echo "$STATUS" | jq -r '.enabled // "unknown"')
TOTAL_TRADES=$(echo "$STATUS" | jq -r '.total_trades // 0')
DAILY_PNL=$(echo "$STATUS" | jq -r '.daily_pnl // 0')
DAILY_PNL_PCT=$(echo "$STATUS" | jq -r '.daily_pnl_pct // 0')
ACTIVE_POS=$(echo "$STATUS" | jq -r '.active_positions // 0')

echo "Running: $RUNNING" | tee -a "$REPORT_FILE"
echo "Enabled: $ENABLED" | tee -a "$REPORT_FILE"
echo "Total Trades: $TOTAL_TRADES" | tee -a "$REPORT_FILE"
echo "Active Positions: $ACTIVE_POS" | tee -a "$REPORT_FILE"
echo "Daily P&L: €$(printf "%.2f" "$DAILY_PNL") ($DAILY_PNL_PCT%)" | tee -a "$REPORT_FILE"
echo "" | tee -a "$REPORT_FILE"

# 2. Count events from logs
echo "2. TRADE EVENTS (Last 24h)" | tee -a "$REPORT_FILE"
echo "───────────────────────────────────────────────" | tee -a "$REPORT_FILE"

SIGNAL_EVENTS=$(grep "SIGNAL_DECISION" "$LOGS_DIR/api_server.log" 2>/dev/null | wc -l | tr -d ' ')
TRADE_EXECUTED=$(grep "TRADE_EXECUTED" "$LOGS_DIR/api_server.log" 2>/dev/null | wc -l | tr -d ' ')
TRADE_EXIT=$(grep "TRADE_EXIT" "$LOGS_DIR/api_server.log" 2>/dev/null | wc -l | tr -d ' ')
ORDER_FAILED=$(grep "ORDER_FAILED" "$LOGS_DIR/api_server.log" 2>/dev/null | wc -l | tr -d ' ')
EXIT_FAILED=$(grep "EXIT_FAILED" "$LOGS_DIR/api_server.log" 2>/dev/null | wc -l | tr -d ' ')

echo "Signal Decisions: $SIGNAL_EVENTS" | tee -a "$REPORT_FILE"
echo "Entries Executed: $TRADE_EXECUTED" | tee -a "$REPORT_FILE"
echo "Exits Executed: $TRADE_EXIT" | tee -a "$REPORT_FILE"
echo "Failed Orders: $ORDER_FAILED" | tee -a "$REPORT_FILE"
echo "Failed Exits: $EXIT_FAILED" | tee -a "$REPORT_FILE"

if [ "$TRADE_EXIT" -gt 0 ]; then
    WIN_RATE=$((TRADE_EXIT > 0 ? $(grep "TRADE_EXIT" "$LOGS_DIR/api_server.log" 2>/dev/null | jq -s '[.[] | select(.pnl_pct > 0)] | length') * 100 / TRADE_EXIT : 0))
    echo "Win Rate: ~${WIN_RATE}% (based on positive exits)" | tee -a "$REPORT_FILE"
fi
echo "" | tee -a "$REPORT_FILE"

# 3. Check for errors
echo "3. RECENT ERRORS (Last 5)" | tee -a "$REPORT_FILE"
echo "───────────────────────────────────────────────" | tee -a "$REPORT_FILE"
if ERRORS=$(grep -h "ORDER_FAILED\|EXIT_FAILED\|ERROR\|error" "$LOGS_DIR/api_server.log" 2>/dev/null | tail -5); then
    if [ -n "$ERRORS" ]; then
        echo "$ERRORS" | jq -r '.message' 2>/dev/null | head -5 | tee -a "$REPORT_FILE"
    else
        echo "✅ No errors detected" | tee -a "$REPORT_FILE"
    fi
else
    echo "✅ No errors detected" | tee -a "$REPORT_FILE"
fi
echo "" | tee -a "$REPORT_FILE"

# 4. Phase 1 progress
echo "4. PHASE 1 PROGRESS (Target: 10 days, ends ~2026-07-05)" | tee -a "$REPORT_FILE"
echo "───────────────────────────────────────────────" | tee -a "$REPORT_FILE"
PHASE1_START="2026-06-25"
DAYS_ELAPSED=$(($(date +%s) - $(date -d "$PHASE1_START" +%s)))
DAYS_ELAPSED=$((DAYS_ELAPSED / 86400))
DAYS_REMAINING=$((10 - DAYS_ELAPSED))

echo "Days Elapsed: $DAYS_ELAPSED / 10" | tee -a "$REPORT_FILE"
echo "Days Remaining: $DAYS_REMAINING" | tee -a "$REPORT_FILE"
echo "" | tee -a "$REPORT_FILE"

# 5. Success criteria check
echo "5. SUCCESS CRITERIA CHECK" | tee -a "$REPORT_FILE"
echo "───────────────────────────────────────────────" | tee -a "$REPORT_FILE"
echo "Target: Win Rate > 55%, Cumulative P&L > €0, No crashes" | tee -a "$REPORT_FILE"

if [ "$RUNNING" = "true" ] && [ "$ENABLED" = "true" ]; then
    echo "✅ Trader is running and enabled" | tee -a "$REPORT_FILE"
else
    echo "❌ Trader not running or not enabled - ATTENTION NEEDED" | tee -a "$REPORT_FILE"
fi

if [ "$(echo "$DAILY_PNL > 0" | bc)" -eq 1 ]; then
    echo "✅ Daily P&L is positive: €$(printf "%.2f" "$DAILY_PNL")" | tee -a "$REPORT_FILE"
elif [ "$(echo "$DAILY_PNL < 0" | bc)" -eq 1 ]; then
    echo "⚠️  Daily P&L is negative: €$(printf "%.2f" "$DAILY_PNL")" | tee -a "$REPORT_FILE"
else
    echo "ℹ️  Daily P&L is neutral: €0.00" | tee -a "$REPORT_FILE"
fi

TOTAL_FAILURES=$((ORDER_FAILED + EXIT_FAILED))
if [ "$TOTAL_FAILURES" -eq 0 ]; then
    echo "✅ No order failures detected" | tee -a "$REPORT_FILE"
else
    echo "⚠️  Found failures - Order: $ORDER_FAILED, Exit: $EXIT_FAILED (Total: $TOTAL_FAILURES)" | tee -a "$REPORT_FILE"
fi

echo "" | tee -a "$REPORT_FILE"
echo "Report saved to: $REPORT_FILE" | tee -a "$REPORT_FILE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" | tee -a "$REPORT_FILE"
echo "" | tee -a "$REPORT_FILE"
