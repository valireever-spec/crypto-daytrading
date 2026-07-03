# Baseline Validation Status

**Window Started:** 2026-07-03 08:57:48 UTC  
**Window Ends:** 2026-07-04 08:57:48 UTC (~24 hours)  
**Current Time:** 2026-07-03 (In Progress)  
**Status:** 🟢 LIVE AND MONITORING

---

## What We're Validating

**Question:** Is the hardened system stable enough for live trading with €1,000?

**Method:** Automated 24-hour baseline monitoring on both PRIMARY (192.168.30.137:8001) and BACKUP (192.168.3.25:8002).

**Metrics Collected:** Every 60 seconds, logged independently on each machine to systemd journal.

---

## Pass/Fail Criteria

### ✅ PASS (Approve Live Trading)
All of these must be TRUE throughout 24 hours:

**Process Health:**
- ✓ Socket count: <50 (target: ~30)
- ✓ Thread count: <50 (target: ~30)
- ✓ Memory %: <5% (target: ~3%)
- ✓ CPU %: Normal (target: <10% idle)
- ✓ Restarts/hour: 0 (NO unexpected crashes)

**Reliability:**
- ✓ Circuit breaker: Stays CLOSED entire 24h
- ✓ Circuit breaker trip count: 0 or <1
- ✓ CRITICAL errors in logs: 0
- ✓ Heartbeat failures: 0 (PRIMARY/BACKUP healthy)

**Trading Health:**
- ✓ Cash balance: Stable (baseline: €1,220.41)
- ✓ Positions: Update normally
- ✓ P&L: Ticking in expected direction
- ✓ WebSocket staleness events: <5 in 24h (normal)
- ✓ WebSocket reconnects: <5 in 24h (normal)

**HA Health:**
- ✓ Explicit heartbeat: Steady (BACKUP reporting)
- ✓ Heartbeat misses: 0 (no false positives)
- ✓ State sync: 0 errors

**Result:** If all green → 🟢 **APPROVE LIVE TRADING**

---

### ⚠️ FAIL (Requires Investigation)
Any of these would be a failure:

**Red Flags:**
- ✗ Sockets growing continuously (resource leak)
- ✗ Memory creeping up (memory leak)
- ✗ Circuit breaker trips (any quantity)
- ✗ Multiple restarts (instability)
- ✗ CRITICAL errors appearing
- ✗ Heartbeat failures (>3 in 24h)
- ✗ Cash balance changing unexpectedly
- ✗ WebSocket stale events >10 in 24h

**Result:** If any red → 🔴 **INVESTIGATE AND RETEST**

---

## Monitoring Architecture

### How It Works

```
PRIMARY (192.168.30.137:8001)
├─ MonitoringLogger.start() → asyncio task
├─ Every 60 seconds:
│  ├─ Gather metrics (process, CB, trading, HA)
│  └─ Log to systemd journal with event: BASELINE_METRICS
└─ Metrics stored in: journalctl -u crypto-trading

BACKUP (192.168.3.25:8002)
├─ MonitoringLogger.start() → asyncio task
├─ Every 60 seconds:
│  ├─ Gather metrics (process, CB, trading, HA heartbeat)
│  └─ Log to systemd journal with event: BASELINE_METRICS
└─ Metrics stored in: journalctl -u crypto-trading
```

### Data Independence

✅ **Critical:** Both machines log independently to their own systemd journals
- PRIMARY logs go to PRIMARY's `/var/log/journal`
- BACKUP logs go to BACKUP's `/var/log/journal`
- No single point of failure
- Each machine validates its own health

---

## Baseline Metrics Definition

### Full Metric Payload (Every 60s)

```json
{
  "timestamp": "2026-07-03T08:57:48.123456Z",
  "machine_id": "PRIMARY" or "BACKUP",
  "is_primary": true or false,
  
  "process": {
    "sockets": 32,
    "threads": 28,
    "memory_percent": 3.2,
    "cpu_percent": 5.1,
    "restarts_last_hour": 0
  },
  
  "circuit_breaker": {
    "state": "CLOSED",
    "trip_count": 0
  },
  
  "trading": {
    "mode": "PAPER",
    "cash": 1220.41,
    "total_pnl": 221.56,
    "positions_count": 3
  },
  
  "heartbeat": {
    "heartbeats_received": 3240,
    "consecutive_misses": 0,
    "promoted": false
  }
}
```

