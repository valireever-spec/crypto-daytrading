# Phase 1 Gaps & Post-Phase 1 Fixes

**Document:** Bug & Gap Tracker  
**Status:** Phase 1 Running (defer fixes to post-Phase 1)  
**Target Fix Date:** 2026-07-05 to 2026-07-15 (before Phase 2 live trading)

---

## Critical Gaps (Must Fix Before Phase 2 Live Trading)

### 1. State Persistence on Crash ⚠️ CRITICAL
**Category:** Resilience  
**Severity:** CRITICAL  
**Impact:** On API crash, all open positions lost (no recovery)  
**Symptoms:** Restart API → active_positions empty, trades abandoned  
**Fix Scope:** Save position state to SQLite before each trade, restore on startup  
**Phase 1 Risk:** None (paper trading, acceptable to restart)  
**Phase 2 Risk:** CRITICAL (real money exposed)  
**Estimated Effort:** 4-6 hours  

### 2. Partial Fill Handling ⚠️ CRITICAL
**Category:** Order Execution  
**Severity:** CRITICAL  
**Impact:** Order fills partially, position size recorded wrong  
**Symptoms:** Order placed 0.5 qty, Binance fills 0.3, code thinks 0.5 is open  
**Fix Scope:** Poll Binance until order status = FILLED or CANCELED, retry logic  
**Phase 1 Risk:** Low (Binance paper trading rarely partials)  
**Phase 2 Risk:** CRITICAL (live market gaps/slippage)  
**Estimated Effort:** 3-4 hours  

### 3. Slippage Assumptions Unvalidated ⚠️ CRITICAL
**Category:** Risk Management  
**Severity:** CRITICAL  
**Impact:** 0.1% slippage assumed, real slippage could be 0.5%+ in crypto  
**Symptoms:** P&L worse than backtested, losses exceed expectations  
**Fix Scope:** Log actual vs expected price, measure slippage distribution  
**Phase 1 Risk:** Medium (overestimate win rate if slippage high)  
**Phase 2 Risk:** CRITICAL (loses money if assumption wrong)  
**Estimated Effort:** 2-3 hours (instrumentation + analysis)  

### 4. Daily P&L Not Resetting ⚠️ HIGH
**Category:** Risk Management  
**Severity:** HIGH  
**Impact:** Daily loss limit shows cumulative, not daily  
**Symptoms:** Day 1: €500 loss → trading paused, but should reset Day 2  
**Fix Scope:** Track P&L per-day, reset at 00:00 UTC daily  
**Phase 1 Risk:** High (prevents testing on losing days)  
**Phase 2 Risk:** HIGH (capital could be trapped)  
**Estimated Effort:** 1-2 hours  

### 5. Config Unification ⚠️ MEDIUM
**Category:** Configuration  
**Severity:** MEDIUM  
**Impact:** Different config sources (code defaults, .env, persistent JSON)  
**Symptoms:** Config changed in .env but code has hardcoded 0.015 override  
**Fix Scope:** Single source of truth (ConfigManager), no code defaults  
**Phase 1 Risk:** Low (manually verified before Phase 1)  
**Phase 2 Risk:** MEDIUM (changes could silently fail)  
**Estimated Effort:** 2-3 hours  

---

## High-Priority Gaps (Fix Before Phase 2)

### 6. Graceful Shutdown Missing ⚠️ HIGH
**Category:** Reliability  
**Fix Scope:** SIGTERM handler to close open positions, flush logs  
**Phase 1 Risk:** Low  
**Phase 2 Risk:** HIGH  

### 7. Log Rotation Missing ⚠️ MEDIUM
**Category:** Operations  
**Fix Scope:** Rotate logs daily, archive old ones  
**Phase 1 Risk:** Low (single 10-day run)  
**Phase 2 Risk:** MEDIUM (disk fill risk in production)  

### 8. RSI Division-by-Zero Workaround ⚠️ MEDIUM
**Category:** Code Quality  
**Symptom:** Using 0.0001 as min volatility guard (fragile)  
**Fix Scope:** Proper volatility buffer logic  
**Phase 1 Risk:** Low  
**Phase 2 Risk:** MEDIUM  

### 9. Double-Entry Risk (Same Symbol) ⚠️ MEDIUM
**Category:** Risk Management  
**Symptom:** Position limit enforced in code, but logic could be wrong  
**Fix Scope:** Unit test position limit enforcement  
**Phase 1 Risk:** Low  
**Phase 2 Risk:** MEDIUM  

### 10. Regime Detection Robustness ⚠️ MEDIUM
**Category:** Signal Quality  
**Symptom:** Stuck at "unknown" regime → signals unreliable  
**Fix Scope:** Better regime detection, fallback to default  
**Phase 1 Risk:** Medium (see Day 5 checkpoint)  
**Phase 2 Risk:** HIGH  

### 11. Price Staleness Detection ⚠️ MEDIUM
**Category:** Data Quality  
**Fix Scope:** Check timestamp age, warn if >5 min old  
**Phase 1 Risk:** Low  
**Phase 2 Risk:** MEDIUM  

