#!/bin/bash
# Simple Debian Backup Deployment - Copy from local machine
set -e

DEBIAN_HOST="${1:-192.168.3.25}"
DEBIAN_USER="${2:-claude}"
PRIMARY_HOST="${3:-192.168.30.137}"
PRIMARY_PORT="${4:-8001}"
BACKUP_PORT="8002"

BACKUP_DIR="/home/${DEBIAN_USER}/crypto-daytrading"
LOCAL_DIR="$(pwd)"

echo "═══════════════════════════════════════════════════════════════════════════════"
echo "🚀 SIMPLE DEBIAN BACKUP DEPLOYMENT"
echo "═══════════════════════════════════════════════════════════════════════════════"
echo ""
echo "Debian: $DEBIAN_HOST ($DEBIAN_USER)"
echo "Primary: $PRIMARY_HOST:$PRIMARY_PORT"
echo "Local copy from: $LOCAL_DIR"
echo ""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# [1/7] SSH Connectivity
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

echo "[1/7] Verifying SSH connectivity..."
if ssh "${DEBIAN_USER}@${DEBIAN_HOST}" "echo OK" > /dev/null 2>&1; then
    echo "✅ SSH OK"
else
    echo "❌ SSH failed to $DEBIAN_HOST"
    exit 1
fi

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# [2/7] Install Dependencies
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

echo "[2/7] Installing dependencies..."
ssh "${DEBIAN_USER}@${DEBIAN_HOST}" "
sudo apt-get update -qq
sudo apt-get install -y -qq python3 python3-venv python3-pip curl jq
" 2>&1 | grep -v "^[WD]:" || true
echo "✅ Dependencies installed"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# [3/7] Copy Repository
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

echo "[3/7] Copying repository to Debian..."

# Remove old directory if exists
ssh "${DEBIAN_USER}@${DEBIAN_HOST}" "rm -rf $BACKUP_DIR" 2>/dev/null || true

# Copy entire project
rsync -avz --exclude='.git' --exclude='venv' --exclude='__pycache__' \
    --exclude='.pytest_cache' --exclude='logs' --exclude='*.pyc' \
    "$LOCAL_DIR/" "${DEBIAN_USER}@${DEBIAN_HOST}:${BACKUP_DIR}/"

echo "✅ Repository copied"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# [4/7] Python Environment
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

echo "[4/7] Setting up Python environment..."
ssh "${DEBIAN_USER}@${DEBIAN_HOST}" "
cd '$BACKUP_DIR'
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip setuptools wheel -q
pip install -r requirements.txt -q
"
echo "✅ Python ready"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# [5/7] Configure .env
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

echo "[5/7] Configuring .env..."
ssh "${DEBIAN_USER}@${DEBIAN_HOST}" "
cat > '$BACKUP_DIR/.env' << 'ENVEOF'
BINANCE_TESTNET=false
LOG_LEVEL=INFO
API_HOST=0.0.0.0
API_PORT=$BACKUP_PORT
BACKUP_MODE=true
TRADING_MODE=paper
PRIMARY_API_URL=http://$PRIMARY_HOST:$PRIMARY_PORT
HEARTBEAT_INTERVAL=10
ENVEOF
"
echo "✅ .env configured"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# [6/7] Systemd Services
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

echo "[6/7] Installing systemd services..."

# Backup Trader Service
ssh "${DEBIAN_USER}@${DEBIAN_HOST}" "
sudo tee /etc/systemd/system/backup-trader.service > /dev/null << 'SVCEOF'
[Unit]
Description=Crypto Daytrading Backup (Standby)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$DEBIAN_USER
WorkingDirectory=$BACKUP_DIR
Environment=\"PYTHONPATH=$BACKUP_DIR\"
EnvironmentFile=$BACKUP_DIR/.env
ExecStart=$BACKUP_DIR/venv/bin/uvicorn backend.api.main:app --host 0.0.0.0 --port $BACKUP_PORT
Restart=on-failure
RestartSec=10
MemoryMax=4G
CPUQuota=150%
StandardOutput=journal
StandardError=journal
SyslogIdentifier=backup-trader

[Install]
WantedBy=multi-user.target
SVCEOF
"

# Failover Monitor Service
ssh "${DEBIAN_USER}@${DEBIAN_HOST}" "
sudo tee /etc/systemd/system/failover-monitor.service > /dev/null << 'SVCEOF'
[Unit]
Description=Crypto Failover Monitor
After=backup-trader.service
StartLimitInterval=300
StartLimitBurst=3

[Service]
Type=simple
User=$DEBIAN_USER
WorkingDirectory=$BACKUP_DIR
ExecStart=$BACKUP_DIR/venv/bin/python $BACKUP_DIR/scripts/failover_monitor.py $PRIMARY_HOST $PRIMARY_PORT
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=failover-monitor

[Install]
WantedBy=multi-user.target
SVCEOF
"

# Create logs directory
ssh "${DEBIAN_USER}@${DEBIAN_HOST}" "mkdir -p '$BACKUP_DIR/logs'"

# Reload and enable
ssh "${DEBIAN_USER}@${DEBIAN_HOST}" "
sudo systemctl daemon-reload
sudo systemctl enable backup-trader failover-monitor
"

echo "✅ Services installed"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# [7/7] Start Services
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

echo "[7/7] Starting services..."
ssh "${DEBIAN_USER}@${DEBIAN_HOST}" "
sudo systemctl start backup-trader
sudo systemctl start failover-monitor
sleep 3
sudo systemctl status backup-trader --no-pager | head -5
"

echo "✅ Services started"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Verify
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

echo ""
echo "Verifying deployment..."
sleep 5

HEALTH=$(curl -s "http://$DEBIAN_HOST:$BACKUP_PORT/api/health" 2>/dev/null || echo "")

if echo "$HEALTH" | grep -q "ok"; then
    echo "✅ Backup trader ONLINE"
    echo "$HEALTH" | jq . 2>/dev/null || echo "$HEALTH"
else
    echo "⚠️  Checking status..."
    ssh "${DEBIAN_USER}@${DEBIAN_HOST}" "
    echo '=== Backup Trader ==='
    sudo systemctl status backup-trader --no-pager | head -10
    echo ''
    echo '=== Failover Monitor ==='
    sudo systemctl status failover-monitor --no-pager | head -10
    echo ''
    echo '=== Logs ==='
    journalctl -u backup-trader -n 10 --no-pager 2>/dev/null || echo '(no logs yet)'
    "
fi

echo ""
echo "═══════════════════════════════════════════════════════════════════════════════"
echo "✅ DEPLOYMENT COMPLETE"
echo "═══════════════════════════════════════════════════════════════════════════════"
echo ""
echo "Configuration:"
echo "  Debian:  $DEBIAN_HOST:$BACKUP_PORT"
echo "  Primary: $PRIMARY_HOST:$PRIMARY_PORT"
echo ""
echo "Test the deployment:"
echo "  curl http://$DEBIAN_HOST:$BACKUP_PORT/api/health"
echo ""
echo "Monitor logs:"
echo "  ssh $DEBIAN_USER@$DEBIAN_HOST journalctl -u backup-trader -f"
echo "  ssh $DEBIAN_USER@$DEBIAN_HOST journalctl -u failover-monitor -f"
echo ""
echo "Test failover (from this machine):"
echo "  sudo systemctl stop crypto-daytrading"
echo "  sleep 35"
echo "  curl http://$DEBIAN_HOST:$BACKUP_PORT/api/health"
echo ""
echo "═══════════════════════════════════════════════════════════════════════════════"
