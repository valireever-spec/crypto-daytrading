# RUNBOOK: Operational Decision Tree

**Last Updated:** 2026-07-03  
**Purpose:** Help ops engineers quickly diagnose and respond to issues  
**Related Runbooks:** All others (this is the index)

---

## Quick Start: "System Not Trading - What Do I Do?"

```
START HERE
    │
    ├─→ [1] Is the system UP at all?
    │
    ├─→ [2] Can you reach the API?
    │
    ├─→ [3] Is WebSocket connected?
    │
    ├─→ [4] Is circuit breaker open?
    │
    ├─→ [5] Is HA showing split-brain?
    │
    ├─→ [6] Is database responsive?
    │
    └─→ [ESCALATE]
```

---

## Decision Tree: Full Flowchart

### [1] Is the System UP at All?

```
Q: Can you access the API at all?
   curl http://localhost:8000/api/monitoring/status

   YES (200 OK)
   └─→ Continue to [2] (API is responding)

   NO (Connection refused, timeout)
   └─→ PRIMARY PROCESS DOWN
       ├─→ Check: ps aux | grep autonomous
       ├─→ If not running: systemctl start crypto-daytrading-primary
       ├─→ Wait 15 seconds
       ├─→ Return to [1]
       
       └─→ If running but not responding:
           ├─→ Check logs: tail -100 /var/log/crypto-daytrading/api.log
           ├─→ Look for errors (exception, crash, etc)
           ├─→ See corresponding runbook (WebSocket, Database, etc)
           └─→ If no clear error: ESCALATE to engineer
```

### [2] Can You Reach the API?

```
Q: Does this work?
   curl -s http://localhost:8000/api/monitoring/status | jq '.trading_active'

   YES (true)
   └─→ System is UP and trading is ACTIVE
       └─→ Not a problem (no incident)

   NO (false)
   └─→ Trading is HALTED
       ├─→ Something is blocking trades
       └─→ Continue to [3]

   ERROR (can't parse, error message)
   └─→ API might be malformed
       ├─→ Check API logs: tail -50 /var/log/crypto-daytrading/api.log
       ├─→ Look for "500 Internal Server Error"
       ├─→ If found: ESCALATE (API code issue)
```

### [3] Is WebSocket Connected?

```
Q: Is WebSocket health good?
   curl -s http://localhost:8000/api/monitoring/health/websocket

   Response shows:
   {
     "status": "connected",
     "staleness_seconds": 3,
     "last_update": "2026-07-03T10:25:42Z"
   }

   ✅ HEALTHY
   └─→ WebSocket is fine, proceed to [4]

   ⚠️ STALE (staleness_seconds > 15)
   └─→ Prices frozen, WebSocket likely dead
       ├─→ See: RUNBOOK_WEBSOCKET_FAILURE.md
       ├─→ Follow: Steps 1-4 (auto-recovery should fix in 60s)
       ├─→ If not fixed in 60s: Proceed to Step 5 (manual)
       ├─→ Return to [3] after recovery

   ❌ DISCONNECTED (status != "connected")
   └─→ WebSocket not connected to Binance
       ├─→ See: RUNBOOK_WEBSOCKET_FAILURE.md
       ├─→ Follow: Same as STALE above
```

### [4] Is Circuit Breaker CLOSED?

```
Q: Check circuit breaker state
   curl -s http://localhost:8000/api/safety/circuit-breaker | jq '.state'

   Response: "CLOSED"
   └─→ ✅ Good, proceed to [5]

   Response: "OPEN"
   └─→ ❌ Circuit breaker is OPEN (trading halted for safety)
       ├─→ See: RUNBOOK_CIRCUIT_BREAKER_OPEN.md
       ├─→ This is usually caused by: WebSocket stale (most common)
       ├─→ Follow: Verify WebSocket health, then wait 60-120s
       ├─→ If >5 min still OPEN: Follow manual reset steps
       ├─→ Return to [4] after recovery

   Response: "HALF_OPEN"
   └─→ ⚠️ Recovery in progress (testing small orders)
       ├─→ Wait 10-30 seconds
       ├─→ Check again (should be CLOSED or back to OPEN)
       ├─→ If takes >2 min: Follow RUNBOOK_CIRCUIT_BREAKER_OPEN.md
```

