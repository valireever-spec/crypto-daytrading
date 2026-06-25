# CLAUDE.md

Crypto Daytrading Platform — Development Guidance

## Project Overview

**Name:** Crypto Daytrading HA System  
**Purpose:** Learn and practice crypto daytrading with automated execution on Binance  
**Architecture:** Dual-machine HA (active-passive redundancy)  
**Status:** Phase 0 (Design) → Phase 1 (MVP paper trading)  
**Target Launch:** 2026-07-15 (live with €1,000)

---

## Architecture Decision: Separate Project (Not integrated with investing-platform)

**Why separate?**
- ✅ Fresh codebase: easier to learn and modify
- ✅ No risk: stock platform stays stable and profitable
- ✅ Focused: 100% optimized for crypto 24/7 trading
- ✅ Independent: can fail without affecting stock system

**Reusable components from investing-platform:**
- Backtesting math (Sharpe, Sortino, drawdown)
- HA architecture (heartbeat, failover, UUID deduplication)
- Systemd timer patterns (15-min execution)
- Risk dashboard concepts (zone indicators, alerts)

**Do NOT copy:**
- yfinance integration (crypto needs Binance API)
- Stock signal generation (crypto needs different indicators)
- Market hours logic (crypto is 24/7)
- Stock-specific backtesting (crypto volatility different)

---

## Critical Systems Framework (CSF) Application

This project implements the **Critical Systems Framework (CSF)** — a 26-pillar hardening standard for autonomous trading systems.

**Current Phase:** Phase 1 (Core Safety) — 11 pillars
- Phase 1 (Paper Trading): 11 pillars ← Current
- Phase 2 (Live Trading): 17 pillars
- Phase 3 (Production): 26 pillars

See `CRITICAL_SYSTEMS_FRAMEWORK.md` for full specification.

### 1️⃣ Architecture Discipline & Traceability (Target: 4/5)

**Current Status:** Design phase  
**What we're doing:**
- V-Model requirements traceability (FR-001 → design → unit test → integration test → acceptance)
- Architecture diagram (TBD: Phase 0)
- ADRs (Architecture Decision Records) for major choices:
  - ADR-001: Separate project vs. modify investing-platform (DECIDED: separate)
  - ADR-002: Binance API wrapper vs. library (TBD)
  - ADR-003: Paper trading in-memory vs. file-backed (TBD)

**Files:**
- `FUNCTIONAL_REQUIREMENTS.md` — 9 functional requirements
- `NONFUNCTIONAL_REQUIREMENTS.md` — 26 non-functional requirements
- `ARCHITECTURE.md` (TBD) — High-level design, dependencies, data flow
- `docs/ADR/` (TBD) — Decision records per phase

**Target metric:** Every feature maps to requirement → design doc → tests

---

### 2️⃣ Build Quality In / Error-Proofing (Target: 4/5)

**Current Status:** TBD  
**Standards:**
- Type hints: 100% (mypy 0 errors)
- Linting: black + ruff (0 issues)
- Pinned dependencies: requirements.txt with exact versions
- No secrets in code: API keys only from environment variables
- Input validation: all user inputs validated at boundaries

**Files:**
- `.flake8` / `pyproject.toml` — Linting config (black, ruff, mypy)
- `requirements.txt` — Pinned dependencies (no `*` versions)
- `.env.example` — Template for environment variables (no real keys)
- `backend/core/config.py` — Configuration validation (pydantic)

**Target metric:** Pre-commit hooks catch 100% of type errors before commit

---

### 3️⃣ Verification & Validation (Target: 4/5)

**Current Status:** TBD  
**Standards:**
- Test coverage: ≥85% on critical paths (signals, execution, portfolio)
- Test gates: All tests must pass before merge
- Test types:
  - Unit: <10ms per test, no I/O
  - Integration: real Binance testnet, realistic latency
  - Acceptance: paper trading runs, live trading validation
- No tests skipped (all tagged with `@pytest.mark` for filtering)

**Files:**
- `tests/unit/` — Fast tests (<1s total), mocked I/O
- `tests/integration/` — Real Binance testnet, <30s total
- `tests/acceptance/` — Paper trading runs, 10+ days
- `tests/conftest.py` — Fixtures for mocking Binance API

**Commands:**
```bash
pytest tests/unit -v                    # Fast
pytest tests/unit tests/integration -v  # Medium (5-10s)
pytest tests/                           # All (includes 10-day paper tests)
coverage run -m pytest && coverage report  # Coverage analysis
```

