# Critical Pillars Hardening Framework

**Purpose:** Defensive hardening of 7 critical system pillars before Phase 1 completion  
**Status:** 2/7 COMPLETE (Data Freshness, Signal Validation)  
**Target Completion:** 2026-07-01 (before Phase 1 ends)  
**Philosophy:** Fail safely, log loudly, never trade on bad data

---

## Hardening Progress

| # | Pillar | Status | Commit | Lines | Risk |
|---|--------|--------|--------|-------|------|
| 1 | Data Freshness Gate | ✅ DONE | ae019f1 | 50 | CRITICAL |
| 2 | Signal Validation | ✅ DONE | ae019f1 | 28 | CRITICAL |
| 3 | Order Execution | 🔧 TODO | — | est 40 | HIGH |
| 4 | Risk Enforcement | 🔧 TODO | — | est 30 | HIGH |
| 5 | State Persistence | 🔧 TODO | — | est 80 | CRITICAL |
| 6 | Failover Health | 🔧 TODO | — | est 40 | HIGH |
| 7 | Logging Fidelity | 🔧 TODO | — | est 60 | MEDIUM |

---

## PILLAR #1: Data Freshness Gate (G-011) ✅ COMPLETE

**What was hardened:**
- Added `get_prices_fresh()` to reject stale prices
- Max age: 5 seconds per symbol
- Validates WebSocket connected before trading
- Logs all rejected prices

**Files changed:**
- `backend/exchange/binance_stream.py` (+50 lines)
- `backend/trading/autonomous_trader.py` (+28 lines)

**How it works:**
```python
# Before: Returned any cached price, even if 30+ min old
prices = client.get_prices(symbols)  # ❌ No age check

# After: Rejects prices older than 5 seconds
prices = client.get_prices_fresh(symbols, max_age_seconds=5)  # ✅ Age validated
if len(prices) < len(symbols):
    logger.warning(f"Insufficient fresh prices, skipping trading")
    return {}  # Skip this iteration
```

**Impact:**
- **Before:** Could trade with data 30+ minutes old → hidden slippage risk
- **After:** Rejects all prices > 5 seconds old → prevents stale data trading

**Test:**
```bash
# Check that WebSocket is connected and prices fresh
curl -s http://localhost:8001/api/autonomous/status | jq '.running'
# Verify logs show price freshness checks
tail -50 logs/api_server.log | grep "price.*age\|freshness\|stale"
```

---

## PILLAR #2: Signal Validation ✅ COMPLETE

**What was hardened:**
- Validates signal score is numeric, not NaN/Inf
- Validates range [0-100]
- Validates all component scores are numeric
- Rejects malformed signals before execution

**Files changed:**
- `backend/trading/autonomous_trader.py` (+28 lines)

**How it works:**
```python
# Before: Could trade on NaN or invalid signals
signal_score = 45.5  # or math.nan, or 150, etc.
# → Trade placed without validation ❌

# After: Validates before trading
if math.isnan(signal_score) or math.isinf(signal_score):
    logger.error(f"Invalid signal {signal_score}, skipping")
    return None
if signal_score < 0 or signal_score > 100:
    logger.error(f"Out of range {signal_score}, skipping")
    return None
# All validations passed → proceed to trade ✅
```

**Impact:**
- **Before:** Could trade on garbage signal scores
- **After:** All signals validated before execution, bad signals logged

**Test:**
```bash
# Check signal validation is active
tail -100 logs/api_server.log | grep "Invalid signal\|Out of range"
# Should see 0 such errors (signals valid)
```

---

## PILLAR #3: Order Execution Validation 🔧 TODO

**What needs hardening:**
- Verify orders actually fill completely
- Reject partial fills (don't scale, it's risky)
- Log discrepancies between requested and filled qty
- Add timeout for pending orders

**Implementation plan:**
```python
# In paper_trading.py place_order():
# 1. Verify fill_quantity == requested_quantity
if fill_quantity < requested_quantity:
    logger.error(f"Partial fill: {fill_quantity}/{requested_quantity}")
    # Option: Cancel remaining, or retry
    return {"status": "PARTIAL", "filled": fill_quantity, ...}

# 2. Verify fill_price is within slippage bounds
expected_min = current_price * (1 - SLIPPAGE - 0.001)  # Add 0.1% buffer
expected_max = current_price * (1 + SLIPPAGE + 0.001)
if not (expected_min < fill_price < expected_max):
    logger.warning(f"Unexpected slippage: {fill_price} vs {current_price}")

# 3. Log all fills with comparison
logger.info(f"ORDER_FILLED", extra={"extra_fields": {
    "requested_qty": requested_quantity,
    "filled_qty": fill_quantity,
    "requested_price": current_price,
    "fill_price": fill_price,
    "slippage_pct": (fill_price - current_price) / current_price * 100
}})
```

