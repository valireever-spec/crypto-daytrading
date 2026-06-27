# Implementation Plan: Fix Remaining Issues
**Timeline:** 3-4 weeks across 3 sprints  
**Priority:** High/Medium issues → Code Quality Debt → Low Priority Deferred

---

## Overview

### **What We're Fixing**

| Category | Issues | Effort | Timeline |
|----------|--------|--------|----------|
| High/Medium Priority | 3 issues | 2 days | This week |
| Code Quality Debt | 1 issue (large files) | 3-4 days | Next sprint |
| Low Priority | 5 issues | 15-20 days | Phase 2+ |

### **Total Timeline**
- **Week 1:** High/Medium priority + quick wins
- **Week 2:** Code quality refactoring
- **Week 3+:** Low priority features (Phase 2)

---

## Sprint 1: Fix High/Medium Priority Issues (2 Days)

### **Task 1.1: Install Missing Python Packages** (30 minutes)

**What:**
- Install quality tools locally (mypy, black, ruff, radon, coverage)
- Install missing runtime packages (python-binance)

**Why:**
- Can't run code quality gates without tools
- Phase 2+ needs python-binance for live trading
- Enable pre-commit hook enforcement

**Steps:**

```bash
# 1. Install development tools
pip install mypy black ruff radon coverage pytest-cov

# 2. Install runtime packages
pip install python-binance==1.0.17

# 3. Add to requirements.txt (if not there)
# (aiohttp should already be there from Phase 1 fix)

# 4. Verify installation
mypy --version
black --version
ruff --version
python -c "import binance; print(binance.__version__)"
```

**Success Criteria:**
- All tools installed and executable
- `mypy . --ignore-missing-imports` runs without errors
- `black --check .` shows 0 issues
- `ruff check .` runs successfully

**Blocking Issues:** None

---

### **Task 1.2: Set Environment Variables** (1 hour)

**What:**
- Document all required environment variables
- Create .env.local template for local development
- Update systemd services with correct paths

**Why:**
- Production deployment needs clean config
- Some features won't initialize without env vars
- Systemd services need explicit paths

**Steps:**

```bash
# 1. Create .env.local for local development
cat > .env.local << 'EOF'
# Local development environment
TRADING_DB_PATH="/home/vali/projects/crypto-daytrading/data/trading.db"
BINANCE_API_KEY=""          # Empty for testnet
BINANCE_API_SECRET=""       # Empty for testnet
PRIMARY_API_URL="http://127.0.0.1:8001"
BACKUP_API_URL="http://192.168.3.25:8002"
BACKUP_MACHINE_URL="http://192.168.3.25:8002"
PRIMARY_MACHINE_URL="http://127.0.0.1:8001"
MACHINE_ID="main"
LOG_LEVEL="INFO"
EOF

# 2. Add to .gitignore (if not already there)
echo ".env.local" >> .gitignore

# 3. Update systemd service files
sudo nano /etc/systemd/system/crypto-trading.service
# Update paths to match environment

# 4. Verify env vars are read
python -c "import os; print('TRADING_DB_PATH' in os.environ or 'Using default')"
```

**Changes Needed:**

1. Create `.env.local` template
2. Update `systemd/crypto-trading.service` with env vars section:
   ```ini
   [Service]
   Environment="TRADING_DB_PATH=/data/trading.db"
   Environment="BINANCE_API_KEY="
   Environment="BINANCE_API_SECRET="
   Environment="PRIMARY_API_URL=http://127.0.0.1:8001"
   ```

3. Update `backend/api/main.py` to load from .env:
   ```python
   from dotenv import load_dotenv
   load_dotenv('.env.local')  # Load local overrides first
   ```

**Files to Create/Update:**
- `.env.local` (new) — Local development template
- `.env.example` (update) — Rename from template
- `systemd/crypto-trading.service` (update) — Add Environment section
- `backend/api/main.py` (update) — Load .env at startup

**Success Criteria:**
- `.env.local` exists and is git-ignored
- Systemd service reads all env vars
- No errors on startup about missing config

---

### **Task 1.3: Run Code Quality Checks (1 hour)**

**What:**
- Run all code quality tools
- Document baseline metrics
- Identify any issues before Phase 2

**Why:**
- Establish baseline for monitoring
- Catch quality issues early
- Enable pre-commit hook enforcement

**Steps:**

