# Trend-Following Signal: Complete Design Specification

**Version:** 1.0  
**Status:** Final Design (Ready for Backtesting)  
**Date:** 2026-07-04  
**Strategy:** Multi-Timeframe Trend-Following with Momentum Confirmation

---

## Executive Summary

This signal trades **breakouts above resistance with trend confirmation**, designed specifically for crypto's directional moves on intraday timeframes.

**Key Metrics (Target):**
- Win Rate: 55-60%
- Profit Factor: 1.5x+
- Sharpe Ratio: 1.0+
- Max Drawdown: <15%
- Avg Trade Duration: 5-15 minutes

---

## Part 1: Data Requirements

### Candle Data
- **Entry Candles:** 5-minute OHLCV (open, high, low, close, volume)
- **Trend Candles:** 1-hour OHLCV
- **Trend Filter:** 4-hour OHLCV
- **History Depth:** 100 candles per timeframe minimum

### Symbols
- BTCUSDT
- ETHUSDT
- BNBUSDT

### Availability
- Binance Spot (paper trading during backtest)
- Live market data during paper trading phase

---

## Part 2: Indicator Definitions

### 1. Exponential Moving Average (EMA)
**Formula:**
```
EMA = (Close × Multiplier) + (EMA_Previous × (1 - Multiplier))
where Multiplier = 2 / (N + 1)
```

**Used in Signal:**
- `EMA5_5min`: 5-period EMA on 5-minute candles
- `EMA20_5min`: 20-period EMA on 5-minute candles
- `EMA5_1hr`: 5-period EMA on 1-hour candles
- `EMA20_1hr`: 20-period EMA on 1-hour candles
- `EMA20_4hr`: 20-period EMA on 4-hour candles

### 2. RSI (Relative Strength Index)
**Formula:**
```
RSI = 100 - (100 / (1 + RS))
where RS = AvgGain / AvgLoss (14-period)
```

**Used in Signal:**
- `RSI14_5min`: 14-period RSI on 5-minute candles
- Overbought: > 70
- Oversold: < 30

### 3. Volume
**Used in Signal:**
- `Avg_Volume_20`: Average volume over last 20 candles
- `Current_Volume`: Current candle volume
- Volume Ratio: Current_Volume / Avg_Volume_20

### 4. Support & Resistance (Lookback)
**Used in Signal:**
- `High5_5min`: Highest high over last 5 candles (resistance)
- `Low5_5min`: Lowest low over last 5 candles (support)

---

## Part 3: Entry Signal (Complete Logic)

### Pre-Conditions (Must All Be True)

**1. Trend Filter (4-hour timeframe) — Is the Macro Trend Up?**
```
Current_Price > EMA20_4hr
Interpretation: Price is trading above the 4-hour trend line
Rationale: Don't buy in downtrends; only go long when 4-hour trend is up
```

**2. Momentum Filter (1-hour timeframe) — Is Momentum Positive?**
```
EMA5_1hr > EMA20_1hr
Interpretation: Short-term 1-hour momentum is above longer-term 1-hour average
Rationale: Price is accelerating upward on the 1-hour
```

**3. Entry Signal (5-minute timeframe) — New Breakout?**
```
Close_5min > High5_5min (previous 5 candles' high)
Interpretation: Current candle closes above the last 5 candles' high
Rationale: Momentum break above recent resistance; classic breakout entry
```

**4. Volume Confirmation (5-minute timeframe) — Is There Real Interest?**
```
Current_Volume_5min > (1.5 × Avg_Volume_20)
Interpretation: Current candle has 50% more volume than 20-candle average
Rationale: Volume confirms breakout is real, not a false break
```

**5. Overbought Filter (5-minute timeframe) — Not Too Extended?**
```
RSI14_5min < 70
Interpretation: RSI is not in overbought territory
Rationale: Avoids buying at extremes where reversal is likely
```

### Entry Signal Strength Calculation

**Base Score: 50 points**
- Awarded when all 5 pre-conditions are met

