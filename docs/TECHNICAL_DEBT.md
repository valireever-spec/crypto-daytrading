# Technical Debt Register

**Purpose**: Track known architectural debt, design limitations, and improvement opportunities.

**Review Cadence**: Quarterly (end of each quarter)  
**Last Updated**: 2026-06-24  
**Next Review**: 2026-09-30

---

## Format

Each debt item includes:
- **ID**: Unique identifier (DEBT-001, etc.)
- **Title**: Clear, actionable name
- **Area**: Module or pillar affected
- **Severity**: Critical / High / Medium / Low
- **Effort**: Time estimate (small/medium/large)
- **Impact**: What gets worse if not fixed
- **Status**: Open / In-Progress / Resolved
- **Owner**: Who's responsible
- **Notes**: Context, workarounds, dependencies

---

## Current Debt Backlog

### DEBT-001: Demo Tokens in Auth System

**Area**: Pillar 6 (Security)  
**Severity**: High  
**Effort**: Medium (1-2 weeks)  
**Status**: Open

**Problem**:
- Auth system uses hardcoded demo tokens (admin-token-123, etc.)
- Not production-ready; no token expiration
- No user management API

**Impact**:
- Can't scale to multiple users
- Tokens never expire (security risk)
- No audit trail of who did what

**Workaround**: Demo tokens work for Phase 337; Phase 338 will replace with OAuth2/JWT

**Solution**:
1. Implement OAuth2 or JWT
2. Add token expiration (30-60 min)
3. Add token refresh mechanism
4. Create user management API
5. Implement audit logging

**Dependencies**: Phase 338 (Production Hardening)

---

### DEBT-002: No Database Transaction Support

**Area**: Pillar 3 (Verification)  
**Severity**: Medium  
**Effort**: Large (2-3 weeks)  
**Status**: Open

**Problem**:
- Multi-step operations (buy + hedge + log) aren't atomic
- If one step fails, others may already have committed
- No rollback on partial failures

**Impact**:
- Data inconsistency during failures
- Duplicate trades or lost trades possible
- Audit trail gaps

**Workaround**: Idempotent operations (same call = same result)

**Solution**:
1. Use database transactions (BEGIN/COMMIT/ROLLBACK)
2. Implement saga pattern for cross-service operations
3. Add compensation logic for rollbacks
4. Test with fault injection (chaos engineering)

**Dependencies**: Database layer refactoring

---

### DEBT-003: Hard-Coded Thresholds Scattered in Code

**Area**: Pillar 8 (Maintainability)  
**Severity**: Medium  
**Effort**: Small (1 week)  
**Status**: Open (partially fixed in Phase 336)

**Problem**:
- Values like "1% error rate threshold", "2s latency limit" are scattered
- Hard to find and change
- No central place to tune for different environments

**Impact**:
- Hard to adjust thresholds without code changes
- Can't tune prod vs staging separately
- Inconsistent thresholds across modules

**Fixed in Phase 337**: ✅
- Moved FX rates, volatilities, correlations to `backend/config/asset_config.py`
- Moved risk-free rate, transaction costs to config

**Remaining**:
- Alert thresholds (error rate >10%, latency >1s) still in runbooks
- Should move to config file

**Solution**:
1. Extend `PortfolioOptimizationConfig` to include alert thresholds
2. Load from environment variables (dev/staging/prod different values)
3. Validate thresholds on startup

---

### DEBT-004: No Distributed Tracing

**Area**: Pillar 7 (Observability)  
**Severity**: Medium  
**Effort**: Medium (1-2 weeks)  
**Status**: Open

**Problem**:
- Request IDs added in Phase 337, but not propagated across services
- Hard to trace a request through multiple services
- No timing breakdown by component

**Impact**:
- Can't debug slow requests across service boundaries
- No dependency-level performance visibility
- Hard to correlate logs from different services

**Workaround**: Request ID in logs (single-service correlation)

**Solution**:
1. Use Jaeger or Datadog APM
2. Propagate trace context in HTTP headers
3. Instrument each service to emit spans
4. Create Grafana dashboards for trace visualization

**Dependencies**: Phase 338+ (observability expansion)

---

### DEBT-005: No Cache Invalidation Strategy

**Area**: Pillar 2 (Build Quality) + Pillar 7 (Observability)  
**Severity**: Medium  
**Effort**: Medium (1-2 weeks)  
**Status**: Open

**Problem**:
- Composite signals cached 1 hour (Phase 226)
- FX rates not cached, but could be (API rate limiting)
- No way to force cache invalidation
- Stale data risk during crises

**Impact**:
- Stale signals during market events
- Rate limiting on external APIs
- No manual invalidation in emergencies

**Workaround**: Cache TTL expires eventually (max 1 hour staleness)

**Solution**:
1. Add cache invalidation endpoint (`DELETE /cache/signals`)
2. Implement event-driven cache expiry (new price → invalidate)
3. Add cache metrics to observability
4. Document cache-busting procedure in runbooks

**Dependencies**: Redis or in-memory caching library

---

### DEBT-006: No Circuit Breaker for External APIs

**Area**: Pillar 4 (CI/Delivery) + Pillar 7 (Observability)  
**Severity**: High  
**Effort**: Medium (1-2 weeks)  
**Status**: Open

**Problem**:
- Binance WebSocket fails → API hangs waiting for prices
- Finnhub rate limits → retry loop with exponential backoff missing
- No graceful degradation when exchanges down

