# WebSocket Staleness Skill - Quick Start (5 Minutes)

## What This Does

Stops the 3am cascading failure loop by detecting stale WebSocket prices early and auto-recovering before trading logic breaks.

**Before:**
```
WebSocket dies (10:23:45) → no action → prices stale 30s (10:24:15) → circuit breaker trips → repeats every 10s all night → manual restart needed
```

**After:**
```
WebSocket dies (10:23:45) → detected at 15s stale (10:24:00) → auto-reconnect 2 attempts → recovered (10:24:10) → no circuit breaker trip
```

---

## 3-Step Deployment

### 1. Check the files exist
```bash
cd /home/vali/projects/crypto-daytrading
ls backend/exchange/websocket_staleness_monitor.py && echo "✓ Skill module created"
```

### 2. Start the bot
```bash
python -m uvicorn backend.api.main:app --host 0.0.0.0 --port 8000
```

Look for this in startup logs:
```
✅ WebSocket staleness monitor initialized (SKILL #1: Early detection + auto-reconnect)
```

### 3. Verify health endpoint
```bash
curl http://localhost:8000/api/monitoring/health/websocket | jq
```

Should show:
```json
{
  "status": "healthy",
  "details": {
    "streams": {
      "BTCUSDT": {"staleness_secs": 0.1, "is_healthy": true},
      "ETHUSDT": {...},
      "BNBUSDT": {...}
    }
  }
}
```

---

## Test It (Optional)

Kill WebSocket and watch auto-recovery:

```bash
# Terminal 1: Watch logs
tail -f /tmp/crypto_daytrading.log | grep -i "stale\|reconnect"

# Terminal 2: Simulate network disconnect
sudo pkill -f websocket

# Expected in logs (within 20s):
# 🚨 CRITICAL staleness
# 🔄 Reconnect attempt 1/3
# ✅ Reconnect successful
```

---

## Done ✓

The skill is now active. Monitor these metrics over the next 24 hours:

- ✅ Circuit breaker trips/day: Should drop from >10 to <1
- ✅ Manual restarts: Should drop from 1-2 to 0
- ✅ Auto-recovery events: Should show 1+ successful reconnects

See `WEBSOCKET_SKILL_DEPLOYMENT.md` for detailed testing and tuning.
