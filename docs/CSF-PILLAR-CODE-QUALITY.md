# CSF Pillar #27: Code Quality Excellence

**Status:** CRITICAL FOUNDATION  
**Applies To:** Every commit, every PR, entire project lifetime  
**Enforcement:** Pre-commit hooks + CI/CD gates + weekly reviews

---

## Vision

> High-quality code is not optional. It is the **foundation** that enables every other pillar. 
> Without it, we cannot trust reliability (Pillar #6), security (Pillar #9), or maintainability (Pillar #8).

A codebase that decays into technical debt will eventually:
- ❌ Fail in production (undetectable bugs)
- ❌ Lose team velocity (harder to change anything)
- ❌ Accumulate security vulnerabilities (untested edge cases)
- ❌ Become unmaintainable (impossible to onboard new team members)

---

## Standards (Non-Negotiable)

### 1. Type Hints: 100%
```python
# ❌ BAD - Not typed
def place_order(symbol, quantity, price):
    return execute(symbol, quantity, price)

# ✅ GOOD - Fully typed
def place_order(symbol: str, quantity: float, price: float) -> Dict[str, Any]:
    return execute(symbol, quantity, price)
```

**Enforcement:**
```bash
mypy . --strict
# Must be 0 errors before commit
```

### 2. Code Formatting: Black

```python
# ❌ BAD - Inconsistent
result=calculate_pnl(quantity,entry_price,exit_price,fee)

# ✅ GOOD - Auto-formatted by Black
result = calculate_pnl(quantity, entry_price, exit_price, fee)
```

**Enforcement:**
```bash
black . --check
# Auto-fix with: black .
```

### 3. Linting: Ruff (No Warnings)

```python
# ❌ BAD - Unused import
import json
from typing import Dict
result = {}

# ✅ GOOD - Clean imports
from typing import Dict
result = {}
```

**Enforcement:**
```bash
ruff check . --fix
# Must be 0 warnings
```

### 4. Cyclomatic Complexity: <10 per function

```python
# ❌ BAD - Too many branches (CC=8)
def execute_trade(order):
    if order.type == "BUY":
        if order.symbol == "BTC":
            if market.btc_price > threshold:
                if account.cash > cost:
                    if not position_exists():
                        if not rate_limited():
                            # Execute (buried 7 levels deep)
                            pass

# ✅ GOOD - Extracted early returns (CC=3)
def execute_trade(order):
    if not _validate_order(order):
        return False
    
    if not _validate_market(order):
        return False
    
    if not _validate_account(order):
        return False
    
    # Execute cleanly
    return _do_execute(order)
```

**Enforcement:**
```bash
radon cc . -a
# All functions must be CC <= 10
```

### 5. File Size: <300 lines (Max 500 with exception)

**Rule:** Split files at 400 lines, must split at 500 lines.

```
❌ main.py: 2,557 lines (UNACCEPTABLE)
❌ autonomous_trader.py: 1,766 lines (UNACCEPTABLE)
✅ paper_trading.py: 632 lines (ACCEPTABLE but at limit)
```

**Enforcement:** PR blocked if file exceeds 500 lines without explicit approval.

### 6. Duplication: <5%

```python
# ❌ BAD - Duplicated logic
def buy_order(symbol, qty):
    price = fetch_price(symbol)
    fee = price * qty * 0.001
    cost = price * qty + fee
    if account.cash < cost:
        return False
    return execute(symbol, qty, price)

def sell_order(symbol, qty):
    price = fetch_price(symbol)
    fee = price * qty * 0.001
    revenue = price * qty - fee
    if not position_exists(symbol):
        return False
    return execute(symbol, qty, price)

# ✅ GOOD - Extracted common logic
def _calculate_fee(symbol, qty, price):
    return price * qty * 0.001

def _validate_account(symbol, qty, price):
    total_cost = price * qty + _calculate_fee(symbol, qty, price)
    if account.cash < total_cost:
        return False
    return True

def buy_order(symbol, qty):
    if not _validate_account(symbol, qty, fetch_price(symbol)):
        return False
    return execute(symbol, qty, fetch_price(symbol))

def sell_order(symbol, qty):
    if not position_exists(symbol):
        return False
    return execute(symbol, qty, fetch_price(symbol))
```

**Enforcement:**
```bash
radon dup . --min 3
# Must be <5% duplication
```

### 7. Test Coverage: ≥85%

```bash
coverage run -m pytest
coverage report --fail-under=85
# PR blocked if coverage drops below 85%
```

### 8. Documentation: Every Public Function

```python
# ❌ BAD - No docstring
def calculate_pnl(entry, exit, qty):
    return (exit - entry) * qty

# ✅ GOOD - Clear docstring
def calculate_pnl(entry_price: float, exit_price: float, quantity: float) -> float:
    """Calculate realized P&L for a closed position.
    
    Args:
        entry_price: Price at which position was opened
        exit_price: Price at which position was closed
        quantity: Position size in base currency
    
    Returns:
        Realized P&L (positive = profit, negative = loss)
    """
    return (exit_price - entry_price) * quantity
```

---

## Pre-Commit Enforcement

Every commit MUST pass this gate:

```bash
#!/bin/bash
# .git/hooks/pre-commit

echo "🔍 Running quality gates..."

# Type checking
mypy . --ignore-missing-imports || exit 1

# Formatting
black --check . || exit 1

# Linting
ruff check . || exit 1

# Coverage
coverage run -m pytest --cov=backend --cov-report=term-missing
coverage report --fail-under=85 || exit 1

echo "✅ All quality gates passed"
```

**Install hook:**
```bash
chmod +x .git/hooks/pre-commit
```

---

## CI/CD Quality Gates

Every PR MUST pass:

1. **mypy --strict**
   - 0 type errors (no `# type: ignore` except explicit exceptions)

2. **black --check**
   - Code must be formatted correctly

3. **ruff check**
   - 0 linting warnings

4. **coverage --fail-under=85**
   - Minimum 85% test coverage (blocks PRs that drop coverage)

5. **radon cc -a**
   - No functions with CC > 10

6. **radon dup**
   - <5% code duplication

7. **Code Review**
   - Senior reviewer approves quality (not just functionality)

---

## Debt Management

### Tracking Technical Debt

Every piece of tech debt MUST be:
1. Logged in code with `# TODO: <reason>` comment
2. Linked to GitHub issue
3. Prioritized (P1=blocks shipping, P2=do next sprint, P3=nice-to-have)

```python
# TODO: P2 - Split this file at 500 lines (currently 632)
# GitHub issue: #123
class PaperTradingEngine:
    ...
```

### Repayment Cadence

- **P1 debt:** Fixed before next release
- **P2 debt:** Fixed next sprint
- **P3 debt:** Backlog, fix when capacity exists

---

## Consequences of Ignoring This Pillar

### What Happens Without Code Quality

**Week 1:** "It works, ship it"  
**Week 4:** "Why is adding features taking so long?"  
**Week 12:** "We can't find bugs because the code is unreadable"  
**Week 24:** "We need to rewrite everything"  

### The Debt Spiral
```
Low quality code
  ↓
More bugs
  ↓
Harder to debug
  ↓
Fixes introduce more bugs
  ↓
Team morale drops
  ↓
Code quality gets worse
  ↓
[CATASTROPHIC FAILURE]
```

---

## Success Metrics

Track these metrics every sprint:

| Metric | Target | Current |
|--------|--------|---------|
| Type Coverage | 100% | ? |
| Test Coverage | ≥85% | 97.6% ✅ |
| Avg File Size | <300 lines | 800 lines ❌ |
| Cyclomatic Complexity | <10 | ? |
| Code Duplication | <5% | ? |
| Mypy Errors | 0 | ? |
| Linting Warnings | 0 | ? |

---

## This is Non-Negotiable

**This is not a "nice-to-have."**

High code quality is:
- ✅ Required for security (Pillar #9)
- ✅ Required for reliability (Pillar #6)
- ✅ Required for maintainability (Pillar #8)
- ✅ Required for our team's ability to move fast

**Every commit that violates these standards is a step backward.**

**Every commit that maintains these standards is a step forward.**

---

**Pillar Owner:** Code Review Committee  
**Enforcement:** Pre-commit hooks + CI/CD gates  
**Review Cadence:** Weekly  
**Last Updated:** 2026-06-27  
**Effective Immediately:** ALL COMMITS GOING FORWARD
