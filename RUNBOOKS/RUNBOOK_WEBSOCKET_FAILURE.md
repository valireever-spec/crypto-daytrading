# RUNBOOK: WebSocket Failure Recovery

**Last Updated:** 2026-07-03  
**Severity:** HIGH  
**Target RTO:** <60 seconds (auto), <5 minutes (manual)  
**Related Runbooks:** [Circuit Breaker](RUNBOOK_CIRCUIT_BREAKER_OPEN.md), [Decision Tree](RUNBOOK_DECISION_TREE.md)

---

## Detection

### Alert Indicators

| Signal | Meaning | Action |
|--------|---------|--------|
| "WebSocket stale >30s" | Prices frozen, no updates for 30+ seconds | **IMMEDIATE** - check below |
| "No orders placing" | System attempting orders but none executing | Check WebSocket health first |
| Prices timestamp: `infs` | "Infinite staleness" - data age unknown/stuck | WebSocket disconnected |
| Circuit breaker OPEN | Trading halted due to repeated failures | Likely WebSocket is root cause |

### Log Grep Patterns

```bash
# Find stale WebSocket warnings
grep -i "websocket stale" /var/log/crypto-daytrading/*.log

# Find reconnection attempts (Skill #1 working)
grep -i "reconnect" /var/log/crypto-daytrading/*.log | grep -i websocket

# Find Binance connection errors
grep -i "binance" /var/log/crypto-daytrading/*.log | grep -i "error\|timeout\|failed"

# See stale price data
grep "infs\|infinite" /var/log/crypto-daytrading/*.log
```

### Manual Check

```bash
# Check if WebSocket is connected
curl -s http://localhost:8000/api/monitoring/health/websocket | jq '.status'
# Should see: "connected", "monitoring", or "staleness_seconds: <15"

# Check all stream ages
curl -s http://localhost:8000/api/monitoring/health/websocket | jq '.streams'
# Expected: Each stream has recent timestamp (seconds, not "infs")

# Check last price update time
curl -s http://localhost:8000/api/portfolio/positions | jq '.prices_timestamp'
# Should be within last 5 seconds
```

---

## Root Cause Analysis

### Most Common Causes

1. **Network Issue (40% of cases)**
   - Connection dropped between PRIMARY and Binance
   - Firewall/proxy blocking WebSocket upgrade
   - Network latency spike causing TCP reset
   - Test: `ping stream.binance.com` and `nc -zv stream.binance.com 443`

2. **Binance API Maintenance (30% of cases)**
   - Binance WebSocket servers down/restarting
   - Binance rolling out new API version
   - Rate limit hit (IP temporarily blocked)
   - Test: Check https://www.binance.us/en/support/announcement (Binance status page)

3. **Connection Pooling Exhaustion (15% of cases)**
   - Too many WebSocket connections from this IP
   - Previous reconnection attempts not closed properly
   - System trying to open 10+ connections simultaneously
   - Test: `netstat -an | grep stream.binance.com | wc -l`

4. **TLS/SSL Certificate Issue (10% of cases)**
   - Certificate validation failing (local clock skew)
   - Proxy intercepting HTTPS (man-in-the-middle)
   - Test: `echo | openssl s_client -connect stream.binance.com:443`

5. **Data Quality Gate Threshold (5% of cases)**
   - Skill #1 detects stale but recovery fails (network keeps dropping)
   - Circuit breaker opened before recovery completes
   - Test: Check circuit breaker state via API

---

## Recovery Procedure

### Automated Recovery (Skill #1 - Current System)

**What happens automatically:**

1. **Detection Phase (0-15 seconds)**
   - Skill #1 monitors stream age every 1 second
   - At 5s stale: Logs warning (yellow alert)
   - At 15s stale: Logs critical (red alert)

2. **Reconnection Phase (15-35 seconds)**
   - Skill #1 initiates exponential backoff:
     - **Attempt 1:** Wait 2 seconds, try reconnect
     - **Attempt 2:** Wait 4 seconds, try reconnect
     - **Attempt 3:** Wait 8 seconds, try reconnect
   - **Success:** Connection re-established, prices flow again
   - **Failure:** Falls through to circuit breaker

3. **Expected Timeline**
   ```
   T+0s:   WebSocket dies (Binance connection lost)
   T+15s:  Skill #1 detects critical staleness
   T+17s:  Attempt 1 (wait 2s, retry)
   T+21s:  Attempt 2 (wait 4s, retry)
   T+29s:  Attempt 3 (wait 8s, retry)
   T+31s:  Connection re-established (typical)
   T+32s:  Prices flowing, trading resumes
   ```

### Manual Recovery (If Automatic Fails)

**When to intervene:** If WebSocket still stale after 60 seconds

#### Step 1: Verify Current State

```bash
# Check WebSocket health (current state)
curl -s http://localhost:8000/api/monitoring/health/websocket
# Response should show staleness_seconds and stream status

# Check if Binance is up
curl -I https://api.binance.us/api/v3/ping
# Should see: HTTP 200 OK (API is up, WebSocket likely too)

# Check if local network can reach Binance
nc -zv stream.binance.com 443
# Should see: Connection successful
# If fail: Network partition detected - escalate to network team
```

#### Step 2: Check for Rate Limiting

```bash
# Look for rate limit errors in logs
grep "429\|rate.*limit" /var/log/crypto-daytrading/*.log

# If found: IP is temporarily blocked
# Action: Wait 60 seconds, then retry
# If persistent: Contact Binance support or use proxy
```

#### Step 3: Force Manual Reconnection

```bash
# Restart WebSocket connection
curl -X POST http://localhost:8000/api/websocket/restart

# Wait for reconnection (should take <10s)
sleep 10

# Verify connection restored
curl -s http://localhost:8000/api/monitoring/health/websocket | jq '.status'
# Should see: "connected"
```

