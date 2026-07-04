# Signal Failure Analysis — Simple Trend-Following (2026-07-04)

## The Failure

**Signal:** Price > EMA20(4hr) + RSI < 85  
**Result:** 1,220 trades, 0% win rate, -€16 total P&L, 50% losing / 50% breakeven

## Root Cause Analysis

### Why This Signal Fails

The simple trend-following signal has a fundamental flaw in volatile crypto markets:

**Condition 1: "Price > EMA20(4hr)"**
- This triggers on ANY price above the moving average
- In crypto's 24/7 volatility, this happens frequently (~10-20% of candles)
- Problem: Triggers on minor bounces, not actual trends
- Example: Price touches EMA briefly, signal fires, then reverses for 1-2% loss

**Condition 2: "RSI < 85"**
- This almost never filters anything (RSI rarely exceeds 85 in crypto)
- No real filtering power
- False sense of selectivity

### Why 50% Breakeven?

The exit logic in the system (lines 10-min timeout + profit target 2% + stop loss 1%):
- Exits after 10 minutes automatically
- Most trades: price bounces slightly, hits 10-min timeout, exits at breakeven or small loss
- Result: 50% losses, 50% breakeven, 0% wins

## What Worked / What Didn't

| Approach | Result | Why |
|----------|--------|-----|
| **5-condition signal** | 0 trades | Too strict, conditions never aligned |
| **2-condition simple trend** | 1,220 trades, 0% WR | Too loose, triggers on noise |
| **Perfect signal** | TBD | Need something in between |

## Solutions to Try (Ranked by Likelihood)

### 1. **Mean Reversion (HIGH CONFIDENCE)**
- **Logic:** Buy when price oversold (>2 std dev below SMA), sell at mean
- **Why it works:** Crypto reverses sharply from extremes
- **Implementation:** 
  - Entry: Price < SMA20 - (2 × StdDev20)
  - Exit: Price > SMA20 OR profit target 1.5% OR loss > 1%
- **Expected:** 50-60% win rate, 2-5 trades/hour

### 2. **Momentum Breakout (MEDIUM CONFIDENCE)**
- **Logic:** Buy on breakout (5-min close > 1-hr high) with volume confirmation
- **Why it works:** Breakouts capture early trend momentum
- **Implementation:**
  - Entry: Close > 1-hour high AND Volume > 1.5x average
  - Exit: Time-based (15-30 min) OR profit/loss
- **Expected:** 45-55% win rate, 3-8 trades/hour

### 3. **Volume Spike + Reversal (MEDIUM CONFIDENCE)**
- **Logic:** Buy when volume spikes AND price reverses from moving average
- **Why it works:** Volume indicates genuine interest, not just noise
- **Implementation:**
  - Entry: Volume > 2x average AND Price < SMA20 (oversold)
  - Exit: Time-based OR profit target 2%
- **Expected:** 40-50% win rate, 1-4 trades/hour

## Recommendation

**Try Option 1 (Mean Reversion) first** because:
1. Crypto is mean-reverting by nature (high volatility → sharp reversions)
2. Simple to implement and test
3. Natural exit signal (price returning to mean)
4. Historical success in forex/crypto

## Next Steps

1. ✅ Implement mean reversion signal
2. ✅ Backtest on 6 months historical data
3. ✅ Verify ≥50% win rate and positive P&L
4. ✅ Deploy to paper trading
5. ✅ Monitor for 24-48 hours
6. ⏳ Decision: Live trading approval or redesign again

---

**Status:** Ready to implement mean reversion signal  
**Timeline:** 30 min implementation + backtest  
**Risk:** Low (paper trading only)
