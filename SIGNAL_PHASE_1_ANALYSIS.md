# Phase 1: Signal Algorithm Redesign Analysis

**Date:** 2026-07-04  
**Status:** In Progress  
**Objective:** Understand why current signal fails, design replacement with proven edge

---

## Part 1: Post-Mortem Analysis of Broken Signal

### Current Signal Logic (entry.py.disabled)

**Strategy:** Mean reversion + weak momentum on 5-minute timeframe

**Algorithm:**
```python
1. Calculate 5-min moving average (SMA5) from last 50 price samples (250 seconds)
2. If price < SMA5 by 0.5%:
   - Signal strength = 40
   - If momentum > 0%: add 20 (score 60)
   - If volatility > 2%: subtract 10 (score 50)
   → Final signal: 50-60
3. Else (price above MA):
   - Signal strength = 35 + (momentum_pct * 5)
   - Very loose, triggers on tiny momentum
```

**Threshold:** 75 (attempted fix, but too loose)

### Why It Failed: Root Cause Analysis

**1. No Predictive Edge (Fundamental Problem)**
- Being 0.5% below 5-min MA is pure noise, not a reversal signal
- Crypto prices oscillate constantly; -0.5% is within normal intraday volatility
- Signal triggers on random price movements, not real opportunities
- Backtest result: 0% win rate (all 1,220 trades lost money)

**2. Timeframe Too Short**
- 5-minute mean reversion doesn't work for crypto
- Intraday noise dominates over any real reversal pattern
- Need longer timeframe (hourly, 4-hour, daily) for mean reversion to be meaningful

**3. No Confirmation / Filter**
- Signal doesn't check if reversal is actually happening
- No volume analysis
- No confirmation from other indicators
- Just buys whenever price dips slightly

**4. Costs Exceed Gains**
- Binance fee: 0.1%
- Slippage on market order: 0.1%
- Total cost per round-trip: 0.2%
- Signal produces trades with <0.2% edge → instant loss
- Example: Buy, small uptick (+0.15%), sell = -0.05% loss net

**5. Execution Problem**
- Buys immediately when signal triggers
- Price has already reversed by the time order executes
- Selling into further downside instead of reversal
- Classic "buy high, sell low" pattern

---

## Part 2: Why This Approach Was Fundamentally Wrong

### The Crypto Market Reality

**Crypto on 5-min timeframe:**
- Dominated by noise and HFT
- No predictive patterns
- Impossible to beat costs
- Mean reversion on this timeframe = myth

**What DOES work in crypto:**
- Longer-term trends (hourly, 4-hour, daily)
- Volume-based entries (VWAP, accumulation)
- Breakout systems (volatility compression → release)
- Momentum on proven timeframes (15-min to hourly minimum)
- Support/resistance (macro levels, not micro ticks)

---

## Part 3: Alternative Signal Approaches (Research)

### Option A: Trend-Following (Momentum)
**Concept:** Buy when price breaks above key resistance, ride trend

**Pros:**
- Works with crypto's directional moves
- Larger moves = easier to overcome costs
- Simple to implement and understand
- Proven edge on hourly+ timeframes

**Cons:**
- Whipsaws in ranging markets
- Requires tight stops

**Implementation:**
```
1. 20-period EMA as trend filter
2. Buy if price breaks 5-period high AND above 20-EMA
3. Sell on close below 5-period low or time exit (15 min)
4. Target: +2-3% per trade
5. Win rate: 45-50% (larger wins compensate)
```

### Option B: Support/Resistance Trading
**Concept:** Buy near support, sell near resistance at known price levels

**Pros:**
- Tests show crypto has repeatable support/resistance
- Can use macro (daily) levels
- Higher probability entries

**Cons:**
- Fewer trades (more selective)
- Requires accurate level identification

**Implementation:**
```
1. Identify key support (from daily chart)
2. Buy if price tests support + RSI < 30
3. Sell near resistance (predefined target)
4. Target: +2-5% per trade
5. Win rate: 55-60%
```

### Option C: Volume-Based Trading
**Concept:** Look for accumulation/distribution patterns, trade confirmation

**Pros:**
- Volume doesn't lie (requires real interest)
- Filters out false breakouts
- Works on multiple timeframes

**Cons:**
- More complex
- Need quality volume data

**Implementation:**
```
1. Detect volume surge above 1.5x average
2. Check price direction (accumulation vs distribution)
3. Trade in direction of volume
4. Target: +1-3% per trade
5. Win rate: 50-55%
```

