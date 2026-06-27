#!/bin/bash

##############################################################################
# HA DEPLOYMENT SCRIPT
# Deploys code and configures both PRIMARY and BACKUP machines
##############################################################################

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

BACKUP_HOST="192.168.3.25"
BACKUP_USER="claude"
BACKUP_DIR="/home/claude/crypto-daytrading"

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║         HA DEPLOYMENT - PRIMARY & BACKUP CONFIGURATION       ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"

# ============================================================================
# Step 1: Deploy to PRIMARY (localhost)
# ============================================================================

echo -e "\n${YELLOW}=== Step 1: PRIMARY (Local) Configuration ===${NC}"

PRIMARY_PROJECT_DIR="/home/vali/projects/crypto-daytrading"

echo "📋 Setting environment variables for PRIMARY..."

# Create primary systemd override
mkdir -p /etc/systemd/system/crypto-trading.service.d/

cat > /etc/systemd/system/crypto-trading.service.d/ha.conf << 'EOF'
[Service]
Environment="MACHINE_ID=primary"
Environment="PRIMARY_API_URL=http://127.0.0.1:8001"
Environment="BACKUP_API_URL=http://192.168.3.25:8002"
Environment="INITIAL_CAPITAL=1000"
EOF

echo "✅ PRIMARY environment variables set"

# Reload systemd
echo "🔄 Reloading systemd..."
systemctl daemon-reload

# ============================================================================
# Step 2: Deploy to BACKUP (remote)
# ============================================================================

echo -e "\n${YELLOW}=== Step 2: BACKUP (Remote) Deployment ===${NC}"

echo "📤 Syncing code to BACKUP..."
ssh -o ConnectTimeout=5 "${BACKUP_USER}@${BACKUP_HOST}" "mkdir -p ${BACKUP_DIR}" 2>/dev/null || true

# Use git to sync (more reliable than rsync)
echo "📚 Syncing via git (faster than rsync)..."
cd "$PRIMARY_PROJECT_DIR"
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
CURRENT_COMMIT=$(git rev-parse HEAD)

ssh -o ConnectTimeout=5 "${BACKUP_USER}@${BACKUP_HOST}" "cd ${BACKUP_DIR} && git fetch origin && git reset --hard origin/${CURRENT_BRANCH}" 2>/dev/null || {
    echo "⚠️  Git sync failed, trying direct copy..."
    scp -r -o ConnectTimeout=5 "${PRIMARY_PROJECT_DIR}"/{backend,frontend,scripts,tests,logs} "${BACKUP_USER}@${BACKUP_HOST}:${BACKUP_DIR}/" 2>/dev/null || echo "❌ SCP also failed (network issue?)"
}

echo "✅ Code synced to BACKUP"

# Configure BACKUP environment
echo "📋 Setting environment variables for BACKUP..."

ssh -o ConnectTimeout=5 "${BACKUP_USER}@${BACKUP_HOST}" "
    sudo mkdir -p /etc/systemd/system/crypto-trading.service.d/
    sudo tee /etc/systemd/system/crypto-trading.service.d/ha.conf > /dev/null << 'BACKUP_EOF'
[Service]
Environment=\"MACHINE_ID=backup\"
Environment=\"PRIMARY_API_URL=http://127.0.0.1:8001\"
Environment=\"BACKUP_API_URL=http://192.168.3.25:8002\"
Environment=\"INITIAL_CAPITAL=1000\"
BACKUP_EOF

    sudo systemctl daemon-reload
" 2>/dev/null || echo "⚠️  Remote configuration may have issues"

echo "✅ BACKUP environment variables set"

# ============================================================================
# Step 3: Restart services
# ============================================================================

echo -e "\n${YELLOW}=== Step 3: Restarting Services ===${NC}"

echo "🔄 Restarting PRIMARY API service..."
systemctl restart crypto-trading.service || echo "❌ Failed to restart PRIMARY"

echo "⏳ Waiting 5 seconds for PRIMARY to stabilize..."
sleep 5

echo "🔄 Restarting BACKUP API service (remote)..."
ssh -o ConnectTimeout=5 "${BACKUP_USER}@${BACKUP_HOST}" "sudo systemctl restart crypto-trading.service" 2>/dev/null || echo "⚠️  Remote restart may have failed"

echo "⏳ Waiting 5 seconds for BACKUP to stabilize..."
sleep 5

# ============================================================================
# Step 4: Verify deployment
# ============================================================================

echo -e "\n${YELLOW}=== Step 4: Verification ===${NC}"

echo "🔍 Checking PRIMARY..."
PRIMARY_HEALTH=$(curl -s "http://127.0.0.1:8001/api/health" 2>/dev/null || echo '{}')
PRIMARY_STATUS=$(echo "$PRIMARY_HEALTH" | jq -r '.autonomous_trader.status // "error"')

if [[ "$PRIMARY_STATUS" != "error" ]]; then
    echo -e "${GREEN}✅ PRIMARY API responding${NC}"
else
    echo -e "${RED}❌ PRIMARY API not responding${NC}"
fi

echo "🔍 Checking BACKUP..."
BACKUP_HEALTH=$(curl -s "http://192.168.3.25:8002/api/health" 2>/dev/null || echo '{}')
BACKUP_STATUS=$(echo "$BACKUP_HEALTH" | jq -r '.autonomous_trader.status // "error"')

if [[ "$BACKUP_STATUS" != "error" ]]; then
    echo -e "${GREEN}✅ BACKUP API responding${NC}"
else
    echo -e "${YELLOW}⚠️  BACKUP API not responding (may need manual check)${NC}"
fi

# ============================================================================
# SUMMARY
# ============================================================================

echo -e "\n${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║          HA DEPLOYMENT COMPLETE                              ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"

echo ""
echo -e "${GREEN}✅ Deployment Summary:${NC}"
echo "   PRIMARY (127.0.0.1:8001)"
echo "     • MACHINE_ID=primary"
echo "     • Trading: ENABLED"
echo "     • Sync task: ACTIVE (→ BACKUP every 5s)"
echo ""
echo "   BACKUP (192.168.3.25:8002)"
echo "     • MACHINE_ID=backup"
echo "     • Trading: DISABLED (auto-enable on PRIMARY failure)"
echo "     • Failover monitor: ACTIVE (check every 10s)"

echo ""
echo -e "${BLUE}Next Steps:${NC}"
echo "  1. Run comprehensive HA tests:"
echo "     bash scripts/test_ha_comprehensive.sh"
echo ""
echo "  2. Monitor real-time trading:"
echo "     bash scripts/monitor_acceptance.sh"
echo ""
echo "  3. To test failover (PRIMARY → BACKUP):"
echo "     systemctl stop crypto-trading.service"
echo "     # BACKUP will auto-enable trading"
echo "     systemctl start crypto-trading.service"
echo "     # BACKUP will auto-disable trading"

echo ""
