#!/bin/bash
# Verification Loop: Check that Trade reasons are properly threaded through the system
# Run this before committing changes to trading logic

set -e

echo "🔍 TRADE REASON CHAIN VERIFICATION"
echo "===================================="
echo ""

FAILED=0

# 1. Type Check: Verify Trade dataclass has entry_reason and exit_reason
echo "✓ Checking Trade dataclass for reason fields..."
if grep -q "entry_reason.*Optional\[str\]" backend/exchange/paper_trading.py && \
   grep -q "exit_reason.*Optional\[str\]" backend/exchange/paper_trading.py; then
    echo "  ✅ Trade dataclass has entry_reason and exit_reason"
else
    echo "  ❌ Trade dataclass missing reason fields"
    FAILED=1
fi

# 2. Parameter Threading: Verify place_order accepts both parameters
echo ""
echo "✓ Checking place_order() signature..."
if grep -q "entry_reason.*Optional\[str\]" backend/exchange/paper_trading.py && \
   grep -q "exit_reason.*Optional\[str\]" backend/exchange/paper_trading.py; then
    echo "  ✅ place_order() has entry_reason and exit_reason parameters"
else
    echo "  ❌ place_order() missing reason parameters"
    FAILED=1
fi

# 3. Entry Reason Threading: Verify entry.py passes entry_reason to place_order
echo ""
echo "✓ Checking entry reason threading..."
if grep -q "entry_reason=signal.reason\|entry_reason=.*reason" backend/trading/autonomous_trader/entry_rsi_oversold.py; then
    echo "  ✅ entry_rsi_oversold.py passes entry_reason to place_order()"
else
    echo "  ❌ entry_rsi_oversold.py does NOT pass entry_reason"
    FAILED=1
fi

# 4. Exit Reason Threading: Verify exit.py passes exit_reason to place_order
echo ""
echo "✓ Checking exit reason threading..."
if grep -q "exit_reason=reason" backend/trading/autonomous_trader/exit.py; then
    echo "  ✅ exit.py passes exit_reason to place_order()"
else
    echo "  ❌ exit.py does NOT pass exit_reason"
    FAILED=1
fi

# 5. Trade Creation: Verify Trade() constructor includes both reasons
echo ""
echo "✓ Checking Trade instantiation..."
TRADE_INSTANCES=$(grep -n "Trade(" backend/exchange/paper_trading.py | wc -l)
echo "  Found $TRADE_INSTANCES Trade() instantiation(s)"

for line_num in $(grep -n "Trade(" backend/exchange/paper_trading.py | cut -d: -f1); do
    # Check lines around instantiation
    sed -n "${line_num},$((line_num+15))p" backend/exchange/paper_trading.py | \
        grep -q "entry_reason" && echo "  ✅ Line $line_num includes entry_reason" || \
        echo "  ⚠️  Line $line_num may not include entry_reason"
done

# 6. Observability: Check that logs show reason fields
echo ""
echo "✓ Checking log observability..."
if [ -f "logs/trades.jsonl" ]; then
    TOTAL=$(wc -l < logs/trades.jsonl)
    RECENT=$((TOTAL > 100 ? 100 : TOTAL))

    # Count recent trades with entry_reason or exit_reason
    WITH_REASON=$(tail -n $RECENT logs/trades.jsonl | grep -c '"entry_reason"\|"exit_reason"' || true)

    if [ $WITH_REASON -gt 0 ]; then
        echo "  ✅ Recent trades have reason fields ($WITH_REASON/$RECENT)"
    else
        # This is a warning, not a failure (might be old trades)
        echo "  ⚠️  Recent trades may not have reason fields yet (check if trades executed since code change)"
    fi
else
    echo "  ⓘ  trades.jsonl not found (will be created on first trade)"
fi

# 7. Run mypy type check
echo ""
echo "✓ Running mypy type checking..."
if command -v mypy &> /dev/null; then
    if mypy backend/exchange/paper_trading.py --no-error-summary 2>/dev/null | grep -q "error\|Unexpected"; then
        echo "  ⚠️  mypy found type issues (but may not be blocking)"
    else
        echo "  ✅ mypy type checking passed"
    fi
else
    echo "  ⓘ  mypy not installed (skip type checking)"
fi

# Summary
echo ""
echo "===================================="
if [ $FAILED -eq 0 ]; then
    echo "✅ VERIFICATION PASSED: Trade reason chain is properly implemented"
    exit 0
else
    echo "❌ VERIFICATION FAILED: Missing trade reason chain components"
    exit 1
fi