### [5] Is HA Showing Split-Brain?

```
Q: Check split-brain status (on BACKUP machine)
   curl -s http://192.168.3.25:8002/api/ha/split-brain-status

   Response: {"detected": false}
   └─→ ✅ No split-brain, proceed to [6]

   Response: {"detected": true}
   └─→ ❌ SPLIT-BRAIN DETECTED (both machines think they're active)
       ├─→ See: RUNBOOK_SPLIT_BRAIN.md
       ├─→ This is a KNOWN BUG (Phase 1 issue)
       ├─→ Trading will be HALTED
       ├─→ Follow: Option A or B (kill one machine or restart both)
       ├─→ Typical fix time: 5-10 minutes
       ├─→ Return to [5] after restart

   Response: Can't reach BACKUP
   └─→ ⚠️ BACKUP machine unreachable
       ├─→ See: RUNBOOK_PRIMARY_FAILURE.md
       ├─→ This might indicate PRIMARY failure
       ├─→ Proceed to [6], or check if BACKUP is down
       ├─→ Return to [5] after BACKUP recovery
```

### [6] Is Database Responsive?

```
Q: Check database health
   curl -s http://localhost:8000/api/monitoring/health | jq '.database'

   Response: {"status": "healthy", "latency_ms": 5}
   └─→ ✅ Database is fine, proceed to ESCALATE (no obvious issue)

   Response: {"status": "error", "error": "Connection failed"}
   └─→ ❌ Database is DOWN (can't read/write trades)
       ├─→ See: RUNBOOK_DATABASE_FAILURE.md
       ├─→ Follow: Steps 1-3 (health check, disk space, integrity)
       ├─→ If corrupted: Restore from backup (Step 5)
       ├─→ Typical fix time: 2-5 minutes
       ├─→ Return to [6] after recovery

   Response: Can't reach API (timeout)
   └─→ ❌ API UNRESPONSIVE (not the database, but the API itself)
       ├─→ Go back to [1] (system might be crashing)
       ├─→ Check process: ps aux | grep autonomous
       ├─→ Check logs for crashes
       └─→ Restart if needed
```

### [ESCALATE] What to Do If Nothing Found

```
At this point, you've checked:
✅ API is responding
✅ WebSocket is connected
✅ Circuit breaker is closed
✅ No split-brain detected
✅ Database is healthy

But trading is STILL not happening

This is likely:
1. A logic issue (system won't generate signals)
2. A rare race condition
3. A new issue not covered above

ACTION:
├─→ Check logs for errors
│   grep -i "error\|exception\|fail" /var/log/crypto-daytrading/*.log | tail -50
│
├─→ Check if autonomous trader is running
│   curl -s http://localhost:8000/api/autonomous/status | jq '.'
│
├─→ Check account balance (might be zero)
│   curl -s http://localhost:8000/api/portfolio/positions | jq '.account_balance'
│
├─→ Gather info and PAGE ENGINEER
```

---

## Symptom-to-Runbook Mapping

| Symptom | Root Cause | Runbook |
|---------|-----------|---------|
| Prices frozen (no updates for 30s) | WebSocket down | [WEBSOCKET_FAILURE](RUNBOOK_WEBSOCKET_FAILURE.md) |
| No new orders placed | Circuit breaker OPEN | [CIRCUIT_BREAKER_OPEN](RUNBOOK_CIRCUIT_BREAKER_OPEN.md) |
| Can't save trades to DB | Database down/full | [DATABASE_FAILURE](RUNBOOK_DATABASE_FAILURE.md) |
| Trading halted, both machines responsive | Split-brain detected | [SPLIT_BRAIN](RUNBOOK_SPLIT_BRAIN.md) |
| BACKUP not responding, trading paused | PRIMARY died, failover starting | [PRIMARY_FAILURE](RUNBOOK_PRIMARY_FAILURE.md) |
| "Max recovery attempts exceeded" | Split-brain + heartbeat timeout | [SPLIT_BRAIN](RUNBOOK_SPLIT_BRAIN.md) + Phase 2 fix |
| Circuit breaker trips 10+ times/hour | WebSocket unstable or rate limited | [WEBSOCKET_FAILURE](RUNBOOK_WEBSOCKET_FAILURE.md) |
| API 500 error | Code crash or configuration issue | Check logs, ESCALATE |

