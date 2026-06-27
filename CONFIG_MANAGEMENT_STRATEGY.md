# Configuration Management Strategy

**Status:** CRITICAL DESIGN ISSUE IDENTIFIED  
**Date:** 2026-06-26  
**Issue:** Operational parameters are hardcoded; not synced between primary/backup

---

## The Problem

### Current Architecture (UNSUSTAINABLE)

```
TRADING PARAMETERS (Synced via trading_config.json)
├── entry_threshold ✅ (synced)
├── exit_profit_target ✅ (synced)
├── max_positions ✅ (synced)
└── quality_gate_entry ✅ (synced)

OPERATIONAL PARAMETERS (Hardcoded, NOT synced)
├── WebSocket subscriptions ❌ (main.py line 208-213)
├── Price max_age (5s) ❌ (binance_stream.py)
├── Health check intervals ❌ (health_checker.py)
├── Restart limits (3 attempts) ❌ (systemd service)
├── Circuit breaker threshold ❌ (config.py)
└── Many others scattered across codebase ❌
```

### Why This Is Broken

| Scenario | Impact | Risk |
|----------|--------|------|
| **Add new symbol** | Must redeploy code to BOTH machines | Drift if backup misses update |
| **Change price freshness requirement** | Must redeploy + restart services | Downtime for both machines |
| **Adjust health check frequency** | Must redeploy + systemd reload | Inconsistent monitoring |
| **Tune safety gates** | Must redeploy code | Primary/backup diverge |
| **Update WebSocket subscriptions** | Must redeploy code | Data quality issues on backup |

**Current state:** If code changes only go to primary, backup becomes stale.

---

## Solution: Three-Tier Configuration

### Tier 1: CODE-LEVEL (Runtime, Deployed Once)
- Core algorithms (signal logic, risk management)
- Safety mechanisms (circuit breaker, validation)
- **Once deployed to both machines, stays stable**

### Tier 2: TRADING CONFIG (Runtime, Synced Every Change)
- `trading_config.json` (synced every request)
- Entry/exit thresholds, position sizing, symbols
- **Changes propagate to backup immediately**

### Tier 3: SYSTEM CONFIG (Runtime, Synced Every Change)
- `system_config.json` (synced like trading_config.json)
- WebSocket subscriptions, health check intervals, timeout values
- **Changes propagate to backup immediately**

---

## Implementation Plan

### Phase 1: Create System Config (DONE ✅)
- ✅ Created `system_config.json` with all operational parameters
- Defines: WebSocket subscriptions, safety gates, health check intervals

### Phase 2: Integrate System Config into Code (TODO)
- Load `system_config.json` on startup
- Use config values instead of hardcoded values
- Examples:
  ```python
  # Before (hardcoded)
  ws.subscribe("btcusdt@kline_1m", on_price_update)
  
  # After (from config)
  for subscription in load_system_config()['websocket']['subscriptions']:
      ws.subscribe(subscription, on_price_update)
  ```

### Phase 3: Sync System Config (TODO)
- Add `system_config.json` to backup sync mechanism
- Update `ConfigManager.sync_to_backup()` to sync both:
  - `trading_config.json` ✅ (already done)
  - `system_config.json` (new)
- Verify sync happens before API startup

### Phase 4: Validation (TODO)
- Test that changing WebSocket subscriptions in config → applied to both machines
- Test that changing health check interval → applied to both machines
- Audit startup logs to confirm config was loaded

---

## Configuration Hierarchy

```
PRIMARY MACHINE                      BACKUP MACHINE
     │                                    │
     └─→ Code (stable, deployed once)    │
         - Signal algorithms              │
         - Risk management                │
         - Safety gates (logic)           │
                 │                        │
                 ├─→ Synced via SSH ──────┘
                 │
     ├─ trading_config.json
     │  (entry_threshold, max_positions, symbols, etc.)
     │
     └─ system_config.json (NEW)
        (websocket, health checks, timeouts, etc.)
```

**Principle:** _Changes that affect trading behavior must be synced immediately; changes to core algorithms only happen on redeploy._

---

## Why This Is Sustainable

### Before (Current State)
```
Primary updated:  code changes → only on primary
Backup becomes:   stale code + old behavior
Result:           primary/backup diverge over time ❌
```

### After (Proposed)
```
Primary updated:  
  - code changes → redeploy to both (one-time)
  - parameter changes → synced immediately (via trading_config.json + system_config.json)

Backup becomes:   always in sync with primary ✅
Result:           primary/backup always identical ✅
```

---

## Files to Update

### 1. `backend/api/main.py` (lines 208-213)
- Load WebSocket subscriptions from `system_config.json`
- Apply to both `ws` and `stream_client`

### 2. `backend/exchange/binance_stream.py`
- Load `price_max_age` from `system_config.json`
- Use for freshness validation

### 3. `backend/core/health_checker.py`
- Load health check intervals from `system_config.json`
- Use for timeout values

### 4. `backend/core/config_manager.py`
- Update `sync_to_backup()` to sync `system_config.json`
- Add validation to ensure both files are in sync

### 5. `systemd/crypto-trading.service`
- Load systemd parameters from `system_config.json` (via environment)
- Or move to code-based restarts instead of systemd

---

## Current Impact

**WebSocket Subscription Issue (discovered today):**
- ❌ Primary: Fixed (code updated with trade streams)
- ❌ Backup: Still broken (running old code)
- ❌ No automatic sync for code changes

**How to fix TODAY:**
```bash
# On backup machine
ssh backup "cd /home/claude/crypto-daytrading && git pull && sudo systemctl restart crypto-trading-backup.service"
```

**Permanent solution:** Implement system_config.json sync (Phase 2-4 above)

---

## Sustainability Checklist

- [ ] All operational parameters in `system_config.json`
- [ ] `system_config.json` synced with `trading_config.json`
- [ ] Code loads from `system_config.json`, not hardcoded
- [ ] Backup automatically gets parameter changes
- [ ] Documentation shows parameter locations
- [ ] Audit trail logs which config version is running

---

## Example: How System Config Solves This

**Scenario:** "Add ADAUSDT to trading symbols"

### Before (Hardcoded)
```python
# main.py (hardcoded)
ws.subscribe("adausdt@trade", on_price_update)  # Must edit code!
# systemd service must restart
# Backup must be manually updated
# Risk: Backup forgotten, trades only on primary
```

### After (System Config)
```json
// system_config.json (runtime)
{
  "websocket": {
    "subscriptions": [
      "btcusdt@kline_1m", "btcusdt@trade",
      "ethusdt@kline_1m", "ethusdt@trade",
      "bnbusdt@kline_1m", "bnbusdt@trade",
      "adausdt@kline_1m", "adausdt@trade"  // ← Just add here!
    ]
  }
}
// sync_to_backup() automatically propagates
// Both machines trade ADAUSDT within seconds
// Audit log shows config change
```

---

## Conclusion

**Current State:** ❌ UNSUSTAINABLE - Hardcoded params diverge between machines  
**Proposed State:** ✅ SUSTAINABLE - All runtime params synced via system_config.json  
**Effort:** ~4 hours to implement Phases 2-4  
**Benefit:** No more manual syncing; backup always in sync; clear audit trail

