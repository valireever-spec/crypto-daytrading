# RUNBOOK: Split-Brain Detection & Recovery

**Last Updated:** 2026-07-03  
**Severity:** CRITICAL  
**Current Status:** KNOWN BUG - Blocking all failover  
**Target Fix:** Phase 2 (2026-07-15)  
**Related Runbooks:** [Primary Failure](RUNBOOK_PRIMARY_FAILURE.md), [Decision Tree](RUNBOOK_DECISION_TREE.md)

---

## Detection

### Alert Indicators

| Signal | Meaning | Action |
|--------|---------|--------|
| "SPLIT-BRAIN DETECTED - both machines healthy" | HA coordination issue | **IMMEDIATE** - halt orders |
| "Trading halted - split-brain prevention" | Trades blocked (safety mechanism) | Investigate root cause |
| "PRIMARY declared dead but both responding" | Contradiction in signals | Network jitter causing false alarm |
| "MAX RECOVERY ATTEMPTS EXCEEDED" | System can't resolve split-brain | Likely needs manual restart |

### Log Grep Patterns

```bash
# Find all split-brain detections
grep -i "split.brain\|split_brain" /var/log/crypto-daytrading/*.log

# Find the specific detection message
grep "SPLIT-BRAIN DETECTED" /var/log/crypto-daytrading/*.log

# See when trading was halted
grep -i "halting trades\|trades halted\|halt.*split" /var/log/crypto-daytrading/*.log

# Find contradictions (dead + healthy)
grep -E "PRIMARY.*dead.*healthy|healthy.*PRIMARY.*dead" /var/log/crypto-daytrading/*.log

# Count incidents
grep -c "SPLIT-BRAIN DETECTED" /var/log/crypto-daytrading/*.log
```

### Manual Check

```bash
# Check HA status (what does BACKUP think?)
curl -s http://192.168.3.25:8002/api/ha/split-brain-status
# Response: {"detected": true/false, "reason": "...", "primary_status": "...", "backup_status": "..."}

# Check if PRIMARY is actually responding
curl -s -m 3 http://192.168.3.1:8000/api/monitoring/status
# If timeout: PRIMARY is unreachable (not split-brain)
# If 200 OK: PRIMARY is responding (might be split-brain)

# Check if BACKUP is trading
curl -s http://192.168.3.25:8002/api/autonomous/status | jq '.trading_active'
# If false: Trading halted (split-brain detected)

# Check heartbeat status
curl -s http://192.168.3.25:8002/api/ha/heartbeat-status | jq '{failure_count, last_check_time, primary_responsive}'
# failure_count should be 0-3 (3 = declaring dead)
# primary_responsive should be true/false
```

---

## Root Cause Analysis

### What is Split-Brain?

In HA systems, **split-brain** means both machines think they are the authority. This can cause:
- Duplicate orders (both buy 0.1 BTC)
- Conflicting position data
- Lost trades (write to two different databases)

### Why Does It Happen Here?

**The Bug (Current - Until Phase 2 Fix):**

```
Heartbeat Module (every 5s):
  └─→ Checks PRIMARY via: GET /api/health (timeout: 3s)
  └─→ If times out: Count as failure
  └─→ After 3 failures: Declare PRIMARY dead

Split-Brain Prevention (same 5s cycle):
  └─→ Checks BOTH machines via: GET /api/health (parallel)
  └─→ If both respond: Report "both healthy"
  └─→ Doesn't matter if slow (no timeout check)

The Problem:
  PRIMARY responds slowly (3.2s) due to network jitter or load
  ├─ Heartbeat: >3s timeout → count as failure (1/3)
  ├─ Split-brain: Responds eventually → "both healthy!"
  └─ CONTRADICTION: Dead + healthy simultaneously
  
Result:
  ├─ Heartbeat wants failover
  ├─ Split-brain prevents failover (safety mechanism)
  ├─ Deadlock created
  └─ Trades halted indefinitely
```

### Root Cause: 3 Design Issues

1. **Heartbeat Timeout Too Aggressive (3 seconds)**
   - Cloud networks have 2-5s latency spikes
   - Microservices take 3-10s on startup
   - 3s is unrealistic
   - **Fix:** Increase to 5-10 seconds

2. **Split-Brain Logic Inverted**
   - Designed to prevent duplicate orders
   - Actually prevents failover entirely
   - Should use: "Both healthy + data consistent? Use PRIMARY"
   - Currently uses: "Both healthy? HALT ALL TRADES"
   - **Fix:** Change to coordinate, not halt

3. **Inconsistent Timeout Values**
   - Heartbeat: 3 seconds
   - Split-brain: 2 seconds
   - Different endpoints checked
   - **Fix:** Use same timeout (5-10s) and same endpoint

