# Tracker Integration: Gaps → Requirements → Fixes

**Purpose:** Link 22 gaps to Non-Functional Requirements (NFRs) for systematic tracking  
**Status:** Prepared for Phase 1 completion review (2026-07-05)

---

## Critical Gaps → NFRs

| Gap ID | Gap Name | Related NFR | Type | Phase 2 Blocker |
|--------|----------|------------|------|-----------------|
| **G-001** | State Persistence on Crash | NFR-011 (Reliability) | Data Loss Risk | ⛔ YES |
| **G-002** | Partial Fill Handling | NFR-002 (Execution Speed) | Position Integrity | ⛔ YES |
| **G-003** | Slippage Unvalidated | NFR-002, NFR-004 | Financial Risk | ⛔ YES |
| **G-004** | Daily P&L Reset Bug | NFR-015 (Risk Limits) | Control Flow | ⛔ YES |
| **G-005** | Config Unification | NFR-020 (Configurability) | Operational Risk | ⚠️ MEDIUM |

---

## High-Priority Gaps → NFRs

| Gap ID | Gap Name | Related NFR | Type | Phase 2 Blocker |
|--------|----------|------------|------|-----------------|
| **G-006** | Graceful Shutdown | NFR-011 (Reliability) | Operational | ⚠️ MEDIUM |
| **G-007** | Log Rotation | NFR-017 (Disk Management) | Operations | ⚠️ MEDIUM |
| **G-008** | RSI Division-by-Zero | NFR-006 (Signal Quality) | Code Quality | ⚠️ MEDIUM |
| **G-009** | Double-Entry Risk | NFR-015 (Risk Limits) | Safety | ⚠️ MEDIUM |
| **G-010** | Regime Detection Robust | NFR-006 (Signal Quality) | Algorithm | ⚠️ MEDIUM |
| **G-011** | Price Staleness Check | NFR-008 (Data Quality) | Alerting | ⚠️ MEDIUM |
| **G-012** | Binance Rate Limiting | NFR-003 (Latency) | API Safety | ⚠️ MEDIUM |

---

## Medium-Priority Gaps → NFRs

| Gap ID | Gap Name | Related NFR | Type | Phase |
|--------|----------|------------|------|-------|
| **G-013** | Look-Ahead Bias | NFR-021 (Backtest Accuracy) | Testing | Phase 2+ |
| **G-014** | Regime-Aware Thresholds | NFR-006 (Signal Quality) | Strategy | Phase 2+ |
| **G-015** | Pyramid Scaling | NFR-004 (Throughput) | Strategy | Phase 2+ |
| **G-016** | Cost Averaging | NFR-004 (Throughput) | Strategy | Phase 3+ |
| **G-017** | Tax Tracking | NFR-022 (Compliance) | Reporting | Phase 2+ |
| **G-018** | Multi-Timeframe Analysis | NFR-006 (Signal Quality) | Signals | Phase 2+ |
| **G-019** | Correlation-Based Risk | NFR-015 (Risk Limits) | Portfolio | Phase 2+ |
| **G-020** | Dynamic Position Sizing | NFR-004 (Throughput) | Strategy | Phase 3+ |
| **G-021** | Trade Journaling | NFR-023 (Learning) | UX | Phase 3+ |
| **G-022** | Backtesting with Live Fees | NFR-021 (Backtest Accuracy) | Testing | Phase 2+ |

---

## Tracker Status Summary

### Phase 1 (In Progress: 2026-06-25 to 2026-07-05)
- **Focus:** Run paper trading, collect data
- **Gaps Accepted:** All 22 (defer fixes)
- **Success Criteria:** 
  - ✅ Win rate ≥ 55%
  - ✅ P&L > €0
  - ✅ No crashes
  - ✅ All trades logged

### Phase 1 → Phase 2 Transition (2026-07-05 to 2026-07-15)
- **Focus:** Fix critical gaps before live trading
- **Gaps to Fix:** G-001 to G-012 (12 items)
- **Effort Estimate:** 20-25 hours
- **Validation:** 3-day paper retest with fixes

**Checkpoint:** If Phase 1 success criteria met → Proceed to fix gaps → Live Phase 2

