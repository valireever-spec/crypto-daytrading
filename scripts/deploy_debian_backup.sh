#!/bin/bash
# Deploy Crypto Daytrading Bot to Debian Backup Machine
# This script sets up complete HA with automatic failover

set -e

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

# Update these with your actual machine details
DEBIAN_HOST="${1:-192.168.3.204}"           # Debian machine IP
DEBIAN_USER="${2:-trader}"                  # SSH user on Debian
PRIMARY_HOST="${3:-192.168.30.137}"         # Primary machine IP
PRIMARY_PORT="${4:-8001}"                   # Primary API port

# Paths
REPO_URL="https://github.com/yourusername/crypto-daytrading.git"  # Update this
BACKUP_DIR="/home/${DEBIAN_USER}/crypto-daytrading"
BACKUP_PORT="8002"

echo "═══════════════════════════════════════════════════════════════════════════════"
echo "🚀 CRYPTO DAYTRADING - DEBIAN BACKUP DEPLOYMENT"
echo "═══════════════════════════════════════════════════════════════════════════════"
echo ""
echo "Configuration:"
echo "  Debian machine: $DEBIAN_HOST"
echo "  SSH user: $DEBIAN_USER"
echo "  Primary machine: $PRIMARY_HOST:$PRIMARY_PORT"
echo "  Backup port: $BACKUP_PORT"
echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

ssh_cmd() {
    # Execute command on Debian via SSH
    ssh "${DEBIAN_USER}@${DEBIAN_HOST}" "$@"
}

scp_cmd() {
    # Copy file to Debian via SCP
    scp "$1" "${DEBIAN_USER}@${DEBIAN_HOST}:$2"
}

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 1: Verify connectivity
# ═══════════════════════════════════════════════════════════════════════════════

echo "[1/10] Verifying SSH connectivity..."
if ssh_cmd "echo 'OK'" > /dev/null 2>&1; then
    echo "✅ SSH connection successful"
else
    echo "❌ Cannot connect to $DEBIAN_HOST via SSH"
    echo "   Check: IP address, SSH key, firewall"
    exit 1
fi

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 2: Install dependencies
# ═══════════════════════════════════════════════════════════════════════════════

echo ""
echo "[2/10] Installing dependencies on Debian..."
ssh_cmd "sudo apt update && sudo apt install -y python3 python3-venv python3-pip git postgresql-client postgresql curl jq"
echo "✅ Dependencies installed"

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 3: Clone repository
# ═══════════════════════════════════════════════════════════════════════════════

echo ""
echo "[3/10] Cloning repository..."
ssh_cmd "
if [ ! -d '$BACKUP_DIR' ]; then
    git clone '$REPO_URL' '$BACKUP_DIR'
    echo 'Repository cloned'
else
    cd '$BACKUP_DIR' && git pull origin master
    echo 'Repository updated'
fi
"
echo "✅ Repository ready"

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 4: Set up Python environment
# ═══════════════════════════════════════════════════════════════════════════════

echo ""
echo "[4/10] Setting up Python virtual environment..."
ssh_cmd "
cd '$BACKUP_DIR'
if [ ! -d 'venv' ]; then
    python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip setuptools wheel
    pip install -r requirements.txt
    echo 'Virtual environment created'
else
    source venv/bin/activate
    pip install -r requirements.txt
    echo 'Virtual environment updated'
fi
"
echo "✅ Python environment ready"

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 5: Configure .env for backup
# ═══════════════════════════════════════════════════════════════════════════════

echo ""
echo "[5/10] Configuring environment variables..."
ssh_cmd "
cat > '$BACKUP_DIR/.env' << 'ENVEOF'
# Backup Trader Configuration
BINANCE_TESTNET=false
LOG_LEVEL=INFO
API_HOST=0.0.0.0
API_PORT=$BACKUP_PORT

# Backup mode
BACKUP_MODE=true
TRADING_MODE=paper

# Primary machine details
PRIMARY_API_URL=http://$PRIMARY_HOST:$PRIMARY_PORT

# Heartbeat monitoring
HEARTBEAT_INTERVAL=10
HEARTBEAT_TIMEOUT=30
FAILOVER_THRESHOLD=3

# Database (if using PostgreSQL replication)
DB_HOST=localhost
DB_PORT=5432
DB_NAME=crypto_db
DB_USER=trader
ENVEOF

echo '✅ .env configured'
"

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 6: Create backup trader systemd service
# ═══════════════════════════════════════════════════════════════════════════════

echo ""
echo "[6/10] Setting up backup trader systemd service..."
ssh_cmd "
sudo tee /etc/systemd/system/backup-trader.service > /dev/null << 'SVCEOF'
[Unit]
Description=Crypto Trading Backup Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$DEBIAN_USER
WorkingDirectory=$BACKUP_DIR
Environment=\"PYTHONPATH=$BACKUP_DIR\"
EnvironmentFile=-$BACKUP_DIR/.env
ExecStart=$BACKUP_DIR/venv/bin/uvicorn backend.api.main:app --host 0.0.0.0 --port $BACKUP_PORT
Restart=on-failure
RestartSec=10

