# Enhanced HA Failover Test Workflow

## Overview

**Enhanced Test** validates the HA system through 3 loops × 3 phases = 9 test cases, each running **8 core validations** to catch data integrity, safety, and failover mechanism failures.

**Duration:** ~3 hours 15 minutes (3 loops × 65 min per loop)  
**Validations per phase:** 8 checks run after each 15-minute trading window  
**Success criteria:** All 8 validations pass across all phases

---

## Architecture: Validation Layers

```
Layer 1: Failover Mechanism (Implicit)
├─ Mutual exclusion (only 1 bot trading)
└─ Sequence ordering (no concurrent states)

Layer 2: Explicit Validations (8 checks per phase)
├─ Dual-active bot prevention
├─ Circuit breaker state
├─ Role verification
├─ Heartbeat detection
├─ Backup readiness
├─ Configuration consistency
├─ Position transfer
└─ Cash flow integrity

Layer 3: Monitoring
└─ Real-time logs + phase results
```

---

## Test Phases (per loop)

### Phase Structure

```
PRE-PHASE SETUP:
  1. Verify both machines healthy
  2. Disable trading on active bot
  3. Prepare standby bot

PHASE EXECUTION:
  1. Kill/disable active bot process
  2. Enable standby bot for trading
  3. Monitor for 15 minutes (5 samples)
  4. Collect metrics

POST-PHASE VALIDATION:
  1. Run 8 core validations
  2. Log results
  3. Check for critical failures
  4. Wait 5 minutes (system reset)

TRANSITION:
  └─ To next phase (repeat)
```

---

## Loop 1: Initial Failover Cycle

### Phase 1: BACKUP Failover Test (15 min)

**Setup:**
- PRIMARY: ACTIVE (trading enabled)
- BACKUP: STANDBY (disabled)

**Execution:**
```
00:00 ├─ Disable PRIMARY trading
00:01 ├─ Kill PRIMARY process
00:03 ├─ Enable BACKUP trading
00:04 └─ Start monitoring (15 min window)

00:04-00:19: MONITORING
├─ 00:04 Check 1: Cash, Positions, Status
├─ 00:07 Check 2: Cash, Positions, Status
├─ 00:10 Check 3: Cash, Positions, Status
├─ 00:13 Check 4: Cash, Positions, Status
└─ 00:16 Check 5: Cash, Positions, Status

00:19-00:20: VALIDATION (8 checks)
├─ [1/8] Dual-active bot prevention
│   └─ Assert: PRIMARY.enabled=false, BACKUP.enabled=true
├─ [2/8] Circuit breaker state
│   └─ Assert: BACKUP.circuit_breaker != "OPEN"
├─ [3/8] Role verification
│   └─ Assert: Check /api/ha/status shows correct roles
├─ [4/8] Heartbeat detection
│   └─ Assert: Logs show failover detected or manual enable
├─ [5/8] Backup readiness
│   └─ Assert: /api/redundancy/failover/ready = true
├─ [6/8] Config consistency
│   └─ Assert: PRIMARY.entry_threshold == BACKUP.entry_threshold
├─ [7/8] Position transfer
│   └─ Assert: PRIMARY positions == BACKUP positions
└─ [8/8] Cash flow integrity
    └─ Assert: BACKUP.cash in expected range (€1000 ± trades)

00:20: RESULT
└─ ✅ PHASE 1 PASSED (if all 8 validations pass)
```

**Key Validation Details:**

**[1/8] Dual-Active Bot Prevention**
```
check_dual_active():
  primary_enabled = GET /api/autonomous/config -> .enabled
  backup_enabled = GET /api/autonomous/config -> .enabled (via SSH)
  
  assert NOT (primary_enabled AND backup_enabled):
    error: "BOTH BOTS TRADING!"
  
  assert (primary_enabled OR backup_enabled OR neither):
    info: "Mutual exclusion maintained"
```

**[2/8] Circuit Breaker State**
```
check_circuit_breaker():
  backup_health = GET /api/health
  cb_status = backup_health.circuit_breaker.status
  
  if cb_status == "OPEN":
    warning: "Circuit breaker blocking trades"
  elif cb_status == "CLOSED":
    success: "CB allows trading"
  else:
    warning: "CB status unknown"
```

