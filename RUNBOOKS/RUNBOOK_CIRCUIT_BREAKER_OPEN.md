# RUNBOOK: Circuit Breaker Open Recovery

**Last Updated:** 2026-07-03  
**Severity:** HIGH  
**Target RTO:** 60-120 seconds (auto), 30 seconds (manual)  
**Related Runbooks:** [WebSocket Failure](RUNBOOK_WEBSOCKET_FAILURE.md), [Decision Tree](RUNBOOK_DECISION_TREE.md)

---

## Detection

### Alert Indicators

| Signal | Meaning | Action |
|--------|---------|--------|
| "Circuit breaker OPEN for >1 minute" | No new orders being placed | Check root cause immediately |
| "CB state: OPEN" | Protection mode active (exits allowed, entries blocked) | Trading degraded but controlled |
| "CB trips: N" | Circuit breaker has tripped N times | If >5/hour, something wrong |
| No new trades in 60s | Trading loop halted (CB blocking entries) | Check CB status and root cause |

### Log Grep Patterns

```bash
# Find all circuit breaker state changes
grep -i "circuit.*open\|circuit.*closed\|circuit.*half" /var/log/crypto-daytrading/*.log

# Find what caused CB to open
grep -B 5 "circuit.*open" /var/log/crypto-daytrading/*.log | grep -i "error\|fail\|timeout"

# Count total trips in last hour
grep "circuit.*open" /var/log/crypto-daytrading/*.log | tail -100 | wc -l

# See reason for most recent trip
grep -i "circuit.*open" /var/log/crypto-daytrading/*.log | tail -1
```

### Manual Check

```bash
# Check circuit breaker current state
curl -s http://localhost:8000/api/safety/circuit-breaker
# Response: {"state": "OPEN" or "CLOSED" or "HALF_OPEN", "trips": N, "last_error": "..."}

# Check how long it's been open
curl -s http://localhost:8000/api/safety/circuit-breaker | jq '{
  state: .state,
  trips_total: .trips_total,
  time_open_seconds: .time_open_seconds,
  reason: .failure_reason
}'

# Expected when healthy: state = "CLOSED", trips_total = small number

# Check if trading is active
curl -s http://localhost:8000/api/autonomous/status | jq '.trading_active'
# Should be: true (or false if CB open)
```

---

## Root Cause Analysis

### Most Common Causes

1. **WebSocket Staleness (70% of cases)**
   - Prices haven't updated for >15 seconds
   - Skill #1 detected stale, attempting reconnect
   - While reconnecting, CB trips (data too old to trade safely)
   - **Test:** See [RUNBOOK_WEBSOCKET_FAILURE.md](RUNBOOK_WEBSOCKET_FAILURE.md)

2. **Network Connectivity Issue (15% of cases)**
   - Connection to Binance REST API failing (timeouts)
   - ORDER placement endpoints unreachable
   - **Test:** `curl -I https://api.binance.us/api/v3/account` (should get 200)

3. **API Rate Limiting (10% of cases)**
   - IP getting throttled by Binance (429 Too Many Requests)
   - Recovery in progress, requests rejected
   - **Test:** `grep "429\|rate.*limit" /var/log/crypto-daytrading/*.log`

4. **System Overload (3% of cases)**
   - PRIMARY machine CPU/memory maxed out
   - Database query taking too long (>1 second)
   - **Test:** `top`, `free -h`, `df -h` on PRIMARY machine

5. **Binance API Down (2% of cases)**
   - Binance REST API endpoints not responding
   - Order placement endpoint experiencing issues
   - **Test:** Check https://www.binance.us/en/support/announcement

---

## Recovery Procedure

### Automatic Recovery (Current System)

**What happens automatically:**

1. **Detection (Immediate)**
   - Circuit breaker detects failures reaching threshold
   - State changes to OPEN
   - Logs: "Circuit breaker OPEN after 5 consecutive failures"
   - New entries BLOCKED (risk protection)
   - Exits ALLOWED (can close positions)

2. **Recovery Window (60-120 seconds)**
   - CB waits in OPEN state for 60-120 seconds
   - Behind scenes: WebSocket reconnecting, network recovering
   - After timeout, CB moves to HALF_OPEN

3. **Half-Open Testing (10 seconds)**
   - CB allows small test orders (10% normal size)
   - If test succeeds → CLOSED (fully recovered)
   - If test fails → back to OPEN (not ready yet)

4. **Full Recovery**
   - CB returns to CLOSED state
   - Normal trading resumes
   - **Typical timeline:** 2-5 minutes total

### Manual Recovery (If Automatic Fails)

**When to intervene:** If CB still OPEN after 5 minutes

#### Step 1: Identify Root Cause

```bash
# Check recent errors in logs
grep -B 3 "circuit.*open" /var/log/crypto-daytrading/*.log | tail -20

# Most common patterns:
# - "WebSocket stale": See WebSocket runbook
# - "Connection timeout": Network issue, proceed to Step 2
# - "Rate limit (429)": Binance throttling, wait 60s
# - "Database connection failed": See Database runbook
```

