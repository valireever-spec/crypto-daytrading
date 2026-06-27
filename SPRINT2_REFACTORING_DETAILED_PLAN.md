# Sprint 2: Code Quality Refactoring (Detailed Plan)
**Timeline:** 3-4 days  
**Goal:** Split 2 large files into focused modules  
**Complexity:** MEDIUM (high risk of breaking things, need careful testing)

---

## Overview

| Task | Current | Target | Effort | Days |
|------|---------|--------|--------|------|
| **Task 2.1** | autonomous_trader.py | 5 modules | 2-3 days | 2.5 |
| **Task 2.2** | main.py | 4 modules | 2-3 days | 2.5 |
| **Task 2.3** | paper_trading.py | Monitor | 0.5 days | 0.5 |
| **Testing & Fixes** | All modules | Tests pass | 1 day | 1 |
| **TOTAL** | | | | **6 days** |

---

## Strategy: Safe Refactoring

### **Rule 1: One Module at a Time**
Never split multiple files simultaneously. Split one file completely, test, commit, then move to next.

### **Rule 2: Create Parallel Structure**
Keep old file working while building new package structure. Only delete old file after new works.

### **Rule 3: Test After Each Step**
After each module extracted, run tests to ensure nothing broke.

### **Rule 4: Git Commits**
One commit per extracted module (clear git history of what changed).

---

## Task 2.1: Refactor autonomous_trader.py (2-3 days)

### Current Structure (1,766 lines)
```
autonomous_trader.py (1 file)
├── Lines 1-100:    Imports, dataclasses (TradingConfig, TradeSignal)
├── Lines 100-200:  AutonomousTrader class init
├── Lines 200-400:  Main trading loop (_trading_loop)
├── Lines 400-700:  Entry signal logic (_check_symbol, _execute_entry)
├── Lines 700-1000: Exit signal logic (_check_exits, _execute_exit)
├── Lines 1000-1400: Portfolio decisions (_check_portfolio_decisions, _execute_portfolio_decision)
├── Lines 1400-1600: Validation helpers (_measure_data_quality, _check_daily_loss_limit, etc.)
└── Lines 1600-1766: Global functions (get_autonomous_trader, init_autonomous_trader)
```

### Target Structure (5 modules)
```
autonomous_trader/                          (package)
├── __init__.py              (40 lines)     - Exports & initialization
├── core.py                  (200 lines)    - Main loop, AutonomousTrader class
├── entry.py                 (300 lines)    - Entry signal logic
├── exit.py                  (300 lines)    - Exit signal logic
├── portfolio.py             (300 lines)    - Portfolio decisions
└── validation.py            (250 lines)    - Validation helpers
```

---

## Detailed Steps for Task 2.1

### **Step 1: Create Package Directory**

```bash
cd /home/vali/projects/crypto-daytrading

# Create package
mkdir -p backend/trading/autonomous_trader

# Move original file (backup)
cp backend/trading/autonomous_trader.py \
   backend/trading/autonomous_trader_backup.py

# Start fresh with empty files
touch backend/trading/autonomous_trader/__init__.py
touch backend/trading/autonomous_trader/core.py
touch backend/trading/autonomous_trader/entry.py
touch backend/trading/autonomous_trader/exit.py
touch backend/trading/autonomous_trader/portfolio.py
touch backend/trading/autonomous_trader/validation.py
```

### **Step 2: Move Dataclasses to core.py**

**Source:** Lines 78-100 of original file

```python
# backend/trading/autonomous_trader/core.py

"""Autonomous trading loop - core functionality."""

import asyncio
import logging
import uuid
import json
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

_signal_thread_pool = ThreadPoolExecutor(
    max_workers=2, thread_name_prefix="signal_calc"
)


@dataclass
class TradeSignal:
    """Signal to buy or sell."""
    symbol: str
    side: str  # BUY or SELL
    strength: float  # 0-100
    reason: str
    timestamp: datetime


@dataclass
class TradingConfig:
    """Configuration for autonomous trading."""
    enabled: bool = True
    entry_threshold: float = 60.0
    exit_profit_target: float = 4.5
    exit_stop_loss: float = 3.0
    position_size_pct: float = 2.5
    max_positions: int = 8
    max_daily_loss_pct: float = 5.0
    quality_gate_entry: float = 70.0
    quality_gate_exit: float = 30.0
    loop_sleep_seconds: float = 10.0
    retry_sleep_seconds: float = 5.0
    symbols: List[str] = None

    def __post_init__(self):
        if self.symbols is None:
            self.symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
```

### **Step 3: Move Main Trading Loop to core.py**

**Source:** Lines 217-399 (start, stop, _trading_loop)

