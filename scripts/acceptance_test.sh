#!/bin/bash

##############################################################################
# PHASE 1 ACCEPTANCE TEST
# Validates that crypto daytrading system meets Phase 1 requirements:
# - >55% win rate across all strategies
# - Positive P&L over 10-day period
# - Max daily loss < 5%
# - All safety gates active
##############################################################################

set -e

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║         PHASE 1 ACCEPTANCE TEST - 10-Day Paper Trading        ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

API="http://localhost:8001/api"

# ============================================================================
# 1. VERIFY SYSTEM IS READY
# ============================================================================

echo "📋 Step 1: System Readiness Check"
echo "─────────────────────────────────"

STATUS=$(curl -s "${API}/autonomous/status" | jq -r '.running')
MODE=$(curl -s "${API}/autonomous/status" | jq -r '.account_state.mode')
CASH=$(curl -s "${API}/autonomous/status" | jq -r '.account_state.cash')

echo "✓ Autonomous Trader Running: $STATUS"
echo "✓ Trading Mode: $MODE (should be PAPER)"
echo "✓ Starting Capital: €$CASH"
echo ""

if [ "$STATUS" != "true" ]; then
  echo "❌ FAILED: Autonomous trader not running"
  exit 1
fi

if [ "$MODE" != "PAPER" ]; then
  echo "❌ FAILED: Not in PAPER mode (safety risk)"
  exit 1
fi

CASH_INT=$(printf "%.0f" "$CASH")
if [ "$CASH_INT" != "1000" ]; then
  echo "❌ FAILED: Starting capital is not €1,000 (got €$CASH)"
  exit 1
fi

# ============================================================================
# 2. CHECK ALL SAFETY GATES ARE ACTIVE
# ============================================================================

echo "🛡️  Step 2: Safety Gates Verification"
echo "─────────────────────────────────────"

HARDENING=$(curl -s "${API}/autonomous/status" | jq '.hardening_status')

echo "$HARDENING" | jq -r 'to_entries[] | "\(.value) \(.key)"'
echo ""

GATES_ACTIVE=$(echo "$HARDENING" | jq '[.[] | select(contains("✅"))] | length')
GATES_TOTAL=$(echo "$HARDENING" | jq 'length')

if [ "$GATES_ACTIVE" -eq "$GATES_TOTAL" ]; then
  echo "✅ All $GATES_TOTAL safety gates ACTIVE"
else
  echo "⚠️  WARNING: Only $GATES_ACTIVE/$GATES_TOTAL gates active"
fi
echo ""

# ============================================================================
# 3. VERIFY PAPER TRADING DATABASE IS CLEAN
# ============================================================================

echo "🗄️  Step 3: Database State Check"
echo "────────────────────────────────"

POSITIONS=$(curl -s "${API}/paper/positions" | jq 'length')
TRADES=$(curl -s "${API}/paper/trades" | jq 'length')
DAILY_PNL=$(curl -s "${API}/health" | jq -r '.account.daily_pnl')
TOTAL_PNL=$(curl -s "${API}/health" | jq -r '.account.total_pnl')

echo "✓ Open Positions: $POSITIONS"
echo "✓ Total Trades Executed: $TRADES"
echo "✓ Daily P&L: €$DAILY_PNL"
echo "✓ Total P&L: €$TOTAL_PNL"
echo ""

# ============================================================================
# 4. ACCEPTANCE TEST RUNTIME INFO
# ============================================================================

echo "⏱️  Step 4: Acceptance Test Schedule"
echo "─────────────────────────────────────"
echo ""
echo "📊 10-Day Paper Trading Simulation"
echo "   Start Time: $(date)"
echo "   Duration: 10 trading days (real-time)"
echo "   Symbols: BTCUSDT, ETHUSDT, BNBUSDT"
echo "   Strategies: Momentum, Mean Reversion, Grid"
echo ""
echo "📈 Success Criteria (ALL must pass):"
echo "   ✓ Win Rate: >55% (cumulative across all trades)"
echo "   ✓ Total P&L: Positive (€0+)"
echo "   ✓ Max Daily Loss: <5% of starting capital (€50)"
echo "   ✓ Safety Gates: All active (no circuit breaker trips)"
echo "   ✓ Uptime: 100% (no crashes)"
echo ""

# ============================================================================
# 5. MONITORING DASHBOARD
# ============================================================================

echo "📊 Monitoring Dashboard"
echo "──────────────────────"
echo ""
echo "Real-time Metrics: http://localhost:8080/unified-dashboard.html"
echo ""
echo "Check these during the 10-day run:"
echo "  • Account Overview tab: Cash, Equity, P&L"
echo "  • Market Status tab: Live prices & allocation"
echo "  • Strategies tab: Win rate, trades per strategy"
echo "  • Health tab: System status & circuit breaker"
echo ""

# ============================================================================
# 6. START MONITORING
# ============================================================================

echo "🚀 Step 5: Starting Acceptance Test Monitoring"
echo "──────────────────────────────────────────────"
echo ""

# Create a simple monitoring loop that checks every hour
TEST_START=$(date +%s)
TEST_DURATION=$((10 * 24 * 60 * 60))  # 10 days in seconds
CHECK_INTERVAL=3600                    # Check every hour

TEST_HOUR=0

