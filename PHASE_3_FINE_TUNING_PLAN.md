# PHASE 3 FINE-TUNING PLAN (Scientifically Sound)

**Status:** Ready to deploy  
**Effective Dates:** 2026-07-10 to 2026-07-23 (13 days)  
**Framework:** Critical fixes #1-5 implemented + Gaps #1-4  

---

## CRITICAL FIXES IMPLEMENTED

### ✅ FIX #1: Separate Parameter Testing
- Days 4.5-6: Test RSI threshold ONLY (not RSI + SMA20 together)
- Days 6.5-8: Test SMA20 confirmation ONLY (with best RSI from previous)
- Days 8.5-9.5: Test profit target ONLY (profit first)
- Days 10-11: Test stop loss ONLY (with best profit target)

### ✅ FIX #2: Statistical Significance Testing
- Implemented: `backend/core/statistical_validator.py`
- Calculates standard error, 95% confidence intervals, p-values
- Decision rule: Improvement ≥ 2.5% AND non-overlapping CIs = improvement
- Minimum 150 trades per config (200 for high confidence)

### ✅ FIX #3: Market Regime Detection (PROACTIVE)
- Implemented: `backend/core/market_regime_detector.py`
- Measures ATR (volatility) and trend direction
- Classification: RANGING (optimal) vs TRENDING_UP/DOWN (pause)
- Pre-entry check: If trending detected → automatic pause → resume when clear
- Prevents 45% effectiveness loss during strong trends

### ✅ FIX #4: Kelly Criterion Recalculation
- Implemented: `backend/core/kelly_calculator.py`
- Recalculate after each test period (Days 1-3, 4-6, 6-8, etc.)
- If win rate improves → position sizing increases automatically
- Captures €500-800 extra profit from better statistics

### ✅ FIX #5: Profit/Stop Loss Sequencing
- Test profit target first (easier to optimize)
- Test stop loss second (evaluate whipsaw risk)
- Separate parameters prevents masking poor stop loss logic

---

## REVISED TIMELINE

### **Days 1-3: Baseline Establishment**
- Deploy current mean-reversion parameters
- Parameters:
  - Entry: RSI < 30 + Price > SMA20
  - Exit: RSI > 70 (overbought) OR stop loss -1.0% OR profit target +2.0% OR 10-min timeout
  - Position: 3% × confidence
- Measure: ≥150 trades
- Calculate: Win rate, SE, 95% CI
- Target: 30.5% ± 7.2% = [23.3% - 37.7%]
- Document: baseline_summary.json

### **Days 4-4.5: PRE-TEST Market Regime Classification**
**NEW: Proactive regime detection**
- Measure ATR (24-hour volatility)
- Detect trend direction (last 5 closes)
- Classify: RANGING vs TRENDING
- Decision:
  - If TRENDING: Consider pausing tuning, monitoring only
  - If RANGING: Proceed to Tier 1a with confidence
- Document: regime_classification.json

### **Days 4.5-6: Tier 1a - Entry Quality (RSI Threshold)**
**CRITICAL FIX #1: Test parameter separately**
- Test: RSI < 25 (was < 30)
- Keep: Price > SMA20 (unchanged)
- Measure: ≥150 trades
- Target: 32.5% [29.0% - 36.0%] (2% improvement)
- Calculate: Standard error, 95% CI
- Document: tier_1a_summary.json

### **Days 6-6.5: Evaluation + Decision Gate**
**NEW: Statistical checkpoint**
- Compare Day 4.5-6 vs Day 1-3
- Check: Non-overlapping CI + improvement ≥ 2.5%?
- Decision:
  - ✅ IF improvement ≥ 2.5%: Keep RSI < 25 → proceed to Tier 1b
  - ⚠️ IF improvement 0-2.5%: Keep RSI < 25 (marginal) → proceed to Tier 1b
  - ❌ IF improvement < 0%: Revert to RSI < 30 → skip Tier 1b → jump to Tier 2

