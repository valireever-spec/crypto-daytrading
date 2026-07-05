# Log Archival & Rotation Strategy

## Overview

This trading system implements **archive + rotate** strategy: logs are automatically rotated when they exceed size limits AND compressed with gzip to save disk space while maintaining compliance audit trails.

**Current disk savings:** ~90% (1 GB uncompressed → ~100 MB compressed)

## Two-Layer Approach

### Layer 1: Application-Level (Python)
**File:** `backend/core/log_archiver.py`

The `CompressedRotatingFileHandler` class automatically:
1. **Rotates** log files when they exceed size limits:
   - api.log: rotates at 100 MB
   - trades.jsonl: rotates at 50 MB
2. **Compresses** rotated files immediately with gzip
3. **Deletes** uncompressed files after successful compression
4. **Logs** compression events for observability

**Benefits:**
- Application controls rotation without external dependencies
- Compression happens immediately (no gap)
- Handles concurrent writes safely
- Backward compatible (no config changes)

### Layer 2: System-Level (logrotate)
**File:** `systemd/crypto-trading.logrotate`

System logrotate provides enterprise-grade log management:
1. **Size-based rotation** (100 MB api.log, 50 MB trades.jsonl)
2. **Time-based rotation** fallback (daily api.log, weekly trades.jsonl)
3. **Compression** immediately after rotation
4. **Retention policy** (30 days api.log, 90 days trades.jsonl)
5. **Automatic cleanup** of very old logs

## Setup Instructions

### Step 1: Enable Application-Level Compression (Already Done)

The Python code already uses `CompressedRotatingFileHandler`:

```python
# backend/core/structured_logging.py
api_handler = CompressedRotatingFileHandler(
    str(api_log),
    maxBytes=100 * 1024 * 1024,  # 100 MB
    backupCount=10,
)
```

✅ This is **already enabled** and working.

### Step 2: Install System-Level Logrotate (Optional but Recommended)

For production deployments, also set up system logrotate:

```bash
# Copy logrotate config to system
sudo cp systemd/crypto-trading.logrotate /etc/logrotate.d/crypto-trading

# Verify it's correct
sudo logrotate -v /etc/logrotate.d/crypto-trading
```

**What this does:**
- Runs `logrotate` daily (system cron)
- Rotates logs at 100 MB (api) or 50 MB (trades)
- Compresses rotated files with gzip
- Keeps logs for 30-90 days
- Automatically deletes very old logs

## Retention Policy

| Log Type | Max Size | Backup Count | Compressed? | Total Space |
|----------|----------|--------------|-------------|-------------|
| api.log | 100 MB | 10 → 30 days | ✅ Yes | ~100 MB |
| trades.jsonl | 50 MB | 5 → 90 days | ✅ Yes | ~50 MB |

**Total disk usage:** ~150 MB (vs. 1.5 GB if uncompressed)

## Compression Details

When a log file rotates:
1. Current file renamed: `api.log` → `api.log.1`
2. New file created: `api.log` (fresh)
3. Old file compressed: `api.log.1` → `api.log.1.gz`
4. Uncompressed deleted: `api.log.1` removed

**Example:**
```
Before rotation (100 MB written):
  api.log (100 MB)

After rotation:
  api.log (new, 0 MB)
  api.log.1.gz (10 MB)  ← Compressed!
  api.log.2.gz (10 MB)
  ...
  api.log.10.gz (10 MB)

Total: api.log (100 MB) + 10 × 10 MB = 200 MB
Instead of: api.log (100 MB) + 10 × 100 MB = 1.1 GB
```

## Compliance & Audit

For a **trading system with financial records**, log retention is critical:

1. **Immutability:** All trades are append-only (never deleted during trading)
2. **Retention:** Logs kept for 30-90 days minimum (adjust for your jurisdiction)
3. **Auditability:** Every trade logged with timestamp + order ID + result
4. **Recovery:** Compressed logs are readable for post-incident analysis

**Audit trail example:**
```json
{
  "timestamp": "2026-07-05T09:30:15Z",
  "event": "ORDER_FILLED",
  "symbol": "BTCUSDT",
  "side": "BUY",
  "quantity": 0.5,
  "price": 45000.50,
  "order_id": "uuid-123",
  "profit_loss_usd": 15.50,
  "strategy": "momentum"
}
```

All trades logged before → disk → compressed → archived → available for 30-90 days.

## Monitoring

Check log rotation status:

```bash
# View all API log files (uncompressed + compressed)
ls -lh logs/api.log*

# View trade log files
ls -lh logs/trades.jsonl*

# Estimate total disk usage
du -sh logs/

# Watch for compression in real-time (check system logs)
tail -f /var/log/syslog | grep "crypto-trading"
```

**Expected output:**
```
-rw-r----- 1 vali vali 8.2M Jul  5 09:30 api.log
-rw-r----- 1 vali vali 9.8M Jul  4 23:45 api.log.1.gz
-rw-r----- 1 vali vali 9.9M Jul  4 17:15 api.log.2.gz
-rw-r----- 1 vali vali 9.7M Jul  4 10:45 api.log.3.gz
...
```

## Reading Compressed Logs

Compressed logs are readable without decompression:

```bash
# Read compressed log (transparent)
zcat logs/api.log.1.gz | head -20

# Search in compressed log
zgrep "ORDER_FILLED" logs/api.log.1.gz

# Count errors in compressed log
zgrep "ERROR" logs/api.log.*.gz | wc -l

# Extract specific date range
zcat logs/api.log.*.gz | jq 'select(.timestamp > "2026-07-04T00:00:00Z")' | head
```

## Troubleshooting

### Issue: Compression failing
- Check disk space: `df -h`
- Check permissions: `ls -l logs/`
- Check temp space: `df /tmp`

### Issue: Old logs not deleted
- Verify logrotate config: `sudo cat /etc/logrotate.d/crypto-trading`
- Manual cleanup: `find logs/ -name "*.gz" -mtime +30 -delete`

### Issue: Logs growing too fast
- Increase rotation size in `log_archiver.py` (line 93, 106)
- Reduce logging level from INFO to WARNING
- Check for log loops or verbose modules

## Future Improvements

1. **External archival:** Send compressed logs to S3/CloudStorage after 30 days
2. **Structured queries:** Use log streaming services (ELK, Datadog)
3. **Real-time alerts:** Alert on ERROR/CRITICAL logs during trading
4. **Log anonymization:** Hash API keys in logs before long-term storage

## Files

- **`backend/core/log_archiver.py`** — CompressedRotatingFileHandler (application)
- **`backend/core/structured_logging.py`** — Uses handler in setup_structured_logging()
- **`systemd/crypto-trading.logrotate`** — System-level rotation config
- **`docs/LOG_ARCHIVAL_STRATEGY.md`** — This file

## Commands

```bash
# Test compression by forcing rotation (if logs exist)
# Note: create large test file
dd if=/dev/zero bs=1M count=100 of=logs/api.log

# View rotation in action
watch -n1 'ls -lh logs/api.log*'

# Install system logrotate
sudo cp systemd/crypto-trading.logrotate /etc/logrotate.d/crypto-trading

# Verify system logrotate
sudo logrotate -v /etc/logrotate.d/crypto-trading

# View size savings
du -h logs/
du -h logs/api.log.*.gz | awk '{sum += $1} END {print "Total compressed:", sum}'
```
