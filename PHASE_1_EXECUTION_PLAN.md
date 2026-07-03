# Phase 1 Execution Plan: Critical Analysis Gaps

**Approved:** 2026-07-03  
**Duration:** 1 week (Jul 3-10)  
**Effort:** 32-44 hours  
**Team:** 1-2 people  
**Status:** READY TO START

---

## Overview: 4 Critical Gaps to Close This Week

| # | Gap | Why First | Hours | Owner | Status |
|---|-----|-----------|-------|-------|--------|
| 1 | **Performance Baseline** | Validates NFRs met | 6-8h | Platform Eng | ⏳ Starting |
| 2 | **Runbooks** | Needed for deployment safety | 12-16h | Ops Eng | ⏳ Starting |
| 3 | **Traceability Matrix** | Know what's implemented | 8-12h | Developer | ⏳ Queued |
| 4 | **API Contract** | Onboard users/developers | 6-8h | Tech Writer | ⏳ Queued |

**Total:** 32-44 hours → "System is operationally ready" ✅

---

## Gap 1: Performance Baseline (6-8 hours)

### What to Deliver
```
PERFORMANCE_BASELINE.md
├─ Signal Latency (NFR-001: target <500ms)
│  └─ Actual: P50/P99/Max measured
├─ Order Execution Speed (NFR-002: target <2s)
│  └─ Actual: P50/P99/Max measured
├─ Candle Fetch Latency (NFR-003: target <2s batch)
│  └─ Actual: measured for 400 candles
├─ Throughput (NFR-004: target ≥100 trades/day)
│  └─ Actual: measured from logs
├─ Memory Usage (NFR-005: target <500MB)
│  └─ Actual: peak measured over 24h
├─ RTO Failover Time (NFR-008: target <30s)
│  └─ Actual: measured in current state (likely 6+ min due to split-brain)
└─ Pass/Fail Summary
   ├─ Meeting NFRs: ✅ or ❌ for each
   └─ Recommendations: What to prioritize
```

### How to Measure

**Test 1: Signal Latency**
```bash
# Measure: Time from price update to signal generation
cd /home/vali/projects/crypto-daytrading
python3 -c "
import time
import backend.trading.autonomous_trader.core as trader

# Simulate 100 trading loops with prices
for i in range(100):
    start = time.time()
    # Simulate getting prices and generating signals
    elapsed = time.time() - start
    print(f'Loop {i}: {elapsed*1000:.2f}ms')
" > /tmp/signal_latency.log

# Analyze
python3 -c "
import statistics
times = [float(line.split(': ')[1].split('ms')[0]) for line in open('/tmp/signal_latency.log')]
print(f'P50: {statistics.median(times):.1f}ms')
print(f'P99: {sorted(times)[int(len(times)*0.99)]:.1f}ms')
print(f'Max: {max(times):.1f}ms')
print(f'Target: <500ms')
print(f'Status: {'PASS' if sorted(times)[int(len(times)*0.99)] < 500 else 'FAIL'}')
"
```

**Test 2: Order Execution Speed**
```bash
# Measure: Time from order creation to Binance confirmation
# Use recent log entries showing order execution times

grep "Order executed in" /home/vali/projects/crypto-daytrading/logs/api.log | \
  awk '{print $(NF-1)}' | \
  sort -n | \
  awk '
    BEGIN { count=0; sum=0; }
    { 
      times[count++] = $1
      sum += $1
    }
    END {
      print "P50: " times[int(count*0.50)] "s"
      print "P99: " times[int(count*0.99)] "s"
      print "Max: " times[count-1] "s"
      print "Target: <2s"
      print "Status: " (times[int(count*0.99)] < 2 ? "PASS" : "FAIL")
    }
  '
```

**Test 3: Candle Fetch Latency**
```bash
# Measure: Time to fetch 400 candles (100 symbols × 4 timeframes)
# Use Binance API calls from logs

grep "Fetched.*candles" /home/vali/projects/crypto-daytrading/logs/api.log | \
  head -100 | \
  awk '{print $(NF-3)}' | \
  sort -n | \
  awk '
    BEGIN { count=0; }
    { 
      times[count++] = $1
    }
    END {
      print "P50: " times[int(count*0.50)] "s"
      print "P99: " times[int(count*0.99)] "s"
      print "Max: " times[count-1] "s"
      print "Target: <2s batch"
      print "Status: " (times[int(count*0.99)] < 2 ? "PASS" : "FAIL")
    }
  '
```

