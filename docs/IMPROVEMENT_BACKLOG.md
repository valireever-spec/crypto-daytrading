# Improvement Backlog

**Purpose**: Track patterns of recurring issues and improvements that drive maturity.

**Review Cadence**: Monthly  
**Last Updated**: 2026-06-24

---

## Pattern: Incidents & Lessons

Each incident teaches us something. This backlog captures those lessons and prevents repeats.

### Lesson 1: Global State Causes Testing Headaches

**Pattern**: Singleton patterns with global mutable state  
**Incidents**: None (proactively detected in Phase 336)  
**Severity**: High  
**Status**: ✅ RESOLVED (Phase 336)

**Problem**:
- Asset registry, currency calculator, optimizer were singletons
- Tests couldn't isolate state; test pollution occurred
- Mutation risks if shared state modified unexpectedly

**Solution Applied**:
- Removed globals entirely (Phase 336)
- Implemented dependency injection
- Direct class instantiation instead of init/get functions
- Documented in ADR-001

**Improvement**:
- Test isolation perfect
- Code clarity improved (dependencies explicit)
- Pillar 1 (Architecture) improved from 3/5 → 4/5

**Prevention**:
- Code review rule: "No global mutable state"
- Linter rule: Flag singletons
- New checklist item: "Are tests isolated?"

---

### Lesson 2: No Observability = Slow Debugging

**Pattern**: Lack of structured logging and metrics  
**Incidents**: Slow debugging of API latency spike (estimated)  
**Severity**: High  
**Status**: ✅ RESOLVED (Phase 337)

**Problem**:
- Had plain text logs; hard to parse and aggregate
- No request correlation IDs
- No metrics; had to guess what's slow
- Latency percentiles unknown (only saw averages)

**Solution Applied**:
- JSON structured logging (Phase 337)
- Request ID in every log line
- Metrics collector with latency histograms (p50, p95, p99)
- `/metrics` endpoint for real-time visibility

**Improvement**:
- Can now correlate logs across services (when distributed)
- Latency regressions visible immediately
- SLO enforcement possible
- Pillar 7 (Observability) improved from 2/5 → 4/5

**Prevention**:
- Monitoring checklist in PR review
- Runbooks for common latency scenarios
- SLO alerts trigger before user impact

---

### Lesson 3: Hardcoded Values Scattered Everywhere

**Pattern**: Magic numbers and strings in code  
**Incidents**: Hard to adjust risk parameters, FX rates, fees without code edits  
**Severity**: Medium  
**Status**: ✅ PARTIAL (Phase 336 config module; more needed)

**Problem**:
- FX rates in currency_risk.py (hardcoded dict)
- Risk-free rate 0.02 in global_optimization.py
- Transaction costs 0.001 scattered around
- Different values in different places (inconsistent)

**Solution Applied** (Phase 336):
- Centralized configuration module
- `backend/config/asset_config.py` with all defaults
- Deep copy of config on instantiation (prevents mutation)
- All values from one place

**Still Needed**:
- Alert thresholds (error rate >10%, latency >1s)
- Spread values (ETF 1bp, US 4bp, EU 10bp, Asia 20bp)
- Load from environment vars (different prod/staging values)

**Prevention**:
- Config review: "Are there any hardcoded values?"
- Linter rule: Flag magic numbers >0 (except array indices)
- Checklist: "Can this be changed without code edits?"

---

### Lesson 4: No Root-Cause Analysis Process

**Pattern**: Issues fixed but root causes never addressed  
**Incidents**: Would keep happening if not systematized  
**Severity**: High (causes repeats)  
**Status**: ✅ RESOLVED (Phase 337)

**Problem**:
- No incident response process documented
- Didn't ask "why?" 5 times to get root cause
- Symptoms fixed; root causes allowed to grow
- Debt accumulated silently

**Solution Applied** (Phase 337):
- Incident Response Process (5 phases)
- 5-Why framework documented
- Post-mortem template created
- Technical debt register started (TECHNICAL_DEBT.md)
- Improvement backlog (this document)

**Improvement**:
- Every incident now drives process improvement
- Root causes tracked in debt register
- Lessons shared with team
- Pillar 5 (Root-Cause) improved from 2/5 → 4/5

**Prevention**:
- Every incident → post-mortem within 48h
- Post-mortem → debt register entry
- Quarterly review of debt (deprioritize/fix/accept)

---

### Lesson 5: No Security Until End (Bolted-On)

**Pattern**: Security added after features  
**Incidents**: None yet; proactively prevented in Phase 337  
**Severity**: Critical (if real incident)  
**Status**: ✅ RESOLVED (Phase 337)

**Problem**:
- Phase 336 had no auth on endpoints
- Anyone could call /api/multi-asset/assets
- No tokens, no roles, no audit trail
- Would need to retrofit later (breaking change)

**Solution Applied** (Phase 337):
- Auth & RBAC system built into Phase 337
- 4 roles (Admin/Trader/Analyst/Viewer)
- Bearer tokens on all sensitive endpoints
- CORS middleware from day 1
- Secrets scanning in CI

**Improvement**:
- Security not a retrofit
- Built-in from start
- Pillar 6 (Security) improved from 2/5 → 4/5

**Prevention**:
- Security checklist before code review:
  - Is auth required? ✅
  - Are secrets safe? ✅
  - Is input validated? ✅
  - Does CORS make sense? ✅

---

## Pattern: Code Quality Regressions

### Lesson 6: Tests Can't Catch All Regressions

