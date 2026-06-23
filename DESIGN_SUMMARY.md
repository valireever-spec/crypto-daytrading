# Design Summary — Crypto Daytrading Platform (Phase 0)

**Status:** ✅ COMPLETE — Ready for Phase 1 Implementation  
**Date:** 2026-06-23  
**Project:** Separate from investing-platform (fresh codebase, full HA redundancy)

---

## Design Deliverables ✅

| Deliverable | Status | Location | Notes |
|-------------|--------|----------|-------|
| Functional Requirements | ✅ DONE | `FUNCTIONAL_REQUIREMENTS.md` | 9 FR-001 to FR-009, traceability to tests |
| Non-Functional Requirements | ✅ DONE | `NONFUNCTIONAL_REQUIREMENTS.md` | 26 NFR-001 to NFR-026, acceptance metrics |
| V-Model Board | ✅ DONE | `V_MODEL_BOARD.md` | Progress tracker, auto-synced to tracker |
| CLAUDE.md (Guidance) | ✅ DONE | `CLAUDE.md` | 8-pillar framework, development workflow |
| Project Structure | ✅ DONE | Directory tree | backend/, frontend/, tests/, docs/, logs/ |
| Environment Config | ✅ DONE | `.env.example` | All settings, no secrets in code |
| Dependencies | ✅ DONE | `requirements.txt` | Pinned versions, core packages only |
| README.md | ✅ DONE | `README.md` | Quick start, architecture overview |
| README.md | ✅ DONE | `README.md` | Quick start, architecture overview |

---

## 8-Pillar Framework Applied

```
Pillar 1: Architecture Discipline & Traceability
  ├─ V-Model requirements (FR-001 to FR-009)
  ├─ Non-functional specs (NFR-001 to NFR-026)
  ├─ Use cases (UC-1 to UC-3)
  └─ Traceability matrix (requirement → design → test)
  
Pillar 2: Build Quality In / Error-Proofing
  ├─ Type hints: 100% (mypy 0 errors)
  ├─ Linting: black + ruff
  ├─ Pinned dependencies (requirements.txt)
  └─ Input validation on all params
  
Pillar 3: Verification & Validation
  ├─ Unit tests: <10ms, mocked I/O
  ├─ Integration tests: real Binance testnet
  ├─ Acceptance tests: 10-day paper run
  └─ Coverage target: ≥85% critical paths
  
Pillar 4: Continuous Integration & Safe Delivery
  ├─ Pre-commit hooks (mypy, black, ruff, secrets)
  ├─ Git conventional commits
  ├─ Reversible deployments
  └─ Rollback capability (strategy versioning)
  
Pillar 5: Root-Cause Driven Improvement
  ├─ Incident logs (losses >€10)
  ├─ Weekly retrospectives
  ├─ Tech debt tracking
  └─ 0% repeated mistakes
  
Pillar 6: Security & Privacy by Design
  ├─ API keys in .env only
  ├─ Secrets scanning (pre-commit)
  ├─ Input validation (all boundaries)
  ├─ Audit trail (immutable, append-only)
  └─ Rate limiting (Binance 1200 req/min)
  
Pillar 7: Observability & Telemetry
  ├─ JSON structured logging
  ├─ Real-time metrics dashboard
  ├─ Critical alerts (with runbooks)
  ├─ Health checks (API, exchange, failover)
  └─ <5s lag to dashboard
  
Pillar 8: Maintainability & Sustainable Pace
  ├─ File size: <500 lines max
  ├─ Dependencies: <10 external packages
  ├─ Documented strategies (with examples)
  ├─ Domain naming (crypto terms)
  └─ Incremental improvements only
```

---

## Key Design Decisions

### Decision 1: Separate Project (Not Integrated)

| Aspect | Separate (CHOSEN) | Modify investing-platform |
|--------|------|-----------|
| Risk | ✅ Low (fresh codebase) | ❌ High (breaks stock platform) |
| Learning | ✅ Focused (crypto only) | ❌ Complex (two systems mixed) |
| Coupling | ✅ Independent | ❌ Tight (shared code) |
| Speed | ✅ Fast iteration | ❌ Slow (refactor risk) |
| Time to live | ✅ 4 weeks | ❌ 8-12 weeks |

**Why separate?** Clean break allows learning crypto first, zero risk to profitable stock system.

---

### Decision 2: Dual-Machine HA from Day 1

| Mode | Redundancy | Risk | Recommendation |
|------|-----------|------|-----------------|
| Single machine | None | ❌ Downtime = lost trades | ❌ Unacceptable |
| HA backup | Active-passive | ✅ Failover in 30s | ✅ CHOSEN |

**Why HA?** Crypto trades 24/7. Single machine crash = missed trades, lost opportunity.

---

### Decision 3: Paper Trading for 2+ Weeks

| Strategy | Risk | Validation |
|----------|------|-----------|
| Manual on Binance | ⚠️ Learning curve high | ❌ You said "I don't know what I'm doing" |
| Paper on platform | ✅ Safe, realistic | ✅ CHOSEN (10 days minimum) |
| Go live immediately | ❌ Ruin risk | ❌ Unacceptable |

**Why paper first?** Validate >55% win rate with €10,000 virtual before risking €1,000 real.

---

### Decision 4: V-Model Traceability

