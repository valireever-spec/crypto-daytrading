# RUNBOOK: Primary Machine Failure & Failover

**Last Updated:** 2026-07-03  
**Severity:** CRITICAL  
**Target RTO:** <30 seconds (auto, after split-brain fix), 6+ minutes (current with split-brain bug)  
**Related Runbooks:** [Split-Brain](RUNBOOK_SPLIT_BRAIN.md), [Decision Tree](RUNBOOK_DECISION_TREE.md)

---

## Detection

### Alert Indicators

| Signal | Meaning | Action |
|--------|---------|--------|
| "PRIMARY heartbeat timeout (3x failed)" | No response for 15+ seconds | **IMMEDIATE** - failover in progress |
| "PRIMARY DECLARED DEAD" | Heartbeat module confirmed failure | BACKUP taking over (or blocked by split-brain) |
| "Trading paused then resumed" | Trading halted briefly, then continued | Failover completed, BACKUP is active |
| "BACKUP is now PRIMARY" | Failover completed successfully | Confirm customer traffic redirected |

### Log Grep Patterns

```bash
# Find heartbeat failures on PRIMARY
grep -i "heartbeat.*fail\|primary.*dead\|primary.*unreachable" /var/log/crypto-daytrading/*.log

# Find failover events
grep -i "failover\|backup.*promoted\|backup.*active" /var/log/crypto-daytrading/*.log

# See the sequence
grep -i "heartbeat\|primary.*dead\|failover\|backup.*active" /var/log/crypto-daytrading/*.log | tail -20
```

### Manual Check

```bash
# Check if PRIMARY is responding
curl -s http://192.168.3.1:8000/api/monitoring/status
# If timeout/connection refused: PRIMARY is down

# Check if BACKUP took over (promoted)
curl -s http://192.168.3.25:8002/api/ha/status
# Should show: {"role": "PRIMARY" or "BACKUP", "status": "..."}

# Check which machine is trading now
curl -s http://localhost:8000/api/autonomous/status | jq '.host'
# Should show: Either PRIMARY or BACKUP (whichever is active)

# Check heartbeat status (from BACKUP perspective)
curl -s http://192.168.3.25:8002/api/ha/heartbeat-status
# Should show: last_successful_heartbeat, failure_count, state
```

---

## Root Cause Analysis

### Most Common Causes

1. **PRIMARY Machine Powered Off (35% of cases)**
   - Operator accidentally shut down machine
   - Power loss or blackout
   - Hardware failure (disk/memory/CPU)
   - **Test:** Try SSH to PRIMARY: `ssh 192.168.3.1 "ps aux"` (connection refused = powered off)

2. **Network Partition (30% of cases)**
   - PRIMARY machine is up but unreachable
   - Network cable disconnected
   - Firewall rule blocking traffic
   - Switch/router issue isolating PRIMARY
   - **Test:** From BACKUP: `ssh 192.168.3.1 "echo OK"` (should connect)

3. **PRIMARY Process Crashed (25% of cases)**
   - Autonomous trader process died
   - Python exception not caught
   - Out of memory (OOM) killer
   - **Test:** `ssh 192.168.3.1 "ps aux | grep autonomous"` (no output = process dead)

4. **PRIMARY Storage Full (7% of cases)**
   - Database can't write (partition 100% full)
   - Log files consumed all space
   - Trading loop halted due to disk error
   - **Test:** `ssh 192.168.3.1 "df -h"` (check available space)

5. **Split-Brain Condition (3% of cases)**
   - PRIMARY alive but heartbeat timeout (network jitter)
   - Heartbeat module says "dead", split-brain says "both alive"
   - BACKUP can't failover (blocked by split-brain detection)
   - See [RUNBOOK_SPLIT_BRAIN.md](RUNBOOK_SPLIT_BRAIN.md)

---

## Recovery Procedure

### Understanding the Timeline

**Current Failover Time (2026-07-03): 6+ minutes**
- Blocked by split-brain bug
- See RUNBOOK_SPLIT_BRAIN.md for details

**After Phase 2 Fix (Target): <30 seconds**
- Split-brain logic will allow coordination
- Failover will complete automatically

### Automatic Failover (What Happens)

**Phase 1: Detection (First 15 seconds)**

```
T+0s:   PRIMARY machine dies or network partitions
        └─→ BACKUP continues running normally
        
T+5s:   BACKUP sends heartbeat to PRIMARY
        GET http://192.168.3.1:8000/api/health
        └─→ Timeout (PRIMARY not responding)
        └─→ Failure count: 1/3
        
T+10s:  BACKUP sends heartbeat again (retry)
        └─→ Timeout again
        └─→ Failure count: 2/3
        
T+15s:  BACKUP sends heartbeat (final check)
        └─→ Timeout again
        └─→ Failure count: 3/3 → PRIMARY DECLARED DEAD
```

