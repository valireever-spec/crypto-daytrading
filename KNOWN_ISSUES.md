# Known Issues & Gaps Inventory

**Last Updated:** 2026-06-25  
**Phase:** 1 (Paper Trading Validation)  
**Status:** ✅ GO FOR PHASE 1

---

## 🔴 Critical Bugs (0 blockers)

### 1. Database Integrity Check Disabled
- **File:** `backend/core/circuit_breaker.py:139`
- **Issue:** `check_database_integrity()` always returns True
- **Why:** Schema not aligned with hash verification; old test data corruption
- **Impact:** Circuit breaker won't detect data corruption
- **Timeline:** Phase 2
- **Fix:** Re-enable after proper schema cleanup

### 2. Backup Machine Code Outdated
- **File:** `/home/claude/crypto-daytrading` (192.168.3.25:8002)
- **Issue:** Running old `autonomous_trader.py` (before sync fix)
- **Why:** User constraint: cannot restart backup machine
- **Impact:** Failover reports 0 positions initially
- **Timeline:** When backup is restarted
- **Workaround:** Manual config sync works; will auto-sync on restart

### 3. Config Sync Endpoint 404 on Backup
- **File:** `POST /api/autonomous/config/sync` (backup)
- **Issue:** Endpoint doesn't exist on older backup code
- **Impact:** Auto-sync from primary fails
- **Timeline:** When backup is restarted
- **Workaround:** ✅ Manual sync via `POST /api/autonomous/config/update` works

---

## 🟠 High-Priority Gaps (Should fix for Phase 1)

### 1. Type Hints Incomplete
- **Files:** ~50+ backend modules
- **Issue:** Only 3 files checked by mypy; rest uncovered
- **Impact:** Type errors not caught until runtime
- **Fix:** Enable mypy check in pre-commit for all backend/
- **Effort:** 4-6 hours
- **Priority:** HIGH (catches bugs early)

### 2. Test Coverage Baseline Missing
- **Issue:** 967 tests exist but no % measured
- **Impact:** Don't know which code paths are untested
- **Fix:** 
  ```bash
  pytest --cov=backend tests/ --cov-report=html
  ```
- **Effort:** 1-2 hours
- **Target:** ≥85% on critical paths

### 3. No Runbooks for Circuit Breaker Triggers
- **File:** `docs/runbooks.md` (exists but minimal)
- **Missing:**
  - WebSocket disconnected >2 min → ?
  - Data quality <30% → ?
  - Position reconciliation failed → ?
  - Daily loss >5% → ?
- **Impact:** On-call won't know how to respond
- **Effort:** 2-3 hours

### 4. No Anomaly Detection
- **Missing:** Alerts for:
  - 5+ consecutive losses
  - Unusual slippage >2%
  - Concentration >50% capital
  - Signal-but-no-fill patterns
- **Timeline:** Phase 2
- **Impact:** Won't detect systematic problems early

---

## 🟡 Medium-Priority Gaps (Nice-to-have for Phase 1)

