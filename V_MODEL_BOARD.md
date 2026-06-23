# V-Model Board — Crypto Daytrading Platform

**Auto-generated from FUNCTIONAL_REQUIREMENTS.md and NONFUNCTIONAL_REQUIREMENTS.md**  
**Last sync:** 2026-06-23 (placeholder — would auto-update every 5 minutes in production)

---

## Phase 0: Design (REDESIGNED - Path A)

### Functional Requirements (REVISED: 14 vs 9)

| ID | Name | Status | Tests | Coverage | NEW? |
|----|----|--------|-------|----------|------|
| FR-001 | Binance API Integration | 🔵 Proposed | 0/10 | 0% | — |
| FR-002 | Paper Trading Engine | 🔵 Proposed | 0/8 | 0% | — |
| FR-003 | Real-Time Signal Generation | 🔵 Proposed | 0/12 | 0% | ♻️ Redesigned |
| FR-003B | Dynamic Strategy Allocation | 🔵 Proposed | 0/8 | 0% | 🆕 CRITICAL |
| FR-003C | Time-Based Parameters | 🔵 Proposed | 0/6 | 0% | 🆕 CRITICAL |
| FR-004 | Real-Time Alerts | 🔵 Proposed | 0/8 | 0% | 🆕 CRITICAL |
| FR-005 | Manual Order Entry & Exit | 🔵 Proposed | 0/10 | 0% | 🆕 CRITICAL |
| FR-006 | Stop/Profit Override | 🔵 Proposed | 0/6 | 0% | 🆕 CRITICAL |
| FR-007 | System States & Pause | 🔵 Proposed | 0/5 | 0% | 🆕 CRITICAL |
| FR-008 | Dynamic Position Sizing | 🔵 Proposed | 0/12 | 0% | 🆕 CRITICAL |
| FR-009 | Portfolio Monitoring (Live) | 🔵 Proposed | 0/8 | 0% | ♻️ Redesigned |
| FR-010 | Per-Strategy Analytics | 🔵 Proposed | 0/10 | 0% | 🆕 CRITICAL |
| FR-011 | Alerts & Runbooks | 🔵 Proposed | 0/6 | 0% | ♻️ Enhanced |
| FR-012 | Trade Quality Analysis | 🔵 Proposed | 0/8 | 0% | 🆕 CRITICAL |
| FR-013 | HA Redundancy | 🔵 Proposed | 0/9 | 0% | — |
| FR-014 | Overnight Mode | 🔵 Proposed | 0/4 | 0% | 🆕 NEEDED |

**Functional Coverage:** 0/130 tests passing (0%)
**Requirements:** 14 (was 9) — All critical daytrading needs

---

### Non-Functional Requirements

| Category | ID | Name | Status | Tests |
|----------|----|----|--------|-------|
| **Performance** | NFR-001 | Signal Latency <500ms | 🔵 Proposed | 0/1 |
| | NFR-002 | Order Execution <2s | 🔵 Proposed | 0/1 |
| | NFR-003 | Candle Fetch <2s | 🔵 Proposed | 0/1 |
| | NFR-004 | Throughput ≥100 trades/day | 🔵 Proposed | 0/1 |
| | NFR-005 | Memory <500MB | 🔵 Proposed | 0/1 |
| **Reliability** | NFR-006 | Availability 99.5% | 🔵 Proposed | 0/1 |
| | NFR-007 | No Duplicate Trades | 🔵 Proposed | 0/1 |
| | NFR-008 | RTO <30s | 🔵 Proposed | 0/1 |
| | NFR-009 | RPO ≤1 trade | 🔵 Proposed | 0/1 |
| **Security** | NFR-010 | API Key Protection | 🔵 Proposed | 0/1 |
| | NFR-011 | Input Validation | 🔵 Proposed | 0/1 |
| | NFR-012 | Audit Trail | 🔵 Proposed | 0/1 |
| **Observability** | NFR-013 | Structured Logging | 🔵 Proposed | 0/1 |
| | NFR-014 | Metrics & Dashboard | 🔵 Proposed | 0/1 |
| | NFR-015 | Alerts & Runbooks | 🔵 Proposed | 0/1 |
| **Maintainability** | NFR-016 | Code Organization | 🔵 Proposed | 0/1 |
| | NFR-017 | Type Hints & Linting | 🔵 Proposed | 0/1 |
| | NFR-018 | Test Coverage ≥85% | 🔵 Proposed | 0/1 |
| | NFR-019 | Documentation | 🔵 Proposed | 0/1 |
| **Cost** | NFR-020 | Cost Coverage 2x | 🔵 Proposed | 0/1 |
| **Scalability** | NFR-021 | Asset Expansion | 🔵 Proposed | 0/1 |
| | NFR-022 | Strategy Expansion | 🔵 Proposed | 0/1 |
| **Deployment** | NFR-023 | Zero-Downtime Deploy | 🔵 Proposed | 0/1 |
| | NFR-024 | Config Management | 🔵 Proposed | 0/1 |
| **Acceptance** | NFR-025 | Paper Trading Accept | 🔵 Proposed | 0/1 |
| | NFR-026 | Live Trading Accept | 🔵 Proposed | 0/1 |