---

## Quick Diagnostics: Copy-Paste Commands

### Comprehensive Health Check (Run All At Once)

```bash
echo "=== API Status ==="
curl -s http://localhost:8000/api/monitoring/status | jq '.trading_active' || echo "ERROR"

echo "=== WebSocket ==="
curl -s http://localhost:8000/api/monitoring/health/websocket | jq '{status, staleness}' || echo "ERROR"

echo "=== Circuit Breaker ==="
curl -s http://localhost:8000/api/safety/circuit-breaker | jq '.state' || echo "ERROR"

echo "=== Database ==="
curl -s http://localhost:8000/api/monitoring/health | jq '.database.status' || echo "ERROR"

echo "=== HA Status (BACKUP) ==="
curl -s http://192.168.3.25:8002/api/ha/status | jq '{role, split_brain: .split_brain_detected}' 2>/dev/null || echo "ERROR or BACKUP unreachable"

echo "=== Recent Errors ==="
tail -20 /var/log/crypto-daytrading/api.log | grep -i "error\|fail" || echo "No recent errors"
```

### One-Liner: "Is Trading Active?"

```bash
curl -s http://localhost:8000/api/autonomous/status | jq '.trading_active' && echo "✅ YES" || echo "❌ NO or ERROR"
```

### One-Liner: "What's Broken?"

```bash
# Shows which subsystems are NOT healthy
echo "API: $(curl -s http://localhost:8000/api/monitoring/status | jq -r '.status // "ERROR"')" && \
echo "WebSocket: $(curl -s http://localhost:8000/api/monitoring/health/websocket | jq -r '.status // "ERROR"')" && \
echo "CB: $(curl -s http://localhost:8000/api/safety/circuit-breaker | jq -r '.state // "ERROR"')" && \
echo "DB: $(curl -s http://localhost:8000/api/monitoring/health | jq -r '.database.status // "ERROR"')"
```

### Full Incident Report (For Engineer)

```bash
#!/bin/bash
echo "=== INCIDENT REPORT $(date) ===" > /tmp/incident.txt

echo -e "\n=== API RESPONSE ===" >> /tmp/incident.txt
curl -s -m 5 http://localhost:8000/api/monitoring/status >> /tmp/incident.txt 2>&1

echo -e "\n=== WEBSOCKET HEALTH ===" >> /tmp/incident.txt
curl -s -m 5 http://localhost:8000/api/monitoring/health/websocket >> /tmp/incident.txt 2>&1

echo -e "\n=== CIRCUIT BREAKER ===" >> /tmp/incident.txt
curl -s -m 5 http://localhost:8000/api/safety/circuit-breaker >> /tmp/incident.txt 2>&1

echo -e "\n=== HA STATUS ===" >> /tmp/incident.txt
curl -s -m 5 http://192.168.3.25:8002/api/ha/status >> /tmp/incident.txt 2>&1

echo -e "\n=== RECENT LOGS ===" >> /tmp/incident.txt
tail -50 /var/log/crypto-daytrading/api.log >> /tmp/incident.txt

echo -e "\n=== PROCESSES ===" >> /tmp/incident.txt
ps aux | grep -E "autonomous|crypto" >> /tmp/incident.txt

echo -e "\n=== DISK SPACE ===" >> /tmp/incident.txt
df -h /home/vali/projects/crypto-daytrading/ >> /tmp/incident.txt

echo "Report written to /tmp/incident.txt"
cat /tmp/incident.txt
```

---

## Escalation Criteria & Contact Info

### Severity Levels

| Level | Issue | RTO Target | Action |
|-------|-------|-----------|--------|
| **P1 (CRITICAL)** | No trading, >5 min downtime | <30 min | Page on-call engineer immediately |
| **P2 (HIGH)** | Degraded trading (CB open, WebSocket stale) | <5 min | Contact engineer, start fix |
| **P3 (MEDIUM)** | Frequent issues (<5 min each) | Monitoring | Document, track trends |
| **P4 (LOW)** | Minor alerts, auto-recovered | N/A | Log for post-mortem |

