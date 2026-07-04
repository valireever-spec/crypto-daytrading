# HA Redundancy Validator: Specification & Gap Analysis

**Current Status:** No specialized validator exists for bidirectional HA detection

---

## Gap Analysis

### Existing Validators (CSF Meta-Validator)
- ✅ **Phase 1-4:** Structural code analysis (type hints, linting, etc.)
- ✅ **Phase 5:** Operational config validation (timeouts, error handling)
- ✅ **Phase 6-9:** Runtime monitoring (uptime, latency, cascades)
- ❌ **HA-Specific:** Bidirectional sync, heartbeat, reverse SSH, promotion logic

### What We Need

```
DETECTION LAYER 1: Static Code Analysis
├─ Heartbeat code exists (both directions?)
├─ WebSocket on both machines (or only PRIMARY?)
├─ Sync is bidirectional (forward + backward?)
├─ SSH reverse tunnel setup exists?
├─ Promotion logic uses multiple signals?
└─ State conflict resolution implemented?

DETECTION LAYER 2: Configuration Validation
├─ Heartbeat timeout configured
├─ Sync retry logic exists
├─ SSH key exchange for reverse tunnel
├─ Promotion thresholds sensible
└─ Rollback procedure documented?

DETECTION LAYER 3: Runtime Testing
├─ Heartbeat actually arrives (both directions)
├─ WebSocket connects on both machines
├─ Forward sync succeeds (PRIMARY → BACKUP)
├─ Backward sync succeeds (BACKUP ← PRIMARY)
├─ Reverse SSH tunnel works (emergency recovery)
├─ Promotion triggers correctly (multiple signals)
└─ State consistent after failover

DETECTION LAYER 4: Live Production Monitoring
├─ Heartbeat freshness (no missed beats)
├─ Sync latency (forward + backward)
├─ WebSocket staleness (both machines)
├─ Promotion events (successful? timely?)
├─ State divergence (do machines agree?)
└─ Cascade patterns (WebSocket → HA → divergence)
```

---

## Proposed: HA Redundancy Validator

### Validator: `bidirectional_ha_validator`

```python
class BidirectionalHAValidator:
    """
    Validates bidirectional high-availability architecture.
    
    Detects:
    - Missing heartbeat in either direction
    - WebSocket only on PRIMARY (not BACKUP)
    - One-way sync (missing backward path)
    - No reverse SSH tunnel for recovery
    - Weak promotion logic (single signal only)
    - State divergence (PRIMARY ≠ BACKUP)
    - Cascade patterns (WebSocket → HA → divergence)
    """
    
    name = "bidirectional_ha_validator"
    category = "ha_architecture"
    phases = ["phase_1", "phase_2", "phase_3"]  # Runs all phases
    
    def __init__(self):
        self.issues = []
        self.score = 0
```

### Validator Checks

