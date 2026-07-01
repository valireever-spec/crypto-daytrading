# E2E Testing Quick Start — FR-016, FR-017, FR-020

**Tool:** playwright-testing-v2  
**Duration:** ~50 minutes for full test suite  
**Target:** Validate FR implementations with real API

---

## Quick Start (5 minutes)

### Step 1: Start the API

```bash
cd /home/vali/projects/crypto-daytrading
source venv/bin/activate
python -m uvicorn backend.api.main:app --host 0.0.0.0 --port 8001
```

Expected output:
```
INFO:     Application startup complete
INFO:     Uvicorn running on http://0.0.0.0:8001
```

### Step 2: Verify API is Running

```bash
curl http://localhost:8001/api/health
```

Expected response:
```json
{"status": "healthy", ...}
```

### Step 3: Run Smoke Tests

```bash
# Quick 5-minute smoke test
python -m pytest tests/ -k "emergency or crash or autonomous" -v --tb=short
```

---

## Full Test Suite

### Phase 1: Emergency Stop Tests (5 min)

```bash
# Test emergency stop endpoint
curl -X POST http://localhost:8001/api/emergency/stop \
  -H "Content-Type: application/json" \
  -d '{"reason": "E2E Test"}'

# Expected response:
# {"success": true, "positions_closed": 0, "timestamp": "...", "reason": "E2E Test"}

# Check status
curl http://localhost:8001/api/emergency/status

# Expected: {"active": true, ...}

# Reset (requires confirmation)
curl -X POST "http://localhost:8001/api/emergency/reset?confirm=true"

# Expected: {"message": "Emergency stop system reset", ...}
```

**Test Checklist:**
- [ ] Stop endpoint responds with 200
- [ ] Status shows active=true
- [ ] Reset requires confirm=true
- [ ] Reset clears flag

### Phase 2: Crash Detection Tests (10 min)

```bash
# Check crash status (no crash initially)
curl -X POST http://localhost:8001/api/emergency/close-all \
  -H "Content-Type: application/json" \
  -d '{"threshold_percent": 5.0, "lookback_minutes": 5, "min_candles": 3}'

# Expected: {"crash_detected": false, ...}

# Set crash threshold
curl -X POST "http://localhost:8001/api/emergency/set-crash-threshold?threshold_percent=3.0"

# Expected: {"threshold_percent": 3.0, ...}

# Verify status reflects threshold
curl http://localhost:8001/api/emergency/status
```

**Test Checklist:**
- [ ] No crash detected when no prices recorded
- [ ] Threshold config accepts 0-50%
- [ ] Rejects invalid thresholds
- [ ] Status reflects configured threshold

### Phase 3: Autonomous Trading Tests (15 min)

```bash
# Check autonomous status
curl http://localhost:8001/api/autonomous/status

# Expected: {"enabled": false, "running_now": false, ...}

# Configure overnight trading schedule
curl -X POST http://localhost:8001/api/autonomous/set-schedule \
  -H "Content-Type: application/json" \
  -d '{
    "enabled": true,
    "start_hour": 22,
    "start_minute": 0,
    "end_hour": 7,
    "end_minute": 0,
    "interval_minutes": 15
  }'

# Expected: {"enabled": true, "start_time": "22:00 UTC", ...}

# Enable autonomous
curl -X POST http://localhost:8001/api/autonomous/enable

# Expected: {"message": "Autonomous trading enabled", ...}

# Get next execution time
curl http://localhost:8001/api/autonomous/next-execution

# Expected: {"will_execute": true, "next_execution": "...", "seconds_until": 123, ...}

# Disable autonomous
curl -X POST http://localhost:8001/api/autonomous/disable

# Expected: {"message": "Autonomous trading disabled", ...}
```

**Test Checklist:**
- [ ] Schedule configuration accepted
- [ ] Enable/disable toggle works
- [ ] Next execution calculated correctly
- [ ] Status reflects current configuration

### Phase 4: Integration Test (10 min)

```bash
# Test interaction: Emergency stop blocks autonomous

# 1. Enable autonomous
curl -X POST http://localhost:8001/api/autonomous/enable

# 2. Check status (should show running_now depends on current time)
curl http://localhost:8001/api/autonomous/status

# 3. Trigger emergency stop
curl -X POST http://localhost:8001/api/emergency/stop \
  -H "Content-Type: application/json" \
  -d '{"reason": "Test interaction"}'

# 4. Check status (should show running_now: false)
curl http://localhost:8001/api/autonomous/status

# Expected: "running_now": false, "emergency_stop_active": true

# 5. Reset emergency stop
curl -X POST "http://localhost:8001/api/emergency/reset?confirm=true"

# 6. Check status (should restore running_now based on time)
curl http://localhost:8001/api/autonomous/status
```

**Test Checklist:**
- [ ] Autonomous blocked when emergency stop active
- [ ] running_now = false despite in time window
- [ ] Can reset and resume
- [ ] Emergency stop is hard block

---

## Automated Test Execution

### Using pytest (Unit Tests)

```bash
# Run all FR tests
python -m pytest tests/test_emergency_stop.py \
                  tests/test_crash_detector.py \
                  tests/test_autonomous.py \
                  -v --tb=short

# Expected: 24/43 tests passing (56%)
```

### Using playwright-testing-v2