### When to Escalate

```
YES, PAGE ENGINEER if ANY of these:
├─ Trading completely halted >10 minutes
├─ Database corrupted (can't restore from backup)
├─ Both PRIMARY and BACKUP offline
├─ Split-brain lasting >15 minutes (can't recover)
├─ API crashes repeatedly
├─ Manual restart didn't work
└─ You're not sure and it's been >5 minutes

MAYBE, WAIT & MONITOR if:
├─ Circuit breaker OPEN (auto-recovery in 60-120s)
├─ WebSocket stale <90s (Skill #1 reconnecting)
├─ Heartbeat timeout but trading ongoing (might be split-brain, see runbook)
└─ Single process crash (auto-restart may work)

NO, DON'T PAGE if:
├─ Incident auto-recovered in <5 minutes
├─ Known issue with scheduled maintenance
├─ Upgrade or deployment in progress
└─ Test/staging environment (unless needed for demo)
```

### Contact Info Template

```
Engineer: [Name]
Phone: [Number]
Slack: @[Handle]
Email: [Email]

For: Code issues, debugging, unfamiliar errors

DevOps: [Name]
Phone: [Number]
For: Infrastructure, network, machine issues

Finance/Compliance: [Name]
For: Suspected data loss or duplicate orders
```

---

## Common Issues Quick Reference

### "I Just See Errors in Logs"

```bash
# Get last 20 errors
tail -100 /var/log/crypto-daytrading/api.log | grep -i "error\|exception"

# Common ones:
# - "WebSocket stale": See WEBSOCKET runbook
# - "Circuit breaker OPEN": See CIRCUIT_BREAKER runbook
# - "Database connection failed": See DATABASE runbook
# - "SPLIT-BRAIN DETECTED": See SPLIT_BRAIN runbook
# - "PRIMARY declared dead": See PRIMARY_FAILURE runbook
# - Other: Might need engineer

# Check error rate (how many in last hour?)
grep -c "ERROR" /var/log/crypto-daytrading/api.log
```

### "System Was Working, Now It's Not"

```bash
# 1. Check what changed
ps aux | grep -i crypto
# Is the process still running?

# 2. Check if anything restarted
journalctl -u crypto-daytrading-primary -n 20
# Any crashes or restarts?

# 3. Check recent errors
tail -50 /var/log/crypto-daytrading/api.log | grep -i "error\|fail"
# What failed?

# 4. Check resources
free -h; df -h /home/vali/projects/crypto-daytrading/
# Ran out of memory or disk?
```

### "Everything Looks Healthy But No Trading"

```bash
# Check if trading is explicitly paused
curl -s http://localhost:8000/api/autonomous/status | jq '.paused'

# Check if account has balance
curl -s http://localhost:8000/api/portfolio/positions | jq '.account_balance'

# Check if data quality too low
curl -s http://localhost:8000/api/autonomous/status | jq '.data_quality'
# If <80%: Maybe not enough price data

# Check if max position size reached
curl -s http://localhost:8000/api/portfolio/positions | jq '.total_notional_exposure'

# Otherwise: Might be intentionally not trading (strategy says hold)
# Check latest signals
curl -s http://localhost:8000/api/analytics/signals | jq '.signals | last'
```

---

## Post-Incident Checklist

After any incident is resolved, run this checklist:

### Immediate (Ops)

- [ ] System trading again? Verify: `curl http://localhost:8000/api/autonomous/status | jq '.trading_active'`
- [ ] No duplicate orders? Check: `sqlite3 /home/vali/projects/crypto-daytrading/data/trading.db "SELECT * FROM trades WHERE created_at > datetime('now', '-10 minutes') ORDER BY created_at DESC;"`
- [ ] Database consistent? Verify PRIMARY and BACKUP have same trade count
- [ ] Customers notified? (If trading was down >10 min)
- [ ] Logs gathered? `cp /var/log/crypto-daytrading/*.log /tmp/incident-$(date +%Y%m%d-%H%M%S)/`

### Within 1 Hour (Ops)

- [ ] Post-mortem started? Document: What happened, Timeline, Root cause, Fix
- [ ] Trending data: Is this a new issue or recurring?
- [ ] Any fixes needed? Or wait for Phase 2?
- [ ] Engineer notified? (If anything unusual)

