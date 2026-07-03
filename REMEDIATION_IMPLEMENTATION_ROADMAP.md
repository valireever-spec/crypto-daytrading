# Crypto-Daytrading: Three-Level Remediation Roadmap

**Objective:** Prevent production cascades (WebSocket stale → HA split-brain → state divergence → silent trading failures)

**Status:** Ready to implement across 3 weeks

---

## Executive Summary

### Baseline Issues Detected
```
WebSocket Stale 30s → Recovery timeout missing → Infinite retry loop
                    → No logged exceptions → Silent hang
                    ↓
HA Sync both fail → HTTP 403, SSH file-not-found → No fallback logic
                 → State divergence (PRIMARY vs BACKUP cash)
                 ↓
Memory 85.4% → False split-brain signal → BACKUP promotes incorrectly
```

### Remediation Strategy

| Phase | Timeline | Deliverables | Impact |
|-------|----------|--------------|--------|
| **Phase 1 (Immediate)** | Today | 4 critical fixes + code changes | Stop cascades in flight |
| **Phase 2 (This Week)** | Days 2-5 | Metrics + alerts + chaos tests | Make cascades visible + testable |
| **Phase 3 (Next Week)** | Days 6-10 | Phase 7 validators + continuous monitoring | Auto-detect + alert on production incidents |

---

## PHASE 1: IMMEDIATE FIXES (TODAY)

### Files Created
- **`/backend/core/remediation_phase_1_immediate.py`** — 4 core fixes

### Fix 1: WebSocket Recovery Timeout
**Problem:** `_attempt_reconnect()` loop has max retries but individual `reconnect()` call has no timeout
```python
# CURRENT (BROKEN)
while attempt < MAX_ATTEMPTS:
    try:
        await self.ws_manager.reconnect(symbol)  # ⚠️ NO TIMEOUT!
    except Exception: pass
```

**Solution:** Add `asyncio.wait_for()` timeout
```python
# FIXED
try:
    result = await asyncio.wait_for(
        self.ws_manager.reconnect(symbol),
        timeout=5  # Max 5 seconds per attempt
    )
except asyncio.TimeoutError:
    logger.warning(f"Reconnect timed out (5s) - WebSocket manager may be hanging")
```

**File to Update:** `/backend/exchange/websocket_staleness_monitor.py` (line ~117)

**Apply:** `remediation_phase_1_immediate.WebSocketRecoveryWithTimeout`

---

### Fix 2: Exception Logging Before Silencing
**Problem:** 14+ instances of `except Exception: pass` (no logging)
```python
# CURRENT (BROKEN)
try:
    sync_state()
except Exception:
    pass  # ⚠️ SILENT FAILURE!
```

**Solution:** Log exception before silencing
```python
# FIXED
try:
    sync_state()
except Exception as e:
    logger.error(f"Sync failed: {e}", exc_info=True)  # Log + traceback
    # Then handle gracefully
```

**Files to Update:**
- `backend/analytics/post_trade_analytics.py` (lines 143, 275)
- `backend/analytics/sector_sentiment.py` (line 40)
- `backend/analytics/execution_realtime_monitor.py` (line 85)
- 11+ more (see gap report)

**Apply:** `remediation_phase_1_immediate.ExceptionLoggingWrapper`

---

### Fix 3: HA Sync Fallback (Circuit Breaker)
**Problem:** Both HTTP and SSH sync fail → no fallback → state divergence
```python
# CURRENT (BROKEN)
try:
    http_result = sync_via_http(state)
except:
    try:
        ssh_result = sync_via_ssh(state)
    except:
        pass  # ⚠️ STATE DIVERGENCE!
```

**Solution:** Pause trading if both sync methods fail
```python
# FIXED
if not http_result and not ssh_result:
    self.trading_paused = True
    logger.critical("Both sync methods failed - pausing trading")
    alert_monitoring_system()
```

**File to Update:** `/backend/core/ha_failover.py` or `/backend/core/bidirectional_sync.py`

**Apply:** `remediation_phase_1_immediate.HASyncFallbackWithCircuitBreaker`