# Resource limits
MemoryMax=4G
CPUQuota=150%

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=backup-trader

[Install]
WantedBy=multi-user.target
SVCEOF

sudo systemctl daemon-reload
echo '✅ Backup trader service created'
"

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 7: Create failover monitor service
# ═══════════════════════════════════════════════════════════════════════════════

echo ""
echo "[7/10] Setting up failover monitor..."

# Copy failover monitor script
cat > /tmp/failover_monitor.py << 'PYEOF'
#!/usr/bin/env python3
"""Monitor primary trader and trigger failover if needed."""

import requests
import subprocess
import time
import logging
from pathlib import Path
from datetime import datetime

log_dir = Path.home() / "crypto-daytrading/logs"
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / "failover_monitor.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

PRIMARY_URL = "http://{{PRIMARY_HOST}}:{{PRIMARY_PORT}}"
HEALTH_CHECK_INTERVAL = 10
FAILOVER_THRESHOLD = 3

class FailoverMonitor:
    def __init__(self):
        self.failure_count = 0
        self.is_failed_over = False

    def check_primary_health(self) -> bool:
        """Check if primary is healthy."""
        try:
            r = requests.get(f"{PRIMARY_URL}/api/health", timeout=5)
            return r.status_code == 200
        except Exception as e:
            logger.warning(f"Primary health check failed: {e}")
            return False

    def trigger_failover(self):
        """Activate backup trader."""
        logger.critical("🚨 FAILOVER TRIGGERED - Primary is down!")

        # Stop backup in standby mode
        subprocess.run(["sudo", "systemctl", "stop", "backup-trader"], check=False)

        # Wait for clean stop
        time.sleep(2)

        # Restart in active mode
        subprocess.run(["sudo", "systemctl", "start", "backup-trader"], check=True)

        self.is_failed_over = True
        logger.critical("✅ Backup trader is now ACTIVE")

    def check_primary_recovery(self):
        """Check if primary came back online."""
        if self.check_primary_health():
            if self.is_failed_over:
                logger.warning("⚠️  Primary is back online - backup continues trading")
                logger.warning("   To return control to primary, manually stop backup")
                # In active-passive: backup keeps trading until manually stopped
            return True
        return False

    def run(self):
        """Main monitoring loop."""
        logger.info("Failover monitor started")
        logger.info(f"Monitoring: {PRIMARY_URL}")
        logger.info(f"Health check interval: {HEALTH_CHECK_INTERVAL}s")
        logger.info(f"Failover threshold: {FAILOVER_THRESHOLD} missed checks (30s)")

        while True:
            try:
                if self.check_primary_health():
                    self.failure_count = 0
                    if not self.is_failed_over:
                        logger.info(f"Primary healthy - backup in standby")
                else:
                    self.failure_count += 1
                    logger.warning(f"Primary check #{self.failure_count} failed")

                    if self.failure_count >= FAILOVER_THRESHOLD:
                        self.trigger_failover()

                time.sleep(HEALTH_CHECK_INTERVAL)

            except Exception as e:
                logger.error(f"Monitor error: {e}")
                time.sleep(HEALTH_CHECK_INTERVAL)

if __name__ == "__main__":
    monitor = FailoverMonitor()
    monitor.run()
PYEOF

# Replace placeholders
sed -i "s|{{PRIMARY_HOST}}|$PRIMARY_HOST|g" /tmp/failover_monitor.py
sed -i "s|{{PRIMARY_PORT}}|$PRIMARY_PORT|g" /tmp/failover_monitor.py

# Copy to Debian
scp_cmd /tmp/failover_monitor.py "$BACKUP_DIR/scripts/failover_monitor.py"

# Create failover monitor service
ssh_cmd "
sudo tee /etc/systemd/system/failover-monitor.service > /dev/null << 'SVCEOF'
[Unit]
Description=Crypto Trader Failover Monitor
After=backup-trader.service

[Service]
Type=simple
User=$DEBIAN_USER
WorkingDirectory=$BACKUP_DIR
ExecStart=$BACKUP_DIR/venv/bin/python $BACKUP_DIR/scripts/failover_monitor.py
Restart=on-failure
RestartSec=10

StandardOutput=journal
StandardError=journal
SyslogIdentifier=failover-monitor

[Install]
WantedBy=multi-user.target
SVCEOF

chmod +x '$BACKUP_DIR/scripts/failover_monitor.py'
sudo systemctl daemon-reload
echo '✅ Failover monitor service created'
"

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 8: Create resource monitor
# ═══════════════════════════════════════════════════════════════════════════════