**Phase 2: Split-Brain Verification (Next 5 seconds)**

```
T+15s+: BACKUP runs split-brain check
        SSH to PRIMARY: "ps aux | grep autonomous"
        └─→ If no response: Confirmed dead
        └─→ If response: Both machines healthy (split-brain)
        
T+20s:  If confirmed dead, proceed to failover
        If split-brain: Halt trades (see split-brain runbook)
```

**Phase 3: Failover to BACKUP (20-30 seconds)**

```
T+20s:  BACKUP syncs latest database from PRIMARY DB
        ├─→ Copy trades, positions, signals
        ├─→ Verify data integrity
        └─→ Ready to trade
        
T+25s:  BACKUP transitions to ACTIVE role
        ├─→ Stops heartbeat monitoring
        ├─→ Starts AutonomousTrader (was paused)
        ├─→ Connects to Binance WebSocket
        └─→ Subscribes to price feeds
        
T+30s:  BACKUP now actively trading
        ├─→ Making decisions
        ├─→ Placing orders
        ├─→ Writing to database
        └─→ API endpoints now respond on BACKUP
        
T+30s+: Dashboard/customers redirected to BACKUP:8002
        (or DNS updated to point to BACKUP IP)
```

### Current Reality (With Split-Brain Bug)

**The problem: Failover blocked by split-brain detection**

```
T+15s:  PRIMARY DECLARED DEAD (failure_count = 3/3)
        
T+15s:  Split-brain check: "Is BACKUP healthy?" YES
        └─→ Split-brain detection: "Both healthy!"
        └─→ PROBLEM: Contradicts heartbeat module
        
T+15s+: Failover blocked
        ├─ Heartbeat says: "PRIMARY dead, failover now"
        ├─ Split-brain says: "Both healthy, don't failover"
        ├─ Result: Deadlock, no action taken
        
T+20s:  Recovery loop attempts resolution
        ├─ Tries resolve_split_brain()
        ├─ But split-brain condition persists
        ├─ Keeps looping
        
T+60+:  Manual intervention required
        └─ Operator: Restart PRIMARY or kill BACKUP
        └─ Either action breaks deadlock
        
T+380s: System recovers (6+ minutes downtime)
```

**See RUNBOOK_SPLIT_BRAIN.md for how to handle this**

### Manual Failover (If Auto-Failover Fails)

**When to do this:** If >10 minutes with no trading activity

#### Option A: Force Failover to BACKUP

```bash
# 1. Verify PRIMARY is truly unreachable
ssh 192.168.3.1 "echo OK" 2>&1
# Expected: "Connection refused" or timeout (PRIMARY down)

# 2. Stop PRIMARY (if it's running but just slow)
ssh 192.168.3.1 "systemctl stop crypto-daytrading-primary" 2>/dev/null || true
# (Fails gracefully if PRIMARY offline)

# 3. Sync database from PRIMARY to BACKUP
# (If PRIMARY DB is still accessible)
scp 192.168.3.1:/home/vali/projects/crypto-daytrading/data/trading.db \
    /tmp/trading.db.primary.backup
    
# If PRIMARY unreachable, BACKUP already has synced copy
# (From its last 5s sync before PRIMARY died)

# 4. Promote BACKUP to PRIMARY
ssh 192.168.3.25 "curl -X POST http://localhost:8002/api/ha/promote-to-primary"
# Response: {"status": "promoted", "role": "PRIMARY"}

# 5. Wait for BACKUP to connect to Binance
sleep 10

# 6. Verify BACKUP is now trading
curl -s http://192.168.3.25:8002/api/autonomous/status | jq '.trading_active'
# Should show: true

# 7. Update customer traffic (if manual DNS)
# Change DNS or load balancer to point to 192.168.3.25:8002
# Or if already 192.168.3.25, it will work on port 8002
```

#### Option B: Restore PRIMARY and Demote BACKUP