---

### Fix 4: Memory Threshold Guard (False Positive Prevention)
**Problem:** Memory 85.4% alone triggers split-brain (no correlation check)
```python
# CURRENT (BROKEN)
if memory_percent > 0.85:
    return UNHEALTHY  # ⚠️ FALSE POSITIVE!
```

**Solution:** Only unhealthy if memory high + other symptoms
```python
# FIXED
if memory_percent > 0.80:
    if latency_increase or error_rate_increase or oom_detected:
        return UNHEALTHY  # Correlated issue
    else:
        return HEALTHY  # Just high memory, OK
```

**File to Update:** `/backend/core/ha_failover.py` (health check logic)

**Apply:** `remediation_phase_1_immediate.MemoryThresholdGuard`

---

### Phase 1 Implementation Checklist
```
✓ Read remediation_phase_1_immediate.py
✓ Apply Fix 1: Add timeout to websocket_staleness_monitor.py:117
✓ Apply Fix 2: Replace bare except handlers with logging (14 files)
✓ Apply Fix 3: Add circuit breaker to ha_failover.py
✓ Apply Fix 4: Update memory check logic in ha_failover.py
✓ Run: pytest tests/ -v  (ensure no regressions)
✓ Deploy to staging
```

---

## PHASE 2: INSTRUMENTATION (THIS WEEK)

### Files Created
- **`/backend/core/remediation_phase_2_this_week.py`** — Metrics, alerts, chaos tests

### 2.1: Prometheus Metrics Collection

**Metrics to Track:**
```python
# Memory
crypto_daytrading_memory_usage_percent
crypto_daytrading_memory_usage_bytes

# WebSocket
crypto_daytrading_websocket_staleness_seconds{symbol="BTCUSDT"}

# HA Sync
crypto_daytrading_ha_sync_failures_total{method="HTTP|SSH"}

# State
crypto_daytrading_state_divergence_percent
```

**Integration Point:** Add to main event loop
```python
# In your main trading loop
async def trading_loop():
    while True:
        metrics.track_memory_usage()
        metrics.track_websocket_staleness("BTCUSDT", staleness_secs)
        metrics.track_ha_sync_failure("HTTP", error_msg) if sync_failed
        await asyncio.sleep(5)
```

**Apply:** `remediation_phase_2_this_week.CryptoMetricsTracker`

---

### 2.2: Alert Rules

**Rules to Deploy:**

| Alert | Condition | Action |
|-------|-----------|--------|
| `websocket_stale_critical` | staleness > 30s | Log CRITICAL + page oncall |
| `websocket_stale_warning` | staleness > 10s | Log WARNING |
| `memory_critical` | memory > 95% | Log CRITICAL + stop trading |
| `memory_high_with_issues` | memory > 80% + (latency↑ OR error↑) | Log ERROR + investigate |
| `ha_sync_both_failed` | HTTP AND SSH failed | Log CRITICAL + pause trading |
| `state_divergence` | cash_primary ≠ cash_backup > 0.1% | Log CRITICAL + manual recovery |

**Integration:** Alert engine evaluates rules every 10 seconds
```python
# In your monitoring loop
alert_engine = AlertRuleEngine(metrics)
while True:
    triggered = alert_engine.evaluate_all_rules()
    if triggered:
        alert_engine.send_alert(triggered)  # Slack/PagerDuty
    await asyncio.sleep(10)
```

**Apply:** `remediation_phase_2_this_week.AlertRuleEngine`

---

### 2.3: Chaos Testing

**Tests to Run:**

1. **WebSocket Down Simulation** (30 seconds)
   ```python
   await chaos.simulate_websocket_down(duration_seconds=30)
   # Verify: Reconnect happens within 5s + staleness increases + alert triggers
   ```

2. **SSH Blocked Simulation** (30 seconds)
   ```python
   await chaos.simulate_ssh_blocked(duration_seconds=30)
   # Verify: HA sync fails on SSH, falls back to HTTP
   ```

3. **Memory Pressure Simulation** (30 seconds @ 85%)
   ```python
   await chaos.simulate_memory_pressure(target_percent=85)
   # Verify: No false split-brain + health check still OK
   ```