---

## Recovery Procedure

### Current System (Phase 1 - Split-Brain Bug Active)

**The Bad News:** Failover is blocked. Trades halted indefinitely.

**The Good News:** It's a safety mechanism. Prevents duplicate orders.

**Your Options:**

#### Option A: Manual Break (Force One to Shut Down)

```bash
# This breaks the deadlock by removing the contradiction

# 1. Check which machine is actually the authority
# The one with the most recent database should be the authority
sqlite3 /home/vali/projects/crypto-daytrading/data/trading.db \
  "SELECT MAX(timestamp) FROM trades;"
# (Note the most recent trade timestamp)

ssh 192.168.3.25 "sqlite3 /home/vali/projects/crypto-daytrading/data/trading.db \
  'SELECT MAX(timestamp) FROM trades;'"
# Compare timestamps

# 2. Machine with NEWER timestamp is the active one
# Let's say PRIMARY has newer data = PRIMARY should be active

# 3. Kill BACKUP temporarily (to break split-brain)
ssh 192.168.3.25 "systemctl stop crypto-daytrading-primary"

# 4. Wait for failover logic to notice BACKUP is down
sleep 10

# 5. PRIMARY should now proceed with normal operations
# (No more "both healthy" contradiction)

# 6. Verify PRIMARY is trading
curl -s http://192.168.3.1:8000/api/autonomous/status | jq '.trading_active'
# Should show: true

# 7. Restart BACKUP
ssh 192.168.3.25 "systemctl start crypto-daytrading-primary"

# 8. Verify BACKUP syncs and becomes standby
sleep 10
curl -s http://192.168.3.25:8002/api/ha/status | jq '.role'
# Should show: "BACKUP"
```

#### Option B: Restart Both (Cleanest Option)

```bash
# This clears the deadlock by starting fresh

# 1. Stop both machines
curl -X POST http://localhost:8000/api/autonomous/stop
ssh 192.168.3.25 "curl -X POST http://localhost:8002/api/autonomous/stop"

# Wait for clean shutdown
sleep 10

# 2. Restart PRIMARY first
systemctl restart crypto-daytrading-primary

# Wait for PRIMARY to stabilize
sleep 15

# 3. Verify PRIMARY is healthy
curl -s http://192.168.3.1:8000/api/autonomous/status | jq '.trading_active'
# Should show: true

# 4. Restart BACKUP
ssh 192.168.3.25 "systemctl restart crypto-daytrading-primary"

# Wait for BACKUP to connect
sleep 10

# 5. Verify BACKUP is in standby and syncing
curl -s http://192.168.3.25:8002/api/ha/status | jq '.role'
# Should show: "BACKUP"

# 6. Verify both are communicating
curl -s http://192.168.3.25:8002/api/ha/heartbeat-status | jq '.primary_responsive'
# Should show: true
```

#### Option C: Investigate & Resolve

```bash
# If you want to understand what happened

# 1. Check heartbeat failure count
curl -s http://192.168.3.25:8002/api/ha/heartbeat-status | jq '.failure_count'
# If 3: PRIMARY declared dead

# 2. Check if PRIMARY is actually responsive
curl -s -m 5 http://192.168.3.1:8000/api/monitoring/status 2>&1
# If timeout: PRIMARY truly unreachable (not jitter)
# If 200 OK: PRIMARY is alive (this is jitter-caused split-brain)

# 3. If jitter-caused (PRIMARY responds when given more time):
# The issue is the 3-second timeout is too aggressive
# Temporary fix: Increase heartbeat timeout and restart

# 4. Restart heartbeat module with longer timeout
# (Requires code change or config reload)
# For now: Restart the bot (Option B above)

# 5. After restart, PRIMARY should be responding within 5 seconds
# (Adjusted timeout in backoff phase - but still might trigger)
```

---

## Timeline

### Current System (With Split-Brain Bug)

| Time | Event | Action |
|------|-------|--------|
| **T+0s** | WebSocket recovers from staleness | Skill #1 reconnects |
| **T+5s** | Heartbeat check to PRIMARY times out (>3s) | Failure count = 1/3 |
| **T+10s** | Second heartbeat timeout | Failure count = 2/3 |
| **T+15s** | Third heartbeat timeout | Failure count = 3/3 → PRIMARY DEAD |
| **T+15s** | Split-brain check: "both healthy" | CONTRADICTION |
| **T+15s+** | Trading HALTED (safety mechanism) | Deadlock created |
| **T+60s+** | Recovery loop attempts resolution | Fails repeatedly |
| **T+380s+** | Manual operator intervention | Restart one/both machines |
| **T+410s** | System recovers | ~6 minutes downtime |

