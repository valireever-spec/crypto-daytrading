# RUNBOOK: Database Connection Failure

**Last Updated:** 2026-07-03  
**Severity:** CRITICAL  
**Target RTO:** <5 minutes  
**Related Runbooks:** [Primary Failure](RUNBOOK_PRIMARY_FAILURE.md), [Decision Tree](RUNBOOK_DECISION_TREE.md)

---

## Detection

### Alert Indicators

| Signal | Meaning | Action |
|--------|---------|--------|
| "Database connection failed" | Can't read/write trades | **IMMEDIATE** - check below |
| "Can't save trades" | Orders executing but not recorded | Database down or full |
| "Database locked" | Another process has exclusive lock | Check for stuck queries |
| "Disk full" | /home/vali/... partition at 100% | Delete logs or expand disk |

### Log Grep Patterns

```bash
# Find all database errors
grep -i "database\|sqlite\|connection.*fail" /var/log/crypto-daytrading/*.log

# Find disk full errors
grep -i "disk.*full\|no space\|enospc" /var/log/crypto-daytrading/*.log

# Find database lock errors
grep -i "database.*lock\|locked" /var/log/crypto-daytrading/*.log

# Count recent DB errors (last hour)
grep -i "database.*error" /var/log/crypto-daytrading/*.log | tail -100 | wc -l
```

### Manual Check

```bash
# Check database file exists and is accessible
ls -lh /home/vali/projects/crypto-daytrading/data/trading.db
# Should show: -rw-r--r-- with size >1MB

# Check if database is locked (process holding it)
lsof /home/vali/projects/crypto-daytrading/data/trading.db
# Should show: Only the backend process

# Check disk space
df -h /home/vali/projects/crypto-daytrading/
# Should show: >10% free space

# Try basic SQL query (health check)
sqlite3 /home/vali/projects/crypto-daytrading/data/trading.db "SELECT COUNT(*) FROM trades;"
# Should show: A number (e.g., "42") without error

# Test API connection to database
curl -s http://localhost:8000/api/monitoring/health | jq '.database'
# Should show: {"status": "healthy", "latency_ms": 5, ...}
```

---

## Root Cause Analysis

### Most Common Causes

1. **PostgreSQL/SQLite Process Crashed (40% of cases)**
   - Database daemon stopped unexpectedly
   - Out of memory (OOM killer)
   - Unhandled exception in DB code
   - **Test:** `ps aux | grep -E "postgres|sqlite"` or `systemctl status postgresql`

2. **Disk Full (30% of cases)**
   - `/home/vali/...` partition at 100%
   - Database file can't grow (WAL mode requires space)
   - Log files consuming space
   - **Test:** `df -h /home/vali/projects/crypto-daytrading/ | head -2`

3. **Database File Corrupted (15% of cases)**
   - Unclean shutdown (power loss, crash)
   - File system corruption
   - WAL (Write-Ahead Log) files inconsistent
   - **Test:** `sqlite3 .../data/trading.db "PRAGMA integrity_check;"` (should show "ok")

4. **Permission Issue (10% of cases)**
   - Wrong file permissions (not readable/writable)
   - User changed
   - SELinux/AppArmor blocking access
   - **Test:** `touch /home/vali/projects/crypto-daytrading/data/test.tmp` (should succeed)

5. **Network Partition (Remote DB only - 5% of cases)**
   - If using PostgreSQL on different machine
   - Network unreachable to DB server
   - Firewall blocking port 5432

---

## Recovery Procedure

### Quick Health Check (Before Taking Action)

```bash
# Run all these checks to understand severity
echo "=== Database Process ==="
ps aux | grep -E "postgres|sqlite|autonomous" | grep -v grep

echo "=== Disk Space ==="
df -h /home/vali/projects/crypto-daytrading/

echo "=== Database File ==="
ls -lh /home/vali/projects/crypto-daytrading/data/trading.db

echo "=== Database Integrity ==="
sqlite3 /home/vali/projects/crypto-daytrading/data/trading.db "PRAGMA integrity_check;" 2>&1

echo "=== Recent DB Errors ==="
grep -i "database.*error" /var/log/crypto-daytrading/*.log | tail -5
```

