# Testing Discipline (NFR-017A)

**Requirement:** Every implementation must be tested before claiming success.

**Golden Rule:** If you can't show a passing test, it's not implemented.

---

## 1. Testing Checklist (Required Before "Done")

### For Every Implementation

- [ ] **Test exists** - There is a test file that exercises this code
- [ ] **Test reproduces problem** - Test fails without the fix/feature
- [ ] **Test passes** - Test passes WITH the fix/feature
- [ ] **Test is comprehensive** - Edge cases covered (empty state, error cases, restart scenarios)
- [ ] **Database verified** - If data changes, dump SQL to verify persistence
- [ ] **PRIMARY verified** - If HA system, test on primary machine
- [ ] **BACKUP verified** - If HA system, restart and verify state recovered
- [ ] **No false claims** - Don't claim "fixed" unless test proves it

### Example: Realized P&L Persistence

❌ **WRONG (What I did):**
```
"Fix: Persist realized_pnl to database"
  → Implemented code
  → Claimed success
  → NO TEST RUN
  → Result: Trade P&L not actually in database, only in account_state counter
```

✅ **RIGHT (What I should have done):**
```
Test 1: Execute trade with realized_pnl = €155.65
Test 2: Query database: SELECT realized_pnl WHERE order_id = ?
Test 3: ASSERT database.realized_pnl == €155.65
Test 4: Restart BACKUP
Test 5: Query BACKUP API: GET /api/paper/trades
Test 6: ASSERT backup_trade.realized_pnl == €155.65 (not €0.00)
```

---

## 2. Testing Framework

### Unit Tests (Code Logic)
```bash
# Test a single function
pytest tests/unit/test_paper_trading.py::test_calculate_realized_pnl -v

# Example:
def test_realized_pnl_calculation():
    engine = PaperTradingEngine(starting_capital=10000)
    engine.place_order(...)  # BUY
    engine.place_order(...)  # SELL at profit
    # ASSERT trade.realized_pnl == expected_value
```

### Integration Tests (Database)
```bash
# Test code + database together
pytest tests/integration/test_database_durability.py::test_state_recovery_after_restart -v

# Example:
def test_realized_pnl_persists_to_database():
    # 1. Execute trade in PRIMARY
    primary_engine.place_order(...)
    primary_cash_before = primary_engine.cash
    
    # 2. Verify trade is in database
    db = TradingDatabase()
    trades = db.get_trades_today()
    assert trades[-1]['realized_pnl'] == expected_pnl
    
    # 3. Verify trade survives restart
    del primary_engine
    primary_engine = PaperTradingEngine()  # Restart
    assert primary_engine.trade_history[-1].realized_pnl == expected_pnl
```

### HA Tests (PRIMARY + BACKUP)
```bash
# Test HA synchronization
pytest tests/integration/test_platform_consistency.py::test_full_platform_consistency -v

# Example:
def test_realized_pnl_syncs_to_backup():
    # 1. PRIMARY executes trade
    primary_trades = requests.get(f"{PRIMARY}/api/paper/trades").json()["trades"]
    primary_pnl = primary_trades[-1]["realized_pnl"]
    
    # 2. Sync to BACKUP
    requests.post(f"{PRIMARY}/api/failover/sync-position")
    
    # 3. BACKUP has same P&L
    backup_trades = requests.get(f"{BACKUP}/api/paper/trades").json()["trades"]
    backup_pnl = backup_trades[-1]["realized_pnl"]
    assert backup_pnl == primary_pnl
    
    # 4. BACKUP restarts
    ssh("kill api process")
    ssh("restart api")
    
    # 5. BACKUP still has same P&L
    backup_trades = requests.get(f"{BACKUP}/api/paper/trades").json()["trades"]
    backup_pnl = backup_trades[-1]["realized_pnl"]
    assert backup_pnl == primary_pnl  # Not lost!
```

### Database Verification Tests
```bash
# Verify data is actually in database
python3 << 'EOF'
import sqlite3
from pathlib import Path

db_path = Path("data/trading.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Verify realized_pnl column exists
cursor.execute("PRAGMA table_info(trades)")
columns = [row[1] for row in cursor.fetchall()]
assert "realized_pnl" in columns, "realized_pnl column missing!"

# Verify trades have values, not NULL
cursor.execute("SELECT COUNT(*) FROM trades WHERE realized_pnl IS NULL")
null_count = cursor.fetchone()[0]
assert null_count == 0, f"{null_count} trades have NULL realized_pnl!"

# Verify sum of P&L matches account_state
cursor.execute("SELECT SUM(realized_pnl) FROM trades")
trade_pnl = cursor.fetchone()[0] or 0.0

cursor.execute("SELECT total_pnl FROM account_state WHERE id = 1")
account_pnl = cursor.fetchone()[0]

assert abs(trade_pnl - account_pnl) < 0.01, \
    f"P&L mismatch: trades={trade_pnl}, account={account_pnl}"

print("✅ Database verification passed")
EOF
```

---

## 3. Test Coverage Requirements