**Test 4: Throughput**
```bash
# Measure: Trades per day from logs
grep -c "Order executed" /home/vali/projects/crypto-daytrading/logs/api.log
# Divide by number of days to get trades/day

python3 -c "
from datetime import datetime
import re

with open('/home/vali/projects/crypto-daytrading/logs/api.log') as f:
    dates = set()
    trade_count = 0
    for line in f:
        if 'Order executed' in line:
            # Extract date from log line
            match = re.search(r'(\d{4}-\d{2}-\d{2})', line)
            if match:
                dates.add(match.group(1))
                trade_count += 1

days = len(dates)
trades_per_day = trade_count / days if days > 0 else 0
print(f'Total trades: {trade_count}')
print(f'Days active: {days}')
print(f'Trades/day: {trades_per_day:.1f}')
print(f'Target: ≥100 trades/day')
print(f'Status: {'PASS' if trades_per_day >= 100 else 'FAIL'} (but OK for paper trading)')
"
```

**Test 5: Memory Usage**
```bash
# Measure: Peak memory during 24h window
# From logs: look for memory reports or use ps

# If monitoring available:
ps aux | grep autonomous_trader | awk '{print $6}' # Shows RSS in KB

# Or from Docker stats (if containerized):
# docker stats crypto-daytrading --no-stream | grep -v CONTAINER

# Manual check: Parse logs for memory reports
grep "Memory:" /home/vali/projects/crypto-daytrading/logs/*.log | \
  awk '{print $(NF-2)}' | \
  sort -n | \
  tail -1
# Should be <500MB

echo "Peak memory: $(ps aux | grep autonomous_trader | awk '{print $6}' | sort -rn | head -1) KB"
echo "Target: <500MB"
```

**Test 6: RTO (Failover Time)**
```bash
# Measure: Time from PRIMARY failure to BACKUP taking over
# From logs: search for failover events

grep -A 10 "PRIMARY FAILURE DETECTED" /home/vali/projects/crypto-daytrading/logs/api.log | \
  grep "BACKUP.*trading" | \
  head -1
# Calculate time difference between "PRIMARY FAILURE" and "BACKUP trading"

python3 -c "
import re
from datetime import datetime

log_file = '/home/vali/projects/crypto-daytrading/logs/api.log'
with open(log_file) as f:
    lines = f.readlines()

failure_time = None
backup_time = None

for line in lines:
    if 'PRIMARY FAILURE DETECTED' in line and not failure_time:
        match = re.search(r'(\d{2}:\d{2}:\d{2})', line)
        if match:
            failure_time = match.group(1)
    if 'BACKUP.*taking over' in line and failure_time:
        match = re.search(r'(\d{2}:\d{2}:\d{2})', line)
        if match:
            backup_time = match.group(1)
            break

if failure_time and backup_time:
    # Simple calculation (assumes same day)
    f_h, f_m, f_s = map(int, failure_time.split(':'))
    b_h, b_m, b_s = map(int, backup_time.split(':'))
    elapsed = (b_h*3600 + b_m*60 + b_s) - (f_h*3600 + f_m*60 + f_s)
    print(f'RTO (failover time): {elapsed}s')
    print(f'Target: <30s')
    print(f'Status: {'PASS' if elapsed < 30 else 'FAIL'}')
else:
    print('No recent failover detected in logs')
    print('Target: <30s')
    print('Status: UNTESTED')
"
```

### Acceptance Criteria
- ✅ Collect 6 performance metrics
- ✅ Compare each to NFR target
- ✅ Document pass/fail status
- ✅ Identify which metrics block production deployment

### Output
`PERFORMANCE_BASELINE.md` with:
- Current vs target for each metric
- Detailed measurement methodology
- Recommendations for improvement
- Go/No-go for production

---

## Gap 2: Runbooks (12-16 hours)

### What to Deliver
```
RUNBOOKS/ directory with 6 procedures:
├─ RUNBOOK_WEBSOCKET_FAILURE.md
├─ RUNBOOK_CIRCUIT_BREAKER_OPEN.md
├─ RUNBOOK_DATABASE_FAILURE.md
├─ RUNBOOK_PRIMARY_FAILURE.md
├─ RUNBOOK_SPLIT_BRAIN.md
└─ RUNBOOK_DECISION_TREE.md
```

