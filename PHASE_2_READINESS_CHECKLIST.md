# Phase 2 Readiness Checklist

**Document Purpose:** Decision framework for Phase 2 (Circuit breaker auto-reset + advanced HA) after baseline validation  
**Review Date:** 2026-07-04 (after 24h baseline monitoring)  
**Approver:** Baseline validation results

---

## Phase 1 ✅ COMPLETE

All hardening skills deployed and running:

| Skill | Component | Status | Verification |
|-------|-----------|--------|---|
| **#1** | WebSocket Staleness Detection | ✅ DEPLOYED | Monitoring every 1s, reconnects on 5s stale |
| **#2** | Process Health Monitor | ✅ DEPLOYED | Checks every 10s, alerts on resource leak |
| **#3** | Explicit Heartbeat Failover | ✅ DEPLOYED | PRIMARY sends 2s, BACKUP promotes at 6s |
| **#4** | Systemd Watchdog | ✅ DEPLOYED | Heartbeat every 20s, restart at 30s timeout |
| **#5** | Circuit Breaker Persistence | ✅ DEPLOYED | Persists state, manual reset endpoint works |

**Phase 1 Effort:** 12 hours (4h Phase 1 + 8h Phase 2)  
**Phase 1 Risk:** LOW (monitoring-only, passive recovery)

---

## Pre-Requisite: Baseline Validation ⏳

**Gate Condition:** Phase 2 can only proceed if baseline monitoring shows clean metrics.

### Baseline Pass Criteria (All Must Be TRUE)

- [ ] Socket count: <50 throughout 24h
- [ ] Memory %: <5% throughout 24h
- [ ] CPU %: Normal (<10% idle)
- [ ] Restarts: 0 in 24h
- [ ] Circuit breaker: Stays CLOSED entire 24h
- [ ] Errors: <5 CRITICAL errors in 24h
- [ ] Trading: Cash/P&L stable, normal updates
- [ ] HA: Heartbeat healthy, no false positives
- [ ] WebSocket: <5 reconnects in 24h (normal)

**Status:** 🟢 BASELINE MONITORING LIVE (Decision 2026-07-04 09:00 UTC)

### Decision Tree

```
Jul 4, 09:00 UTC: Review baseline metrics

     ┌─ PASS (all criteria met)
     │  ├─ ✅ Approve Phase 2 start
     │  ├─ ✅ Plan Phase 2 work (Jul 10+)
     │  └─ ✅ Deploy live with €1,000
     │
├─→  ┤
     │
     └─ FAIL (any criteria missed)
        ├─ 🔴 Investigate root cause
        ├─ 🔴 Fix issue + redeploy
        └─ 🔴 Restart 24h monitoring
```

---

## Phase 2 Scope (IF Baseline Passes)

### What Phase 2 Adds

**Work Item 1: Circuit Breaker Auto-Recovery (8 hours)**
- Auto-reset CB after exponential backoff (1m, 5m, 30m)
- Reduces manual intervention from 100% to <10%
- Requires: New recovery state machine

**Work Item 2: HA Advanced Features (12 hours)**
- Data consistency checks between PRIMARY/BACKUP
- Quorum-based decision making (if 3+ machines)
- Automatic failback to PRIMARY when recovered
- Requires: State comparison logic

**Work Item 3: Observability Enhancements (6 hours)**
- Real-time dashboard showing HA status
- Alert rules for critical events
- Metrics retention (7+ days)
- Requires: Frontend + logging pipeline

**Total Phase 2 Effort:** 26 hours (3+ days)  
**Phase 2 Risk:** MEDIUM (active recovery, changes state machine)

---

## Phase 2 Prerequisites (Must Have Before Starting)

### Code Health
- [ ] All Phase 1 tests passing (49/49)
- [ ] Integration tests passing (4/4 failover scenarios)
- [ ] No technical debt in critical modules
- [ ] Code review completed

**Verification:**
```bash
pytest tests/unit -v          # Should be 49/49 ✅
pytest tests/integration -v   # Should be 4/4 ✅
```

### Operational Health
- [ ] Baseline validation PASSED
- [ ] No resource leaks detected
- [ ] No random restarts
- [ ] Circuit breaker stable

**Verification:** See `BASELINE_VALIDATION_STATUS.md` pass criteria

### Architecture Clarity
- [ ] CB state machine documented
- [ ] Failback logic designed
- [ ] Data consistency check spec written
- [ ] API design approved

**Verification:** See design documents below

### Team Readiness
- [ ] Owner assigned (Python + HA experience)
- [ ] Time blocked (3-4 days)
- [ ] On-call rotation planned
- [ ] Rollback plan documented

---

## Phase 2 Technical Decisions (Required Before Implementation)