### 12. Binance Rate Limiting ⚠️ MEDIUM
**Category:** API Safety  
**Fix Scope:** Respect 1200 req/min limit, add backoff  
**Phase 1 Risk:** Low  
**Phase 2 Risk:** MEDIUM  

---

## Medium-Priority Gaps (Fix In Phase 2+)

### 13. Look-Ahead Bias in Backtesting ⚠️ MEDIUM
**Category:** Testing  
**Issue:** Backtest uses tomorrow's price to decide today's trade  
**Fix Scope:** Strict temporal isolation in backtest replay  

### 14. Regime Adjustment of Thresholds ⚠️ MEDIUM
**Category:** Strategy  
**Issue:** Entry threshold same in bull/bear/sideways (should differ)  
**Fix Scope:** Regime-aware threshold adjustment (75 in bear, 55 in bull)  

### 15. Position Averaging (Pyramid) ⚠️ MEDIUM
**Category:** Strategy  
**Issue:** Not implemented, only new entries  
**Fix Scope:** Add pyramid scaling (Phase 2+)  

### 16. Cost Averaging (Average Down) ⚠️ LOW
**Category:** Strategy  
**Issue:** Not implemented, too risky without validation  
**Fix Scope:** Add after win rate stable >55%  

### 17. Tax Tracking ⚠️ MEDIUM
**Category:** Reporting  
**Issue:** No tax-lot accounting for capital gains  
**Fix Scope:** Track cost basis, calculate gains, export for tax filing  

### 18. Multi-Timeframe Analysis ⚠️ MEDIUM
**Category:** Signals  
**Issue:** All signals from 1H candles, no multi-TF confirmation  
**Fix Scope:** Add 4H/1D confirmation for signal strength  

### 19. Correlation-Based Risk ⚠️ MEDIUM
**Category:** Risk Management  
**Issue:** Position size doesn't account for symbol correlations  
**Fix Scope:** Measure portfolio correlation, reduce sizes if correlated  

### 20. Dynamic Position Sizing ⚠️ LOW
**Category:** Strategy  
**Issue:** Fixed 5% per trade regardless of market volatility  
**Fix Scope:** Adjust position size based on current volatility  

### 21. Trade Journaling ⚠️ MEDIUM
**Category:** Learning  
**Issue:** No manual annotations on trades (why did this win/lose?)  
**Fix Scope:** API endpoint to add post-trade notes  

### 22. Backtesting with Live Fees ⚠️ MEDIUM
**Category:** Accuracy  
**Issue:** Backtests assume 0.1% fees, live is 0.075% maker / 0.1% taker  
**Fix Scope:** Use accurate fee schedule in backtest  

---

## Phase 1 Success Criteria (Ignore These Gaps During Phase 1)

**These gaps do NOT block Phase 1 success:**
- State persistence (can restart)
- Partial fills (paper trading rarely partials)
- Slippage measurement (can estimate post-Phase 1)
- Log rotation (single 10-day run)
- Tax tracking (paper trading only)

**Phase 1 Focus:** Validate >55% win rate, positive P&L, system stability

**Phase 2 Gate:** Fix items 1-12 (Critical & High) before live trading with €1,000

---

## Timeline

### Phase 1 (2026-06-25 to 2026-07-05)
- ✅ Run paper trading for 10 days
- ✅ Monitor daily for crashes, errors, win rate
- ⏳ Collect P&L data and trade logs
- ⏳ Analyze signal quality and slippage

### Post-Phase 1 (2026-07-05 to 2026-07-15)
- Fix items 1-5 (Critical: 6-8 hours each)
- Fix items 6-12 (High: 1-3 hours each)
- Validate with 3-day paper retest
- Prepare Phase 2 deployment

### Phase 2+ (2026-07-15+)
- Live trading with €1,000 (items 1-12 fixed)
- Fix items 13-22 as needed (continuous improvement)

---

## How to Track This Document

**In Tracker System:**
- Link to `FUNCTIONAL_REQUIREMENTS.md` → "FR-002: Paper trading engine"
- Link to `NONFUNCTIONAL_REQUIREMENTS.md` → "NFR-013: Resilience & Recovery"
- Each bug maps to a requirement gap

**Commit Reference:**
```bash
git log --oneline --grep="gap\|bug\|fix" | head -20
```

**Post-Phase 1 Checklist:**
```bash
# After 2026-07-05, before proceeding to Phase 2:
[ ] Fix #1: State persistence
[ ] Fix #2: Partial fills
[ ] Fix #3: Slippage validation
[ ] Fix #4: Daily P&L reset
[ ] Fix #5: Config unification
[ ] Fix #6: Graceful shutdown
[ ] Fix #7: Log rotation
[ ] Fix #8: RSI division-by-zero
[ ] Fix #9: Double-entry risk
[ ] Fix #10: Regime detection
[ ] Fix #11: Price staleness
[ ] Fix #12: Rate limiting
[ ] 3-day paper retest
[ ] Code review + approval
[ ] → Ready for Phase 2 live
```

---

**Document Status:** READY FOR TRACKING  
**Last Updated:** 2026-06-25  
**Next Review:** 2026-07-05 (post-Phase 1)
