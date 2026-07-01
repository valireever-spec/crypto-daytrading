# E2E Testing: PRIMARY & BACKUP with playwright-testing-v2

**Framework:** playwright-testing-v2  
**Scope:** Comprehensive end-to-end testing of both PRIMARY and BACKUP  
**Date:** 2026-07-01  
**Status:** Test plan complete, ready for execution

---

## Test Suite Architecture

### PRIMARY Machine Tests (127.0.0.1:8001)

```python
primary_tests = [
    # Core API Tests
    {
        "name": "PRIMARY Health Check",
        "url": "http://127.0.0.1:8001/api/health",
        "method": "GET",
        "assert_status": 200,
        "assert_response": {"status": "healthy"},
        "confidence": 95
    },
    
    # Emergency Stop Tests
    {
        "name": "PRIMARY Emergency Status Available",
        "url": "http://127.0.0.1:8001/api/emergency/status",
        "method": "GET",
        "assert_status": 200,
        "assert_keys": ["emergency_stop_active", "crash_detected"],
        "confidence": 95
    },
    
    {
        "name": "PRIMARY Emergency Stop Trigger",
        "url": "http://127.0.0.1:8001/api/emergency/stop",
        "method": "POST",
        "data": {"reason": "E2E Test - PRIMARY"},
        "assert_status": 200,
        "assert_response": {"success": True},
        "confidence": 95
    },
    
    # Crash Detection Tests
    {
        "name": "PRIMARY Crash Detection Available",
        "url": "http://127.0.0.1:8001/api/emergency/close-all",
        "method": "POST",
        "data": {"threshold_percent": 5.0},
        "assert_status": 200,
        "assert_keys": ["crash_detected"],
        "confidence": 90
    },
    
    # Autonomous Trading Tests
    {
        "name": "PRIMARY Autonomous Status Available",
        "url": "http://127.0.0.1:8001/api/autonomous/status",
        "method": "GET",
        "assert_status": 200,
        "assert_keys": ["enabled", "running_now"],
        "confidence": 95
    },
    
    {
        "name": "PRIMARY Autonomous Enable",
        "url": "http://127.0.0.1:8001/api/autonomous/enable",
        "method": "POST",
        "assert_status": 200,
        "assert_response": {"enabled": True},
        "confidence": 90
    },
    
    # Database Tests
    {
        "name": "PRIMARY Database Health",
        "url": "http://127.0.0.1:8001/api/paper/account",
        "method": "GET",
        "assert_status": 200,
        "assert_keys": ["cash", "total_pnl"],
        "confidence": 95
    },
]
```

### BACKUP Machine Tests (192.168.3.25:8002)

```python
backup_tests = [
    # Core API Tests
    {
        "name": "BACKUP Health Check",
        "url": "http://192.168.3.25:8002/api/health",
        "method": "GET",
        "assert_status": 200,
        "assert_response": {"status": "healthy"},
        "confidence": 95
    },
    
    # Emergency Stop Tests
    {
        "name": "BACKUP Emergency Status Available",
        "url": "http://192.168.3.25:8002/api/emergency/status",
        "method": "GET",
        "assert_status": 200,
        "assert_keys": ["emergency_stop_active"],
        "confidence": 95
    },
    
    {
        "name": "BACKUP Emergency Stop Accessible",
        "url": "http://192.168.3.25:8002/api/emergency/stop",
        "method": "POST",
        "data": {"reason": "E2E Test - BACKUP"},
        "assert_status": 200,
        "confidence": 90
    },
    
    # Crash Detection Tests
    {
        "name": "BACKUP Crash Detection Available",
        "url": "http://192.168.3.25:8002/api/emergency/close-all",
        "method": "POST",
        "data": {"threshold_percent": 5.0},
        "assert_status": 200,
        "confidence": 85
    },
    
    # HA Tests
    {
        "name": "BACKUP Heartbeat Status",
        "url": "http://192.168.3.25:8002/api/ha/heartbeat-status",
        "method": "GET",
        "assert_status": 200,
        "confidence": 90
    },
    
    {
        "name": "BACKUP Autonomous Status",
        "url": "http://192.168.3.25:8002/api/autonomous/status",
        "method": "GET",
        "assert_status": 200,
        "assert_keys": ["enabled"],
        "confidence": 85
    },
]
```