```bash
# 1. Investigate what happened to PRIMARY
ssh 192.168.3.1 "systemctl status crypto-daytrading-primary" 2>&1

# 2. If process crashed, restart it
ssh 192.168.3.1 "systemctl restart crypto-daytrading-primary"

# 3. If disk full, clean up
ssh 192.168.3.1 "df -h /home/vali/projects/crypto-daytrading/"
# If >90% full: Clean logs
ssh 192.168.3.1 "rm -f /var/log/crypto-daytrading/*.log.{1,2,3,4,5}; > /var/log/crypto-daytrading/api.log"

# 4. Restart PRIMARY service
ssh 192.168.3.1 "systemctl restart crypto-daytrading-primary"
sleep 10

# 5. Verify PRIMARY is responding
curl -s http://192.168.3.1:8000/api/autonomous/status | jq '.trading_active'
# Should show: true

# 6. Demote BACKUP back to standby
ssh 192.168.3.25 "curl -X POST http://localhost:8002/api/ha/demote-to-backup"

# 7. Verify BACKUP is now in standby
curl -s http://192.168.3.25:8002/api/ha/status | jq '.role'
# Should show: "BACKUP"

# 8. Primary resumes
# If there was data loss between PRIMARY crash and BACKUP takeover:
# The BACKUP will have the latest state (from last sync)
# PRIMARY will sync from BACKUP on startup
```

---

## Timeline

### Expected RTO (Recovery Time Objective)

| Scenario | Current Time | After Phase 2 Fix |
|----------|--------------|-------------------|
| **PRIMARY powered off** | 6+ minutes | <30 seconds |
| **Network partition** | 6+ minutes | <30 seconds |
| **PRIMARY process crashed** | 6+ minutes | <30 seconds |
| **PRIMARY disk full** | 6+ minutes | <30 seconds |
| **Manual failover** | 2-5 minutes | N/A (auto is faster) |

**Note:** Current times are blocked by split-brain bug (see RUNBOOK_SPLIT_BRAIN.md)

### Monitoring During Failover

```bash
# Watch failover in progress (every 2 seconds)
watch -n 2 'curl -s http://192.168.3.25:8002/api/ha/status | jq "{role: .role, trading_active: .trading_active, last_heartbeat: .last_primary_heartbeat_time}"'

# Exit with Ctrl+C
```

---

## Escalation

### When to Page Engineer

**Page immediately if:**
- PRIMARY down >15 minutes (failover blocked)
- BACKUP failover command fails
- Both machines appear offline
- Database corruption after failover

**Page within 10 minutes if:**
- Failover in progress (monitor status)
- Need manual database recovery
- Data loss >1 hour of trades

### Troubleshooting Checklist Before Escalating

```bash
# 1. Is PRIMARY truly dead?
ssh 192.168.3.1 "ps aux | grep autonomous"
# No output = process dead
# Process running = PRIMARY alive (network issue, not machine failure)

# 2. What is BACKUP status?
curl -s http://192.168.3.25:8002/api/ha/status | jq '.role'
# Should show: "BACKUP" (or "PRIMARY" if already promoted)

# 3. Is BACKUP trading?
curl -s http://192.168.3.25:8002/api/autonomous/status | jq '.trading_active'
# If true: Failover succeeded, update customer DNS/routing
# If false: BACKUP not trading (blocked by split-brain?)

# 4. Are there any split-brain errors?
curl -s http://192.168.3.25:8002/api/ha/split-brain-status | jq '.detected'
# If true: See RUNBOOK_SPLIT_BRAIN.md
# If false: Failover should work, check logs

# 5. Database sync status
curl -s http://192.168.3.25:8002/api/monitoring/health | jq '.database'
# Should show: "healthy"
```

### Escalation Path

```
PRIMARY unreachable >5 min
    │
    ├─→ Verify PRIMARY truly offline
    │   ├─ SSH works: PRIMARY is alive (network issue, not failure)
    │   ├─ SSH fails: PRIMARY is offline (proceed)
    │
    ├─→ Check BACKUP status
    │   ├─ Trading active: Failover succeeded, update routing
    │   ├─ Trading inactive: Check split-brain (see below)
    │
    ├─→ Check for split-brain detection
    │   ├─ Detected: See RUNBOOK_SPLIT_BRAIN.md
    │   ├─ Not detected: Proceed to manual failover
    │
    ├─→ Manual failover attempt
    │   ├─ Success: Verify customer traffic redirected
    │   ├─ Fail: PAGE ENGINEER (HA system issue)
    │
    └─→ If >15 min: PAGE ENGINEER
```

---

## Post-Failover Verification

### Checklist After Failover Completes