#### Step 4: Verify Prices Updating

```bash
# Check latest price timestamp
for i in {1..5}; do
  echo "Check $i:"
  curl -s http://localhost:8000/api/portfolio/positions | jq '.prices_timestamp'
  sleep 2
done

# Timestamps should increment (moving forward in time)
# If stuck: WebSocket still dead, escalate to Step 5
```

#### Step 5: Check for Binance Maintenance

```bash
# If WebSocket restart fails repeatedly:
# 1. Check Binance status page
#    https://www.binance.us/en/support/announcement

# 2. Try REST API fallback (slower but reliable)
curl -s https://api.binance.us/api/v3/ticker/price?symbol=BTCUSDT
# If success: Binance WebSocket down, but REST API works
# Action: Trading can continue (slowly) on REST API

# 3. Check if circuit breaker is OPEN
curl -s http://localhost:8000/api/safety/circuit-breaker
# If OPEN: See RUNBOOK_CIRCUIT_BREAKER_OPEN.md
```

---

## Timeline

### Expected RTO (Recovery Time Objective)

| Scenario | Time to Recovery | Who Handles |
|----------|------------------|-------------|
| **Typical network blip** | 15-35 seconds | Skill #1 (automatic) |
| **Binance temporary down** | 2-5 minutes | Skill #1 + manual check |
| **Rate limit hit** | 60-120 seconds | Manual wait + retry |
| **Connection pool exhausted** | <30 seconds (Skill #1) | Automatic or manual restart |
| **Binance major outage** | >30 minutes | Escalate to Binance support |

### Monitoring During Recovery

```bash
# Watch recovery in real-time (every 2 seconds)
watch -n 2 'curl -s http://localhost:8000/api/monitoring/health/websocket | jq ".status, .staleness_seconds"'

# Exit with Ctrl+C
```

---

## Escalation

### When to Page Engineer

**Page immediately if:**
- WebSocket stale >90 seconds (recovery failed 3x)
- Manual restart via POST /api/websocket/restart fails
- Binance connection shows repeated 429 (rate limit), not recovering
- Multiple failed reconnection attempts with error logs

**Page within 10 minutes if:**
- WebSocket stale 60+ seconds and still recovering
- Binance status page says "Maintenance" (expected, not urgent)

### When to Contact Binance Support

- WebSocket down >30 minutes (check status page first)
- Repeated rate limiting (IP blocked)
- Connection refused (firewall/IP ban)
- Contact: https://www.binance.us/en/support

### Escalation Workflow

```
WebSocket stale >60s
    │
    ├─→ Check Binance status page
    │   ├─ "Maintenance": Wait 30 min, document as expected downtime
    │   ├─ "Operational": Proceed to next step
    │
    ├─→ Check logs for "rate limit" (429)
    │   ├─ Found: IP blocked, wait 60s, retry (don't page)
    │   ├─ Not found: Proceed to next step
    │
    ├─→ Check network connectivity
    │   ├─ Binance unreachable: Network partition (page DevOps)
    │   ├─ Binance reachable: Proceed to next step
    │
    └─→ Multiple reconnection failures
        └─ Page engineer (debugging needed)
```

---

## Post-Recovery Verification

### Checklist After WebSocket Recovers

- [ ] **Prices flowing?** - `curl http://localhost:8000/api/portfolio/positions | jq '.prices_timestamp'` shows recent time
- [ ] **No stale warnings?** - `grep "stale" /var/log/crypto-daytrading/*.log | tail -5` shows no recent warnings
- [ ] **Circuit breaker CLOSED?** - `curl http://localhost:8000/api/safety/circuit-breaker | jq '.state'` shows "CLOSED"
- [ ] **Trading resumed?** - `curl http://localhost:8000/api/autonomous/status | jq '.trading_active'` shows true
- [ ] **Database syncing?** - Check PRIMARY and BACKUP databases have same latest trade timestamp

### Log Inspection

```bash
# Verify recovery completed successfully
grep -A 5 "WebSocket reconnect success" /var/log/crypto-daytrading/*.log | tail -10

# Check if any orders were missed (should be empty or few)
grep "order.*rejected\|trade.*skipped" /var/log/crypto-daytrading/*.log | wc -l

# Ensure no circuit breaker trips during recovery
grep "circuit.*trip" /var/log/crypto-daytrading/*.log | tail -5
```

### Performance Check

```bash
# Verify Skill #1 metrics (reconnection success rate)
curl -s http://localhost:8000/api/monitoring/health/websocket | jq '{
  staleness_max_seconds: .max_staleness,
  reconnect_attempts_total: .reconnect_attempts,
  reconnect_success_rate: .success_rate,
  avg_recovery_time: .avg_recovery_seconds
}'

# Expected values:
# - staleness_max_seconds: <30 (should stay under 30s)
# - reconnect_attempts: Small number (1-2 per 24h is normal)
# - success_rate: >95% (most reconnections should work)
# - avg_recovery_time: <20 seconds
```

---

## Summary

| Step | Action | Expected Outcome |
|------|--------|------------------|
| **Detect** | Monitor alert or manual check | Confirm WebSocket stale >30s |
| **Auto-Recover** | Skill #1 retries (2s, 4s, 8s backoff) | Connection re-established <60s |
| **Verify** | Check `/api/monitoring/health/websocket` | Status = "connected", staleness = <10s |
| **Escalate** | If >90s, page engineer | Engineer investigates network/Binance |
| **Post-Recovery** | Check logs, verify circuit breaker closed | Trading resumes normally |

**Success = Prices flowing, circuit breaker CLOSED, trading active within 60 seconds**