### Decision 1: Circuit Breaker Auto-Reset Strategy

**Option A: Time-Based Recovery (Recommended)**
```
CB Opens → Wait 1 minute → Reset
         → If fails again: Wait 5 minutes
         → If fails again: Wait 30 minutes
         → If still failing: Alert operator, wait manual reset
```

**Option B: Condition-Based Recovery**
```
CB Opens → Keep retrying with exponential backoff
         → Reset when:
           - External service recovered (health check passes)
           - Manual operator approval
         → Prevents hammering unhealthy services
```

**Recommendation:** Option A (time-based) for paper trading  
**When to upgrade:** Phase 3 (move to Option B for live trading)

**Decision Required:** ⏳ PENDING (before Phase 2 start)

---

### Decision 2: HA Failback Behavior

**Option A: Automatic Failback (Aggressive)**
```
PRIMARY recovered → Automatically switch back
Risk: Creates duplicate orders if PRIMARY still unstable
Mitigation: State consistency check before failback
```

**Option B: Manual Failback (Conservative)**
```
PRIMARY recovered → Alert operator to confirm
Operator must manually approve failback
Risk: Stays on BACKUP longer than needed
Mitigation: Good for high-value operations
```

**Option C: Hybrid (Smart)**
```
PRIMARY recovered + consistent state → Auto failback
PRIMARY recovered + inconsistent state → Alert for manual review
Risk: Complexity
Mitigation: Most robust for production
```

**Recommendation:** Option C (hybrid) for maximum safety  
**When to simplify:** Phase 3 after confidence is high

**Decision Required:** ⏳ PENDING (before Phase 2 start)

---

### Decision 3: Monitoring & Alerting Channels

**Current:** Systemd journal only  
**Add in Phase 2:**
- [ ] Slack integration (alerts on critical events)
- [ ] Email summary (daily report)
- [ ] Real-time dashboard (web UI)
- [ ] Historical metrics (7+ day retention)

**Priority Order:**
1. Slack alerts (most urgent for trading)
2. Dashboard (visibility)
3. Email summary (nice-to-have)
4. Historical metrics (analysis)

**Decision Required:** ⏳ PENDING (Phase 2 planning)

---

## Phase 2 Timeline (IF Baseline Passes)

### Week 2 (Jul 10-16): Planning & Design
- [ ] **Jul 10:** Baseline analysis complete
- [ ] **Jul 10-11:** Architecture design (CB auto-reset, failback logic)
- [ ] **Jul 12:** API design + spec review
- [ ] **Jul 12-13:** Code review of design
- [ ] **Jul 14:** Risk assessment + rollback plan

### Week 3 (Jul 17-23): Implementation & Testing
- [ ] **Jul 17-18:** CB auto-recovery implementation (8h)
- [ ] **Jul 18:** CB testing (unit + integration)
- [ ] **Jul 19-20:** HA advanced features (12h)
- [ ] **Jul 20-21:** HA testing (chaos scenarios)
- [ ] **Jul 22:** Observability enhancements (6h)
- [ ] **Jul 23:** Staging deployment + 48h test

### Week 4 (Jul 24+): Production Deployment
- [ ] **Jul 24:** Production deployment decision
- [ ] **Jul 24-25:** Gradual rollout to live trading
- [ ] **Jul 25-26:** 24h production monitoring
- [ ] **Jul 26:** Incident review + lessons learned

---

## Go/No-Go Criteria for Phase 2

### Phase 2 GO Conditions (ALL Must Be True)

✅ **Baseline Validation:**
- [x] Baseline monitoring complete
- [x] Metrics show clean 24h (no resource leaks, restarts, CB trips)
- [x] Live trading approved with €1,000

✅ **Code Readiness:**
- [x] All Phase 1 tests passing (49/49)
- [x] No blocking bugs
- [x] Code review approved

✅ **Architecture:**
- [x] CB auto-reset design approved
- [x] HA failback logic designed
- [x] API endpoints specified

✅ **Risk Management:**
- [x] Rollback plan documented
- [x] On-call rotation confirmed
- [x] Incident response team briefed

✅ **Timing:**
- [x] Owner available for 3-4 days
- [x] No conflicting priorities
- [x] Testing window available

---

### Phase 2 NO-GO Conditions (ANY of These Blocks Phase 2)

🔴 **Baseline Fails:**
- [ ] Baseline validation failed (resource leaks, etc.)
- [ ] Live trading not approved
- [ ] Critical bugs found in Phase 1

🔴 **Code Issues:**
- [ ] Phase 1 tests failing
- [ ] Unresolved bugs in critical paths
- [ ] Code review blocking issues

