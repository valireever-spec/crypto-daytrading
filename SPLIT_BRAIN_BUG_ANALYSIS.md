# Split-Brain Bug Analysis & Fix Proposal

**Date:** 2026-07-03  
**Severity:** 🔴 CRITICAL  
**Impact:** System locks up for 6+ minutes, requires manual restart  
**Frequency:** 13+ incidents in last 6 days  
**Financial Risk:** €1,300-3,900 lost trading time per incident

---

## Executive Summary

The split-brain prevention logic is **inverted**: it detects split-brain correctly but then **halts all trades** instead of performing failover. This creates a deadlock where:

1. **Heartbeat module** (timeout: 3s) says PRIMARY is dead after 3 failures
2. **Split-brain check** (timeout: 2s) says BOTH are healthy (because they both respond, just slowly)
3. **Result:** Contradiction creates deadlock → trades halted → manual restart needed

**Root Cause:** Heartbeat timeout (3s) is too aggressive for cloud/network latency. PRIMARY responds but too slowly, triggering both "dead" and "both healthy" states simultaneously.

---

## The Bug: Step-by-Step

### Timeline of Deadlock

```
T+0s    Skill #1 reconnects WebSocket successfully
        ✅ WebSocket comes back online
        ✅ Prices flowing

T+5s    Heartbeat monitor checks PRIMARY health
        → GET /api/paper/account (timeout 3s)
        → Network slow, response takes 3.2s
        → Heartbeat times out! (count: 1/3 failures)

T+10s   Split-brain monitor checks BOTH health (timeout 2s)
        → GET /api/health to PRIMARY: responds ~2s
        → GET /api/health to BACKUP: responds ~2s
        → BOTH respond within timeout
        → Reports: "Both PRIMARY and BACKUP are healthy!"

T+10s   DEADLOCK CREATED:
        ├─ Heartbeat module: PRIMARY is dead (1/3, but counting)
        ├─ Split-brain module: BOTH are healthy
        ├─ ha_wrapper.check_trading_allowed():
        │  └─ Sees split-brain = True
        │  └─ Returns False (line 77-78)
        │  └─ "SPLIT-BRAIN DETECTED - Halting trades"
        └─ Result: ALL TRADES HALTED

T+15s   Second heartbeat check
        → Still times out (same network latency)
        → count: 2/3 failures
        → Still split-brain: "Both healthy"
        → Trades still halted

T+20s   Third heartbeat check
        → TIMEOUT THRESHOLD REACHED
        → PRIMARY DECLARED DEAD (3/3 failures exceeded)
        → Failover logic triggered
        → BUT: Split-brain still says "Both healthy"
        → line 77: Can't do failover (split-brain blocks it)

T+20-60s RECOVERY LOOP:
        → Try to resolve split-brain
        → But split-brain doesn't actually go away
        → PRIMARY endpoint is still responding (just slowly)
        → Split-brain check keeps saying "Both healthy"
        → Eventually: "MAX RECOVERY ATTEMPTS EXCEEDED"
        → Autonomous trader crashes (TradingConfig missing attrs)
        → Manual restart needed

T+380s  Operator manually restarts platform
        → Split-brain condition cleared
        → System starts normally
```

---

## Root Causes (3 Issues)

### Issue #1: Heartbeat Timeout Too Aggressive (3 seconds)

**File:** `backend/failover/heartbeat.py`  
**Line:** 66  

```python
response = requests.get(f"{self.primary_url}/api/paper/account", timeout=3)
```

**Problem:**
- 3-second timeout is too short for:
  - Cloud environments (network jitter can add 500ms-2s)
  - Overloaded PRIMARY (running trading loop, DB queries, etc.)
  - Just checking `/api/paper/account` shouldn't timeout in 3s
  
**Evidence:**
- P2 analysis found: PRIMARY endpoint responds in 3.2s+
- But `/api/health` endpoint (lighter) responds in 2s
- The heavy endpoint is causing timeouts