- [ ] **BACKUP role changed?** - `curl http://192.168.3.25:8002/api/ha/status | jq '.role'` shows "PRIMARY"
- [ ] **BACKUP trading?** - `curl http://192.168.3.25:8002/api/autonomous/status | jq '.trading_active'` shows true
- [ ] **Database synced?** - `curl http://192.168.3.25:8002/api/monitoring/health | jq '.database'` shows "healthy"
- [ ] **Recent trades?** - `curl http://192.168.3.25:8002/api/portfolio/history | jq '.trades | last | .timestamp'` is recent (within 2 min)
- [ ] **WebSocket connected?** - `curl http://192.168.3.25:8002/api/monitoring/health/websocket | jq '.status'` shows "connected"
- [ ] **Positions intact?** - `curl http://192.168.3.25:8002/api/portfolio/positions | jq '.positions | length'` equals expected count

### Database Verification

```bash
# Verify BACKUP database has all recent trades
sqlite3 /home/vali/projects/crypto-daytrading/data/trading.db \
  "SELECT COUNT(*), MAX(timestamp) FROM trades;"
# Count should be same as before PRIMARY failed
# Timestamp should be within 5 seconds of failure time

# Check for duplicates (in case both machines traded briefly)
sqlite3 /home/vali/projects/crypto-daytrading/data/trading.db \
  "SELECT symbol, timestamp, COUNT(*) as cnt FROM trades GROUP BY timestamp, symbol HAVING cnt > 1;"
# Should return: empty (no duplicates)
```

### Metrics to Check

```bash
# Verify failover metrics
curl -s http://192.168.3.25:8002/api/monitoring/ha-status | jq '{
  failover_count: .failover_count,
  last_failover_time: .last_failover_time,
  data_loss_trades: .data_loss_trades,
  downtime_seconds: .downtime_seconds
}'

# Expected:
# - failover_count: Should increment by 1
# - downtime_seconds: <120 if successful auto-failover, <300 if manual
# - data_loss_trades: 0 (all synced before PRIMARY died)
```

---

## PRIMARY Recovery (Optional)

### If PRIMARY Recovers Later

```bash
# 1. PRIMARY comes back online (power restored, network fixed)
# 2. PRIMARY service starts
# 3. PRIMARY checks: "Am I PRIMARY or BACKUP?"
# 4. PRIMARY reads BACKUP DB to determine authority
# 5. PRIMARY sees: "BACKUP is now PRIMARY"
# 6. PRIMARY demotes itself to BACKUP
# 7. PRIMARY starts heartbeat monitoring (watches new PRIMARY on BACKUP)

# To verify this happened:
ssh 192.168.3.1 "curl http://192.168.3.1:8000/api/ha/status | jq '.role'"
# Should show: "BACKUP"

# Verify it's monitoring the original BACKUP (now PRIMARY)
ssh 192.168.3.1 "curl http://192.168.3.1:8000/api/ha/heartbeat-status | jq '.target_machine'"
# Should show: "192.168.3.25:8002"
```

### Manual Failback (If Desired)

**Note: Only do this after PRIMARY has been stable for 30+ minutes**

```bash
# 1. Stop trading on current PRIMARY (ex-BACKUP)
curl -X POST http://192.168.3.25:8002/api/autonomous/stop
sleep 5

# 2. Sync current PRIMARY state to original PRIMARY (now BACKUP)
scp /home/vali/projects/crypto-daytrading/data/trading.db \
    192.168.3.1:/home/vali/projects/crypto-daytrading/data/trading.db

# 3. Promote original PRIMARY
ssh 192.168.3.1 "curl -X POST http://192.168.3.1:8000/api/ha/promote-to-primary"

# 4. Wait for reconnection
sleep 10

# 5. Demote current PRIMARY (ex-BACKUP)
curl -X POST http://192.168.3.25:8002/api/ha/demote-to-backup

# 6. Verify
curl -s http://192.168.3.1:8000/api/ha/status | jq '.role'
# Should show: "PRIMARY"
curl -s http://192.168.3.25:8002/api/ha/status | jq '.role'
# Should show: "BACKUP"
```

---

## Summary

| Step | Action | Expected Outcome | Timing |
|------|--------|------------------|--------|
| **Detect** | Heartbeat fails 3x | PRIMARY DECLARED DEAD | 15s |
| **Verify** | Split-brain check | Confirmed dead (or split-brain) | +5s |
| **Failover** | BACKUP syncs + starts trading | BACKUP now PRIMARY | +10s |
| **Verify** | Check trading active | Trades resuming | +5s |
| **Redirect** | Update customer routing | Traffic to new PRIMARY | +5s |
| **Total** | All steps | **<30s target (after fix)** | 40s max |

**Success = BACKUP trading actively, database synced, no data loss, <120s downtime**

**Note:** Current system blocked by split-brain bug (6+ minutes). See RUNBOOK_SPLIT_BRAIN.md and Phase 2 fix plan for improvement.