echo ""
echo "[8/10] Setting up resource monitor..."

# Copy existing resource monitor if available
if [ -f "scripts/resource_monitor.py" ]; then
    scp_cmd scripts/resource_monitor.py "$BACKUP_DIR/scripts/resource_monitor.py"

    ssh_cmd "
    sudo tee /etc/systemd/system/resource-monitor.service > /dev/null << 'SVCEOF'
[Unit]
Description=System Resource Monitor - Stops Backup Trader if Resources Low
After=network.target

[Service]
Type=simple
User=$DEBIAN_USER
WorkingDirectory=$BACKUP_DIR
ExecStart=$BACKUP_DIR/venv/bin/python $BACKUP_DIR/scripts/resource_monitor.py
Restart=on-failure
RestartSec=10

MemoryMax=500M
StandardOutput=journal
StandardError=journal
SyslogIdentifier=resource-monitor

[Install]
WantedBy=multi-user.target
SVCEOF

    chmod +x '$BACKUP_DIR/scripts/resource_monitor.py'
    sudo systemctl daemon-reload
    sudo systemctl enable resource-monitor
    sudo systemctl start resource-monitor
    echo '✅ Resource monitor deployed'
    "
else
    echo "⚠️  Resource monitor script not found (optional)"
fi

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 9: Enable and start services
# ═══════════════════════════════════════════════════════════════════════════════

echo ""
echo "[9/10] Starting backup trader services..."
ssh_cmd "
# Enable services on boot
sudo systemctl enable backup-trader
sudo systemctl enable failover-monitor

# Start services
sudo systemctl start backup-trader
sudo systemctl start failover-monitor

# Wait for startup
sleep 3

# Check status
echo '=== SERVICE STATUS ==='
sudo systemctl status backup-trader --no-pager | head -10
echo ''
sudo systemctl status failover-monitor --no-pager | head -10
"
echo "✅ Services started"

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 10: Verify deployment
# ═══════════════════════════════════════════════════════════════════════════════

echo ""
echo "[10/10] Verifying deployment..."

# Wait for backup trader to start
echo "Waiting for backup trader to start..."
sleep 5

# Test health endpoint
HEALTH_RESPONSE=$(curl -s "http://$DEBIAN_HOST:$BACKUP_PORT/api/health" 2>/dev/null || echo "")

if echo "$HEALTH_RESPONSE" | grep -q "ok"; then
    echo "✅ Backup trader is RUNNING and responding"
    echo ""
    echo "Health response:"
    echo "$HEALTH_RESPONSE" | jq . 2>/dev/null || echo "$HEALTH_RESPONSE"
else
    echo "⚠️  Backup trader may still be starting..."
    echo "   Check status with: ssh ${DEBIAN_USER}@${DEBIAN_HOST} sudo systemctl status backup-trader"
fi

# ═══════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════

echo ""
echo "═══════════════════════════════════════════════════════════════════════════════"
echo "✅ DEPLOYMENT COMPLETE"
echo "═══════════════════════════════════════════════════════════════════════════════"
echo ""
echo "Next steps:"
echo ""
echo "1. Verify backup trader is healthy:"
echo "   curl http://$DEBIAN_HOST:$BACKUP_PORT/api/health"
echo ""
echo "2. Monitor logs in real-time:"
echo "   ssh ${DEBIAN_USER}@${DEBIAN_HOST} journalctl -u backup-trader -f"
echo "   ssh ${DEBIAN_USER}@${DEBIAN_HOST} journalctl -u failover-monitor -f"
echo ""
echo "3. Check failover monitoring:"
echo "   ssh ${DEBIAN_USER}@${DEBIAN_HOST} tail -f ~/crypto-daytrading/logs/failover_monitor.log"
echo ""
echo "4. Test failover (from primary machine):"
echo "   sudo systemctl stop crypto-daytrading"
echo "   # Wait 30 seconds for backup to take over"
echo "   curl http://$DEBIAN_HOST:$BACKUP_PORT/api/health"
echo ""
echo "5. View account status:"
echo "   curl http://$DEBIAN_HOST:$BACKUP_PORT/api/paper/account"
echo ""
echo "Key configurations:"
echo "  Primary: $PRIMARY_HOST:$PRIMARY_PORT"
echo "  Backup: $DEBIAN_HOST:$BACKUP_PORT"
echo "  Failover timeout: 30 seconds"
echo "  Heartbeat check interval: 10 seconds"
echo ""
echo "Architecture:"
echo "  PRIMARY (Active) ──heartbeat──> BACKUP (Standby)"
echo "                                   └─ Auto-activates on failure"
echo "  Both share same trading strategy and risk parameters"
echo ""
echo "═══════════════════════════════════════════════════════════════════════════════"