**Non-Functional Coverage:** 0/26 tests passing (0%)

---

## Open Bugs

None yet (design phase).

---

## Phase Progress (REDESIGNED Path A)

```
Phase 0: Design (Redesigned) ████████████████████░░░░░░░░░░░░░░░░░░░░ 60%
├─ Functional requirements: ✅ COMPLETE (14 FR-001 to FR-014, decision-support model)
├─ Daytrading workflows: ✅ COMPLETE (6 real scenarios mapped to requirements)
├─ Design review complete: ✅ COMPLETE (8 gaps identified & fixed)
├─ Architecture diagram: ⏳ TBD (signal alerts, manual flow, analytics)
├─ Dashboard mockups: ⏳ TBD (real-time alerts, strategy allocation sliders)
└─ Updated timeline: ✅ COMPLETE (6-7 weeks vs 4 weeks)

Phase 1: MVP + Decision Support ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 0%
├─ Week 1: Binance API + Signal generation (<500ms): ⏳ TODO
├─ Week 2: Manual order buttons + partial exits: ⏳ TODO
├─ Week 2.5: Strategy allocation + time-based params: ⏳ TODO
├─ Week 3: Real-time dashboard + alerts: ⏳ TODO
├─ Week 3.5: Dynamic position sizing + heat tracking: ⏳ TODO
├─ Week 4: Per-strategy analytics + trade quality: ⏳ TODO
├─ Week 4.5: Paper acceptance test (10 days): ⏳ TODO
└─ Acceptance: >55% win rate, positive P&L, trader can override signals

Phase 2: HA & Live ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 0%
├─ Week 5.5: HA setup (dual machine, heartbeat, UUID): ⏳ TODO
├─ Week 6: Overnight mode + SMS/push alerts: ⏳ TODO
├─ Week 6.5: Live trading test (2 weeks with €1,000): ⏳ TODO
└─ Acceptance: >55% win rate, no loss >5%, slippage <2% vs paper

OVERALL: 0% CODE BUILT, 100% DESIGNED (Phase 0.5 complete)
```

---

## Milestone Timeline (REVISED - Path A: 6-7 weeks)

| Milestone | Target Date | Status |
|-----------|-------------|--------|
| Phase 0 Design COMPLETE | 2026-06-24 | ✅ DONE (redesigned) |
| Phase 1 Week 1 (MVP Core) | 2026-07-01 | ⏳ Pending |
| Phase 1 Week 2 (Manual Interface) | 2026-07-08 | ⏳ Pending |
| Phase 1 Week 3 (Real-Time) | 2026-07-15 | ⏳ Pending |
| Phase 1 Week 4 (Analytics) | 2026-07-22 | ⏳ Pending |
| Phase 1 Acceptance (10d paper) | 2026-08-01 | ⏳ Pending |
| Phase 2 Week 5.5 (HA Setup) | 2026-08-05 | ⏳ Pending |
| Phase 2 Week 6 (Overnight/Alerts) | 2026-08-12 | ⏳ Pending |
| **Phase 2 Live Launch** | **2026-08-15** | ⏳ Pending (was 07-15) |
| Phase 2 Acceptance (2w live) | 2026-08-30 | ⏳ Pending |

**CHANGE:** 4 weeks → 6-7 weeks. More realistic, all gaps fixed.

---

## Key Metrics (Tracked)

| Metric | Target | Current | Status |
|--------|--------|---------|--------|
| **Test Coverage** | ≥85% | 0% | ⚠️ Not started |
| **Win Rate** | ≥55% | N/A | ⏳ Paper pending |
| **Sharpe Ratio** | ≥0.5 | N/A | ⏳ Paper pending |
| **Signal Latency** | <500ms | N/A | ⏳ TBD |
| **Order Latency** | <2s | N/A | ⏳ TBD |
| **Availability** | 99.5% | N/A | ⏳ Phase 2 |
| **HA RTO** | <30s | N/A | ⏳ Phase 2 |

---

## Next Steps

1. **Today:** ✅ Design complete (requirements + architecture)
2. **Tomorrow:** Start Phase 1 implementation
   - [ ] Binance API wrapper
   - [ ] Paper trading simulator
   - [ ] Initial strategies
   - [ ] Unit tests for each module
3. **Week 2:** Paper trading acceptance (10-day run)
4. **Week 3:** Phase 2 HA setup (dual machines)
5. **Week 4:** Live launch with €1,000

---

**Status Legend:**
- 🟢 Validated (tests passing)
- 🔵 Proposed (designed, waiting for tests)
- ⏳ Pending (not started)
- ⚠️ At Risk (tests failing, needs attention)
- ❌ Failed (blocker)