#### LAYER 1: Code Structure (Phase 1)
```python
def check_heartbeat_bidirectional():
    """Verify both PRIMARY and BACKUP send heartbeats."""
    # Check for:
    # - PRIMARY sends to BACKUP.heartbeat_endpoint()
    # - BACKUP sends to PRIMARY.heartbeat_endpoint()
    # - Both endpoints listen for heartbeats
    # - Heartbeat includes: WebSocket staleness, memory, state version
    
    if not has_primary_heartbeat_send:
        issues.append("CRITICAL: PRIMARY does not send heartbeat to BACKUP")
    if not has_backup_heartbeat_send:
        issues.append("CRITICAL: BACKUP does not send heartbeat to PRIMARY")
    if not has_heartbeat_payload_details:
        issues.append("HIGH: Heartbeat lacks health details (WebSocket, memory, state)")

def check_websocket_bidirectional():
    """Verify both machines connect to WebSocket."""
    # Check for:
    # - PRIMARY.websocket_manager.connect()
    # - BACKUP.websocket_manager.connect()
    # - Both track staleness independently
    # - BACKUP doesn't trade but monitors
    
    if not has_backup_websocket:
        issues.append("CRITICAL: BACKUP has no WebSocket connection")
    if not has_dual_staleness_tracking:
        issues.append("HIGH: No independent staleness tracking on BACKUP")

def check_sync_bidirectional():
    """Verify sync works both directions."""
    # Check for:
    # - Forward: PRIMARY → BACKUP (every 5s)
    # - Backward: BACKUP ← PRIMARY (on-demand + periodic)
    # - Conflict resolution: version + timestamp
    
    if not has_forward_sync:
        issues.append("CRITICAL: No forward sync PRIMARY → BACKUP")
    if not has_backward_sync:
        issues.append("CRITICAL: No backward sync BACKUP ← PRIMARY")
    if not has_conflict_resolution:
        issues.append("HIGH: No conflict resolution if states diverge")

def check_ssh_bidirectional():
    """Verify SSH tunnel works both directions."""
    # Check for:
    # - Forward: ssh -L (PRIMARY can reach BACKUP services)
    # - Reverse: ssh -R (BACKUP can reach PRIMARY services for recovery)
    
    if not has_forward_ssh:
        issues.append("MEDIUM: No forward SSH tunnel")
    if not has_reverse_ssh:
        issues.append("CRITICAL: No reverse SSH tunnel for recovery")

def check_promotion_logic():
    """Verify promotion uses multiple signals."""
    # Check for:
    # - Trigger 1: Heartbeat missed 3+ times
    # - Trigger 2: WebSocket stale >60s
    # - Trigger 3: State version not advancing
    # - Trigger 4: Memory critical + other issues
    # - Multiple triggers required (not just 1)
    
    trigger_count = sum([
        has_heartbeat_trigger,
        has_websocket_trigger,
        has_state_trigger,
        has_memory_trigger
    ])
    
    if trigger_count < 2:
        issues.append("CRITICAL: Promotion requires only 1 signal (too risky)")
    
    if not has_state_validation_before_promote:
        issues.append("HIGH: No state validation before promotion")
    
    if not has_recovery_sync_after_promote:
        issues.append("HIGH: No state recovery for old PRIMARY after failover")
```

#### LAYER 2: Configuration Validation (Phase 2)
```python
def check_heartbeat_config():
    """Validate heartbeat configuration."""
    # Check:
    # - Timeout: 5-10 seconds (reasonable)
    # - Miss threshold: 2-3 (before escalation)
    # - Frequency: 5 seconds (monitoring granularity)
    
    if heartbeat_timeout > 10:
        issues.append("HIGH: Heartbeat timeout too long (>10s)")
    if heartbeat_miss_threshold < 2:
        issues.append("MEDIUM: Miss threshold too low (<2)")

def check_sync_config():
    """Validate sync configuration."""
    # Check:
    # - Forward sync interval: 5-10 seconds
    # - Backward pull: on-demand + periodic every 30s
    # - Timeout: 5 seconds per operation
    # - Retry: exponential backoff
    
    if forward_sync_interval > 10:
        issues.append("HIGH: Forward sync too infrequent (>10s)")
    if not has_backward_pull_periodic:
        issues.append("HIGH: No periodic backward sync check")

def check_ssh_config():
    """Validate SSH tunnel configuration."""
    # Check:
    # - Forward: Established on PRIMARY startup
    # - Reverse: Established on PRIMARY startup
    # - Reconnect: Automatic if tunnel dies
    # - Timeout: 5 seconds for SSH operations
    
    if not has_automatic_tunnel_reconnect:
        issues.append("HIGH: SSH tunnel doesn't auto-reconnect on failure")
```

