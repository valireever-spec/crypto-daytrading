# Phase Completion Checklist

**REQUIRED:** All items must pass before declaring a phase "DONE" and moving to next phase.

This checklist prevents the failure pattern we just experienced:
- Writing code ✅
- Passing tests ✅
- **Skipping verification ❌ ← THIS FAILED**
- Declaring production ready ❌

---

## ✅ Phase 1: Code Written & Tested

- [ ] Code compiles without errors
- [ ] Unit tests exist for all critical paths
- [ ] Tests pass (>75% of test suite)
- [ ] No test skips or `.skip()` markers

**Typical test count for feature:**
- Simple feature: 5-10 tests
- Medium feature: 10-20 tests
- Critical system: 20+ tests

---

## ✅ Phase 2: Code Quality Review

### File Size & Complexity
- [ ] All files <500 lines (or split if larger)
- [ ] No circular imports
- [ ] No deeply nested functions (>3 levels)

### Type Safety
- [ ] `def func(arg: Type)` — All parameters typed
- [ ] `def func(...) -> ReturnType` — All returns typed
- [ ] No `Any` or `Optional` without justification
- [ ] Pass through `mypy --strict`

### Exception Handling
- [ ] No bare `except:` clauses
- [ ] No `except Exception:` (except at top-level handlers)
- [ ] All exceptions logged with context
- [ ] Errors propagate cleanly or handled locally

### Code Debt Markers
- [ ] No `TODO` or `FIXME` comments (commit these tasks)
- [ ] No `HACK` or `XXX` markers (fix or document)
- [ ] No commented-out code (delete it)
- [ ] No debug `print()` statements

### Import Validation

**For each module import used:**
```bash
python3 -c "from module import Class; print(type(Class))"
```

- [ ] All `from X import Y` paths resolve correctly
- [ ] All class names actually exist
- [ ] All function names actually exist
- [ ] No import errors on fresh Python process

**Script to verify:**
```bash
python3 << 'EOF'
imports_to_test = [
    ('backend.core.health_checker', 'HealthChecker'),
    ('backend.exchange.binance_stream', 'get_stream_client'),
    # ... add all critical imports
]

for mod, name in imports_to_test:
    m = __import__(mod, fromlist=[name])
    obj = getattr(m, name)
    print(f"✅ {mod}.{name}")
EOF
```

### Dependencies
- [ ] All external dependencies pinned in requirements.txt
- [ ] No version conflicts
- [ ] No deprecated libraries

---

## ✅ Phase 3: Integration Verification

### Module Integration
- [ ] All modules used together pass tests
- [ ] Cross-module data flows work
- [ ] No missing dependencies between modules

### API/Endpoint Testing
- [ ] All endpoints return correct HTTP status codes
- [ ] Response schemas match documentation
- [ ] Error responses have proper error codes
- [ ] No unhandled exceptions in endpoints

### Database/Persistence
- [ ] Data persists correctly
- [ ] No data loss on restart
- [ ] Migrations (if any) are reversible
- [ ] Schema integrity verified

### Configuration
- [ ] All config values have defaults
- [ ] Config validation works
- [ ] Invalid config is caught before runtime
- [ ] Sensitive values aren't logged

---

## ✅ Phase 4: Stability Testing

### Cold Start
- [ ] System starts from fresh state
- [ ] No initialization order issues
- [ ] No "first run" bugs
- [ ] All systems fully operational after start

**Test:**
```bash
# Fresh start
rm -rf data/* logs/*
python -m backend.api.main &
sleep 10
curl http://localhost:8001/health
# Should respond fully operational
```

### Sustained Operation
- [ ] System runs for 1+ hour without crashing
- [ ] No memory leaks (memory usage stable)
- [ ] No file descriptor leaks
- [ ] All background tasks remain responsive

**Test:**
```bash
# Monitor for 1 hour
watch 'ps aux | grep uvicorn | grep -v grep'
# Memory usage should be stable within ±5%
```