### After Phase 2 Fix

| Time | Event | Action |
|------|-------|--------|
| **T+0s** | WebSocket recovers from staleness | Skill #1 reconnects |
| **T+5s** | Heartbeat check to PRIMARY (timeout: 5-10s) | Times out if PRIMARY truly slow |
| **T+10s** | Second heartbeat attempt | Still timeout (or succeeds) |
| **T+15s** | Third heartbeat (or already recovered) | PRIMARY dead OR healthy |
| **T+15-20s** | Split-brain check + coordination | PRIMARY is authority (has data) |
| **T+20s** | If truly dead: BACKUP takes over | Failover succeeds |
| **T+30s** | Trading resumes on BACKUP | No deadlock |
| **T+30s total** | Full recovery | <30 seconds downtime |

---

## Escalation

### When to Page Engineer

**Page immediately if:**
- Split-brain detected AND trades halted >5 minutes
- Split-brain preventing ANY recovery action
- Need to understand if PRIMARY is truly dead or just slow

**Page within 10 minutes if:**
- Split-brain in progress (monitor, but likely to resolve)
- Manual restart attempt doesn't clear split-brain
- Data inconsistency suspected (PRIMARY vs BACKUP dbs differ)

### Information to Gather Before Paging

```bash
# 1. Are both machines responsive?
echo "=== PRIMARY ==="
curl -s -m 5 http://192.168.3.1:8000/api/monitoring/status | head -5

echo "=== BACKUP ==="
curl -s -m 5 http://192.168.3.25:8002/api/monitoring/status | head -5

# 2. What are their databases saying?
echo "=== PRIMARY DB ==="
sqlite3 /home/vali/projects/crypto-daytrading/data/trading.db "SELECT COUNT(*), MAX(timestamp) FROM trades;"

echo "=== BACKUP DB ==="
ssh 192.168.3.25 "sqlite3 /home/vali/projects/crypto-daytrading/data/trading.db 'SELECT COUNT(*), MAX(timestamp) FROM trades;'"

# 3. What's the heartbeat status?
curl -s http://192.168.3.25:8002/api/ha/heartbeat-status

# 4. Recent logs
grep "SPLIT-BRAIN\|PRIMARY.*dead\|both.*healthy" /var/log/crypto-daytrading/*.log | tail -20
```

---

## Post-Recovery Verification

### Checklist After Split-Brain Clears

- [ ] **Split-brain detected?** - `curl http://192.168.3.25:8002/api/ha/split-brain-status | jq '.detected'` shows false
- [ ] **One is PRIMARY?** - `curl http://192.168.3.1:8000/api/ha/status | jq '.role'` shows "PRIMARY"
- [ ] **One is BACKUP?** - `curl http://192.168.3.25:8002/api/ha/status | jq '.role'` shows "BACKUP"
- [ ] **Trading active?** - `curl http://192.168.3.1:8000/api/autonomous/status | jq '.trading_active'` shows true
- [ ] **Databases in sync?** - Compare timestamps: `sqlite3 ... SELECT MAX(timestamp) FROM trades;` on both
- [ ] **No duplicates?** - `sqlite3 ... SELECT COUNT(*) FROM trades;` compare with backup (should match)
- [ ] **Recent trades?** - `curl http://192.168.3.1:8000/api/portfolio/history | jq '.trades | last'` is recent

### Database Validation

```bash
# Verify no duplicates were created
sqlite3 /home/vali/projects/crypto-daytrading/data/trading.db \
  "SELECT symbol, timestamp, direction, COUNT(*) as cnt FROM trades 
   GROUP BY symbol, timestamp, direction HAVING cnt > 1;"
# Should return: empty (no duplicates)

# Verify both machines' databases match
PRIMARY_COUNT=$(sqlite3 /home/vali/projects/crypto-daytrading/data/trading.db "SELECT COUNT(*) FROM trades;")
BACKUP_COUNT=$(ssh 192.168.3.25 "sqlite3 /home/vali/projects/crypto-daytrading/data/trading.db 'SELECT COUNT(*) FROM trades;'")

echo "PRIMARY trades: $PRIMARY_COUNT"
echo "BACKUP trades: $BACKUP_COUNT"
# Should be equal

# Check most recent trade (should match on both)
PRIMARY_LATEST=$(sqlite3 /home/vali/projects/crypto-daytrading/data/trading.db "SELECT MAX(timestamp) FROM trades;")
BACKUP_LATEST=$(ssh 192.168.3.25 "sqlite3 /home/vali/projects/crypto-daytrading/data/trading.db 'SELECT MAX(timestamp) FROM trades;'")

echo "PRIMARY latest: $PRIMARY_LATEST"
echo "BACKUP latest: $BACKUP_LATEST"
# Should be equal (or BACKUP <= PRIMARY by a few seconds)
```

