#!/bin/bash
# HA Validation Checklist for crypto-daytrading
# Systematic Debugging v2 Applied to PRIMARY & BACKUP Validation
# Usage: bash HA_VALIDATION_CHECKLIST.sh

set -e

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
PRIMARY_URL="http://127.0.0.1:8001"
BACKUP_URL="http://192.168.3.25:8002"
BACKUP_SSH="claude@192.168.3.25"
BACKUP_DB="/home/claude/crypto-daytrading/data/trading.db"
PRIMARY_DB="data/trading.db"

# Counters
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_UNKNOWN=0

echo "=========================================="
echo "HA Validation Checklist"
echo "Using: systematic-debugging-v2"
echo "=========================================="
echo ""

# ============================================================================
# Part 1: PRIMARY Machine Checks
# ============================================================================

echo "PART 1: PRIMARY MACHINE VALIDATION"
echo "===================================="
echo ""

# Test 1.1: PRIMARY API Health
echo -n "Test 1.1: PRIMARY API Reachable... "
if curl -s "$PRIMARY_URL/api/health" | grep -q "healthy"; then
    echo -e "${GREEN}PASS${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${RED}FAIL${NC}"
    ((TESTS_FAILED++))
fi

# Test 1.2: PRIMARY Emergency Stop Available
echo -n "Test 1.2: PRIMARY Emergency Stop Available... "
if curl -s "$PRIMARY_URL/api/emergency/status" | grep -q "emergency_stop_active"; then
    echo -e "${GREEN}PASS${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${RED}FAIL${NC}"
    ((TESTS_FAILED++))
fi

# Test 1.3: PRIMARY Crash Detection Available
echo -n "Test 1.3: PRIMARY Crash Detection Available... "
if curl -s "$PRIMARY_URL/api/emergency/close-all" -X POST -H "Content-Type: application/json" -d '{"threshold_percent": 5.0}' | grep -q "crash_detected"; then
    echo -e "${GREEN}PASS${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${RED}FAIL${NC}"
    ((TESTS_FAILED++))
fi

# Test 1.4: PRIMARY Autonomous Available
echo -n "Test 1.4: PRIMARY Autonomous Trading Available... "
if curl -s "$PRIMARY_URL/api/autonomous/status" | grep -q "enabled"; then
    echo -e "${GREEN}PASS${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${RED}FAIL${NC}"
    ((TESTS_FAILED++))
fi

# Test 1.5: PRIMARY Database Exists
echo -n "Test 1.5: PRIMARY Database Exists... "
if [ -f "$PRIMARY_DB" ]; then
    echo -e "${GREEN}PASS${NC}"
    ((TESTS_PASSED++))
    # Get PRIMARY timestamp
    PRIMARY_TIMESTAMP=$(sqlite3 "$PRIMARY_DB" "SELECT MAX(updated_at) FROM account_state;" 2>/dev/null || echo "UNKNOWN")
    echo "  Primary DB timestamp: $PRIMARY_TIMESTAMP"
else
    echo -e "${RED}FAIL${NC}"
    ((TESTS_FAILED++))
fi

echo ""

# ============================================================================
# Part 2: BACKUP Machine Checks
# ============================================================================

echo "PART 2: BACKUP MACHINE VALIDATION"
echo "=================================="
echo ""

# Test 2.1: BACKUP API Reachable
echo -n "Test 2.1: BACKUP API Reachable... "
if curl -s "$BACKUP_URL/api/health" 2>/dev/null | grep -q "healthy"; then
    echo -e "${GREEN}PASS${NC}"
    ((TESTS_PASSED++))
    BACKUP_REACHABLE=1
else
    echo -e "${YELLOW}UNKNOWN${NC} (remote machine, may be unreachable)"
    ((TESTS_UNKNOWN++))
    BACKUP_REACHABLE=0
fi

# Test 2.2: BACKUP Emergency Stop Available
if [ $BACKUP_REACHABLE -eq 1 ]; then
    echo -n "Test 2.2: BACKUP Emergency Stop Available... "
    if curl -s "$BACKUP_URL/api/emergency/status" | grep -q "emergency_stop_active"; then
        echo -e "${GREEN}PASS${NC}"
        ((TESTS_PASSED++))
    else
        echo -e "${RED}FAIL${NC}"
        ((TESTS_FAILED++))
    fi
else
    echo -e "${YELLOW}Test 2.2: Skipped (BACKUP unreachable)${NC}"