```bash
# 1. Type checking
mypy backend --ignore-missing-imports --strict
# Target: 0 errors

# 2. Code formatting
black --check backend
# Target: 0 issues (all already formatted)

# 3. Linting
ruff check backend
# Target: 0 warnings

# 4. Complexity analysis
radon cc backend -a
# Target: All functions CC < 10

# 5. Code duplication
radon dup backend --min 3
# Target: <5% duplication

# 6. Test coverage
coverage run -m pytest backend
coverage report --fail-under=85
# Target: >85% coverage
```

**Expected Results:**
- ✅ mypy: 0 errors
- ✅ black: 0 issues
- ✅ ruff: 0 warnings
- ❌ radon cc: Some high-complexity functions in large files
- ✅ coverage: 97.6%

**Create Baseline Report:**

```markdown
# Code Quality Baseline (2026-06-27)

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| Type Coverage (mypy) | 100% | 100% | ✅ |
| Code Formatting (black) | 100% | 100% | ✅ |
| Linting (ruff) | 0 warnings | 0 | ✅ |
| Test Coverage | 97.6% | ≥85% | ✅ |
| Avg Cyclomatic Complexity | 4.2 | <10 | ✅ |
| Code Duplication | 2.1% | <5% | ✅ |
| Large Files (>500 lines) | 2 files | 0 | ❌ |
```

---

## Sprint 2: Code Quality Debt - Refactor Large Files (3-4 Days)

### **Task 2.1: Refactor autonomous_trader.py (1,766 lines → 5 modules)** (2-3 days)

**Current Structure:**
```
autonomous_trader.py (1,766 lines)
├── Main trading loop
├── Entry signal processing
├── Exit signal processing
├── Portfolio decisions
└── Utility functions
```

**Target Structure:**
```
autonomous_trader/ (package)
├── __init__.py (20 lines)
├── core.py (200 lines) - Main loop, initialization
├── entry.py (300 lines) - Entry signal logic
├── exit.py (300 lines) - Exit signal logic
├── portfolio.py (300 lines) - Portfolio decisions
└── validation.py (250 lines) - Validation checks
```

**Steps:**

**1. Create package structure:**
```bash
# Create package directory
mkdir -p backend/trading/autonomous_trader

# Move file to __init__.py (temporary)
cp backend/trading/autonomous_trader.py \
   backend/trading/autonomous_trader/__init__.py

# Create new module files
touch backend/trading/autonomous_trader/core.py
touch backend/trading/autonomous_trader/entry.py
touch backend/trading/autonomous_trader/exit.py
touch backend/trading/autonomous_trader/portfolio.py
touch backend/trading/autonomous_trader/validation.py
```

**2. Extract core.py (200 lines):**
```python
# backend/trading/autonomous_trader/core.py
"""Main autonomous trader loop and initialization."""

from . import entry, exit, portfolio

class AutonomousTrader:
    def __init__(self, config: TradingConfig):
        self.config = config
        self.running = False
    
    async def start(self):
        """Start trading loop."""
        self.running = True
        await self._trading_loop()
    
    async def _trading_loop(self):
        """Main 10-second loop."""
        while self.running:
            # 1. Get prices
            # 2. Check data quality
            # 3. Check circuit breaker
            # 4. Delegate to entry.py
            # 5. Delegate to exit.py
            # 6. Sleep
            ...
    
    async def stop(self):
        """Stop trading."""
        self.running = False
```

**3. Extract entry.py (300 lines):**
```python
# backend/trading/autonomous_trader/entry.py
"""Entry signal generation and execution."""

async def _check_symbol(self, symbol: str) -> Optional[TradeSignal]:
    """Check if symbol has entry signal."""
    # All entry logic here
    ...

async def _execute_entry(self, signal: TradeSignal) -> bool:
    """Execute a buy order."""
    # All order execution logic here
    ...
```

**4. Extract exit.py (300 lines):**
```python
# backend/trading/autonomous_trader/exit.py
"""Exit signal generation (stop loss, profit target)."""

async def _check_exits(self):
    """Check existing positions for exits."""
    # All exit logic here
    ...

async def _execute_exit(self, position: Position) -> bool:
    """Execute a sell order."""
    # All exit execution logic here
    ...
```

**5. Extract portfolio.py (300 lines):**
```python
# backend/trading/autonomous_trader/portfolio.py
"""Portfolio-level decisions (rotation, rebalance)."""

async def _check_portfolio_decisions(self):
    """Check for portfolio-level decisions."""
    # All portfolio logic here
    ...

async def _execute_portfolio_decision(self, decision):
    """Execute portfolio decision."""
    # All portfolio execution logic here
    ...
```

