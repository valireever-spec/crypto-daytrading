# Critical Parameters Monitoring System

**Status:** ✅ LIVE  
**Purpose:** Real-time visibility into 6 critical trading parameters  
**Update Frequency:** 10 seconds (dashboard), continuous (backend)

---

## 📊 The 6 Critical Parameters

### 1️⃣ **TREND FILTER** (1h RSI > 50)
**What:** Only trade when market is trending upward  
**Target:** ≥50% signals pass trend filter  
**Why:** Prevents buying in downtrends and sideways chop

```
Example:
✅ Market: 1h RSI = 65 (uptrend) → ENTER
❌ Market: 1h RSI = 45 (weak) → SKIP
❌ Market: 1h RSI = 25 (downtrend) → SKIP
```

**Endpoint:** `/api/parameters/trend-filter`

**Shows:**
- Total signals checked (last 60 min)
- Signals that passed filter (1h RSI > 50)
- Pass rate percentage
- Current 1h RSI level

**Health Status:**
- 🟢 GREEN: ≥50% pass rate (strong uptrends)
- 🟡 YELLOW: 20-50% pass rate (choppy market)
- 🔴 RED: <20% pass rate (downtrending, no setups)

---

### 2️⃣ **SIGNALS** (Entry Generation)
**What:** Quality and frequency of entry signals  
**Target:** 40-50 signals/hour with avg strength ≥60  
**Why:** Signals are your trading opportunities

```
Ideal distribution:
- Weak (<40 strength): 30% - filter these out
- Medium (40-70): 50% - decent setups
- Strong (70+): 20% - best entries
```

**Endpoint:** `/api/parameters/signals`

**Shows:**
- Total signals generated
- Average signal strength (0-100)
- Signal strength distribution (weak/medium/strong)
- Regime distribution (uptrend/downtrend/ranging)
- Signals per minute

**Health Status:**
- 🟢 GREEN: 20+ signals in window
- 🟡 YELLOW: 5-20 signals (quiet market)
- 🔴 RED: <5 signals (no trading opportunities)

---

### 3️⃣ **STOPS** (Stop Loss at -0.5%)
**What:** Effectiveness of stop loss protection  
**Target:** Avg loss should be around -0.4% to -0.5%  
**Why:** Protects capital on bad entries

```
Good: Avg loss -0.45% (stops working as intended)
Bad: Avg loss -0.2% (stops hit too early, premature exits)
Bad: Avg loss -0.8% (slippage issues, needs tighter entry)
```

**Endpoint:** `/api/parameters/stops`

**Shows:**
- Stop loss hits (count in last 2 hours)
- Average loss percentage
- Worst single stop loss
- Best (smallest) stop loss
- Average hold time before stop

**Health Status:**
- 🟢 GREEN: Hits occurring, avg loss -0.4% to -0.5%
- 🟡 YELLOW: Few hits or avg worse than -0.5%
- 🔴 RED: No stop protection working

---

### 4️⃣ **TARGETS** (Profit Target at +2.0%)
**What:** Effectiveness of profit taking  
**Target:** Should hit ≥40% as often as stops hit  
**Why:** Locks in profits when market moves your way

```
Good: Targets hit 50% as often as stops (balanced)
Bad: Targets hit 10%, stops hit 90% (strategy losing)
```

**Endpoint:** `/api/parameters/targets`

**Shows:**
- Profit target hits (count in last 2 hours)
- Average win percentage
- Best single profit target hit
- Worst profit target hit
- Average hold time to target

**Health Status:**
- 🟢 GREEN: Targets hit frequently, avg win +1.8% to +2.0%
- 🟡 YELLOW: Few target hits
- 🔴 RED: No targets hitting

---

### 5️⃣ **EXIT REASONS** (Why Positions Closed)
**What:** Breakdown of how/why positions ended  
**Target:** Balanced between "Profit target" and "Stop loss"  
**Why:** Shows if strategy works (exits profit) or fails (exits loss)

```
Perfect balance:
- Profit target: 50%
- Stop loss: 40%
- 10-min timeout: 10%

Problem: 
- Profit target: 10%
- Stop loss: 90%
→ Strategy losing, need better entries
```

**Endpoint:** `/api/parameters/exit-reasons`

**Shows:**
- Distribution of exit types (profit target, stop loss, timeout)
- Count of each exit type
- Average P&L for each exit type
- Most common exit reason

**Expected Exits:**
1. **"Profit target"** — Strategy working, position grew to +2%
2. **"Stop loss"** — Entry was bad, lost -0.5%
3. **"10-minute timeout"** — Market stalled, force-closed for safety

---