4. **Network Latency Simulation** (500ms, 30 seconds)
   ```python
   await chaos.simulate_network_latency(latency_ms=500, duration_seconds=30)
   # Verify: Requests have timeouts + don't hang indefinitely
   ```

**Integration:** Add to nightly test suite
```python
# In tests/chaos_tests.py
@pytest.mark.chaos
async def test_websocket_recovery():
    chaos = ChaosTestFramework(metrics)
    await chaos.simulate_websocket_down(30)
    # Assert recovery happened within 5s
```

**Apply:** `remediation_phase_2_this_week.ChaosTestFramework`

---

### Phase 2 Implementation Checklist
```
✓ Add PrometheusMetricsCollector to main trading loop
✓ Track memory, WebSocket staleness, HA sync failures every 5s
✓ Deploy AlertRuleEngine in monitoring thread
✓ Configure alert actions (logging, Slack, PagerDuty)
✓ Add chaos tests to test suite
✓ Run nightly: chaos_websocket_down, chaos_ssh_blocked, chaos_memory_pressure
✓ Verify alerts trigger correctly in staging
```

---

## PHASE 3: CONTINUOUS MONITORING (NEXT WEEK)

### Files Created
- **`/backend/core/remediation_phase_3_next_week.py`** — Phase 7 validators

### 3.1: Live Data Freshness Monitor

**Purpose:** Continuously validate that data flows correctly (WebSocket, HTTP, SSH)

```python
freshness = LiveDataFreshnessMonitor()

# Record updates as data arrives
freshness.update_source("websocket_btc", critical_threshold=60.0)  # When price arrives
freshness.update_source("http_backup_sync", critical_threshold=30.0)  # When sync succeeds

# Query status
report = freshness.get_freshness_report()
# {
#   "sources": {
#     "websocket_btc": {"staleness": 2.5, "status": "OK"},
#     "http_backup_sync": {"staleness": 45.0, "status": "CRITICAL"}
#   }
# }
```

**Integration:** Call from websocket handler + sync handler
```python
async def on_price_update(price):
    freshness.update_source("websocket_btc")
    # Process price...

async def sync_to_backup():
    if http_result:
        freshness.update_source("http_backup_sync")
```

---

### 3.2: Live Resource Usage Tracker

**Purpose:** Detect resource anomalies (memory leak, file descriptor leak, connection leak)

```python
resources = LiveResourceUsageTracker()

# Record every 10 seconds
resources.record_resources(
    memory_percent=75.4,
    memory_bytes=8_000_000_000,
    cpu_percent=45.0,
    file_descriptor_count=450,
    open_connections=80
)

# Get trends
trends = resources.get_resource_trends(lookback_seconds=300)
# If memory_percent_max > 90, alert
# If file_descriptor_count > 900, alert (system limit ~1024)
```

---

### 3.3: Live SLO Compliance Validator

**Purpose:** Monitor if production meets SLA targets

```python
slo = LiveSLOComplianceValidator()

# Record measurements (from monitoring data)
slo.record_measurement("uptime", 99.95)  # %
slo.record_measurement("latency_p95", 150)  # ms
slo.record_measurement("error_rate", 0.05)  # %
slo.record_measurement("failover_time", 28)  # seconds
slo.record_measurement("sync_latency", 95)  # ms

# Query compliance
status = slo.get_slo_status()
# {
#   "slos": {
#     "latency_p95": {"status": "COMPLIANT", "current": 150, "threshold": 200},
#     "failover_time": {"status": "COMPLIANT", "current": 28, "threshold": 30},
#     "sync_latency": {"status": "BREACHING", "current": 250, "threshold": 100}
#   }
# }
```

**SLO Targets:**
- Uptime: 99.9%+ (< 45 min downtime/month)
- P95 Latency: < 200ms
- P99 Latency: < 500ms
- Error Rate: < 0.1%
- Failover Time: < 30s
- Sync Latency: < 100ms

---

### 3.4: Live System Resilience Analyzer