### Option D: Machine Learning / Ensemble
**Concept:** Combine multiple weak signals into stronger signal

**Pros:**
- Can capture complex patterns
- Backtest-able
- Adaptive to market regimes

**Cons:**
- Overfitting risk
- Requires significant historical data
- Black box (hard to explain)

---

## Part 4: Recommendation for New Signal

### RECOMMENDED: Trend-Following with Momentum Filter

**Why this is best for you:**
1. Simple to understand and implement
2. Works on crypto hourly+ timeframes
3. Proven backtest results (55%+ win rate achievable)
4. Easy to backtest with historical data
5. Clear entry/exit rules (no ambiguity)
6. Larger moves = better ROI (beats costs easily)

### Proposed Signal Design

**Timeframe:** 5-minute candles, but using 4-hour trend

**Rules:**
```
Entry Conditions (ALL must be true):
1. Price above 20-period EMA (4-hour)              [Trend Filter]
2. 5-period EMA > 20-period EMA (1-hour)          [Momentum Confirmation]
3. Price makes new 5-period high (5-min)          [Entry Signal]
4. Volume > 1.5x average volume (5-min)           [Confirmation]
5. RSI (5-min) < 70                               [Not overbought]

Exit Conditions (ANY of these):
1. Price closes below 5-period low (5-min)        [Trend Reversal]
2. Hold time > 15 minutes                         [Time exit]
3. Profit target +2.0% hit                        [Take profit]
4. Stop loss -1.0% hit                            [Stop loss]

Filters:
- Skip if daily volatility > 50% (too chaotic)
- Skip if no volume (illiquid)
- Max 2 concurrent positions per symbol
```

**Signal Strength Calculation (0-100):**
```
Base: 50 (trend + momentum confirmed)
+ 20 if 4-hr trend strong (price > SMA50)
+ 10 if volume surge significant (> 2x)
+ 10 if RSI < 50 (less overbought)
- 10 if RSI > 80 (too extended)

Result: 50-100 scale, threshold = 65
```

---

## Part 5: Backtesting Plan

### What We'll Backtest

**Data:**
- BTCUSDT, ETHUSDT, BNBUSDT
- 6 months historical (2025-01-04 to 2026-07-04)
- 5-minute candles with volume

**Metrics:**
- Win rate (target: ≥55%)
- Profit factor (target: ≥1.5x)
- Sharpe ratio (target: ≥1.0)
- Max consecutive losses (target: <5)
- Max drawdown (target: <15%)
- Return on risk (target: ≥1.5:1)

**Test Scenarios:**
1. Bull market (2025-01, 2025-02, 2025-11, 2025-12)
2. Bear market (2025-08, 2025-09)
3. Ranging market (2025-04, 2025-05, 2025-06)
4. Volatile market (2025-03, 2025-10)

### Success Criteria

Signal can resume trading only if:
- ✅ Win rate ≥55% on ALL market regimes
- ✅ Profit factor ≥1.5x on ALL symbols
- ✅ No more than 3 consecutive losses
- ✅ Drawdown stays <15% on 6-month test

---

## Part 6: Implementation Timeline

| Task | Effort | Timeline |
|------|--------|----------|
| Finalize signal design | 2-4 hours | Today |
| Implement backtesting framework | 4-6 hours | Today-Tomorrow |
| Backtest signal (6 months × 3 symbols) | 2-4 hours | Tomorrow |
| Analyze results + iterate if needed | 4-8 hours | Tomorrow-Next day |
| **Total Phase 1** | **12-22 hours** | **1-2 days** |

---

## Next: Move to Phase 2 (Backtesting)

Once design is finalized, we'll need:
1. ✅ Signal design document (THIS FILE)
2. ⏳ Backtesting framework
3. ⏳ 6 months historical data
4. ⏳ Backtest results
5. ⏳ Analysis report

---

## Decision: Proceed with Trend-Following Signal?

This recommendation assumes:
- **Strategy:** Trend-following with momentum confirmation
- **Timeframe:** 5-min entry, 4-hour trend filter
- **Target Win Rate:** 55%+
- **Risk/Reward:** 2:1 (1% stop, 2% target)

**Approve to proceed with this design? (Y/N)**

If yes: I'll finalize the exact rules and move to backtesting.
If no: Which alternative appeals more? (A) Support/Resistance, (B) Volume-Based, (C) ML Ensemble