Each runbook:
- **Detection:** How do we know this happened? (alert, symptoms)
- **Root Cause:** Why did it happen?
- **Recovery Steps:** What do we do? (manual + automated)
- **Timeline:** How long should recovery take?
- **Escalation:** When to involve others

### Runbook 1: WebSocket Failure

```markdown
# RUNBOOK: WebSocket Connection Failure

## Detection
- Alert: "WebSocket stale >30s"
- Symptoms: Orders not placing, prices frozen
- Log signature: "ERROR: [BTCUSDT] CRITICAL staleness: XXs > 15s"

## Root Cause Analysis
1. Binance API is down (external)
2. Network connectivity issue (internal/ISP)
3. Binance rate limit exceeded (rate limiting)
4. WebSocket connection dropped (transient)

## Recovery Procedure

### Immediate (Automated - Skill #1)
1. Skill #1 detects staleness at 15s
2. Initiates reconnect with backoff (2s, 4s, 8s)
3. Attempts up to 3 reconnections
4. If successful: Resume trading ✅

### If Automated Recovery Fails (Manual)
1. Check Binance status: https://status.binance.com
   - If DOWN: Wait for status page update, monitor logs
   - If UP: Continue to step 2
2. Check network connectivity: `ping api.binance.com`
   - If timeout: Check ISP/firewall, escalate to DevOps
   - If OK: Continue to step 3
3. Check API logs for rate limit errors
   - If rate limited: Reduce request frequency, contact support
   - If not: Continue to step 4
4. Restart WebSocket connection manually (optional, Skill #1 should handle)
   - POST /admin/reconnect-websocket
5. Monitor for 5 minutes (should see prices flowing)
   - If OK: Incident closed ✅
   - If still failing: Escalate to platform team

## Timeline
- **0s:** Alert triggered
- **15s:** Skill #1 detects + starts recovery
- **20s:** First reconnect attempt (2s backoff)
- **30s:** Second attempt (4s backoff)
- **45s:** Third attempt (8s backoff)
- **60s:** Give up, escalate if manual intervention needed

**Target RTO:** <60 seconds (automated)

## Escalation
- If not recovered in 60s: Page on-call engineer
- If Binance down: Wait, no action needed
- If network down: Escalate to DevOps
```

### Runbook 2: Circuit Breaker Open

```markdown
# RUNBOOK: Circuit Breaker Opened (Trading Halted)

## Detection
- Alert: "Circuit breaker OPEN for >1 minute"
- Symptoms: New orders blocked, only exits allowed
- Log signature: "Circuit breaker OPEN after N failures"

## Root Cause Analysis
- Trigger: Usually WebSocket staleness or Binance API failures
- Effect: System stops new entries (protective measure)

## Recovery Procedure

### Automatic (Timeout)
- Circuit breaker auto-resets after 60-120 seconds
- No manual action needed
- Monitor logs for successful reset

### Manual Reset (If Urgent)
1. Verify root cause is resolved
   - Check WebSocket is streaming fresh prices
   - Check Binance API responding
2. Reset circuit breaker: `POST /admin/reset-breaker`
3. Verify: `curl http://localhost:8000/api/monitoring/health`
   - Should show: "circuit_breaker": "CLOSED"
4. Resume trading (system auto-resumes)

## Timeline
- **0s:** Circuit breaker opens (protective)
- **60-120s:** Auto-resets (if issue resolved)
- **0s (manual):** Can reset immediately after verifying fix

**Target RTO:** <120 seconds (automatic) or <30 seconds (manual)

## Phase 2 Note
After circuit breaker reset phase, this will be fully automated.
```

### Runbook 3: Database Failure

```markdown
# RUNBOOK: Database Connection Lost

## Detection
- Alert: "Database connection failed"
- Symptoms: Can't save trades, system may crash
- Log signature: "ERROR: Database connection lost"