### 6️⃣ **ENTRY REASONS** (Why Positions Opened)
**What:** Breakdown of entry signal types  
**Target:** Diverse (different reasons = multiple market conditions)  
**Why:** Single entry reason = relies on one market pattern

```
Good:
- "UPTREND DIP: 1h RSI strong, 5m RSI dipped": 60%
- Other regimes: 40%
→ Diversified

Bad:
- "UPTREND DIP": 99%
→ Only works in one condition
```

**Endpoint:** `/api/parameters/entry-reasons`

**Shows:**
- Distribution of entry reason types
- Count for each reason
- Percentage of total entries
- Most common entry reason

---

## 🎯 Dashboard Access

### URL
```
http://localhost:8001/api/parameters/dashboard
```

### Features
- **Real-time updates** every 10 seconds
- **6 parameter cards** with health status
- **System health check** showing overall state
- **Exit/Entry tables** with full breakdown
- **Smart alerts** highlighting issues
- **Visual indicators** (green/yellow/red)

### Interpretation Guide

| Parameter | Red 🔴 | Yellow 🟡 | Green 🟢 |
|-----------|-------|----------|---------|
| **Trend Filter** | <20% | 20-40% | ≥50% |
| **Signals** | <5/hr | 5-20/hr | 20+/hr |
| **Stops** | Not hitting | Avg loss >-0.6% | Avg loss -0.4% to -0.5% |
| **Targets** | <5 hits | 5-15 hits | 15+ hits |
| **Win Rate** | <30% | 30-45% | ≥45% |
| **Exit Dist** | 80% stops | 50-80% stops | <50% stops |
| **Entry Variety** | One reason | Few reasons | Multiple reasons |

---

## 📡 API Endpoints

### Summary (All 6 Parameters)
```bash
curl http://localhost:8001/api/parameters/summary
```

Returns complete parameter state in one call.

### Individual Parameters
```bash
# Trend filter monitoring
curl http://localhost:8001/api/parameters/trend-filter?minutes=60

# Signal quality
curl http://localhost:8001/api/parameters/signals?minutes=60

# Stop loss effectiveness
curl http://localhost:8001/api/parameters/stops?minutes=120

# Profit target effectiveness
curl http://localhost:8001/api/parameters/targets?minutes=120

# Exit reason distribution
curl http://localhost:8001/api/parameters/exit-reasons?minutes=120

# Entry reason distribution
curl http://localhost:8001/api/parameters/entry-reasons
```

### Health Check
```bash
curl http://localhost:8001/api/parameters/health-check
```

Quick status: 🟢 HEALTHY | 🟡 CAUTION | 🔴 CRITICAL

---

## 🔧 How Parameters Are Collected

### Signal Recording (entry_rsi_oversold.py)
```python
# When signal generated
param_monitor.record_signal(
    symbol="BTCUSDT",
    regime="oversold",
    rsi_1h=65.0,
    rsi_5m=35.0,
    trend_filter_passed=(rsi_1h > 50),  # ← Trend filter check
    signal_strength=75,
    entry_reason="UPTREND DIP: 1h RSI 65 strong, 5m RSI 35 dipped"
)

param_monitor.record_entry_reason(reason)
```

### Exit Recording (exit.py)
```python
# When position closed
param_monitor.record_exit(
    symbol="BTCUSDT",
    exit_reason="Profit target",  # or "Stop loss" or "10-minute timeout"
    entry_price=63000.0,
    exit_price=64260.0,
    realized_pnl=1200.0,
    realized_pnl_pct=1.9,
    hold_seconds=850
)
```

---

## 🚨 Alerts & Interpretation

### Trend Filter Alert
```
🔴 CRITICAL: Trend filter <20%
→ Market not trending
→ Too many false signals
→ Solution: Wait for 1h RSI to break above 50
```

### Signal Quality Alert
```
🔴 CRITICAL: Signal strength <40
→ Signals are weak and unreliable
→ Entry conditions not confident
→ Solution: Tighten RSI dip range (20-30 instead of 20-40)
```

### Win Rate Alert
```
🔴 CRITICAL: Win rate 20% (10 wins / 40 stops)
→ Strategy losing, more stops than wins
→ Entry logic broken
→ Solution: Check entry_reason in logs, adjust trend filter
```

### Stop Loss Alert
```
⚠️ WARNING: Avg stop loss -0.6% (worse than -0.5% target)
→ Stops hitting harder than expected
→ Possible slippage or premature entry
→ Solution: Look at exact prices when stops hit
```

---

## 📈 Real-World Example

### Scenario: Today's Trading Session