**Target metric:** ≥85% coverage on FR-001 (Binance), FR-003 (strategies), FR-004 (execution), FR-005 (portfolio)

---

### 4️⃣ Continuous Integration & Safe Delivery (Target: 3/5)

**Current Status:** TBD  
**Standards:**
- Git: conventional commits (`feat:`, `fix:`, `test:`, `docs:`, `refactor:`)
- CI: Local pre-commit checks (no external CI yet)
- Deployments:
  - Paper trading: Instant (code reload)
  - Live trading: Confirmed manual step (requires yes/no prompt)
- Reversibility: All schema migrations reversible, all trades logged
- Rollback: Can instantly revert to previous strategy version

**Files:**
- `.pre-commit-config.yaml` — Pre-commit hooks (mypy, black, ruff, no-secrets)
- `scripts/test.sh` — Runs full test suite with gates
- `scripts/deploy-paper.sh` — Deploy to paper trading (fast)
- `scripts/deploy-live.sh` — Deploy to live trading (manual confirm)

**Target metric:** 100% of commits pass pre-commit checks before push

---

### 5️⃣ Root-Cause Driven Improvement (Target: 2/5 → 4/5)

**Current Status:** TBD  
**Standards:**
- Incident logs: Every trade loss >€10 logged with root cause
- Post-mortems: Weekly review of losing trades (why? preventable?)
- Refactor cadence: After every 10 trades, analyze and improve
- Tech debt: Logged and prioritized (must not block trading)

**Files:**
- `logs/trades.jsonl` — Append-only trade log (never delete)
- `logs/incidents.jsonl` — Losses >€10 with analysis
- `RETROSPECTIVES.md` (TBD) — Weekly learnings and improvements

**Target metric:** 0% repeated mistakes (same loss reason >1 time)

---

### 6️⃣ Security & Privacy by Design (Target: 4/5)

**Current Status:** TBD  
**Standards:**
- API keys: Never in code, only in `.env` (git-ignored)
- Secrets scanning: Pre-commit checks for hardcoded keys
- Input validation: All parameters validated (type, range, format)
- Rate limiting: Respect Binance 1200 req/min limit
- Audit trail: Every trade logged immutably (append-only)
- Least privilege: Read-only for non-critical operations