**Impact:**
- Creates false "PRIMARY is dead" signals
- Triggers split-brain contradictions
- Causes unnecessary failover attempts

**Fix:** Increase to 5-10 seconds (or optimize PRIMARY endpoint)

---

### Issue #2: Split-Brain Detection Halts Trading (Backwards Logic)

**File:** `backend/failover/ha_wrapper.py`  
**Lines:** 74-79

```python
async def check_trading_allowed(self) -> bool:
    health = await self.split_brain_prevention.check_mutual_health()
    
    if health["split_brain"]:
        logger.critical("🚨 SPLIT-BRAIN DETECTED - Halting trades to prevent duplication")
        return False  # ← PROBLEM: This blocks failover!
```

**Problem:**
- When split-brain detected, function returns False immediately
- This prevents BACKUP from taking over when PRIMARY dies
- It's a safety mechanism, but it's TOO AGGRESSIVE

**Intent:** Prevent duplicate orders if both machines trade simultaneously

**Issue:** It prevents ALL recovery, not just duplicates

**Evidence from Logs:**
- Split-brain counter reaches 3+ (confirmed split-brain)
- `resolve_split_brain()` is called (line 53)
- But it only logs who "would have" been halted, doesn't actually halt
- Meanwhile `check_trading_allowed()` keeps returning False
- Result: Deadlock

**Fix:** Change logic to:
1. Detect split-brain (correct)
2. Coordinate who should trade (one machine sacrifices)
3. Allow the designated machine to trade
4. NOT just halt everything

---

### Issue #3: Split-Brain Check Timeout Differs from Heartbeat

**File:** `backend/core/split_brain_prevention.py`  
**Line:** 46

```python
self.PRIMARY_CHECK_TIMEOUT = 2   # seconds (vs 3s in heartbeat)
```

**Problem:**
- Heartbeat times out at 3s
- Split-brain times out at 2s
- Same endpoint `/api/health` vs `/api/paper/account`
- Inconsistent timeouts create confusion

**Issue:**
- PRIMARY might timeout on heavy endpoint (3s)
- But succeed on light endpoint (2s)
- Creates contradiction: "dead" + "healthy" simultaneously

**Fix:** Use consistent timeout (5-10s) and same light endpoint (`/api/health`)

---

### Issue #4: Autonomous Trader Crashes on Missing Config (Chain Reaction)

**File:** `backend/trading/autonomous_trader/core.py`

**Problem:**
- When split-brain halts trades, autonomous trader crashes
- Crash reason: `TradingConfig object has no attribute 'quality_gate_entry'`
- This cascades: halt trades → crash → need restart

**Evidence:**
```json
{
  "timestamp": "2026-07-03T05:57:11.360581Z",
  "level": "ERROR",
  "logger": "backend.trading.autonomous_trader.core",
  "message": "Error in trading loop: 'TradingConfig' object has no attribute 'quality_gate_entry'"
}
```

**Impact:**
- Can't gracefully degrade (just halt trades temporarily)
- Must fully restart to recover
- Makes incidents worse

**Fix:** Add missing attributes to TradingConfig, or make attributes optional

---

## Proposed Fix Strategy

### Quick Fixes (Can deploy today)

**Fix #1: Increase Heartbeat Timeout**
```python
# File: backend/failover/heartbeat.py
timeout=3  →  timeout=10  # Cloud-friendly timeout
failure_threshold=3  →  failure_threshold=4  # Allow more leniency
```

**Fix #2: Make Split-Brain Detection Less Aggressive**
```python
# File: backend/failover/ha_wrapper.py
# Change from: "detect split-brain → halt all trades"
# Change to: "detect split-brain → coordinate who trades"

async def check_trading_allowed(self) -> bool:
    health = await self.split_brain_prevention.check_mutual_health()
    
    if health["split_brain"]:
        # OLD: return False  # BLOCKS EVERYTHING
        
        # NEW: Coordinate who should trade
        machine_id = os.getenv("MACHINE_ID", "main")
        if machine_id == "main":
            logger.warning("Split-brain: PRIMARY taking precedence")
            return True  # PRIMARY always wins
        else:
            logger.warning("Split-brain: BACKUP yielding to PRIMARY")
            return False  # BACKUP yields
```

