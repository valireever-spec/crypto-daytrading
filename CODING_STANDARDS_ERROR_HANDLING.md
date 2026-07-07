# Coding Standards: Error Handling

**Document Version:** 1.0  
**Date:** 2026-07-07  
**Purpose:** Standardize error handling across the codebase

---

## Error Handling Patterns

### ✅ RECOMMENDED PATTERNS

#### Pattern 1: Raise Exceptions (Preferred for API endpoints)
```python
async def fetch_data(url: str) -> dict:
    """Fetch data from URL or raise exception."""
    try:
        response = await client.get(url)
        return response.json()
    except Exception as e:
        logger.error(f"Failed to fetch data: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail=str(e))
```

**When to use:** API endpoints, critical operations, any place where caller MUST handle the error

**Pros:** Explicit error propagation, caller cannot ignore
**Cons:** Requires caller to catch exceptions

---

#### Pattern 2: Return Result Type (For complex scenarios)
```python
from dataclasses import dataclass
from typing import Optional, Union

@dataclass
class Result:
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None

async def fetch_data(url: str) -> Result:
    """Fetch data or return error result."""
    try:
        response = await client.get(url)
        return Result(success=True, data=response.json())
    except Exception as e:
        logger.error(f"Failed: {e}")
        return Result(success=False, error=str(e))
```

**When to use:** Functions that need to handle multiple error cases, optional operations

**Pros:** Caller can inspect success/error clearly
**Cons:** Verbose, requires Result type definition

---

#### Pattern 3: Return None + Log (For secondary operations)
```python
async def fetch_optional_config() -> Optional[dict]:
    """Fetch optional config or return None."""
    try:
        response = await client.get(url)
        return response.json()
    except Exception as e:
        logger.warning(f"Optional config unavailable: {e}")
        return None  # ← Caller checks for None
```

**When to use:** Optional features, fallback operations, non-critical paths

**Pros:** Simple, doesn't break caller
**Cons:** Caller MUST check for None

**REQUIREMENT:** ALWAYS log when returning None!

---

### ❌ ANTI-PATTERNS (DO NOT USE)

#### Anti-Pattern 1: Silent Exception Swallowing
```python
def process_data(data):
    try:
        return process(data)
    except Exception:
        pass  # ❌ NEVER DO THIS!
```

**Problem:** Caller has no idea why None is returned

---

#### Anti-Pattern 2: Bare Exception Clauses Without Logging
```python
def calculate(x):
    try:
        return 100 / x
    except:  # ❌ No logging!
        return 0
```

**Problem:** No audit trail, debugging impossible

---

#### Anti-Pattern 3: Different Error Handling for Similar Functions
```python
# Function 1: Raises exception
async def get_account():
    try:
        return await fetch(url)
    except Exception as e:
        raise HTTPException(...)  # Raises!

# Function 2: Returns empty
async def get_trades():
    try:
        return await fetch(url)
    except Exception as e:
        return []  # Returns empty!
```

**Problem:** Inconsistent API makes errors hard to track

---

## Application by Module

### API Routers (`backend/api/routers/`)
**Pattern:** Raise HTTPException
**Rationale:** HTTP clients expect exceptions for error status codes
```python
@router.get("/api/data")
async def get_data():
    try:
        data = await fetch(...)
        return data
    except Exception as e:
        logger.error(f"Failed: {e}")
        raise HTTPException(status_code=503, detail=str(e))
```

### Core Business Logic (`backend/core/`, `backend/execution/`)
**Pattern:** Raise exceptions for critical paths, log always
**Rationale:** Ensures errors propagate and are logged
```python
def close_position(position_id: int) -> None:
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE positions SET status='CLOSED' WHERE id=?", (position_id,))
        conn.commit()
    except Exception as e:
        logger.error(f"Error closing position: {e}", exc_info=True)
        raise  # ← Propagate error
    finally:
        if conn:
            conn.close()
```

### Entry/Exit Logic (`backend/trading/autonomous_trader/`)
**Pattern:** Return None + log for optional operations
**Rationale:** Entry signals are optional; not finding a signal is normal
```python
async def check_symbol(symbol: str) -> Optional[TradeSignal]:
    """Generate entry signal or None if conditions not met."""
    try:
        prices = await fetch_prices(symbol)
        if len(prices) < MIN_CANDLES:
            logger.debug(f"{symbol}: Insufficient price history")
            return None
        signal_strength = calculate_signal(prices)
        if signal_strength < THRESHOLD:
            logger.debug(f"{symbol}: Signal too weak")
            return None
        return TradeSignal(symbol, signal_strength)
    except Exception as e:
        logger.error(f"Error checking {symbol}: {e}", exc_info=True)
        return None  # Optional operation, fail silently
```

---

## Logging Requirements

### When Returning None
**MANDATORY:** Always log why None is returned
```python
❌ WRONG:
return None

✅ RIGHT:
logger.debug(f"{symbol}: Insufficient history")
return None
```

### When Raising Exception
**MANDATORY:** Log the error with context
```python
❌ WRONG:
raise HTTPException(detail="Error")

✅ RIGHT:
logger.error(f"Cannot fetch data: {e}", exc_info=True)
raise HTTPException(status_code=503, detail=str(e))
```

### When Catching Exception
**MANDATORY:** Always log before returning/raising
```python
try:
    result = do_something()
except Exception as e:
    logger.error(f"Operation failed: {e}", exc_info=True)  # ← Always log first
    return None  # OR raise, but log first
```

---

## Audit: Current State

**Compliant:** 75% of codebase (good patterns in routers, core, entry/exit)

**Non-Compliant:** 25% (silent failures, bare excepts, inconsistent patterns)

**Status:** Post-audit remediation in progress (commit 2cbc322)

---

## Checklist for Code Review

Before merging any PR:
- [ ] All try/except blocks have logging
- [ ] No bare except clauses (must specify exception type)
- [ ] If function returns None, must log why
- [ ] If function raises exception, must log before raising
- [ ] Error handling consistent with module pattern (API vs Core vs Entry/Exit)
- [ ] No silent failures (no pass without logging)

---

## Examples by Module

### ✅ GOOD: Routers
```python
# backend/api/routers/monitoring.py
try:
    health = requests.get(url, timeout=2).json()
except Exception as e:
    logger.warning(f"Failed to fetch health status: {e}")
    health = {}  ← Empty fallback with logging
```

### ✅ GOOD: Core Database
```python
# backend/core/database.py
conn = None
try:
    conn = sqlite3.connect(db_path)
    # ... operations
except Exception as e:
    logger.error(f"Database error: {e}", exc_info=True)
    raise
finally:
    if conn:
        conn.close()
```

### ✅ GOOD: Entry/Exit
```python
# backend/trading/autonomous_trader/entry.py
if len(prices) < 25:
    logger.debug(f"{symbol}: Insufficient price history (need 25+ candles)")
    return None  ← Reason logged before returning None
```

---

## Migration Path

1. **Phase 1 (Done):** Remove bare except clauses, add logging
2. **Phase 2:** Standardize patterns by module (API vs Core vs Trading)
3. **Phase 3:** Extract Result types for complex return values
4. **Phase 4:** Add pre-commit linting to enforce patterns

---

## References

- [Python Exception Handling Best Practices](https://docs.python.org/3/tutorial/errors.html)
- [FastAPI Error Handling](https://fastapi.tiangolo.com/tutorial/handling-errors/)
- [Rust Result Pattern](https://doc.rust-lang.org/book/ch09-02-recoverable-errors-with-result.html) (for inspiration)