#### Step 2: Verify Issue is Resolved

```bash
# If WebSocket was issue:
curl -s http://localhost:8000/api/monitoring/health/websocket | jq '.status'
# Should show: "connected" (not "stale")

# If network was issue:
curl -s -I https://api.binance.us/api/v3/ticker/price?symbol=BTCUSDT
# Should show: HTTP 200 OK

# If rate limit was issue:
# Just wait 60 seconds (Binance IP ban expires)
# Then try: curl -s https://api.binance.us/api/v3/ticker/price?symbol=BTCUSDT
```

#### Step 3: Reset Circuit Breaker Manually

```bash
# NOTE: In Phase 2, this endpoint will exist
# For now (Phase 1), manual reset requires restart

# Option A: Graceful restart (if running)
curl -X POST http://localhost:8000/api/autonomous/stop
sleep 5
curl -X POST http://localhost:8000/api/autonomous/start

# Option B: Check if auto-recovery is in progress
curl -s http://localhost:8000/api/safety/circuit-breaker | jq '.state'
# If "HALF_OPEN": Just wait another 10-30 seconds (testing in progress)
# If "OPEN": Verify root cause is fixed, then wait for 60s timeout

# Option C: Verify issue truly resolved before proceeding
# Check that both conditions are true:
curl -s http://localhost:8000/api/monitoring/health/websocket | jq '.status'
# Should be: "connected"
curl -s http://localhost:8000/api/autonomous/status | jq '.can_trade'
# Should be: true (or will be after CB opens)
```

#### Step 4: Monitor Recovery

```bash
# Watch circuit breaker state transition
for i in {1..10}; do
  echo "Check $i:"
  curl -s http://localhost:8000/api/safety/circuit-breaker | jq '{state, trips_total, time_open_seconds}'
  sleep 10
done

# Expected progression:
# Check 1: state = "OPEN", time_open_seconds = 0
# Check 2: state = "OPEN", time_open_seconds = 10
# ...
# Check 7: state = "HALF_OPEN" (test mode, testing orders)
# Check 10: state = "CLOSED" (recovered!)
```

#### Step 5: Verify Trading Resumed

```bash
# Check if new trades are happening
curl -s http://localhost:8000/api/portfolio/history | jq '.trades | last'
# Should show recent timestamp (last 1-2 minutes)

# Check if circuit breaker is CLOSED
curl -s http://localhost:8000/api/safety/circuit-breaker | jq '.state'
# Should be: "CLOSED"

# If still open after manual attempts:
# Escalate to engineer (see Escalation section)
```

---

## Timeline

### Expected RTO (Recovery Time Objective)

| Scenario | Time to Recovery | Action |
|----------|------------------|--------|
| **WebSocket briefly stale, auto-recovers** | 60-90 seconds | CB auto-resets, no manual action |
| **WebSocket recovers, CB still open** | 120-180 seconds | Wait for auto-recovery or manual reset |
| **Network issue, manual identification needed** | 30 seconds (once fixed) | Identify root cause, CB auto-closes |
| **Binance rate limit (429)** | 60+ seconds | Wait for IP to be unblocked, then recover |
| **System overload (CPU/memory)** | Variable (2-10 min) | Requires investigation and possible restart |

### Phase 1 vs Phase 2

**Phase 1 (Current):**
- CB auto-resets after 60-120 seconds
- No manual reset endpoint
- Manual intervention = graceful restart

**Phase 2 (Coming):**
- CB auto-resets after 60-120 seconds
- Manual reset endpoint: `POST /admin/reset-breaker`
- Can reset immediately without restart

### Monitoring During Recovery

```bash
# Real-time monitoring (updates every 5 seconds)
watch -n 5 'curl -s http://localhost:8000/api/safety/circuit-breaker | jq "{state: .state, trips: .trips_total, open_time_sec: .time_open_seconds}"'
```

---

## Escalation

### When to Page Engineer

**Page immediately if:**
- CB trips >10 times in 1 hour (repeated failures)
- CB stays OPEN >10 minutes (auto-recovery failed)
- CB trips occur while WebSocket is healthy (root cause unclear)
- Manual reset doesn't restore trading

**Page within 15 minutes if:**
- CB trips 5-10 times/hour (degraded but recovering)
- Root cause identified but can't fix manually

### Troubleshooting Checklist Before Escalating

```bash
# Run these checks to gather info for engineer

# 1. Current CB state
curl -s http://localhost:8000/api/safety/circuit-breaker

# 2. WebSocket health (most common root cause)
curl -s http://localhost:8000/api/monitoring/health/websocket | jq '{status: .status, staleness_seconds: .staleness_seconds}'

# 3. Network to Binance
ping -c 3 api.binance.us

# 4. Recent errors (last 50 lines)
grep -i "error\|fail\|timeout" /var/log/crypto-daytrading/*.log | tail -50 > /tmp/recent_errors.txt

# 5. System resources
free -h; df -h; top -bn1 | head -15

# Provide all this info when paging engineer
echo "CB state: $(curl -s http://localhost:8000/api/safety/circuit-breaker | jq '.state')"
echo "WebSocket status: $(curl -s http://localhost:8000/api/monitoring/health/websocket | jq '.status')"
```