### Step 1: Verify Database Process

```bash
# Check if SQLite process is running
# (SQLite is file-based, but PRIMARY Python process might be stuck)

ps aux | grep autonomous
# Should show: `python ... autonomous_trader/core.py`
# If not running: Restart it

# Check if PostgreSQL is running (if using remote DB)
systemctl status postgresql
# Should show: "active (running)"
# If stopped: systemctl start postgresql

# If process found but unresponsive:
# Kill and restart (will be done in Step 3)
```

### Step 2: Check Disk Space

```bash
# Get disk usage
df -h /home/vali/projects/crypto-daytrading/

# If <5% free: CRITICAL, need cleanup
# If 5-10% free: Proceed carefully, monitor
# If >10% free: OK, proceed to Step 3

# If disk is full (<1%), clean up logs immediately
# Backup old logs first
mkdir -p /tmp/crypto-daytrading-backup
cp /var/log/crypto-daytrading/*.log.{1,2,3,4,5} /tmp/crypto-daytrading-backup/ 2>/dev/null
cp /var/log/crypto-daytrading/*.log /tmp/crypto-daytrading-backup/ 2>/dev/null

# Remove old rotated logs
rm -f /var/log/crypto-daytrading/*.log.{1,2,3,4,5}

# Truncate current logs (if very large)
> /var/log/crypto-daytrading/api.log
> /var/log/crypto-daytrading/server.log

# Verify disk space recovered
df -h /home/vali/projects/crypto-daytrading/

# If still full: Check what else is consuming space
du -sh /home/vali/projects/crypto-daytrading/*/ | sort -rh
```

### Step 3: Test Database Integrity

```bash
# Stop the bot temporarily (to release DB lock)
curl -X POST http://localhost:8000/api/autonomous/stop
sleep 5

# Run integrity check
sqlite3 /home/vali/projects/crypto-daytrading/data/trading.db "PRAGMA integrity_check;"

# Expected result: "ok"
# If error: Database corrupted, see recovery below

# If corrupted, check WAL files (Write-Ahead Log)
ls -la /home/vali/projects/crypto-daytrading/data/trading.db*
# Should show:
# - trading.db (main)
# - trading.db-shm (shared memory, can be large)
# - trading.db-wal (write-ahead log)

# If WAL is corrupted, backup and rebuild
# WARNING: This loses recent uncommitted writes
if [ -f /home/vali/projects/crypto-daytrading/data/trading.db-wal ]; then
  # Backup original
  cp /home/vali/projects/crypto-daytrading/data/trading.db /tmp/trading.db.backup
  cp /home/vali/projects/crypto-daytrading/data/trading.db-wal /tmp/trading.db-wal.backup
  
  # Remove WAL files (force DB to rebuild on next open)
  rm /home/vali/projects/crypto-daytrading/data/trading.db-wal
  rm /home/vali/projects/crypto-daytrading/data/trading.db-shm 2>/dev/null || true
  
  # Re-check integrity
  sqlite3 /home/vali/projects/crypto-daytrading/data/trading.db "PRAGMA integrity_check;"
fi
```

### Step 4: Restart Database Connection

```bash
# Start the bot again
curl -X POST http://localhost:8000/api/autonomous/start
sleep 3

# Verify connection
curl -s http://localhost:8000/api/monitoring/health | jq '.database'
# Should show: {"status": "healthy", ...}

# Test by running a simple query
curl -s http://localhost:8000/api/portfolio/positions
# Should show: Positions (not error)

# If still failing: Restart the entire PRIMARY bot
systemctl restart crypto-daytrading-primary

# Wait for startup
sleep 10

# Verify again
curl -s http://localhost:8000/api/autonomous/status | jq '.status'
```

### Step 5: Restore from Backup (If Corrupted)

**Only if integrity check failed and couldn't be fixed:**