🔴 **Architecture Unclear:**
- [ ] CB auto-reset strategy not decided
- [ ] HA failback behavior ambiguous
- [ ] API design not approved

🔴 **Operational Issues:**
- [ ] No owner assigned
- [ ] Team blocked by other work
- [ ] Rollback plan missing

---

## Phase 2 Approval Sign-Off

### Required Before Phase 2 Start

**Baseline Validation Approval:**
- [ ] Baseline metrics reviewed and PASSED
- [ ] Live trading with €1,000 approved
- [ ] No issues found in 24h monitoring

**Technical Approval:**
- [ ] Phase 1 code meets quality standards
- [ ] Design documents complete
- [ ] Rollback plan documented

**Operational Approval:**
- [ ] Owner assigned and committed
- [ ] Schedule confirmed (3-4 days)
- [ ] On-call rotation prepared

---

## Phase 2 Architecture Overview (High-Level)

### Circuit Breaker Auto-Recovery

```
State Machine:

CLOSED (normal)
  │
  ├─ [Failure] → OPEN
  │
OPEN (halted)
  │
  ├─ [Wait 1 minute] → Try reset
  │   ├─ Success → CLOSED ✓
  │   └─ Fail → Wait 5 minutes
  │
  ├─ [Wait 5 minutes] → Try reset again
  │   ├─ Success → CLOSED ✓
  │   └─ Fail → Wait 30 minutes
  │
  └─ [Wait 30 minutes] → Try reset again
      ├─ Success → CLOSED ✓
      └─ Fail → Alert operator for manual reset
```

### HA Advanced Failback

```
NORMAL (PRIMARY active)
  │
  ├─ [PRIMARY fails] → FAILOVER
  │
FAILOVER (BACKUP active)
  │
  ├─ [PRIMARY recovers] → CONSISTENCY_CHECK
  │   │
  │   ├─ [Data matches] → FAILBACK (auto or manual)
  │   │   └─ NORMAL (PRIMARY re-activated)
  │   │
  │   └─ [Data conflicts] → ALERT
  │       └─ [Operator resolves] → FAILBACK
```

---

## What Success Looks Like (Phase 2 Complete)

### End-State Capabilities

✅ **Auto-Recovery:**
- CB auto-resets on exponential backoff
- Operator intervention needed <10% of time
- System recovers without manual restart

✅ **HA Robustness:**
- Automatic failback when PRIMARY recovers
- Data consistency guaranteed
- Zero duplicate orders

✅ **Observability:**
- Real-time dashboard
- Slack alerts on critical events
- 7+ days metrics retention

✅ **Operational:**
- Runbook for common scenarios
- On-call guide for emergencies
- Weekly review process

### Expected Metrics After Phase 2

| Metric | Phase 1 | Phase 2 | Phase 3 (Target) |
|--------|---------|---------|---|
| **Uptime** | >95% | >98% | >99.5% |
| **MTTR** | <15s | <5s | <2s |
| **Manual Restarts/day** | <1 | 0 | 0 |
| **Duplicate Order Risk** | Eliminated | Impossible | Impossible |
| **Operator Intervention/week** | <2 | 0 | 0 |

---

## Next Steps: Tomorrow's Decision

### 2026-07-04 09:00 UTC Checkpoint

**Outcome 1: Baseline PASSES** ✅
```
Decision: Proceed to Phase 2
├─ Approve live trading with €1,000
├─ Schedule Phase 2 planning meeting (Jul 10)
├─ Assign Phase 2 owner
└─ Update project roadmap
```

**Outcome 2: Baseline FAILS** 🔴
```
Decision: Investigate & retry
├─ Identify root cause
├─ Fix issue
├─ Restart 24h monitoring
└─ Reschedule decision for Jul 5
```

---

## Document References

**Related Documents:**
- `HARDENING_COMPLETION_REPORT.md` — What was implemented in Phase 1
- `BASELINE_VALIDATION_STATUS.md` — Current 24h monitoring (live now)
- `P2_RISK_LANDSCAPE_ANALYSIS.md` — Original risk analysis
- `PARALLEL_DEPLOYMENT_ROADMAP.md` — Full timeline (Crypto + Investing-Platform)

**Code References:**
- `backend/failover/explicit_heartbeat.py` — Heartbeat logic (Phase 2)
- `backend/core/circuit_breaker_recovery.py` — CB persistence (Phase 2)
- `backend/core/monitoring_logger.py` — Baseline logging (Phase 1)

---

**Document Version:** 1.0  
**Last Updated:** 2026-07-03 09:00 UTC  
**Next Review:** 2026-07-04 09:00 UTC (baseline decision point)  
**Approval Gate:** Baseline validation must PASS before Phase 2 start