---

## Integration Test Scenarios

### Scenario 1: Cross-Machine Failover Response

```python
scenario_failover = {
    "name": "PRIMARY → BACKUP Failover Sequence",
    "steps": [
        {
            "name": "Verify PRIMARY is active",
            "action": "GET /api/health",
            "url": "http://127.0.0.1:8001",
            "expect": {"status": "healthy"}
        },
        {
            "name": "Verify BACKUP is standby",
            "action": "GET /api/autonomous/status",
            "url": "http://192.168.3.25:8002",
            "expect": {"running_now": False}
        },
        {
            "name": "Simulate PRIMARY failure",
            "action": "KILL PRIMARY API (manual)",
            "note": "Operator must stop PRIMARY service"
        },
        {
            "name": "Wait for heartbeat timeout",
            "action": "WAIT 20 seconds",
            "reason": "Heartbeat timeout threshold"
        },
        {
            "name": "Verify BACKUP detects failure",
            "action": "GET /api/ha/heartbeat-status",
            "url": "http://192.168.3.25:8002",
            "expect": "PRIMARY unreachable"
        },
        {
            "name": "Verify BACKUP starts trading",
            "action": "GET /api/autonomous/status",
            "url": "http://192.168.3.25:8002",
            "expect": {"running_now": True}
        }
    ],
    "duration_minutes": 5,
    "confidence": 85
}
```

### Scenario 2: Emergency Stop Across Both Machines

```python
scenario_emergency_stop = {
    "name": "Emergency Stop Affects Both Machines",
    "steps": [
        {
            "name": "Verify both APIs healthy",
            "action": "GET /api/health on both",
            "expect": "Both return 200 OK"
        },
        {
            "name": "Trigger emergency stop on PRIMARY",
            "action": "POST /api/emergency/stop",
            "url": "http://127.0.0.1:8001",
            "data": {"reason": "E2E Test - Emergency Stop"}
        },
        {
            "name": "Verify PRIMARY stopped",
            "action": "GET /api/emergency/status",
            "url": "http://127.0.0.1:8001",
            "expect": {"emergency_stop_active": True}
        },
        {
            "name": "Verify BACKUP receives signal",
            "action": "GET /api/autonomous/status",
            "url": "http://192.168.3.25:8002",
            "expect": {"running_now": False}
        },
        {
            "name": "Reset emergency stop",
            "action": "POST /api/emergency/reset",
            "url": "http://127.0.0.1:8001",
            "data": {"confirm": True}
        },
        {
            "name": "Verify reset successful",
            "action": "GET /api/emergency/status",
            "url": "http://127.0.0.1:8001",
            "expect": {"emergency_stop_active": False}
        }
    ],
    "duration_minutes": 2,
    "confidence": 90
}
```

### Scenario 3: Database State Consistency

```python
scenario_db_sync = {
    "name": "Database State Synchronized Across Machines",
    "steps": [
        {
            "name": "Get PRIMARY account state",
            "action": "GET /api/paper/account",
            "url": "http://127.0.0.1:8001",
            "expect": "Returns cash, total_pnl"
        },
        {
            "name": "Get BACKUP account state",
            "action": "GET /api/paper/account",
            "url": "http://192.168.3.25:8002",
            "expect": "Same cash and P&L as PRIMARY"
        },
        {
            "name": "Verify timestamp consistency",
            "action": "Compare updated_at timestamps",
            "expect": "Timestamps within 5 seconds"
        },
        {
            "name": "Verify position sync",
            "action": "Compare open positions",
            "expect": "Both machines have same positions"
        }
    ],
    "duration_minutes": 1,
    "confidence": 80
}
```

---

