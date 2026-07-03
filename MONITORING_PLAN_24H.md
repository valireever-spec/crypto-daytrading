# 24-Hour Skill #1 Validation Plan

## Objective
Measure impact of WebSocket Staleness Skill #1 in production over 24 hours.

## Metrics to Track

### Primary (Most Important)
1. **Circuit Breaker Trips/Day**
   - Before: >10/day
   - Target: <1/day
   - Where: Check logs for "CIRCUIT BREAKER" messages
   - How: `grep "CIRCUIT BREAKER" logs/ | wc -l`

2. **Manual Restarts Needed**
   - Before: 1-2/week (e.g., 3am restart)
   - Target: 0
   - How: Track manually or check systemd logs
   - `journalctl -u crypto-trading --since "24 hours ago" | grep -i restart`

3. **Auto-Recovery Events**
   - Target: >0 (proves skill working)
   - Where: Look for "Reconnect successful" messages
   - `grep "Reconnect successful" logs/`

### Secondary (Health Checks)
4. **Uptime %**
   - Before: ~95%
   - Target: >99.5%
   - Calculate: (total time - downtime) / total time

5. **Staleness Warnings**
   - Target: Should see some (proves monitoring), but <100/day
   - `grep "Price stale" logs/ | wc -l`

## Monitoring Setup

### Option 1: Simple Manual Checks (Every 6 hours)

```bash
# Run every 6 hours (0:00, 6:00, 12:00, 18:00)
TIMESTAMP=$(date "+%Y-%m-%d %H:%M:%S")
echo "$TIMESTAMP - Circuit breaker trips today:"
grep "CIRCUIT BREAKER" logs/ | wc -l

echo "$TIMESTAMP - Reconnect successes:"
grep "Reconnect successful" logs/ | wc -l

echo "$TIMESTAMP - Health check:"
curl -s http://localhost:8000/api/monitoring/health/websocket | jq '.details.metrics'
```

### Option 2: Automated Monitoring Script (Recommended)

Create `/home/vali/projects/crypto-daytrading/monitor_24h.py`:

```python
#!/usr/bin/env python3
"""24-hour Skill #1 validation monitor."""
import subprocess
import json
import requests
from datetime import datetime
import time

HEALTH_ENDPOINT = "http://localhost:8000/api/monitoring/health/websocket"
LOG_FILE = "/path/to/logs/crypto-daytrading.log"  # Update path

def get_log_metrics():
    """Extract metrics from logs."""
    try:
        # Circuit breaker trips
        result = subprocess.run(
            f"grep 'CIRCUIT BREAKER' {LOG_FILE} | wc -l",
            shell=True, capture_output=True, text=True
        )
        cb_trips = int(result.stdout.strip())
        
        # Reconnect successes
        result = subprocess.run(
            f"grep 'Reconnect successful' {LOG_FILE} | wc -l",
            shell=True, capture_output=True, text=True
        )
        reconnect_success = int(result.stdout.strip())
        
        return cb_trips, reconnect_success
    except Exception as e:
        print(f"Error reading logs: {e}")
        return 0, 0

def get_health_status():
    """Get current health from endpoint."""
    try:
        resp = requests.get(HEALTH_ENDPOINT, timeout=5)
        data = resp.json()
        return data['details']['metrics']
    except Exception as e:
        print(f"Health endpoint error: {e}")
        return None

def main():
    print("=" * 60)
    print("SKILL #1 VALIDATION MONITOR - 24 HOUR TEST")
    print("=" * 60)
    
    start_time = datetime.now()
    
    while True:
        elapsed = (datetime.now() - start_time).total_seconds() / 3600
        
        print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Elapsed: {elapsed:.1f}h")
        print("-" * 60)
        
        cb_trips, reconnect_success = get_log_metrics()
        health = get_health_status()
        
        print(f"Circuit Breaker Trips:    {cb_trips} (target: <1)")
        print(f"Reconnect Successes:      {reconnect_success} (target: >0)")
        
        if health:
            print(f"Staleness Warnings:       {health.get('staleness_warnings', 0)}")
            print(f"Reconnect Attempts:       {health.get('reconnect_attempts', 0)}")
            print(f"Reconnect Failures:       {health.get('reconnect_failures', 0)}")
        
        if elapsed >= 24:
            print("\n" + "=" * 60)
            print("TEST COMPLETE - 24 HOUR VALIDATION DONE")
            print("=" * 60)
            print(f"\nFinal Results:")
            print(f"  Circuit Breaker Trips: {cb_trips}")
            print(f"  Reconnect Successes:   {reconnect_success}")
            if cb_trips < 1 and reconnect_success > 0:
                print("\n✅ TEST PASSED - Skill #1 working as expected!")
            else:
                print("\n⚠️  Review results - may need tuning")
            break
        
        time.sleep(3600)  # Check every hour

if __name__ == "__main__":
    main()
```

