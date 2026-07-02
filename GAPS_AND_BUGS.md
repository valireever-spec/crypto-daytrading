# Gap & Bug Analysis - Crypto Daytrading Platform
**Generated:** 2026-07-02  
**Status:** API operational, but HA deployment NOT READY

---

## 1. CRITICAL ISSUES (MUST FIX BEFORE LIVE TRADING)

### 🔴 Thread Safety — HA NOT READY
**Issue:** 94 critical globals without thread locks  
**Impact:** Cannot safely deploy to BACKUP (race conditions, state corruption)  
**Fix Available:** `backend/core/ha_globals_manager.py` + migration script  
**Blockers:** Circular import in allocation.py/portfolio_optimizer.py (attempted Phase 1)  
**Effort:** 6-8 hours for careful re-migration  

### 🔴 Database Sync Failing at Startup
**Issue:** `/home/claude/crypto-daytrading/data/` directory doesn't exist on BACKUP  
**Error Log:** `Database sync failed: [Errno 2] No such file or directory`  
**Impact:** BACKUP database not synced (PRIMARY continues, but BACKUP is out of sync)  
**Fix:** `mkdir -p /home/claude/crypto-daytrading/data/` on BACKUP machine  
**Effort:** 2 minutes  

### 🔴 HA Failover Never Tested
**Missing Tests:**
- Failover when PRIMARY dies
- Both machines trading simultaneously (split-brain)
- Network partition scenarios
- State consistency after failover

**Risk:** Unknown failure modes in production  
**Effort:** 4-6 hours (chaos testing + stress tests)

---

## 2. HIGH PRIORITY (BEFORE PAPER TRADING PHASE)

### 🟠 Missing Test Coverage for New Code
**Critical Modules Without Tests:**
- `backend/core/ha_globals_manager.py` (271 lines, untested)
- `backend/exchange/websocket_manager.py` (400+ lines, no unit tests)
- `backend/core/circuit_breaker_v2.py` (180+ lines, no state transition tests)
- HA failover scenarios (no dedicated tests)
- Database authority detection edge cases

**Coverage Gaps:**
```
- Circuit breaker CLOSED → DEGRADED → OPEN transitions
- WebSocket reconnection with exponential backoff (1s → 2s → 4s... → 60s)
- REST polling fallback behavior under load
- Trade execution when circuit breaker in DEGRADED state
- Split-brain detection and recovery
```

**Effort:** 8-10 hours  

### 🟠 No Monitoring/Observability
**Missing:**
- API response time metrics
- WebSocket message latency tracking
- Trade execution failure alerts
- Position reconciliation mismatch detection
- Database sync lag monitoring
- Circuit breaker state change alerts

**Current State:** Only structured JSON logs (no dashboard, no aggregation)  
**Impact:** Can't detect degradation until trading breaks  
**Effort:** 6 hours (Prometheus + Grafana setup)  

### 🟠 No Runtime Configuration Management
**Issue:** Trading parameters hardcoded in Python code:
```python
entry_threshold = 50/65  # Should be configurable
exit_profit_target = 0.025  # 2.5%
exit_stop_loss = 0.015  # 1.5%
max_positions = 10
```

**Impact:** Changing strategy requires code change + redeploy  
**Solution Ready:** `system_config.json` design exists (in memory notes)  
**Effort:** 4 hours (implement runtime config loading)  

---

## 3. MEDIUM PRIORITY (BEFORE LIVE TRADING)

### 🟡 Legacy WebSocket Duplication
**Issue:** Two WebSocket implementations running in parallel:
1. `backend/exchange/websocket_manager.py` (new, with fallback)
2. `backend/exchange/binance_stream.py` (legacy, for backward compatibility)

**Risk:** Duplicate price processing, memory overhead  
**Solution:** Deprecate legacy stream (keep new manager only)  
**Effort:** 2 hours (safe cleanup + validation)  

### 🟡 Database Architecture Limitation
**Issue:** SQLite on individual machines → trade history NOT synced  
**Current State:**
- Positions synced ✅
- Cash synced ✅
- Trade history NOT synced ❌

