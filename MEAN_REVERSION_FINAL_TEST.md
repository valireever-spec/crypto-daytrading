# Mean-Reversion Strategy Validation — 2026-07-05

**Status:** 🟢 LIVE  
**Start Time:** 17:20 UTC  
**Duration:** 24-48 hours  
**Success Criteria:** Win rate ≥55% (from backtesting)  

## Strategy
Mean-reversion: Buy when RSI < 30 (oversold), Sell when RSI > 70 (overbought) or hit profit target.

### Configuration
- Entry threshold: 55 (from system_config.json)
- Quality gate: 75% data quality required
- Exit profit target: 2.0%
- Exit stop loss: 1.0%
- Risk ratio: 2:1 (2% profit vs 1% loss)

## Validation Plan

### Checkpoint Template (Check every 4-6 hours)
```
## Checkpoint: HH:MM UTC

### Trades
- New trades: X
- Win rate: Y% (cumulative)
- Daily P&L: €Z
- Largest win: €A
- Largest loss: €B

### Signal Quality  
- Entry signals: X per hour
- Entry signals fired: Y (ratio %)
- Avg signal strength: Z%

### System Health
- PRIMARY: healthy
- BACKUP: healthy
- HA sync: OK
- Memory: <5%
- CPU: <10%

### Decision
- ✅ Trending toward success (WR >50%)
- ⚠️ Marginal (WR 40-50%)
- ❌ Failing (WR <40%)
```

## Key Metrics to Track
1. **Win rate** — Must reach ≥55% by end of 48 hours
2. **Trade count** — Need 50+ completed trades for stat significance
3. **Drawdown** — Daily loss must stay within €50 (5% of capital)
4. **Signal frequency** — Mean-reversion usually triggers on RSI extremes (1-5/hour)

## Timeline
- **T+0 (17:20 UTC):** Mean-reversion enabled
- **T+6h (23:20 UTC):** First checkpoint
- **T+24h (17:20 next day):** Day 1 decision
  - ✅ If WR ≥55% → APPROVED for live trading
  - ⚠️ If WR 45-55% → Continue monitoring
  - ❌ If WR <45% → Redesign/abort
- **T+48h:** Final validation (if needed)

## Success Indicators
✅ Entries firing when RSI < 30  
✅ Exits firing at RSI > 70 or profit targets  
✅ Win rate trending toward 50%+  
✅ System stays stable (no crashes/restarts)  

---
**Hypothesis:** Mean-reversion is better suited for crypto volatility than momentum.
**Expected outcome:** 55% win rate, ~€50 daily profit on €1,000 capital.