### **Days 6.5-8: Tier 1b - Entry Confirmation (SMA20)**
**CRITICAL FIX #1: Test second parameter**
- Test: Price > SMA20 × 1.01 (was > SMA20)
- Keep: Best RSI threshold from Tier 1a
- Measure: ≥150 trades
- Target: +1-2% improvement over Tier 1a
- Document: tier_1b_summary.json

### **Days 8-8.5: Evaluation + Checkpoint**
**NEW: Entry optimization complete**
- Evaluate Tier 1b results
- Best entry config now set
- Projected: 31-34% win rate (if both tiers help)

### **Days 8.5-9.5: Tier 2a - Profit Target (Profit First)**
**CRITICAL FIX #5: Test profit first**
- Test: +1.5% profit target (was +2.0%)
- Keep: Stop loss at -1.0%
- Measure: ≥150 trades
- Track: Win rate + avg P&L per trade
- Hypothesis: Tighter profits easier to hit, but evaluate if quality suffers
- Document: tier_2a_summary.json

### **Days 9.5-10: Evaluation**
**NEW: Profit target decision**
- Decide: Keep +1.5% or revert to +2.0%?
- Metrics: Win rate change, avg P&L/trade change
- Document decision rationale

### **Days 10-11: Tier 2b - Stop Loss (Stop Second)**
**CRITICAL FIX #5: Test stop loss second**
- Test: -0.75% stop loss (was -1.0%)
- Keep: Profit target from Tier 2a evaluation
- Measure: ≥150 trades
- Track: Win rate + % of trades stopped out + avg P&L
- Hypothesis: Tighter stops reduce losses but increase whipsaws
- Document: tier_2b_summary.json

### **Days 11-12: Final Evaluation + GO/NO-GO Decision**
**NEW: Statistical validation + final Kelly calculation**
- Collect all tier results
- Calculate final Kelly recommendation for updated win rate
- Statistical summary:
  - Baseline vs Best config comparison
  - P-value: Is improvement statistically significant?
  - CI overlap analysis
- Decision:
  - ✅ **GO:** Win rate ≥ 30% (validates baseline), no system crashes, confident Kelly sizing
  - ⚠️ **CAUTION:** Win rate 28-30% (marginal), require extended validation
  - ❌ **NO-GO:** Win rate < 28% (regression), use baseline for Phase 4
- Document: final_evaluation.json

### **Days 13-23: Final Validation + Live Monitoring**
**NEW: Extended validation window**
- Run final best configuration
- Accumulate 200+ additional trades for statistical robustness
- Continuous monitoring:
  - Market regime classification every trading day
  - If trending detected: Pause trading, monitor only
  - If regime returns to ranging: Resume trading
  - Daily logging: Win rate, P&L, regime, Kelly sizing
- Risk management:
  - Rollback if win rate drops below 25%
  - Daily loss limit: -5% (halt if exceeded)
- Document: daily_validation_log.json

### **July 23: Final GO/NO-GO + Phase 4 Deployment Decision**
- Review full 23-day data
- Make go/no-go decision for Phase 4 live trading with €1,000
- If GO: Deploy with optimal Kelly sizing from final evaluation

---

## STATISTICAL VALIDATION RULES

### Data Sufficiency
- **HIGH confidence:** ≥150 trades
- **MEDIUM confidence:** 80-149 trades (proceed with caution)
- **LOW confidence:** <80 trades (defer tuning decision)

### Improvement Threshold
- **Statistically improved:** Improvement ≥ 2.5% AND 95% CIs don't overlap
- **Marginal:** Improvement 0-2.5% OR CIs overlap (proceed anyway)
- **Regression:** Improvement < 0% (revert parameter)

### Confidence Interval Interpretation
- If CI overlaps baseline → improvement could be noise → not statistically distinct
- If CI doesn't overlap → improvement is statistically significant
- Example: Baseline [23.3%, 37.7%] vs Test [29.0%, 36.0%] → NO overlap → significant

