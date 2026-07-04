# Momentum Strategy Performance Monitor

**Deployment:** 2026-07-04 23:28:00 UTC  
**Strategy:** EMA12/EMA26 + RSI > 50 (momentum-based entry)  
**Target Win Rate:** > 50% (proven from investing-platform)

---

## Real-Time Performance Tracking

### Status: MONITORING IN PROGRESS ⏳

| Time (UTC) | New Trades | Wins | Losses | Win Rate | Total P&L | Notes |
|----------|-----------|------|--------|----------|-----------|-------|
| 23:28 | Deployment | - | - | - | - | Momentum strategy live on both machines |
| 23:32 | 0 | 0 | 0 | - | €0.00 | Waiting for uptrend + momentum conditions |

---

## Entry Signal Requirements
For a trade to trigger, ALL must be true:
1. ✅ Price > EMA12 (fast MA)
2. ✅ Price > EMA26 (slow MA)
3. ✅ EMA12 > EMA26 (uptrend)
4. ✅ RSI > 50 (momentum, not oversold)

Current status: Market conditions not yet aligned (likely downtrend or low momentum RSI)

---

## Key Metrics to Monitor

| Metric | Target | Status |
|--------|--------|--------|
| **Win Rate** | > 50% | Pending first trades |
| **Avg Trade Duration** | 5-15 min | Pending first trades |
| **Avg P&L per Trade** | > €0.10 | Pending first trades |
| **Total Daily P&L** | > €0 | €0.00 (pre-momentum) |
| **Max Drawdown** | < 5% | Pending assessment |

---

## What Success Looks Like

✅ **Good Signal:** 
- Trades generated when uptrend + momentum align
- Win rate > 50% (better than random)
- Avg P&L > €0.10 per trade
- No consecutive losses > 3

❌ **Red Flags:**
- Win rate < 30% (signal is worse than useless)
- Avg trade lasts < 2 minutes (exit firing too early)
- Max consecutive losses > 5 (signal is catching noise)
- Total P&L < -€10 after 100+ trades

---

## Decision Framework (After 48 Hours)

### IF Win Rate > 50% + Positive P&L
✅ **Signal is working** → Monitor for 1-2 more weeks, consider live trading approval

### IF Win Rate 30-50% + Breakeven
⚠️ **Signal is marginal** → Continue monitoring, may need parameter tuning

### IF Win Rate < 30% + Losses
❌ **Signal is broken** → Revert to exploring other strategies

---

## Notes

- Momentum strategy chosen because: proven on stocks (52% WR), simple rules, avoids false bottoms
- Current market may not have uptrend/momentum right now (normal, signal is being selective)
- First trades will appear when BTC/ETH/BNB develop strong uptrend with positive momentum
- Will update this log as trades generate

**Live Until:** 2026-07-05 23:28:00 UTC (48-hour validation window)

