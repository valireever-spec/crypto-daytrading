# Quick Reference: Inconsistencies by File

## CRITICAL FIXES REQUIRED

### Timestamp Format Issues

| File | Line | Current | Should Be | Issue |
|------|------|---------|-----------|-------|
| `backend/core/structured_logging.py` | 24 | `datetime.utcnow().isoformat() + "Z"` | ✓ CORRECT | Adds "Z" suffix |
| `backend/analytics/portfolio_analyzer.py` | 150 | `datetime.now().isoformat()` | `datetime.now(timezone.utc).isoformat() + "Z"` | LOCAL time! |
| `backend/analytics/signals.py` | N/A | `pd.Timestamp.now().isoformat()` | Use `datetime.now(timezone.utc)` | LOCAL time! |
| `backend/analytics/history_cleanup_manager.py` | N/A | `datetime.now(timezone.utc).isoformat()` | Add "Z" suffix | Missing "Z" |
| `backend/api/routers/risk_metrics.py` | 69 | `datetime.utcnow().isoformat()` | Add "Z" suffix | Missing "Z" |
| `backend/api/routers/backtest_allocation.py` | N/A | `datetime.utcnow().isoformat()` | Add "Z" suffix | Missing "Z" |
| `backend/core/logging.py` | 21 | `datetime.utcnow().isoformat() + "Z"` | ✓ CORRECT | Adds "Z" suffix |

### Configuration Default Mismatches

| Setting | `.env.example` | `backend/core/config.py` | Correct Value | Impact |
|---------|---|---|---|---|
| MAX_DAILY_LOSS_PCT | 8.0 | 5.0 | ? | 60% difference in risk control! |
| MAX_POSITIONS | 6 | 5 | ? | 20% difference |
| POSITION_SIZE_PCT | 2.0 | 1.5 | ? | 33% more aggressive |
| INITIAL_CAPITAL | 10000.0 | 10000.0 | ✓ | Matches |

**Decision Required:** Which is source of truth?

---

## HIGH SEVERITY ISSUES

### Market Regime Case Mismatch

| File | Line | Returns | Expects | Status |
|------|------|---------|---------|--------|
| `backend/analytics/regime_detector.py` | 87, 90, 93, 96 | `"BULL"`, `"BEAR"`, `"SIDEWAYS"`, `"VOLATILE"` | - | SOURCE |
| `backend/analytics/portfolio_regime_monitor.py` | 196 | - | `"bull"` | Broken comparison |
| `backend/analytics/sector_rotation_advisor.py` | 131 | - | `"bear"` | Broken comparison |
| `backend/api/routers/risk_metrics.py` | 141 | - | `["bull", "bear", "sideways", "volatile"]` | API expects lowercase |

**Fix:** Update `regime_detector.py` to return lowercase

### Account State Field Naming

| File | Line | Access Pattern | Comment |
|------|------|---|---|
| `backend/exchange/paper_trading.py` | 227 | Returns `"cash"` | SOURCE |
| `backend/execution/smart_executor.py` | 91 | `account.get("cash") or account.get("available_cash", 0)` | DEFENSIVE |
| `backend/execution/portfolio_orchestrator.py` | 87 | `account.get("cash", 0)` | ASSUMES "cash" |

**Fix:** Document that key is always `"cash"`, remove defensive code

### Order Status Values

| File | Line | Declared | Used | Issue |
|------|------|---|---|---|
| `backend/exchange/paper_trading.py` | 40 | `Literal["FILLED", "CANCELLED"]` | - | Type definition |
| `backend/exchange/paper_trading.py` | 105, 195 | - | `"REJECTED"` | NOT IN LITERAL |
| `backend/execution/smart_executor.py` | 19 | Comment: `# EXECUTE, WAIT, REJECT` | - | "WAIT" never used |

**Fix:** Update Literal to include "REJECTED", remove "WAIT"

---

## MEDIUM SEVERITY ISSUES

### API Response Structure (Inconsistent Wrappers)

| Endpoint | File | Line | Response Structure |
|----------|------|------|---|
| `GET /api/autonomous/status` | `autonomous.py` | 38 | Returns `trader.get_status()` — unknown structure |
| `POST /api/autonomous/start` | `autonomous.py` | 53-56 | `{"status": "started", "message": "..."}` |
| `GET /api/autonomous/config` | `autonomous.py` | 81-90 | `{"entry_threshold": ..., "exit_profit_target": ...}` |
| `GET /api/risk/limits` | `risk_management.py` | 38-48 | `{"limits": {...}}` nested |
| `GET /api/risk/portfolio-var` | `risk_management.py` | 108-114 | `{"portfolio_value": ..., "var_95": ...}` flat |

