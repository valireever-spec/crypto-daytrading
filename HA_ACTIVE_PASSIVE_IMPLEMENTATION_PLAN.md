# HA ACTIVE-PASSIVE IMPLEMENTATION PLAN
## Crypto-Daytrading: Making It HA-Ready

**Date:** 2026-07-02  
**Objective:** Convert crypto-daytrading to work in HA active-passive setup  
**Model:** PRIMARY (active trading) + BACKUP (standby, synced)  
**Status:** Planning phase

---

## 📊 HA ARCHITECTURE: Active-Passive

```
NORMAL OPERATION:
┌──────────────────────┐        ┌──────────────────────┐
│   PRIMARY (ACTIVE)   │        │   BACKUP (PASSIVE)   │
├──────────────────────┤        ├──────────────────────┤
│ • Executes trades    │──────→ │ • Syncs state        │
│ • Updates portfolio  │        │ • Ready to takeover  │
│ • Writes globals     │        │ • Reads-only for     │
│ • All logic running  │        │   monitoring         │
└──────────────────────┘        └──────────────────────┘
         |
         | (every 5s heartbeat)
         ↓
    Still alive?
         |
         ├─ YES: Continue
         └─ NO: BACKUP PROMOTES TO PRIMARY

FAILOVER:
┌──────────────────────┐        ┌──────────────────────┐
│   PRIMARY (DEAD)     │        │   BACKUP (PROMOTED)  │
├──────────────────────┤        ├──────────────────────┤
│ ✗ No longer running  │        │ ✓ Takes over trading │
│                      │        │ ✓ Uses synced state  │
│                      │        │ ✓ Resumes trading    │
└──────────────────────┘        └──────────────────────┘
```

---

## 🎯 KEY REQUIREMENTS FOR HA ACTIVE-PASSIVE

### Requirement 1: State Synchronization
**What:** BACKUP must have up-to-date copies of all critical state
**Why:** On failover, BACKUP must resume trading with consistent data
**How:** Sync every 5 seconds (heartbeat interval)

### Requirement 2: No Concurrent Writes During Normal Operation
**What:** Only PRIMARY writes to globals (BACKUP is read-only)
**Why:** Simplifies logic - no race conditions during normal operation
**How:** BACKUP never modifies trading state, only reads

### Requirement 3: Failover-Safe State
**What:** On failover, BACKUP promotes with guaranteed consistency
**Why:** Trading resumption must not lose money or create duplicates
**How:** State snapshot on every sync, clean handoff

### Requirement 4: Heartbeat Monitoring
**What:** PRIMARY sends heartbeat every 5 seconds
**Why:** BACKUP detects PRIMARY failure quickly
**How:** TCP heartbeat with 3-miss timeout = 15 seconds to failover

---

## 🔧 IMPLEMENTATION: 4-Phase Plan

### PHASE 1: Add State Synchronization (4 hours)

**Goal:** Make BACKUP maintain copies of critical state

```python
# NEW: State sync mechanism

# backend/core/ha_state_manager.py
class HAStateManager:
    """Manages state sync between PRIMARY and BACKUP"""
    
    def __init__(self):
        self.critical_state = {
            'signal_generator': None,
            'allocation_manager': None,
            'portfolio_monitor': None,
            'fill_tracker': None,
            'skills': None,
            # ... all 92 critical globals
        }
        self.last_sync = time.time()
    
    async def sync_state(self):
        """PRIMARY: Send state to BACKUP every 5s"""
        state_snapshot = {
            'timestamp': time.time(),
            'state': self.critical_state,
            'checksum': calculate_hash(self.critical_state)
        }
        await self.send_to_backup(state_snapshot)
    
    async def receive_state(self):
        """BACKUP: Receive and validate state"""
        state = await self.receive_from_primary()
        if self._validate(state):
            self.critical_state = state['state']
            self.last_sync = state['timestamp']
```

**Files to modify:**
- Create: `backend/core/ha_state_manager.py`
- Create: `backend/core/ha_heartbeat.py`
- Modify: `backend/trading/bot_runner.py` (add sync calls)

**Deliverable:** State sync working every 5 seconds

---

### PHASE 2: Add Heartbeat Monitoring (2 hours)

**Goal:** Detect PRIMARY failure and trigger failover

