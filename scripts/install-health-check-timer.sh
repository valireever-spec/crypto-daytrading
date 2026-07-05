#!/bin/bash
# Installation script for 15-minute health check timer
# Run this with sudo: sudo bash scripts/install-health-check-timer.sh

set -e

echo "📦 Installing 15-minute health check timer..."

# Create service file
cat > /etc/systemd/system/crypto-health-check.service << 'SVCEOF'
[Unit]
Description=Crypto Trading HA Health Check (15-minute)
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=vali
WorkingDirectory=/home/vali/projects/crypto-daytrading
ExecStart=/home/vali/projects/crypto-daytrading/venv/bin/python3 /home/vali/projects/crypto-daytrading/scripts/health_check_15min.py
StandardOutput=journal
StandardError=journal
SyslogIdentifier=crypto-health-check
SVCEOF

# Create timer file
cat > /etc/systemd/system/crypto-health-check.timer << 'TIMEREOF'
[Unit]
Description=Crypto Trading HA Health Check Timer (every 15 minutes)
Requires=crypto-health-check.service

[Timer]
OnBootSec=1min
OnUnitActiveSec=15min
AccuracySec=30s

[Install]
WantedBy=timers.target
TIMEREOF

# Reload systemd daemon
systemctl daemon-reload

# Enable and start the timer
systemctl enable crypto-health-check.timer
systemctl start crypto-health-check.timer

echo "✅ Health check timer installed and started"
echo ""
echo "To check status:"
echo "  systemctl status crypto-health-check.timer"
echo "  systemctl list-timers crypto-health-check.timer"
echo ""
echo "To view recent checks:"
echo "  journalctl -u crypto-health-check.service -n 100 -f"
echo ""
echo "To manually trigger a check:"
echo "  systemctl start crypto-health-check.service"