### Phase 2+ (After 2026-07-15)
- **Focus:** Live trading with €1,000
- **Gaps Permitted Open:** G-013 to G-022 (10 items)
- **Continuous Improvement:** Fix as discovered

---

## How Tracker System Works

### 1. Gaps Document (PHASE1_GAPS_AND_FIXES.md)
- Detailed description of each gap
- Severity, impact, fix scope, effort estimate
- Links to code files and test files

### 2. NFR Mapping (This Document)
- Which gap maps to which requirement
- Blocker status (Phase 2? Phase 3?)
- Priority for scheduling fixes

### 3. Implementation Checklist (Post-Phase 1)
```bash
# After 2026-07-05, open PHASE1_GAPS_AND_FIXES.md and follow:
[ ] Fix G-001: State persistence (4-6h)
[ ] Fix G-002: Partial fills (3-4h)
[ ] Fix G-003: Slippage validation (2-3h)
[ ] Fix G-004: Daily P&L reset (1-2h)
[ ] Fix G-005: Config unification (2-3h)
[ ] Fix G-006: Graceful shutdown (1-2h)
[ ] Fix G-007: Log rotation (1h)
[ ] Fix G-008: RSI div-by-zero (1h)
[ ] Fix G-009: Double-entry (1-2h)
[ ] Fix G-010: Regime detection (2h)
[ ] Fix G-011: Price staleness (1-2h)
[ ] Fix G-012: Rate limiting (1-2h)
[ ] Retest with 3-day paper run
[ ] Code review + approval
[ ] Deploy to Phase 2
```

---

## Tracker Integration Points

### In CLAUDE.md
Link to this document under "After Phase 1" roadmap:
```
→ Phase 2: If >55% win rate, proceed to live trading with €1,000
  1. Review PHASE1_GAPS_AND_FIXES.md (22 items)
  2. Fix G-001 to G-012 (12 critical/high items)
  3. Validate with 3-day paper retest
  4. Deploy to Phase 2
```

### In V-Model Dashboard (http://localhost:5173)
Proposed requirements & gaps:
- NFR-011 → Blocked by G-001 (State Persistence)
- NFR-015 → Blocked by G-004 (Daily P&L Reset)
- NFR-002 → Blocked by G-002 (Partial Fills)

### In Git Commits
Reference gaps when fixing:
```bash
git commit -m "Fix G-001: State persistence via SQLite"
git commit -m "Fix G-002: Partial fill handling with polling"
```

---

## Risk Assessment: Phase 1 → Phase 2 Transition

### If Phase 1 Success (Win Rate ≥55%, P&L > €0)
```
Phase 1 End (2026-07-05)
    ↓
Fix G-001 to G-012 (1 week)
    ↓
3-day paper retest
    ↓
Phase 2 Go Live (2026-07-15) ✅
```

### If Phase 1 Failure (Win Rate <45% or P&L negative)
```
Phase 1 End (2026-07-05)
    ↓
Root Cause Analysis:
  - Review SIGNAL_DECISION logs
  - Analyze slippage (might be G-003)
  - Check regime detection (might be G-010)
  - Verify config (might be G-005)
    ↓
Fix discovered issues + G-001 to G-012
    ↓
Retry Phase 1 for another 10 days
    ↓
Phase 2 Go Live (2026-07-22) ⏳
```

---

## Decision Gate (2026-07-05)

**Questions to Answer:**
1. ✅ Is win rate ≥ 55%?
2. ✅ Is cumulative P&L > €0?
3. ✅ Were there crashes? (should be 0)
4. ✅ Are all trades logged?

**If ALL YES:**
- Proceed to fix G-001 to G-012
- Schedule Phase 2 for 2026-07-15

**If ANY NO:**
- Analyze what went wrong
- Check if gap-related (slippage? regime? config?)
- Fix root cause + G-001 to G-012
- Retry Phase 1 for another 10 days

---

**Document Purpose:** Central tracker for 22 known gaps  
**Last Updated:** 2026-06-25  
**Next Review:** 2026-07-05 (Phase 1 completion)  
**Responsible:** Vali Reever (ilie_vali@yahoo.com)