```python
# backend/core/ha_heartbeat.py

class HAHeartbeat:
    """PRIMARY and BACKUP heartbeat mechanism"""
    
    async def start_heartbeat(self):
        """PRIMARY: Send heartbeat every 5 seconds"""
        while True:
            try:
                await self.send_heartbeat_to_backup()
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
    
    async def monitor_heartbeat(self):
        """BACKUP: Monitor PRIMARY heartbeat"""
        missed_beats = 0
        while True:
            try:
                await asyncio.wait_for(
                    self.receive_heartbeat(),
                    timeout=6  # Allow 1 extra second
                )
                missed_beats = 0
            except asyncio.TimeoutError:
                missed_beats += 1
                if missed_beats >= 3:
                    # PRIMARY is dead (>15 seconds)
                    await self.promote_to_primary()
                    return
```

**Deliverable:** Failover detected within 15 seconds of PRIMARY death

---

### PHASE 3: Add Failover Logic (3 hours)

**Goal:** BACKUP promotes cleanly when PRIMARY fails

```python
# backend/core/ha_failover.py

class HAFailover:
    """Handle promotion from BACKUP to PRIMARY"""
    
    async def promote_to_primary(self):
        """
        Executed on BACKUP when PRIMARY dies.
        Ensures clean state takeover.
        """
        logger.critical("PRIMARY died. Promoting BACKUP to PRIMARY")
        
        # Step 1: Stop reading PRIMARY
        await self.disconnect_from_primary()
        
        # Step 2: Validate last synced state
        if not self.validate_state():
            raise StateValidationError("Cannot promote - state invalid")
        
        # Step 3: Resume trading with synced state
        await self.resume_trading()
        
        # Step 4: Update role
        self.role = 'PRIMARY'
        
        logger.info("Promotion complete - now trading as PRIMARY")
    
    def validate_state(self):
        """Verify state consistency before taking over"""
        # Check: portfolio math is consistent
        # Check: no pending incomplete orders
        # Check: signal generators ready
        # Check: all globals initialized
        return True
```

**Deliverable:** Clean failover with state validation

---

### PHASE 4: Add Monitoring & Testing (5 hours)

**Goal:** Verify HA works correctly

```python
# Tests for HA active-passive

# tests/integration/test_ha_failover.py

async def test_primary_failure_detected():
    """Verify BACKUP detects PRIMARY death"""
    primary = PrimaryBot()
    backup = BackupBot()
    
    # Start both
    await primary.start()
    await backup.start()
    
    # Let them sync for 10 seconds
    await asyncio.sleep(10)
    
    # Kill PRIMARY
    await primary.stop()
    
    # BACKUP should detect within 15 seconds
    start = time.time()
    while time.time() - start < 20:
        if backup.is_primary():
            elapsed = time.time() - start
            assert elapsed < 15, "Took too long to detect failure"
            return
        await asyncio.sleep(0.5)
    
    raise AssertionError("BACKUP didn't promote")

async def test_state_consistency_after_failover():
    """Verify state is consistent after failover"""
    primary = PrimaryBot()
    backup = BackupBot()
    
    await primary.start()
    await backup.start()
    await asyncio.sleep(10)
    
    # Record state snapshot
    primary_state = primary.get_state_snapshot()
    backup_state = backup.get_state_snapshot()
    
    assert primary_state == backup_state, "States diverged"
    
    # Kill PRIMARY
    await primary.stop()
    
    # Let BACKUP promote
    await asyncio.sleep(15)
    
    # Verify BACKUP state hasn't changed (resuming from known point)
    assert backup.get_state_snapshot() == backup_state
```

**Deliverable:** Passing HA tests

---

## 📋 CRITICAL GLOBALS NEEDING SYNC

**92 globals need to be included in state sync:**

### Tier 1: Must Sync (20 globals)
1. _signal_generator — Signal state
2. _allocation_manager — Asset allocation
3. _analyzer — Portfolio analysis
4. _optimizer — Optimization state
5. _rebalancing_engine — Rebalancing state
6. _portfolio_monitor — Portfolio state
7. _fill_tracker — Order fills
8. skills — Available skills
9. _risk_engine — Risk metrics
10. _explainer — Signal explanation
... (10 more critical ones)

### Tier 2: Should Sync (30 globals)
- Cost models, regime detectors, volatility managers, etc.

### Tier 3: Nice to Sync (42 globals)
- Support and utility globals

---

## 🛠️ IMPLEMENTATION CHECKLIST

### Week 1: Phase 1-2 (State Sync + Heartbeat)
- [ ] Design state sync protocol
- [ ] Implement HAStateManager
- [ ] Implement HAHeartbeat
- [ ] Unit tests for sync (5 tests)
- [ ] Verify sync every 5 seconds
- [ ] Verify heartbeat detection

### Week 2: Phase 3 (Failover Logic)
- [ ] Implement HAFailover
- [ ] Add state validation
- [ ] Add role switching
- [ ] Integration tests (5 tests)
- [ ] Manual failover test
- [ ] Verify clean promotion