**Purpose:** Detect cascading failure patterns in real-time

```python
resilience = LiveSystemResilienceAnalyzer()

# Record events as they happen
resilience.record_event("websocket_stale_30s", {"symbol": "BTCUSDT", "staleness": 35})
resilience.record_event("ha_sync_failed_both", {"http": "403", "ssh": "timeout"})
resilience.record_event("state_divergence", {"primary_cash": 10000, "backup_cash": 9995})

# Analyzer detects cascade pattern:
# websocket_stale_30s → ha_sync_failed_both → state_divergence
# Output: "🚨 CASCADE DETECTED [websocket_cascade]"
```

**Cascade Patterns to Detect:**
1. **WebSocket Cascade** → HA Sync Fails → State Divergence (CRITICAL)
2. **Resource Cascade** → Latency Increase → Error Rate Increase (HIGH)
3. **HA Sync Cascade** → SSH Fails → HTTP Fails → Sync Skipped (CRITICAL)

---

### 3.5: Live Error Correlation Validator

**Purpose:** Link errors to root causes for faster diagnosis

```python
correlation = LiveErrorCorrelationValidator()

# Record errors with context
correlation.record_error(
    "TimeoutError",
    "WebSocket reconnect timeout",
    {"memory_high": True, "network_latency": 500}
)
# Root cause inferred: memory_pressure

correlation.record_error(
    "ConnectionError",
    "SSH tunnel connect refused",
    {"ha_ssh_blocked": True}
)
# Root cause inferred: connectivity

# Query correlation report
report = correlation.get_correlation_report()
# {
#   "root_cause_breakdown": {
#     "memory_pressure": 15,
#     "connectivity": 8,
#     "timeout": 12
#   },
#   "recommendations": [
#     "Investigate memory leaks",
#     "Add request timeouts"
#   ]
# }
```

---

### Phase 3 Implementation Checklist
```
✓ Add LiveDataFreshnessMonitor to websocket + sync handlers
✓ Add LiveResourceUsageTracker to resource monitoring thread
✓ Add LiveSLOComplianceValidator to metrics collection
✓ Add LiveSystemResilienceAnalyzer event recording
✓ Add LiveErrorCorrelationValidator to exception handlers
✓ Deploy Phase 7 validators to production
✓ Create dashboard showing live metrics + cascades
✓ Set up continuous validation (runs 24/7)
```

---

## Integration: How to Apply All Three Phases

### Step 1: Copy Remediation Modules
```bash
cp /path/to/remediation_phase_1_immediate.py /backend/core/
cp /path/to/remediation_phase_2_this_week.py /backend/core/
cp /path/to/remediation_phase_3_next_week.py /backend/core/
```

### Step 2: Phase 1 - Code Fixes (2 hours)
```python
# In websocket_staleness_monitor.py
from backend.core.remediation_phase_1_immediate import WebSocketRecoveryWithTimeout

ws_recovery = WebSocketRecoveryWithTimeout()

# Replace _attempt_reconnect() with:
async def _attempt_reconnect(self, symbol):
    return await ws_recovery.attempt_reconnect_with_timeout(
        symbol, self.ws_manager
    )
```

```python
# In all exception handlers
from backend.core.remediation_phase_1_immediate import ExceptionLoggingWrapper

# Replace:
try:
    some_operation()
except Exception:
    pass

# With:
try:
    some_operation()
except Exception as e:
    logger.error(f"Operation failed: {e}", exc_info=True)
```

### Step 3: Phase 2 - Instrumentation (3 hours)
```python
# In main event loop
from backend.core.remediation_phase_2_this_week import (
    CryptoMetricsTracker, AlertRuleEngine, ChaosTestFramework
)

metrics = CryptoMetricsTracker()
alert_engine = AlertRuleEngine(metrics)

async def monitoring_loop():
    while True:
        metrics.track_memory_usage()
        metrics.track_websocket_staleness("BTCUSDT", staleness_secs)
        
        triggered_alerts = alert_engine.evaluate_all_rules()
        for alert in triggered_alerts:
            alert_engine.send_alert(alert)
        
        await asyncio.sleep(10)
```