**Files:**
- `.env.example` — Template (no real keys)
- `.gitignore` — Ignores .env, *.key, logs/*
- `backend/core/config.py` — Pydantic validation
- `backend/exchange/auth.py` — API key loading from environment
- `logs/audit.jsonl` — Immutable trade log

**Target metric:** 0 API keys in git history, 100% input validation

---

### 7️⃣ Observability & Telemetry (Target: 4/5)

**Current Status:** TBD  
**Standards:**
- Structured logging: JSON format, timestamp + level + event + context
- Metrics: Real-time dashboard (P&L, win rate, Sharpe, system health)
- Alerts: Critical events trigger warnings with runbooks
- Health checks: Binance connectivity, order queue, failover status

**Files:**
- `backend/core/logging.py` — Structured JSON logger
- `frontend/dashboard.html` — Real-time metrics dashboard
- `backend/api/health.py` — Health check endpoints
- `docs/runbooks.md` — Runbooks for common alerts

**Logging spec:**
```json
{
  "timestamp": "2026-07-15T09:30:00Z",
  "level": "INFO",
  "event": "ORDER_FILLED",
  "symbol": "BTCUSDT",
  "side": "BUY",
  "qty": 0.5,
  "price": 45000.50,
  "order_id": "uuid-123",
  "strategy": "momentum",
  "account": "paper" or "live",
  "context": { ... }
}
```

**Target metric:** 100% of trades logged, <5s lag to dashboard update

---

### 8️⃣ Maintainability & Sustainable Pace (Target: 4/5)

**Current Status:** TBD  
**Standards:**
- File size: Max 500 lines per file (single responsibility)
- Dependencies: <10 external packages (keep it lean)
- Documentation: Every strategy documented with examples
- Naming: Domain-driven (use crypto terms: candle, position, maker/taker)
- Refactoring: Small, incremental improvements only (no big rewrites)

**Files:**
- `backend/exchange/` — Binance API wrapper (max 300 lines)
- `backend/strategies/` — Strategy implementations (max 200 lines each)
- `backend/execution/` — Order management (max 300 lines)
- `backend/portfolio/` — Position tracking (max 300 lines)
- `docs/strategies/` — Strategy guides with examples

**Target metric:** Average file size <300 lines, every strategy documented

---

## Requirements Traceability (V-Model)

All work is traced from requirements to tests:

```
REQUIREMENTS (Left)
├─ Functional (FR-001 to FR-009)
├─ Non-Functional (NFR-001 to NFR-026)
└─ Use Cases (UC-1 to UC-3)

DESIGN (Center)
├─ Architecture
├─ Data models
└─ API endpoints

IMPLEMENTATION (Center)
└─ Code modules

VALIDATION (Right)
├─ Unit Tests (UT-*)
├─ Integration Tests (IT-*)
└─ Acceptance Tests (AT-*)
```

Every requirement must map to:
1. Design document
2. Unit tests (code paths)
3. Integration test (real behavior)
4. Acceptance criteria (manual validation)

**Tracker integration:**
- Tracker dashboard shows requirement status (Proposed → Validated)
- Each requirement gets JIRA-style ID (FR-001, NFR-001, etc.)
- Link bugs to requirements when discovered
- Auto-update status as tests pass

---

## Tracker Setup (Central Dashboard)

**V-Model board:** http://localhost:5173  
**Your project files:**
- `FUNCTIONAL_REQUIREMENTS.md` — User-facing features
- `NONFUNCTIONAL_REQUIREMENTS.md` — System properties
- `V_MODEL_BOARD.md` (auto-generated) — Status + coverage %

**Your workflow:**
1. Define features in `FUNCTIONAL_REQUIREMENTS.md`
2. Tracker auto-imports every 5 minutes
3. As you implement: run tests and mark requirement as Validated
4. Link bugs when found (e.g., "signal sometimes returns NaN")
5. V_MODEL_BOARD auto-updates with progress

**Dashboard shows:**
- Requirements: Proposed (blue) → Validated (green)
- Coverage: # tests passing / # requirements
- Bugs: By severity, linked to requirements
- Phase progress: What % complete

---

## Development Workflow

### Phase 0: Design (This Week)
- [x] Create project structure
- [x] Write functional requirements (FR-001 to FR-009)
- [x] Write non-functional requirements (NFR-001 to NFR-026)
- [ ] Architecture diagram
- [ ] API endpoint design
- [ ] Data model (position, trade, account)

### Phase 1: MVP Paper Trading (Weeks 2-3)
- **FR-001:** Binance API integration (testnet)
- **FR-002:** Paper trading engine
- **FR-003:** 3-4 strategies (momentum, mean reversion, grid)
- **FR-004:** Execution engine (15-min cadence)
- **FR-005:** Portfolio tracking

**Acceptance:** 10-day paper run, >55% win rate, positive P&L

### Phase 2: HA & Live (Weeks 4-5)
- **FR-007:** Dual-machine HA (heartbeat, failover)
- **FR-008:** Dashboard & monitoring
- **FR-009:** Alerts & runbooks

**Acceptance:** 2-week live trading with €1,000, >55% win rate, no loss >5%

### Phase 3: Optimization (Weeks 6+)
- Add more strategies
- Optimize signal parameters
- Improve Sharpe ratio
- Scale capital

---

## Commands

```bash
# Setup
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run tests
pytest tests/unit -v                    # Fast
pytest tests/unit tests/integration -v  # Medium
pytest tests/                           # All (includes paper tests)
coverage run -m pytest && coverage report

# Format and lint
black . && ruff check . --fix
mypy .

# Run paper trading (manually)
python -m backend.strategies.paper_profit_strategy

# View logs
tail -f logs/trades.jsonl | jq .

# Deploy to paper trading
bash scripts/deploy-paper.sh

# Deploy to live (with confirmation)
bash scripts/deploy-live.sh
```

---

## Key Files & Directories

```
crypto-daytrading/
├── CLAUDE.md                          # This file
├── FUNCTIONAL_REQUIREMENTS.md         # 9 FR-001 to FR-009
├── NONFUNCTIONAL_REQUIREMENTS.md      # 26 NFR-001 to NFR-026
├── V_MODEL_BOARD.md                  # Auto-generated, synced every 5 min
├── ARCHITECTURE.md                    # (TBD) High-level design
│
├── backend/
│   ├── core/
│   │   ├── config.py                 # Configuration & validation
│   │   └── logging.py                # Structured JSON logging
│   ├── exchange/
│   │   ├── binance.py                # Binance API wrapper
│   │   └── paper.py                  # Paper trading simulator
│   ├── strategies/
│   │   ├── base.py                   # Strategy interface
│   │   ├── momentum.py               # Momentum scalper strategy
│   │   ├── mean_reversion.py         # Mean reversion strategy
│   │   ├── grid.py                   # Grid trading strategy
│   │   └── registry.py               # Strategy loader
│   ├── execution/
│   │   ├── order_manager.py          # Order placement & tracking
│   │   └── portfolio.py              # Position tracking
│   ├── api/
│   │   ├── main.py                   # FastAPI app
│   │   ├── routers/
│   │   │   ├── trades.py             # GET /api/trades
│   │   │   ├── positions.py          # GET /api/positions
│   │   │   ├── signals.py            # GET /api/signals
│   │   │   ├── health.py             # GET /api/health
│   │   │   └── backtest.py           # POST /api/backtest
│   │   └── schemas.py                # Pydantic models
│   └── failover/
│       └── ha_monitor.py             # Heartbeat, failover logic
│
├── frontend/
│   └── dashboard.html                # Single-page dashboard
│
├── tests/
│   ├── unit/
│   │   ├── test_exchange.py          # Binance API tests
│   │   ├── test_strategies.py        # Strategy signal tests
│   │   ├── test_execution.py         # Order execution tests
│   │   └── test_portfolio.py         # Position tracking tests
│   ├── integration/
│   │   ├── test_binance_testnet.py   # Real testnet integration
│   │   ├── test_end_to_end.py        # Full flow tests
│   │   └── test_ha.py                # Failover tests
│   └── acceptance/
│       └── test_paper_trading.py     # 10-day paper run
│
├── logs/
│   ├── trades.jsonl                  # Append-only trade log
│   ├── incidents.jsonl               # Loss analysis
│   └── system.log                    # Debug logs
│
├── docs/
│   ├── ARCHITECTURE.md               # Design overview
│   ├── runbooks.md                   # Alert runbooks
│   ├── strategies/                   # Strategy guides
│   │   ├── momentum.md
│   │   ├── mean_reversion.md
│   │   └── grid.md
│   └── ADR/                          # Architecture decisions
│       └── ADR-001-separate-project.md
│
├── scripts/
│   ├── deploy-paper.sh               # Deploy to paper trading
│   ├── deploy-live.sh                # Deploy to live (confirm)
│   └── test.sh                       # Full test suite with gates
│
├── systemd/
│   ├── crypto-trading.service        # Main API service
│   ├── crypto-trading.timer          # 15-min execution timer
│   └── crypto-failover.service       # HA monitor service
│
├── requirements.txt                  # Pinned dependencies
├── .env.example                      # Template for env vars
├── .gitignore                        # Ignore secrets, logs
├── pyproject.toml                    # Black, ruff, mypy config
├── .pre-commit-config.yaml           # Pre-commit hooks
└── README.md                         # Quick start guide
```

---

## Success Criteria (Phase 0 Design)

- [x] Separate project created
- [x] Functional requirements written (9 FR-001 to FR-009)
- [x] Non-functional requirements written (26 NFR-001 to NFR-026)
- [ ] Architecture diagram (TBD)
- [ ] Tracker board created
- [ ] All requirements registered in tracker

**When complete:** Ready for Phase 1 (code implementation)

---

## Important Notes

1. **Separate from investing-platform:** This is intentional. Learn crypto first, then decide if you want to integrate later.

2. **Focus on learning:** Paper trading for 2+ weeks before risking real money. Use this time to:
   - Understand crypto volatility (different from stocks)
   - Test multiple strategies (find what works)
   - Practice position sizing and risk management
   - Build confidence in the system

3. **HA from day 1:** Dual-machine redundancy is non-negotiable for 24/7 trading.

4. **Track everything:** Every trade logged, every loss analyzed. This data is gold for learning.

5. **Safe to live:** Once you've validated >55% win rate in paper, switching to live with €1,000 is low-risk.

---

## Next Phase: Architecture & API Design

After design is approved, we'll document:
1. **ARCHITECTURE.md** — Data flow, module dependencies, key decisions
2. **API.md** — All endpoints (GET /signals, POST /execute, etc.)
3. **DATA_MODELS.md** — Position, Trade, Account schema
4. **ADRs** — Decision records for key choices

Then: Phase 1 implementation begins.