### 1. API Documentation Missing
- **File:** `docs/API.md` (doesn't exist)
- **Issue:** 23 routers, 50+ endpoints only in code
- **Fix:** Auto-generate from FastAPI annotations
- **Effort:** 2-3 hours

### 2. Incomplete ADRs (Architecture Decision Records)
- **Existing:** ADR-001 (eliminate global state)
- **Missing:**
  - ADR-002: Binance API wrapper vs. library
  - ADR-003: Paper trading in-memory vs. persistent
  - ADR-004: WebSocket vs. REST for prices
- **Effort:** 3-4 hours

### 3. File Size Violations
- `backend/api/main.py`: 2,087 LOC (violates <500 LOC rule)
- `backend/trading/autonomous_trader.py`: 1,448 LOC
- 3 other routers exceed 500 LOC
- **Timeline:** Phase 2 refactoring
- **Impact:** Hard to test/maintain but functional

### 4. Dependency Count = 23 (Target: <10)
- **Current:** 23 packages (borderline)
- **Excess:** ipython, ipdb (dev-only)
- **Fix:** 1 hour cleanup
- **Impact:** Acceptable trade-off for Phase 1

### 5. Log Rotation Not Documented
- **Issue:** logs/ can grow unbounded (currently 970KB)
- **Risk:** Disk exhaustion after 1+ months
- **Fix:** Document archival policy (1 hour)

### 6. No Distributed Tracing
- **Missing:** Request ID propagation
- **Timeline:** Phase 2 (Phase 1 single-machine)
- **Impact:** Hard to debug multi-component issues

---

## 🟢 Known Limitations (By Design)

### 1. Testnet Prices vs. Real Prices
- **Status:** ✅ **FIXED** (2026-06-25)
- **Was:** BTC off by $122, BNB by $5.71
- **Now:** Mainnet prices ±$3-17 (acceptable WebSocket lag)

### 2. Autonomous Trader State Loss on Restart
- **Status:** ✅ **FIXED** (2026-06-25)
- **Was:** API reported 0 positions after restart
- **Now:** Syncs from paper engine on startup

### 3. Fixed Slippage (Not Dynamic)
- **Design:** 0.1% market, 0.05% limit (fixed)
- **Why:** Real slippage varies; fixed % simulates average
- **Risk:** May not match real execution
- **Timeline:** Phase 2 (dynamic model)

### 4. WebSocket-Only Prices (No REST Fallback)
- **Design:** Stream prices from WebSocket only
- **Issue:** If disconnected, prices stale until reconnect
- **Mitigation:** Circuit breaker trips if no update >2 min
- **Acceptable:** Phase 1 (circuit breaker handles this)

---

## 📋 Deferred to Phase 2

| Item | Reason | Effort |
|------|--------|--------|
| GitHub Actions CI/CD | Local pre-commit works | 4-5h |
| Prometheus metrics | Health checks sufficient | 6-8h |
| Refactor main.py & autonomous_trader | Functional as-is | 12-16h |
| Reduce dependencies to <10 | 23 acceptable | 2-3h |
| Database integrity re-enable | Schema cleanup needed | 4-6h |

---

## ✅ Workarounds in Place

### Backup Config Sync
- **Workaround:** Manual sync via `POST /api/autonomous/config/update`
- **Status:** ✅ Tested & working
- **Limitation:** Manual (not auto)

### Data Quality Monitoring
- **Workaround:** Circuit breaker stops trading if <30%
- **Status:** ✅ Working
- **Limitation:** Reactive (stops after detected)

### Position Recovery
- **Workaround:** Database restore on startup
- **Status:** ✅ Working
- **Limitation:** Requires clean DB (blocks corrupted data)

---

## 📊 Phase 1 Readiness

```
Critical Blockers:       0 ✅
High Priority Issues:    4 (manageable)
Medium Priority Gaps:    6 (deferred)
Known Limitations:       4 (acceptable)

VERDICT: ✅ GO FOR PHASE 1

Risk Level: LOW
Conditions:
- Monitor backup machine status
- Track coverage % manually
- Have circuit breaker runbooks
- Monitor type errors manually
```

---

## 🎯 Action Items

### Before Phase 1 Start
- [ ] Review runbooks for circuit breaker triggers
- [ ] Set up manual coverage tracking (`pytest --cov`)
- [ ] Brief team on backup machine status

### During Phase 1
- [ ] Monitor daily loss patterns (track in RETROSPECTIVES.md)
- [ ] Note any type errors encountered
- [ ] Test failover if backup needs restart

### After Phase 1 (Phase 2 Planning)
- [ ] Refactor main.py & autonomous_trader.py
- [ ] Set up GitHub Actions CI/CD
- [ ] Re-enable database integrity check
- [ ] Add Prometheus metrics dashboard
- [ ] Complete missing ADRs

---

**Last Updated:** 2026-06-25  
**Next Review:** End of Phase 1 (2026-07-15)