| Method | Coverage | Overhead | Quality |
|--------|----------|----------|---------|
| No traceability | None | 0% | ⚠️ Unknown coverage |
| Ad-hoc testing | ~40% | Minimal | ⚠️ Gaps everywhere |
| V-Model (CHOSEN) | 100% | ~10% time | ✅ No blind spots |

**Why V-Model?** Ensures every feature has unit + integration + acceptance test. Zero surprises in production.

---

## Architecture at a Glance

```
BINANCE (24/7 market)
    ↓ (Testnet for paper, Real for live)
    
MAIN MACHINE (Active Trading)
├─ Exchange wrapper (binance_client.py)
├─ Strategies (momentum, mean_reversion, grid)
├─ Execution engine (orders, fills, audit)
├─ Portfolio tracker (positions, P&L)
└─ API (HTTP endpoints)
    
↔ Heartbeat (every 10s)

BACKUP MACHINE (Standby → Failover)
├─ Same code as main
├─ Monitors main health
├─ Takes over on 3 missed heartbeats (30s)
├─ Reads audit trail to avoid duplicate trades
└─ Falls back to main when it recovers
```

---

## Phase 1 Roadmap (4 weeks to live)

### Week 1: MVP Core
- [ ] Binance API wrapper (testnet)
  - GET ticker prices
  - POST market orders
  - GET order status
  - ~100 lines, unit tests
  
- [ ] Paper trading engine
  - Track virtual cash/positions
  - Simulate fills at market prices
  - Calculate P&L
  - ~150 lines, unit tests
  
- [ ] Basic strategy (momentum)
  - RSI + MACD signals
  - Entry/exit logic
  - Signal scoring
  - ~120 lines, unit tests

**Acceptance:** Can run paper trades manually

---

### Week 2: Strategies & Execution
- [ ] Mean reversion strategy
- [ ] Grid trading strategy
- [ ] Execution scheduler (every 15 min)
- [ ] Automated entry/exit

**Acceptance:** 3+ strategies running, auto-execute every 15 min

---

### Week 3: Paper Trading Validation
- [ ] Full 10-day paper run
- [ ] Win rate ≥55%
- [ ] Positive P&L
- [ ] All trades logged

**Acceptance:** 10-day acceptance test PASSED

---

### Week 4: HA & Live
- [ ] Dual machine sync
- [ ] Heartbeat monitoring
- [ ] Failover logic
- [ ] Live trading with €1,000

**Acceptance:** 2-week live test, no losses >5%

---

## Success Metrics

### Phase 1 (Paper Trading)
- ✅ Win rate ≥55%
- ✅ Positive P&L over 10 days
- ✅ All trades logged
- ✅ No crashes

### Phase 2 (HA)
- ✅ RTO <30s
- ✅ No duplicate trades
- ✅ Both machines synchronized

### Phase 2 (Live)
- ✅ Win rate ≥55%
- ✅ Daily P&L +€3-10
- ✅ No daily loss >5%
- ✅ Slippage <2% vs paper

---

## Testing Strategy (100% Coverage)

### Unit Tests (Week 1-2)
```
tests/unit/
├─ test_exchange.py (5 tests: fetch price, place order, etc.)
├─ test_strategies.py (15 tests: signal generation per strategy)
├─ test_execution.py (4 tests: order logic)
└─ test_portfolio.py (6 tests: position tracking)

Total: ~30 tests, <1 second, mocked I/O
```

### Integration Tests (Week 2-3)
```
tests/integration/
├─ test_binance_testnet.py (real API, 10 tests)
├─ test_end_to_end.py (full flow, 5 tests)
└─ test_ha.py (failover, 4 tests)

Total: ~20 tests, ~30 seconds, real Binance testnet
```

### Acceptance Tests (Week 3)
```
tests/acceptance/
└─ test_paper_trading.py (10-day run)
    ├─ Win rate ≥55%
    ├─ Positive P&L
    ├─ All trades logged
    └─ No crashes
```

---

## Files & Ownership

| File | Size | Owner | Status |
|------|------|-------|--------|
| FUNCTIONAL_REQUIREMENTS.md | 3KB | Claude | ✅ DONE |
| NONFUNCTIONAL_REQUIREMENTS.md | 8KB | Claude | ✅ DONE |
| CLAUDE.md | 10KB | Claude | ✅ DONE |
| V_MODEL_BOARD.md | 3KB | Claude | ✅ DONE |
| README.md | 4KB | Claude | ✅ DONE |
| requirements.txt | 1KB | Claude | ✅ DONE |
| .env.example | 2KB | Claude | ✅ DONE |
| .gitignore | 1KB | Claude | ✅ DONE |
| ARCHITECTURE.md | TBD | Next phase | ⏳ Phase 1 |
| API.md | TBD | Next phase | ⏳ Phase 1 |
| DATA_MODELS.md | TBD | Next phase | ⏳ Phase 1 |
| ADR-001, ADR-002, etc. | TBD | Next phase | ⏳ Phase 1 |

---

## Next Steps

When you're ready to proceed:

1. **Review design** — Does this architecture make sense?
2. **Approve timeline** — 4 weeks to live acceptable?
3. **Confirm tracker** — Want to use tracker.localhost:5173 for progress?
4. **Start Phase 1** — Begin implementation

**Phase 1 entry point:** `backend/exchange/binance.py` (Binance API wrapper)

---

## Questions?

- Need to adjust requirements?
- Prefer different strategies?
- Want more/fewer testing levels?
- Timeline too aggressive?

Let me know before Phase 1 starts!