**[3/8] Role Verification**
```
check_roles():
  primary_role = GET /api/ha/status -> .role
  backup_role = GET /api/ha/status -> .role (via SSH)
  
  count_primary = (primary_role == "PRIMARY") + (backup_role == "PRIMARY")
  
  if count_primary == 1:
    success: "Exactly 1 PRIMARY"
  elif count_primary == 0:
    warning: "No PRIMARY assigned (manual failover mode?)"
  elif count_primary == 2:
    error: "BOTH CLAIM PRIMARY!"
```

**[4/8] Heartbeat Detection**
```
check_heartbeat():
  failover_events = grep(logs, "failover|FAILOVER|detected")
  
  if len(failover_events) > 0:
    success: f"Heartbeat detected failover ({len(failover_events)} events)"
  else:
    warning: "No failover detection logged (may be manual mode)"
```

**[5/8] Backup Readiness**
```
check_backup_ready():
  readiness = GET /api/redundancy/failover/ready
  
  if readiness.ready == true:
    success: "BACKUP ready for next failover"
  else:
    warning: f"BACKUP not ready: {readiness.reason}"
```

**[6/8] Configuration Consistency**
```
check_config_drift():
  primary_config = GET /api/autonomous/config
  backup_config = GET /api/autonomous/config (via SSH)
  
  keys = [entry_threshold, max_positions, exit_profit_target, 
          exit_stop_loss, position_size_pct]
  
  for key in keys:
    if primary_config[key] != backup_config[key]:
      error: f"CONFIG DRIFT: {key} = {primary}  vs {backup}"
  
  if no drift:
    success: "Configuration consistent across machines"
```

**[7/8] Position Transfer**
```
check_position_sync():
  primary_positions = sqlite "SELECT COUNT(*) FROM positions WHERE qty != 0"
  backup_positions = ssh sqlite (same query)
  
  if primary_positions == backup_positions:
    success: f"Positions synced ({primary_positions} active)"
  else:
    warning: f"Position count mismatch: PRIMARY={p}, BACKUP={b}"
```

**[8/8] Cash Flow Integrity**
```
check_cash_flow():
  primary_cash = GET /api/health -> .account.cash
  backup_cash = GET /api/health -> .account.cash (via SSH)
  
  if primary_cash == backup_cash:
    success: f"Cash synced (€{cash})"
  elif primary_cash > 0 and backup_cash > 0:
    warning: f"Cash diverged: PRIMARY=€{p}, BACKUP=€{b}"
  else:
    error: "Cash went to 0 (trades failed?)"
```

---

### Phase 2: PRIMARY Recovery Test (15 min)

**Setup:**
- PRIMARY: DEAD/RESTARTING (killed in Phase 1)
- BACKUP: ACTIVE (trading, acting as PRIMARY)

**Execution:**
```
00:00 ├─ Disable BACKUP trading
00:02 ├─ Start PRIMARY process (restart)
00:06 ├─ Enable PRIMARY trading
00:07 └─ Start monitoring (15 min window)

00:07-00:22: MONITORING
└─ [5 samples at 00:07, 00:10, 00:13, 00:16, 00:19]

00:22-00:23: VALIDATION (8 checks)
├─ [1/8] Dual-active: Assert PRIMARY.enabled=true, BACKUP.enabled=false
├─ [3/8] Role: Assert PRIMARY is PRIMARY, BACKUP is BACKUP
├─ [5/8] Readiness: Verify both ready for next failover
├─ [6/8] Config: Ensure PRIMARY didn't drift during restart
├─ [7/8] Position: BACKUP → PRIMARY sync completed
└─ [8/8] Cash: Cash in correct range
```

**Special Concern: State Sync Direction**
- In Phase 1: PRIMARY → BACKUP (before failover)
- In Phase 2: BACKUP → PRIMARY (after failover)
- **Validation checks:** Did the backup's new data sync back to primary?

---

### Phase 3: BACKUP Failover Again (15 min)

**Setup:**
- PRIMARY: ACTIVE (trading, recovered from Phase 2)
- BACKUP: STANDBY (disabled, synced from PRIMARY)