```python
# Create test_e2e_runner.py
from playwright_testing_v2 import PlaywrightTestingV2

runner = PlaywrightTestingV2(api_url="http://localhost:8001")

# Define tests
tests = [
    {
        "name": "Emergency Stop",
        "url": "/api/emergency/stop",
        "method": "POST",
        "data": {"reason": "E2E Test"},
        "assert_status": 200,
        "assert_response_keys": ["success", "positions_closed"]
    },
    {
        "name": "Crash Detection",
        "url": "/api/emergency/close-all",
        "method": "POST",
        "data": {"threshold_percent": 5.0},
        "assert_status": 200,
        "assert_response_keys": ["crash_detected"]
    },
    {
        "name": "Autonomous Status",
        "url": "/api/autonomous/status",
        "method": "GET",
        "assert_status": 200,
        "assert_response_keys": ["enabled"]
    }
]

# Run tests
results = runner.run_tests(tests)

# Print results
for result in results:
    print(f"{result['test_name']}: {result['status']}")
```

---

## Performance Baseline Testing

### Measure Response Times

```bash
# Test 1: Emergency Stop Response Time
time curl -X POST http://localhost:8001/api/emergency/stop \
  -H "Content-Type: application/json" \
  -d '{"reason": "Perf test"}'

# Target: <100ms real time, <500ms total

# Test 2: Crash Detection Response Time
time curl -X POST http://localhost:8001/api/emergency/close-all \
  -H "Content-Type: application/json" \
  -d '{"threshold_percent": 5.0}'

# Target: <100ms real time

# Test 3: Status Check Response Time
time curl http://localhost:8001/api/autonomous/status

# Target: <10ms real time
```

### Load Testing (100 concurrent requests)

```bash
# Using Apache Bench
ab -n 100 -c 10 http://localhost:8001/api/autonomous/status

# Expected:
# Requests per second: >100
# Failed requests: 0
# Time per request: <50ms
```

---

## Troubleshooting

### API Won't Start

```bash
# Check if port 8001 already in use
lsof -i :8001

# Kill existing process
kill -9 <PID>

# Try again
python -m uvicorn backend.api.main:app --port 8001
```

### Test Failures

```bash
# Check logs
tail -f logs/api.log

# Run single test with verbose output
python -m pytest tests/test_emergency_stop.py::TestEmergencyStopTriggering::test_trigger_stops_trading -vv -s

# Check database state
sqlite3 data/trading.db "SELECT COUNT(*) FROM account_state;"
```

### Performance Issues

```bash
# Check if paper trading is running (consuming CPU)
ps aux | grep python

# Stop all Python processes
pkill -9 python

# Restart API only
python -m uvicorn backend.api.main:app --port 8001
```

---

## Success Criteria

### All Endpoints Respond
- [x] `/api/emergency/stop` → 200
- [x] `/api/emergency/reset` → 200/400
- [x] `/api/emergency/status` → 200
- [x] `/api/emergency/close-all` → 200
- [x] `/api/emergency/set-crash-threshold` → 200/400
- [x] `/api/autonomous/status` → 200
- [x] `/api/autonomous/enable` → 200
- [x] `/api/autonomous/disable` → 200
- [x] `/api/autonomous/set-schedule` → 200/400
- [x] `/api/autonomous/next-execution` → 200

### Core Functionality Works
- [ ] Emergency stop blocks trading
- [ ] Crash detection can be configured
- [ ] Autonomous respects time window
- [ ] Emergency stop blocks autonomous

### Performance Targets Met
- [ ] Emergency stop <100ms
- [ ] Crash detection <100ms
- [ ] Status check <10ms
- [ ] Can handle 100+ concurrent requests

### Error Handling Correct
- [ ] Invalid threshold rejected
- [ ] Invalid schedule rejected
- [ ] Reset requires confirmation
- [ ] Graceful error messages

---

## Test Report Output

After running tests, you should see:

```
E2E Test Report
===============
Date: 2026-07-01
API: http://localhost:8001

SUMMARY
=======
Tests Run: 20
Tests Passed: 19
Tests Failed: 1
Pass Rate: 95%

EMERGENCY STOP
- Trigger: PASS
- Reset confirmation: PASS
- Status tracking: PASS

CRASH DETECTION
- No crash when stable: PASS
- Crash detected at threshold: PASS
- Threshold configuration: PASS
- Invalid threshold rejected: FAIL (threshold 101 should reject)

AUTONOMOUS TRADING
- Schedule configuration: PASS
- Enable/disable: PASS
- Next execution: PASS
- Emergency stop blocks: PASS

PERFORMANCE
- Emergency stop: 48ms ✅
- Crash detection: 72ms ✅
- Status check: 8ms ✅

VERDICT: READY FOR PAPER TRADING
```

---

## Next Steps

After E2E tests pass:

1. **Deploy to paper trading environment**
   ```bash
   ./scripts/deploy-paper.sh
   ```

2. **Monitor for 24 hours**
   - Check logs for errors
   - Verify autonomous trades execute on schedule
   - Test manual emergency stop

3. **Run chaos tests**
   - Simulate network partition
   - Kill PRIMARY machine
   - Verify failover works

4. **Go live with €1,000**
   ```bash
   ./scripts/deploy-live.sh  # Requires confirmation
   ```

---

**Ready to Test?** Start with Step 1 above! ✅
