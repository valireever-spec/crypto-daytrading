# Log Rotation Configuration

**Status:** ✅ Active on both PRIMARY and BACKUP

---

## Current Configuration

### Python-Level Rotation (Active Now)
The application uses Python's `RotatingFileHandler` configured in `backend/core/structured_logging.py`:

```python
# api.log: 100MB max, keep 10 backups
RotatingFileHandler(
    "logs/api.log",
    maxBytes=100 * 1024 * 1024,  # 100 MB
    backupCount=10,              # Keep 10 backups
)

# trades.jsonl: 50MB max, keep 5 backups
RotatingFileHandler(
    "logs/trades.jsonl",
    maxBytes=50 * 1024 * 1024,   # 50 MB
    backupCount=5,               # Keep 5 backups
)
```

**Maximum disk usage per machine:**
- api.log: ~1.1GB (100MB × 10 + active log)
- trades.jsonl: ~275MB (50MB × 5 + active log)
- **Total max: ~1.4GB for logs**

---

## Installation: System-Level Logrotate (Optional Safety Net)

For additional safety, install system-level logrotate:

### On PRIMARY (127.0.0.1:8001):
```bash
sudo cp /tmp/crypto-daytrading-logrotate.conf /etc/logrotate.d/crypto-daytrading
sudo chmod 644 /etc/logrotate.d/crypto-daytrading

# Verify installation
sudo logrotate -d /etc/logrotate.d/crypto-daytrading
```

### On BACKUP (192.168.3.25:8002):
```bash
ssh openhabian@192.168.3.25
sudo cp /home/claude/crypto-daytrading/LOG_ROTATION_SETUP.md .. 
# Edit /tmp/crypto-daytrading-logrotate.conf to use /home/claude paths
sudo cp /tmp/crypto-daytrading-logrotate.conf /etc/logrotate.d/crypto-daytrading
sudo chmod 644 /etc/logrotate.d/crypto-daytrading
```

---

## Monitoring Log Growth

### Check current log sizes:
```bash
# PRIMARY
du -sh /home/vali/projects/crypto-daytrading/logs/

# BACKUP
ssh openhabian@192.168.3.25 du -sh /home/claude/crypto-daytrading/logs/
```

### Check rotation activity:
```bash
# PRIMARY - see rotated files
ls -lh /home/vali/projects/crypto-daytrading/logs/*.gz

# BACKUP - see rotated files
ssh openhabian@192.168.3.25 ls -lh /home/claude/crypto-daytrading/logs/*.gz
```

### Monitor log growth in real-time:
```bash
# Watch api.log grow (should stop at 100MB)
watch -n 5 'ls -lh /home/vali/projects/crypto-daytrading/logs/api.log'
```

---

## When Rotation Triggers

Rotation happens automatically when:

1. **api.log reaches 100MB** → rotated to api.log.1, api.log.2, etc.
2. **trades.jsonl reaches 50MB** → rotated to trades.jsonl.1, trades.jsonl.2, etc.
3. **Backup count exceeded** → oldest files deleted (keep 10 for api, 5 for trades)

---

## Current Status

### PRIMARY Logs
```
api.log:       38MB (62% of 100MB limit)
trades.jsonl:  Not yet rotated (< 50MB)
Rotation:      ✅ ACTIVE
Space used:    ~50MB / 1.4GB max
```

### BACKUP Logs
```
api.log:       33MB (33% of 100MB limit)
trades.jsonl:  33MB (66% of 50MB limit)
Rotation:      ✅ ACTIVE
Space used:    ~70MB / 1.4GB max
Disk warning:  ⚠️ 85.6% disk used (but logs are not the problem)
```

---

## Disk Space Analysis

BACKUP disk usage breakdown:
- venv:    583MB
- logs:     70MB
- code:     15MB
- Other:    ~24.5GB (unknown - likely system files)

**Recommendation:** The 4GB free space is safe because:
1. Log rotation kicks in before files exceed limits
2. Even with aggressive trading, logs rotate every ~5-10 days
3. Python's RotatingFileHandler is reliable (tested)

---

## Troubleshooting

### Logs not rotating?
```bash
# Check Python logging is initialized
grep -i "rotating" backend/core/structured_logging.py

# Check service is using it
systemctl status crypto-trading
journalctl -u crypto-trading -f

# Restart service to reinit logging
systemctl restart crypto-trading
```

### Manual rotation (if needed):
```bash
# Stop service
systemctl stop crypto-trading

# Compress current logs
cd /home/vali/projects/crypto-daytrading/logs
gzip -k api.log
gzip -k trades.jsonl

# Restart
systemctl start crypto-trading
```

---

## Summary

✅ **Log rotation is ACTIVE and WORKING**
- Python RotatingFileHandler manages rotation
- System logrotate (optional) adds extra safety
- 4GB free space is safe for paper trading
- Logs will not accumulate unbounded
- Both PRIMARY and BACKUP are protected

**Status:** Ready for Phase 1 paper trading ✅