**Impact**:
- Cascading failures (one API down → whole system down)
- Slow error detection (timeout-based, not immediate)
- No fallback strategies

**Workaround**: Manual restart when external APIs fail

**Solution**:
1. Implement circuit breaker pattern (open/half-open/closed)
2. Add fallback to cached data or default values
3. Metrics on circuit state changes
4. Runbooks for circuit breaker troubleshooting

**Dependencies**: Phase 338 (Resilience Framework)

---

### DEBT-007: No User Audit Trail

**Area**: Pillar 6 (Security)  
**Severity**: Medium  
**Effort**: Small (1 week)  
**Status**: Open

**Problem**:
- Don't log who did what (user_id missing from most logs)
- Can't reconstruct who made trades, changed configs, etc.
- Compliance issue for audit requirements

**Impact**:
- No audit trail for regulatory compliance
- Can't investigate suspicious activity
- User accountability missing

**Workaround**: Manual log correlation with request IDs (tedious)

**Solution**:
1. Add user_id to request context in auth middleware
2. Log user_id with every action (trade, config change, etc.)
3. Create audit log query API (filter by user, action, date)
4. Archive logs for compliance

**Dependencies**: Phase 337+ (structured logging framework in place)

---

### DEBT-008: Hardcoded Liquidity Tier Spreads

**Area**: Pillar 2 (Build Quality) + Pillar 8 (Maintainability)  
**Severity**: Low  
**Effort**: Small (1 day)  
**Status**: Open

**Problem**:
- Bid-ask spreads hardcoded in backtesting engine (ETF=1bp, US=4bp, EU=10bp, Asia=20bp)
- Can't adjust without code change
- Different strategies need different spread assumptions

**Impact**:
- Can't test different execution scenarios
- Hard to compare realistic vs optimistic backtests

**Workaround**: Code changes for different scenarios

**Solution**:
1. Move spreads to config file
2. Load from environment or parameter
3. Allow per-strategy overrides

**Dependencies**: None (quick fix)

---

### DEBT-009: No SLO Definition

**Area**: Pillar 7 (Observability)  
**Severity**: Medium  
**Effort**: Small (1 week)  
**Status**: Open

**Problem**:
- No explicit Service Level Objectives
- Alerts set arbitrarily (error rate >10%, latency >1s)
- No agreed SLAs with users/stakeholders

**Impact**:
- No clear performance targets
- Can't measure success/failure of releases
- Alerts not tied to business impact

**Solution**:
1. Define SLOs:
   - **Availability**: 99% uptime (43.2 minutes downtime/month)
   - **Latency**: p95 <500ms, p99 <2s
   - **Error Rate**: <5% of requests fail
2. Implement SLO tracking dashboard
3. Set budget for breaches (error budget)
4. Alerts fire when budget depleted

**Dependencies**: Phase 338 (Prometheus + Grafana)

---

## Debt Lifecycle

**1. Identification** (this document)
   - New debt discovered and logged
   - Severity/effort estimated

**2. Prioritization** (quarterly review)
   - Rank by impact vs effort
   - Decide: fix now, defer, accept forever

**3. Resolution** (sprint planning)
   - Assign owner and deadline
   - Create tickets for implementation
   - Update status to "In-Progress"

**4. Closure** (code review)
   - Verify fix is complete
   - Update documentation
   - Mark status as "Resolved"

**5. Verification** (next quarterly review)
   - Confirm fix holds
   - Document lessons learned

---

## Quarterly Review Checklist

**Every Quarter (end of Q1, Q2, Q3, Q4)**:

- [ ] Review all "Open" items; any resolved?
- [ ] Add new debt discovered since last review
- [ ] Re-estimate effort for open items
- [ ] Prioritize top 3 items for next quarter
- [ ] Document trends (debt increasing? decreasing?)
- [ ] Update this file with new entries
- [ ] Share summary with team in architecture review

---

## Debt Trends

| Quarter | Count | Trend | Notes |
|---------|-------|-------|-------|
| Q2 2026 | 9 | → | Initial register (Phase 337) |
| Q3 2026 | ? | ? | TBD (next review 2026-09-30) |
| Q4 2026 | ? | ? | TBD |

---

## Resolved Debt Archive

### ✅ DEBT-000: Global Mutable State (RESOLVED)

**Area**: Pillar 1 (Architecture)  
**Resolution Date**: 2026-06-24  
**Status**: Resolved ✅

**Problem** (was):
- Singleton patterns in asset_classes, currency_risk, global_optimization
- Difficult to test, mutation risks

**Solution Applied**:
- Implemented in Phase 336
- Dependency injection + direct instantiation
- Documented in ADR-001

**Outcome**: Pillar 1 score improved to 4/5; test isolation perfect

---

## How to Add Debt

If you discover new technical debt:

1. **Create an issue** with title and description
2. **Add to this register** with ID (next available)
3. **Estimate severity** (Critical/High/Medium/Low)
4. **Estimate effort** (time to fix)
5. **Note workaround** (if any)
6. **Mark as Open**

Example:
```markdown
### DEBT-XXX: [Your Issue Title]

**Area**: Pillar X  
**Severity**: Medium  
**Effort**: Small  
**Status**: Open

**Problem**:
- What is wrong

**Impact**:
- What gets worse

**Workaround**: If any

**Solution**:
- How to fix
```

---

## Key Principle

> **Don't accumulate debt silently.**  
> **Log it, prioritize it, fix it.**  
> **This register is the source of truth for engineering excellence.**

