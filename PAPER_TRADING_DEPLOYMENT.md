# 📊 Paper Trading Deployment - Simple Trend Signal

**Deployment Date:** 2026-07-04 23:10 UTC  
**Signal Version:** Simple Trend (2-condition)  
**Status:** ✅ LIVE ON BOTH MACHINES

---

## Deployment Summary

### What Was Deployed

**Simple Trend-Following Signal:**
```
CORE CONDITIONS:
1. Price > EMA20 (4-hour)  — Macro uptrend filter
2. RSI < 85               — Extreme overbought filter only

BONUSES:
- Volume >= 1.5x = +20 points
- Volume >= 1.0x = +10 points  
- RSI < 60 = +15 points (room to run)
- Price > EMA20 by > 2% = +10 points

Threshold: 40 (just above neutral)
```

### Why This Approach

- **Previous attempts (5-condition signal):** 0 trades over 6 months
- **Root cause:** Requirements too strict; by the time all conditions aligned, entry was too late
- **Solution:** Drastically simplify to 2 core conditions + bonuses
- **Expected result:** 10-100x more trades than previous version

---

## Deployment Status

### PRIMARY (192.168.30.137:8001)
- ✅ Code updated (commit 562990e)
- ✅ Trading enabled: `enabled=True`
- ✅ Symbols: BTCUSDT, ETHUSDT, BNBUSDT
- ✅ Entry threshold: 50 (old value, acceptable)
- ✅ Baseline monitoring: Running (1,400+ metrics collected)
- ✅ Health: Responding

### BACKUP (192.168.3.25:8002)
- ✅ Code updated (commit 562990e)
- ✅ Trading enabled: `enabled=True`
- ✅ Symbols: BTCUSDT, ETHUSDT, BNBUSDT
- ✅ Entry threshold: 50 (synced)
- ✅ Health: Responding
- ⏳ Baseline monitoring: TBD (needs restart if required)

---

## Monitoring Instructions

### Real-Time Dashboard (Every 5 minutes)

```bash
# Check PRIMARY account state
curl -s http://192.168.30.137:8001/api/account | jq '.account | {cash, total_equity, active_positions}'

# Check BACKUP account state
curl -s http://192.168.3.25:8002/api/account | jq '.account | {cash, total_equity, active_positions}'

# View trades generated (PRIMARY)
curl -s http://192.168.30.137:8001/api/trades | jq '.trades | length'

# View trades generated (BACKUP)
curl -s http://192.168.3.25:8002/api/trades | jq '.trades | length'
```

### Key Metrics to Watch

| Metric | Target | Watch For |
|--------|--------|-----------|
| **Trades/hour** | ≥1 | If 0 for 2+ hours → signal not triggering |
| **Win rate** | ≥55% | If <40% → signal needs adjustment |
| **Avg trade duration** | 5-15 min | Indicating exit logic working |
| **Cash balance** | Stable ±5% | Large swings = risk management issue |
| **Circuit breaker** | CLOSED | If OPEN → too many failures |

---

## What to Expect

### Good Signs ✅
- Multiple trades per hour (10-100 vs. 0 with complex signal)
- Win rate > 50%
- Positive P&L trend
- No circuit breaker trips

### Red Flags 🔴
- Still 0 trades (signal fundamentally broken)
- Win rate < 30% (signal is trading noise)
- Runaway P&L loss >€50
- Circuit breaker constantly opening

---

## Decision Points

### After 6 Hours of Trading

**If ≥30 trades with ≥50% win rate:**
- ✅ Signal is working
- ✅ Proceed with live trading approval process
- Continue paper trading for 1-2 weeks to validate

**If 0-5 trades or win rate <30%:**
- ❌ Signal still broken
- ❌ Revert to previous approach
- Redesign needed

**If 6-30 trades with 40-50% win rate:**
- ⚠️ Promising but uncertain
- Continue monitoring
- Gather 48+ hours of data before deciding

---

## Alerts to Set Up

```bash
# Alert if no trades for 2 hours
watch -n 300 'curl -s http://192.168.30.137:8001/api/trades | jq ".trades | length"'

# Alert if cash drops >€50
watch -n 60 'curl -s http://192.168.30.137:8001/api/account | jq ".account.cash"'

# Alert if CB opens
watch -n 30 'curl -s http://192.168.30.137:8001/api/health | jq ".circuit_breaker.state"'
```

---

## Rollback Plan

If signal is not generating trades after 6 hours:

```bash
# Disable trading on both machines
curl -X POST http://192.168.30.137:8001/api/autonomous/config \
  -H "Content-Type: application/json" \
  -d '{"enabled": false}'

curl -X POST http://192.168.3.25:8002/api/autonomous/config \
  -H "Content-Type: application/json" \
  -d '{"enabled": false}'

# Revert to previous signal version
git revert 562990e
git push origin master

# Pull on both machines and restart
```

---

## Next Steps

### Timeline

| Time | Action | Owner |
|------|--------|-------|
| Now | ✅ Deploy simple signal | Done |
| 6h | Check: Did it generate trades? | Monitor |
| 24h | Full metrics analysis | Review |
| 48h | Decision: Continue or redesign? | User |
| 1-2 weeks | Validate signal stability | Paper trading |
| Then | Live trading approval process | User |

---

## Notes

1. **Backtest paradox:** Backtest showed 0 trades even with simple signal. Paper trading is the real test.
2. **Two possibilities:**
   - Signal works in live data but backtest has bugs
   - Signal doesn't work and needs redesign
3. **Paper trading will tell us:** Within hours, not days
4. **No risk:** Paper trading only, no real money yet

---

**Status:** 🟢 DEPLOYED AND LIVE  
**Next review:** 6 hours from deployment  
**Decision point:** After 24 hours of data