### Metrics to Check

```bash
# Verify HA status is healthy
curl -s http://192.168.3.25:8002/api/ha/status | jq '{
  role: .role,
  split_brain_detected: .split_brain_detected,
  heartbeat_status: .heartbeat_status,
  uptime_seconds: .uptime_seconds
}'

# Expected:
# - role: "BACKUP" (or "PRIMARY" if on PRIMARY machine)
# - split_brain_detected: false
# - heartbeat_status: "healthy"
```

---

## Phase 2 Fix (Target: 2026-07-15)

### What's Changing

**Problem:** Split-brain logic is backwards - halts all trades when both healthy

**Solution:** Three-part fix
1. Increase heartbeat timeout from 3s to 5-10s
2. Change split-brain coordination (allow PRIMARY to keep trading)
3. Use consistent timeouts and endpoints

### Expected Impact

```
Before Fix (Current):
- Split-brain incidents: 100+ per day
- Downtime per incident: 6-10 minutes
- Manual restarts: 9-10 per day
- Total downtime: 1-2 hours per day

After Fix:
- Split-brain incidents: <5 per day (detection only, no halt)
- Downtime per incident: <30 seconds
- Manual restarts: <1 per day
- Total downtime: <5 minutes per day
- Uptime target: >99%
```

### Testing After Fix Deploys

```bash
# Run chaos test: Simulate slow PRIMARY (3-5s response)
tc qdisc add dev lo root netem delay 2000ms

# Verify no split-brain triggered
curl -s http://192.168.3.25:8002/api/ha/split-brain-status | jq '.detected'
# Should show: false (even if PRIMARY is slow)

# Verify trading continues
curl -s http://192.168.3.1:8000/api/autonomous/status | jq '.trading_active'
# Should show: true (not halted)

# Clean up test
tc qdisc del dev lo root
```

---

## Preventive Measures (Until Phase 2)

### Monitor Split-Brain Frequency

```bash
# Check if split-brain is happening often
grep -c "SPLIT-BRAIN DETECTED" /var/log/crypto-daytrading/api.log

# If >10 per hour: Something is wrong
# Check PRIMARY load/network latency
# Consider manual restart to clear the condition
```

### Alert Setup (For Ops Team)

```bash
# Add monitoring alert:
# Alert if: split_brain_detected = true AND trading_halted = true

# Action threshold:
# - First alert: Monitor (might auto-recover)
# - Second alert (within 5 min): Investigate
# - Third alert (within 10 min): Manual restart
```

### Quick Recovery Script

```bash
#!/bin/bash
# save as /usr/local/bin/crypto-recovery.sh

echo "Checking for split-brain..."
SPLIT_BRAIN=$(curl -s http://192.168.3.25:8002/api/ha/split-brain-status | jq '.detected')

if [ "$SPLIT_BRAIN" = "true" ]; then
  echo "Split-brain detected, attempting recovery..."
  
  # Option: Kill BACKUP to break deadlock
  echo "Stopping BACKUP..."
  ssh 192.168.3.25 "systemctl stop crypto-daytrading-primary"
  
  sleep 10
  
  echo "Checking if PRIMARY is trading..."
  curl -s http://192.168.3.1:8000/api/autonomous/status | jq '.trading_active'
  
  echo "Restarting BACKUP..."
  ssh 192.168.3.25 "systemctl start crypto-daytrading-primary"
  
  echo "Recovery complete"
else
  echo "No split-brain detected"
fi
```

**Usage:**
```bash
chmod +x /usr/local/bin/crypto-recovery.sh
sudo /usr/local/bin/crypto-recovery.sh
```

---

## Summary

| Aspect | Current (Phase 1) | After Phase 2 |
|--------|-------------------|---------------|
| **What triggers it** | Heartbeat timeout (3s) + both responding | Same, but less false alarms |
| **How it manifests** | Trades HALTED | Trades continue (coordinated) |
| **Recovery action** | Restart one/both machines | Auto-recovery within 30s |
| **Downtime** | 6+ minutes | <30 seconds |
| **Manual intervention** | Required | Rarely needed |
| **Duplicate order risk** | Prevented (by halting) | Prevented (by coordination) |

**Key Takeaway:** Split-brain is a safety mechanism gone wrong. Phase 2 fix will allow safe coordination instead of brute-force halting.

**Until then:** If detected, restart PRIMARY or both machines to clear the deadlock.