## Test Execution Plan

### Phase 1: Automated Unit Tests (5 minutes)
```bash
# Run all endpoint tests against both machines
playwright_runner.run_tests(
    tests=primary_tests + backup_tests,
    parallel=True,
    timeout_per_test=5000,
    report_format="json"
)
```

**Expected Results:**
- 14 tests total
- Target: 13/14 passing (93%)
- No >5s response times
- No 500 errors

### Phase 2: Integration Scenarios (20 minutes)
```bash
# Run cross-machine scenarios
playwright_runner.run_scenarios([
    scenario_emergency_stop,      # 2 min
    scenario_db_sync,             # 1 min
    scenario_failover              # 5 min (manual trigger)
])
```

**Expected Results:**
- All scenarios pass
- Failover detects within 20s
- Emergency stop affects both machines
- Database stays synchronized

### Phase 3: Load & Stress Testing (10 minutes)
```bash
# Concurrent requests to both machines
playwright_runner.concurrent_test(
    url_primary="http://127.0.0.1:8001/api/health",
    url_backup="http://192.168.3.25:8002/api/health",
    concurrent_requests=50,
    duration_seconds=60
)
```

**Expected Results:**
- Both APIs handle 50 concurrent requests
- Response times <100ms (p95)
- Zero dropped connections
- No cascading failures

---

## Test Report Template

```markdown
# E2E Test Report — 2026-07-01

## Summary
- Tests Run: 14 unit + 3 scenarios + load test
- Pass Rate: X% (Y/Z passed)
- Duration: 35 minutes
- Critical Issues: 0
- Warnings: 0

## Unit Tests
| Test | PRIMARY | BACKUP | Status |
|------|---------|--------|--------|
| Health Check | ✅ 47ms | ✅ 52ms | PASS |
| Emergency Status | ✅ 38ms | ✅ 41ms | PASS |
| ... | ... | ... | ... |

## Integration Scenarios
| Scenario | Duration | Result | Status |
|----------|----------|--------|--------|
| Emergency Stop | 1.5s | Both stopped | PASS |
| Database Sync | 0.8s | Synchronized | PASS |
| Failover Detection | 18s | BACKUP detects in 18s | PASS |

## Load Test Results
- Concurrent Requests: 50
- Response Time (p95): 85ms
- Success Rate: 100%
- Errors: 0

## Deployment Recommendation
✅ **READY FOR PRODUCTION**
```

---

## Execution Checklist

- [ ] Verify PRIMARY API running on 127.0.0.1:8001
- [ ] Verify BACKUP API running on 192.168.3.25:8002
- [ ] Run unit tests (14 tests, ~1 min)
- [ ] Run integration scenarios (20 min)
- [ ] Run load test (10 min)
- [ ] Document results
- [ ] Get approval for production deployment

---

## Success Criteria

✅ **Must Pass:**
- All 14 unit tests pass
- Both machines respond <200ms
- No 500 errors
- Emergency stop works on both
- Crash detection available on both

✅ **Should Pass:**
- Failover detection <20s
- Database state synchronized
- Load test handles 50 concurrent
- Response times p95 <100ms

⚠️ **Nice to Have:**
- Failover detection <15s
- Load test handles 100 concurrent
- Response times p95 <50ms

---

## Confidence Levels

| Component | Confidence |
|-----------|-----------|
| Unit Tests | 95% |
| Integration | 85% |
| Load Test | 80% |
| Failover | 85% |
| Database Sync | 75% |

---

## Next Steps After E2E Testing

1. ✅ E2E tests pass → Proceed to deployment
2. ✅ Review test report → Approve production release
3. ✅ Deploy paper trading → Start trading with €1,220
4. ✅ Monitor 24+ hours → Collect baseline metrics
5. ✅ Plan live deployment → Schedule with €1,000

---

**Framework:** playwright-testing-v2  
**Methodology:** Automated API testing + integration scenarios + load test  
**Estimated Duration:** 35 minutes total  
**Status:** Ready for execution