## Root Cause Analysis
1. PostgreSQL/SQLite process crashed
2. Disk full (can't write)
3. Network partition (for remote DB)
4. Authentication failed (credentials wrong)

## Recovery Procedure

1. Check database process running
   - SQLite: `file /path/to/trading.db` (should exist)
   - PostgreSQL: `ps aux | grep postgres`

2. If not running: Start it
   - SQLite: No action (auto-created on first write)
   - PostgreSQL: `systemctl start postgres`

3. Check disk space: `df -h /var/lib/`
   - If >90% full: Delete old logs or add storage
   - If OK: Continue

4. Test database connection
   - SQLite: `python3 -c "import sqlite3; sqlite3.connect('/path/to/trading.db').execute('SELECT 1')"`
   - PostgreSQL: `psql -U postgres -c "SELECT 1"`

5. Restart trading system
   - `systemctl restart crypto-daytrading` (or manual restart)

6. Verify: `curl http://localhost:8000/api/paper/account`
   - Should return account balance
   - If error: Check logs for details

## Timeline
- **0s:** Alert triggered
- **5min:** Should recover (depends on root cause)

**Target RTO:** <5 minutes

## Escalation
- If disk full: Escalate to DevOps
- If PostgreSQL won't start: Escalate to DBA
- If data corruption suspected: Restore from backup
```

### Runbook 4: PRIMARY Machine Failure

```markdown
# RUNBOOK: PRIMARY Machine Failure

## Detection
- Alert: "PRIMARY heartbeat timeout (3x failed)"
- Symptoms: Trading paused briefly, then resumes on BACKUP
- Log signature: "PRIMARY DECLARED DEAD after 3 failures"

## Root Cause Analysis
1. PRIMARY machine powered off
2. Network partition (can't reach PRIMARY)
3. PRIMARY process crashed (Python interpreter died)
4. PRIMARY disk full (can't respond to health checks)

## Recovery Procedure

### Automatic (HA Takes Over)
1. BACKUP detects PRIMARY heartbeat failure
2. Confirms failure via split-brain check
3. Takes over: Starts autonomous trader
4. Resumes trading within 30s

**Note:** After split-brain fix, this should be fully automatic.

### Manual (If Auto-Failover Stuck)
1. Verify PRIMARY is actually down
   - Try SSH: `ssh user@primary-ip`
   - Try curl: `curl http://primary-ip:8001/api/health`
   - If both timeout: PRIMARY is unreachable

2. If PRIMARY is down: Let BACKUP handle it
   - Verify BACKUP is trading: `curl http://backup-ip:8002/api/paper/account`
   - If trading: Incident resolved ✅
   - If not trading: See RUNBOOK_SPLIT_BRAIN

3. Investigate PRIMARY
   - Power cycle machine (if in data center)
   - Check network connectivity
   - Check disk space
   - Check Python process status

4. Restore PRIMARY when ready
   - May take 30-60 minutes for full provisioning
   - After PRIMARY comes back: DATABASE SYNC needed

## Timeline
- **0s:** PRIMARY stops responding
- **15s:** BACKUP detects failure (3 × 5s heartbeat interval)
- **30s:** BACKUP takes over, resumes trading
- **5-10min:** Operator investigates PRIMARY

**Target RTO:** <30 seconds (automatic via HA)

## Post-Recovery: Database Sync
When PRIMARY comes back online:
1. Sync latest data from BACKUP → PRIMARY
   - Should be automatic (see code)
   - Verify: `SELECT COUNT(*) FROM trades` (should match BACKUP)
2. Once synced: PRIMARY can take over again

## Escalation
- If BACKUP can't take over: Page on-call immediately
- If both PRIMARY and BACKUP down: Major incident (restore from backup)
```

### Runbook 5: Split-Brain Detection

```markdown
# RUNBOOK: Split-Brain Detected (Both Machines Think They're Primary)

## Detection
- Alert: "SPLIT-BRAIN DETECTED - both PRIMARY and BACKUP are healthy"
- Symptoms: Possible duplicate orders, confusion in logs
- Log signature: "🚨 SPLIT-BRAIN DETECTED"

## Root Cause Analysis
- Heartbeat timeout threshold too aggressive (3s)
- Or: Network latency spike
- After split-brain fix: Should rarely occur

## Recovery Procedure

### Current State (Before Phase 2 Fix)
1. Detection: System detects both machines responding
2. Action: Halts all trades to prevent duplicates (safety mode)
3. Manual: Operator must investigate

### Automated (After Phase 2 Fix)
1. Detection: System detects split-brain
2. Coordination: PRIMARY wins (source of truth), BACKUP yields
3. Result: No trading halt, automatic resolution

### Manual Recovery (If Stuck)
1. Check PRIMARY is responding: `curl http://primary-ip:8001/api/health`
2. Check BACKUP is responding: `curl http://backup-ip:8002/api/health`
3. If both responding: Verify network connectivity between them
4. Designate PRIMARY as authority: It wins
5. Make BACKUP yield: Stop trading on BACKUP
   - `curl -X POST http://backup-ip:8002/admin/stop-trading`
6. Resume PRIMARY trading: `curl -X POST http://primary-ip:8001/admin/resume-trading`
7. Verify no duplicates: Check audit trail
   - `SELECT * FROM trades WHERE (symbol, time) IN (SELECT symbol, time FROM trades GROUP BY symbol, time HAVING COUNT(*) > 1)`

## Timeline
- **0s:** Split-brain detected
- **0-60s:** Automatic resolution (after Phase 2 fix)
- **N/A:** Manual investigation if stuck

**Target RTO:** <60 seconds

## Escalation
- If stuck >5 minutes: Page on-call engineer
- If duplicates found: Alert finance/risk team
```

### Runbook 6: Decision Tree

```markdown
# DECISION TREE: "System Not Trading - What Do I Do?"

```
SYSTEM NOT TRADING
├─ Q1: Is WebSocket connected?
│  ├─ Check: curl http://localhost:8000/api/monitoring/health/websocket
│  ├─ If NO staleness, prices <5s old → YES, Continue to Q2
│  ├─ If staleness >15s → NO, See RUNBOOK_WEBSOCKET_FAILURE
│  └─ If staleness 5-15s → YES (Skill #1 recovering), Wait 20s then recheck
│
├─ Q2: Is Circuit Breaker CLOSED?
│  ├─ Check: curl http://localhost:8000/api/monitoring/health | grep circuit_breaker
│  ├─ If "CLOSED" → YES, Continue to Q3
│  ├─ If "OPEN" → NO, See RUNBOOK_CIRCUIT_BREAKER_OPEN
│  └─ If "HALF_OPEN" → Likely recovering, Wait 30s then recheck
│
├─ Q3: Is HA Healthy?
│  ├─ Check: curl http://localhost:8000/api/monitoring/ha-status
│  ├─ If "PRIMARY_ACTIVE" or "BACKUP_ACTIVE" → YES, Continue to Q4
│  ├─ If "BOTH_HEALTHY" (split-brain) → ALERT, See RUNBOOK_SPLIT_BRAIN
│  ├─ If "BOTH_DEAD" → CRITICAL, See runbook below
│  └─ If "PRIMARY_DEAD" → Failover in progress, Wait 30s
│
└─ Q4: Is Database Responding?
   ├─ Check: curl http://localhost:8000/api/paper/account
   ├─ If returns balance → YES, System should trade
   │  └─ If still not trading: Escalate (unusual, check logs)
   └─ If ERROR → Database issue, See RUNBOOK_DATABASE_FAILURE

ESCALATION: If you answered YES to all 4 questions and system still isn't trading:
- Collect logs from /logs/api.log
- Contact platform team with incident details
- Have rollback plan ready
```
```

### Effort Breakdown
- Runbook 1 (WebSocket): 2 hours
- Runbook 2 (Circuit Breaker): 1.5 hours
- Runbook 3 (Database): 2 hours
- Runbook 4 (PRIMARY Failure): 2 hours
- Runbook 5 (Split-Brain): 2 hours
- Runbook 6 (Decision Tree): 1.5 hours
- Review + refinement: 1.5 hours

**Total:** 12-13 hours

---

## Gap 3: Traceability Matrix (8-12 hours)

### What to Deliver
```
TRACEABILITY_MATRIX.md
├─ FR-001: Binance API Integration
│  ├─ Code files: backend/exchange/binance_manager.py (lines 1-150)
│  ├─ Tests: tests/exchange/test_binance.py
│  ├─ Status: IMPLEMENTED ✅
│  ├─ Test Status: 2/3 passing ⚠️
│  └─ Validation: COMPLETE
├─ FR-002: Paper Trading Engine
│  └─ ... (all FRs)
└─ Coverage Summary
   ├─ Implemented: 25/25 FRs (100%)
   ├─ Tested: 23/25 (92%)
   ├─ Passing: 21/25 (84%)
   └─ Gaps: FR-X, FR-Y, FR-Z need fixes
```

### How to Build

**Step 1: Extract all FRs from FUNCTIONAL_REQUIREMENTS.md**
```bash
grep "^### FR-" /home/vali/projects/crypto-daytrading/FUNCTIONAL_REQUIREMENTS.md | \
  awk '{print $2}' | \
  sort | \
  uniq
# Output: FR-001, FR-002, ... FR-025
```

**Step 2: Find code files for each FR**
```bash
# For each FR, search codebase:
# Example: FR-001 (Binance API Integration)
find /home/vali/projects/crypto-daytrading/backend -type f -name "*.py" | \
  xargs grep -l "binance" | \
  head -5
# Output: backend/exchange/binance_manager.py, etc.
```

**Step 3: Find tests for each FR**
```bash
find /home/vali/projects/crypto-daytrading/tests -type f -name "*.py" | \
  xargs grep -l "FR-001\|binance" | \
  head -5
```

**Step 4: Check test status**
```bash
cd /home/vali/projects/crypto-daytrading
pytest tests/ -v --tb=short 2>&1 | \
  grep "PASSED\|FAILED\|ERROR" | \
  grep -i "FR-001\|binance"
```

**Step 5: Build matrix**
```python
# Create TRACEABILITY_MATRIX.md with:
# FR → Code file(s) → Test file(s) → Status

# Automation:
# 1. Parse FUNCTIONAL_REQUIREMENTS.md for all FRs
# 2. For each FR, grep codebase for implementation
# 3. For each FR, grep tests for validation
# 4. Run pytest to get pass/fail status
# 5. Generate markdown table
```

### Effort
- Extract FRs: 1 hour
- Map code files: 3-4 hours
- Map test files: 2-3 hours
- Run tests + compile results: 1 hour
- Document + formatting: 1-2 hours

**Total:** 8-11 hours

---

## Gap 4: API Contract (6-8 hours)

### What to Deliver
```
API_CONTRACT.md (or api_spec.json in OpenAPI format)

GET /api/paper/account
  Summary: Get paper trading account balance
  Parameters: none
  Response: {
    "cash": 1220.41,
    "equity": 1441.97,
    "pnl": 221.56,
    "currency": "EUR"
  }
  Status Codes: 200, 500
  Rate Limit: 100 req/min

POST /api/paper/order
  Summary: Place simulated order
  Parameters:
    symbol (BTCUSDT, ETHUSDT)
    side (BUY, SELL)
    quantity (float)
    order_type (MARKET, LIMIT)
  Response: { "order_id": "123", "status": "FILLED" }
  Status Codes: 200, 400, 500

... (all 30+ endpoints)
```

### How to Build

**Step 1: Extract all endpoints from code**
```bash
grep -r "@app.get\|@app.post\|@app.put\|@app.delete" /home/vali/projects/crypto-daytrading/backend/api/ | \
  grep -o '"/api/[^"]*"' | \
  sort | \
  uniq
# Output: /api/health, /api/paper/account, /api/paper/order, ...
```

**Step 2: Document each endpoint**
- Endpoint path + method
- Summary (1 line)
- Parameters (if any)
- Response schema
- Status codes
- Rate limits

**Step 3: Add examples**
```bash
curl http://localhost:8000/api/paper/account
# Returns: {"cash": 1220.41, "equity": 1441.97, ...}
```

**Step 4: Generate OpenAPI spec (optional)**
```bash
# Can use automated tools:
# - fastapi-openapi-generator
# - swagger-ui
# - ReDoc
```

### Effort
- Extract endpoints: 1 hour
- Document parameters: 2-3 hours
- Document responses: 2-3 hours
- Add examples: 1 hour

**Total:** 6-8 hours

---

## Execution Schedule (This Week)

```
JUL 3 (Wed) - TODAY
├─ 🟢 Create Phase 1 Execution Plan (this document)
├─ 🟢 Brief team on gaps + priorities
└─ 🟢 Assign owners + start Gap 1 (Performance Baseline)

JUL 4 (Thu) - DAY 2
├─ 🔵 Gap 1: Performance Baseline (6-8h work)
│  └─ Run benchmarks, measure latencies
├─ 🔵 Gap 2: Start Runbooks skeleton (2-3h)
│  └─ Start RUNBOOK_WEBSOCKET_FAILURE.md
└─ 🔵 Gap 3: Start Traceability Matrix (2-3h)
   └─ Extract all FRs from requirements

JUL 5 (Fri) - DAY 3
├─ 🔵 Gap 1: Finish Performance Baseline (finalize report)
├─ 🔵 Gap 2: Continue Runbooks (3-4h)
│  └─ Complete WebSocket, Circuit Breaker, Database
└─ 🔵 Gap 3: Map code files to FRs (3-4h)

JUL 6 (Sat) - DAY 4
├─ 🔵 Gap 2: Finish Runbooks (2-3h)
│  └─ Add Decision Tree, review all
├─ 🔵 Gap 3: Finish Traceability Matrix (2-3h)
│  └─ Compile final report
└─ 🔵 Gap 4: Start API Contract (2-3h)
   └─ Extract endpoints

JUL 7 (Sun) - DAY 5
├─ 🔵 Gap 4: Finish API Contract (3-4h)
├─ ✅ Review all 4 deliverables
└─ ✅ Compile into Phase 1 Summary Report

JUL 8-10 - BUFFER/REFINEMENT
├─ Fix any incomplete sections
├─ Get stakeholder feedback
└─ Prepare for Phase 2 (Week 2)
```

---

## Parallel Tracks (Non-Blocking)

**While Phase 1 analysis happens:**
- ✅ Crypto split-brain fix (Jul 4-7)
- ✅ Investing-platform Phase 1 impl (Jul 4-7)

**All can proceed simultaneously (different owners)**

---

## Success Criteria

### Gap 1: Performance Baseline ✅
- [ ] 6 metrics measured (Signal, Order, Candle, Memory, Throughput, RTO)
- [ ] Each compared to NFR target
- [ ] Pass/Fail documented
- [ ] Recommendations identified

### Gap 2: Runbooks ✅
- [ ] 6 runbooks written (WebSocket, CB, DB, PRIMARY, Split-brain, Decision Tree)
- [ ] Each has: Detection, Root Cause, Recovery Steps, Timeline, Escalation
- [ ] Reviewed by ops team
- [ ] Ready for production use

### Gap 3: Traceability Matrix ✅
- [ ] All 25+ FRs mapped to code files
- [ ] All FRs mapped to test files
- [ ] Test status collected (Passed/Failed/Pending)
- [ ] Coverage % calculated

### Gap 4: API Contract ✅
- [ ] All 30+ endpoints documented
- [ ] Parameters, responses, status codes for each
- [ ] Examples provided
- [ ] Ready for API users

---

## Output: Phase 1 Summary Report

After all 4 gaps complete, create:

```
PHASE_1_SUMMARY_REPORT.md
├─ Executive Summary
│  ├─ System is operationally ready: YES/NO
│  ├─ Blockers for production: [list]
│  └─ Recommendations: [list]
├─ Gap 1: Performance Baseline
│  ├─ Status: PASS/FAIL
│  └─ Highlights: [key findings]
├─ Gap 2: Runbooks
│  ├─ Status: COMPLETE
│  └─ Coverage: 6/6 runbooks
├─ Gap 3: Traceability Matrix
│  ├─ Status: COMPLETE
│  ├─ FR coverage: X%
│  └─ Test coverage: Y%
├─ Gap 4: API Contract
│  ├─ Status: COMPLETE
│  └─ Endpoints documented: 30+
└─ Readiness Assessment
   ├─ Functional completeness: X%
   ├─ Operational readiness: X%
   └─ Production readiness: X%
```

---

## Resources Needed

### Tools
- Python 3.11+ (already installed)
- Bash (analysis scripts)
- Git (check commit history for performance)
- Pytest (run tests)

### Knowledge
- Understanding of FR/NFR
- System architecture (have this: SYSTEM_ARCHITECTURE.md)
- Operations procedures (learning from logs)
- Test framework (pytest knowledge)

### People
- 1-2 people for 1 week
- 30-40 hours total effort
- Can work in parallel on different gaps

---

## Getting Started

**TODAY (RIGHT NOW):**

1. Decide: Do you want me to start on Gap 1 (Performance Baseline) manually?
2. Or spawn Agent to do it in parallel?
3. Confirm who owns each gap (you can do all 4, or assign to team)

**Recommendation:** Start Gap 1 immediately (performance is most valuable, fastest to measure)

Ready to start?
