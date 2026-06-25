# When to Buy More: Logical Decision Framework

**Document:** Phase 1 & Beyond  
**Date:** 2026-06-25  
**Status:** Reference guide for position management

---

## Quick Answer

**Phase 1 (NOW):** Buy more when signal score ≥ 60 AND active positions < 5 AND daily loss > -€500

**Phase 2+:** Add pyramid strategy (average up on winners, careful averaging down)

---

## Current System Parameters

```
Entry Threshold:      60.0 (signal score, 0-100 scale)
Position Size:        5% per trade (€500 on €10k)
Max Positions:        5 concurrent
Profit Target:        3% per trade
Stop Loss:            2% per trade
Daily Loss Limit:     5% (€500)
Capital:              €10,000 (paper trading)
```

---

## Decision Framework: When to Buy More

### ✅ NEW SYMBOL ENTRY (Currently Implemented)

**Sound to buy new position when ALL of:**
- Signal score ≥ 60 ✅
- Active positions < 5 ✅
- Daily P&L > -€500 ✅
- Capital available ✅
- Different symbol (not averaging) ✅

**Example:**
```
Active: BTC, ETH, BNB (3/5 positions)
Signal: ADA score 62 (above 60 threshold)
Daily P&L: €0 (safe zone)
Action: ✅ BUY ADA (new position #4)
```

**Why this works:**
- Each position independently 5% of capital
- Diversification across symbols
- Clear entry rule (score-based)
- Predictable risk per position

---

### ⚠️ AVERAGING INTO WINNERS (Phase 2+)

**Sound to scale up position when ALL of:**
- Position in PROFIT (e.g., +1-2%)
- Signal score INCREASING (momentum strong)
- Total position < 15% of capital (3x max)
- Daily P&L has buffer (> -€300)

**Example:**
```
Entry 1: BTC @ €61,758 (5% position)
Current: BTC @ €62,500 (+1.2%)
Signal: 60.0 → 70.0 (momentum building!)

Sound to add? ✅ YES
  • In profit (€100+ buffer)
  • Signal stronger (70 > 60)
  • Total BTC = 10% < 15% limit
  • Daily loss room: €500 - €100 = €400 ✅

Entry 2: Add 5% more BTC at €62,500
```

**Why this works (pyramid strategy):**
- Reduce average cost as winner grows
- Each new entry already has profit cushion
- Signal strength validates momentum
- Capped risk per symbol (15% max)

**Result after 3 entries:**
```
Entry 1: €100 @ €61,758 (now €101.20)
Entry 2: €100 @ €62,500 (now €100 at market)
Entry 3: €100 @ €62,800 (now €99.50)
────────────────────────────────
Total: €300 at avg €62,350
Risk: If exits at €62,000, loss = €105 (manageable)
Win: If exits at €64,500, gain = €645 (67% ROI on €300 stake)
```

---

### ❌ AVERAGING INTO LOSERS (CAUTION!)

**Only sound if ALL conditions met:**
- Signal score INCREASES despite price drop (technical recovery)
- RSI < 30 (oversold = reversal signal)
- Position loss < 1% (small loss only)
- Can absorb 2x loss before hitting daily limit

**Example (NOT sound):**
```
Entry 1: ETH @ €1,650
Current: ETH @ €1,600 (-0.3%)
Signal: 60.0 → 50.0 (DECREASING - momentum failing)

Sound to average down? ❌ NO
  • Signal WEAKENED (50 < 60)
  • Momentum failing, not recovering
  • Averaging down into weakness = trap
```

**Example (CONDITIONALLY sound):**
```
Entry 1: ETH @ €1,650
Current: ETH @ €1,600 (-0.3%)
Signal: 60.0 → 65.0 (INCREASING - recovery!)
RSI: 28 (oversold)

Sound to average down? ⚠️ ONLY IF:
  • Daily P&L > -€400 (buffer exists)
  • Max 1 more position same symbol
  • Can afford 2x loss (€60 × 2 = €120)

Entry 2: Add 5% at €1,600 (lower average)
```

**Why dangerous:**
- Throwing good money after bad (if signal is wrong)
- Doubles loss if price continues down
- Requires strong technical signals to justify

---

## Regime-Aware Buying

Your system detects market regime. Adjust buying logic:

### BULL MARKET (Price UP, RSI 50-70)
```
Entry Threshold: 60 (normal)
Position Size: 5% (normal)
Strategy: BUY MORE on dips
Rationale: Momentum with you, add on -0.5% pullbacks
```

### BEAR MARKET (Price DOWN, RSI 30-50)
```
Entry Threshold: 70 (RAISE - require stronger signal)
Position Size: 2.5% (REDUCE - half risk)
Strategy: BUY ONLY on reversal signals (RSI < 20)
Rationale: Trend against you, need strong confirmation
```

### SIDEWAYS MARKET (Range-bound, RSI 40-60)
```
Entry Threshold: 60 (normal)
Position Size: 5% (normal)
Strategy: BUY at support, SELL at resistance
Rationale: Mean reversion works best here
```

### VOLATILE MARKET (Wild swings, RSI extreme)
```
Entry Threshold: 75 (RAISE - only extreme signals)
Position Size: 2.5% (REDUCE - half risk)
Stop Loss: 1% (TIGHTEN - exit noise faster)
Strategy: REDUCE exposure, wait for calm
Rationale: Random moves break position sizing logic
```