#### LAYER 3: Runtime Testing (Phase 3)
```python
async def test_heartbeat_bidirectional():
    """Test both-direction heartbeat in runtime."""
    # Test 1: PRIMARY sends to BACKUP
    primary_heartbeat_ok = await primary.send_heartbeat()
    if not primary_heartbeat_ok:
        issues.append("CRITICAL: PRIMARY cannot send heartbeat to BACKUP")
    
    # Test 2: BACKUP receives heartbeat
    backup_received_count = await backup.count_received_heartbeats(duration=10)
    if backup_received_count < 1:
        issues.append("CRITICAL: BACKUP is not receiving PRIMARY heartbeats")
    
    # Test 3: BACKUP sends to PRIMARY
    backup_heartbeat_ok = await backup.send_heartbeat()
    if not backup_heartbeat_ok:
        issues.append("CRITICAL: BACKUP cannot send heartbeat to PRIMARY")
    
    # Test 4: PRIMARY receives heartbeat
    primary_received_count = await primary.count_received_heartbeats(duration=10)
    if primary_received_count < 1:
        issues.append("CRITICAL: PRIMARY is not receiving BACKUP heartbeats")

async def test_websocket_dual_connection():
    """Test WebSocket on both machines."""
    # Test 1: PRIMARY WebSocket
    primary_ws_ok = await primary.websocket_manager.connect("BTCUSDT")
    if not primary_ws_ok:
        issues.append("CRITICAL: PRIMARY cannot connect to WebSocket")
    
    # Test 2: BACKUP WebSocket
    backup_ws_ok = await backup.websocket_manager.connect("BTCUSDT")
    if not backup_ws_ok:
        issues.append("CRITICAL: BACKUP cannot connect to WebSocket")
    
    # Test 3: Staleness tracking on both
    primary_staleness = await primary.get_websocket_staleness("BTCUSDT")
    backup_staleness = await backup.get_websocket_staleness("BTCUSDT")
    
    if primary_staleness is None:
        issues.append("HIGH: PRIMARY not tracking WebSocket staleness")
    if backup_staleness is None:
        issues.append("HIGH: BACKUP not tracking WebSocket staleness")

async def test_sync_bidirectional():
    """Test sync works both directions."""
    # Test 1: Forward sync (PRIMARY → BACKUP)
    test_state = {"cash": 10000, "positions": {"BTC": 5}}
    forward_ok = await primary.sync_to_backup(test_state)
    if not forward_ok:
        issues.append("CRITICAL: Forward sync PRIMARY → BACKUP failed")
    
    # Test 2: Backward sync (BACKUP ← PRIMARY)
    backward_ok = await backup.pull_state_from_primary()
    if not backward_ok:
        issues.append("CRITICAL: Backward sync BACKUP ← PRIMARY failed")
    
    # Test 3: State matches after sync
    backup_state = await backup.get_state()
    if backup_state != test_state:
        issues.append("CRITICAL: State divergence after sync")
    
    # Test 4: Conflict resolution
    divergent_state_backup = {"cash": 9999, "positions": {}}
    resolved = await primary.resolve_state_conflict(test_state, divergent_state_backup)
    if resolved["cash"] != 10000:  # Should pick PRIMARY (newer)
        issues.append("HIGH: Conflict resolution incorrect")

async def test_ssh_bidirectional():
    """Test SSH tunnels work both ways."""
    # Test 1: Forward SSH (PRIMARY can reach BACKUP via SSH)
    forward_ssh_ok = await primary.ssh_tunnel.test_forward_connection()
    if not forward_ssh_ok:
        issues.append("MEDIUM: Forward SSH tunnel not working")
    
    # Test 2: Reverse SSH (BACKUP can reach PRIMARY via reverse tunnel)
    reverse_ssh_ok = await backup.ssh_tunnel.test_reverse_connection()
    if not reverse_ssh_ok:
        issues.append("CRITICAL: Reverse SSH tunnel not working (emergency recovery blocked)")

async def test_promotion_logic():
    """Test promotion triggers and state recovery."""
    # Simulate: PRIMARY is down
    # Test 1: BACKUP detects missing heartbeats
    missed = await backup.simulate_missing_heartbeats(count=3)
    if missed < 3:
        issues.append("HIGH: BACKUP doesn't detect 3 missed heartbeats")
    
    # Test 2: BACKUP evaluates promotion readiness
    can_promote = await backup.should_promote()
    if not can_promote:
        issues.append("CRITICAL: BACKUP should promote but doesn't")
    
    # Test 3: BACKUP tries to pull state from PRIMARY (may fail if PRIMARY is down)
    # But should NOT fail if reverse SSH works
    
    # Test 4: BACKUP successfully promotes
    promote_ok = await backup.promote_to_primary()
    if not promote_ok:
        issues.append("CRITICAL: BACKUP promotion failed")
    
    # Test 5: Old PRIMARY recovers and syncs state
    if primary_recovered:
        sync_ok = await primary.pull_state_from_new_primary()
        if not sync_ok:
            issues.append("CRITICAL: Old PRIMARY cannot recover state from new PRIMARY")
```

