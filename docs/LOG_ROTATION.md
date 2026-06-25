# Log Rotation & Archival Policy

**Updated:** 2026-06-25  
**Phase:** 1 (Paper Trading)

## Overview

Phase 1 generates ~500KB-1MB of logs per day. Without rotation, disk space exhaustion risk after 30+ days.

## Log Files

| File | Growth Rate | Max Size | Action |
|------|-----------|----------|--------|
| `logs/trades.jsonl` | ~100KB/day | 100MB | Archive & compress |
| `logs/system.log` | ~50KB/day | 50MB | Delete after 30 days |
| `logs/immutable/` | ~10KB/day | 20MB | Keep all (audit) |

## Automatic Rotation (Phase 2)

Python `logging.handlers.RotatingFileHandler`:
```python
from logging.handlers import RotatingFileHandler

handler = RotatingFileHandler(
    'logs/system.log',
    maxBytes=50*1024*1024,  # 50MB
    backupCount=10,          # Keep 10 rotated files
)
```

## Manual Rotation (Phase 1)

Run weekly or when log size >50MB:

### Archive Old Trades
```bash
# Compress trades older than 7 days
tar czf logs/archive/trades-$(date -d '7 days ago' +%Y%m%d).tar.gz \
  logs/trades.jsonl.* 2>/dev/null || true

# Keep only last 1000 lines (recent trades)
tail -1000 logs/trades.jsonl > logs/trades.tmp
mv logs/trades.tmp logs/trades.jsonl
```

### Clean Up System Logs
```bash
# Delete system logs older than 30 days
find logs -name "system.log*" -mtime +30 -delete

# Or compress and archive
gzip logs/system.log.*
mkdir -p logs/archive
mv logs/system.log.*.gz logs/archive/
```

### Check Disk Usage
```bash
du -sh logs/
df -h /  # Check filesystem

# If >80% full
du -sh logs/* | sort -h | tail -10
# Archive or delete large files
```

## Automated Script (Phase 1)

Create `scripts/rotate-logs.sh`:

```bash
#!/bin/bash
set -e

LOGS_DIR="/home/vali/projects/crypto-daytrading/logs"
ARCHIVE_DIR="${LOGS_DIR}/archive"
MAX_LOG_SIZE=$((50 * 1024 * 1024))  # 50MB
MAX_DISK_USAGE=0.85  # 85%

# Create archive directory
mkdir -p "${ARCHIVE_DIR}"

# Check disk usage
DISK_USED=$(df / | tail -1 | awk '{print $5}' | tr -d '%')
if [ "$DISK_USED" -gt 85 ]; then
    echo "⚠️ Disk usage high: ${DISK_USED}%"
    # Archive trades older than 7 days
    find "${LOGS_DIR}" -name "trades.jsonl*" -mtime +7 -exec \
        gzip {} \; -exec \
        mv {} "${ARCHIVE_DIR}/" \;
fi

# Archive trades log if >50MB
if [ -f "${LOGS_DIR}/trades.jsonl" ]; then
    SIZE=$(stat -f%z "${LOGS_DIR}/trades.jsonl" 2>/dev/null || stat -c%s "${LOGS_DIR}/trades.jsonl")
    if [ "$SIZE" -gt "$MAX_LOG_SIZE" ]; then
        echo "📦 Archiving trades.jsonl (${SIZE} bytes)"
        gzip -c "${LOGS_DIR}/trades.jsonl" > \
            "${ARCHIVE_DIR}/trades-$(date +%Y%m%d-%H%M%S).jsonl.gz"
        # Keep last 1000 lines
        tail -1000 "${LOGS_DIR}/trades.jsonl" > "${LOGS_DIR}/trades.tmp"
        mv "${LOGS_DIR}/trades.tmp" "${LOGS_DIR}/trades.jsonl"
    fi
fi

# Remove old system logs (>30 days)
find "${LOGS_DIR}" -name "system.log*" -mtime +30 -delete

echo "✅ Log rotation complete"
```

Run manually:
```bash
bash scripts/rotate-logs.sh
```

Or schedule with cron (Phase 2):
```bash
0 2 * * 0  # Every Sunday at 2 AM
/home/vali/projects/crypto-daytrading/scripts/rotate-logs.sh >> /var/log/crypto-rotate.log 2>&1
```

## Immutable Logs (DO NOT TOUCH)

Files in `logs/immutable/`:
- **NEVER** delete
- **NEVER** modify
- **NEVER** compress
- These are audit trail for compliance

These are append-only and protected by database triggers.

## Retention Policy

| Log Type | Retention | Backup |
|----------|-----------|--------|
| Trades (trades.jsonl) | 90 days | Yes (archive/compress) |
| System logs | 30 days | No |
| Immutable (audit) | Forever | Yes (daily) |
| Incidents (incidents.jsonl) | Forever | Yes (daily) |

## Phase 1 Action

Run rotation script weekly:
```bash
# Every Sunday
bash scripts/rotate-logs.sh
```

Or set reminder in calendar.

## Monitoring

Alert if:
- `logs/` exceeds 500MB
- Disk usage exceeds 80%
- Archive directory exceeds 1GB

Check weekly:
```bash
du -sh logs/
du -sh logs/archive/
df -h /
```

## Phase 2: Automated Rotation

Implement `logging.handlers.RotatingFileHandler`:
```python
# backend/core/structured_logging.py
handler = RotatingFileHandler(
    'logs/system.log',
    maxBytes=50*1024*1024,   # 50MB
    backupCount=10,           # 500MB total
)
```

Cron job:
```
0 2 * * 0  /usr/local/bin/crypto-rotate-logs.sh
```

## Recovery from Full Disk

If disk gets full:
1. Stop API: `pkill -f uvicorn`
2. Archive trades: `gzip logs/trades.jsonl*`
3. Delete system logs: `rm logs/system.log*`
4. Verify: `df -h /`
5. Restart API: `python -m uvicorn ...`

**Note:** Never delete `logs/immutable/` or database files.

---

**Last Updated:** 2026-06-25  
**Next Review:** 2026-07-01
