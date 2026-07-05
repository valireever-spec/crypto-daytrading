# Mean-Reversion Strategy Validation Plan

**Status:** ⏸️ Ready for testing (trading paused)  
**Strategy:** Mean-reversion (RSI-based)  
**Expected Win Rate:** 55%+  
**Current Momentum Win Rate:** 0% (116 trades)

---

## Strategy Overview

### Entry Signal (RSI < 30 Oversold)
```
Condition: RSI < 30 AND Price > SMA20
Signal Strength: 50-100 based on RSI depth
Example: RSI 15 = 75 strength, RSI 30 = 50 strength
Reason: "Mean Reversion Oversold: RSI 15 < 30, Price $62,000 > SMA20 $61,900"
```

### Exit Signals
```
1. RSI > 70 (Overbought) ← PRIMARY exit (mean-reversion core)
2. +2.0% Profit Target ← Secondary exit
3. -1.0% Stop Loss ← Risk control
4. 10-min Timeout ← Prevent holding losers
```

### Configuration
```json
{
  "strategy": "mean_reversion",
  "entry_threshold": 50,
  "exit_profit_target": 2.0,
  "exit_stop_loss": 1.0,
  "enabled": false (currently paused)
}
```

---

## Validation Phases

### Phase 1: Backtest Historical Data (OPTIONAL)
**Goal:** Verify strategy performance on real crypto data  
**Duration:** 1-2 hours  
**Data:** 30+ days BTCUSDT, ETHUSDT, BNBUSDT 1-min candles  
**Pass Criteria:** Win rate ≥ 55%  

**Status:** Skipped (simulated data doesn't capture RSI extremes)  
**Reason:** Real market testing more valuable than simulated tests

---

### Phase 2: Paper Trading Validation (REQUIRED)
**Goal:** Validate on LIVE market conditions before resuming  
**Duration:** 24-48 hours  
**Markets:** BTCUSDT, ETHUSDT, BNBUSDT  
**Capital:** €931.25 (paper trading, no real money)

**Pass Criteria:**
- ✅ Win rate ≥ 55% (vs 0% from momentum)
- ✅ At least 20 completed trades
- ✅ No more than 3 consecutive losses
- ✅ No catastrophic drop (< -€20 daily)

**Monitoring:**
- Real-time alerts on every entry/exit
- 15-min health checks
- Daily P&L tracking

**Decision Framework:**
- ✅ **PASS** → Resume live trading with €931.25
- ⚠️ **MARGINAL** (45-55% WR) → Adjust threshold & re-test
- ❌ **FAIL** (<45% WR) → Back to drawing board

---

### Phase 3: Live Trading (IF VALIDATED)
**Start Capital:** €931.25  
**Duration:** 2+ weeks  
**Goal:** Validate profitability with real money  

**Pass Criteria for Scaling:**
- ✅ Win rate ≥ 55%
- ✅ Daily P&L consistently positive (avg +€1-€2/day)
- ✅ No daily loss > -€25
- ✅ 14+ days without critical failure

**If Pass:** Scale to €1,000 capital  
**If Fail:** Revert to paper trading, adjust parameters

---

## Deployment Steps

### To Resume Trading

1. **Enable Strategy**
   ```bash
   # Edit trading_config.json
   "enabled": true
   ```

2. **Deploy to Both Machines**
   ```bash
   # PRIMARY
   cp trading_config.json ...
   
   # BACKUP
   scp -i ~/.ssh/crypto_sync trading_config.json \
     openhabian@192.168.3.25:/home/claude/crypto-daytrading/
   ```

3. **Restart Trading**
   ```bash
   # Hot-reload will pick up new config
   # Or manually restart if needed
   ```

4. **Monitor**
   - Watch first 5 trades for signal quality
   - Verify RSI calculations are correct
   - Check alert messages in Telegram

---

## Key Differences from Momentum

| Aspect | Momentum | Mean-Reversion |
|--------|----------|-----------------|
| Entry | SMA3 > SMA10 (uptrend) | RSI < 30 (oversold) |
| Exit | Time/SMA cross | RSI > 70 (overbought) |
| Market Type | Trending | Range-bound |
| Recent Performance | 0% WR (116 trades) | Unknown (testing) |
| Philosophy | Chase winners | Buy dips |

---

## Success Metrics

### Trade Quality
```
✅ Good: 
  - 55%+ win rate
  - Avg win > avg loss
  - Consistent entries
  
⚠️ Marginal:
  - 48-54% win rate
  - Needs parameter tuning
  
❌ Bad:
  - <48% win rate
  - Strategy doesn't work
```

### System Health
```
✅ All Healthy:
  - PRIMARY/BACKUP synced
  - Heartbeat active
  - Memory <400MB
  - 0 trading halts
  - 0 errors
  
❌ Issues:
  - HA failures
  - Memory spikes
  - Trading halts
  - Sync divergence
```

---

## Timeline

**Week of 2026-07-05:**
- Fri: Implement mean-reversion ✅ COMPLETE
- Sat: Paper trading validation (24h)
- Sun: Decision point (resume vs refactor)

**If Pass (Sun):**
- Mon: Live trading resumes with €931.25
- Tue-Fri: Monitor + collect data
- Next week: Scale if 14-day validation passes

**If Fail (Sun):**
- Mon: Analyze failure, identify issue
- Tue: Attempt fix #2
- Wed-Fri: Re-test mean-reversion or try alternative

---

## Rollback Plan

**If mean-reversion fails after resuming:**

1. Immediately pause: `"enabled": false`
2. Revert to momentum? NO - momentum has 0% WR
3. Try alternative strategy? YES - grid trading or hybrid
4. Stay paused? YES - don't risk capital on unvalidated strategies

---

## Next Steps

**Now:**
1. ✅ Strategy implemented
2. ✅ Code deployed to both machines
3. ⏭️ **READY FOR PHASE 2: Paper Trading**

**To Start Paper Trading:**
```json
{
  "enabled": true,
  "strategy": "mean_reversion"
}
```

Then monitor for 24-48 hours and decide whether to resume live trading.

---

## Questions to Monitor

1. **Are entries happening?** (RSI should hit <30 in range-bound crypto)
2. **Is win rate improving?** (Target: >55% vs 0% from momentum)
3. **Are exits working?** (RSI > 70 or profit/stop targets hit)
4. **Is system stable?** (HA sync, memory, errors all healthy)
5. **Is capital safe?** (Daily losses < €20, not hitting halt limit)

