# Database Security & Poisoning Prevention

**Purpose:** Prevent corrupted, invalid, or malicious data from poisoning the trading database  
**Status:** 🚨 **CRITICAL** — Implement before Phase 2 live trading  
**Target:** 100% data integrity with audit trail

---

## Database Poisoning Vectors (Threats)

### 1️⃣ **Invalid Input Data**
**Risk:** Bad values written to DB (negative qty, invalid prices, NaN values)
```
Examples:
- quantity: -0.5 (negative position)
- price: NaN, Inf, 0.0 (invalid price)
- symbol: "FAKE_XYZ" (non-existent pair)
- side: "SELL" without open position
```

### 2️⃣ **Data Type Corruption**
**Risk:** Wrong SQL types written to DB
```
Examples:
- quantity stored as string instead of REAL
- price stored as text instead of REAL
- timestamp stored as number instead of TEXT
```

### 3️⃣ **Duplicate Transactions**
**Risk:** Same trade recorded twice (API retry without idempotency)
```
Example:
- BTCUSDT BUY 0.5 @ 61000 logged twice (double-counted)
```

### 4️⃣ **Partial Writes**
**Risk:** Transaction interrupted, partial data written
```
Example:
- Position saved to DB but trade not logged
- Position saved twice (crash between operations)
```

### 5️⃣ **Database File Tampering**
**Risk:** Direct modification of SQLite file on disk
```
Example:
- trading.db edited with sqlite3 CLI
- Trades modified or deleted outside API
```

### 6️⃣ **Schema Poisoning**
**Risk:** Schema altered or corrupted, breaking queries
```
Example:
- trades table missing columns
- open_positions table has wrong structure
```

### 7️⃣ **Audit Trail Loss**
**Risk:** Historical data modified/deleted, no proof of what happened
```
Example:
- losing trade modified to show profit
- config change not logged
```

### 8️⃣ **Race Conditions**
**Risk:** Concurrent writes cause inconsistent state
```
Example:
- Two threads insert same trade simultaneously
- Position closed and opened at same time
```

---

## Prevention Strategies

### Strategy 1: Input Validation (Gatekeeper)
**Apply to:** Every DB write operation  
**How:** Validate before INSERT/UPDATE

```python
def _validate_input(symbol: str, quantity: float, price: float, side: str):
    """Validate trade data before DB write."""
    assert symbol in VALID_SYMBOLS, f"Invalid symbol: {symbol}"
    assert quantity > 0, f"Quantity must be positive, got {quantity}"
    assert price > 0, f"Price must be positive, got {price}"
    assert side in ["BUY", "SELL"], f"Invalid side: {side}"
    assert isinstance(quantity, float), f"Quantity must be float, got {type(quantity)}"
    assert isinstance(price, float), f"Price must be float, got {type(price)}"
    assert not (math.isnan(quantity) or math.isinf(quantity)), f"Quantity is NaN/Inf"
    assert not (math.isnan(price) or math.isinf(price)), f"Price is NaN/Inf"
```

### Strategy 2: Checksums & Hash Verification
**Apply to:** All trades (immutable audit trail)  
**How:** Calculate SHA256 hash of each trade, detect tampering

```python
def _calculate_trade_hash(trade_record: Dict) -> str:
    """Hash trade for integrity verification."""
    data = json.dumps({
        'symbol': trade_record['symbol'],
        'side': trade_record['side'],
        'quantity': trade_record['quantity'],
        'price': trade_record['price'],
        'trade_time': trade_record['trade_time'],
        'order_id': trade_record['order_id'],
    }, sort_keys=True)
    return hashlib.sha256(data.encode()).hexdigest()

def verify_trade_integrity(trade_id: int) -> bool:
    """Check if trade was modified after insertion."""
    # Retrieve stored hash
    stored_hash = db.query_hash_for_trade(trade_id)
    
    # Recalculate from current data
    current_record = db.get_trade(trade_id)
    calculated_hash = _calculate_trade_hash(current_record)
    
    # Must match
    return stored_hash == calculated_hash
```

### Strategy 3: Append-Only Enforcement
**Apply to:** trades table (never update/delete)  
**How:** Schema + triggers prevent modifications

