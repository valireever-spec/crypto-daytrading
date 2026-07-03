# WebSocket Staleness Skill Deployment Guide

## What Was Integrated

**SKILL #1: WebSocket Staleness Detection + Auto-Reconnect**

Automatically detects stale price feeds (WebSocket connection loss) and attempts recovery **before** circuit breaker activates. Prevents cascading failures from transient network issues.

### Files Created/Modified

1. ✅ **NEW:** `backend/exchange/websocket_staleness_monitor.py` — Staleness monitor class (160 lines)
2. ✅ **MODIFIED:** `backend/exchange/websocket_manager.py` — Added `reconnect()` method
3. ✅ **MODIFIED:** `backend/api/lifecycle.py` — Initialize monitor + register callbacks
4. ✅ **MODIFIED:** `backend/api/routers/monitoring.py` — Added `/api/monitoring/health/websocket` endpoint

---

## Deployment Steps

### Step 1: Verify Files

```bash
cd /home/vali/projects/crypto-daytrading

# Check files exist
ls -la backend/exchange/websocket_staleness_monitor.py
echo "✓ Staleness monitor module"

grep -n "def reconnect" backend/exchange/websocket_manager.py
echo "✓ Reconnect method added"

grep -n "WebSocketStalenessMonitor" backend/api/lifecycle.py
echo "✓ Lifecycle integration added"

grep -n "health/websocket" backend/api/routers/monitoring.py
echo "✓ Health endpoint added"
```

### Step 2: Start the Bot

```bash
# Terminal 1: Start the API server
cd /home/vali/projects/crypto-daytrading
export PYTHONPATH=$(pwd)
python -m uvicorn backend.api.main:app --host 0.0.0.0 --port 8000 --reload

# Expected output:
# ✅ WebSocket staleness monitor initialized (SKILL #1: Early detection + auto-reconnect)
```

### Step 3: Monitor in Real-Time

```bash
# Terminal 2: Watch logs for staleness detection
cd /home/vali/projects/crypto-daytrading
journalctl -u crypto-trading -f | grep -i "stale\|reconnect\|websocket"

# Or directly from logs if running locally:
tail -f /tmp/crypto_daytrading.log | grep -i "stale\|reconnect"
```

### Step 4: Check Health Endpoint

```bash
# Terminal 3: Query WebSocket health
curl http://localhost:8000/api/monitoring/health/websocket | jq

# Expected response (healthy):
{
  "status": "healthy",
  "details": {
    "timestamp": "2026-07-03T10:30:45.123Z",
    "streams": {
      "BTCUSDT": {
        "staleness_secs": 0.2,
        "is_healthy": true,
        "reconnect_attempts": 0,
        "last_update": "2026-07-03T10:30:45.000Z"
      },
      "ETHUSDT": {...},
      "BNBUSDT": {...}
    },
    "metrics": {
      "staleness_warnings": 0,
      "reconnect_attempts": 0,
      "reconnect_successes": 0,
      "reconnect_failures": 0
    }
  }
}
```

---

## Testing Scenarios

### Scenario 1: Network Blip (Transient Failure) ⭐ RECOMMENDED FIRST

**What:** Simulate short network outage, verify auto-recovery

```bash
# Terminal 1: Start bot (if not already running)
python -m uvicorn backend.api.main:app --host 0.0.0.0 --port 8000

# Wait 10 seconds for prices to flow normally
# Expected in logs: no staleness warnings

# Terminal 2: Simulate network disconnect
# Kill WebSocket process (or disable Binance connectivity)
sudo pkill -f "websocket\|binance" || true

# Watch logs in Terminal 3
tail -f /tmp/crypto_daytrading.log | grep -E "STALE|reconnect|Reconnect"

# Expected sequence (within 20 seconds):
# 1. ⚠️  [BTCUSDT] Price stale: 5.2s > 5s threshold
# 2. 🚨 [BTCUSDT] CRITICAL staleness: 15.1s > 15.0s, triggering reconnect
# 3. 🔄 [BTCUSDT] Reconnect attempt 1/3, waiting 2s
# 4. 🔄 [BTCUSDT] Reconnect attempt 2/3, waiting 4s
# 5. ✅ [BTCUSDT] Reconnect successful after 2 attempts

# Restore connectivity (if you disabled it)
# Expected: Trading resumes, NO circuit breaker trip
```