### Week 3: Phase 4 (Testing & Hardening)
- [ ] Chaos tests (kill PRIMARY, verify BACKUP)
- [ ] Load tests (high trading volume + failover)
- [ ] Stress tests (rapid failovers)
- [ ] Monitor tests (health checks working)
- [ ] Documentation

---

## 🎯 HA REQUIREMENTS CHECKLIST

**For Active-Passive to work safely:**

```
STATE MANAGEMENT:
[ ] PRIMARY syncs state every 5 seconds
[ ] BACKUP maintains synced copy of all 92 critical globals
[ ] State includes: signals, allocations, fills, portfolio, skills
[ ] State sync includes checksum for validation

HEARTBEAT:
[ ] PRIMARY sends heartbeat every 5 seconds
[ ] BACKUP monitors for 3 missed beats = 15 seconds timeout
[ ] Heartbeat includes PRIMARY timestamp

FAILOVER:
[ ] BACKUP detects PRIMARY death (within 15s)
[ ] BACKUP validates state consistency
[ ] BACKUP resumes trading from last synced state
[ ] BACKUP updates role to PRIMARY
[ ] Logging records all failover events

TESTING:
[ ] Unit tests: state sync works
[ ] Unit tests: heartbeat detection works
[ ] Integration tests: failover succeeds
[ ] Chaos tests: kill PRIMARY, verify BACKUP resume
[ ] Load tests: failover under high trading volume
```

---

## 📊 EFFORT ESTIMATE

| Phase | Task | Hours |
|-------|------|-------|
| 1 | State synchronization | 4 |
| 2 | Heartbeat monitoring | 2 |
| 3 | Failover logic | 3 |
| 4 | Testing & hardening | 5 |
| **TOTAL** | | **14 hours** |

---

## 🚀 DEPLOYMENT SEQUENCE

1. **Implement all 4 phases** (14 hours)
2. **Test on 2 machines** (3 hours)
3. **Run chaos scenarios** (2 hours)
4. **Document operations** (1 hour)
5. **Deploy to production** with HA enabled

**Total timeline:** ~3 weeks with 1 developer

---

## ✅ SUCCESS CRITERIA

✅ PRIMARY and BACKUP sync every 5 seconds  
✅ BACKUP detects PRIMARY failure within 15 seconds  
✅ BACKUP promotes and resumes trading cleanly  
✅ State is consistent after failover  
✅ No lost orders or duplicate trades  
✅ Chaos tests pass (kill PRIMARY, verify BACKUP)  
✅ Documentation complete  

---

## 🔴 CRITICAL DIFFERENCES from Current Design

**Current (Single Machine):**
```python
global _signal_generator
_signal_generator = SignalGenerator()

async def analyze():
    return _signal_generator.analyze()  # Direct access
```

**HA Active-Passive:**
```python
# State sync manager handles globals
state_manager = HAStateManager()

async def analyze():
    # PRIMARY: Compute and sync
    signal = _signal_generator.analyze()
    await state_manager.sync_state()
    return signal

# BACKUP: Never computes, only reads synced state
async def monitor():
    state = await state_manager.receive_state()
    # Use state for monitoring only, never trade
```

---

## 📁 NEW FILES TO CREATE

```
backend/core/
├── ha_state_manager.py      (250 lines) - State sync
├── ha_heartbeat.py          (150 lines) - Heartbeat monitor
├── ha_failover.py           (200 lines) - Failover logic
└── ha_config.py             (100 lines) - HA configuration

tests/integration/
└── test_ha_failover.py      (300 lines) - HA tests

docs/
└── HA_OPERATIONS_GUIDE.md   (200 lines) - Operations manual
```

---

## 📝 MODIFIED FILES

```
backend/trading/bot_runner.py
  - Add: Initialize HAStateManager, HAHeartbeat, HAFailover
  - Add: Call state_manager.sync_state() every loop
  - Add: Check role before executing trades (PRIMARY only)

backend/__init__.py
  - Export: HAStateManager, HAHeartbeat, HAFailover

requirements.txt
  - No new dependencies (uses asyncio, which is built-in)
```

---

## 🎯 EXPECTED RESULT

After implementing this plan:

✅ **Crypto-daytrading works in HA active-passive**
✅ **PRIMARY executes trades, BACKUP syncs**
✅ **Failover detection: 15 seconds**
✅ **BACKUP promotes cleanly, resumes trading**
✅ **State is consistent across failover**
✅ **No lost orders or duplicates**
✅ **Deployable on 2 machines**

---

**Next Step:** Approve this plan and we can start Phase 1 (state synchronization)

---

**Plan Created:** 2026-07-02  
**Status:** Ready for implementation