```bash
# 1. Stop the bot
curl -X POST http://localhost:8000/api/autonomous/stop

# 2. Check if backup exists (from PRIMARY or HA sync)
# Backup locations:
ls -lh /tmp/trading.db.backup  # From our cleanup
ls -lh /home/vali/projects/crypto-daytrading/backups/  # Scheduled backups (if any)

# 3. Restore from backup
cp /tmp/trading.db.backup /home/vali/projects/crypto-daytrading/data/trading.db
# OR if from BACKUP machine:
scp 192.168.3.25:/home/vali/projects/crypto-daytrading/data/trading.db \
    /home/vali/projects/crypto-daytrading/data/trading.db

# 4. Verify integrity after restore
sqlite3 /home/vali/projects/crypto-daytrading/data/trading.db "PRAGMA integrity_check;"
# Should show: "ok"

# 5. Start bot
curl -X POST http://localhost:8000/api/autonomous/start
sleep 5

# 6. Verify
curl -s http://localhost:8000/api/monitoring/health | jq '.database'

# NOTE: May lose recent trades (those not in backup)
# Check database size to estimate data loss
sqlite3 /home/vali/projects/crypto-daytrading/data/trading.db "SELECT COUNT(*) FROM trades;"
```

---

## Timeline

### Expected RTO (Recovery Time Objective)

| Scenario | Time to Recovery | Action |
|----------|------------------|--------|
| **Database process crashed** | <2 minutes | Restart bot + verify |
| **Disk full** | <5 minutes | Clean logs + restart |
| **Database locked** | <1 minute | Kill stuck process (if any) |
| **Database corrupted** | 5-15 minutes | Rebuild from WAL or restore backup |
| **Remote DB unreachable** | 10+ minutes | Network troubleshooting (escalate to DevOps) |

### Monitoring During Recovery

```bash
# Watch database status every 5 seconds
watch -n 5 'curl -s http://localhost:8000/api/monitoring/health | jq "{database: .database, last_trade: .last_trade_timestamp}"'
```

---

## Escalation

### When to Page Engineer

**Page immediately if:**
- Database integrity check fails after repair attempts
- Disk full and cleanup doesn't free up space
- Database still unreachable after restart
- Backup restore doesn't work