### Within 24 Hours (Team)

- [ ] Post-mortem completed
- [ ] Action items assigned
- [ ] Issue added to backlog (if new)
- [ ] Runbook updated (if outdated)

---

## Tips for Ops Engineers

### 1. Always Check in This Order

1. Is API responding? (if not, restart process)
2. Is WebSocket connected? (if not, wait 60s for auto-recovery)
3. Is circuit breaker closed? (if not, wait 120s for auto-recovery)
4. Is database responding? (if not, see DB runbook)
5. Is split-brain detected? (if yes, see split-brain runbook)
6. Anything else? (escalate)

### 2. Use Watches for Real-Time Monitoring

```bash
# Watch system status every 5 seconds
watch -n 5 'curl -s http://localhost:8000/api/monitoring/status | jq "{trading: .trading_active, cb: .circuit_breaker_state, ws: .websocket_status}"'

# Exit with: Ctrl+C
```

### 3. Keep This Tab Open During Incidents

```
https://www.binance.us/en/support/announcement
(Check Binance status page in parallel)
```

### 4. Know the Difference Between:

- **"Stale"** = Data is old but connection alive (wait for Skill #1 reconnect)
- **"Dead"** = No connection, no data flowing (manual restart might be needed)
- **"Slow"** = Responding but >3s latency (might trigger split-brain, wait)

### 5. Don't Panic If:

- Circuit breaker OPEN for 60-120s (auto-recovery)
- WebSocket stale for 30-60s (Skill #1 reconnecting)
- Heartbeat fails once (might recover on retry)
- Brief trading halt (during HA failover)

### 6. Do Panic If:

- Trading halted >10 minutes
- Database corrupted (can't read trades)
- Both PRIMARY and BACKUP offline
- Can't connect to Binance (network issue?)
- Duplicate orders found

---

## Summary

```
┌─────────────────────────────────────────────────────┐
│     CRYPTO-DAYTRADING OPERATIONAL SUMMARY          │
├─────────────────────────────────────────────────────┤
│                                                     │
│ Healthy System Indicators:                          │
│ ✅ Trading: Active                                 │
│ ✅ WebSocket: Connected (stale < 10s)              │
│ ✅ Circuit Breaker: CLOSED                         │
│ ✅ Database: Healthy latency <10ms                 │
│ ✅ HA: No split-brain, PRIMARY/BACKUP in sync      │
│ ✅ Recent trades: Within last 2-5 minutes          │
│                                                     │
│ Unhealthy Indicators:                               │
│ ❌ Trading: Halted >5 min                           │
│ ❌ WebSocket: Stale >60s                            │
│ ❌ Circuit Breaker: OPEN >5 min                     │
│ ❌ Database: Error on query                         │
│ ❌ HA: Split-brain detected                         │
│ ❌ No new trades for >10 minutes                    │
│                                                     │
│ Typical Response Times:                             │
│ • WebSocket issue: 60-120s (auto)                  │
│ • Circuit breaker: 60-120s (auto)                  │
│ • Database issue: 2-5 min                           │
│ • Primary failure: <30s (after Phase 2 fix)        │
│ • Manual restart: 5-10 min total                    │
│                                                     │
│ Key Runbooks (In Order of Frequency):              │
│ 1. WEBSOCKET_FAILURE (stale prices)                │
│ 2. CIRCUIT_BREAKER_OPEN (trading halted)           │
│ 3. SPLIT_BRAIN (coordination issue)                │
│ 4. PRIMARY_FAILURE (HA failover)                   │
│ 5. DATABASE_FAILURE (data persistence)             │
│ 6. DECISION_TREE (this one, for diagnosis)         │
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

## Version History

| Date | Status | Changes |
|------|--------|---------|
| 2026-07-03 | Initial | Created 6 runbooks for Phase 1 (known bugs) |
| 2026-07-15 (planned) | Phase 2 | Update after split-brain, heartbeat fixes |
| 2026-08-01 (planned) | Phase 3 | Add manual failover controls, improved metrics |

---

**Always start with the Decision Tree. If you get stuck, use Symptom-to-Runbook mapping. When in doubt, PAGE ENGINEER.**
