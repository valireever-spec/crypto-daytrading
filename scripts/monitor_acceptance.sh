#!/bin/bash

##############################################################################
# PHASE 1 ACCEPTANCE TEST MONITOR
# Watches paper trading in real-time and validates acceptance criteria
##############################################################################

set -e

API="http://localhost:8001/api"
INTERVAL=5  # Check every 5 seconds

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║      PHASE 1 ACCEPTANCE TEST - Live Monitoring Started        ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "📊 Dashboard: http://localhost:8080/unified-dashboard.html"
echo ""
echo "Success Criteria:"
echo "  ✓ Win Rate: >55%"
echo "  ✓ Total P&L: Positive"
echo "  ✓ Max Daily Loss: <5%"
echo "  ✓ All Safety Gates: Active"
echo ""
echo "─────────────────────────────────────────────────────────────────"
echo ""

LAST_TRADE_COUNT=0

while true; do
  # Get current metrics
  HEALTH=$(curl -s "${API}/health" 2>/dev/null || echo '{}')
  TRADES=$(curl -s "${API}/paper/trades" 2>/dev/null || echo '[]')

  CASH=$(echo "$HEALTH" | jq -r '.account.cash // "?"')
  EQUITY=$(echo "$HEALTH" | jq -r '.account.total_equity // "?"')
  TOTAL_PNL=$(echo "$HEALTH" | jq -r '.account.total_pnl // "?"')
  DAILY_PNL=$(echo "$HEALTH" | jq -r '.account.daily_pnl // "?"')
  ACTIVE_POS=$(echo "$HEALTH" | jq -r '.account.active_positions // "?"')

  TRADE_COUNT=$(echo "$TRADES" | jq 'length')

  # Check if new trades were executed
  if [ "$TRADE_COUNT" -gt "$LAST_TRADE_COUNT" ]; then
    NEW_TRADES=$((TRADE_COUNT - LAST_TRADE_COUNT))
    echo "🎯 NEW TRADES EXECUTED: +$NEW_TRADES (Total: $TRADE_COUNT)"
    LAST_TRADE_COUNT=$TRADE_COUNT
  fi

  # Display current state
  TIMESTAMP=$(date "+%H:%M:%S")
  echo "[$TIMESTAMP] Cash: €$CASH | Equity: €$EQUITY | P&L: €$TOTAL_PNL | Daily: €$DAILY_PNL | Positions: $ACTIVE_POS | Total Trades: $TRADE_COUNT"

  # Calculate win rate
  if [ "$TRADE_COUNT" -gt 0 ]; then
    WINNING=$(echo "$TRADES" | jq "[.[] | select(.realized_pnl > 0)] | length")
    WIN_RATE=$(awk "BEGIN {printf \"%.1f\", ($WINNING / $TRADE_COUNT) * 100}")
    echo "           Win Rate: $WIN_RATE% ($WINNING/$TRADE_COUNT)"
  fi

  sleep $INTERVAL
done