**Bonus Points:**
```
+ 15 points if EMA5_1hr > EMA20_1hr AND distance > 0.5% (strong momentum)
+ 10 points if Current_Volume_5min > (2.0 × Avg_Volume_20) (very strong volume)
+ 10 points if RSI14_5min < 50 (room to run up)
+ 5 points if Close_5min > EMA5_5min (in uptrend on 5-min)

Total Score Range: 50-90 points
```

### Threshold
```
Entry_Threshold = 65
Buy Signal Generated if: Signal_Strength ≥ 65
```

### Example Entry
```
Symbol: BTCUSDT
Current Price: $62,500

Pre-Conditions Check:
✅ $62,500 > $62,000 (EMA20_4hr)        — Trend: UP
✅ EMA5_1hr ($62,150) > EMA20_1hr ($62,050)  — Momentum: UP
✅ Close ($62,520) > High5 ($62,450)    — Breakout: YES
✅ Volume (150 BTC) > 1.5× Avg (80 BTC) — Confirmation: YES
✅ RSI (62) < 70                        — Not overbought: YES

Signal Strength:
Base: 50
+ 15 (EMA distance > 0.5%)
+ 10 (Volume > 2x)
+ 0 (RSI > 50)
+ 5 (Close > EMA5)
= 80 points

Action: BUY at market price ($62,500)
Strength: 80/100
Reason: "Breakout above 5-candle resistance with strong volume + positive momentum"
```

---

## Part 4: Exit Signals (Strict Order)

Exit triggers are checked in order. First true condition wins.

### Exit Condition 1: Trend Reversal (Tightest Stop)
```
Close_5min < Low5_5min (closes below last 5 candles' low)

Interpretation: Price closes below recent support; trend has reversed
Trigger Speed: Immediate on next candle close below support
Exit Price: Market price at next bar open
Reason: "Trend reversal below support"

Why This First: Protects against reversals; stops losses immediately
```

### Exit Condition 2: Stop Loss (Hard Stop)
```
Current_Price ≤ Entry_Price × (1 - 0.01)
In Plain English: Unrealized loss ≥ 1.0%

Interpretation: Position has lost 1% of entry value
Trigger Speed: Continuous check, executes immediately when hit
Exit Price: Market price (or stop order execution)
Reason: "Stop loss -1.0%"

Why This: Hard risk limit; prevents catastrophic losses
```

### Exit Condition 3: Profit Target (Take Profit)
```
Current_Price ≥ Entry_Price × (1 + 0.02)
In Plain English: Unrealized profit ≥ 2.0%

Interpretation: Position has gained 2% of entry value
Trigger Speed: Continuous check, executes when target hit
Exit Price: Market price (or limit order at target)
Reason: "Profit target +2.0%"

Why This: Locks in wins; maintains 2:1 risk/reward ratio
```

### Exit Condition 4: Time Exit (Maximum Hold Time)
```
Hold_Time ≥ 600 seconds (10 minutes)

Interpretation: Position held for 10 minutes with no other exit
Trigger Speed: Checked every minute
Exit Price: Market price at 10-minute mark
Reason: "Time exit after 10 minutes"

Why This: Frees capital; prevents positions from running indefinitely
```

### Exit Condition 5: Daily Halt (Emergency Stop)
```
Daily_Loss ≥ 2.0% (€20 on €1,000 account)

Interpretation: Daily losses hit the hard limit
Trigger Speed: Checked before every new entry
Exit Price: Current market price (already lost)
Reason: "Daily loss limit reached"

Action: STOP ALL ENTRIES until next day. Allow exits only.

Why This: Prevents loss spirals; mandatory trading pause
```

### Exit Logic Diagram
```
┌─ Trend Reversal? (Close < Low5)     → SELL (tightest, protects first)
│
├─ Stop Loss? (Loss ≥ 1%)             → SELL (hard risk limit)
│
├─ Profit Target? (Gain ≥ 2%)         → SELL (locks wins)
│
├─ Time Exit? (Hold ≥ 10 min)         → SELL (free capital)
│
└─ Daily Halt? (Daily Loss ≥ 2%)      → STOP ENTRIES (emergency)
```

---

## Part 5: Position Sizing