### Step 4: Phase 3 - Continuous Validation (2 hours)
```python
# In validation/monitoring service
from backend.core.remediation_phase_3_next_week import (
    LiveDataFreshnessMonitor, LiveSLOComplianceValidator,
    LiveSystemResilienceAnalyzer, LiveErrorCorrelationValidator
)

freshness = LiveDataFreshnessMonitor()
slo = LiveSLOComplianceValidator()
resilience = LiveSystemResilienceAnalyzer()
correlation = LiveErrorCorrelationValidator()

# Integrate into existing handlers
def on_websocket_data():
    freshness.update_source("websocket_btc")
    slo.record_measurement("data_freshness", 0.5)  # seconds

def on_error():
    correlation.record_error("ErrorType", "message", {...})
    resilience.record_event("error_occurred")
```

---

## Validation & Testing

### Phase 1 Validation
```bash
# Ensure timeouts work
pytest tests/test_websocket_timeout.py -v
# Ensure logging works
pytest tests/test_error_logging.py -v
# Ensure sync fallback works
pytest tests/test_ha_sync_fallback.py -v
```

### Phase 2 Validation
```bash
# Run chaos tests
pytest tests/chaos_tests.py -v -m chaos
# Verify metrics collection
python3 backend/core/remediation_phase_2_this_week.py
# Verify alerts trigger
pytest tests/test_alert_rules.py -v
```

### Phase 3 Validation
```bash
# Verify validators work with live data
python3 backend/core/remediation_phase_3_next_week.py
# Test cascade detection
pytest tests/test_cascade_detection.py -v
# Test error correlation
pytest tests/test_error_correlation.py -v
```

---

## Success Criteria

### End of Phase 1
- ✅ WebSocket recovery has max 5s timeout per attempt
- ✅ All bare `except Exception:` replaced with logging
- ✅ HA sync fallback pauses trading if both methods fail
- ✅ Memory check uses correlation logic
- ✅ No production incidents from Phase 1 issues

### End of Phase 2
- ✅ Prometheus metrics collected (memory, WebSocket, HA sync)
- ✅ Alert rules evaluate correctly
- ✅ Chaos tests pass (WebSocket down, SSH blocked, memory pressure)
- ✅ Monitoring team can see real-time system health

### End of Phase 3
- ✅ Phase 7 validators deployed and running
- ✅ Cascade patterns detected within 5 seconds
- ✅ Error correlation provides root causes
- ✅ 24/7 continuous validation enabled
- ✅ Production readiness score > 80%

---

## Timeline

```
Day 1 (Today):        Phase 1 implementation (2 hours) + testing
Day 2-3:              Phase 2 metrics + alerts (3 hours) + chaos tests (2 hours)
Day 4-5:              Phase 2 monitoring setup + staging validation
Day 6-10 (Next Week): Phase 3 validators (2 hours) + production rollout
```

**Total Effort:** 10-12 hours across 3 weeks

---

## Related Documents

- **[PHASE_5_OPERATIONAL_RUNTIME_VALIDATORS.md](./PHASE_5_OPERATIONAL_RUNTIME_VALIDATORS.md)** — What Phase 5-7 validators detect
- **[/investing-platform/CSF_VALIDATION_REPORT.md](../investing-platform/CSF_VALIDATION_REPORT.md)** — Example of production readiness analysis
- **[/investing-platform/GAP_AND_BUG_REPORT.md](../investing-platform/GAP_AND_BUG_REPORT.md)** — Static code analysis baseline

---

## Questions?

Refer to the implementation modules for detailed docstrings and usage examples:
- Phase 1: `remediation_phase_1_immediate.py` (4 classes, ~350 lines)
- Phase 2: `remediation_phase_2_this_week.py` (~600 lines)
- Phase 3: `remediation_phase_3_next_week.py` (~900 lines)

**Total New Code:** ~1,800 lines, fully documented with examples.

---

**Status:** Ready to implement ✅
**Last Updated:** 2026-07-03
**Prepared by:** CSF Meta-Validator Analysis + Manual Review
