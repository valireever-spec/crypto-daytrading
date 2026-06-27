#!/bin/bash
# Cleanup BACKUP disk space (run on BACKUP machine)
# Run this on BACKUP (192.168.3.25) with sudo access

set -e

echo "=== BACKUP Disk Cleanup ==="
echo ""

BACKUP_PATH="/home/claude/crypto-daytrading"

if [ ! -d "$BACKUP_PATH" ]; then
    echo "❌ Directory not found: $BACKUP_PATH"
    exit 1
fi

cd "$BACKUP_PATH"

echo "Stopping trading services..."
systemctl stop crypto-trading crypto-failover-monitor 2>/dev/null || true

echo "Clearing old logs..."
cd logs
rm -f *.20260624.gz *.20260625.gz
rm -f api.log trades.jsonl failover_monitor.log system.log
rm -f *.log.*.gz  # Remove all rotated logs

echo "Clearing Python cache..."
cd "$BACKUP_PATH"
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find . -type f -name '*.pyc' -delete 2>/dev/null || true

echo "Clearing pytest cache..."
rm -rf .pytest_cache .mypy_cache

echo "Clearing venv (if needed)..."
# Uncomment to rebuild venv
# rm -rf venv
# python3 -m venv venv
# source venv/bin/activate
# pip install -r requirements.txt

echo ""
echo "Restarting services..."
systemctl start crypto-trading crypto-failover-monitor 2>/dev/null || true

echo ""
echo "✅ Cleanup complete!"
echo ""
echo "Disk usage:"
df -h /
echo ""
echo "BACKUP project size:"
du -sh "$BACKUP_PATH"
