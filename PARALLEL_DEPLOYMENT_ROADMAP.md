# Parallel Deployment Roadmap: Crypto & Investing-Platform

**Status:** APPROVED (Option B) - July 3, 2026

---

## High-Level Timeline

```
Week 1 (Jul 3-9)
├─ CRYPTO: Fix split-brain logic (P1 work)
├─ INVEST-PLATFORM: Phase 1 - Monitoring deployment
└─ RISK: Deploy both in parallel (monitoring is safe)

Week 2 (Jul 10-16)
├─ CRYPTO: Validate Skill #1 (24h post-split-brain fix)
├─ INVEST-PLATFORM: 48h staging validation
└─ GATE: Both must show improvement before Phase 2

Week 3 (Jul 17-23)
├─ CRYPTO: Phase 2 - Circuit breaker auto-reset
├─ INVEST-PLATFORM: Phase 2 - Auto-reconnect deployment
└─ RISK: Phase 2 is higher risk, need gates

Week 4+ (Jul 24+)
├─ CRYPTO: Phase 3 - HA failover automation (if needed)
├─ INVEST-PLATFORM: Phase 3 - Circuit breaker auto-reset (optional)
└─ RISK: Continuous monitoring, post-mortem on any incidents
```

---

## TRACK 1: Crypto-DayTrading (Split-Brain Fix)

### Work Item 1: Investigate Split-Brain Bug

**Owner:** TBD  
**Effort:** 4 hours  
**Timeline:** Jul 3-4 (URGENT)

**Tasks:**
1. Read P2_RISK_LANDSCAPE_ANALYSIS.md (findings)
2. Review split-brain logic in `backend/failover/split_brain_prevention.py`
3. Understand: Why does "both healthy" halt all trades?
4. Find: What condition should trigger failover instead?
5. Document: Proposed fix (pseudo-code)

**Output:** `SPLIT_BRAIN_BUG_ANALYSIS.md` (1-2 pages)

**Success Criteria:**
- Root cause identified
- Fix approach documented
- Risk assessment complete

---

### Work Item 2: Fix Split-Brain Logic

**Owner:** TBD  
**Effort:** 6-8 hours  
**Timeline:** Jul 4-5

**Tasks:**
1. Implement split-brain fix (likely 20-50 lines of code)
2. Update heartbeat timeout from 3s → 5-10s (less aggressive)
3. Fix TradingConfig missing attributes crash
4. Add comprehensive logging (log who wins split-brain decision)
5. Code review (2 reviewers required)

**Code Files to Change:**
- `backend/failover/split_brain_prevention.py`
- `backend/failover/ha_heartbeat.py`
- `backend/core/config.py` (TradingConfig attributes)
- `backend/api/routers/monitoring.py` (logging endpoint)

**Output:** PR ready for merge

**Success Criteria:**
- All changes reviewed
- Unit tests pass
- No regression in other HA logic

---

### Work Item 3: Validate Crypto Split-Brain Fix

**Owner:** TBD  
**Effort:** 8 hours (monitoring)  
**Timeline:** Jul 5-6

**Tasks:**
1. Deploy split-brain fix to staging
2. Run chaos tests: 
   - Disconnect PRIMARY heartbeat → verify failover works
   - Verify no duplicate orders
   - Verify split-brain decisions logged correctly
3. Monitor for 24h
4. Measure: How many split-brain halts? (Should be 0 or <1/day)

**Output:** `SPLIT_BRAIN_FIX_VALIDATION_RESULTS.md`

**Success Criteria:**
- 0 false split-brain halts in chaos tests
- Failover works correctly (BACKUP takes over)
- No duplicate orders detected

**GATE:** Must pass before proceeding to production

---

### Work Item 4: Re-Validate Skill #1 (Post-Fix)

**Owner:** TBD  
**Effort:** 16 hours (monitoring)  
**Timeline:** Jul 6-7

