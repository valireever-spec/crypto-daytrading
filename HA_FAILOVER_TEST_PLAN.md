# HA Failover Acceptance Test Plan
**Test Start Date:** 2026-06-28  
**Test Coordinator:** Claude Code  
**Test Status:** IN PROGRESS

## Test Objective
Validate 3-loop failover cycle to ensure:
- Primary ↔ Backup switching works smoothly
- Database state syncs correctly during failover
- Trading continues without data loss
- Logs properly capture all failover events

## Equipment Status (Pre-Test)
- **Primary:** 127.0.0.1:8001 (ACTIVE) - Cash €1000.00, daily_pnl €0.00
- **Backup:** 192.168.3.25:8002 (PASSIVE) - Cash €1000.00, daily_pnl €221.56 (stale from prior run)
- **Network:** SSH to backup via openhabian@192.168.3.25
- **Monitoring:** Real-time logs via journalctl and curl health checks

## Test Protocol

### LOOP 1 - TEST 1: PRIMARY DISABLED → BACKUP FAILOVER (Target: 1+ hour trading)
**Start Time:** [PENDING]
**Target End Time:** [PENDING]

**Pre-Test Checks:**
- [ ] Primary running on 8001
- [ ] Backup running on 8002
- [ ] HA status shows PRIMARY role
- [ ] Database synced (check trade counts)

**Execution Steps:**
1. [ ] Disable PRIMARY (kill process)
2. [ ] Monitor BACKUP logs for failover detection (should see role change to PRIMARY)
3. [ ] Verify BACKUP assumes PRIMARY role
4. [ ] Check database sync from PRIMARY→BACKUP
5. [ ] Monitor trading on BACKUP for 1+ hour
6. [ ] Collect metrics: trades executed, P&L, any errors

**Success Criteria:**
- [ ] BACKUP detects PRIMARY down <30 seconds
- [ ] BACKUP assumes PRIMARY role (logs show role="PRIMARY")
- [ ] BACKUP trades without errors
- [ ] No data loss

**Findings:**
[PENDING - Will populate after test]

---

### LOOP 1 - WAIT: 15 Minutes
**Start Time:** [PENDING]  
**Status:** [PENDING]

---

### LOOP 1 - TEST 2: PRIMARY RE-ENABLED → REVERT TO PRIMARY (Target: 1+ hour trading)
**Start Time:** [PENDING]
**Target End Time:** [PENDING]

**Pre-Test Checks:**
- [ ] BACKUP still active
- [ ] BACKUP has completed trades from Test 1

**Execution Steps:**
1. [ ] Re-enable PRIMARY (start process)
2. [ ] Monitor PRIMARY logs for startup
3. [ ] Monitor BACKUP logs for role change to BACKUP
4. [ ] Verify DATABASE SYNC: BACKUP→PRIMARY (important: backup's new trades sync to primary)
5. [ ] Monitor PRIMARY trading for 1+ hour
6. [ ] Verify BACKUP is now in passive mode

**Success Criteria:**
- [ ] PRIMARY starts <30 seconds
- [ ] PRIMARY assumes PRIMARY role
- [ ] BACKUP's trades replicate to PRIMARY
- [ ] PRIMARY trades without errors

**Findings:**
[PENDING - Will populate after test]

---

### LOOP 1 - WAIT: 15 Minutes
**Start Time:** [PENDING]  
**Status:** [PENDING]

---

### LOOP 1 - TEST 3: PRIMARY DISABLED AGAIN → BACKUP FAILOVER (Target: 1+ hour trading)
**Start Time:** [PENDING]
**Target End Time:** [PENDING]

**Execution Steps:**
1. [ ] Disable PRIMARY again
2. [ ] Monitor for failover
3. [ ] BACKUP assumes PRIMARY role
4. [ ] Monitor trading for 1+ hour
5. [ ] Verify database consistency

**Success Criteria:**
- [ ] Failover works consistently (2nd time)
- [ ] BACKUP trades without errors
- [ ] Database state preserved

**Findings:**
[PENDING - Will populate after test]

---

### LOOP 1 - WAIT: 15 Minutes
**Start Time:** [PENDING]  
**Status:** [PENDING]

---

## LOOP 2 - Same 3 tests as LOOP 1
[TO START AFTER LOOP 1 COMPLETE]

---

## LOOP 3 - Same 3 tests as LOOP 1
[TO START AFTER LOOP 2 COMPLETE]

---

## Summary of Findings

### Critical Issues Found
[PENDING]

### Performance Observations
[PENDING]

### Recommendations
[PENDING]

---

## Approval
- [ ] All 9 tests completed (3 loops × 3 tests)
- [ ] 0 critical issues
- [ ] Ready for Phase 2 (live trading)