---

## Query Commands

### Count Total Logs (should be ~1,440 per 24h)

**PRIMARY:**
```bash
ssh vali@192.168.30.137 "journalctl -u crypto-trading | grep BASELINE_METRICS | wc -l"
# Expected: ~1,440
```

**BACKUP:**
```bash
ssh openhabian@192.168.3.25 "journalctl -u crypto-trading | grep BASELINE_METRICS | wc -l"
# Expected: ~1,440
```

### View Latest Metric

**PRIMARY:**
```bash
ssh vali@192.168.30.137 "journalctl -u crypto-trading -n 1 | grep BASELINE_METRICS"
```

**BACKUP:**
```bash
ssh openhabian@192.168.3.25 "journalctl -u crypto-trading -n 1 | grep BASELINE_METRICS"
```

### Watch in Real-Time

**PRIMARY:**
```bash
ssh vali@192.168.30.137 "journalctl -u crypto-trading -f | grep BASELINE_METRICS"
```

**BACKUP:**
```bash
ssh openhabian@192.168.3.25 "journalctl -u crypto-trading -f | grep BASELINE_METRICS"
```

### Extract Metrics to CSV (Analysis)

**PRIMARY:**
```bash
ssh vali@192.168.30.137 \
  "journalctl -u crypto-trading | grep BASELINE_METRICS | \
   jq '.metrics | [.timestamp, .machine_id, .process.sockets, .process.memory_percent, .circuit_breaker.state]' \
   > baseline_primary.csv"
```

**BACKUP:**
```bash
ssh openhabian@192.168.3.25 \
  "journalctl -u crypto-trading | grep BASELINE_METRICS | \
   jq '.metrics | [.timestamp, .machine_id, .process.sockets, .process.memory_percent, .circuit_breaker.state]' \
   > baseline_backup.csv"
```

---

## Scheduled Check-In: Tomorrow 09:00 UTC

**When:** 2026-07-04 approximately 09:00 UTC (24h ±15min from start)

**What to Do:**

1. **Count logs:**
   ```bash
   ssh vali@192.168.30.137 "journalctl -u crypto-trading | grep BASELINE_METRICS | wc -l"
   # Should be ~1,440 (24 * 60)
   ```

2. **View latest metrics (both machines):**
   ```bash
   ssh vali@192.168.30.137 "journalctl -u crypto-trading | tail -10 | grep BASELINE_METRICS"
   ssh openhabian@192.168.3.25 "journalctl -u crypto-trading | tail -10 | grep BASELINE_METRICS"
   ```

3. **Check for errors (both machines):**
   ```bash
   ssh vali@192.168.30.137 "journalctl -u crypto-trading | grep -i 'critical\|error\|exception' | wc -l"
   ssh openhabian@192.168.3.25 "journalctl -u crypto-trading | grep -i 'critical\|error\|exception' | wc -l"
   # Should be <5 each
   ```

4. **Review metrics snapshot (latest reading):**
   ```bash
   ssh vali@192.168.30.137 "journalctl -u crypto-trading -n 1 --no-pager"
   ssh openhabian@192.168.3.25 "journalctl -u crypto-trading -n 1 --no-pager"
   ```

5. **Make decision:**
   - If all PASS criteria met → ✅ **Approve live trading with €1,000**
   - If any FAIL criteria triggered → 🔴 **Debug, fix, restart 24h monitoring**

---

## Expected Timeline