### Escalation Path

```
CB OPEN >5 min
    │
    ├─→ Check WebSocket status
    │   ├─ Stale: Follow WebSocket runbook, wait 90s
    │   ├─ Healthy: Proceed to next
    │
    ├─→ Check Binance API (curl -I https://api.binance.us/api/v3/ping)
    │   ├─ HTTP 200: Good, proceed to next
    │   ├─ Timeout/error: Network issue, escalate to DevOps
    │
    ├─→ Check for rate limit errors (grep "429")
    │   ├─ Found: Wait 60s, then verify recovery
    │   ├─ Not found: Proceed to next
    │
    ├─→ Check system load (top, free, df)
    │   ├─ CPU >80% or memory >90%: Investigate resource issue
    │   ├─ Normal: Proceed to next
    │
    └─→ Manual reset and monitor
        ├─ If succeeds: Document incident
        ├─ If fails >10 min: PAGE ENGINEER
```

---

## Post-Recovery Verification

### Checklist After CB Closes

- [ ] **CB state is CLOSED?** - `curl http://localhost:8000/api/safety/circuit-breaker | jq '.state'` shows "CLOSED"
- [ ] **Trading active?** - `curl http://localhost:8000/api/autonomous/status | jq '.trading_active'` shows true
- [ ] **Recent trade?** - `curl http://localhost:8000/api/portfolio/history | jq '.trades | last | .timestamp'` is recent (within 2 min)
- [ ] **WebSocket healthy?** - `curl http://localhost:8000/api/monitoring/health/websocket | jq '.status'` shows "connected"
- [ ] **No new errors?** - `grep "error\|fail" /var/log/crypto-daytrading/*.log | grep -v "previous\|historical" | tail -5` has no recent entries
- [ ] **Positions intact?** - `curl http://localhost:8000/api/portfolio/positions | jq '.positions | length'` shows expected count

### Metrics to Check

```bash
# Verify CB metrics after recovery
curl -s http://localhost:8000/api/safety/circuit-breaker | jq '{
  state: .state,
  trips_total: .trips_total,
  trips_last_hour: .trips_last_hour,
  avg_recovery_seconds: .avg_recovery_seconds,
  last_reset_time: .last_reset_time
}'

# Expected healthy values:
# - state: "CLOSED"
# - trips_total: <10 per day (normal)
# - trips_last_hour: 0 (unless just recovered)
# - avg_recovery_seconds: <120
```

### Log Analysis

```bash
# Verify incident is over
tail -50 /var/log/crypto-daytrading/api.log | grep -i "circuit"
# Should see "CLOSED" or no CB entries in recent logs

# Check if root cause was identified
tail -100 /var/log/crypto-daytrading/api.log | grep -i "websocket\|network\|rate.*limit"
# Help identify what triggered the incident

# Verify no trades were duplicated during CB recovery
grep "duplicate\|two.*orders\|order.*skipped" /var/log/crypto-daytrading/*.log
# Should be empty (CB prevents this)
```

---

## Difference: Phase 1 vs Phase 2

### Phase 1 (Current - Until July 15)

**How CB recovers:**
```
T+0s:  CB opens (failures detected)
T+60s: CB waits 60s, transitions to HALF_OPEN
T+70s: CB tests small order
T+75s: If test succeeds → CLOSED
       If test fails → back to OPEN (try again)
```

**Manual reset:**
- Requires: `curl -X POST http://localhost:8000/api/autonomous/stop` + start
- Time: 10-30 seconds
- Disruption: Brief pause in trading

**No direct `/admin/reset-breaker` endpoint yet**

### Phase 2 (After July 15 - Target Improvement)

**How CB recovers:**
```
T+0s:  CB opens
T+60s: Auto-reset endpoint available
       OR manually: POST /admin/reset-breaker
```

**Manual reset:**
- Becomes: `curl -X POST http://localhost:8000/api/admin/reset-breaker`
- Time: 1-2 seconds
- Disruption: None (no need to restart)

**Impact:** Manual intervention will be faster and non-disruptive

---

## Summary

| Step | Action | Expected Outcome |
|------|--------|------------------|
| **Detect** | Alert or manual check | Confirm CB state = "OPEN" |
| **Root Cause** | Check WebSocket, network, rate limit | Identify what triggered CB |
| **Auto-Recover** | Wait 60-120 seconds | CB auto-transitions to HALF_OPEN, then CLOSED |
| **Verify** | Check CB state, trading status | CB = "CLOSED", trades resuming |
| **Manual Reset** | If >5 min, stop/start autonomous | Trading fully restored |
| **Post-Recovery** | Check logs and metrics | No duplicates, incident documented |

**Success = Circuit breaker CLOSED, trading active, prices flowing within 120 seconds**