### Restart Resilience
- [ ] System survives graceful shutdown
- [ ] System survives forced kill (`-9`)
- [ ] No state is lost on restart
- [ ] No corruption of persistent data

**Test:**
```bash
# Start system
python -m backend.api.main &
sleep 5

# Kill it
pkill -9 uvicorn

# Restart
python -m backend.api.main &
sleep 5

# Verify state restored
curl http://localhost:8001/api/positions
# Should show same positions as before kill
```

### Resource Usage
- [ ] CPU usage <50% at idle
- [ ] Memory usage <100MB at idle
- [ ] Disk I/O reasonable (<10MB/s sustained)
- [ ] No resource exhaustion scenarios

---

## ✅ Phase 5: Error Path Testing

### Failure Scenarios (health check should detect these)
- [ ] WebSocket dies → health check CRITICAL
- [ ] Database disconnects → health check CRITICAL
- [ ] Disk full → health check CRITICAL
- [ ] Memory exhausted → health check CRITICAL

**Test each failure:**
```bash
# Simulate WebSocket failure
pkill -f binance_stream

# Check health endpoint
curl http://localhost:8001/api/health
# Should return 503 with websocket:false
```

### Error Messages
- [ ] All errors have actionable messages
- [ ] No generic "An error occurred"
- [ ] Stack traces only in debug mode
- [ ] Errors logged consistently

### Graceful Degradation
- [ ] System degrades safely (doesn't crash)
- [ ] Critical functions have fallbacks
- [ ] Non-critical functions can fail
- [ ] Recovery is automatic or documented

---

## ✅ Phase 6: Documentation & Handoff

### Code Documentation
- [ ] Every public function has a docstring
- [ ] Every class has a docstring
- [ ] Complex algorithms have comments (WHY, not WHAT)
- [ ] No undocumented breaking changes

### User Documentation
- [ ] README covers normal operations
- [ ] Runbook documents common failures
- [ ] API documentation is current
- [ ] Configuration documented

### Operational Documentation
- [ ] Deployment procedure documented
- [ ] Rollback procedure documented
- [ ] Health check interpretation documented
- [ ] Alert thresholds documented

---

## Checklist Completion

### Sign-Off
- [ ] All 6 phases completed and verified
- [ ] No outstanding bugs or issues
- [ ] Ready for production deployment

**Signed off by:** `<your name>`  
**Date:** `<date>`  
**Phase:** `Phase <number>`  

---

## What Happens If You Skip a Phase

| Phase Skipped | What Breaks | Cost to Fix |
|---|---|---|
| Quality Review | Crashes in production | Hours of debugging + hotfix |
| Integration Verification | Modules incompatible | Redesign + rebuild |
| Stability Testing | Memory leak after 48hrs | Emergency patch + restart |
| Error Path Testing | System doesn't detect failures | Silent data loss |
| Documentation | Team can't operate it | Training costs + mistakes |

**The time to do a proper checklist < The time to fix production failures**

---

## Usage

**Before moving to next phase:**
```
1. Go through each section
2. Verify each checkbox
3. Document any issues found
4. Fix issues (don't skip items)
5. Re-verify
6. Only then: mark phase complete
```

**For this project:**
- Phase 0 (Design): Used for requirements
- Phase 1 (MVP): Should have used this checklist
- All future phases: MUST use this checklist

---

## Example: Health Check System (What We Just Fixed)

**Where checklist would have caught the issues:**

```
Phase 2: Code Quality Review
  ├─ Import Validation
  │  ├─ ❌ from backend.core.database import Database
  │  │   └─ "Database class not found" ← CAUGHT HERE
  │  └─ ✅ Fix: Use get_database() instead
  │
  └─ Type Safety
     ├─ ❌ def __init__(self):  # No return type
     │  └─ "Missing return type" ← CAUGHT HERE
     └─ ✅ Fix: Add -> None
```

**Result:** Fixes applied BEFORE deployment, not after.