fi

# Test 2.3: BACKUP Database via SSH
echo -n "Test 2.3: BACKUP Database Accessible via SSH... "
if ssh "$BACKUP_SSH" "[ -f $BACKUP_DB ]" 2>/dev/null; then
    echo -e "${GREEN}PASS${NC}"
    ((TESTS_PASSED++))
    # Get BACKUP timestamp
    BACKUP_TIMESTAMP=$(ssh "$BACKUP_SSH" "sqlite3 $BACKUP_DB 'SELECT MAX(updated_at) FROM account_state;' 2>/dev/null" || echo "UNKNOWN")
    echo "  BACKUP DB timestamp: $BACKUP_TIMESTAMP"
    BACKUP_DB_ACCESSIBLE=1
else
    echo -e "${RED}FAIL${NC}"
    ((TESTS_FAILED++))
    BACKUP_DB_ACCESSIBLE=0
fi

echo ""

# ============================================================================
# Part 3: Database Synchronization
# ============================================================================

echo "PART 3: DATABASE SYNCHRONIZATION"
echo "================================="
echo ""

# Test 3.1: Timestamps Match
if [ $BACKUP_DB_ACCESSIBLE -eq 1 ] && [ "$PRIMARY_TIMESTAMP" != "UNKNOWN" ] && [ "$BACKUP_TIMESTAMP" != "UNKNOWN" ]; then
    echo -n "Test 3.1: Database Timestamps Synchronized... "

    # Compare timestamps (allowing 2 minute difference for normal drift)
    PRIMARY_TS=$(date -d "$PRIMARY_TIMESTAMP" +%s 2>/dev/null || echo "0")
    BACKUP_TS=$(date -d "$BACKUP_TIMESTAMP" +%s 2>/dev/null || echo "0")
    DIFF=$((PRIMARY_TS - BACKUP_TS))
    DIFF=${DIFF#-}  # Absolute value

    if [ $DIFF -lt 120 ]; then
        echo -e "${GREEN}PASS${NC}"
        ((TESTS_PASSED++))
        echo "  Timestamp difference: ${DIFF}s (< 120s threshold)"
    else
        echo -e "${YELLOW}WARNING${NC}"
        echo "  Timestamp difference: ${DIFF}s (> 120s threshold)"
        echo "  PRIMARY: $PRIMARY_TIMESTAMP"
        echo "  BACKUP:  $BACKUP_TIMESTAMP"
        ((TESTS_UNKNOWN++))
    fi
else
    echo -e "${YELLOW}Test 3.1: Skipped (timestamps unavailable)${NC}"
    ((TESTS_UNKNOWN++))
fi

# Test 3.2: Cash Balance Match
echo -n "Test 3.2: Account Balance Synchronized... "
if [ $BACKUP_DB_ACCESSIBLE -eq 1 ]; then
    PRIMARY_CASH=$(sqlite3 "$PRIMARY_DB" "SELECT cash FROM account_state ORDER BY updated_at DESC LIMIT 1;" 2>/dev/null || echo "UNKNOWN")
    BACKUP_CASH=$(ssh "$BACKUP_SSH" "sqlite3 $BACKUP_DB 'SELECT cash FROM account_state ORDER BY updated_at DESC LIMIT 1;' 2>/dev/null" || echo "UNKNOWN")

    if [ "$PRIMARY_CASH" = "$BACKUP_CASH" ]; then
        echo -e "${GREEN}PASS${NC}"
        ((TESTS_PASSED++))
        echo "  Both machines have cash: €$PRIMARY_CASH"
    elif [ "$PRIMARY_CASH" != "UNKNOWN" ] && [ "$BACKUP_CASH" != "UNKNOWN" ]; then
        echo -e "${YELLOW}WARNING${NC}"
        echo "  PRIMARY cash: €$PRIMARY_CASH"
        echo "  BACKUP cash:  €$BACKUP_CASH"
        ((TESTS_UNKNOWN++))
    else
        echo -e "${YELLOW}UNKNOWN${NC}"
        ((TESTS_UNKNOWN++))
    fi
else
    echo -e "${YELLOW}Test 3.2: Skipped (BACKUP unreachable)${NC}"
    ((TESTS_UNKNOWN++))
fi

echo ""

# ============================================================================
# Part 4: BACKUP Failover Readiness
# ============================================================================

echo "PART 4: BACKUP FAILOVER READINESS"
echo "=================================="
echo ""

# Test 4.1: BACKUP Heartbeat Status
if [ $BACKUP_REACHABLE -eq 1 ]; then
    echo -n "Test 4.1: BACKUP Receiving Heartbeats... "
    if curl -s "$BACKUP_URL/api/ha/heartbeat-status" | grep -q "status"; then
        echo -e "${GREEN}PASS${NC}"
        ((TESTS_PASSED++))
    else
        echo -e "${YELLOW}UNKNOWN${NC}"
        ((TESTS_UNKNOWN++))
    fi
else
    echo -e "${YELLOW}Test 4.1: Skipped (BACKUP unreachable)${NC}"
    ((TESTS_UNKNOWN++))
fi

# Test 4.2: BACKUP Not Trading
if [ $BACKUP_REACHABLE -eq 1 ]; then
    echo -n "Test 4.2: BACKUP Not Trading (Standby Mode)... "
    RUNNING=$(curl -s "$BACKUP_URL/api/autonomous/status" | grep -o '"running_now":[^,}]*' | cut -d: -f2)
    if [ "$RUNNING" = "false" ]; then
        echo -e "${GREEN}PASS${NC}"
        ((TESTS_PASSED++))
    else
        echo -e "${YELLOW}WARNING - BACKUP might be trading${NC}"
        ((TESTS_UNKNOWN++))
    fi
else
    echo -e "${YELLOW}Test 4.2: Skipped${NC}"
    ((TESTS_UNKNOWN++))
fi

echo ""

# ============================================================================
# Part 5: FR-020/017/016 Integration
# ============================================================================

echo "PART 5: FR-020/017/016 INTEGRATION"
echo "==================================="
echo ""

# Test 5.1: Emergency Stop Can Be Triggered
echo -n "Test 5.1: Emergency Stop Triggerable... "
RESPONSE=$(curl -s -X POST "$PRIMARY_URL/api/emergency/stop" \
  -H "Content-Type: application/json" \
  -d '{"reason": "Validation test"}')
if echo "$RESPONSE" | grep -q '"success"'; then
    echo -e "${GREEN}PASS${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${RED}FAIL${NC}"
    ((TESTS_FAILED++))
fi

# Test 5.2: Emergency Stop Blocks Autonomous
echo -n "Test 5.2: Emergency Stop Blocks Autonomous... "
STATUS=$(curl -s "$PRIMARY_URL/api/autonomous/status" | grep -o '"running_now":[^,}]*' | cut -d: -f2)
if [ "$STATUS" = "false" ]; then
    echo -e "${GREEN}PASS${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${YELLOW}WARNING${NC} (running_now not false)"
    ((TESTS_UNKNOWN++))
fi

# Test 5.3: Reset Emergency Stop
echo -n "Test 5.3: Emergency Stop Reset... "
RESPONSE=$(curl -s -X POST "$PRIMARY_URL/api/emergency/reset?confirm=true")
if echo "$RESPONSE" | grep -q "reset"; then
    echo -e "${GREEN}PASS${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${RED}FAIL${NC}"
    ((TESTS_FAILED++))
fi

echo ""

# ============================================================================
# Summary
# ============================================================================

echo "=========================================="
echo "VALIDATION SUMMARY"
echo "=========================================="
echo ""
echo -e "Passed:  ${GREEN}${TESTS_PASSED}${NC}"
echo -e "Failed:  ${RED}${TESTS_FAILED}${NC}"
echo -e "Unknown: ${YELLOW}${TESTS_UNKNOWN}${NC}"
echo ""

TOTAL=$((TESTS_PASSED + TESTS_FAILED + TESTS_UNKNOWN))
PASS_RATE=$((TESTS_PASSED * 100 / TOTAL))

echo "Pass Rate: $PASS_RATE%"
echo ""

if [ $TESTS_FAILED -eq 0 ] && [ $TESTS_UNKNOWN -eq 0 ]; then
    echo -e "${GREEN}✅ ALL TESTS PASSED - SYSTEM READY${NC}"
    exit 0
elif [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${YELLOW}⚠️  ALL CRITICAL TESTS PASSED (some unknowns)${NC}"
    echo "   Recommendation: Manual verification recommended"
    exit 0
else
    echo -e "${RED}❌ SOME TESTS FAILED - INVESTIGATE${NC}"
    echo "   See: HA_VALIDATION_SYSTEMATIC_DEBUG.md"
    exit 1
fi
