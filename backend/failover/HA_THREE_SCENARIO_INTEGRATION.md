# HA Three-Scenario Integration Guide

## Overview

This guide explains how to integrate the new three-scenario HA system:
1. **Scenario A (Local):** 192.168.3.25:22 reachable → use local IPs
2. **Scenario B (Remote DDNS):** Local fails → try r33v3r.ddns.net:22 → use DDNS
3. **Scenario C (Offline):** Both fail, but PRIMARY has internet → proceed without failover, retry DDNS every 45s

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ PRIMARY Machine (192.168.30.137)                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  trading_loop()                                             │
│    ↓                                                        │
│  ha_scenario_orchestrator.determine_scenario()             │
│    ├─→ _check_local_network() [1s timeout]                 │
│    ├─→ _check_ddns_resolution() [2s timeout]               │
│    └─→ _check_internet_connectivity() [2s timeout]         │
│         (parallel execution)                                │
│    ↓                                                        │
│  BiDirectionalHeartbeatSender.send_to_[A|B|C]()            │
│    │                                                        │
│    ├─ Scenario A: http://192.168.3.25:8002/api/ha/heartbeat
│    ├─ Scenario B: http://r33v3r.ddns.net:8002/api/ha/heartbeat
│    └─ Scenario C: log (no-op), periodic DDNS retry         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                              ↑
                              │
                              │ [SSH tunnel or direct HTTP]
                              │
┌─────────────────────────────────────────────────────────────┐
│ BACKUP Machine (192.168.3.25)                               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  failover_monitor()                                         │
│    ↓                                                        │
│  heartbeat_endpoint = /api/ha/heartbeat                     │
│    │                                                        │
│    ├─ Receive heartbeat from PRIMARY                        │
│    ├─ BiDirectionalHeartbeatMonitor.record_heartbeat()     │
│    └─ Response: {status: "received", timestamp, backup_state}
│                                                             │
│  heartbeat_monitor_loop()                                   │
│    ├─ Check if heartbeat stale (>6s)                        │
│    ├─ 3 misses → trigger promotion                          │
│    └─ Take over trading                                     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Integration Steps

### 1. Update backend/api/main.py (PRIMARY setup)

```python
from backend.failover.ha_scenario_orchestrator import (
    get_ha_orchestrator,
    ScenarioConfig,
)
from backend.failover.ha_bidirectional_heartbeat import (
    get_bidirectional_heartbeat_sender,
)

# In lifespan startup:
async def lifespan(app: FastAPI):
    # ... existing code ...
    
    # Initialize HA orchestrator (determines scenario A/B/C)
    config = ScenarioConfig(
        backup_local_ip="192.168.3.25",
        backup_local_port=22,
        backup_ddns_hostname="r33v3r.ddns.net",
        backup_ddns_port=22,
        backup_ssh_user="openhabian",
        local_ping_timeout_ms=1000,
        ddns_resolve_timeout_ms=2000,
        ddns_ping_timeout_ms=1000,
        internet_check_timeout_ms=2000,
        ddns_retry_interval_seconds=45,
    )
    orchestrator = get_ha_orchestrator(config)
    
    # Start bidirectional heartbeat sender
    heartbeat_sender = get_bidirectional_heartbeat_sender()
    await heartbeat_sender.start()
    
    yield
    
    # Cleanup
    await heartbeat_sender.stop()
```

### 2. Update backend/trading/autonomous_trader/core.py (PRIMARY trading loop)

```python
from backend.failover.ha_scenario_orchestrator import get_ha_orchestrator

async def _trading_loop(self):
    """Main trading loop - check scenario before executing trades."""
    
    orchestrator = get_ha_orchestrator()
    
    while self.running:
        try:
            # Determine current HA scenario
            scenario = await orchestrator.determine_scenario()
            
            # Log scenario info periodically
            if self.loop_count % 300 == 0:  # Every 5 min
                info = orchestrator.get_scenario_info()
                logger.info(f"HA Scenario: {info['current_scenario']} → {info['backup_endpoint']}")
            
            # Execute trading logic (unchanged)
            await self._execute_trades()
            
            # If in scenario C, periodically check if we can upgrade to B
            if orchestrator.should_retry_ddns():
                logger.info("Retrying DDNS resolution (scenario C recovery attempt)")
            
            self.loop_count += 1
            
        except Exception as e:
            logger.error(f"Trading loop error: {e}")
            await asyncio.sleep(1)
```

### 3. Update backend/api/routers/redundancy.py (BACKUP heartbeat endpoint)

```python
from backend.failover.ha_bidirectional_heartbeat import (
    get_bidirectional_heartbeat_monitor,
)

@router.post("/api/ha/heartbeat")
async def receive_heartbeat(request: Request):
    """BACKUP receives heartbeat from PRIMARY.
    
    Bidirectional verification:
    - Checks machine_id == "primary"
    - Records heartbeat_id and scenario
    - Responds with BACKUP state
    """
    try:
        data = await request.json()
        
        # Verify it's from PRIMARY
        if data.get("machine_id") != "primary":
            return JSONResponse(
                {"status": "rejected", "reason": "Invalid machine_id"},
                status_code=400
            )
        
        # Record heartbeat in BACKUP's monitor
        monitor = get_bidirectional_heartbeat_monitor()
        monitor.record_heartbeat(
            heartbeat_id=data.get("heartbeat_id"),
            scenario=data.get("scenario"),
            state_hash=data.get("state_hash"),
        )
        
        # Response with BACKUP state
        return JSONResponse({
            "status": "received",
            "timestamp": datetime.utcnow().isoformat(),
            "backup_state": {
                "machine_id": "backup",
                "promoted": monitor.promoted,
            }
        })
        
    except Exception as e:
        logger.error(f"Heartbeat reception error: {e}")
        return JSONResponse(
            {"status": "error", "detail": str(e)},
            status_code=500
        )
```

