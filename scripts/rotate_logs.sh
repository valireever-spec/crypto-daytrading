#!/bin/bash
# Log rotation and archival script
# Implements: RETENTION_POLICY.md
#
# Runs daily to:
# 1. Archive trades older than 3 years (1095 days)
# 2. Verify archive integrity
# 3. Clean up rotated logs

set -e

PROJECT_DIR="/home/vali/projects/crypto-daytrading"
cd "$PROJECT_DIR"

# Activate venv
source venv/bin/activate

LOG_FILE="logs/rotation.log"
DATE=$(date '+%Y-%m-%d %H:%M:%S')

echo "[$DATE] Starting log rotation" >> "$LOG_FILE"

# 1. Archive trades older than 3 years
echo "[$DATE] Archiving trades older than 1095 days..." >> "$LOG_FILE"
python3 scripts/archive_old_trades.py --days 1095 >> "$LOG_FILE" 2>&1 || {
    echo "[$DATE] ERROR: Archive failed" >> "$LOG_FILE"
    exit 1
}

# 2. Verify integrity
echo "[$DATE] Verifying archive integrity..." >> "$LOG_FILE"
python3 scripts/verify_archive.py --all >> "$LOG_FILE" 2>&1 || {
    echo "[$DATE] WARNING: Verification detected issues" >> "$LOG_FILE"
}

# 3. Rotate this log if it gets too large (>10MB)
if [ -f "$LOG_FILE" ]; then
    SIZE=$(stat -f%z "$LOG_FILE" 2>/dev/null || stat -c%s "$LOG_FILE" 2>/dev/null || echo 0)
    if [ $SIZE -gt 10485760 ]; then
        mv "$LOG_FILE" "${LOG_FILE}.$(date +%Y%m%d)"
        gzip "${LOG_FILE}".* 2>/dev/null || true
    fi
fi

echo "[$DATE] Log rotation complete" >> "$LOG_FILE"
