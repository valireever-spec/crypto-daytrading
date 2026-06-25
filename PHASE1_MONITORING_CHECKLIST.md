# Phase 1 Daily Monitoring Checklist

**Duration:** 2026-06-25 to 2026-07-05 (10 days)  
**Frequency:** Once daily (morning recommended)  
**Time:** ~5 minutes per day  
**Success Gate:** >55% win rate + positive P&L + zero crashes

---

## Daily Check (5 minutes)

### 1. SYSTEM HEALTH ✅
```bash
# Run this first thing every morning
bash scripts/monitor-phase1.sh
```

**What to look for:**
- ✅ `running: true` (trader still active)
- ✅ `enabled: true` (not paused)
- ❌ `No crashes detected` (check logs if false)
- ✅ `Daily P&L: €0.00 to €500.00` (winning range)
- ❌ If P&L < -€500: CRITICAL - daily loss limit hit

**Red flags:**
- Running: false → Trader crashed, needs restart
- P&L < -€500 → Hit daily loss limit, trading paused
- Same error 3+ times → Systematic problem

---

### 2. TRADING ACTIVITY
```bash
# Check: Are trades happening?
grep TRADE_EXECUTED logs/api_server.log | tail -5 | jq '{timestamp, symbol, side, price}'

# Check: Any exits yet?
grep TRADE_EXIT logs/api_server.log | tail -5 | jq '{symbol, pnl_pct, exit_reason}'
```

**Track daily:**
| Date | Entries | Exits | Win Rate | Daily P&L |
|------|---------|-------|----------|-----------|
| 2026-06-25 | 3 | 0 | — | €0.00 |
| 2026-06-26 | ? | ? | ? | ? |

**Expected trajectory:**
- Days 1-3: 2-5 entries/day, 0-2 exits (positions accumulate)
- Days 4-7: 3-7 entries/day, 2-5 exits/day (positions cycling)
- Days 8-10: 3-5 entries/day, 3-7 exits/day (full cycle)

**Red flags:**
- 0 entries for 2+ hours → Signal generation broken
- Entries but 0 exits for 3+ days → No profit targets hit (bad signal quality)
- Win rate drops below 40% → Strategy may be broken

---

### 3. SIGNAL QUALITY

```bash
# How many signals generated?
grep SIGNAL_DECISION logs/api_server.log | wc -l

# What's the average signal score?
grep SIGNAL_DECISION logs/api_server.log | jq '.signal_score' | \
  awk '{sum+=$1; count++} END {print "Avg: " sum/count}'

# Are signals actually being converted to trades?
SIGNALS=$(grep -c SIGNAL_DECISION logs/api_server.log)
TRADES=$(grep -c TRADE_EXECUTED logs/api_server.log)
echo "Signal→Trade conversion: $TRADES / $SIGNALS"
```

**Expected numbers:**
- Signals: 20-50/day (roughly 1 per symbol per hour)
- Avg score: 60-75 (around threshold)
- Conversion: 10-30% (not all signals result in trades due to position limits)

**Red flags:**
- Avg score = 59.0 (just below threshold, signals weak)
- 0 signals for 1+ hour → Binance connection issue
- Conversion = 0% → Orders failing silently

---

### 4. ERRORS & ANOMALIES

```bash
# Check for order failures
grep ORDER_FAILED logs/api_server.log | jq '{symbol, error_message}' | tail -5

# Check for exit failures
grep EXIT_FAILED logs/api_server.log | jq '{symbol, error_message}' | tail -5

# Check for crashes
grep -i "exception\|error\|failed" logs/api_server.log | grep -v "ORDER_FAILED\|EXIT_FAILED" | tail -5
```

**Acceptable:**
- 0 order failures → ✅ Perfect
- 0 exit failures → ✅ Perfect
- 0 crashes → ✅ Perfect

**Concerning (investigate):**
- 1-2 order failures → Unusual price movement? Insufficient balance?
- 1-2 exit failures → Target price never reached? Slippage?
- 1+ crashes → What caused it? Memory issue? Binance connection?

**Critical (stop and debug):**
- 3+ of same error → Systematic bug
- Crash and restart → Data loss risk

---

### 5. CONFIG VERIFICATION

```bash
# Verify actual config being used
curl -s http://localhost:8001/api/autonomous/config | jq .

# Should match:
# - entry_threshold: 60.0
# - exit_profit_target: 0.03
# - exit_stop_loss: 0.02
# - max_positions: 5
# - symbols: ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
# - enabled: true
```

**Red flags:**
- entry_threshold: 55.0 (changed? should be 60.0)
- max_positions: 10 (changed? should be 5)
- symbols: empty (CRITICAL - config corrupt)
- enabled: false (trader paused)

---

## Weekly Check (Day 5 & 10)

### WEEK 1 (Day 5): Mid-Phase Checkpoint