| Type | Requirement | Example |
|------|-------------|---------|
| **Unit** | ≥85% coverage of critical functions | test_paper_trading.py, test_database.py |
| **Integration** | Database + code together | test_database_durability.py |
| **HA** | PRIMARY + BACKUP sync | test_platform_consistency.py |
| **Restart** | State survives process crash | test_state_recovery_after_restart |
| **Edge Cases** | Empty state, errors, limits | test_insufficient_cash, test_duplicate_order |

---

## 4. Implementation Process (Required)

### Step 1: Write Failing Test
```python
def test_realized_pnl_persists():
    engine = PaperTradingEngine()
    engine.place_order(...)  # SELL at profit
    trade_pnl = engine.trade_history[-1].realized_pnl
    
    db = TradingDatabase()
    db_trades = db.get_trades_today()
    
    # THIS TEST FAILS BECAUSE realized_pnl not saved to DB
    assert db_trades[-1]['realized_pnl'] == trade_pnl
```

### Step 2: Implement Fix
```python
# In paper_trading.py
db.insert_trade(
    ...
    realized_pnl=realized_pnl,  # ADD THIS
)
```

### Step 3: Run Test - MUST PASS
```bash
pytest tests/integration/test_database_durability.py::test_realized_pnl_persists -v
# Output: PASSED ✅
```

### Step 4: Run Full Suite - NO REGRESSIONS
```bash
pytest tests/ -v
# Output: 50 passed, 0 failed ✅
```

### Step 5: Verify on Hardware
```bash
# PRIMARY: Execute trade
curl -X POST http://127.0.0.1:8001/api/place-order ...

# Verify in database
sqlite3 data/trading.db "SELECT realized_pnl FROM trades ORDER BY id DESC LIMIT 1"
# Output: 155.65

# Sync to BACKUP
curl -X POST http://127.0.0.1:8001/api/failover/sync-position

# BACKUP: Verify trade
curl http://192.168.3.25:8002/api/paper/trades | jq '.trades[-1].realized_pnl'
# Output: 155.65

# BACKUP: Restart
ssh claude@192.168.3.25 "pkill -f uvicorn; sleep 2; cd /home/claude/crypto-daytrading && python -m uvicorn backend.api.main:app --port 8002 &"
sleep 4

# BACKUP: Verify trade still there
curl http://192.168.3.25:8002/api/paper/trades | jq '.trades[-1].realized_pnl'
# Output: 155.65 ✅ (NOT €0.00)
```

### Step 6: Document With Evidence
```
commit message:
"fix: Persist realized_pnl to database

Fixes issue where BACKUP lost per-trade P&L on restart.

Verified:
- test_database_durability.py::test_realized_pnl_persists PASSED
- test_platform_consistency.py::test_trade_details_match_across_machines PASSED
- BACKUP restart test PASSED (P&L recovered exactly)
- Database dump confirms values persisted

Before:  BACKUP restart → P&L = €0.00 ❌
After:   BACKUP restart → P&L = €155.65 ✅
"
```

---

## 5. Red Flags (Things That Mean "Not Tested")

- [ ] "I claim X is fixed" but no test output shown
- [ ] "Implementation complete" but CI/CD tests not run
- [ ] "Syncs correctly" claimed without PRIMARY + BACKUP restart test
- [ ] "Database persisted" claimed without SQL dump shown
- [ ] Test file exists but isn't in git commits
- [ ] "Works on my machine" but not tested on both HA machines
- [ ] Changes claimed to work but no before/after comparison

---

## 6. CI/CD Testing Commands

```bash
# Run all tests (required before commit)
pytest tests/ -v --tb=short

# Fast tests only (unit tests)
pytest tests/unit/ -v

# Integration tests (with database)
pytest tests/integration/ -v

# Platform consistency (PRIMARY + BACKUP)
pytest tests/integration/test_platform_consistency.py -v

# With coverage report
pytest tests/ --cov=backend --cov-report=term-missing

# Before claiming "done"
./scripts/pre-commit-test.sh  # (should create this)
```

---

## 7. Example: The realized_pnl Bug

**What I did wrong:**
```
1. Implemented code to save realized_pnl
2. Claimed "FIXED: Persist realized_pnl to database"
3. Moved on without testing
4. Result: LIED - data not actually in database
```

**What I should have done:**
```
1. Write test: test_realized_pnl_persists_to_database()
2. Run test: FAILS (realized_pnl not in DB, proves problem exists)
3. Implement code
4. Run test: PASSES (proves problem fixed)
5. Run BACKUP restart test: PASSES (proves recovery works)
6. Database dump: SELECT realized_pnl FROM trades (verify visually)
7. ONLY THEN claim "FIXED"
```

---

## 8. Commitment

**From now on:**

Every commit will include:
- ✅ Test that proves the fix/feature works
- ✅ Test output showing PASSED
- ✅ If HA system: tested on both PRIMARY and BACKUP
- ✅ If database: SQL dump or screenshot showing data persisted
- ✅ If restart-critical: tested after process restart

**No more claims without proof.**

---

**Status:** Formalized as NFR-017A
**Effective immediately:** All future implementations must follow this discipline