### Position Size Calculation
```
Available_Cash = Account_Cash - Reserve
Reserve = 10% of total account (safety buffer)

Position_Size_USD = Available_Cash × Position_Size_Pct
Position_Size_Pct = 1.5% (of available capital)

Quantity = Position_Size_USD / Entry_Price
```

### Example Position Size
```
Account Cash: €1,000
Reserve (10%): €100
Available: €900

Position Size %: 1.5%
Order Value: €900 × 1.5% = €13.50

BTCUSDT at €62,500:
Quantity: €13.50 / €62,500 = 0.000216 BTC ≈ 0.0002 BTC
```

### Constraints
```
Max Concurrent Positions: 2 per symbol
Max Daily Orders: 50 (prevents runaway system)
Min Order Size: €5.00 (minimum viable position)
Max Order Size: €50.00 (never more than 5% per trade)
```

---

## Part 6: Risk Management

### Per-Trade Risk Limit
```
Max Loss Per Trade: 1.0%
Max Win Per Trade: 2.0% (stops gains)
Risk/Reward Ratio: 1:2 (1% risk, 2% reward)
Position Size: 1.5% of account
```

### Daily Risk Limit
```
Max Daily Loss: 2.0% (€20 on €1,000)
Action on Breach: Stop all new entries, allow exits only
Recovery: Resets at midnight UTC
```

### Account-Level Limits
```
Max Positions: 2 concurrent (never more than 2 active trades)
Max Symbols: 3 (BTCUSDT, ETHUSDT, BNBUSDT)
Emergency Stop: Total Account Loss ≥ 5% (€50)
```

---

## Part 7: Signal Strength Scoring

### How Signal Strength is Calculated (0-100 scale)

**Step 1: Check all 5 pre-conditions**
```
If ANY pre-condition fails:
  Signal_Strength = 0
  Return: NO SIGNAL

If ALL pre-conditions pass:
  Signal_Strength = 50 (baseline)
  Continue to Step 2
```

**Step 2: Add bonuses for strong confirmation**
```
Bonus 1: Strong Momentum (+ 15 points)
  IF EMA5_1hr > EMA20_1hr AND distance > 0.5%
  Reason: Not just barely above; distance shows strength

Bonus 2: Volume Surge (+ 10 points)
  IF Current_Volume > (2.0 × Avg_Volume_20)
  Reason: 100% above average = really strong confirmation

Bonus 3: RSI Room to Run (+ 10 points)
  IF RSI14_5min < 50
  Reason: Still has room to go up; not yet overbought

Bonus 4: 5-min Uptrend (+ 5 points)
  IF Close_5min > EMA5_5min
  Reason: Immediate 5-min trend supports entry
```

**Step 3: Calculate final score**
```
Final_Score = 50 + Sum(Bonuses)
Range: 50-90 points

Threshold: 65 points
  If Score ≥ 65: Generate BUY signal
  If Score < 65: Wait for next candle
```

### Signal Strength Examples

```
Scenario 1: Weak Breakout
- Base: 50
- No strong momentum (EMA distance < 0.5%): 0
- Volume just > 1.5x: 0
- RSI > 50: 0
- Close > EMA5: +5
= 55 points → NO SIGNAL (below 65)

Scenario 2: Strong Breakout (Typical)
- Base: 50
- Strong momentum (EMA distance 1.5%): +15
- Volume > 2x: +10
- RSI < 50: +10
- Close > EMA5: +5
= 90 points → BUY SIGNAL (at maximum)

Scenario 3: Moderate Breakout
- Base: 50
- Momentum (0.8%): +15
- Volume 1.8x: +10
- RSI = 62: 0
- Close > EMA5: +5
= 80 points → BUY SIGNAL
```

---

## Part 8: Backtesting Parameters

### Test Configuration
```
Historical Data: 2025-01-04 to 2026-07-04 (18 months)
Candle Interval: 5-minute OHLCV
Symbols: BTCUSDT, ETHUSDT, BNBUSDT
Starting Capital: €1,000
Commission: 0.1% (Binance maker)
Slippage: 0.1% (market order impact)
```