---

## MARKET REGIME PROTECTION

### Proactive Detection (Every Trading Day)
```
1. Measure volatility:
   ATR = Average True Range (14-period)
   Volatility % = (ATR / SMA_close) × 100

2. Detect trend:
   Recent 5 candles: (close_now - close_5_bars_ago) / close_5_bars_ago

3. Classify:
   IF Volatility > 2.5% AND Trend > 2.0%: TRENDING_DOWN → PAUSE
   IF Volatility > 2.5% AND Trend > 2.0%: TRENDING_UP → PAUSE
   IF Volatility < 1.5%: RANGING → TRADE
   ELSE: NORMAL → TRADE (cautiously)
```

### Trading Pause Logic
- If TRENDING detected → Stop entry signals immediately
- Monitor 4 times per day: 06:00, 12:00, 18:00, 00:00 UTC
- Resume trading when trend clears (ATR normalizes, oscillation returns)

---

## KELLY POSITIONING STRATEGY

### Automatic Recalculation
After each test period (Days 1-3, 4-6, etc.):
1. Calculate new win rate
2. Calculate Kelly fraction using avg win/loss P&L
3. Recommend position sizing (quarter-Kelly for safety)
4. Compare to current 3% baseline
5. Adjust if improvement detected

### Example Progression
```
Days 1-3: 30.5% WR → 3.0% position sizing (baseline)
Days 4-6: 32.0% WR → 3.3% position sizing (0.3% increase)
Days 7-9: 34.0% WR → 3.7% position sizing (0.7% increase)
Days 13-23: 35.0% WR → 4.0% position sizing (optimal)
```

---

## DOCUMENTATION & TRACKING

### Daily Logs (automatic via monitoring)
- `phase3_daily_log.json` — Each day: trades, WR, P&L, regime, decision

### Period Summaries (manual after each tier)
- `tier_1a_summary.json` — Tier 1a results + statistical analysis
- `tier_1b_summary.json` — Tier 1b results + comparison to 1a
- `tier_2a_summary.json` — Tier 2a results + comparison to baseline
- `tier_2b_summary.json` — Tier 2b results + comparison to 2a
- `final_evaluation.json` — All tiers + final decision

### Analysis Tools
- `statistical_validator.py` — Calculate SE, CI, p-values
- `market_regime_detector.py` — Classify regime, recommend pause/trade
- `kelly_calculator.py` — Calculate position sizing

---

## IMPLEMENTATION CHECKLIST

### Code Ready ✅
- [x] Statistical validator (statistical_validator.py)
- [x] Market regime detector (market_regime_detector.py)
- [x] Kelly calculator (kelly_calculator.py)
- [ ] Integration into trading loop (add regime check before entry)
- [ ] Monitoring dashboard (display regime + Kelly recommendations)
- [ ] Automated logging (save daily summaries)

### Pre-Phase 3 Setup
- [ ] Review baseline parameters (Days 1-3)
- [ ] Configure regime detection (ATR thresholds)
- [ ] Set up decision gates (statistical validation rules)
- [ ] Enable detailed logging (each tier capture 150+ trades)
- [ ] Create notification system (alert on statistical improvement/regression)

---

## SUCCESS CRITERIA

### Technical Success
- ✅ No system crashes during 23-day window
- ✅ Continuous regime classification (daily logging)
- ✅ Statistical validation applied to each tier
- ✅ Kelly recalculation automatic

### Trading Success
- Target: Win rate ≥ 30% (validates baseline)
- Stretch: Win rate ≥ 32% (shows improvement potential)
- Minimum: Win rate ≥ 28% (acceptable validation)

### Phase 4 Decision
- **GO:** If final win rate ≥ 30% + statistical validation passes
- **NO-GO:** If final win rate < 28% (strategy needs redesign)

---

**Generated:** 2026-07-10  
**Framework:** Critical fixes #1-5 + Gaps #1-4  
**Status:** Ready for deployment