```sql
-- Make trades immutable with trigger
CREATE TRIGGER IF NOT EXISTS prevent_trade_update
BEFORE UPDATE ON trades
BEGIN
  SELECT RAISE(ABORT, 'Trades table is append-only: UPDATE not allowed');
END;

CREATE TRIGGER IF NOT EXISTS prevent_trade_delete
BEFORE DELETE ON trades
BEGIN
  SELECT RAISE(ABORT, 'Trades table is append-only: DELETE not allowed');
END;
```

### Strategy 4: Deduplication (Idempotency)
**Apply to:** All trade writes  
**How:** Use order_id as unique key, detect re-inserts

```python
def insert_trade_idempotent(order_id: str, symbol: str, side: str, 
                            quantity: float, price: float) -> bool:
    """Insert trade, reject if order_id already exists."""
    try:
        db.insert_trade(order_id, symbol, side, quantity, price)
        return True  # New trade inserted
    except sqlite3.IntegrityError as e:
        if "UNIQUE constraint failed" in str(e):
            logger.warning(f"Duplicate trade rejected: {order_id}")
            return False  # Already exists, rejected
        raise
```

### Strategy 5: Database Locking & Transactions
**Apply to:** Multi-step operations (position + trade)  
**How:** Use SQLite transactions with serialization

```python
def save_position_and_trade(symbol: str, quantity: float, price: float, 
                           order_id: str) -> bool:
    """Atomic save: position AND trade, or nothing."""
    conn = sqlite3.connect(db_path)
    conn.isolation_level = "DEFERRED"  # Serializable isolation
    try:
        cursor = conn.cursor()
        
        # Step 1: Save position
        cursor.execute("INSERT INTO open_positions ...")
        pos_id = cursor.lastrowid
        
        # Step 2: Save trade
        cursor.execute("INSERT INTO trades ...")
        
        # Both succeed or both fail
        conn.commit()
        return True
        
    except Exception as e:
        conn.rollback()  # Both rolled back
        logger.error(f"Transaction failed: {e}")
        return False
    finally:
        conn.close()
```

### Strategy 6: File-Level Protection
**Apply to:** SQLite database file on disk  
**How:** Make file read-only after each write session

```python
def protect_database_file():
    """Make trading.db read-only to prevent external tampering."""
    db_path = Path("data/trading.db")
    if db_path.exists():
        db_path.chmod(0o444)  # Read-only for all
        logger.info(f"Database file protected: {db_path}")
```

### Strategy 7: Schema Validation
**Apply to:** On every startup  
**How:** Verify schema matches expected structure

```python
def verify_schema_integrity() -> bool:
    """Check schema hasn't been tampered with."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check trades table structure
    cursor.execute("PRAGMA table_info(trades)")
    columns = {row[1]: row[2] for row in cursor.fetchall()}
    
    required = {
        'id': 'INTEGER',
        'symbol': 'TEXT',
        'side': 'TEXT',
        'quantity': 'REAL',
        'price': 'REAL',
        'trade_time': 'TEXT',
        'order_id': 'TEXT',
    }
    
    for col_name, col_type in required.items():
        if col_name not in columns or columns[col_name] != col_type:
            logger.error(f"SCHEMA POISONED: {col_name} has wrong type!")
            return False
    
    conn.close()
    return True
```

### Strategy 8: Audit Trail (Change Log)
**Apply to:** Config changes and position modifications  
**How:** Log ALL changes with timestamp, operator, before/after

```python
class AuditLog:
    def log_change(self, table: str, operation: str, record_id: int, 
                  before: Dict, after: Dict) -> None:
        """Log change for audit trail."""
        audit_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'table': table,
            'operation': operation,  # INSERT, UPDATE, DELETE
            'record_id': record_id,
            'before': before,
            'after': after,
            'user': os.getenv('MACHINE_ID', 'unknown'),
        }
        
        with open('logs/audit_trail.jsonl', 'a') as f:
            f.write(json.dumps(audit_entry) + '\n')
```

---

## Implementation Checklist

### Phase 1 (Before Trading Starts) ✅
- [x] Immutable transaction logging (implemented)
- [x] Order ID deduplication (UNIQUE constraint exists)
- [ ] Input validation on all DB writes
- [ ] SQL injection prevention (parameterized queries - already done ✅)
- [ ] Transaction atomicity for multi-step ops
- [ ] Schema verification on startup