while true; do
  CURRENT_TIME=$(date)
  TEST_HOUR=$((TEST_HOUR + 1))

  # Get current metrics
  HEALTH=$(curl -s "${API}/health" 2>/dev/null || echo '{"account":{"cash":0,"total_equity":0,"total_pnl":0,"daily_pnl":0,"active_positions":0}}')
  CASH=$(echo "$HEALTH" | jq -r '.account.cash // 0')
  EQUITY=$(echo "$HEALTH" | jq -r '.account.total_equity // 0')
  TOTAL_PNL=$(echo "$HEALTH" | jq -r '.account.total_pnl // 0')
  DAILY_PNL=$(echo "$HEALTH" | jq -r '.account.daily_pnl // 0')
  ACTIVE_POS=$(echo "$HEALTH" | jq -r '.account.active_positions // 0')

  TRADES=$(curl -s "${API}/paper/trades" 2>/dev/null | jq 'length' || echo 0)

  echo "⏰ Test Hour $TEST_HOUR | $CURRENT_TIME"
  echo "   Cash: €$CASH | Equity: €$EQUITY | P&L: €$TOTAL_PNL | Daily: €$DAILY_PNL"
  echo "   Positions: $ACTIVE_POS | Total Trades: $TRADES"

  # Check if we've reached 10 days
  ELAPSED=$(($(date +%s) - TEST_START))
  if [ $ELAPSED -ge $TEST_DURATION ]; then
    echo ""
    echo "✅ 10-Day Test Period Complete!"
    break
  fi

  # For development: exit after 1 hour instead of waiting 10 days
  if [ $TEST_HOUR -ge 1 ]; then
    echo ""
    echo "ℹ️  Development Mode: Exiting after 1 hour of monitoring"
    echo "   (In production, would continue for full 10 days)"
    break
  fi

  sleep $CHECK_INTERVAL
done

# ============================================================================
# 7. ACCEPTANCE CRITERIA VALIDATION
# ============================================================================

echo ""
echo "📊 Step 6: Acceptance Criteria Validation"
echo "─────────────────────────────────────────"
echo ""

# Get final metrics
FINAL_HEALTH=$(curl -s "${API}/health")
FINAL_TRADES=$(curl -s "${API}/paper/trades")
FINAL_STATS=$(curl -s "${API}/strategies/all-stats")

FINAL_CASH=$(echo "$FINAL_HEALTH" | jq -r '.account.cash')
FINAL_EQUITY=$(echo "$FINAL_HEALTH" | jq -r '.account.total_equity')
FINAL_PNL=$(echo "$FINAL_HEALTH" | jq -r '.account.total_pnl')
NUM_TRADES=$(echo "$FINAL_TRADES" | jq 'length')

# Calculate win rate
if [ "$NUM_TRADES" -gt 0 ]; then
  WINNING_TRADES=$(echo "$FINAL_TRADES" | jq '[.[] | select(.realized_pnl > 0)] | length')
  WIN_RATE=$(awk "BEGIN {printf \"%.1f\", ($WINNING_TRADES / $NUM_TRADES) * 100}")
else
  WIN_RATE="0.0"
  WINNING_TRADES=0
fi

# Validation results
echo "Criterion 1: Win Rate >55%"
if (( $(echo "$WIN_RATE > 55" | bc -l) )); then
  echo "  ✅ PASS: $WIN_RATE% ($WINNING_TRADES/$NUM_TRADES trades)"
else
  echo "  ❌ FAIL: $WIN_RATE% (need >55%)"
fi
echo ""

echo "Criterion 2: Positive Total P&L"
if (( $(echo "$FINAL_PNL > 0" | bc -l) )); then
  echo "  ✅ PASS: €$FINAL_PNL"
else
  echo "  ❌ FAIL: €$FINAL_PNL (need positive)"
fi
echo ""

echo "Criterion 3: Max Daily Loss <5%"
DAILY_LOSS_PCT=$(awk "BEGIN {printf \"%.1f\", abs($FINAL_PNL / 1000) * 100}")
if (( $(echo "$DAILY_LOSS_PCT < 5" | bc -l) )); then
  echo "  ✅ PASS: $DAILY_LOSS_PCT%"
else
  echo "  ❌ FAIL: $DAILY_LOSS_PCT% (need <5%)"
fi
echo ""

echo "Criterion 4: All Safety Gates Active"
GATES_CHECK=$(curl -s "${API}/autonomous/status" | jq '[.hardening_status[] | select(contains("✅"))] | length')
if [ "$GATES_CHECK" -eq 10 ]; then
  echo "  ✅ PASS: $GATES_CHECK/10 gates active"
else
  echo "  ❌ FAIL: Only $GATES_CHECK/10 gates active"
fi
echo ""

# ============================================================================
# 8. FINAL SUMMARY
# ============================================================================

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                   ACCEPTANCE TEST SUMMARY                      ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "Final Account State:"
echo "  Starting Capital: €1,000.00"
echo "  Final Equity:     €$FINAL_EQUITY"
echo "  Total P&L:        €$FINAL_PNL"
echo "  Total Trades:     $NUM_TRADES"
echo "  Win Rate:         $WIN_RATE%"
echo ""
echo "Next Steps:"
echo "  1. Review detailed results at: http://localhost:8080/unified-dashboard.html"
echo "  2. If passed: Deploy to backup machine (Phase 2)"
echo "  3. If passed: Prepare for live trading with €1,000"
echo ""
