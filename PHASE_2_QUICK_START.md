# Phase 2: Quick Start Integration Guide

**Status:** Ready to integrate into main.py  
**Setup Time:** 15 minutes  
**Test:** 5 minutes

---

## What Phase 2 Does

Monitors your system for cascade precursors:
- 🔴 Memory pressure (75% WARNING → 85% CRITICAL)
- 🔴 WebSocket staleness (30s+ no updates)
- 🔴 HA sync failures (latency >10s)
- 🔴 Exception spikes (>1% errors)

When ANY 2+ conditions active simultaneously → **CASCADE ALERT**

---

## Installation (30 seconds)

The modules are already in place:
```bash
backend/core/
  ├─ phase_2_metrics.py      ✅ Ready
  ├─ phase_2_alerts.py       ✅ Ready
  └─ phase_2_monitoring.py   ✅ Ready
```

No external dependencies. Only stdlib + psutil (already installed).

---

## Integration: 5 Lines of Code

**Add to your `backend/api/main.py`:**

```python
from backend.core.phase_2_monitoring import init_phase2_monitoring

# In FastAPI lifespan/startup:
monitoring = init_phase2_monitoring()
await monitoring.start()

# In shutdown:
await monitoring.stop()

# Register alert handler (optional):
async def on_cascade_alert(alert):
    logger.critical(f"PHASE2 ALERT: {alert}")
    # Add your alert action here

monitoring.register_alert_handler(on_cascade_alert)
```

---

## Recording Events (2 Lines Each)

**After Trade:**
```python
metrics = get_phase2_metrics()
metrics.record_trade(
    symbol="BTCUSDT",
    success=True,
    slippage=0.015
)
```

**After HA Sync:**
```python
metrics = get_phase2_metrics()
metrics.record_ha_sync(
    success=True,
    latency_ms=142
)
```

---

## Monitoring Health (Every 10s)

```python
monitoring = get_phase2_monitoring()
health = monitoring.get_system_health()

print(f"Status: {health['status']}")  # HEALTHY/WARNING/CRITICAL
print(f"Risk: {health['risk_score']}/100")
print(f"Memory: {health['metrics']['memory_percent']:.1f}%")
print(f"WebSocket: {health['metrics']['websocket_age']:.1f}s")
```

**Output:**
```
Status: CAUTION
Risk: 35/100
Memory: 72.5%
WebSocket: 5.2s
```

---

## Alert Examples

**Memory Alert (75%)**
```
2026-07-04 12:30:15 [CRITICAL] MEMORY_PRESSURE: 75.2% (WARNING threshold)
  Action: Monitor closely, prepare for failover
```

**Cascade Alert (Multi-factor)**
```
2026-07-04 12:30:45 [CRITICAL] CASCADE_DETECTED: 
  - Memory: 82% (CRITICAL)
  - WebSocket: 45s stale (WARNING)
  - HA Sync: 8.2s latency (WARNING)
  Risk Score: 78/100
  Action: Failover to backup immediately
```

---

## Testing (5 minutes)

Run the chaos tests:
```bash
python3 -m pytest tests/chaos/chaos_ha_failover.py -v
```

Expected output:
```
test_websocket_stale ............................ PASSED
test_memory_pressure ............................ PASSED
test_ha_sync_failure ............................ PASSED
test_cascade_pattern ............................ PASSED

4/4 PASSED
```

---

## Deployment Timeline

- **Now:** Review Phase 2 code (~30 min)
- **This week:** Integrate into main.py (~2 hours)
- **Next week:** Deploy dashboard + staging test (~4 hours)
- **Week 3:** Production launch with 24/7 monitoring

---

## Key Metrics You'll See

### Every 5 seconds:
- Memory usage (MB, %)
- WebSocket freshness (seconds since last update)
- HA sync success rate
- Exception counts by module
- Trading statistics (trades/hour, slippage)

### On Alerts:
- Risk score (0-100)
- Which precursors triggered
- Recommended actions
- Time since condition started

---

## What Gets Better

**Before:** "System crashed at 3 AM, nobody saw it coming"  
**After:** "Alert at 12:30 PM: Memory 75% → We prepared backup → Zero downtime"

---

## Questions?

See `backend/core/PHASE_2_README.md` for full documentation.

Run chaos tests to see it in action:
```bash
cd /home/vali/projects/crypto-daytrading
python3 tests/chaos/chaos_ha_failover.py
```

---

**Next Step:** Integrate Phase 2 into main.py when ready for Week 3 production launch.