### 4. Update backend/api/routers/health.py (Add scenario info to health endpoint)

```python
from backend.failover.ha_scenario_orchestrator import get_ha_orchestrator

@router.get("/api/ha/status")
async def get_ha_status():
    """Get current HA scenario and status."""
    orchestrator = get_ha_orchestrator()
    info = orchestrator.get_scenario_info()
    
    return JSONResponse({
        "scenario": info["current_scenario"],
        "backup_endpoint": info["backup_endpoint"],
        "transitions": len(info["consecutive_fails"]),  # Total transitions
        "last_transition": info["last_transition"],
    })
```

## Timeout Tuning

All checks run in **parallel** with aggressive timeouts:

```
Local IP check:           1s   (same network, should be <100ms)
DDNS resolution:          2s   (includes DNS lookup + TCP handshake)
DDNS IP ping:             1s   (after DNS resolves)
Internet (Binance API):   2s   (external service, may be slow)
```

**Total time to determine scenario:** ~2s (parallel, not sequential)
**Heartbeat interval:** 2s
**Scenario transitions:** Logged and visible in `/api/ha/status`

## Scenario C Behavior

When BACKUP is unreachable but PRIMARY has internet (scenario C):

1. PRIMARY determines scenario C
2. Trading continues without HA failover
3. Heartbeat sent to /dev/null (no-op)
4. Every 45 seconds: ask orchestrator to re-check DDNS
5. If DDNS resolves and responds: upgrade to scenario B
6. If local network recovers: upgrade to scenario A

## Observability & Monitoring

```python
# Check current scenario in dashboard
curl http://192.168.30.137:8001/api/ha/status
# Response:
{
  "scenario": "local_network",
  "backup_endpoint": "192.168.3.25",
  "transitions": 2,
  "last_transition": {
    "timestamp": "2026-07-05T14:30:00.000Z",
    "from": "remote_ddns",
    "to": "local_network"
  }
}

# Check heartbeat stats
sender_stats = get_bidirectional_heartbeat_sender().get_stats()
# {
#   "heartbeat_count": 1234,
#   "send_failures": 2,
#   "scenario_transitions": 3,
#   "last_scenario": "local_network"
# }

# Check BACKUP heartbeat monitor
monitor_stats = get_bidirectional_heartbeat_monitor().get_stats()
# {
#   "heartbeats_received": 1234,
#   "consecutive_misses": 0,
#   "last_received_scenario": "local_network"
# }
```

## Testing Scenarios

### Test Scenario A → B Transition

```bash
# On PRIMARY, simulate local network failure
sudo ip route del default via 192.168.3.0/24

# Wait 2s for next heartbeat check
# Should transition from A → B

# Restore
sudo ip route add default via 192.168.3.0/24
```

### Test Scenario B → C Transition

```bash
# On BACKUP's router, disable port forwarding for r33v3r.ddns.net:22
# Wait 2s for next heartbeat check
# Should transition from B → C

# Verify: curl /api/ha/status shows "scenario": "backup_offline"
```

### Test Scenario C Recovery

```bash
# Enable port forwarding again
# Every 45s, PRIMARY retries DDNS
# After 45s: should see transition from C → B
```

## Edge Cases Handled

✅ **Network partition:** A→B→C graceful degradation  
✅ **DDNS stale IP:** Ping resolved IP before using  
✅ **DDNS resolution timeout:** Fall back to scenario C  
✅ **Binance API down:** Assume PRIMARY offline (rare)  
✅ **Heartbeat loss:** 3 misses = promotion (6s timeout)  
✅ **Scenario flapping:** Logged and visible in /api/ha/status  

## Edge Cases NOT Solved

❌ **Network partition between PRIMARY and BACKUP:** No solution (your note)  
   - Both machines can reach internet but not each other
   - PRIMARY sees BACKUP as offline (correct)
   - Proceeds without failover
   - Acceptable: either one can fail without cascading

## Files to Deploy

```
backend/failover/ha_scenario_orchestrator.py       (NEW)
backend/failover/ha_bidirectional_heartbeat.py     (NEW)
backend/api/main.py                                (UPDATE: add orchestrator init)
backend/trading/autonomous_trader/core.py          (UPDATE: scenario awareness)
backend/api/routers/redundancy.py                  (UPDATE: heartbeat endpoint)
backend/api/routers/health.py                      (UPDATE: /api/ha/status)
```

## Rollout Plan

1. Deploy ha_scenario_orchestrator.py (no side effects)
2. Deploy ha_bidirectional_heartbeat.py (no side effects)
3. Update main.py to initialize orchestrator
4. Update trading loop to call determine_scenario()
5. Update heartbeat endpoints to use new classes
6. Monitor /api/ha/status for 24h
7. Test scenario transitions manually
8. Enable in production