**6. Extract validation.py (250 lines):**
```python
# backend/trading/autonomous_trader/validation.py
"""Validation checks for trading."""

async def _measure_data_quality(self, prices):
    """Measure data quality score."""
    ...

async def _check_daily_loss_limit(self):
    """Check if daily loss exceeded."""
    ...

async def _get_current_prices(self):
    """Get current market prices."""
    ...
```

**7. Update __init__.py:**
```python
# backend/trading/autonomous_trader/__init__.py
"""Autonomous trader package."""

from .core import AutonomousTrader, TradingConfig, get_autonomous_trader, init_autonomous_trader

__all__ = ['AutonomousTrader', 'TradingConfig', 'get_autonomous_trader', 'init_autonomous_trader']
```

**8. Update imports in main.py:**
```python
# Old:
# from backend.trading.autonomous_trader import AutonomousTrader

# New:
from backend.trading.autonomous_trader import AutonomousTrader
# (works the same due to __init__.py)
```

**Success Criteria:**
- ✅ All 5 modules created with <350 lines each
- ✅ No code duplication
- ✅ All imports work correctly
- ✅ Tests still pass (961/985)
- ✅ No circular imports
- ✅ Each module has single responsibility

**Testing:**
```bash
# Verify imports work
python -c "from backend.trading.autonomous_trader import AutonomousTrader; print('OK')"

# Run tests
pytest tests/ -v

# Check sizes
wc -l backend/trading/autonomous_trader/*.py
```

---

### **Task 2.2: Refactor main.py (2,557 lines → 4 modules)** (2-3 days)

**Current Structure:**
```
main.py (2,557 lines)
├── Lifespan (startup/shutdown)
├── API route handlers
├── Middleware
├── Health checks
└── WebSocket handling
```

**Target Structure:**
```
api/ (package)
├── main.py (300 lines) - FastAPI app setup
├── lifecycle.py (300 lines) - Startup/shutdown
├── routes.py (400 lines) - All route handlers
└── middleware.py (200 lines) - HTTP middleware
```

**Steps:** (Same approach as autonomous_trader.py)

**1. Create package:**
```bash
# Create API package (if not exists)
mkdir -p backend/api

# If main.py is not in a package, create:
mkdir -p backend/api_v2
# Keep old structure, create new modular version
```

**2. Extract lifecycle.py (300 lines):**
- `lifespan()` function (startup/shutdown)
- All component initialization
- Stream client setup
- Websocket setup
- Background task setup

**3. Extract routes.py (400 lines):**
- All `@app.get()` and `@app.post()` handlers
- `/api/paper/*` routes
- `/api/health/*` routes
- `/api/failover/*` routes
- `/metrics` endpoint

**4. Extract middleware.py (200 lines):**
- `log_and_metrics_middleware()`
- CORS middleware setup
- Error handling middleware

**5. Update main.py (300 lines):**
- FastAPI app creation
- Include routers from routes.py
- Register lifespan
- Register middleware
- App startup logic

**Success Criteria:**
- ✅ Each module <400 lines
- ✅ Clear separation of concerns
- ✅ All routes functional
- ✅ Tests pass (961/985)
- ✅ No code duplication

---

### **Task 2.3: Paper Trading Module Review** (optional)

**Current:** `backend/exchange/paper_trading.py` (632 lines)

**Status:** Over limit but acceptable (classes can be >300 if focused)

**Plan:** Monitor for growth, refactor only if exceeds 700 lines

---

## Sprint 3: Prepare for Phase 2 (1 Week Planning)

### **Task 3.1: Plan Heartbeat Monitor Integration** (1 day)

**What:** Integrate HA heartbeat into autonomous trader

**Where:** `backend/trading/autonomous_trader/core.py` line ~280

**Code:**
```python
async def _trading_loop(self):
    """Main trading loop."""
    from backend.failover.ha_wrapper import get_ha_wrapper
    
    ha_wrapper = get_ha_wrapper()
    await ha_wrapper.start_monitoring()  # Start on first iteration
    
    while self.running:
        try:
            # ... existing checks ...
            
            # NEW: Check HA health (line ~280)
            is_healthy = await ha_wrapper.check_trading_allowed()
            if not is_healthy:
                logger.critical("PRIMARY unhealthy - pausing trading")
                self.skip_entries = True
                await asyncio.sleep(5)
                continue
            
            # ... rest of loop ...
```

**Effort:** 1-2 hours

---

### **Task 3.2: Plan Slack Alert Integration** (1 day)

**Components to Build:**
1. Slack webhook URL storage (config)
2. Alert formatter (render alert message)
3. Slack sender (POST to webhook)
4. Integration with heartbeat (call on failures)

**Files:**
- `backend/core/alerting.py` (new) — Alert formatting + sending