Extract the main `AutonomousTrader` class and its core methods:

```python
# backend/trading/autonomous_trader/core.py (continued)

class AutonomousTrader:
    """Main autonomous trading controller."""

    def __init__(self, config: TradingConfig = None):
        self.config = config or TradingConfig()
        self.running = False
        # ... rest of __init__

    async def start(self):
        """Start the autonomous trading loop."""
        self.running = True
        logger.info("Autonomous trader starting...")
        try:
            await self._trading_loop()
        except Exception as e:
            logger.error(f"Autonomous trader error: {e}")
            self.running = False

    async def stop(self):
        """Stop the autonomous trading loop."""
        self.running = False
        logger.info("Autonomous trader stopped")

    async def _trading_loop(self):
        """Main trading loop - runs continuously.
        
        Coordinates with:
        - entry module for new signals
        - exit module for position management
        - portfolio module for rebalancing
        - validation module for health checks
        """
        # Main loop logic here - delegates to other modules
        # Don't copy validation/entry/exit code, call methods from other modules
```

### **Step 4: Move Entry Logic to entry.py**

**Source:** Lines 400-985

```python
# backend/trading/autonomous_trader/entry.py

"""Entry signal generation and execution."""

from typing import Optional
from .core import TradeSignal
# ... other imports

class AutonomousTrader:
    """Entry-related methods."""

    async def _check_symbol(self, symbol: str) -> Optional[TradeSignal]:
        """Check if symbol has entry signal."""
        # Lines 400-985 moved here
        ...

    async def _execute_entry(self, signal: TradeSignal) -> bool:
        """Execute a buy order."""
        ...
```

**Issue:** We have two `AutonomousTrader` classes now (one in core.py, one in entry.py).

**Solution:** Don't create separate classes. Instead, add methods to main AutonomousTrader in core.py by importing them:

```python
# backend/trading/autonomous_trader/core.py
from . import entry  # Import module with helper functions

# Then in _trading_loop, call:
# signal = await entry.check_symbol(self, symbol)
```

**Or better approach:** Keep AutonomousTrader as single class, but split implementation across files:

```python
# backend/trading/autonomous_trader/core.py
class AutonomousTrader:
    # All methods go here, but body is delegated to sub-modules
    
    async def _check_symbol(self, symbol):
        from . import entry
        return await entry._check_symbol_impl(self, symbol)
```

### **Step 5: Move Exit Logic to exit.py**

**Source:** Lines 1221-1400

```python
# backend/trading/autonomous_trader/exit.py

"""Exit signal generation (stop loss, profit target)."""

async def _check_exits_impl(trader_self, current_prices):
    """Check existing positions for exits."""
    # Implementation from _check_exits
    ...

async def _execute_exit_impl(trader_self, position):
    """Execute a sell order."""
    # Implementation from _execute_exit
    ...
```

### **Step 6: Move Portfolio Logic to portfolio.py**

**Source:** Lines 891-985 + 1400-1700

```python
# backend/trading/autonomous_trader/portfolio.py

"""Portfolio-level decisions (rotation, rebalance)."""

async def _check_portfolio_decisions_impl(trader_self):
    """Check for portfolio-level decisions."""
    ...

async def _execute_portfolio_decision_impl(trader_self, decision, current_prices):
    """Execute portfolio decision."""
    ...
```

### **Step 7: Move Validation to validation.py**

**Source:** Lines 735-890 (utility methods)

```python
# backend/trading/autonomous_trader/validation.py

"""Validation and health checks."""

async def _measure_data_quality_impl(trader_self, prices):
    """Measure data quality score."""
    ...

async def _check_daily_loss_limit_impl(trader_self):
    """Check if daily loss exceeded."""
    ...

async def _get_current_prices_impl(trader_self):
    """Get current market prices."""
    ...

async def _check_regime_impl(trader_self):
    """Check market regime."""
    ...

async def _get_target_allocation_impl(trader_self):
    """Get target allocation."""
    ...

def log_trading_decision(decision_type, symbol, decision, reason, context):
    """Log a trading decision."""
    ...
```

### **Step 8: Create __init__.py**

```python
# backend/trading/autonomous_trader/__init__.py

"""Autonomous trader package - monitors signals and executes trades."""

from .core import AutonomousTrader, TradingConfig, TradeSignal

# Global instance
_autonomous_trader = None

def init_autonomous_trader(config: TradingConfig = None) -> AutonomousTrader:
    """Initialize global autonomous trader."""
    global _autonomous_trader
    _autonomous_trader = AutonomousTrader(config)
    return _autonomous_trader

def get_autonomous_trader():
    """Get global autonomous trader."""
    return _autonomous_trader

__all__ = [
    'AutonomousTrader',
    'TradingConfig',
    'TradeSignal',
    'init_autonomous_trader',
    'get_autonomous_trader',
]
```

