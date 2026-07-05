# Pre-Live Deployment Checklist

**Reference:** BUSINESS_SAFETY_ASSESSMENT.md  
**Target Deployment:** $1,000 live capital  
**Status:** 🔴 NOT READY (5 blockers in progress)

---

## Section 1: Critical Blockers (5/5)

- [ ] **Blocker #1: Exit Check UnboundLocalError** ✅ FIXED
  - [x] Code fix applied (commit 19d2875)
  - [ ] No UnboundLocalError in logs during 48h paper trading
  - [ ] Positions exiting correctly at 300-600s window

- [ ] **Blocker #2: HA Sync Broken** 🟡 IN PROGRESS
  - [x] Database paths fixed (machine-aware)
  - [x] datetime import shadowing fixed
  - [ ] Test sync endpoint: POST /api/ha/sync-from-primary
  - [ ] BACKUP can reach PRIMARY via SSH tunnel
  - [ ] State sync payload complete and correct
  - [ ] HA failover tested during paper trading (optional but recommended)

- [ ] **Blocker #3: Risk Gate Bypass (proposed_value=0)** ⏳ NOT STARTED
  - [ ] Actual position value calculated (not hardcoded 0)
  - [ ] Position value passed to risk gate checks
  - [ ] Daily loss limit cannot be bypassed
  - [ ] Test: Daily loss limit enforcement in paper trading

- [ ] **Blocker #4: Zero Observability** 🟡 IN PROGRESS
  - [x] Telegram alerts implemented (both machines)
  - [x] Trade event logging created
  - [ ] Baseline metrics collection active (not 0 bytes)
  - [ ] Exit success rate tracked
  - [ ] Sync lag monitored
  - [ ] Circuit breaker state tracked
  - [ ] Resource usage monitored

- [ ] **Blocker #5: Bare Exception Clauses** ✅ VERIFIED
  - [x] 0 bare except handlers in critical code
  - [x] All exceptions properly typed and logged

---

## Section 2: Business Goals Validation (48-Hour Paper Trading)

**Timeline:** 48 hours continuous simulation (in progress)

- [ ] **Win Rate ≥15%**
  - [ ] Tracked for 48 hours
  - [ ] Result: ___% (goal: ≥15%)
  - [ ] Analysis: Acceptable? Yes / No / Needs Tuning

- [ ] **Hold Time 300-600 Seconds**
  - [ ] Minimum hold enforced (300s)
  - [ ] Maximum hold enforced (600s forced exit)
  - [ ] Average hold time: ___ seconds (goal: 300-600)
  - [ ] All positions respecting window? Yes / No

- [ ] **Single Position Loss <$100**
  - [ ] Max single loss: $___ (goal: <$100)
  - [ ] Achieved? Yes / No
  - [ ] If exceeds: Investigate root cause

- [ ] **Daily Loss Limit ≤$50**
  - [ ] Worst day loss: $___ (goal: ≤-$50)
  - [ ] Achieved? Yes / No
  - [ ] Circuit breaker triggered? If yes, when?

- [ ] **Cumulative P&L Positive or Minimal**
  - [ ] 48-hour P&L: $___
  - [ ] Expected: -$0 to -$50 (neutral to minimal loss)
  - [ ] Acceptable? Yes / No

---

## Section 3: HA Failover Readiness

**Requirement:** BACKUP must safely take over if PRIMARY crashes

- [ ] **HA Sync Verification**
  - [ ] Test 1: Sync endpoint returns valid state
    ```bash
    curl -X POST http://localhost:8001/api/ha/sync-from-primary | jq '.account | {cash, positions}'
    # Should show: cash and positions matching PRIMARY
    ```
  - [ ] Test 2: BACKUP can reach PRIMARY
    ```bash
    ssh openhabian@192.168.3.25 "curl -s http://192.168.30.137:8001/api/health | jq '.status'"
    # Should show: "healthy"
    ```
  - [ ] Test 3: SSH tunnel working
    ```bash
    ssh -R 9001:localhost:8001 openhabian@192.168.3.25 "echo 'Tunnel OK'"
    # Should complete without error
    ```

- [ ] **Failover Simulation (Optional but Recommended)**
  - [ ] Stop PRIMARY: `sudo systemctl stop crypto-trading`
  - [ ] Wait 15 seconds
  - [ ] Check BACKUP took over: `curl http://192.168.3.25:8002/api/health | jq '.status'`
  - [ ] Verify state synced: Check cash/positions match
  - [ ] Restart PRIMARY: `sudo systemctl start crypto-trading`
  - [ ] Verify PRIMARY resume: `curl http://localhost:8001/api/health | jq '.status'`

---

## Section 4: Monitoring & Alerting

**Requirement:** System must alert on critical failures

- [ ] **Telegram Alerts Working**
  - [ ] Test PRIMARY: `curl -X POST http://localhost:8001/api/test-telegram`
    - [ ] Response: `{"status": "success"}`
    - [ ] Telegram message received: [PRIMARY] 🧪 Test alert
  
  - [ ] Test BACKUP: `curl -X POST http://192.168.3.25:8002/api/test-telegram`
    - [ ] Response: `{"status": "success"}`
    - [ ] Telegram message received: [BACKUP 🚨] 🧪 Test alert

