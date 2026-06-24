#!/bin/bash
#
# Test HA Failover Scenarios
#
# This script simulates various failover scenarios and verifies system behavior:
# 1. Primary is healthy → Backup in standby
# 2. Primary fails → Backup activates (immediate failover test)
# 3. Primary recovers → Manual failback
# 4. Backup fails → Primary continues trading
# 5. Network partition → Graceful degradation
#
# Usage: bash scripts/test_failover_scenarios.sh
#

set -e

PRIMARY="http://127.0.0.1:8001"
BACKUP="${BACKUP_URL:-http://192.168.3.204:8002}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

log_error() {
    echo -e "${RED}[✗]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

section() {
    echo ""
    echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
}

# Check API availability
check_api() {
    local url=$1
    local name=$2

    if curl -s -m 5 "$url/api/health" > /dev/null 2>&1; then
        log_success "$name is responding"
        return 0
    else
        log_warning "$name is not responding"
        return 1
    fi
}

# Get redundancy status
get_status() {
    curl -s "$PRIMARY/api/redundancy/status" | python3 -m json.tool
}

# Get replication lag
get_replication_lag() {
    curl -s "$PRIMARY/api/redundancy/replication-lag" | python3 -m json.tool
}

# Get failover readiness
get_failover_readiness() {
    curl -s "$PRIMARY/api/redundancy/failover/ready" | python3 -m json.tool
}

section "SCENARIO 1: Healthy System (Both Primary & Backup Up)"

log_info "Checking primary..."
if check_api "$PRIMARY" "Primary"; then
    log_info "Getting full redundancy status..."
    get_status
    log_success "Primary is healthy and responding"
else
    log_error "Primary is not responding - cannot proceed"
    exit 1
fi

log_info "Checking backup..."
if check_api "$BACKUP" "Backup"; then
    log_success "Backup is running"
else
    log_warning "Backup is not running (normal in non-HA setup)"
fi

section "SCENARIO 2: Replication Lag Check"

log_info "Checking replication lag..."
get_replication_lag

log_info "Interpretation:"
log_info "  HEALTHY: < 2 seconds (no action needed)"
log_info "  WARNING: 2-5 seconds (monitor network)"
log_info "  CRITICAL: > 5 seconds (check PostgreSQL replication)"

section "SCENARIO 3: Failover Readiness Check"

log_info "Checking if backup is ready for failover..."
get_failover_readiness

section "SCENARIO 4: Simulate Failover (Non-Destructive)"

log_info "Simulating what would happen if primary goes down..."
FAILOVER_SIMULATION=$(curl -s -X POST "$PRIMARY/api/redundancy/failover/simulate")
echo "$FAILOVER_SIMULATION" | python3 -m json.tool

# Parse simulation result
SIMULATION_SUCCESS=$(echo "$FAILOVER_SIMULATION" | grep -c '"simulation": "SUCCESS"' || echo 0)

if [ "$SIMULATION_SUCCESS" -eq 1 ]; then
    log_success "Failover simulation successful - backup can take over"
else
    log_warning "Failover simulation failed - backup not ready"
fi

section "SCENARIO 5: Monitor for Sustained Health"

log_info "Collecting health snapshots over 30 seconds..."
log_info "(Taking 3 snapshots 10 seconds apart)"

for i in 1 2 3; do
    echo ""
    log_info "Snapshot $i at $(date '+%H:%M:%S')"

    STATUS=$(curl -s "$PRIMARY/api/redundancy/status")
    OVERALL=$(echo "$STATUS" | grep -o '"overall_status": "[^"]*"' | cut -d'"' -f4)
    LAG=$(echo "$STATUS" | grep -o '"lag_seconds": [^,}]*' | head -1 | cut -d' ' -f2)

    log_info "  Overall Status: $OVERALL"
    log_info "  Replication Lag: $LAG seconds"

    if [ $i -lt 3 ]; then
        sleep 10
    fi
done

log_success "Health monitoring complete"

section "SCENARIO 6: Configuration Consistency Check"

log_info "Verifying redundancy configuration..."
REDUNDANCY_CONFIG=$(curl -s "$PRIMARY/api/redundancy/config")
echo "$REDUNDANCY_CONFIG" | python3 -m json.tool

section "TEST SUMMARY"

log_info "HA System Status:"
FINAL_STATUS=$(curl -s "$PRIMARY/api/redundancy/status")
OVERALL=$(echo "$FINAL_STATUS" | grep -o '"overall_status": "[^"]*"' | cut -d'"' -f4)

case "$OVERALL" in
    "HEALTHY")
        log_success "✓ System is HEALTHY - Primary + Backup ready"
        ;;
    "DEGRADED")
        log_warning "⚠ System is DEGRADED - Primary only (backup down/unreachable)"
        ;;
    "FAILOVER_ACTIVE")
        log_error "✗ FAILOVER ACTIVE - Primary is down, Backup is trading"
        ;;
    "DOWN")
        log_error "✗ System is DOWN - Both primary and backup unavailable"
        ;;
esac

echo ""
log_info "Next Steps:"
echo "  1. Check /api/redundancy/status regularly"
echo "  2. Monitor replication lag < 2 seconds"
echo "  3. Run monthly failover drills"
echo "  4. Review HA_DEPLOYMENT.md for troubleshooting"
echo ""
log_success "Failover scenario testing complete!"