### Scenario 2: Persistent WebSocket Failure (Expected Circuit Breaker)

**What:** Full Binance outage, verify graceful degradation

```bash
# Terminal 1: Start bot
python -m uvicorn backend.api.main:app --host 0.0.0.0 --port 8000

# Block Binance IP entirely
sudo iptables -A OUTPUT -d stream.binance.com -j DROP  # Linux
# (or use firewall rules on your system)

# Watch logs for 30+ seconds
tail -f /tmp/crypto_daytrading.log

# Expected sequence:
# 1. ⚠️  [BTCUSDT] Price stale: 7.0s > 5s threshold (WARN)
# 2. 🚨 [BTCUSDT] CRITICAL staleness: 15.2s > 15.0s, triggering reconnect (attempt 1/3)
# 3. 🔄 Reconnect attempt 1/3, waiting 2s
# 4. ⚠️  Reconnect attempt 1 failed: Connection timeout
# 5. 🔄 Reconnect attempt 2/3, waiting 4s
# 6. ⚠️  Reconnect attempt 2 failed: Connection timeout
# 7. 🔄 Reconnect attempt 3/3, waiting 8s
# 8. ⚠️  Reconnect attempt 3 failed: Connection timeout
# 9. ❌ [BTCUSDT] WebSocket unrecoverable after 3 attempts, deferring to circuit breaker
# 10. Circuit breaker activates (expected) → Trading paused
#
# After restoring Binance connectivity:
# → Bot auto-recovers (circuit breaker resets on success)
# → Trading resumes

# Unblock Binance
sudo iptables -D OUTPUT -d stream.binance.com -j DROP  # Linux
```

### Scenario 3: Slow Network (High Latency)

**What:** Staleness fluctuates around threshold, verify smooth behavior

```bash
# Simulate with tc (traffic control)
# Add 5s latency to Binance traffic
sudo tc qdisc add dev eth0 root netem delay 5000ms

# Watch logs
# Expected: Warnings at 5s threshold, but NOT constant reconnects
# → Reconnect attempts should stabilize once prices resume flowing

# Remove latency
sudo tc qdisc del dev eth0 root
```

---

## Configuration Tuning

If you want to adjust staleness thresholds based on your network:

Edit `backend/exchange/websocket_staleness_monitor.py`:

```python
class WebSocketStalenessMonitor:
    # Current thresholds
    WARN_THRESHOLD = 5.0           # Alert at 5s (default: good for most)
    CRITICAL_THRESHOLD = 15.0      # Reconnect at 15s (default: balance early detection vs false positives)
    BREAKER_THRESHOLD = 30.0       # Circuit breaker should never see this
    MAX_RECONNECT_ATTEMPTS = 3     # Retry max 3 times (default: reasonable for Binance)
    BACKOFF_BASE = 2.0             # Exponential backoff: 2s, 4s, 8s (default: good)

    # TUNING OPTIONS:
    # ✅ If Binance is stable (rare disconnects):
    #    → Lower MAX_RECONNECT_ATTEMPTS to 2 (fail faster)
    #    → Increase CRITICAL_THRESHOLD to 20s (tolerate more latency)
    
    # ✅ If your network is flaky (frequent drops):
    #    → Increase MAX_RECONNECT_ATTEMPTS to 5 (try harder)
    #    → Increase BACKOFF_BASE to 3.0 (slower backoff to avoid hammering)
    #    → Lower CRITICAL_THRESHOLD to 10s (detect failures faster)
```

---

## Monitoring Dashboard

### Real-Time Metrics

Use `/api/monitoring/health/websocket` to power a dashboard:

```bash
# Export metrics continuously (useful for Prometheus/Grafana)
watch -n 1 'curl -s http://localhost:8000/api/monitoring/health/websocket | jq ".details.metrics"'

# Expected output (healthy):
# {
#   "staleness_warnings": 0,
#   "reconnect_attempts": 0,
#   "reconnect_successes": 0,
#   "reconnect_failures": 0
# }

# After a network blip:
# {
#   "staleness_warnings": 5,           # 5 warning-level events logged
#   "reconnect_attempts": 2,           # 2 reconnect attempts made
#   "reconnect_successes": 1,          # 1 successful recovery
#   "reconnect_failures": 0            # 0 failures
# }
```

### Log Patterns to Watch

**Healthy bot** (no staleness):
```
✓ No "Price stale" or "CRITICAL staleness" messages
✓ Occasional "[BTCUSDT] Price update received" or similar
✓ websocket_reconnect_attempts_total = 0
```

**Transient failure + auto-recovery** (expected):
```
⚠️  [BTCUSDT] Price stale: X.Xs
🚨 [BTCUSDT] CRITICAL staleness: Y.Ys, triggering reconnect
🔄 [BTCUSDT] Reconnect attempt 1/3
✅ [BTCUSDT] Reconnect successful after 1 attempts
```

**Persistent failure + circuit breaker** (also expected):
```
🚨 [BTCUSDT] CRITICAL staleness detected
🔄 Reconnect attempt 1/3, 2/3, 3/3
❌ [BTCUSDT] WebSocket unrecoverable after 3 attempts, deferring to circuit breaker
Circuit breaker: Pausing entries
```

---

## Success Criteria (24-hour test)

Run the skill in production for 24 hours and measure:

| Metric | Target | Pass/Fail |
|--------|--------|-----------|
| **Circuit breaker trips/day** | <1 (was >10 before) | |
| **Auto-recover events** | >0 (was 0 before) | |
| **Manual restarts** | 0 (was 1-2 before) | |
| **Mean time to recovery (MTTR)** | <30s (was N/A before) | |
| **Uptime %** | >99.5% (was ~95% before) | |

**Example:** Before deploying skill #1, you'd see circuit breaker trip every 10s with 3am manual restart required. After deploying, you should see 0-1 trips per day with auto-recovery every time.

---

## Rollback (if needed)

If staleness monitor causes issues:

```bash
# Quick disable: Comment out the monitor initialization
# File: backend/api/lifecycle.py
# Around line 230, comment this section:

# if ws_manager:
#     try:
#         staleness_monitor = WebSocketStalenessMonitor(ws_manager)
#         ...
```

Or set environment variable:

```bash
export ENABLE_STALENESS_MONITOR=false
# Then restart bot
```

Then reconnect and verify:

```bash
# Check health endpoint returns error (not critical, just warns)
curl http://localhost:8000/api/monitoring/health/websocket
# Expected: 503 "Staleness monitor not initialized"
```

---

## Next Steps

After 24-hour validation, move to **Phase 2: Circuit Breaker State Reset**:
- Implement `/admin/reset-breaker` endpoint
- Allow trading to resume after recovery without full restart
- Estimated effort: 3 hours

See `/home/vali/projects/skill-creator/HARDENING_IMPLEMENTATION_ROADMAP.md` for full phases.

---

## Questions?

- **Logs not showing reconnect?** → Check that WebSocket manager has `register_callback()` called (line 232 in lifecycle.py)
- **Health endpoint returns 503?** → Check staleness_monitor is initialized in lifecycle
- **Thresholds too aggressive?** → Adjust `WARN_THRESHOLD` and `CRITICAL_THRESHOLD` in websocket_staleness_monitor.py
- **Still seeing circuit breaker trips?** → Increase `MAX_RECONNECT_ATTEMPTS` to 5 or lower `CRITICAL_THRESHOLD` to 10s

**Success looks like:** No more 3am manual restarts, auto-recovery logs showing reconnects succeed, circuit breaker rarely trips.