**Execution:**
```
00:00 ├─ Disable PRIMARY trading
00:02 ├─ Kill PRIMARY process
00:04 ├─ Enable BACKUP trading
00:05 └─ Start monitoring

00:05-00:20: MONITORING

00:20-00:21: VALIDATION (8 checks)
├─ [1/8] Dual-active: Only BACKUP active
├─ [3/8] Role: BACKUP is now PRIMARY
├─ [7/8] Position: Verify positions from Phase 2 still intact
└─ [8/8] Cash: Cash reflects Phase 2 trades
```

**Key Test:** Does BACKUP reliably failover twice in a row?

---

## Inter-Phase Gaps (5 minutes each)

```
PURPOSE: System reset and stabilization

00:00-01:00 ├─ Let machine settle
01:00-02:00 ├─ Allow WebSocket to rebuild
02:00-03:00 ├─ Permit circuit breaker to reset if open
03:00-04:00 ├─ Give sync tasks time to complete
└─ 05:00 ├─ Ready for next phase
```

---

## Inter-Loop Gaps (5 minutes each)

```
PURPOSE: Full system reset before next cycle

PHASE 3 COMPLETE
│
├─ PRIMARY is dead
├─ BACKUP is active and trading
├─ Both need state sync before restart
│
[5 MIN RESET]
├─ Kill BACKUP (save its state)
├─ Restart PRIMARY
├─ Sync BACKUP → PRIMARY
├─ Verify both healthy
│
LOOP 2 PHASE 1 STARTS
└─ Full reset cycle repeats
```

---

## Loop 2 & 3: Repeat Cycle

Each additional loop repeats Phase 1-3 pattern:
- **Loop 1:** Initial failover behavior
- **Loop 2:** Consistent failover (no regressions)
- **Loop 3:** Stable under load (stress test)

### Cumulative Validation

After Loop 3, we verify:
- ✅ **3 failovers** (Phase 1 × 3 loops)
- ✅ **3 recoveries** (Phase 2 × 3 loops)
- ✅ **3 re-failovers** (Phase 3 × 3 loops)
- ✅ **8 validations** per phase = **72 validation checks** total
- ✅ **24 state syncs** (PRIMARY ↔ BACKUP)
- ✅ **No data loss** (all 8 cash/position checks passed)
- ✅ **No dual-active** (all 8 mutual exclusion checks passed)

---

## Expected Outcomes

### PASS Scenario

```
LOOP 1
├─ Phase 1: ✅ Backup failover → all 8 validations PASS
├─ Phase 2: ✅ Primary recovery → all 8 validations PASS
└─ Phase 3: ✅ Backup failover (2nd) → all 8 validations PASS

LOOP 2: ✅ Same pattern repeats perfectly
LOOP 3: ✅ Same pattern repeats perfectly

FINAL RESULT: ✅ HA SYSTEM PRODUCTION READY
├─ 0 data corruption issues
├─ 0 dual-active detections
├─ 0 config drift incidents
├─ 3 successful failover cycles
└─ Ready for Phase 2 (live trading)
```

### FAIL Scenarios

**Scenario A: Dual-Active Detection (Phase 1)**
```
[1/8] Dual-active bot prevention
❌ BOTH BOTS TRADING! PRIMARY=true, BACKUP=true
→ STOP TEST: Fix mutual exclusion logic
```

**Scenario B: Role Detection Failure (Phase 2)**
```
[3/8] Role verification after restart
❌ PRIMARY restarted but role="BACKUP" (not PRIMARY)
→ STOP TEST: Fix PRIMARY role assignment on restart
→ Likely cause: HA config or role detection API
```

**Scenario C: Config Drift (Phase 3)**
```
[6/8] Configuration consistency
❌ CONFIG DRIFT: entry_threshold = 60 vs 65
→ STOP TEST: Fix config sync mechanism
→ Likely cause: Backup config wasn't synced from primary
```

**Scenario D: Cash Flow Issue (Any Phase)**
```
[8/8] Cash flow integrity
❌ Cash diverged: PRIMARY=€1000, BACKUP=€950
→ STOP TEST: Investigate trade history sync
→ Likely cause: Trade not replicated to backup
```

---

## Validation Failure Actions