Run it:
```bash
python3 monitor_24h.py
```

### Option 3: Cloud Monitoring (If Available)

If you have Prometheus/Grafana:
```promql
# Circuit breaker trip rate
rate(circuit_breaker_trips_total[1h])

# Websocket reconnect success rate
rate(websocket_reconnect_attempts_total{status="success"}[1h])

# Mean staleness
avg(websocket_staleness_seconds)
```

## What to Expect

### Hour 0-2 (Baseline)
- Circuit breaker should be silent (0 trips)
- Staleness metrics should show normal (<5s per stream)
- Reconnect metrics should show 0 (no issues yet)

### Hour 2-12 (Normal Operation)
- Occasional small reconnects (expected, network blips)
- Overall status should remain "healthy"
- NO circuit breaker trips

### Hour 12-24 (Validation)
- Cumulative stats should show:
  - **<1 circuit breaker trip** (major improvement!)
  - **1-5 reconnect successes** (skill actively recovering)
  - **0 manual restarts** (biggest win)

## Success Criteria

✅ **Test Passes If:**
- [ ] 0 circuit breaker trips (or ≤1)
- [ ] 1+ reconnect successes logged
- [ ] 0 manual restarts needed
- [ ] Uptime >99%
- [ ] No cascading failures observed

❌ **Test Fails If:**
- [ ] >2 circuit breaker trips
- [ ] Bot crashed and needed manual recovery
- [ ] Repeated failures suggesting tuning needed

## If Test Fails

**Circuit breaker trips still happening?**
→ Lower `CRITICAL_THRESHOLD` in websocket_staleness_monitor.py from 15s to 10s

**Too many reconnect attempts?**
→ Increase `MAX_RECONNECT_ATTEMPTS` from 3 to 5

**Uptime still low?**
→ Check if other systems (HA, database sync) need hardening

## Reporting

After 24 hours, create a file: `/home/vali/projects/crypto-daytrading/SKILL_1_VALIDATION_RESULTS.md`

Include:
```markdown
# Skill #1 Validation Results

**Test Date:** YYYY-MM-DD to YYYY-MM-DD

## Metrics
- Circuit Breaker Trips: X (target: <1) ✅/❌
- Auto-Recovery Events: Y (target: >0) ✅/❌
- Manual Restarts: Z (target: 0) ✅/❌
- Uptime: X% (target: >99.5%) ✅/❌

## Summary
[What happened? Any anomalies? Did skill work as expected?]

## Recommendation
[Proceed to Phase 2? Tune thresholds? Other actions?]
```

---

## Timeline

| Time | Action |
|------|--------|
| T+0h | Start monitoring, baseline health check |
| T+6h | First interim check, ensure no issues |
| T+12h | Mid-point status, verify metrics climbing |
| T+18h | Final checks, prepare to wrap up |
| T+24h | Report results, decide on Phase 2 |

---

## Key Files to Watch

- Logs: Check for "staleness", "reconnect", "CIRCUIT BREAKER"
- Health Endpoint: `/api/monitoring/health/websocket`
- Metrics: `staleness_warnings`, `reconnect_attempts`, `reconnect_successes`

**Good luck! This is the proof point that Skill #1 solves the 3am crisis.** 🚀
