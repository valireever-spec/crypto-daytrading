# 24-Hour Validation Checkpoint Schedule

**Status:** ✅ Both machines operational and ready  
**Start Time:** 2026-07-05 20:53 UTC  
**End Time:** 2026-07-06 14:53 UTC (24 hours)  
**Target Win Rate:** 45-55% (realistic for crypto)

---

## Baseline (Now)

```
PRIMARY:   249 trades, -$5.19 daily, -$40.92 total
BACKUP:    15 trades (passive), healthy status
```

---

## Checkpoint Schedule

### 🔴 CRITICAL MILESTONE: 20:00-21:00 UTC (+1-2 hours)

**What to check:**
- [ ] Entry frequency: 3-4 new trades? (if <1/hr, strategy not working)
- [ ] Win rate early trend: >40%? (if <35%, entry logic broken)
- [ ] Circuit breaker: Staying CLOSED? (healthy operation)
- [ ] WebSocket: 3/3 streams connected?

**Decision:**
- ✅ **Continue** if entries occurring at 3-4/hour
- ❌ **Halt** if entries <1/hour or CB opened

---

### 🟡 PROGRESS CHECK: 22:00-23:00 UTC (+2-3 hours)

**What to check:**
- [ ] Trades so far: 6-12 trades? (pace for 72-96 in 24h)
- [ ] Win rate trend: 38-48%? (on track for 45-55% final)
- [ ] Daily P&L: Positive or negative? (direction matters)
- [ ] Slippage reasonable: <0.5%? (no dead market trades)

**Interpretation:**
- ✅ **Good pace** if 6-12 trades with 40%+ WR
- ⚠️ **Slower** if 3-6 trades (but still viable)
- ❌ **Problem** if <3 trades or negative WR

---

### 🟡 MIDPOINT CHECK: 02:53 UTC next day (+6 hours)

**What to check:**
- [ ] Total trades: 18-24? (pace check)
- [ ] Win rate: 42-52%? (should be converging)
- [ ] Cumulative P&L: +$0.50+? (positive sign)
- [ ] Largest win: >2% or close to target?
- [ ] Largest loss: ~0.5% (stop loss working)?

**If something looks wrong:**
- Win rate drifting <40%? → Note it, continue monitoring
- P&L negative? → Still within normal variation for 6h
- Trades too slow? → May fail to hit 45%+ statistical confidence

---

### 🟡 HALFWAY CHECK: 08:53 UTC (+12 hours)

**What to check:**
- [ ] Total trades: 36-48?
- [ ] Win rate: 43-53%? (converging on final estimate)
- [ ] Daily P&L so far: +$0.75+?
- [ ] Largest drawdown: <5% of balance?

**Decision point:**
- ✅ **Strong signal** if WR 48%+, P&L +$1+
- ⚠️ **Marginal** if WR 43-48%, P&L +$0.50-$1
- ❌ **Failing** if WR <43% or negative P&L

---

### 🟢 FINAL DECISION: 14:53 UTC (+24 hours)

**PASS Criteria (✅):**
```
Win Rate: ≥45%
Total Trades: ≥60 (statistical significance)
Daily P&L: Positive ($1+)
Largest Loss: Not exceeding circuit breaker
```

**MARGINAL Criteria (⚠️):**
```
Win Rate: 40-45%
Daily P&L: $0.50 to $1.00
Decision: Continue with strict monitoring
```

**FAIL Criteria (❌):**
```
Win Rate: <40%
Daily P&L: Negative
Decision: Halt, strategy needs redesign
```

---

## What Success Looks Like

**At 24 hours, a PASS looks like:**

```
PRIMARY (24 hours):
  Baseline: 249 trades
  Final: 321-345 trades (72-96 new)
  Win Rate: 45-55%
  Daily Trades: +72-96
  P&L: +$1.40 to +$2.60
  
Result: ✅ VALIDATION PASSED
Next: Approve for live trading on Monday
```

---

## What Failure Looks Like

**At 24 hours, a FAIL looks like:**

```
PRIMARY (24 hours):
  Baseline: 249 trades
  Final: 250-260 trades (1-11 new)
  Win Rate: <35%
  Daily Trades: +1-11 (filters too strict)
  P&L: -$0.10 to -$5.00
  
Result: ❌ VALIDATION FAILED
Next: Stop trading, diagnose entry logic
```

---

## Monitoring Commands

**Check PRIMARY trades count:**
```bash
curl -s http://localhost:8001/api/health | jq '.account.trades_today'
```

**Check PRIMARY P&L:**
```bash
curl -s http://localhost:8001/api/health | jq '.account.daily_pnl'
```

**View recent trades (if available via API):**
```bash
curl -s http://localhost:8001/api/trades | head -20
```

**Watch logs in real-time:**
```bash
tail -f /tmp/primary.log | grep -i "signal\|entry\|win\|loss"
```

---

## Key Rules for This Validation

1. **Do NOT change strategy mid-run**
   - No adjusting entry thresholds
   - No disabling symbols
   - Let the 24 hours complete

2. **Do NOT stop if hourly P&L is negative**
   - Variance is normal over short periods
   - Only the 24h total matters

3. **Do HALT if circuit breaker opens repeatedly**
   - Indicates system is failing
   - Manual investigation required

4. **Do RECORD trade details**
   - What was the entry price?
   - What was the exit price/reason?
   - These will inform improvements

---

## Post-Validation Actions

**If PASS (45%+ win rate):**
```
Day 1: Announce successful validation
Day 2: Prep live trading environment
Day 3: Go live with €1,000 (Monday)
```

**If MARGINAL (40-45% win rate):**
```
Action: Continue running 24 more hours
Monitor: Very closely for any degradation
Decision: At 48-hour mark if still 40-45%+
```

**If FAIL (<40% win rate):**
```
Action: Halt immediately when apparent
Analyze: Entry logic, MACD filtering, slippage issues
Redesign: Gather data from failed run
Next: Test revised strategy
```

---

## Summary

✅ Both machines healthy  
✅ Code is fixed and realistic  
✅ Math is correct (45% = profitable)  
✅ Checkpoints are clear  
✅ Success criteria are defined  

**24-hour validation is now live. The honest target is 45-55% win rate. Let the data speak.**