**Tasks:**
1. Run 24h validation (Skill #1 already deployed)
2. Compare metrics:
   - Circuit breaker trips: before vs. after split-brain fix
   - WebSocket staleness events: before vs. after
   - Manual restarts: before vs. after
   - Uptime: before vs. after
3. Measure Skill #1 impact:
   - How many reconnects avoided circuit breaker?
   - How much trading uptime improved?
4. Document findings

**Output:** `SKILL_1_POST_FIX_VALIDATION.md`

**Success Criteria:**
- Uptime improved from ~30% to >85%
- Circuit breaker trips reduced by >50%
- No new failures introduced

**GATE:** Success = ready for Phase 2

---

## TRACK 2: Investing-Platform (Phase 1 - Monitoring)

### Work Item 5: Set Up Investing-Platform Environment

**Owner:** TBD  
**Effort:** 2 hours  
**Timeline:** Jul 3-4

**Tasks:**
1. Review `SKILL_1_ADAPTATION_PLAN.md`
2. Answer 5 clarification questions:
   - Monitor Alpaca SIP only or also Polygon.io?
   - Thresholds acceptable (Warn 10s, Critical 25s)?
   - On reconnect failure: alert or switch to Polygon?
   - Monitor only on PRIMARY or both machines?
   - Team experiencing WebSocket staleness in production?
3. Set up staging environment (if not already done)

**Output:** Clarification answers document

**Success Criteria:**
- All questions answered
- Staging ready
- Team aligned on approach

---

### Work Item 6: Implement Phase 1 (Monitoring)

**Owner:** TBD  
**Effort:** 12-16 hours  
**Timeline:** Jul 4-5

**Tasks:**
1. Create `backend/integrations/websocket_staleness_monitor.py`
   - Adapted from crypto version
   - Adjust thresholds (10s warn, 25s critical)
   - Add feed-aware logging (Alpaca vs. Polygon)
2. Create `backend/integrations/websocket_reconnect_handler.py`
   - Alpaca reconnect logic (placeholder, not active in Phase 1)
   - Polygon reconnect logic (placeholder)
3. Integrate monitor into `websocket_feed.py`
   - Call `staleness_monitor.check_staleness()` every 1s
   - Call `on_price_update()` on each tick
4. Add health endpoint: `/api/health/websocket-staleness`
5. Add monitoring dashboard (basic)
6. Code review

**Code Files to Create/Modify:**
- `backend/integrations/websocket_staleness_monitor.py` (NEW)
- `backend/integrations/websocket_reconnect_handler.py` (NEW, placeholder)
- `backend/integrations/websocket_feed.py` (MODIFY)
- `backend/api/routers/monitoring.py` (MODIFY)
- `backend/api/lifecycle.py` (MODIFY, add monitor startup)

**Output:** PR ready for merge to staging

**Success Criteria:**
- Monitoring active (no reconnects yet)
- Health endpoint returns staleness metrics
- No crashes or performance degradation

---

### Work Item 7: Test Phase 1 in Staging

**Owner:** TBD  
**Effort:** 16 hours (monitoring)  
**Timeline:** Jul 5-6

**Tasks:**
1. Deploy Phase 1 to staging
2. Simulate WebSocket staleness scenarios:
   - Pause Alpaca feed for 15s → verify detection
   - Pause Alpaca feed for 30s → verify alert
   - Switch to Polygon fallback → verify feed continues
3. Monitor for 48h:
   - Does monitoring work reliably?
   - Are there false positives?
   - Does it break any existing logic?
4. Measure baseline metrics (for Phase 2 comparison)

**Output:** `INVESTING_PLATFORM_PHASE1_VALIDATION.md`

**Success Criteria:**
- Monitoring detects staleness correctly
- 0 false positives in 48h
- Feed continues flowing (monitoring is passive)
- Staging performance normal

**GATE:** Must pass before production

---

### Work Item 8: Deploy Phase 1 to Production

**Owner:** TBD  
**Effort:** 4 hours (active) + 48h monitoring  
**Timeline:** Jul 6-7

**Tasks:**
1. Deploy Phase 1 to production (canary or full rollout)
2. Monitor for 48h:
   - Is monitoring working?
   - How many staleness events detected?
   - Any performance impact?
3. Collect baseline metrics (for Phase 2 comparison)
4. Document findings

**Output:** `INVESTING_PLATFORM_PHASE1_PROD_REPORT.md`

**Success Criteria:**
- Zero downtime during deployment
- Monitoring working in production
- Baseline metrics collected
- Ready for Phase 2 in Week 3

---

## TRACK 3: Project Management & Gates

### Parallel Work Schedule

```
Jul 3 (Wed)
├─ CRYPTO: Investigate split-brain bug (4h)
├─ INVEST: Set up environment, answer questions (2h)
└─ BOTH: Code reviews prepared

Jul 4 (Thu)
├─ CRYPTO: Fix split-brain logic (6-8h)
├─ INVEST: Implement Phase 1 (12-16h)
└─ GATE: Both PRs ready for review by EOD

Jul 5 (Fri)
├─ CRYPTO: Chaos test split-brain fix (8h monitoring)
├─ INVEST: Test Phase 1 in staging (16h monitoring)
└─ BOTH: Validate in parallel (no blocking)

Jul 6 (Sat)
├─ CRYPTO: Deploy split-brain fix to production (2h)
├─ INVEST: Deploy Phase 1 to production (2h)
├─ CRYPTO: Run 24h Skill #1 validation (monitoring)
├─ INVEST: Run 48h Phase 1 monitoring (monitoring)
└─ BOTH: Can happen simultaneously

Jul 7 (Sun)
├─ CRYPTO: Collect validation metrics (2-4h analysis)
├─ INVEST: Continue Phase 1 monitoring
└─ GATE: Both ready for Week 2 assessment

Jul 10+ (Wed - Week 2)
├─ CRYPTO: Start Phase 2 if validation passed
├─ INVEST: Decide Phase 2 timeline
└─ BOTH: Assess results, adjust roadmap if needed
```

### Risk Management

| Risk | Crypto | Investing | Mitigation |
|------|--------|-----------|-----------|
| Split-brain fix breaks failover | HIGH | N/A | Extensive chaos testing before prod |
| Phase 1 monitoring impacts performance | LOW | LOW | Deployed as passive monitoring only |
| Phase 1 breaks existing feed logic | MEDIUM | MEDIUM | Thorough staging testing (48h) |
| Parallel deployment causes confusion | MEDIUM | MEDIUM | Clear ownership, daily standup |
| Production incident during deployment | LOW | LOW | Deploy on off-hours, have rollback plan |

### Success Gates

**GATE 1 (Jul 5):** Code review complete, no blocking issues
- Split-brain fix reviewed ✅
- Phase 1 implementation reviewed ✅

**GATE 2 (Jul 6):** Staging validation passed
- Split-brain chaos tests: 0 issues ✅
- Phase 1 staging tests: 0 issues ✅

**GATE 3 (Jul 7):** Production deployment successful
- Split-brain fix deployed ✅
- Phase 1 monitoring active ✅
- No incidents during deployment ✅

**GATE 4 (Jul 10):** Results validation
- Crypto uptime improved to >85% ✅
- Crypto CB trips reduced by >50% ✅
- Investing-Platform Phase 1 metrics baseline collected ✅
- Ready for Phase 2 ✅

---

## Staffing & Ownership

### Recommended Team Allocation

**Owner: Split-Brain Fix (Crypto)**
- Skill: Python, HA systems, failover logic
- Time: 18-24 hours over Jul 3-7
- Responsibility: Bug fix, validation, production deployment

**Owner: Phase 1 Implementation (Investing-Platform)**
- Skill: Python, WebSocket, integration logic
- Time: 28-36 hours over Jul 3-7
- Responsibility: Implementation, staging testing, production deployment

**Owner: Validation & Monitoring**
- Skill: Observability, log analysis
- Time: 40+ hours over Jul 5-10
- Responsibility: Chaos testing, production monitoring, metrics analysis

**Owner: Project Coordination**
- Skill: Roadmap management, stakeholder communication
- Time: 10-15 hours over Jul 3-10
- Responsibility: Daily standup, gate reviews, risk escalation

---

## Rollback Plans

### If Split-Brain Fix Causes Issues
```
1. Monitor for: False failover, duplicate orders, deadlock
2. If detected within 1h: Rollback to previous code
3. If detected after 1h: Investigate root cause first
4. Fallback: Disable split-brain prevention temporarily (manual failover mode)
```

### If Phase 1 Causes Performance Issues
```
1. Monitor for: High CPU, memory leak, feed lag
2. If detected: Disable monitor, restart feed
3. Rollback: Remove monitoring code (it's passive only)
4. Root cause analysis during next maintenance window
```

### If Both Fail Simultaneously
```
1. Crypto: Disable split-brain fix → revert to old HA logic
2. Investing-Platform: Disable Phase 1 monitoring → remove monitor
3. Focus on stability → patch and redeploy after analysis
```

---

## Success Metrics (Target)

### Crypto - Week 1
| Metric | Before | Target | Measurement |
|--------|--------|--------|-------------|
| Uptime | ~30% | >85% | Time trading active / total time |
| CB Trips | 199/week | <10/week | Count from logs |
| Manual Restarts | 57/week | <5/week | Count from logs |
| Split-Brain Halts | 1,913/week | <50/week | Count from logs |

### Investing-Platform - Week 1
| Metric | Before | Target | Measurement |
|--------|--------|--------|-------------|
| Monitoring Active | NO | YES | Health endpoint reports metrics |
| False Positives | N/A | <1/day | No false stale alerts |
| Feed Uptime | Unknown | >99% | Monitoring confirms staleness events |
| Performance Impact | Baseline | 0% degradation | CPU/memory unchanged |

---

## Communication Plan

### Stakeholders to Notify
- **Operations:** Daily standup (Jul 3-10)
- **Trading Team:** Pre/post deployment notifications
- **DevOps:** Infrastructure availability windows
- **Finance:** Uptime improvement tracking

### Daily Standup (Jul 3-10)
- 10:00 AM: Status update
- Owner: Project Coordination
- Duration: 15 minutes
- Topics: Progress, blockers, gates

### Deployment Notifications
- Pre-deployment: Email/Slack 30 min before
- Deployment window: Real-time updates
- Post-deployment: "All clear" confirmation within 1h

---

## Documents to Generate

### By Jul 5
- `SPLIT_BRAIN_BUG_ANALYSIS.md`
- `SPLIT_BRAIN_FIX_VALIDATION_RESULTS.md`
- `INVESTING_PLATFORM_PHASE1_STAGING_TEST_RESULTS.md`

### By Jul 8
- `SKILL_1_POST_FIX_VALIDATION.md`
- `INVESTING_PLATFORM_PHASE1_PROD_REPORT.md`

### By Jul 10
- `PARALLEL_DEPLOYMENT_SUMMARY.md` (overall results)
- `PHASE_2_READINESS_CHECKLIST.md` (next steps)

---

## Next Immediate Actions

1. **TODAY (Jul 3)**
   - ✅ Approve Option B (parallel deployment)
   - 🔵 Assign owners for both tracks
   - 🔵 Create calendar blocks for standup
   - 🔵 Notify stakeholders

2. **TOMORROW (Jul 4)**
   - 🔵 Crypto: Investigate split-brain bug
   - 🔵 Investing: Answer clarification questions
   - 🔵 Both: Prepare PRs

3. **THIS WEEK (Jul 5-7)**
   - 🔵 Crypto: Fix, test, deploy
   - 🔵 Investing: Implement, test, deploy
   - 🔵 Both: Monitor results

---

## Questions Before Starting

Before proceeding, confirm:

1. **Ownership:** Who owns split-brain fix? Who owns Phase 1?
2. **Deployment window:** Any constraints on when we can deploy?
3. **Rollback authority:** Who can approve/execute rollback if needed?
4. **Escalation:** Who do we escalate to if gates fail?
5. **Communication:** Slack channel for daily standup?

Once confirmed, we're ready to execute. 🚀