**Questions to answer:**
1. Win rate emerging? (Target: >50%)
   ```bash
   grep TRADE_EXIT logs/api_server.log | \
     jq '[.[] | select(.pnl_pct > 0)] | length as $wins | 
           length as $total | "\($wins) / \($total) = \($wins * 100 / $total)%"'
   ```

2. Any signal anomalies?
   - BTCUSDT signals: How many? What scores?
   - ETHUSDT signals: How many? What scores?
   - BNBUSDT signals: How many? What scores?

3. Regime changing?
   ```bash
   grep SIGNAL_DECISION logs/api_server.log | jq '.regime' | sort | uniq -c
   ```
   Expected: Mix of "unknown", "bull", "bear", etc.

4. Slippage measured?
   ```bash
   # Compare entry price in logs vs signal price
   grep SIGNAL_DECISION logs/api_server.log | jq '.symbol, .timestamp' | head -1
   # Find corresponding TRADE_EXECUTED
   # Calculate: (fill_price - signal_price) / signal_price
   ```
   Expected: ~0.1% slippage (or log actual)

**Action if issues found:**
- Win rate <40% → Review signal quality, check if regime detection is broken
- Specific symbol losing: Review that symbol's signals
- Regime stuck at "unknown" → Volatility data issue?
- Slippage >0.5% → Normal for crypto, adjust expectations

---

### WEEK 2 (Day 10+): Final Evaluation

**Go/No-Go Decision:**

**GO to Phase 2 if ALL of these are met:**
- ✅ Win rate ≥ 55%
- ✅ Cumulative P&L > €0 (preferably >€100)
- ✅ Minimum 50 trades completed (statistical validity)
- ✅ 0 crashes
- ✅ 0 repeated errors (same error 1-2x is fine, 3+ is bad)
- ✅ All trades logged completely

**Note:** If <50 trades in 10 days, extend Phase 1 until 50 trades reached.