- [ ] **Baseline Metrics Collection**
  - [ ] File size > 0 bytes: `ls -lah logs/validation_metrics.jsonl`
  - [ ] Metrics being logged every 60s
  - [ ] Key metrics present: memory, sockets, circuit breaker state

- [ ] **Critical Alerts Configured**
  - [ ] Exit failures alert: ✅ or ⏳ (optional for Phase 1)
  - [ ] Circuit breaker open alert: ✅ or ⏳ (optional for Phase 1)
  - [ ] Sync failures alert: ✅ or ⏳ (optional for Phase 1)
  - [ ] Daily loss limit alert: ✅ or ⏳ (optional for Phase 1)

---

## Section 5: Code Quality & Deployment

- [ ] **Code Review**
  - [ ] All 5 blocker fixes reviewed
  - [ ] No new bugs introduced
  - [ ] Comments clear for future maintainers
  - [ ] Commits follow conventional format

- [ ] **Testing**
  - [ ] Unit tests pass: `pytest tests/unit -v`
  - [ ] Integration tests pass: `pytest tests/integration -v`
  - [ ] No type errors: `mypy backend/`
  - [ ] No lint issues: `ruff check .`

- [ ] **Deployment to Both Machines**
  - [ ] PRIMARY: Code deployed and restarted
    - [ ] Health check returns "healthy"
    - [ ] Logs show normal startup
    - [ ] No errors in first 5 minutes
  
  - [ ] BACKUP: Code deployed and restarted
    - [ ] Health check returns "healthy"
    - [ ] Can reach PRIMARY via SSH
    - [ ] Logs show normal startup

- [ ] **Smoke Tests**
  - [ ] PRIMARY API responses: `curl http://localhost:8001/api/health`
  - [ ] BACKUP API responses: `curl http://192.168.3.25:8002/api/health`
  - [ ] WebSocket connections: Check for staleness events in logs
  - [ ] Trade execution: At least 1 successful trade in past hour (paper mode)

---

## Section 6: Final Safety Verification

**Critical Go/No-Go Criteria**

- [ ] **All 5 Blockers Resolved**
  - [ ] Blocker #1: Exit check ✅
  - [ ] Blocker #2: HA sync ✅
  - [ ] Blocker #3: Risk gates ✅
  - [ ] Blocker #4: Observability ✅
  - [ ] Blocker #5: Exceptions ✅

- [ ] **Business Goals Met**
  - [ ] Win rate ≥15%: ✅ or ⏳ (testing ongoing)
  - [ ] Hold time 300-600s: ✅
  - [ ] Single loss <$100: ✅
  - [ ] Daily loss ≤$50: ✅

- [ ] **System Stability Verified**
  - [ ] Zero crashes in past 24h: ✅
  - [ ] Zero critical errors in logs: ✅
  - [ ] Memory usage stable: ✅ (<5%)
  - [ ] CPU usage normal: ✅ (<10%)
  - [ ] No resource leaks: ✅

- [ ] **HA System Ready**
  - [ ] Both machines operational: ✅
  - [ ] Sync working: ✅
  - [ ] Failover tested: ✅
  - [ ] Recovery verified: ✅

- [ ] **Monitoring Active**
  - [ ] Telegram alerts: ✅
  - [ ] Metrics collection: ✅
  - [ ] Log aggregation: ✅
  - [ ] On-call ready: ✅

---

## Section 7: Sign-Off

**Only check "APPROVED FOR LIVE DEPLOYMENT" if ALL items above are completed**

- [ ] **APPROVED FOR LIVE DEPLOYMENT** ✅
  
  All 5 blockers fixed and verified  
  48-hour paper validation passed  
  Business goals achieved  
  HA system tested  
  Monitoring active  
  Ready to deploy $1,000 live capital

**If any item incomplete:**
  - [ ] **HOLD FOR FURTHER WORK**
  - [ ] Not ready for live deployment
  - [ ] Complete remaining items
  - [ ] Recheck before proceeding

---

## Deployment Day Checklist (When Approved)

1. [ ] Backup current configuration
2. [ ] Set initial capital to $1,000
3. [ ] Change TRADING_MODE from "paper" to "live"
4. [ ] Verify both machines see $1,000 starting capital
5. [ ] Enable trading: symbols active, entry signals enabled
6. [ ] Monitor first trade execution
7. [ ] Verify Telegram alert on first entry
8. [ ] Watch P&L for first 24 hours
9. [ ] Be ready to halt trading if needed

---

## Emergency Stop Procedures

**If Something Goes Wrong:**

1. **Immediate Stop:**
   ```bash
   # Stop all trading
   curl -X POST http://localhost:8001/api/emergency-stop
   # Result: No new positions, exit all existing
   ```

2. **Partial Stop:**
   ```bash
   # Disable specific symbol
   curl -X POST http://localhost:8001/api/disable-symbol -d '{"symbol":"BTCUSDT"}'
   ```

3. **Full System Shutdown:**
   ```bash
   # Stop both machines
   sudo systemctl stop crypto-trading
   ssh openhabian@192.168.3.25 "sudo systemctl stop crypto-backup"
   ```

4. **Recovery:**
   - Identify root cause
   - Fix issue
   - Restart services
   - Verify health
   - Resume trading (if safe)

---

**Last Updated:** 2026-07-05  
**Status:** 🔴 IN PROGRESS (blockers being fixed)  
**Expected Completion:** 2026-07-06