```
Jul 3, 08:57:48 UTC
  ├─ [NOW] Monitoring starts on PRIMARY & BACKUP
  ├─ [08:58] First metrics logged (~5 per machine)
  ├─ [10:00] ~63 metrics per machine (1 hour)
  └─ [20:57] ~720 metrics per machine (12 hours)

Jul 4, 08:57:48 UTC
  ├─ [TOMORROW] ~1,440 metrics per machine (24 hours)
  ├─ [09:00] Decision checkpoint: PASS or FAIL?
  ├─ IF PASS: Approve live trading ✅
  └─ IF FAIL: Debug + retest 🔄
```

---

## Troubleshooting

### Q: Monitoring logs aren't appearing?

**Check if service is running:**
```bash
systemctl status crypto-trading
# Should show: active (running)
```

**Check if monitoring logger initialized:**
```bash
journalctl -u crypto-trading | grep "Monitoring logger started"
# Should show initialization message
```

**Restart monitoring:**
```bash
sudo systemctl restart crypto-trading
sleep 5
journalctl -u crypto-trading -n 10 | grep BASELINE
```

### Q: Sockets growing continuously?

**This is a resource leak.** Check for:
```bash
# What connections are open?
lsof -p $(pgrep -f "crypto-trading") | grep ESTABLISHED | wc -l

# Are they accumulating?
journalctl -u crypto-trading --since "1 hour ago" | grep "socket" | tail -20
```

**Action:** Investigate in `backend/exchange/` for unclosed connections.

### Q: Memory creeping up?

**Check memory usage over time:**
```bash
# Extract memory from baseline logs
journalctl -u crypto-trading | grep BASELINE_METRICS | \
  jq '.metrics.process.memory_percent' | tail -20

# Should stay flat, not trending up
```

**Action:** Look for data structure leaks in `backend/core/`.

### Q: Circuit breaker tripped?

**Check CB state:**
```bash
curl http://localhost:8001/api/monitoring/circuit-breaker/stats | jq .circuit_breaker

# If state is "OPEN", manually reset:
curl -X POST "http://localhost:8001/api/admin/circuit-breaker/reset?reason=manual_reset"

# Verify reset:
curl http://localhost:8001/api/monitoring/circuit-breaker/stats | jq .circuit_breaker.current_state
# Should show: "CLOSED"
```

---

## Expected Baseline Values (Reference)

**Baseline (from pre-hardening observations):**
- Sockets: ~30-40 (normal API operation)
- Threads: ~25-30 (Python + uvicorn)
- Memory: ~2-4% (lightweight deployment)
- CPU: ~5-10% idle (light workload)
- Circuit breaker: CLOSED (should stay this way)
- Cash: €1,220.41 ±small changes (paper trading)
- Positions: 0-5 (normal range)

**Expected Variations:**
- Sockets: ±10 (normal fluctuation)
- Memory: ±1% (Python GC)
- CPU: ±5% (hourly variation)

**NOT Expected:**
- Sockets growing from 30 → 100+
- Memory growing from 3% → 20%+
- Circuit breaker opening
- Restarts occurring

---

## Success Indicator

**If you see this in tomorrow's logs, you've passed baseline validation:**

```json
{
  "timestamp": "2026-07-04T08:57:00Z",
  "metrics": {
    "machine_id": "PRIMARY",
    "process": {
      "sockets": 31,
      "memory_percent": 3.4,
      "cpu_percent": 6.2,
      "restarts_last_hour": 0
    },
    "circuit_breaker": {
      "state": "CLOSED",
      "trip_count": 0
    },
    "trading": {
      "cash": 1220.41,
      "total_pnl": 221.56
    }
  }
}
```

And the same on BACKUP. All good = approval granted. 🚀

---

## Next Decision: After Validation

### If PASS (Baseline clean)
```
Jul 4, 09:00 UTC: Approve live trading
  ↓
Deploy with €1,000 initial capital
  ↓
Start paper-to-live transition
```

### If FAIL (Issues detected)
```
Jul 4, 09:00 UTC: Identify root cause
  ↓
Fix issue + redeploy
  ↓
Restart 24h monitoring
  ↓
Try again next day
```

---

**Document Version:** 1.0  
**Last Updated:** 2026-07-03 08:57:48 UTC  
**Next Update:** 2026-07-04 09:00 UTC (decision point)
