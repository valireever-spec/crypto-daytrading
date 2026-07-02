#!/bin/bash
# Setup cron job for automated retention policy rotation
# Run this once to configure automated archival
#
# Usage: bash scripts/setup_cron.sh

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$PROJECT_DIR/scripts/rotate_logs.sh"

# Verify script exists
if [ ! -f "$SCRIPT" ]; then
    echo "❌ Script not found: $SCRIPT"
    exit 1
fi

# Make script executable
chmod +x "$SCRIPT"
echo "✅ Made executable: $SCRIPT"

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "rotate_logs.sh"; then
    echo "⚠️  Cron job already configured"
    echo ""
    echo "Current cron entry:"
    crontab -l | grep "rotate_logs.sh"
    exit 0
fi

# Add cron job: Run daily at 02:00 UTC
CRON_CMD="0 2 * * * $SCRIPT"

# Create temporary crontab file
TEMP_CRON=$(mktemp)
crontab -l 2>/dev/null > "$TEMP_CRON" || true
echo "$CRON_CMD" >> "$TEMP_CRON"

# Install new crontab
crontab "$TEMP_CRON"
rm "$TEMP_CRON"

echo "✅ Cron job configured:"
echo "   Schedule: 0 2 * * * (daily at 02:00 UTC)"
echo "   Command: $SCRIPT"
echo ""
echo "Verify installation:"
echo "   crontab -l | grep rotate_logs"
