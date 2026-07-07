# Service Level Objectives (SLOs)
**Crypto-Daytrading Platform**  
**Last Updated:** 2026-07-07

---

## Overview

SLOs define target reliability and performance for production trading operations.

---

## 1. Availability SLOs

### API Availability
- **Target:** 99.9% uptime (43.2 minutes downtime/month allowed)
- **Measured:** HTTP endpoint response time <100ms
- **Exception:** Planned maintenance excluded
- **Monitoring:** Prometheus + Grafana dashboard

### Trading Engine Availability
- **Target:** 99.95% uptime (21.6 minutes downtime/month allowed)
- **Measured:** Ability to place orders within 30 seconds
- **Exception:** Exchange downtime excluded
- **Monitoring:** Heartbeat health checks every 10 seconds

### Dashboard Availability
- **Target:** 99.0% uptime (432 minutes downtime/month allowed)
- **Measured:** Dashboard loads in <2 seconds
- **Monitoring:** Synthetic monitoring every 5 minutes

---

## 2. Performance SLOs (Latency)

### Order Execution (NFR-002)
- **Target:** p95 latency <2 seconds (trade to filled)
- **Measured:** From signal generation to order filled confirmation
- **Current:** ~1.5s (baseline from Phase 1)
- **SLA Threshold:** If p95 >3s, escalate immediately

### Signal Generation (NFR-001)
- **Target:** p95 latency <500ms
- **Measured:** From last candle close to signal available
- **Current:** ~200ms (baseline)
- **SLA Threshold:** If p95 >750ms, investigate

### Dashboard Updates
- **Target:** Data refresh <1 second (99% of updates)
- **Measured:** From API response to UI render
- **Current:** ~500ms (baseline)
- **SLA Threshold:** If median >2s, optimize

### API Response Times
- **GET endpoints:** p95 <100ms
- **POST endpoints:** p95 <200ms
- **PATCH endpoints:** p95 <150ms

---

## 3. Reliability SLOs (Error Rates)

### API Error Rate
- **Target:** <0.1% error rate (5xx responses)
- **Measured:** 5xx errors / total requests
- **SLA Threshold:** If >0.5%, page on-call

### Trade Execution Success Rate
- **Target:** 99.9% of orders execute within timeout
- **Measured:** Orders filled / orders placed
- **Current:** 99.8% (baseline)
- **SLA Threshold:** If <99.5%, halt trading

### Data Consistency
- **Target:** 100% of trades synced to database within 10 seconds
- **Measured:** Database vs. in-memory discrepancies
- **Current:** 0 discrepancies (after fix)
- **SLA Threshold:** Any discrepancy triggers alert

### Silent Failure Prevention
- **Target:** 0 unhandled exceptions in production
- **Measured:** Exception logs per hour
- **Current:** 0 (after exception handling fix)
- **SLA Threshold:** Any new exception = incident

---

## 4. Accuracy SLOs

### P&L Calculation Accuracy
- **Target:** 100% accuracy vs. account equity
- **Measured:** Reported P&L = Account equity - Starting capital
- **Current:** 100% (after P&L bug fix)
- **Deviation Tolerance:** <€0.01

### Trade Recording Accuracy
- **Target:** All trades recorded to database within 5 seconds
- **Measured:** Database entries vs. executed orders
- **Current:** 100% (baseline)
- **SLA Threshold:** Any missing trade = incident

### Metrics Consistency
- **Target:** In-memory metrics match database within 30 seconds
- **Measured:** % of metrics in sync
- **Current:** 100% (after sync fix)
- **SLA Threshold:** <99.5% = incident

---

## 5. Disaster Recovery SLOs

### Failover Time (Sentinel Bot HA)
- **Target:** <60 seconds failover to backup machine
- **Measured:** Time from primary heartbeat loss to backup taking over
- **Current:** ~45 seconds (baseline from testing)
- **SLA Threshold:** If >90s, incident

### Backup Data Freshness
- **Target:** <30 seconds behind primary
- **Measured:** Heartbeat check interval
- **Current:** 10 seconds (baseline)
- **SLA Threshold:** N/A (design constraint)

### Trade Loss Prevention
- **Target:** Zero duplicate trades during failover
- **Measured:** UUID collision detection
- **Current:** No duplicates (baseline)
- **SLA Threshold:** Any duplicate = incident

---

## 6. Scalability SLOs

### Concurrent Users
- **Target:** Support 10+ concurrent API clients
- **Measured:** Simultaneous WebSocket connections
- **Current:** 50+ supported (baseline)
- **Headroom:** 5x safety margin

### Trade Throughput
- **Target:** Handle 100 trades/day minimum
- **Measured:** Trades processed per 24 hours
- **Current:** Unlimited (async processing)
- **Headroom:** No known limits

### Data Volume Growth
- **Target:** Support 10,000+ trades in database
- **Measured:** Historical trade count
- **Current:** 2,560+ trades (baseline)
- **Retention Policy:** All trades (no purge)

---

## 7. Security SLOs

### Credential Exposure
- **Target:** 0 hardcoded credentials
- **Measured:** Static analysis results
- **Current:** 0 (verified by audit)
- **SLA Threshold:** Any credential found = emergency

### Deployment Safety
- **Target:** 100% of code reviewed before production
- **Measured:** Code review completion %
- **Current:** 85% (after Phase 1 fixes)
- **SLA Threshold:** <100% = block deployment

### Exception Handling
- **Target:** 100% of exception paths have logging
- **Measured:** Exceptions with error logs / total exceptions
- **Current:** 100% (after Phase 1 fixes)
- **SLA Threshold:** Any unlogged exception = incident

---

## 8. Operational SLOs

### Monitoring Coverage
- **Target:** 100% of critical systems monitored
- **Measured:** Systems with active health checks
- **Current:** 95% (baseline)
- **Gap:** Need SLO dashboard for some components

### Alert Response Time
- **Target:** On-call responds to CRITICAL alerts <5 minutes
- **Measured:** Alert created to on-call acknowledgment
- **SLA Threshold:** N/A (SLA for team, not system)

### Incident Resolution
- **Target:** CRITICAL incidents resolved <30 minutes
- **Measured:** Time from alert to resolution
- **Baseline:** Unknown (first month tracking)
- **SLA Threshold:** Establish after 30 days data

---

## Measurement & Enforcement

### Dashboards
- **Primary:** Grafana at `grafana.internal/d/crypto-slo`
- **Backup:** Custom monitoring endpoint `/api/monitoring/slo-status`

### Alerts
- **CRITICAL:** Page on-call immediately
- **HIGH:** Send to Slack #trading-alerts
- **MEDIUM:** Email summary daily

### Reviews
- **Weekly:** Check SLO compliance
- **Monthly:** Review SLO trends and adjust targets
- **Quarterly:** Full SLO assessment and planning

---

## Compliance History

| Period | Availability | P95 Latency | Error Rate | Status |
|--------|--------------|-------------|------------|--------|
| Phase 1 (baseline) | 99.9% | 1.5s | 0.05% | ✅ PASSING |
| Jun 2026 | TBD | TBD | TBD | 📊 In progress |

---

**Next Review:** 2026-07-14

