# Data Quality Measurement Framework

**Purpose:** Define and measure data quality before trading  
**Status:** Framework proposed, NOT YET IMPLEMENTED  
**Priority:** CRITICAL (should be Pillar #3, before Order Execution)

---

## Data Quality Scorecard

### Dimension 1: Price Sanity (Per Symbol)

**Metric 1.1: Price Change Bounds**
```
Rule: Reject if price changes >20% in 1 minute (crypto can move fast, but not THAT fast)

Example:
  Previous price: €61,500
  Current price: €61,800
  Change: +0.49% ✅ PASS

  Previous price: €61,500
  Current price: €30,000  
  Change: -51% ❌ REJECT (likely data error)
```

**Implementation:**
```python
def validate_price_bounds(symbol: str, prev_price: float, current_price: float) -> bool:
    """Validate price doesn't jump >20% (unrealistic for 1-min candle)."""
    if not prev_price or prev_price <= 0:
        return True  # First data point, accept
    
    pct_change = abs((current_price - prev_price) / prev_price * 100)
    MAX_1MIN_CHANGE = 20.0  # 20% is extremely high for 1 minute
    
    if pct_change > MAX_1MIN_CHANGE:
        logger.warning(f"{symbol}: Price spike rejected: {prev_price} → {current_price} ({pct_change:.1f}%)")
        return False
    return True
```

---

### Dimension 2: Data Completeness

**Metric 2.1: Symbol Coverage**
```
Rule: All required symbols must have fresh data

Example:
  BTCUSDT: ✅ Fresh (2 sec old)
  ETHUSDT: ✅ Fresh (1 sec old)
  BNBUSDT: ✅ Fresh (3 sec old)
  → Score: 100% (3/3 symbols covered)

  BTCUSDT: ✅ Fresh
  ETHUSDT: ✅ Fresh
  BNBUSDT: ❌ Missing (data never arrived)
  → Score: 67% (2/3 symbols) → SKIP TRADING
```

**Implementation:**
```python
def measure_symbol_coverage(prices: Dict[str, float], required_symbols: List[str]) -> float:
    """Percentage of symbols with data."""
    if not required_symbols:
        return 100.0
    coverage = len(prices) / len(required_symbols) * 100
    if coverage < 100:
        logger.warning(f"Incomplete symbol coverage: {coverage:.0f}%")
    return coverage
```

---

### Dimension 3: Data Consistency

**Metric 3.1: WebSocket Connectivity**
```
Rule: WebSocket must be connected and actively receiving data

Checks:
  ✅ is_connected = true
  ✅ received data in last 5 seconds (not stuck)
  ✅ no reconnection attempts in last 60 seconds
  → Score: 100% → Trade

  ✅ is_connected = true
  ❌ last data > 10 seconds ago (stuck)
  ❌ 3 reconnection attempts (unstable)
  → Score: 20% → SKIP TRADING
```

**Implementation:**
```python
def measure_websocket_health(client: BinanceStreamClient) -> Dict[str, float]:
    """Measure WebSocket health score."""
    scores = {
        "connected": 100.0 if client.is_connected else 0.0,
        "stable": max(0, 100 - (client.reconnect_attempts * 20)),  # Deduct 20 per attempt
        "active": 100.0 if (now - client.last_update).total_seconds() < 5 else 0.0
    }
    overall_health = sum(scores.values()) / len(scores)
    return {"scores": scores, "overall": overall_health}
```

---

### Dimension 4: Data Age Distribution

**Metric 4.1: Age Variance**
```
Rule: All symbols should have similar age (not 1 sec and 100 sec)

Example (GOOD):
  BTCUSDT: 2 sec old
  ETHUSDT: 1 sec old
  BNBUSDT: 3 sec old
  Max variance: 2 seconds → ✅ PASS

Example (BAD):
  BTCUSDT: 2 sec old
  ETHUSDT: 1 sec old
  BNBUSDT: 120 sec old (WebSocket missed it)
  Max variance: 119 seconds → ❌ FAIL
```

**Implementation:**
```python
def measure_age_variance(last_updates: Dict[str, datetime], now: datetime) -> float:
    """Check if all prices are similarly fresh."""
    ages = [(now - ts).total_seconds() for ts in last_updates.values()]
    if not ages:
        return 0.0
    
    max_age = max(ages)
    min_age = min(ages)
    variance = max_age - min_age
    
    MAX_ACCEPTABLE_VARIANCE = 5.0  # 5 sec spread is OK
    if variance > MAX_ACCEPTABLE_VARIANCE:
        logger.warning(f"Price age variance too high: {variance:.1f}s (max {max_age:.1f}s)")
        return 0.0
    return 100.0
```

---

### Dimension 5: Volume Validation

**Metric 5.1: Zero Volume Detection**
```
Rule: Warn if a symbol has 0 volume (market might be dead)

Example:
  BTCUSDT: Volume 1.2M ✅ Active
  ETHUSDT: Volume 500K ✅ Active
  BNBUSDT: Volume 0 ❌ No trades happening

Detection: Check candle volume, warn if zero
```

**Implementation:**
```python
def validate_volume(symbol: str, volume: float) -> bool:
    """Check if volume is reasonable."""
    if volume <= 0:
        logger.warning(f"{symbol}: Zero volume detected, market may be dead")
        return False
    return True
```

---

### Dimension 6: Volatility Reasonableness

**Metric 6.1: Volatility Spike**
```
Rule: Warn if volatility suddenly 10x higher (market regime change or data error)

Example:
  BTCUSDT 20-day vol: 2.1%
  Current 1-min vol: 2.3% ✅ Normal
  
  BTCUSDT 20-day vol: 2.1%
  Current 1-min vol: 45.0% ❌ 20x spike (error or flash crash)
```

**Implementation:**
```python
def detect_volatility_spike(symbol: str, historical_vol: float, current_vol: float) -> bool:
    """Check if current volatility is unreasonably high."""
    if historical_vol <= 0:
        return True  # Can't check without baseline
    
    vol_ratio = current_vol / historical_vol
    MAX_RATIO = 10.0  # 10x historical vol = suspicious
    
    if vol_ratio > MAX_RATIO:
        logger.warning(f"{symbol}: Volatility spike {vol_ratio:.1f}x (possible data error or flash crash)")
        return False
    return True
```

---

## Overall Data Quality Score

**Formula:**
```
Overall Score = (
  Price Sanity (25%) +
  Symbol Coverage (25%) +
  WebSocket Health (25%) +
  Age Variance (15%) +
  Volume Validity (5%) +
  Volatility Reasonableness (5%)
) / 100
```

**Trading Gate:**
```
Score >= 90% → TRADE ✅
Score 70-89% → TRADE WITH CAUTION ⚠️
Score < 70% → SKIP TRADING ❌
```

---

## Example: Real Data Quality Audit

**Scenario 1: Normal Market**
```
Time: 2026-06-25 10:30:00 UTC
Symbols: BTCUSDT, ETHUSDT, BNBUSDT

BTCUSDT:
  Price: €61,758 (prev: €61,740) → ✅ +0.03% (normal)
  Age: 2 sec → ✅ Fresh
  Volume: 1.2M → ✅ Active
  Vol spike: 2.1% vs 20-day 2.0% → ✅ 1.05x (normal)

ETHUSDT:
  Price: €1,648 (prev: €1,647) → ✅ +0.06% (normal)
  Age: 1 sec → ✅ Fresh
  Volume: 500K → ✅ Active
  Vol spike: 2.3% vs 20-day 2.1% → ✅ 1.10x (normal)

BNBUSDT:
  Price: €571.7 (prev: €571.5) → ✅ +0.04% (normal)
  Age: 3 sec → ✅ Fresh
  Volume: 300K → ✅ Active
  Vol spike: 1.9% vs 20-day 1.8% → ✅ 1.06x (normal)

Price Sanity: 100% (all within bounds)
Symbol Coverage: 100% (3/3)
WebSocket Health: 100% (connected, stable, active)
Age Variance: 2 sec (max 3, min 1) → ✅ 100%
Volume Validity: 100% (all >0)
Volatility: 100% (all <2x historical)

OVERALL SCORE: 100% ✅ TRADE
```

**Scenario 2: Data Error**
```
Time: 2026-06-25 10:35:00 UTC

BTCUSDT:
  Price: €30,000 (prev: €61,740) → ❌ -51.4% (REJECT)
  Age: 2 sec (fresh) → ✅
  Volume: 1.2M → ✅
  
ETHUSDT:
  Price: €1,648 (normal) → ✅
  Age: 121 sec (STALE) → ❌
  
BNBUSDT:
  Price: €571.7 (normal) → ✅
  Age: 2 sec → ✅
  Volume: 0 (DEAD) → ❌

Price Sanity: 67% (2/3 pass, BTC fails)
Symbol Coverage: 67% (ETHUSDT too old, counted as missing)
WebSocket Health: 60% (one symbol 2 min old)
Age Variance: 119 sec (max 121, min 2) → ❌ 0%
Volume Validity: 67% (BNB has 0 volume)
Volatility: Can't measure (BTC price error)

OVERALL SCORE: 32% ❌ SKIP TRADING
```

---

## Implementation Priority

**Must implement before Phase 2 live trading:**

1. **Price Sanity Bounds** (20% max 1-min change)
   - Effort: 30 min
   - Risk: CRITICAL (prevents data errors)

2. **Symbol Coverage** (all symbols must have data)
   - Effort: 15 min
   - Risk: LOW (already check, just formalize)

3. **WebSocket Health** (connected + active)
   - Effort: 30 min
   - Risk: LOW (already tracked, just measure)

4. **Overall Score Gate** (require >90% before trade)
   - Effort: 30 min
   - Risk: LOW (just a calculation + gate)

**Total effort: ~2 hours**

---

## Success Criteria

**Phase 1 (Now):**
- ✅ Understand what data quality means
- ✅ Identify gaps (price sanity, outliers, etc.)

**Phase 2 (2026-07-15):**
- ✅ Implement all 4 data quality dimensions
- ✅ Require ≥90% score before trading
- ✅ Log all data quality scores
- ✅ Reject trades on low-quality data

**Result:** System refuses to trade on bad data, even if fresh and signal-valid

---

**Status:** FRAMEWORK PROPOSED, NOT YET IMPLEMENTED  
**Should be:** Pillar #3 (before Order Execution validation)  
**Current Pillar #3:** Order Execution (out of order)  
**Recommended Reorder:**
1. Data Freshness ✅
2. Signal Validation ✅
3. **Data Quality Score** ← MOVE HERE
4. Order Execution
5. Risk Enforcement
6. State Persistence
7. Failover Health
8. Logging Fidelity