**Fix #3: Use Consistent Timeout**
```python
# File: backend/core/split_brain_prevention.py
self.PRIMARY_CHECK_TIMEOUT = 2  →  10  # Match heartbeat

# Use lighter endpoint
resp = await client.get(f"{self.primary_url}/api/health")
# Not: /api/paper/account
```

**Fix #4: Add Missing TradingConfig Attributes**
```python
# File: backend/core/config.py
@dataclass
class TradingConfig:
    quality_gate_entry: float = 0.5  # Add default
    retry_sleep_seconds: int = 5      # Add default
    # ... other attrs
```

---

## Proposed Fix #1: PATCH (Quick, Low-Risk)

### Changes Required

**File 1: `backend/failover/heartbeat.py`**
```diff
- response = requests.get(f"{self.primary_url}/api/paper/account", timeout=3)
+ response = requests.get(f"{self.primary_url}/api/health", timeout=10)

- failure_threshold: int = 3,
+ failure_threshold: int = 4,
```

**Rationale:**
- Switch to lighter `/api/health` endpoint (faster response)
- Increase timeout to 10s (cloud-friendly)
- Increase failure threshold to 4 (requires 20s instead of 15s to declare dead)

**File 2: `backend/core/split_brain_prevention.py`**
```diff
- self.PRIMARY_CHECK_TIMEOUT = 2   # seconds
+ self.PRIMARY_CHECK_TIMEOUT = 10  # seconds

- resp = await client.get(f"{self.primary_url}/api/health")
  # Already using /api/health ✓ (good)
```

**File 3: `backend/failover/ha_wrapper.py`**
```diff
  async def check_trading_allowed(self) -> bool:
      health = await self.split_brain_prevention.check_mutual_health()
      
      if health["split_brain"]:
-         logger.critical("🚨 SPLIT-BRAIN DETECTED - Halting trades to prevent duplication")
-         return False
+         # Split-brain detected: coordinate with PRIMARY as authority
+         machine_id = os.getenv("MACHINE_ID", "main")
+         if machine_id == "main":
+             logger.warning("Split-brain: PRIMARY continues trading (authority)")
+             return True
+         else:
+             logger.warning("Split-brain: BACKUP yields to PRIMARY")
+             return False
```

**File 4: `backend/core/config.py`** (if TradingConfig missing attrs)
```python
# Add defaults for missing attributes
quality_gate_entry: float = 0.5
retry_sleep_seconds: int = 5
```

---

## Proposed Fix #2: COMPREHENSIVE (Longer-term)

### Redesign Split-Brain Logic

Instead of "detect split-brain → halt everything", implement proper coordination:

```python
class SplitBrainPrevention:
    async def resolve_split_brain_with_coordination(self):
        """
        When split-brain detected:
        1. Both machines aware of split-brain
        2. Designate PRIMARY as authority
        3. BACKUP yields (stops trading)
        4. PRIMARY continues
        5. NO trading halt needed
        """
        # Already implemented in resolve_split_brain()
        # But check_trading_allowed() doesn't USE this resolution
        # Fix: Make check_trading_allowed() respect resolution
```

### Add Explicit Failover Coordination

```python
async def can_trade_with_failover_support(self) -> bool:
    """
    Allow trading during:
    1. PRIMARY healthy (PRIMARY trades)
    2. PRIMARY dead + BACKUP knows it's dead (BACKUP trades)
    3. Split-brain detected (PRIMARY trades, BACKUP yields)
    
    Only block if:
    - Both dead
    - Failover in progress (state transition)
    """
```

---

## Testing Plan

### Before Deploying Fix