### Phase 2 (Before Live Trading) 🚨
- [ ] Hash verification for trades
- [ ] Append-only enforcement with triggers
- [ ] Database file protection (chmod 0o444)
- [ ] Audit trail for all changes
- [ ] Backup & restore testing
- [ ] Database integrity scan on startup

### Continuous (Ongoing)
- [ ] Weekly integrity checks (hash verification)
- [ ] Monitor for unusual patterns (bulk changes)
- [ ] Backup database daily
- [ ] Test recovery from corrupted backup

---

## Example: Anti-Poisoning Insert

```python
async def insert_trade_safe(symbol: str, side: str, quantity: float, 
                           price: float, order_id: str) -> int:
    """Insert trade with full anti-poisoning checks."""
    
    # Step 1: Validate input
    _validate_input(symbol, quantity, price, side)
    
    # Step 2: Check for duplicates
    if db.trade_exists(order_id):
        logger.warning(f"Duplicate trade rejected: {order_id}")
        return -1
    
    # Step 3: Check position exists (if SELL)
    if side == "SELL":
        position = db.get_position(symbol)
        assert position is not None, f"No position to sell: {symbol}"
        assert position['quantity'] >= quantity, "Insufficient position size"
    
    # Step 4: Atomic transaction
    conn = sqlite3.connect(db_path)
    conn.isolation_level = "DEFERRED"
    try:
        cursor = conn.cursor()
        
        # Calculate hash before insert
        trade_hash = _calculate_trade_hash({
            'symbol': symbol,
            'side': side,
            'quantity': quantity,
            'price': price,
            'trade_time': datetime.utcnow().isoformat(),
            'order_id': order_id,
        })
        
        # Insert with hash
        cursor.execute("""
            INSERT INTO trades 
            (symbol, side, quantity, price, trade_time, order_id, hash)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (symbol, side, quantity, price, datetime.utcnow().isoformat(), 
              order_id, trade_hash))
        
        trade_id = cursor.lastrowid
        conn.commit()
        
        # Log to audit trail
        audit_log.log_change('trades', 'INSERT', trade_id, {}, {
            'symbol': symbol,
            'side': side,
            'quantity': quantity,
            'price': price,
            'order_id': order_id,
        })
        
        logger.info(f"Trade inserted safely: {order_id} (id={trade_id})")
        return trade_id
        
    except sqlite3.IntegrityError as e:
        conn.rollback()
        logger.error(f"Trade insert failed (integrity): {e}")
        return -1
    except Exception as e:
        conn.rollback()
        logger.error(f"Trade insert failed: {e}")
        raise
    finally:
        conn.close()
```

---

## Monitoring & Detection

### Daily Integrity Check
```bash
# Verify all trades are still intact
sqlite3 data/trading.db "SELECT COUNT(*) FROM trades WHERE hash_valid = 0"
# Should return: 0
```

### Weekly Audit Report
```bash
# Check for unusual patterns
sqlite3 data/trading.db "SELECT side, COUNT(*) FROM trades GROUP BY side"
sqlite3 data/trading.db "SELECT symbol, AVG(price), STDDEV(price) FROM trades GROUP BY symbol"
```

### Monthly Backup Verification
```bash
# Test that backup can be restored
cp data/trading.db data/trading.db.backup
# Verify backup integrity
sqlite3 data/trading.db.backup "PRAGMA integrity_check"
```

---

## Summary

**Database poisoning prevention = Layered defense:**

1. ✅ **Input validation** (catch bad data at source)
2. ✅ **Deduplication** (prevent duplicate trades)
3. ✅ **Atomicity** (all-or-nothing transactions)
4. ⏳ **Hash verification** (detect tampering)
5. ⏳ **Append-only enforcement** (prevent modifications)
6. ⏳ **File protection** (prevent external tampering)
7. ⏳ **Audit trail** (prove what happened)
8. ⏳ **Schema validation** (verify structure)

**Phase 1 Status:** ✅ Basic protections in place (validation, dedup, atomicity)  
**Phase 2 Requirement:** 🚨 All 8 strategies implemented for live trading

---

**Document Status:** SECURITY STRATEGY DEFINED  
**Next:** Implement Phase 2 anti-poisoning enhancements