#### LAYER 4: Live Production Monitoring (Phase 7)
```python
class LiveHAHealthMonitor:
    """Continuous HA health validation in production."""
    
    async def monitor_heartbeat_health():
        """Track heartbeat freshness continuously."""
        # Metric: heartbeat_freshness_seconds (should be <5s)
        # Alert: If >10s → heartbeat is stale
        # Critical: If >30s → heartbeat is dead
        
    async def monitor_websocket_health():
        """Track WebSocket health on both machines."""
        # Metric: websocket_staleness_seconds (both PRIMARY and BACKUP)
        # Alert: If both >30s → network globally down
        # Alert: If only PRIMARY >30s → PRIMARY isolated
        
    async def monitor_sync_health():
        """Track sync success rates."""
        # Metric: forward_sync_success_rate (should be 99%+)
        # Metric: backward_sync_success_rate (should be 99%+)
        # Alert: If forward <95% → HTTP to BACKUP failing
        # Alert: If backward <95% → BACKUP cannot pull from PRIMARY
        
    async def monitor_promotion_health():
        """Track promotion events and outcomes."""
        # Metric: promotion_events_total (should be 0 in stable state)
        # Metric: promotion_time_seconds (should be <60s)
        # Alert: Multiple promotions → oscillating failovers (bad)
        # Alert: Promotion takes >60s → slow recovery
        
    async def monitor_state_divergence():
        """Detect state divergence continuously."""
        # Metric: state_divergence_percent (should be 0%)
        # Critical: If >0.1% → state sync is failing
        # Alert: If divergence detected → immediate investigation
```

---

## Validator Output Example

```json
{
  "validator": "bidirectional_ha_validator",
  "project": "crypto-daytrading",
  "score": 35,
  "status": "CRITICAL",
  "phase_scores": {
    "phase_1_code_structure": 25,
    "phase_2_configuration": 40,
    "phase_3_runtime_testing": 20,
    "phase_7_live_production": 15
  },
  "findings": [
    {
      "severity": "CRITICAL",
      "category": "heartbeat",
      "message": "BACKUP does not send heartbeat to PRIMARY",
      "file": "backend/core/ha_failover.py:250",
      "recommendation": "Implement BidirectionalHeartbeat (Fix 7)"
    },
    {
      "severity": "CRITICAL",
      "category": "websocket",
      "message": "BACKUP has no WebSocket connection (monitoring only)",
      "file": "backend/exchange/websocket_manager.py:1",
      "recommendation": "Implement BidirectionalWebSocket (Fix 5)"
    },
    {
      "severity": "CRITICAL",
      "category": "sync",
      "message": "Only PRIMARY → BACKUP sync (missing BACKUP ← PRIMARY)",
      "file": "backend/core/bidirectional_sync.py:1",
      "recommendation": "Implement backward sync (Fix 6)"
    },
    {
      "severity": "CRITICAL",
      "category": "ssh",
      "message": "No reverse SSH tunnel for emergency recovery",
      "file": "backend/core/ssh_tunnel_sync.py:1",
      "recommendation": "Add reverse SSH tunnel (Fix 8)"
    },
    {
      "severity": "CRITICAL",
      "category": "promotion",
      "message": "Promotion logic uses only 1 signal (heartbeat timeout)",
      "file": "backend/core/ha_failover.py:400",
      "recommendation": "Implement smart promotion with multiple signals (Fix 9)"
    }
  ],
  "summary": {
    "total_issues": 5,
    "critical": 5,
    "high": 0,
    "medium": 0,
    "fixes_required": [
      "Fix 5: BidirectionalWebSocket",
      "Fix 6: BidirectionalSync (backward path)",
      "Fix 7: BidirectionalHeartbeat",
      "Fix 8: BidirectionalSSHTunnel (reverse)",
      "Fix 9: SmartPromotionLogic"
    ],
    "estimated_fix_time": "4 hours",
    "production_readiness_delta": "+45% (after fixes)"
  }
}
```

