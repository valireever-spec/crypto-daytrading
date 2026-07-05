# Mean-Reversion Strategy Monitoring — 2026-07-05

**Status:** 🟢 TRADING RESUMED with Mean-Reversion  
**Start Time:** 14:43:51 UTC  
**Target Win Rate:** ≥55%  
**Validation Duration:** 24-48 hours  

---

## Checkpoint Tracking

### Baseline (Before Trading Resume)
- **Time:** 14:43:51 UTC
- **Trades Today:** 247 (from momentum, not counting in validation)
- **Daily P&L:** -€5.20 (from momentum)
- **Strategy:** Switching from Momentum → Mean-Reversion
- **Trading Reset:** Tracking NEW trades under mean-reversion only

---

## Checkpoint Template

```
## Checkpoint: HH:MM UTC (MM min elapsed)

### Trading Activity
- New trades: X (since last check)
- Win rate: Y% (completed trades)
- Daily P&L (mean-reversion): €Z
- Largest win: €A
- Largest loss: €B
- Avg trade: €C

### Signal Quality
- Entry signals: X generated
- Entry signals fired: Y (ratio %)
- Avg signal strength: Z%
- Entry reasons: List top 3

### System Health
- PRIMARY: healthy/degraded/unhealthy
- BACKUP: healthy/degraded/unhealthy
- HA sync: 200 OK last Xs ago
- Memory: XYZB MB
- Errors: X in last 50 lines

### Key Metrics
✅ ≥20 trades generated → tracking progress
✅ Win rate approaching 55% → positive trend
⚠️ Win rate 45-55% → marginal, needs adjustment
❌ Win rate <45% → strategy not working

### Notes
- First entries should fire when RSI < 30 (need market volatility)
- Exits should fire at RSI > 70 or 2% profit or 1% stop loss
- If no entries in first 30 min, check RSI values
```

---

## Validation Criteria (Pass/Fail)

### ✅ PASS (Resume Live Trading)
- Win rate ≥ 55% after 24-48h
- 20+ completed trades
- No more than 3 consecutive losses
- Daily loss stays < -€20

### ⚠️ MARGINAL (Adjust & Re-test)
- Win rate 45-55%
- Increase entry threshold or adjust RSI levels
- Run another 24h validation

### ❌ FAIL (Strategy Redesign)
- Win rate < 45%
- Mean-reversion doesn't work in current market
- Try grid trading or hybrid approach

---

## Monitoring Commands

```bash
# Quick health check
curl -s http://127.0.0.1:8001/api/health | jq '.account | {trades_today, daily_pnl, cash}'

# Check for errors
tail -50 logs/api.log | grep -iE "ERROR|CRITICAL|HALT"

# Watch for entry signals
tail -f logs/api.log | grep -i "Mean Reversion\|oversold"

# Watch for exits
tail -f logs/api.log | grep -iE "overbought|EXIT|PROFIT|STOP"

# Check RSI values
tail -100 logs/api.log | grep -i "RSI"
```

---

## What to Watch For

1. **First Entry** — When does RSI hit <30? How long until first trade?
2. **Entry Quality** — Do entries look correct? (Price > SMA20 + RSI < 30?)
3. **Exit Quality** — Are exits happening at RSI > 70 or profit targets?
4. **Win Rate Trend** — Is it improving toward 55%?
5. **System Stability** — Any crashes, sync issues, memory spikes?

---

## Success Indicators

✅ **Good signs:**
- Entries firing when RSI < 30
- Exits firing at RSI > 70
- Win rate trending toward 50%+
- System stays stable

❌ **Warning signs:**
- No entries in 30+ min (RSI not hitting <30)
- All entries losing (bad signal)
- System errors/halts
- Memory spikes

---

## Timeline

- **T+0 (14:43 UTC):** Trading resumed, monitoring begins
- **T+15min (14:58 UTC):** First checkpoint
- **T+30min (15:13 UTC):** Second checkpoint
- **T+4h (18:43 UTC):** Overnight checkpoint
- **T+24h (14:43 next day):** Day 1 decision point
- **T+48h (14:43 two days later):** Final validation decision

---

## Decision Points

**After 24 hours (15:43 UTC tomorrow):**
- ✅ If WR ≥ 55% → Resume live trading immediately
- ⚠️ If WR 45-55% → Run another 24h with adjusted params
- ❌ If WR < 45% → Pause and redesign

**After 48 hours (15:43 UTC in 2 days):**
- ✅ If sustained ≥ 55% → APPROVED for live trading with €931.25
- ❌ If still < 55% → DENIED, try alternative strategy

---

