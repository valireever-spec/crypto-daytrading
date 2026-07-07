# Coding Standards: Comments

**Document Version:** 1.0  
**Date:** 2026-07-07

---

## Comment Style Guide

### Single-Line Comments

**Style:** `# Comment with space` (space after #)

```python
✅ CORRECT:
# This is a comment
x = 5  # Inline comment

❌ WRONG:
#This is a comment (missing space)
x = 5  #Inline comment (missing space)
```

### Multi-Line Comments

**Style:** Use `"""..."""` for docstrings, `#` for comment blocks

```python
✅ CORRECT:
def my_function():
    """One-line docstring."""
    pass

# Block comment explaining
# complex logic that follows
def complex_function():
    pass

❌ WRONG:
def my_function():
    # This is a docstring
    # But should be triple-quoted
    pass
```

### Inline Comments

**Rule:** Only use when the WHY is not obvious; prefer clear variable names

```python
✅ CORRECT:
# Avoid dividing by zero when price is stale
if entry_price > 0:
    gain_pct = (current_price - entry_price) / entry_price * 100

❌ WRONG:
# Calculate gain percentage
gain_pct = (current_price - entry_price) / entry_price * 100
```

### Docstring Format

**Style:** Google-style docstrings

```python
def fetch_trades(limit: int = 100) -> List[Trade]:
    """Fetch trade history from database.

    Args:
        limit: Maximum number of trades to return (default 100).

    Returns:
        List of Trade objects, most recent first.

    Raises:
        DatabaseError: If database connection fails.
    """
    pass
```

### TODO/FIXME/HACK Comments

**Rule:** Include GitHub issue number, not just bare comments

```python
✅ CORRECT:
# TODO: Issue #123 - Replace with Result type for better error handling
def my_function():
    pass

❌ WRONG:
# TODO: This needs fixing
def my_function():
    pass
```

---

## Current State

**Status:** Generally good, minor inconsistencies in:
- Multi-line comment blocks sometimes use `#` vs `"""` interchangeably
- Some inline comments explain WHAT instead of WHY
- A few TODO comments without issue references

**Effort to Fix:** Low - mostly documentation update

---

## Checklist

Before committing:
- [ ] Single-line comments have space after `#`
- [ ] Multi-line: Use `"""` for docstrings, `#` for blocks
- [ ] Inline comments explain WHY, not WHAT
- [ ] All TODO/FIXME have issue numbers
- [ ] Docstrings follow Google format