**Estimated effort:** 30-40 minutes  
**Risk:** Low (paper trading, logged)  
**Benefit:** Prevents position size mismatches, catches Binance anomalies

---

## PILLAR #4: Risk Enforcement Double-Check 🔧 TODO

**What needs hardening:**
- Double-verify daily loss limit before EACH trade
- Check if position size would exceed limit
- Validate available cash
- Prevent edge-case bypasses

**Implementation plan:**
```python
# In smart_executor.py before placing order:
# 1. Check daily loss limit (already done, but verify again)
daily_pnl = engine.get_account_state()['daily_pnl']
if daily_pnl < -MAX_DAILY_LOSS:
    logger.critical("Daily loss limit would be exceeded, order REJECTED")
    return {"status": "REJECTED", "reason": "daily_loss_limit"}

# 2. Check if NEW trade could push us over limit
worst_case_loss = position_size * WORST_CASE_SLIPPAGE * 2  # 2x for stop loss
projected_pnl = daily_pnl - worst_case_loss
if projected_pnl < -MAX_DAILY_LOSS:
    logger.critical(f"Trade could breach limit: {daily_pnl} - {worst_case_loss} = {projected_pnl}")
    return {"status": "REJECTED", "reason": "exceeds_daily_limit"}

# 3. Validate available cash
position_cost = quantity * current_price
if position_cost > available_cash:
    logger.error(f"Insufficient cash: need {position_cost}, have {available_cash}")
    return {"status": "REJECTED", "reason": "insufficient_cash"}

logger.info("RISK_VALIDATION_PASSED", extra={"extra_fields": {
    "daily_pnl_before": daily_pnl,
    "position_size": position_cost,
    "projected_worst_case": projected_pnl,
    "max_daily_loss": MAX_DAILY_LOSS
}})
```

**Estimated effort:** 20-30 minutes  
**Risk:** Low (defensive only)  
**Benefit:** Prevents daily loss limit bypass, forces conscious risk decisions

---

## PILLAR #5: State Persistence (G-001) 🔧 TODO

**What needs hardening:**
- Save position state to SQLite before each trade
- Restore state on startup
- Prevent orphaned positions on crash

**Implementation plan:**
```python
# 1. Create positions table in SQLite
CREATE TABLE open_positions (
    id INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL,
    quantity REAL NOT NULL,
    entry_price REAL NOT NULL,
    entry_time TIMESTAMP NOT NULL,
    status TEXT DEFAULT 'OPEN',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)

# 2. On position entry, save to DB
await db.insert_position({
    "symbol": "BTCUSDT",
    "quantity": 0.5,
    "entry_price": 61758.0,
    "entry_time": datetime.utcnow()
})

# 3. On position exit, mark as CLOSED in DB
await db.update_position(position_id, status='CLOSED')

# 4. On startup, restore positions
positions = db.query("SELECT * FROM open_positions WHERE status='OPEN'")
for pos in positions:
    logger.info(f"Restored position from crash: {pos['symbol']} {pos['quantity']}")
    # Re-sync with Binance to verify position still exists
```

**Estimated effort:** 1-2 hours (DB setup + restore logic)  
**Risk:** Medium (DB corruption possible, but SQLite robust)  
**Benefit:** CRITICAL - prevents data loss on crash

**Files to create/modify:**
- `backend/core/database.py` (new)
- `backend/exchange/paper_trading.py` (add persistence)
- `backend/api/main.py` (restore on startup)

---

## PILLAR #6: Failover Health Check 🔧 TODO

**What needs hardening:**
- Health check before backup takeover
- Verify backup config is in sync
- Prevent silent failover bugs
- Log all failover transitions

**Implementation plan:**
```python
# In failover_monitor.py before triggering failover:
# 1. Verify primary is truly down
async def is_primary_healthy():
    try:
        response = await http_client.get(
            f"http://{PRIMARY_URL}/api/health",
            timeout=2
        )
        return response.status_code == 200
    except:
        return False

# 2. Verify backup can connect to DB
async def is_backup_ready():
    try:
        # Test DB connection
        db.query("SELECT 1")
        return True
    except:
        return False

# 3. Verify configs match
async def is_config_in_sync():
    primary_config = await http_client.get(f"{PRIMARY_URL}/api/autonomous/config")
    backup_config = await http_client.get(f"{BACKUP_URL}/api/autonomous/config")
    
    if primary_config['entry_threshold'] != backup_config['entry_threshold']:
        logger.error("Config mismatch! Primary and backup out of sync")
        return False
    return True

# 4. Only failover if ALL checks pass
if not (await is_primary_healthy()) and \
   (await is_backup_ready()) and \
   (await is_config_in_sync()):
    logger.critical("FAILOVER: Primary down, backup ready, configs synced → TAKEOVER")
    await backup.start_trading()
else:
    logger.critical("FAILOVER BLOCKED: Backup not ready or config mismatch")
    # Alert human operator
```