**Impact:** Lose trading history on failover  
**Solution:** Move to PostgreSQL shared database (Phase 3 plan)  
**Timeline:** Not critical for Phase 1 paper trading  
**Effort:** 8 hours (Phase 3 work)  

### 🟡 Input Validation Gaps
**Issue:** API endpoints accept unvalidated input  
**Risk:** Invalid strategy parameters could cause unexpected behavior  
**Examples:** No validation on:
- Symbol lists (must match available)
- Risk parameters (must be sensible ranges)
- Position size multipliers (must be >0 and <max)

**Effort:** 3 hours (add Pydantic models to all endpoints)  

### 🟡 API Endpoint Gaps
**Missing Endpoints:**
- `GET /api/config` — Get current runtime configuration
- `POST /api/config` — Update configuration without restart
- `GET /api/trades/analysis` — P&L breakdown by strategy
- `POST /api/failover` — Manual failover trigger (testing)
- `GET /api/ha/status` — Detailed HA state (PRIMARY vs BACKUP)

**Effort:** 4 hours  

---

## 4. LOW PRIORITY (OPTIMIZATION)

### 🟢 WebSocket Startup Staleness Warning
**Log:** `WebSocket stale prices: BTCUSDT(infs), ETHUSDT(infs), BNBUSDT(infs)`  
**Root Cause:** Expected during first 1-2 seconds of startup  
**Actual Impact:** None (auto-recovers with reconnection)  
**Fix:** Suppress warning during initialization warmup  
**Effort:** 1 hour  

### 🟢 Performance Limitations
**Current Constraints:**
- Max 3 symbols (hardcoded: BTCUSDT, ETHUSDT, BNBUSDT)
- Signal thread pool: 2 workers only
- REST polling: 1-second interval (when WebSocket down)
- No request rate limiting on API

**Effort:** 2-3 hours (add symbol scaling, rate limiting)  

---

## BLOCKER STATUS

| Issue | Blocks | Timeline | Effort |
|-------|--------|----------|--------|
| **Thread safety (94 globals)** | HA deployment | Week 2 | 8h |
| **Database sync (missing dir)** | BACKUP sync | Today | 2m |
| **HA failover untested** | Live trading | Week 1 | 6h |
| **Test coverage gaps** | Live trading | Week 1 | 10h |
| **No monitoring** | Production | Week 2 | 6h |
| **Runtime config** | Multi-strategy trading | Week 2 | 4h |

---

## IMMEDIATE ACTIONS (Next 2 Hours)

### 1. Fix Database Sync (2 min)
```bash
ssh claude@192.168.3.25 "mkdir -p /home/claude/crypto-daytrading/data/"
```

### 2. Disable Legacy Binance Stream (30 min)
- Stop running both WebSocket implementations
- Keep only `websocket_manager.py`
- Verify prices still flowing

### 3. Add Missing Tests (2-3 hours)
- WebSocket manager unit tests
- Circuit breaker state transition tests
- HA failover scenario tests

### 4. Document Current State (1 hour)
- Runbook: How to safely deploy BACKUP
- Runbook: How to recover from split-brain
- Runbook: How to manually sync databases

---

## PHASE READINESS

### Paper Trading (Phase 1) → **READY** ✅
- API works
- WebSocket recovers automatically
- Circuit breaker prevents runaway losses
- Single machine is safe

### HA Deployment (Phase 2) → **NOT READY** ❌
- Thread safety incomplete (94 globals)
- Failover untested
- Database sync unreliable
- No split-brain detection

### Live Trading (Phase 3) → **NOT READY** ❌
- All Phase 2 blockers apply
- Plus: No monitoring/alerting
- Plus: Runtime config hardcoded
- Plus: Trade history not synced

---

## RECOMMENDATION

**Next Step:** Complete Phase 1 paper trading validation (10+ days), THEN:
1. Fix thread safety (Phase 1 HA migration — careful re-do)
2. Add HA failover tests (chaos testing)
3. Implement runtime configuration
4. Deploy to BACKUP for HA testing

**DO NOT deploy to live trading until:**
- All Phase 2 work complete
- HA failover tested under load
- Monitoring/alerting in place
- Trade history persistence working
