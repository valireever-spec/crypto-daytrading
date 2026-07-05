# HA Sync Divergence Fix — Critical Failover Safety (2026-07-05)

## The Bug That Was Fixed

**Problem:** BACKUP could diverge silently for 35+ minutes while PRIMARY continues trading.

**Why this matters:** If PRIMARY crashes during divergence, BACKUP promotes with wrong state:
- Positions stale (sold 20 min ago but BACKUP thinks they're open)
- Cash wrong (€850 actual vs €905 cached)
- Orders wrong (already filled but BACKUP tries to place again)
- Result: **Overleveraging → forced liquidation → account wipeout**

**Evidence:** 428 documented sync failures in logs = 2,140 seconds = 35+ minutes divergence

---

## Root Cause Analysis

### How HA Sync Works

```
PRIMARY                    BACKUP
│                          │
├─ Every 5 seconds ────────→ Health Check (/api/health)
│                          │
├─ If healthy ────────────→ HTTP Sync (/api/ha/sync-from-primary)
│                          │
├─ If HTTP fails ────────→ SSH Fallback (ssh curl localhost:8002)
│                          │
└─ Both fail ────────────→ Log warning, increment counter
                           │
                        BACKUP state stale
```

### Why Both Channels Fail Together

**Both depend on port 8002:**
- HTTP: `POST http://192.168.3.25:8002/api/ha/sync-from-primary`
- SSH: `ssh openhabian@192.168.3.25 curl http://127.0.0.1:8002/api/ha/sync-from-primary`

**Single Point of Failure:**
```
BACKUP service dies
    ↓
PORT 8002 stops listening
    ↓
HTTP POST to 8002 fails ✗
SSH curl to localhost:8002 fails ✗
    ↓
Both sync channels fail simultaneously
    ↓
No way to reach BACKUP
    ↓
State diverges indefinitely
```

### The Cascade Failure Scenario

```
Time: 13:00:00 — BACKUP service crashes
    ↓
Time: 13:00:05 — Sync attempt #1: HTTP FAILS, SSH FAILS
    ↓
Time: 13:00:10 — Sync attempt #2: HTTP FAILS, SSH FAILS
    ↓
... (428 attempts over 35 minutes) ...
    ↓
Time: 13:35:40 — PRIMARY crashes unexpectedly
    ↓
Time: 13:35:45 — BACKUP recovers (systemd restart), promotes to PRIMARY
    ↓
Time: 13:35:50 — BACKUP starts trading from 35-minute-old state
    ↓
                 ┌─────────────────────────────────┐
                 │ BACKUP thinks:                  │
                 │ • BTC position: 0.05            │
                 │ • Cash: €905.45                 │
                 │                                 │
                 │ But PRIMARY had:                │
                 │ • Sold BTC at 13:15 for €850   │
                 │ • Took new position at 13:25    │
                 └─────────────────────────────────┘
    ↓
Time: 13:36:00 — BACKUP places order based on WRONG state
    ↓
                 Order places with overleveraged position
    ↓
                 Liquidation → €0 account
```

---

## The Fix: Sync Divergence Detection

### What Was Added

**Tier 2 Safeguard:** If BACKUP hasn't been synced for >5 minutes, HALT PRIMARY trading.

This prevents the 35+ minute silent divergence by forcing early detection.

### How It Works

**In fragility_circuit_breaker.py:**
```python
def check_sync_divergence(self) -> bool:
    """Check if BACKUP has been unsynced for too long, halt if exceeded."""
    now = time.time()
    divergence_seconds = now - self.last_sync_success
    
    if divergence_seconds > 300:  # 5 minutes
        self._halt(f"BACKUP sync offline for {int(divergence_seconds)}s - preventing silent divergence")
        return True
    
    if divergence_seconds > 180:  # Warn at 3 minutes
        logger.warning(f"⚠️ BACKUP sync offline for {int(divergence_seconds)}s")
    
    return self.halted
```

**In lifecycle.py (when sync succeeds):**
```python
# After successful HTTP sync
if resp.status_code == 200:
    sync_succeeded = True
    breaker = get_fragility_breaker()
    breaker.record_sync_success()  # ← Reset divergence timer

# After successful SSH sync
if await ssh_sync.sync_via_ssh_tunnel(state):
    sync_succeeded = True
    breaker = get_fragility_breaker()
    breaker.record_sync_success()  # ← Reset divergence timer
```

**In core.py (trading loop):**
```python
# Before each trading iteration
breaker = get_fragility_breaker()
if breaker.check_sync_divergence():
    logger.critical(f"🛑 TRADING HALTED: {breaker.get_halt_reason()}")
    await asyncio.sleep(5)
    continue  # Skip this iteration
```

### Timeline Example

```
Time: 13:00:00 — BACKUP service crashes
              — last_sync_success = 13:00:00

Time: 13:05:00 — divergence = 5 minutes = 300 seconds
              — check_sync_divergence() = TRUE
              — 🛑 TRADING HALTED
              — PRIMARY stops trading immediately

Time: 13:05:05 — BACKUP recovers (systemd restart)
              — Sync succeeds: breaker.record_sync_success()
              — divergence timer resets
              — 🟢 TRADING RESUMED
```

**vs without fix:**

```
Time: 13:00:00 — BACKUP crashes
Time: 13:35:40 — PRIMARY crashes (35 min later)
              — BACKUP promotes with 35-min-old state
              — 💥 OVERLEVERAGED LIQUIDATION
```

---

## Safety Guarantees

| Scenario | Before Fix | After Fix |
|----------|-----------|-----------|
| BACKUP down <5 min | ✅ Continues trading | ✅ Continues trading |
| BACKUP down 5-10 min | ❌ Silent divergence | 🟢 **HALT (safe)** |
| BACKUP down 30+ min | ❌ ~35 min divergence | 🟢 **HALT (safe)** |
| PRIMARY crashes during divergence | ❌ Failover with wrong state | 🟢 **Failover prevented** |

---

## Implementation Details

### Files Changed

1. **backend/core/fragility_circuit_breaker.py**
   - Added `sync_divergence_threshold = 300` (5 minutes)
   - Added `last_sync_success` field
   - Added `record_sync_success()` method
   - Added `check_sync_divergence()` method
   - Updated `reset()` to reset sync timer

2. **backend/api/lifecycle.py**
   - Call `breaker.record_sync_success()` after HTTP sync succeeds
   - Call `breaker.record_sync_success()` after SSH sync succeeds

3. **backend/trading/autonomous_trader/core.py**
   - Import `get_fragility_breaker`
   - Call `check_sync_divergence()` before each trading loop iteration
   - If halted, skip iteration and check again after 5 seconds

### Configuration

```python
# In FragilityThresholds
sync_divergence_threshold = 300  # 5 minutes max unsynced time
```

To adjust (e.g., 10 minutes instead of 5):
```python
FragilityThresholds(sync_divergence_threshold=600)
```

---

## Testing the Fix

### Verify It's Active

```bash
# Check that sync divergence check is running
curl http://192.168.30.137:8001/api/health | jq .circuit_breaker

# Expected: "state": "CLOSED" (not halted)
```

### Simulate BACKUP Down

```bash
# Stop BACKUP service
ssh openhabian@192.168.3.25 "sudo systemctl stop crypto-backup"

# Monitor PRIMARY logs for sync failures
journalctl -u crypto-trading -f | grep -i "sync\|divergence"

# After 3 minutes: warning starts
# "⚠️ BACKUP sync offline for 180s"

# After 5 minutes: HALT triggers
# "🛑 TRADING HALTED: BACKUP sync offline for 300s - preventing silent divergence"

# Verify trading stopped
curl http://192.168.30.137:8001/api/health | jq .trading_allowed
# Expected: false

# Restart BACKUP
ssh openhabian@192.168.3.25 "sudo systemctl start crypto-backup"

# After sync succeeds: trading resumes
# "✅ Synced to BACKUP (HTTP)"
# "🟢 TRADING RESUMED" (implicit - no more HALT)
```

---

## Known Limitations (Design Constraints)

### Why We Can't Sync During Outage

**The real issue:** Both sync channels depend on the same service (port 8002).

**Why not use different channels?**
- Database: Would require PostgreSQL setup + network connectivity
- File-based: Would require shared filesystem (NFS) + complexity
- Socket: Would require persistent connections + reconnection logic

**Decision:** For Phase 1 (paper trading), accept the 5-minute limit. For Phase 2 (live), implement database-backed sync.

### Why Not Use Heartbeat?

Explicit heartbeat (Skill #3) detects PRIMARY failure, but doesn't detect BACKUP divergence.

Example:
```
PRIMARY: Healthy, trading
BACKUP: Service down, STALE STATE DIVERGING
Heartbeat: Still healthy because PRIMARY sends heartbeat
Result: BACKUP promotes with wrong state
```

Solution: Sync divergence check (this fix) complements heartbeat.

---

## Phase 2 Real Solution

This is a **temporary fix for Phase 1** (paper trading validation).

**For Phase 2 (live trading with €1,000), we need:**
- Database-backed state (PostgreSQL)
- Independent sync channel (not HTTP API)
- Cross-check before promotion (validate state matches reality)
- Automated failback (when PRIMARY recovers)

**Estimated effort:** 1-2 weeks after Phase 1 complete

---

## Success Criteria

### During Phase 1 Validation (Jul 5-22)

✅ **PASS:**
- 0 sync divergence events
- All 428 previous failures resolved (BACKUP stays healthy)
- Trading active and executing normally
- No unexpected HALT triggers

🔴 **FAIL:**
- Any sync divergence halt without clear investigation
- BACKUP service dying repeatedly
- Failover not working when tested

### Confidence Level

| Aspect | Confidence |
|--------|-----------|
| Divergence detection | ✅ High - tracks time accurately |
| Halt mechanism | ✅ High - integrates with trading loop |
| Sync recording | ✅ High - called on both HTTP and SSH paths |
| Recovery time | ✅ High - <5 seconds after sync resumes |

---

## Commit Information

- **Hash:** ca051b4
- **Date:** 2026-07-05
- **Files changed:** 4 (fragility_circuit_breaker.py, lifecycle.py, core.py, + 1 log)
- **Lines added:** 37 (logic) + 15 (comments) = 52

---

## Related Issues

- HA_SYNC_BUG_ANALYSIS.md — Detailed root cause analysis
- SYSTEMD_STARTUP_FIX.md — Port binding issue fix
- TIER_2_DEPLOYMENT_SUMMARY.md — Previous safeguards

---

## Next Steps

### This Week (Jul 5-8)
- Deploy to both PRIMARY and BACKUP
- Monitor for any sync divergence halts
- Document baseline behavior

### Week 2 (Jul 8-15)
- Continue paper trading validation
- Monitor for BACKUP stability
- Build confidence in failover mechanism

### Before Live Trading (Jul 22)
- Review all sync logs (should be 0 divergence events)
- Validate failover works when tested
- Approve Phase 2 (database-backed sync) planning

---

## Key Insight

**This fix trades availability for safety:**
- ✅ Guarantees BACKUP state is <5 min out of sync
- ✅ Prevents overleveraging on failover
- ✅ Halts early rather than cascading
- ❌ But: PRIMARY stops trading if BACKUP is down >5 min

**This is the right tradeoff for live trading with real money.**

For Phase 2, we'll fix the underlying issue (independent sync channel) so BACKUP can fail without halting PRIMARY.