---

## Where This Validator Fits

### In CSF Meta-Validator Architecture
```
CSF Meta-Validator (109 validators)
├─ Phase 1-4: General architecture (48 validators)
├─ Phase 5: Operational config (18 validators)
├─ Phase 6-8: Runtime monitoring (25 validators)
├─ Phase 9: Functional gaps (10 validators)
└─ ⭐ NEW: HA Redundancy Validator (1 specialized validator)
    └─ Detects bidirectional HA specifically
```

### Integration with Existing Validators
- **Complements** `concurrency_load_test_validator` (adds HA under load)
- **Refines** `state_consistency_validator` (adds HA sync verification)
- **Extends** `ha_failover_validator` (if exists) with bidirectional checks

---

## Implementation Priority

### Immediate (Needed Before Remediation)
1. ✅ Code structure checks (Fixes 5-9 present or missing?)
2. ✅ Configuration validation (Timeouts, retry logic configured?)
3. ✅ Runtime testing (Do heartbeats actually flow? Do syncs work?)

### This Week (Deploy with Phase 2)
4. ✅ Live production monitoring (Phase 7-like checks)
5. ✅ Continuous cascade detection (WebSocket → HA → divergence)

### Next Week (Full Integration)
6. ✅ Dashboard integration (show HA health in real-time)
7. ✅ Automated remediation suggestions (link to Fixes 5-9)

---

## Recommendation

**Create `bidirectional_ha_validator` as a standalone skill** (not part of CSF Meta-Validator):

```
/skills/bidirectional-ha-validator/
├─ bidirectional_ha_validator.py (~400 lines)
├─ ha_health_monitor.py (~300 lines)
├─ ha_cascade_detector.py (~200 lines)
└─ README.md
```

**Use cases:**
1. **Pre-remediation:** Detect which Fixes 5-9 are missing
2. **Post-remediation:** Validate all Fixes 5-9 work correctly
3. **Production:** Continuous monitoring 24/7
4. **Dashboards:** Real-time HA health visualization

**Scoring:**
- 0-20%: Critical HA gaps (none of Fixes 5-9 implemented)
- 20-50%: Partial HA (some Fixes implemented, gaps remain)
- 50-80%: Good HA (most Fixes implemented, needs testing)
- 80-95%: Production HA (all Fixes working, monitoring active)
- 95%+: Exemplary HA (bidirectional, auto-remediation enabled)

---

## Status

- ❌ **Skill does not exist** (critical gap)
- ✅ **Specification complete** (this document)
- ⏳ **Ready to build** (400-900 lines of validator code)
- 🎯 **Priority:** HIGH (HA is core infrastructure)

**Recommendation:** Build this as a dependency of `remediation_bidirectional_ha.py` so teams can validate their HA setup is truly bidirectional.

---

**Related Documents:**
- `BIDIRECTIONAL_HA_ARCHITECTURE.md` (explains why bidirectional needed)
- `REMEDIATION_COMPLETE_INTEGRATION.md` (all 9 fixes, Fixes 5-9 need bidirectional)
- `remediation_bidirectional_ha.py` (implementation of Fixes 5-9)