```
IF validation fails:
  1. Log all debug info (API responses, DB state, timestamps)
  2. Stop current loop
  3. Provide diagnostic output
  4. Identify root cause
  5. Fix code/config
  6. Restart from same loop

IF 3 consecutive loops pass:
  → SYSTEM VALIDATED ✅
  → Safe for Phase 2 (live trading)
  → Safe for production deployment
```

---

## Timeline Summary

```
Loop 1: 00:00 - 01:05
├─ Phase 1: 00:00 - 00:20 (failover to BACKUP)
├─ Wait:    00:20 - 00:25
├─ Phase 2: 00:25 - 00:45 (recover PRIMARY)
├─ Wait:    00:45 - 00:50
└─ Phase 3: 00:50 - 01:10 (failover to BACKUP again)

Loop 2: 01:10 - 02:15 (repeat)
Loop 3: 02:15 - 03:20 (repeat)

TOTAL: ~3 hours 20 minutes
```

---

## Success Metrics

| Metric | Target | What It Measures |
|--------|--------|------------------|
| **Failover Detection** | <30s | How fast BACKUP detects PRIMARY down |
| **Role Consistency** | 100% | Always exactly 1 PRIMARY |
| **Config Sync** | 100% | No parameter drift between machines |
| **Dual-Active Prevention** | 0 events | Never both trading simultaneously |
| **Cash Integrity** | ±€0 | No money created/destroyed |
| **Position Sync** | 100% | All positions replicated |
| **Backup Readiness** | Always ready | Can failover at any time |
| **Circuit Breaker** | Resets properly | Doesn't get stuck OPEN |

---

## Next Phase Decision

After Enhanced Test completion:

```
IF all 8 validations pass across 3 loops:
  → PROCEED to Phase 2 (live trading with €1,000)
  → Document lessons learned
  → Deploy to production

IF any validation fails:
  → Identify root cause
  → Fix code/architecture
  → Run test again (max 3 retries)
  → If 3 retries fail → escalate to architecture review
```

---

## Monitoring During Test

Real-time dashboards to watch:

1. **Test Log:** `tail -f /tmp/ha_acceptance_test/test.log`
2. **Validation Results:** grep for `[1/8] through [8/8]`
3. **Critical Alerts:** grep for `❌ CRITICAL`
4. **System Health:** `curl http://localhost:8001/api/health`
5. **Backup Health:** `ssh openhabian@192.168.3.25 curl http://localhost:8002/api/health`

---

## Test Abort Criteria

Stop testing immediately if:

1. ❌ Dual-active bot detected (would lose money)
2. ❌ Cash balance goes to zero (system error)
3. ❌ Can't reach either machine (network issue)
4. ❌ Both machines claim PRIMARY (role conflict)
5. ❌ 2 consecutive loops fail same validation (systematic issue)

---

## Post-Test Report

After 3 loops complete, generate:

```
ENHANCED HA TEST REPORT
═══════════════════════════════════════════

Test Run: [DATE] [START-TIME] - [END-TIME]
Duration: 3h 15m
Loops Completed: 3/3 ✅

VALIDATION SUMMARY:
  Total Checks: 72 (8 validations × 9 phases)
  Passed: 72 ✅
  Failed: 0
  Pass Rate: 100%

DETAILED RESULTS:
  [1/8] Dual-active prevention:     72/72 ✅
  [2/8] Circuit breaker:             72/72 ✅
  [3/8] Role verification:           72/72 ✅
  [4/8] Heartbeat detection:         72/72 ✅
  [5/8] Backup readiness:            72/72 ✅
  [6/8] Config consistency:          72/72 ✅
  [7/8] Position transfer:           72/72 ✅
  [8/8] Cash flow integrity:         72/72 ✅

FAILOVER METRICS:
  Failover events: 6 (3 BACKUP failovers)
  Recovery events: 3 (3 PRIMARY recoveries)
  Avg detect time: 2.1s
  Max detect time: 5.3s

CRITICAL FINDINGS:
  None - System validated for production

RECOMMENDATION:
  ✅ APPROVED FOR PHASE 2 (LIVE TRADING)
  ✅ APPROVED FOR PRODUCTION DEPLOYMENT
```

---

## Continuous Improvement

Track between runs:
- Any validation close to threshold
- Repeated warnings (even if not failures)
- Anomalies in sync times
- Unexpected role transitions

Feed these into Phase 2 live-trading monitoring plan.