---

## Mathematical Decision Rules

### Rule 1: New Position Entry
```python
if (signal_score >= 60 
    and active_positions < 5 
    and daily_pnl > -500 
    and capital_available > 0):
    BUY_NEW_POSITION()  # ✅ Sound
```

### Rule 2: Pyramid Scaling (Average Up)
```python
if (signal_score >= 60 
    and signal_score > previous_signal  # ← Momentum increasing!
    and position_pnl > 0  # ← In profit
    and position_size_for_symbol < 0.15):  # ← Max 15% per symbol
    BUY_MORE_OF_SAME()  # ✅ Sound
```

### Rule 3: Cost Averaging (Average Down)
```python
if (signal_score > previous_signal  # ← MUST IMPROVE
    and rsi < 30  # ← Oversold recovery signal
    and abs(position_pnl) < -0.01  # ← Small loss only
    and daily_pnl > -300  # ← Buffer exists
    and position_count_for_symbol < 2):  # ← Max 2 same symbol
    AVERAGE_DOWN()  # ⚠️ Conditional
```

---

## Phase 1 vs Phase 2 Strategy

### PHASE 1 (NOW): Validation Phase
**Goal:** Understand which entries/exits work

```
Strategy: NEW SYMBOL ENTRIES ONLY
  • Each signal → 5% position
  • No averaging (keep simple)
  • No regime adjustments (need data)
  
Monitor:
  • Which entries hit 3% profit target?
  • Which hit 2% stop loss?
  • Do higher signal scores = higher win rate?
  • What's the Sharpe ratio?
```

### PHASE 2 (After Phase 1): Optimization Phase
**Goal:** Maximize return with validated signals

```
Strategy: ADD PYRAMID SCALING
  • Scale into confirmed winners
  • Use regime-aware adjustments
  • Test cost-averaging on reversals
  
Measure:
  • Does pyramid improve Sharpe ratio?
  • Does averaging down reduce losses?
  • Does regime awareness improve win rate?
```

---

## Risk Limits (Hard Stops)

Never buy more if ANY of these are true:

```
❌ Daily P&L < -€500 (daily loss limit hit)
❌ Active positions >= 5 (max position count)
❌ Capital deployed >= €9,500 (keep cash buffer)
❌ Signal score < 60 (below entry threshold)
❌ Same symbol position >= 15% (concentration limit)
❌ Any single position loss >= 2% (stop loss)
```

---

## Examples: Sound vs Unsound Buying

### SOUND ✅
```
Scenario 1: New entry
  • BTC signal 62 (>60)
  • 2 active positions (<5)
  • P&L €0 (>-€500)
  Action: BUY BTC ✅

Scenario 2: Pyramid (average up)
  • BTC at +1.5% profit
  • Signal 60→68 (increasing)
  • Total BTC = 10% (<15%)
  Action: ADD BTC ✅

Scenario 3: Market opportunity
  • Bull regime (RSI 65)
  • ADA signal 70 (strong)
  • 4 active positions (<5)
  Action: BUY ADA ✅
```

### UNSOUND ❌
```
Scenario 1: Below threshold
  • ETH signal 55 (<60)
  • Why: Signal not strong enough
  Action: SKIP ❌

Scenario 2: Too concentrated
  • BTC already 15% of capital
  • Want to add more
  • Why: Max position size hit
  Action: SKIP ❌

Scenario 3: Averaging down poorly
  • ETH down 0.5%
  • Signal 62→58 (weakening!)
  • Why: Momentum failing, not recovering
  Action: SKIP ❌

Scenario 4: Loss limit
  • Daily P&L = -€480
  • Want to buy more
  • Why: Only €20 buffer left
  Action: SKIP ❌
```

---

## Key Insight: Why Phase 1 is "New Entries Only"

Pyramid scaling works great, but **you must first validate your signal quality**.

If your signals are wrong:
- **New entry at threshold:** Limited damage (5% per bad trade)
- **Pyramid on bad signal:** Compound losses (5% × 3 entries = 15% on one bad trade)

**Answer:** Validate in Phase 1, optimize in Phase 2.

---

## Checklist: Before Buying More

Every time you consider buying more, check:

- [ ] Signal score ≥ 60?
- [ ] Active positions < 5?
- [ ] Daily P&L > -€500?
- [ ] Capital available?
- [ ] Regime-appropriate threshold?
- [ ] If averaging: position in profit?
- [ ] If averaging: signal improving?
- [ ] If averaging: total < 15% per symbol?

**If all YES → Buy more is sound** ✅  
**If any NO → Skip this entry** ❌

---

## Summary

| Strategy | Phase 1 | Phase 2+ | Risk | Profit |
|----------|---------|----------|------|--------|
| New entries only | ✅ | ✅ | Low | Good |
| Pyramid (avg up) | ❌ | ✅ | Medium | Better |
| Cost average (avg down) | ❌ | ⚠️ | High | Risky |
| Regime adjustments | ❌ | ✅ | Low | Better |

**Phase 1 recommendation:** Keep it simple. New entries only, signal ≥ 60.

**Phase 2+ roadmap:** Validate pyramid scaling and regime adjustments with Phase 1 data.