**NO-GO if ANY of these are true:**
- ❌ Win rate < 45%
- ❌ P&L < -€200
- ❌ 2+ crashes
- ❌ Systematic errors (same failure 5+ times)
- ❌ Missing logs (can't trace decisions)
- ❌ <50 trades completed

**If NO-GO, debug priorities:**
1. Check signal quality (are thresholds right?)
2. Check regime detection (is it stuck?)
3. Check slippage (is it worse than assumed?)
4. Check position sizing (too aggressive?)

---

## What NOT to Worry About

❌ **Don't obsess over:**
- Single trade loss (-2% is normal with stop loss)
- Temporary regime change (market is dynamic)
- Minor slippage variance (0.1-0.2% is normal)
- Win rate on Days 1-3 (too few trades to judge)

✅ **Only escalate if:**
- Pattern of losses (3+ consecutive losses)
- Same error repeating (3+ times)
- System crashes (data loss risk)
- Configuration changes unexpectedly

---

## Hour-by-Hour During Trading Hours (Optional Deep Dives)

If you want to monitor more closely during trading hours (best for crypto: 13:00-21:00 UTC when Europe & US overlap):

```bash
# Every hour, check:
tail -100 logs/api_server.log | grep SIGNAL_DECISION | tail -5
tail -100 logs/api_server.log | grep TRADE_EXECUTED | tail -5
tail -100 logs/api_server.log | grep ORDER_FAILED | tail -5

# Look for:
# - Signals still generating? (should see 5-10 per hour)
# - Trades executing? (should see 1-3 per hour)
# - Any failures? (should be 0)
```

---

## Metrics to Track (Spreadsheet Template)

Keep a simple tracking sheet:

```
Date       | Entries | Exits | Wins | Losses | Daily P&L | Crashes | Notes
-----------|---------|-------|------|--------|-----------|---------|-------
2026-06-25 | 3       | 0     | —    | —      | €0.00     | 0       | Initial
2026-06-26 | 5       | 2     | 1    | 1      | €45.00    | 0       | Good day
2026-06-27 | 4       | 3     | 2    | 1      | €120.00   | 0       | Strong
2026-06-28 | 6       | 4     | 2    | 2      | €95.00    | 0       | Volatile
2026-06-29 | 5       | 5     | 3    | 2      | €180.00   | 0       | ✅ Day 5 checkpoint
...        | ...     | ...   | ...  | ...    | ...       | ...     | ...
2026-07-05 | 5       | 6     | 4    | 2      | €215.00   | 0       | ✅ Final evaluation
```

---

## Red Flags Checklist

If you see ANY of these, investigate immediately:

- [ ] `running: false` → Crash, restart trader
- [ ] `enabled: false` → Check why trading paused
- [ ] Daily P&L < -€500 → Paused (expected if loss limit hit)
- [ ] Same error 3+ times → Systematic bug
- [ ] 0 signals for 1+ hour → Binance connection down
- [ ] 0 exits for 3+ days → No positions closing (bad signal quality)
- [ ] Win rate 30% or dropping → Strategy broken
- [ ] Timestamps inconsistent → Data corruption
- [ ] Config changed unexpectedly → Someone modified settings
- [ ] Log file missing → Data loss risk

---

## Daily Action Items

### Morning (First thing)
1. Run `bash scripts/monitor-phase1.sh`
2. Check for crashes in logs
3. Verify config is correct

### If Issues Found
1. Note the error in your tracking sheet
2. If critical (crash, config corruption): Restart trader
3. If pattern (same error 3x): Add to "bugs to fix after Phase 1"

### Evening (Before bed)
1. Quick check: No crashes? Win rate still >50%?
2. Sleep easy if: ✅ Running, ✅ Logging, ✅ No errors

---

## Example: What Good Looks Like (Day 3)

```bash
$ bash scripts/monitor-phase1.sh

Report Date: 2026-06-27 08:15:00

1. TRADER STATUS
   Running: true ✅
   Enabled: true ✅
   Total Trades: 7
   Active Positions: 2
   Daily P&L: €120.00 ✅
   Daily P&L %: 1.2% ✅

2. TRADE EXECUTION SUMMARY
   Entries Executed: 7
   Exits Completed: 5
   Failed Orders: 0 ✅
   Failed Exits: 0 ✅

3. WIN RATE ANALYSIS
   Winning Exits: 3 / 5
   Win Rate: 60% ✅

4. ERROR MONITORING
   ✅ No order or exit failures

5. PROFITABILITY TRACKING
   Daily P&L: €120.00
   Daily P&L %: 1.2%
   Status: ✅ Safe zone

6. PHASE 1 SUCCESS CRITERIA
   ✅ Trader Running: true
   ✅ Trader Enabled: true
   ✅ No Crashes: Yes
   ✅ Trades Logged: 7 entries executed
   📊 Win Rate: 60% ✅

PHASE 1 PROGRESS: Day 3 / 10
```

**Analysis:** Perfect! Keep going.

---

## Example: What Trouble Looks Like (Day 3)

```bash
$ bash scripts/monitor-phase1.sh

Report Date: 2026-06-27 08:15:00

1. TRADER STATUS
   Running: true ✅
   Enabled: false ❌ ← TRADER PAUSED!
   Total Trades: 3
   Active Positions: 0
   Daily P&L: -€520.00 ❌ ← Hit daily loss limit
   Daily P&L %: -5.2%

3. WIN RATE ANALYSIS
   Winning Exits: 1 / 3
   Win Rate: 33% ❌ ← Much worse than target 55%

5. PROFITABILITY TRACKING
   Daily P&L: -€520.00
   Status: ⚠️ Hit daily loss limit - trading paused

PHASE 1 PROGRESS: Day 3 / 10
```

**Action:** 
1. Check logs: Why is win rate only 33%?
2. Review signals: Are they valid?
3. Check config: Are entry threshold, position size correct?
4. Possible causes:
   - Signals weak (average score = 59, just below threshold)
   - Slippage worse than expected (0.5% vs 0.1%)
   - Regime detector broken (all "unknown")
   - Position sizing too aggressive (2x too large)

---

## Phase 2 Abort Criteria (If You Proceed to Live Trading)

**If Phase 1 succeeds and you go live with €1,000, STOP trading immediately if:**

| Event | Threshold | Action |
|-------|-----------|--------|
| **Cumulative Loss** | > €100 (10%) | ⛔ STOP. Debug root cause. |
| **Consecutive Losing Days** | 3 days in a row | ⛔ STOP. Review signals. |
| **API Crashes** | 2+ crashes | ⛔ STOP. Fix state persistence. |
| **Daily Loss Limit Hit** | €500 loss in 1 day | ⏸️ PAUSE (trading already disabled). |

**When to Resume After Abort:**
1. Identify root cause (slippage? regime change? algorithm bug?)
2. Fix the issue
3. Run 3-day paper test with fix
4. Only resume live if paper test validates >55% win rate

**€100 is the Point of No Return**
- After 10 days of >55% win rate in paper
- If live trading loses €100, that suggests:
  - Slippage is much worse than 0.1% (paper assumes)
  - Market conditions changed
  - Algorithm doesn't work in live conditions
- Better to pause and investigate than lose €500+

---

## Summary: The Simple Version

**Every morning, ask yourself:**

1. Is the trader running? (`running: true`)
2. Is it still enabled? (`enabled: true`)
3. Did it crash? (Check logs for exceptions)
4. What's today's P&L? (Should be positive or tiny loss)
5. What's the win rate so far? (Should be trending >50%)

**If all yes → keep going.**

**If any no → investigate.**

That's it. 5 minutes per day, 10 days total. Then decide Phase 2.

---

**Good luck! 🚀**