```
Trend Filter: 🟡 YELLOW (45% pass rate)
→ Market is chopping, some uptrends with downtrend noise

Signals: 🟢 GREEN (35 signals/hour, avg strength 62)
→ Good generation rate, decent confidence

Stops: 🟡 YELLOW (5 hits, avg loss -0.48%)
→ Working as intended, close to target

Targets: 🟡 YELLOW (3 hits, avg win +1.8%)
→ Hitting 60% as often as stops
→ Total: 3 wins, 5 losses = 37.5% win rate ⚠️ LOW

Exit Reasons:
- "Profit target": 3 (avg +1.8%)
- "Stop loss": 5 (avg -0.47%)
- "10-min timeout": 0

Entry Reasons:
- "UPTREND DIP": 8 entries (100%)

ALERT: Win rate 37.5% is below 45% target
→ Check: Are entries happening too close to 1h RSI = 50 threshold?
→ Solution: Raise trend filter to 1h RSI > 55
```

---

## 🎓 Using Parameters to Debug Trading

### Problem: "Low win rate (30%)"

**Check in order:**
1. **Trend Filter** — Are we entering in downtrends?
   - If <30% pass rate → YES, wait for uptrends
2. **Signal Quality** — Is average strength >60?
   - If <50 → Weak signals, tighten entry conditions
3. **Entry Reasons** — Are we only using one entry type?
   - If 100% same reason → Limited to one market condition
4. **Stop Losses** — Are stops worse than -0.5%?
   - If yes → Premature entries, need better timing

**Example Fix:**
```
Before: Trend filter 40%, Signal strength 45, Stops -0.6%
→ Raise trend filter to 1h RSI > 55
→ Require signal strength ≥70
→ Tighter RSI dip range (20-35 instead of 20-40)

After: Trend filter 60%, Signal strength 72, Stops -0.48%
→ Win rate improves from 30% to 50%
```

---

## 📍 Integration with Trading System

### Files Modified
- `backend/core/parameter_monitor.py` — Parameter collection engine
- `backend/api/routers/parameter_monitoring.py` — API endpoints
- `backend/trading/autonomous_trader/entry_rsi_oversold.py` — Signal recording
- `backend/trading/autonomous_trader/exit.py` — Exit recording
- `frontend/parameter_monitor_dashboard.html` — Real-time dashboard
- `backend/api/main.py` — Router registration

### Data Flow
```
Trading System
    ↓
record_signal() → parameter_monitor
record_exit() → parameter_monitor
    ↓
/api/parameters/summary (JSON)
    ↓
Dashboard (HTML)
    ↓
User sees: 🟢 HEALTHY | 🟡 CAUTION | 🔴 CRITICAL
```

---

## 🎯 Success Criteria

**Ideal State:**
```
Trend Filter:      🟢 ≥50% (strong uptrends)
Signals:           🟢 20+/hour, strength ≥65
Stops:             🟢 Avg loss -0.4% to -0.5%
Targets:           🟢 ≥15 hits/2hr (same rate as stops)
Exit Reasons:      🟢 ~50% profits, ~40% losses
Entry Variety:     🟢 Multiple entry reasons
Overall:           🟢 HEALTHY (>50% win rate)
```

**Crisis State:**
```
Trend Filter:      🔴 <20% (downtrending)
Signals:           🔴 <5/hour or strength <40
Stops:             🔴 Not protecting
Targets:           🔴 Rarely hit
Exit Reasons:      🔴 >80% stop losses
Overall:           🔴 CRITICAL (<30% win rate)
```

---

## 🔄 Usage Workflow

### Daily Check
1. Open dashboard: `http://localhost:8001/api/parameters/dashboard`
2. Look at overall status (🟢/🟡/🔴)
3. If yellow/red, check which parameters are affected
4. Review alerts section for recommendations
5. Adjust trading parameters if needed

### After Seeing Low Win Rate
1. Note the time it happened
2. Check Trend Filter — too many signal rejects?
3. Check Entry Reasons — relying on single pattern?
4. Check Exit Reasons — more stops than targets?
5. Adjust one parameter at a time, re-test

### Weekly Review
1. Export last 7 days of parameter data
2. Identify trending issues (e.g., "trend filter always <30%")
3. Plan parameter changes for next week
4. Document what changed and why

---

## Conclusion

These 6 parameters give you complete visibility into:

✅ **Is market trending?** → Trend Filter  
✅ **Are signals good?** → Signals + Entry Reasons  
✅ **Is risk protection working?** → Stops  
✅ **Are profits being taken?** → Targets  
✅ **Why are we exiting?** → Exit Reasons  
✅ **Are we diversified?** → Entry Variety  

**Monitor them constantly. Adjust quickly. Trade profitably.**
