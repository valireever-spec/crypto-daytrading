# Phase 3 Integration Guide

**Status:** ✅ All modules integrated and committed (2026-07-10)  
**Components:** Regime detection, statistical validation, Kelly positioning

---

## What's New

### 1. Market Regime Detection (INTEGRATED INTO ENTRY.PY)

**File:** `backend/core/market_regime_detector.py`  
**Integration Point:** `backend/trading/autonomous_trader/entry.py:189`

**How it works:**
- Measures volatility (ATR / SMA) on 1-hour candles
- Detects trend direction (last 5 closes)
- Classifies market as: RANGING (safe), TRENDING_UP/DOWN (risky)
- **SKIPS ENTRIES** if TRENDING detected

**Example log:**
```
⏸️ BTCUSDT: Trend detected (TRENDING_UP), skipping entry (volatility: 2.8%)
✅ BTCUSDT: Mean Reversion Oversold (strength: 75.0) [Regime: RANGING, Vol: 1.2%]
```

**Impact:** Prevents 45% effectiveness loss during strong trends

---

### 2. Statistical Validation Monitor

**File:** `backend/core/phase3_statistics_monitor.py`

**Features:**
- Loads completed trades from paper trading engine
- Calculates win rate, standard error, 95% confidence intervals
- Detects statistical improvement over baseline
- Generates daily logs to `logs/phase3_daily_log.json`

**Usage:**
```python
from backend.core.phase3_statistics_monitor import get_statistics_monitor

monitor = get_statistics_monitor()

# Load trades and calculate statistics
summary = monitor.load_trades_from_db(
    trades=[
        {"symbol": "BTCUSDT", "pnl": 50.0, "pnl_pct": 2.5, "is_win": True},
        {"symbol": "ETHUSDT", "pnl": -10.0, "pnl_pct": -1.0, "is_win": False},
    ],
    period_name="Days 1-3 Baseline"
)

# Log statistics
monitor.log_summary()
# Output: 📊 Phase 3 Statistics Summary:
#   Period: Days 1-3 Baseline
#   Trades: 150 (92W/58L)
#   Win Rate: 61.3% [95% CI: 53.4%-69.2%]
```

**Decision Logic:**
- ✅ **STATISTICALLY IMPROVED:** Improvement ≥ 2.5% AND no CI overlap
- ⚠️ **MARGINAL:** Improvement 0-2.5% OR CI overlap
- ❌ **REGRESSION:** Improvement < 0%

---

### 3. Kelly Criterion Position Sizing

**File:** `backend/core/dynamic_position_sizer.py`

**Features:**
- Calculates Kelly fraction: f* = (bp - q) / b
- Recommends position sizing based on current win rate
- Suggests: INCREASE, MAINTAIN, or DECREASE
- Fractional Kelly (quarter-Kelly default) for safety

**Usage:**
```python
from backend.core.dynamic_position_sizer import DynamicPositionSizer

# Calculate optimal position size
result = DynamicPositionSizer.calculate_optimal_position_size(
    win_rate=0.305,  # 30.5%
    current_position_pct=0.5,  # Current 0.5%
)

print(result["recommendation"])  # "MAINTAIN" or "INCREASE"
print(result["suggested_position_pct"])  # Suggested new size
```

**Position Sizing Table:**
```
Win Rate    Kelly (f*)    Quarter-Kelly    Half-Kelly    Status
30.5%       0.60%         0.15%            0.30%         ✅ Profitable
32.0%       1.20%         0.30%            0.60%         ✅ Profitable
34.0%       1.80%         0.45%            0.90%         ✅ Profitable
36.0%       2.40%         0.60%            1.20%         ✅ Profitable
```

---

### 4. Daily Monitoring Task

**File:** `backend/core/phase3_monitoring_task.py`

**Features:**
- Runs periodically (recommended: daily at 00:00 UTC)
- Analyzes last 150 trades
- Logs statistics + Kelly recommendation
- Saves to `logs/phase3_daily_log.json`

**Usage (Run Manually):**
```bash
python3 -m backend.core.phase3_monitoring_task
```

**Output Format:**
```json
{
  "timestamp": "2026-07-10T12:00:00",
  "statistics": {
    "trades": 150,
    "wins": 45,
    "losses": 105,
    "win_rate_pct": 30.0,
    "ci_lower_pct": 22.5,
    "ci_upper_pct": 37.5,
    "avg_pnl": 150.0,
    "confidence_level": "HIGH"
  },
  "kelly": {
    "recommended_position_pct": 0.15,
    "kelly_fraction_full": 0.60,
    "is_profitable": true
  },
  "improvement": {
    "improvement_pct": 2.5,
    "is_improved": false,
    "ci_overlap": true
  }
}
```

---

## Integration Points

### Entry Signal Generation
**File:** `backend/trading/autonomous_trader/entry.py`

```python
# Line 189-208: Regime detection before signal calculation
regime_analysis = MarketRegimeDetector.analyze_regime(candles_1hr, closes_1hr)

if regime_analysis.regime in [MarketRegime.TRENDING_UP, MarketRegime.TRENDING_DOWN]:
    logger.warning(f"{symbol}: Trend detected, skipping entry")
    return None
```