**Pattern**: Type errors, lint violations, test flakes  
**Incidents**: Would catch type error if uncaught  
**Severity**: Medium (slows down PR review)  
**Status**: ✅ RESOLVED (Phase 337)

**Problem**:
- Manual code review for types (slow, error-prone)
- Lint errors merged accidentally
- Tests flake randomly (state pollution)
- No pre-commit checks

**Solution Applied** (Phase 337):
- Pre-commit hooks (black, ruff, mypy)
- GitHub Actions CI gates
- Test isolation fixed (dependency injection)

**Improvement**:
- Type errors caught before commit
- Code format consistent
- Test flakes eliminated
- Pillar 2 (Build Quality) improved from 3/5 → 4/5

**Prevention**:
- CI runs on every push (can't skip)
- Pre-commit runs on every commit (can't skip)
- Tests run in isolation (state doesn't leak)

---

## Recurring Pattern: Hardcoded Thresholds

**Pattern**: Alert thresholds, timeouts, limits scattered in code  
**Occurrences**: Error rate >10%, latency >1s, timeout 5s, etc.  
**Severity**: Medium  
**Status**: Open (needs centralization)

**Problem**:
- Alert threshold in runbook (not enforced)
- Timeout in code (need to edit for staging vs prod)
- No way to tune without deploys

**Current Locations**:
- Error rate: RB-001 (>10%)
- Latency: RB-002 (p99 >1000ms)
- Connection timeout: hardcoded in API
- Circuit breaker: not implemented yet
- Cache TTL: hardcoded 1 hour

**Action Items**:
1. [ ] Create config file: `backend/config/alerting_config.py`
2. [ ] Move all thresholds to config
3. [ ] Load from environment (ENV override)
4. [ ] Add validation (threshold must be >0)
5. [ ] Document in RUNBOOKS.md

**Owner**: TBD  
**Target**: Phase 338

---

## Improvements by Pillar

### Pillar 1: Architecture Discipline

✅ **Completed**:
- ADR-001: Global state elimination
- Module boundaries explicit
- No circular dependencies

🔲 **Next**:
- ADR-002: Config-driven constants pattern
- Architecture diagram in docs
- ADR-003: DI framework upgrade (FastAPI Depends)

### Pillar 2: Build Quality

✅ **Completed**:
- 100% type hints on Phase 336 modules
- 6 specific exception types
- Input validation everywhere

🔲 **Next**:
- Mypy strict mode
- Lint all modules (not just Phase 336)
- Dependency scanning (Dependabot)

### Pillar 3: Verification

✅ **Completed**:
- 95+ tests passing
- Error case coverage 41 tests
- Integration tests for boundaries

🔲 **Next**:
- Fault-injection tests (chaos engineering)
- Load tests (capacity planning)
- E2E tests (UI + API)

### Pillar 4: CI/Delivery

✅ **Completed**:
- GitHub Actions CI
- Automated merge gate
- Pre-commit hooks

🔲 **Next**:
- Staging environment
- Canary deployments
- Blue-green strategy
- Automated rollback

### Pillar 5: Root-Cause Improvement

✅ **Completed**:
- Incident response process (Phase 337)
- 5-Why framework
- Technical debt register
- Post-mortem template

🔲 **Next**:
- Quarterly debt review cadence
- Improvement board (public backlog)
- Retrospectives after each major release

### Pillar 6: Security

✅ **Completed**:
- Auth & RBAC (Phase 337)
- Bearer tokens
- CORS middleware
- Secrets scanning

🔲 **Next**:
- OAuth2 integration (Phase 338)
- HTTPS enforcement
- Audit logging
- Penetration testing

### Pillar 7: Observability

✅ **Completed**:
- JSON structured logging
- Metrics endpoint
- Request correlation IDs
- Runbooks (5 scenarios)

🔲 **Next**:
- Prometheus scrape
- Grafana dashboards
- SLO alerting
- Distributed tracing

### Pillar 8: Maintainability

✅ **Completed**:
- Config centralization
- Domain-meaningful naming
- Bounded file/function size
- Clear module boundaries

🔲 **Next**:
- Onboarding guide
- Architecture decision log (public)
- Dependency justification doc

---

## Monthly Review Template

**Use this to track improvements month-to-month:**

```markdown
## Month: June 2026

### Incidents This Month
- 0 critical incidents
- 0 high incidents
- 0 medium incidents
- Proactive: Fixed 9 debt items (Phase 336-337)

### Improvements Shipped
- ✅ ADR-001: Global state elimination
- ✅ GitHub Actions CI
- ✅ Auth & RBAC
- ✅ JSON logging + metrics
- ✅ Technical debt register
- ✅ Runbooks & IRP

### Metrics
- Tests: 95/95 passing ✅
- Type coverage: 100% (Phase 336 modules) ✅
- Code coverage: Unknown (need reporting)
- Incident response time: N/A (no incidents)
- Mean time to recovery: N/A

### Debt Trend
- Opened: 0
- Closed: 9 (Phase 336-337)
- Net: -9 (debt decreasing!) ✅

### Next Month Goals
- Phase 338: OAuth2 + HTTPS + SLO alerts
- Add code coverage reporting
- Quarterly debt review (2026-06-30)
```

---

## How to Drive Continuous Improvement

1. **See a problem?** → Add to TECHNICAL_DEBT.md or this backlog
2. **See a pattern?** → Add to "Recurring Patterns" section
3. **Resolve an issue?** → Write post-mortem with 5-Whys
4. **Learn something?** → Document the lesson
5. **Every month**: Review incidents and update this backlog
6. **Every quarter**: Review all debt and prioritize (TECHNICAL_DEBT.md)