**Estimated effort:** 40-50 minutes  
**Risk:** Low (checks only, no trading changes)  
**Benefit:** Prevents silent failover bugs, ensures backup is actually ready

---

## PILLAR #7: Logging Fidelity 🔧 TODO

**What needs hardening:**
- Log every critical decision with full context
- Standardize log format (already done in JSON)
- Add decision ID for traceability
- Ensure logs are searchable

**Implementation plan:**
```python
# Every critical decision gets logged with:
# 1. Decision ID (uuid) for traceability
# 2. All input parameters
# 3. Decision output
# 4. Timestamp and actor

import uuid
decision_id = str(uuid.uuid4())

# Example: Entry signal decision
logger.info(f"ENTRY_DECISION", extra={"extra_fields": {
    "decision_id": decision_id,
    "symbol": "BTCUSDT",
    "signal_score": 62.5,
    "threshold": 60.0,
    "regime": "bull",
    "position_size": 500.0,
    "daily_pnl": 45.0,
    "decision": "ACCEPT",  # or "REJECT"
    "reason": "Signal score exceeded threshold in bull regime"
}})

# Make logs searchable by decision_id:
# grep "decision_id.*abc123" logs/api_server.log → trace full decision flow
```

**Estimated effort:** 30-40 minutes (add decision IDs throughout)  
**Risk:** Very low (logging only)  
**Benefit:** Enables debugging, audit trail

---

## Implementation Timeline

### Week 1 (2026-06-25 to 2026-07-01)
- ✅ Day 1: Pillars #1-2 DONE (commit ae019f1)
- 🔧 Day 2-3: Pillar #3 (Order Execution) → commit
- 🔧 Day 4: Pillar #4 (Risk Enforcement) → commit
- 🔧 Day 5: Pillar #5 (State Persistence) → commit

### Week 2 (2026-07-01 to 2026-07-05)
- 🔧 Day 6: Pillar #6 (Failover Health) → commit
- 🔧 Day 7: Pillar #7 (Logging Fidelity) → commit
- ✅ Day 8-10: Testing & validation

### Post Phase 1 (2026-07-05+)
- Integrate all 7 pillars with Phase 2 live trading
- Run 3-day paper test with all hardening enabled
- Deploy to live trading (€1,000)

---

## Testing Each Pillar

### Pillar #1: Data Freshness
```bash
# Simulate stale price
# Mock WebSocket to return old timestamp
# Verify bot skips trading
```

### Pillar #2: Signal Validation
```bash
# Return NaN, Inf, -50, 150 as signal scores
# Verify trades rejected, logged with error
```

### Pillar #3: Order Execution
```bash
# Simulate partial fill (qty 0.3 of 0.5)
# Verify logged, position size adjusted
```

### Pillar #4: Risk Enforcement
```bash
# Set daily P&L to -€499
# Try to place €300 position (would exceed limit)
# Verify rejected, logged
```

### Pillar #5: State Persistence
```bash
# Kill API process while position open
# Restart API
# Verify position restored from DB
```

### Pillar #6: Failover Health
```bash
# Kill primary machine
# Verify backup detects and verifies backup is ready
# Verify failover occurs only if all checks pass
```

### Pillar #7: Logging
```bash
# Generate 100 trades
# Search by decision_id: grep "decision_id.*abc" logs/api_server.log
# Verify full trace available
```

---

## Success Criteria

**All 7 pillars hardened = framework CANNOT:**
1. ❌ Trade with stale data (>5s old)
2. ❌ Trade on invalid signals (NaN/Inf/out-of-range)
3. ❌ Accept partial fills without logging
4. ❌ Bypass daily loss limits
5. ❌ Lose position state on crash
6. ❌ Failover silently without verification
7. ❌ Make decisions without full context logged

**Result:** Phase 1 → Phase 2 transition with confidence in system resilience

---

**Document Status:** FRAMEWORK READY  
**Last Updated:** 2026-06-25  
**Target Completion:** 2026-07-01  
**Pillars Complete:** 2/7 ✅