**Fix:** Adopt standard: `{"status": "success|error", "data": {...}}`

### Logging Format Inconsistency

| Module | File | JSON Fields | Issue |
|--------|------|---|---|
| JSONFormatter (old) | `backend/core/logging.py` | timestamp, level, logger, message | Basic |
| JSONFormatter (new) | `backend/core/structured_logging.py` | timestamp, level, logger, message, **function, line, module** | Enhanced |

**Issue:** `main.py:21-22` imports BOTH modules

**Fix:** Consolidate to `structured_logging.py` only, remove `logging.py`

### Error Response Patterns

| File | Line | Status | Detail | Count | Issue |
|------|------|--------|--------|-------|-------|
| `autonomous.py` | 36, 46, 64, 79, 98, 150, 178 | 500 | "Autonomous trader not initialized" | 7x DUP | Wrong status code (should be 503) |
| `rebalancing.py` | 28 | 400 | "Missing allocations" | 1x | ✓ Correct |
| `risk_metrics.py` | 63 | 503 | "Paper trading engine not available" | 1x | ✓ Correct |

**Fix:** 
- Use 503 Service Unavailable for "not initialized"
- Extract error messages to constants
- Define error response wrapper

### Decision Field Naming

| Class | File | Field Name | Values |
|-------|------|---|---|
| `ExecutionDecision` | `smart_executor.py:19` | `decision` | EXECUTE, WAIT, REJECT |
| `PortfolioAction` | `portfolio_orchestrator.py:35` | `action_type` | REDUCE, REBALANCE, ENTER, EXIT, HOLD |

**Issue:** Similar concepts use different field names

**Fix:** Standardize on one naming convention across decision classes

---

## CONSISTENCY CHECKS (No Action Needed)

### Entry Price ✓
- Consistently named `entry_price` across all files
- Used in: `paper_trading.py`, `exit_manager.py`, `portfolio_orchestrator.py`
- Status: **CONSISTENT**

### Quantity ✓
- Consistently named `quantity` across all files
- Used in: `paper_trading.py`, `exit_manager.py`, `smart_executor.py`
- Status: **CONSISTENT**

---

## Impact Assessment Matrix

### Risk Assessment

| Issue | Likelihood | Severity | Risk Level |
|-------|------------|----------|-----------|
| Timestamp mismatch | HIGH | HIGH | **CRITICAL** |
| Config defaults | HIGH | CRITICAL | **CRITICAL** |
| Regime case mismatch | HIGH | HIGH | **CRITICAL** |
| Cash field naming | MEDIUM | MEDIUM | **HIGH** |
| Status inconsistency | MEDIUM | MEDIUM | **HIGH** |
| API responses | LOW | MEDIUM | **MEDIUM** |
| Logging duplication | LOW | MEDIUM | **MEDIUM** |
| Error codes | LOW | LOW | **LOW** |

---

## Testing Checklist

- [ ] Timestamp format test: All UTC times include "Z" suffix
- [ ] Config test: Code defaults match .env.example
- [ ] Regime test: All regimes lowercase, case-insensitive comparisons
- [ ] Cash field test: All account state uses `"cash"` key
- [ ] Status test: Trade statuses match Literal definition
- [ ] API test: All endpoints return `{"status": "...", "data": {...}}`
- [ ] Logging test: All logs produce valid JSON with required fields
- [ ] Error test: 503 for unavailable services, 400 for bad requests

---

## Migration Path

### Phase 1 (This Sprint - CRITICAL)
1. Fix timestamp format globally (2-3 hours)
2. Resolve config defaults (1 hour)
3. Fix regime case (2 hours)

### Phase 2 (Next Sprint - HIGH)
1. Standardize account fields (2 hours)
2. Fix status values (2 hours)
3. Add tests for all three fixes (4 hours)

### Phase 3 (Following Sprint - MEDIUM)
1. Consolidate logging (2 hours)
2. Standardize API responses (4-6 hours)
3. Fix error handling (2 hours)
4. Add integration tests (4 hours)

**Total Effort Estimate:** 24-28 hours