### Success Criteria
```
PASS if ALL are met:
✅ Win Rate ≥ 55% (more wins than losses)
✅ Profit Factor ≥ 1.5x (total wins / total losses)
✅ Sharpe Ratio ≥ 1.0 (return vs risk)
✅ Max Consecutive Losses < 5 (avoid psychological stress)
✅ Max Drawdown < 15% (acceptable loss from peak)
✅ Positive P&L on all 3 symbols (no poison symbols)

FAIL if ANY are not met:
❌ Must redesign and retest
```

---

## Part 9: Candle Patterns to Avoid

### Pattern 1: Gap Down Open
```
If Open_5min < Previous_Close × 0.98 (>2% gap down):
  Don't trade for first 3 candles
  Reason: Volatile opening; wait for stability
```

### Pattern 2: High Volatility Day
```
If ATR14_daily > Historical_ATR × 2.0:
  Reduce position size by 50%
  Reason: High volatility = wider stops = more risk
```

### Pattern 3: News Event
```
If Major_News_Alert (hardcoded dates):
  Skip trading for 1 hour after announcement
  Reason: Unpredictable price action
  Dates: (None initially; add as needed)
```

---

## Part 10: Implementation Checklist

### Pre-Backtest
- [ ] Verify all indicator calculations (EMA, RSI, Volume)
- [ ] Confirm candle data availability (5-min, 1-hr, 4-hr)
- [ ] Test entry conditions on sample candles
- [ ] Test exit conditions on sample positions
- [ ] Verify position sizing calculations
- [ ] Confirm P&L calculation accuracy

### During Backtest
- [ ] Track all trades (entry price, exit price, reason)
- [ ] Calculate win rate, profit factor, Sharpe
- [ ] Identify best/worst performing symbols
- [ ] Chart equity curve
- [ ] Find maximum consecutive losses
- [ ] Identify drawdown periods

### Post-Backtest
- [ ] Analyze results against success criteria
- [ ] If FAIL: Identify which parameter to adjust
- [ ] If PASS: Proceed to Phase 3 (Paper Trading)

---

## Part 11: Parameter Tuning (If Needed)

If backtest fails, adjust in this order:

**Priority 1: Entry Threshold**
```
Current: 65
Options: 60 (looser), 70 (stricter)
Impact: Affects entry frequency
```

**Priority 2: EMA Periods**
```
Current: EMA5 for momentum, EMA20 for trend
Options: EMA3/15 (faster) or EMA7/21 (slower)
Impact: Changes entry frequency and reliability
```

**Priority 3: Stop Loss / Profit Target**
```
Current: 1% stop, 2% target
Options: Try 0.8%/2.4% or 1.5%/3%
Impact: Changes risk/reward ratio
```

**Priority 4: Time Exit**
```
Current: 10 minutes
Options: 5 minutes (faster) or 15 minutes (slower)
Impact: Trade duration and capital efficiency
```

---

## Summary: One-Page Quick Reference

```
ENTRY (ALL must be true):
1. Price > EMA20_4hr        (macro trend up)
2. EMA5_1hr > EMA20_1hr     (momentum up)
3. Close > High5_5min       (breakout confirmed)
4. Volume > 1.5x avg        (real interest)
5. RSI < 70                 (not overbought)

Score = 50 + bonuses (momentum, volume, RSI, trend)
Buy if Score ≥ 65

EXIT (first true condition):
1. Close < Low5_5min        (trend reversal)
2. Loss ≥ 1%                (stop loss)
3. Gain ≥ 2%                (profit target)
4. Hold > 10 min            (time exit)
5. Daily Loss ≥ 2%          (halt trading)

POSITION SIZE: 1.5% of available capital
MAX POSITIONS: 2 concurrent
RISK/REWARD: 1:2 (1% risk, 2% target)

TARGET PERFORMANCE:
✅ Win Rate: 55-60%
✅ Profit Factor: 1.5x+
✅ Max Drawdown: <15%
```

---

## Ready for Backtesting

This specification is complete and unambiguous. Ready to proceed to:
- **Phase 2:** Implement backtesting framework
- **Phase 2:** Backtest on 18 months historical data
- **Phase 2:** Validate performance against criteria

**Status:** ✅ DESIGN COMPLETE — APPROVED FOR BACKTESTING