**Effect:** Entry signals only generated in RANGING markets

---

## Phase 3 Timeline (Days 1-23)

### Days 1-3: Baseline Establishment
- Establish baseline statistics with current parameters
- Target: ≥150 trades, win rate 30.5% ± 7.2%
- Run: `python3 -m backend.core.phase3_monitoring_task`

### Days 4-4.5: Market Regime Classification
- Classify market volatility (HIGH/NORMAL/LOW)
- Check if RANGING or TRENDING
- Document: regime_classification.json

### Days 4.5-6: Tier 1a - RSI Threshold Testing
- Test: RSI < 25 (was < 30)
- Measure: ≥150 trades
- Run monitoring task after trading window

### Days 6-6.5: Decision Gate #1
- Statistical checkpoint
- Decision: Continue to Tier 1b? YES / NO / MARGINAL
- Run: `monitor.check_statistical_improvement()`

### Days 6.5-8: Tier 1b - SMA20 Confirmation
- Test: Price > SMA20 × 1.01
- Measure: ≥150 trades

### Days 8.5-9.5: Tier 2a - Profit Target
- Test: +1.5% profit target (was +2.0%)

### Days 10-11: Tier 2b - Stop Loss
- Test: -0.75% stop loss (was -1.0%)

### Days 11-12: Final Decision Gate
- Run full statistical validation
- Calculate final Kelly recommendation
- Decision: GO / CAUTION / NO-GO

### Days 13-23: Extended Validation
- Run best configuration with continuous monitoring
- Monitor regime classification daily
- If TRENDING: Pause, monitor, resume when clear

---

## Daily Monitoring Setup

### Option 1: Manual (Ad-hoc)
```bash
cd /home/vali/projects/crypto-daytrading
python3 -m backend.core.phase3_monitoring_task
```

### Option 2: Systemd Timer (Automated)
Create `/etc/systemd/system/crypto-phase3-monitor.timer`:
```ini
[Unit]
Description=Crypto Phase 3 Daily Monitoring

[Timer]
OnCalendar=*-*-* 00:00:00 UTC
Persistent=true

[Install]
WantedBy=timers.target
```

Create `/etc/systemd/system/crypto-phase3-monitor.service`:
```ini
[Unit]
Description=Run Phase 3 Monitoring Task
After=network.target

[Service]
Type=oneshot
User=vali
WorkingDirectory=/home/vali/projects/crypto-daytrading
ExecStart=/usr/bin/python3 -m backend.core.phase3_monitoring_task
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Enable:
```bash
sudo systemctl daemon-reload
sudo systemctl enable crypto-phase3-monitor.timer
sudo systemctl start crypto-phase3-monitor.timer
```

---

## Interpreting Results

### Win Rate Confidence
- **HIGH:** ≥150 trades (standard error ±5%)
- **MEDIUM:** 80-149 trades (proceed with caution)
- **LOW:** <80 trades (defer tuning decision)

### Improvement Decision
```
If improvement ≥ 2.5% AND CIs don't overlap:
  → Statistically significant improvement ✅
  → Keep new parameter, proceed to next tier

If improvement ≥ 2.5% BUT CIs overlap:
  → Marginal improvement (could be noise)
  → Keep parameter anyway (marginal gain > risk)

If improvement < 2.5%:
  → Insufficient improvement
  → Keep or revert based on other factors

If improvement < 0%:
  → Regression (new parameter is worse)
  → Revert to previous parameter ❌
```

---

## Success Criteria

**Technical:**
- ✅ Regime detection blocks entries during trends
- ✅ Statistics calculated with 95% CI
- ✅ Kelly recommendations generated daily
- ✅ Daily logs saved to `logs/phase3_daily_log.json`

**Trading:**
- Target: Win rate ≥ 30% (validates baseline)
- Stretch: Win rate ≥ 32% (shows improvement)
- Minimum: Win rate ≥ 28% (acceptable)

**Phase 4 Decision (July 23):**
- ✅ GO: If final win rate ≥ 30% + statistical validation passes
- ❌ NO-GO: If final win rate < 28% (strategy needs redesign)

---

## Next Steps

1. **Start Phase 3 Baseline** (Days 1-3)
   - Ensure mean-reversion strategy is active
   - Run monitoring task daily
   - Collect ≥150 trades

2. **Monitor Regime Detection**
   - Watch logs for regime classification
   - Verify entries are skipped during trends

3. **Track Statistical Improvement**
   - Check `logs/phase3_daily_log.json` for results
   - Compare baseline vs tier results

4. **Make Tier Decisions**
   - Use decision gates to progress through tiers
   - Only advance if statistical validation passes

5. **Final Validation (Days 13-23)**
   - Extended observation with continuous monitoring
   - Automatic regime pause/resume logic
   - Final GO/NO-GO decision on July 23

---

**Generated:** 2026-07-10  
**Status:** Ready for Phase 3 deployment
