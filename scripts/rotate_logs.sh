#!/bin/bash
# Log rotation and archival script with failure notifications
# Implements: RETENTION_POLICY.md
#
# Runs daily (cron: 0 2 * * *) to:
# 1. Archive trades older than 3 years (1095 days)
# 2. Clean up SQLite database (remove archived trades)
# 3. Verify archive integrity
# 4. Clean up rotated logs
# 5. Alert on failures

set -e
trap 'on_error' ERR

PROJECT_DIR="/home/vali/projects/crypto-daytrading"
cd "$PROJECT_DIR"

# Activate venv
source venv/bin/activate

LOG_FILE="logs/rotation.log"
DATE=$(date '+%Y-%m-%d %H:%M:%S')
ARCHIVE_DAYS=1095  # 3 years

on_error() {
    local exit_code=$?
    echo "[$DATE] ❌ ERROR: Archive script failed (exit code: $exit_code)" >> "$LOG_FILE"

    # Send failure notification
    if [ -n "$SLACK_WEBHOOK" ]; then
        curl -X POST "$SLACK_WEBHOOK" \
            -H 'Content-Type: application/json' \
            -d "{\"text\":\"❌ Crypto trading retention policy failed: $(tail -1 $LOG_FILE)\"}" \
            2>/dev/null || true
    fi

    exit "$exit_code"
}

echo "[$DATE] ========== Starting retention policy rotation ==========" >> "$LOG_FILE"

# Validation: Check if cutoff date is reasonable
CUTOFF_DATE=$(date -d "-${ARCHIVE_DAYS} days" '+%Y-%m-%d' 2>/dev/null || date -v-${ARCHIVE_DAYS}d '+%Y-%m-%d' 2>/dev/null || echo "ERROR")
if [ "$CUTOFF_DATE" = "ERROR" ]; then
    echo "[$DATE] ERROR: Failed to calculate cutoff date" >> "$LOG_FILE"
    on_error
fi
echo "[$DATE] Cutoff date: $CUTOFF_DATE (archiving trades before this date)" >> "$LOG_FILE"

# 1. Archive trades older than 3 years AND cleanup SQLite
echo "[$DATE] Starting archive and cleanup (days: $ARCHIVE_DAYS)..." >> "$LOG_FILE"
if python3 scripts/archive_and_cleanup_db.py --days "$ARCHIVE_DAYS" >> "$LOG_FILE" 2>&1; then
    echo "[$DATE] ✅ Archive and cleanup succeeded" >> "$LOG_FILE"
else
    echo "[$DATE] ❌ Archive and cleanup failed" >> "$LOG_FILE"
    on_error
fi

# 2. Verify integrity
echo "[$DATE] Verifying archive integrity..." >> "$LOG_FILE"
if python3 scripts/verify_archive.py --all >> "$LOG_FILE" 2>&1; then
    echo "[$DATE] ✅ Verification passed" >> "$LOG_FILE"
else
    echo "[$DATE] ⚠️  Verification detected issues (see above)" >> "$LOG_FILE"
    # Don't exit - verification issues are warnings
fi

# 3. Rotate this log if it gets too large (>10MB)
if [ -f "$LOG_FILE" ]; then
    SIZE=0
    if [ "$(uname)" = "Darwin" ]; then
        SIZE=$(stat -f%z "$LOG_FILE" 2>/dev/null || echo 0)
    else
        SIZE=$(stat -c%s "$LOG_FILE" 2>/dev/null || echo 0)
    fi

    if [ "$SIZE" -gt 10485760 ]; then
        ROTATED_FILE="${LOG_FILE}.$(date +%Y%m%d)"
        echo "[$DATE] Rotating log (size: $SIZE bytes)" >> "$LOG_FILE"
        mv "$LOG_FILE" "$ROTATED_FILE"
        gzip "$ROTATED_FILE" 2>/dev/null || {
            echo "[$DATE] WARNING: Failed to gzip rotated log" >> "$LOG_FILE"
        }
    fi
fi

echo "[$DATE] Log rotation complete" >> "$LOG_FILE"