### **Step 9: Update Imports in main.py**

**Old:**
```python
from backend.trading.autonomous_trader import AutonomousTrader, TradingConfig, init_autonomous_trader, get_autonomous_trader
```

**New:** (same — __init__.py handles it)
```python
from backend.trading.autonomous_trader import AutonomousTrader, TradingConfig, init_autonomous_trader, get_autonomous_trader
```

### **Step 10: Test**

```bash
# 1. Verify imports
python -c "from backend.trading.autonomous_trader import AutonomousTrader, init_autonomous_trader; print('✅ imports OK')"

# 2. Run unit tests
pytest tests/test_signals.py -v

# 3. Run integration tests
pytest tests/integration/ -v -k "autonomous or trader"

# 4. Verify core functionality
python -c "
from backend.trading.autonomous_trader import AutonomousTrader, TradingConfig
config = TradingConfig()
trader = AutonomousTrader(config)
print('✅ AutonomousTrader instantiates')
"
```

### **Step 11: Delete Old File**

```bash
# Only after tests pass!
rm backend/trading/autonomous_trader.py
rm backend/trading/autonomous_trader_backup.py
```

---

## Task 2.2: Refactor main.py (Similar Process - 2-3 days)

### Target: Split into 4 modules

```
api/
├── main.py              (300 lines)    - FastAPI app + configuration
├── lifecycle.py         (300 lines)    - Startup/shutdown events
├── routes.py            (400 lines)    - All endpoint handlers
└── middleware.py        (200 lines)    - HTTP middleware
```

### Process:

1. Create `backend/api/` package (may already exist)
2. Extract `lifespan()` → `lifecycle.py`
3. Extract all `@app.*` handlers → `routes.py`
4. Extract middleware → `middleware.py`
5. Keep `main.py` minimal (just FastAPI app creation)
6. Update imports
7. Test thoroughly
8. Delete old file

---

## Testing Strategy

After each module is extracted:

```bash
# Unit tests for that module
pytest tests/test_signals.py -v

# Integration tests
pytest tests/integration/ -v

# Full system test
python -m backend.api.main &  # Start API
sleep 5
curl http://localhost:8001/api/health
curl http://localhost:8001/api/paper/account
```

---

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Breaking imports | Keep old file until new works, test imports first |
| Circular imports | Use TYPE_CHECKING, import at function level if needed |
| Missing functions | Copy full implementation, don't partial extracts |
| Test failures | Run tests after each step, commit working state |
| Merge conflicts | Keep changes isolated to single files/modules |

---

## Success Criteria

**After Task 2.1:**
- ✅ autonomous_trader/ package with 5 modules
- ✅ All modules <350 lines each
- ✅ All tests passing (same count as before)
- ✅ No circular imports
- ✅ Code complexity reduced (easier to understand/modify)

**After Task 2.2:**
- ✅ API routes organized into 4 modules
- ✅ Each module <400 lines
- ✅ All endpoints functional
- ✅ Tests passing
- ✅ API starts without errors

**After Both Tasks:**
- ✅ Code meets CSF Pillar #27 standards
- ✅ File sizes: all <400 lines (except paper_trading at 632)
- ✅ Pre-commit hooks can enforce standards
- ✅ Phase 2 integration work unblocked

---

## Timeline

**Day 1-2: Task 2.1 (autonomous_trader.py)**
- Morning: Create package structure, move dataclasses
- Afternoon: Move entry/exit/portfolio logic
- Evening: Test, debug, refactor

**Day 2-3: Task 2.2 (main.py)**
- Same process as above

**Day 3-4: Testing & Documentation**
- Run full integration tests
- Fix any edge cases
- Update documentation
- Prepare for Phase 2

---

## What NOT to Do

❌ Don't refactor multiple files in parallel (merge conflicts)  
❌ Don't split while tests are failing (can't tell if you broke something)  
❌ Don't delete old files before new structure works  
❌ Don't make unrelated changes (focus on splitting only)  
❌ Don't skip tests between steps (accumulated errors are hard to debug)  

---

## Ready to Start?

You'll know you're ready when:
1. ✅ Sprint 1 formatting complete (TODAY)
2. ✅ All imports working
3. ✅ Tests baseline established
4. ✅ Git is clean (no uncommitted changes)
5. ✅ .env.local configured

Then: **Start Task 2.1 tomorrow morning**

---

**Estimated Completion:** 2026-06-30 (3-4 days)  
**Next Milestone:** Phase 2 integration (heartbeat, alerts, dashboard)