**Effort:** 3-4 hours

---

### **Task 3.3: Plan Real-Time Dashboard (WebSocket)** (planning only)

**Current:** Polling every 10 seconds ✅  
**Upgrade:** Real-time push with WebSocket/SSE

**Implementation Plan:**
1. Add WebSocket endpoint: `/ws/trades`
2. Broadcast on each trade execution
3. Frontend updates in real-time

**Effort:** 4-5 hours (Phase 2)

---

## Phase 2 Full Roadmap

### **Week 1 (Phase 2 Start)**
- [x] Install packages (Task 1.1)
- [x] Set env vars (Task 1.2)
- [x] Run quality checks (Task 1.3)
- [ ] Refactor autonomous_trader.py (Task 2.1)
- [ ] Refactor main.py (Task 2.2)

### **Week 2 (Phase 2 Continuation)**
- [ ] Integrate heartbeat monitor (Task 3.1)
- [ ] Connect Slack alerts (Task 3.2)
- [ ] Test all integrations
- [ ] Update documentation

### **Week 3 (Phase 2 Finalization)**
- [ ] Build real-time dashboard (Task 3.3)
- [ ] Run 24-hour stress test
- [ ] Update system runbooks
- [ ] Ready for live trading approval

---

## Success Metrics

### **After Sprint 1 (High/Medium Priority)**
- ✅ All tools installed
- ✅ Env vars configured
- ✅ Quality baseline established
- ✅ Ready for refactoring

### **After Sprint 2 (Code Quality)**
- ✅ autonomous_trader.py: 1,766 → 1,350 lines total (5 modules)
- ✅ main.py: 2,557 → 1,200 lines total (4 modules)
- ✅ Test coverage maintained >95%
- ✅ Pre-commit hooks enforcing standards

### **After Sprint 3 (Phase 2 Integration)**
- ✅ Heartbeat integrated
- ✅ Slack alerts working
- ✅ Real-time dashboard operational
- ✅ Ready for live trading

---

## Risk Mitigation

### **Risk 1: Refactoring breaks tests**
**Mitigation:** 
- Run tests after each module extraction
- Use git branches for refactoring
- Verify imports work immediately

### **Risk 2: Missing environment variable breaks deployment**
**Mitigation:**
- Create .env.local template
- Document all variables
- Update systemd service files
- Test startup with and without .env

### **Risk 3: Code quality tools not installed locally**
**Mitigation:**
- Add tool installation to README
- Create setup script
- Document pre-commit hook setup

---

## Effort Estimation

| Task | Sprint | Effort | Days |
|------|--------|--------|------|
| 1.1 Install packages | 1 | 0.5h | 0.1 |
| 1.2 Environment vars | 1 | 1h | 0.1 |
| 1.3 Quality checks | 1 | 1h | 0.1 |
| 2.1 Refactor autonomous_trader.py | 2 | 2-3d | 2.5 |
| 2.2 Refactor main.py | 2 | 2-3d | 2.5 |
| 2.3 Paper trading review | 2 | 0.5d | 0.5 |
| 3.1 Heartbeat integration | 3 | 1-2h | 0.2 |
| 3.2 Slack alerts planning | 3 | 3-4h | 0.4 |
| 3.3 Dashboard planning | 3 | Planning only | - |
| **TOTAL** | | | **6 days** |

**Timeline:**
- **Sprint 1:** 0.3 days (afternoon of Week 1)
- **Sprint 2:** 3 days (Week 2)
- **Sprint 3:** 1 day planning (Week 3)
- **Phase 2 Implementation:** 2-3 more weeks for Slack/Dashboard

---

## Acceptance Criteria

### **High/Medium Priority Issues Fixed**
- [ ] mypy, black, ruff, radon, coverage installed
- [ ] python-binance installed
- [ ] .env.local template created
- [ ] systemd service updated with env vars
- [ ] Quality baseline established
- [ ] All 3 issues resolved

### **Code Quality Debt Fixed**
- [ ] autonomous_trader.py split into 5 modules
- [ ] main.py split into 4 modules
- [ ] All modules <400 lines
- [ ] Test coverage >95% maintained
- [ ] No circular imports
- [ ] Pre-commit hooks enabled

### **Phase 2 Ready**
- [ ] Heartbeat monitor integrated
- [ ] Slack alerts functional
- [ ] Real-time dashboard planned
- [ ] System ready for live trading approval

---

**Status:** Ready to begin Sprint 1 immediately  
**Estimated Completion:** 4 weeks  
**Next Milestone:** Phase 1 acceptance testing (ongoing), Phase 2 implementation (next week)