**Page within 10 minutes if:**
- Database locked by unknown process (can't kill)
- Remote DB (PostgreSQL) unreachable >5 minutes
- Data loss >1 hour of trading (need to reconcile)

### Escalation Workflow

```
Database error detected
    │
    ├─→ Check disk space (df -h)
    │   ├─ <1% free: Clean logs (ops can handle)
    │   ├─ 1-5% free: Clean logs + monitor
    │   ├─ >5% free: Proceed to integrity check
    │
    ├─→ Check database integrity (PRAGMA integrity_check)
    │   ├─ "ok": Process crashed, restart bot
    │   ├─ Error: Corrupted, attempt repair
    │
    ├─→ Repair: Remove WAL files, restart
    │   ├─ Success: Resume trading
    │   ├─ Fail: Restore from backup
    │
    ├─→ Restore from backup
    │   ├─ Success: Resume, document data loss
    │   ├─ Fail: PAGE ENGINEER (critical data loss)
    │
    └─→ PAGE ENGINEER if >5 min to recovery
```

### Information to Gather Before Paging

```bash
# Collect diagnostic info for engineer
echo "=== Disk Space ==="
df -h /home/vali/projects/crypto-daytrading/

echo "=== Database Process ==="
ps aux | grep autonomous

echo "=== Database Files ==="
ls -lh /home/vali/projects/crypto-daytrading/data/

echo "=== Integrity Check ==="
sqlite3 /home/vali/projects/crypto-daytrading/data/trading.db "PRAGMA integrity_check;" 2>&1

echo "=== Recent Errors ==="
tail -50 /var/log/crypto-daytrading/api.log | grep -i "database\|error"

echo "=== Available Backups ==="
ls -lh /tmp/trading.db.backup 2>/dev/null || echo "No local backup"
ssh 192.168.3.25 "ls -lh /home/vali/projects/crypto-daytrading/data/trading.db" 2>/dev/null || echo "BACKUP DB unreachable"
```

---

## Post-Recovery Verification

### Checklist After Database Recovers

- [ ] **Database responsive?** - `curl http://localhost:8000/api/monitoring/health | jq '.database.status'` shows "healthy"
- [ ] **Trades readable?** - `curl http://localhost:8000/api/portfolio/history | jq '.trades | length'` returns a number
- [ ] **Positions correct?** - `curl http://localhost:8000/api/portfolio/positions | jq '.positions | length'` matches expected
- [ ] **Recent write?** - `curl http://localhost:8000/api/portfolio/history | jq '.trades | last | .timestamp'` is recent
- [ ] **Disk space ok?** - `df -h /home/vali/projects/crypto-daytrading/ | tail -1` shows >10% free
- [ ] **Trading active?** - `curl http://localhost:8000/api/autonomous/status | jq '.trading_active'` shows true
- [ ] **No stale errors?** - `grep -i "database.*error" /var/log/crypto-daytrading/*.log | tail -5` has no recent entries

### Data Reconciliation (If Restored from Backup)

```bash
# Check how much data was potentially lost
sqlite3 /home/vali/projects/crypto-daytrading/data/trading.db \
  "SELECT MAX(timestamp) FROM trades;"
# Compare with: Time of incident (estimate lost data)

# If BACKUP machine has fresher data:
# Sync from BACKUP:
scp 192.168.3.25:/home/vali/projects/crypto-daytrading/data/trading.db \
    /tmp/trading.db.backup-fresh
    
# Verify timestamp in backup
sqlite3 /tmp/trading.db.backup-fresh "SELECT MAX(timestamp) FROM trades;"

# Use the newer one
cp /tmp/trading.db.backup-fresh /home/vali/projects/crypto-daytrading/data/trading.db
```

### Metrics to Check

```bash
# Verify database performance recovered
curl -s http://localhost:8000/api/monitoring/health | jq '{
  database: .database,
  trades_count: .trades_total,
  last_trade: .last_trade_timestamp,
  uptime_seconds: .uptime_seconds
}'

# Expected after recovery:
# - database.status: "healthy"
# - database.latency_ms: <10
# - trades_count: Should match or be close to pre-incident
# - last_trade: Within 1-2 minutes
```

---

## Prevention

### Disk Space Monitoring

```bash
# Add to crontab (check hourly)
# 0 * * * * df -h /home/vali/projects/crypto-daytrading/ | grep -E "8[0-9]%|9[0-9]%|100%" && echo "ALERT: Low disk space" | mail ops@company.com

# Or simpler: Manual check daily
df -h /home/vali/projects/crypto-daytrading/ | tail -1
```

### Log Rotation

```bash
# Ensure logs rotate and don't fill disk
# Add to /etc/logrotate.d/crypto-daytrading:
/var/log/crypto-daytrading/*.log {
    daily
    rotate 7
    compress
    delaycompress
    notifempty
    create 0640 root root
}

# Apply immediately
logrotate -f /etc/logrotate.d/crypto-daytrading
```

### Regular Backups

```bash
# Manual backup before high-risk operations
cp /home/vali/projects/crypto-daytrading/data/trading.db \
   /tmp/trading.db.backup.$(date +%Y%m%d_%H%M%S)

# Scheduled backup (daily)
# 3 3 * * * cp /home/vali/projects/crypto-daytrading/data/trading.db /backup/trading.db.$(date +\%Y\%m\%d)
```

---

## Summary

| Step | Action | Expected Outcome |
|------|--------|------------------|
| **Detect** | Alert or manual check | Confirm database error |
| **Quick Check** | Run health checks | Understand root cause |
| **Clean** | Check disk, clean logs if needed | Disk >10% free |
| **Verify** | Test database integrity | "ok" from PRAGMA check |
| **Restart** | Stop/start bot | Connection re-established |
| **Restore** | If corrupted, restore from backup | Database consistent |
| **Post-Recovery** | Verify trades readable, positions correct | Resume trading |

**Success = Database healthy, trades recorded, trading active within 5 minutes**