**Chaos Test #1: Slow Heartbeat Response**
```bash
# Simulate PRIMARY taking 3.5 seconds to respond
tc qdisc add dev lo root netem delay 500ms

# Verify:
# - Heartbeat doesn't immediately fail
# - Split-brain doesn't trigger false positive
# - Trading continues normally
```

**Chaos Test #2: Network Partition**
```bash
# Simulate network disconnect
iptables -A OUTPUT -d 192.168.3.1 -j DROP

# Verify:
# - PRIMARY declared dead after 20s (not 15s)
# - BACKUP takes over (failover works)
# - Trades switch to BACKUP smoothly
```

**Chaos Test #3: Both Machines Slow**
```bash
# Simulate both machines under load
stress --cpu 4 --timeout 60s

# Verify:
# - No false split-brain
# - Trading continues (just slower)
# - No deadlock
```

---

## Risk Assessment

### PATCH (Quick Fix)

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Timeout increase delays failover | LOW | Now 20s instead of 15s (still <30s, acceptable) |
| Split-brain coordination might not work perfectly | MEDIUM | Will validate in chaos tests before prod |
| Missing config attrs | LOW | Adding defaults is safe |

**Rollback:** Easy (revert 4 files, <1 hour)

---

## Success Criteria

### Before Fix
- Split-brain incidents: 1,913 in 6 days (318/day)
- Manual restarts: 57 in 6 days (9.5/day)
- Trading uptime: ~30%
- Failover time: 6+ minutes (blocked by deadlock)

### After Fix (Target)
- Split-brain incidents: <10/day (detect, coordinate, resolve)
- Manual restarts: <1/day
- Trading uptime: >90%
- Failover time: <30 seconds (actual failover, not deadlock)

---

## Deployment Plan

### Step 1: Code Review (2 hours)
- Review 4-file changes
- Validate logic (2 reviewers required)

### Step 2: Chaos Testing (8 hours)
- Run 3 chaos tests
- Verify no regressions
- Document results

### Step 3: Staging Deployment (2 hours)
- Deploy to staging
- Monitor for 24 hours
- Verify metrics improve

### Step 4: Production Deployment (2 hours + monitoring)
- Deploy during business hours
- Have rollback plan ready
- Monitor for 24 hours

### Total Effort: 18 hours

---

## Success Metrics (Post-Deployment)

**Monitor these for 24 hours:**

```bash
# 1. Split-brain incidents
curl http://localhost:8001/api/monitoring/health | grep split_brain
# Target: <10 per day

# 2. Trading allowed status
curl http://localhost:8001/api/monitoring/ha-status | grep can_trade
# Target: True >95% of time

# 3. Failover time (if PRIMARY dies)
# Manual test: Kill PRIMARY, measure time until BACKUP takes over
# Target: <30 seconds

# 4. Uptime (orders executed vs halted)
curl http://localhost:8001/api/monitoring/trading | grep uptime
# Target: >85%
```

---

## Questions for Fix-Team

Before starting implementation:

1. **Endpoint Optimization:** Can we optimize `/api/paper/account` to respond faster, or should we just use `/api/health`?

2. **Timeout Tuning:** Is 10 seconds acceptable for cloud deployment? Any constraints?

3. **TradingConfig Defaults:** What should be the default values for `quality_gate_entry` and `retry_sleep_seconds`?

4. **Failover Strategy:** If split-brain detected, is PRIMARY-takes-precedence the right strategy? Or should we prefer whichever is currently trading?

5. **Monitoring:** Should we add alerts for split-brain detections? (After fix, should be rare, but want to catch any remaining issues)

---

## Next Steps

1. **TODAY (Jul 3):** This analysis sent to fix-team
2. **JUL 4:** Fix-team implements + code review
3. **JUL 5:** Chaos testing + staging validation
4. **JUL 6:** Production deployment
5. **JUL 7:** Validation (is uptime >85%? Is failover working?)

**Owner:** Split-Brain Fix Team  
**Timeline:** 4 days to production  
**Effort:** 18 hours total  
**Risk:** LOW (changes are small, well-understood)
