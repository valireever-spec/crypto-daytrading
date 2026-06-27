# Requirement: WebSocket Resilience & Automatic Recovery

**Priority:** CRITICAL  
**Status:** SPECIFICATION + IMPLEMENTATION  
**Applies to:** PRIMARY (127.0.0.1:8001) + BACKUP (192.168.3.25:8002)

---

## Problem Statement

**Current Failure Mode:**
- WebSocket stream to Binance stalls (data aging 5-12+ seconds)
- Trading loop detects stale data and **silently halts**
- No automatic recovery
- System appears healthy but produces zero trades
- **Issue undetected for 5+ hours** without manual inspection

**Root Cause:**
- Binance WebSocket connection degrades but doesn't close
- No heartbeat/ping mechanism to detect stale connections
- No automatic reconnection on stream lag
- No alerting on connection health degradation

**Impact:** Capital loss risk (cannot execute trades during stalls)

---

## Formal Requirements

### R1: Automatic Reconnection on Stale Data
**Requirement:** When WebSocket stream ages beyond threshold (>5s), automatically reconnect within 10 seconds.

**Acceptance Criteria:**
- If any price stream stale for >5s, trigger reconnection within 10 seconds ✓
- Reconnection uses exponential backoff (1s, 2s, 4s, 8s max) ✓
- Max 5 retry attempts before escalating to alert ✓
- No manual intervention required ✓

### R2: Bidirectional Heartbeat
**Requirement:** Implement ping/pong heartbeat to detect dead connections.

**Acceptance Criteria:**
- Send ping to Binance every 10 seconds ✓
- If no pong within 5 seconds, mark connection dead ✓
- Trigger reconnection on dead connection ✓
- Both PRIMARY and BACKUP monitor heartbeat ✓

### R3: Circuit Breaker with Escalation
**Requirement:** Prevent cascading failures with circuit breaker.

**Acceptance Criteria:**
- After 3 failed reconnection attempts, trip circuit breaker ✓
- Circuit breaker pauses trading (prevents stale-price trades) ✓
- Alert user: "WebSocket recovery failed, trading paused" ✓
- Auto-retry every 30 seconds (exponential backoff) ✓
- Reset on successful reconnection ✓

### R4: Health Monitoring & Alerting
**Requirement:** Continuous monitoring + alert on degradation.

**Acceptance Criteria:**
- Monitor stream age every 1 second ✓
- Alert on age > 3s (warning) ✓
- Alert on age > 5s (critical) ✓
- Send alert: "WebSocket lag detected: BNBUSDT(Xs)" ✓
- Include in /api/health status ✓

### R5: Graceful Degradation
**Requirement:** Continue trading with available symbols if one stream fails.

**Acceptance Criteria:**
- If BNBUSDT fails, continue trading BTCUSDT + ETHUSDT ✓
- Only halt if >50% of symbols unavailable ✓
- Alert user: "Degraded mode: 1 of 3 symbols unavailable" ✓
- Resume full trading when stream recovers ✓

### R6: Testing & Validation
**Requirement:** Verify recovery works under stress.

**Acceptance Criteria:**
- Test: Kill WebSocket connection, verify auto-recovery <10s ✓
- Test: Simulate lag, verify reconnection triggered ✓
- Test: Verify trading resumes after recovery ✓
- Test: Verify no stale trades during recovery ✓
- Both PRIMARY and BACKUP tested ✓

---

## Implementation Plan

### Phase 1: WebSocket Reconnection Logic (2 hours)
Create `backend/exchange/binance_stream_resilience.py`:
- Automatic reconnection with exponential backoff
- Bidirectional heartbeat (ping/pong)
- Circuit breaker pattern
- Health tracking

### Phase 2: Integration with Trading Loop (1 hour)
Update `backend/trading/autonomous_trader/core.py`:
- Monitor WebSocket health before each trade
- Pause trading on circuit breaker trip
- Resume on recovery

### Phase 3: Alerting (30 minutes)
Update `backend/core/alerting.py`:
- WebSocket lag alerts
- Connection failure alerts
- Recovery success alerts

### Phase 4: Testing (1 hour)
Create `tests/integration/test_websocket_resilience.py`:
- Test auto-recovery on connection failure
- Test heartbeat detection
- Test circuit breaker
- Test graceful degradation
- Test on both PRIMARY and BACKUP

**Total effort:** ~4.5 hours  
**Target completion:** Today (2026-06-27)

---

## Success Criteria

After implementation:
- ✅ WebSocket reconnects automatically within 10 seconds of stale data
- ✅ Zero manual intervention required
- ✅ Trading continues uninterrupted during recovery
- ✅ User alerted on failures and recovery
- ✅ All 4 stress tests pass
- ✅ Both PRIMARY and BACKUP working

---

## Why This Matters

This is **not optional**:
1. **24/7 trading:** System must be resilient (no manual fixes at 3 AM)
2. **Capital at risk:** 5-hour silent stall = missed trades = capital loss
3. **Production requirement:** Any trading system needs auto-recovery
4. **HA system:** BACKUP must also have resilience (not just PRIMARY)

This should have been hardened before declaring "ready for Phase 1".

---

## Architecture

```
Binance WebSocket
        ↓
   [Heartbeat Monitor] ← Ping/Pong every 10s
        ↓
   [Stream Age Check]  ← If age > 5s, trigger reconnect
        ↓
[Reconnection Logic]   ← Exponential backoff (1s, 2s, 4s, 8s)
        ↓
 [Circuit Breaker]     ← Trip after 3 failures
        ↓
[Alert Manager]        ← Notify user on failures
        ↓
[Autonomous Trader]    ← Only trade if connected & fresh
```

---

## Next Steps

1. ✅ This spec (formalized requirement)
2. → Implement resilience layer
3. → Integrate with trading loop
4. → Add alerting
5. → Run stress tests
6. → Verify on both PRIMARY + BACKUP
7. → Deploy

Start implementation now.
