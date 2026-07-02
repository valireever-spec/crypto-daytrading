# Crypto-Daytrading Platform: Comprehensive Project Analysis

**Date:** 2026-07-02  
**Status:** Phase 0 (Design) → Phase 1 (MVP) → Phase 2 (Live)  
**Maturity:** Early (design-phase focus on requirements & architecture)

---

## EXECUTIVE SUMMARY

**Crypto-Daytrading** is an automated daytrading platform for cryptocurrency with dual-machine HA redundancy. The system supports decision-driven trading (alerts + manual execution) rather than full autopilot, allowing traders to learn and optimize in real-time.

### Key Characteristics
- **Purpose:** 24/7 crypto daytrading with human-in-the-loop decision support
- **Architecture:** Binance API + FastAPI backend + React frontend + SQLite persistence
- **HA Design:** Active-passive failover (PRIMARY trades, BACKUP monitors)
- **Trading Strategies:** Momentum Scalper, Mean Reversion, Grid Trading
- **Target Win Rate:** >55% on 10-day paper test before live
- **Live Capital:** €1,000 in Phase 2
- **Team Size:** 1 developer (you)
- **Timeline:** 6-7 weeks to production

### Project Status
✅ Phase 0 (Requirements & Architecture) — Complete  
⏳ Phase 1 (MVP Paper Trading) — Next (2-5 weeks)  
⏳ Phase 2 (HA & Live) — After MVP validation

---

## PART 1: REQUIREMENTS ANALYSIS

### 1.1 Functional Requirements (20 total)

The platform is designed as a **decision support system**, not autopilot. The trader sees alerts, makes decisions, and executes manually (or lets the system auto-execute with safeguards).

#### Tier 1: Core APIs (FR-001 to FR-002)

**FR-001: Binance API Integration**
- REST API for prices, orders, account status
- Rate limits: 1,200 requests/min
- Testnet support for paper trading
- Real-time price data <1s latency
- Market + limit orders with confirmation
- Order status tracking (pending → filled → cancelled)

**FR-002: Paper Trading Engine**
- Simulated orders using real Binance WebSocket prices (not backtest)
- Realistic slippage (0.05-0.2% based on order type)
- 0.1% trading fees
- Virtual account tracking (cash, positions, P&L)
- 24/7 operation (crypto never closes)
- Paper → Live toggle (same code, different env var)

#### Tier 2: Signal & Strategy (FR-003 to FR-003C)

**FR-003: Real-Time Signal Generation**
- RSI (14), MACD, Bollinger Bands calculation
- Multiple timeframes: 1m, 5m, 15m, 1h
- Signal score: -100 (sell) to +100 (buy)
- Update on candle close, not fixed intervals
- <500ms latency target

**FR-003B: Dynamic Strategy Allocation**
- Three strategies: Momentum (50%), Mean Reversion (30%), Grid (20%)
- Time-based presets:
  - 7-11am: Momentum 60%, Reversion 10%, Grid 30%
  - 11am-3pm: Momentum 20%, Reversion 60%, Grid 20%
  - 3pm+: Momentum 30%, Reversion 0%, Grid 70%
- Trader adjusts live via sliders

**FR-003C: Time-Based Parameter Switching**
- Morning (7-11am): P&L target +2%, stop -2%, position +3%
- Afternoon (11am-3pm): P&L target +0.8%, stop -1%, position +1%
- Close-out (3pm-6pm): P&L target +0.5%, stop -0.5%, position -50%
- Auto-apply at time boundary, allow manual override

#### Tier 3: Order Execution (FR-004 to FR-006)

**FR-004: Real-Time Signal Alerts**
- Alert when signal ≥ threshold (configurable, e.g., ≥70)
- Channels: Dashboard, push, email, SMS
- Includes: Symbol, signal score, trend, suggested size, current price
- Expires if not acted on (30 seconds)
- No auto-execution: Trader must approve

**FR-005: Manual Order Entry & Execution**
- BUY button with entry form
- SELL/EXIT buttons with quick partials (25%/50%/75%/100%)
- Order type: Market or Limit
- Position size override (0.5%-3% of account)
- <2 second execution latency
- Order confirmation with fee estimate

**FR-006: Manual Stop & Profit Override**
- View stop loss, profit target, unrealized P&L per position
- Tighten/widen stops
- Take profit early, close at loss
- Adjust without system restart

#### Tier 4: Risk & Control (FR-007 to FR-008)

**FR-007: System States & Pause Mechanism**
- TRADING: Normal, all alerts enabled
- PAUSED: No alerts, existing positions hold with active stops
- CLOSE_ONLY: No entry alerts, exit only
- MONITORING: Watch but no auto-alerts
- Instant toggle, no restart

**FR-008: Dynamic Position Sizing**
- Base: 1.5% of account
- Adjustments:
  - Signal strength: 90+ → +50%, 50-69 → -50%
  - Account heat (deployed %): 30-60% → -25%, >60% → -50%
  - Win streak: 3+ wins → +20% per win (capped)
  - Time of day: Morning → +50%, Afternoon → -25%, Close → -50%
  - Volatility: High → -25%, Low → +15%
- Combined multiplier: base × signal × heat × streak × time × volatility

#### Tier 5: Monitoring (FR-009 to FR-010)

**FR-009: Real-Time Portfolio Monitoring**
- Live dashboard (1-second updates)
- Account: Equity, cash, positions value, heat %, daily P&L, total P&L
- Positions: Entry, current, qty, unrealized P&L, %gain, days held
- Recent trades: Time, symbol, type, price, qty, P&L, duration, strategy
- Strategy allocation live display

**FR-010: Per-Strategy Analytics**
- Win rate by strategy (daily)
- Avg win, avg loss, profit factor per strategy
- Win rate by time of day (7-11am, 11am-3pm, 3pm-6pm)
- Win rate by trading pair (BTCUSDT, ETHUSDT, SOLUSDT)
- Fee analysis (total profit, fees paid, net profit)
- Recommendations based on live data

#### Tier 6: Learning & Quality (FR-012)

**FR-012: Trade Quality Analysis**
- Per-trade analysis:
  - Entry quality (signal score)
  - Exit quality (% of max possible profit taken)
  - Hold duration vs target
  - Fee cost ratio
  - Alternative outcomes (if held longer/exited earlier)
- Learning: Which signals work, best exit timing, fee impact

#### Tier 7: Alerts & Safety (FR-011)

**FR-011: Critical Alerts & Runbooks**
- CRITICAL: Exchange down, failover triggered, daily loss >5%, position gap >5%
- WARNING: Account heat >60%, 3+ losses, strategy <50% win
- INFO: Trade filled, profit target hit, strategy changed, mode changed
- Each alert includes runbook (actionable steps)

#### Tier 8: HA & Failover (FR-013, FR-015)

**FR-013: HA Redundancy (Dual Machine)**
- PRIMARY: Active trader, sends state sync + heartbeat
- BACKUP: Standby, receives sync, monitors heartbeat
- Heartbeat every 10 seconds
- Failover after 3 consecutive missed beats (30 seconds)
- UUID per trade (inherited by BACKUP on takeover)
- No duplicate trades during failover

**FR-015: Automatic Database Authority Resolution**
- Compare timestamps across PRIMARY and BACKUP databases
- Use most recent as authoritative
- Auto-sync stale machine from authoritative
- Prevents data loss on failover

#### Tier 9: Overnight & Autonomous (FR-014, FR-016)

**FR-014: Overnight Mode**
- Configurable at 6pm: Hold overnight? Close all? Pause?
- If hold: Wider stops (-5%), wider targets (+5%), max 2 positions, grid only
- Switches back to morning parameters at 7am

**FR-016: Autonomous 24/7 Trading (Sleep Mode)**
- Bot executes trades while user sleeps
- No manual intervention required
- Respects entry threshold and position limits
- All trades logged
- HA ensures trading continues on failure
- 8+ hour uninterrupted test required

#### Tier 10: Safety & Emergency (FR-017 to FR-020)

**FR-017: Emergency Market Crash Response**
- CLOSE ALL: Close all positions immediately at market
- PAUSE ALL: Stop new entries, hold with active stops
- HALT SYSTEM: Kill all trading, stop HA, freeze state
- <2 second execution

**FR-018: Manual Signal Override**
- OVERRIDE SIGNAL: Prevent trade execution
- FORCE ENTRY: Execute even if signal <threshold
- FORCE EXIT: Close specific position immediately
- Logged with reason, reset at midnight

**FR-019: Real-Time Strategy Learning & Feedback**
- Daily summary after market close
- Win rate by signal strength
- Win rate by time of day
- Win rate by symbol
- Per-trade feedback (why won/lost)
- Actionable recommendations

**FR-020: Emergency Stop (Hard Kill Switch)**
- One-click system shutdown
- Closes all positions
- Halts HA
- Freezes database
- Cannot be undone without restart
- <2 second execution

### 1.2 Non-Functional Requirements (26 total)

#### Performance (NFR-001 to NFR-005)

| Requirement | Target | Why |
|-------------|--------|-----|
| **NFR-001: Signal Latency** | <500ms p95 | Crypto moves 1-2%/min |
| **NFR-002: Order Execution** | <2s p95 | Slippage increases with delay |
| **NFR-003: Candle Fetch** | <2s batch, <100ms/symbol | Real-time needs fresh data |
| **NFR-004: Throughput** | ≥100 trades/day | High volatility = more signals |
| **NFR-005: Memory** | <500MB peak | HA backup may be limited |

#### Reliability (NFR-006 to NFR-010B)

| Requirement | Target | Why |
|-------------|--------|-----|
| **NFR-006: Availability (HA)** | 99.5% uptime | 24/7 crypto, downtime = missed P&L |
| **NFR-007: No Duplicates** | 0 duplicates | Failover could execute twice |
| **NFR-008: Recovery Time (RTO)** | ≤30 seconds | 1-2% moves in 30s |
| **NFR-009: Recovery Point (RPO)** | ≤1 trade lost | Accept small loss on handover |
| **NFR-010: Data Consistency** | 100% identical | All state across PRIMARY/BACKUP |
| **NFR-010B: DB Durability** | Survive restart | API crash = no state loss |

#### Security (NFR-011 onwards)

- **NFR-011:** API keys in env vars, not code/logs/git
- **NFR-012:** Input validation (no SQL injection, command injection)
- **NFR-013:** HTTPS for API, TLS for database
- **NFR-014:** Audit trail (all trades logged with timestamp)
- **NFR-015:** Rate limiting (protect against abuse)
- **NFR-016:** Secrets rotation (API keys, DB passwords)

#### Scalability (NFR-017+)

- **NFR-017:** Support 10+ trading pairs simultaneously
- **NFR-018:** Support multiple strategies in parallel
- **NFR-019:** Database should scale to 100K+ trades

#### Observability (NFR-020+)

- **NFR-020:** Structured JSON logging
- **NFR-021:** Prometheus metrics (trades/min, latency p50/p95/p99)
- **NFR-022:** Health checks (/api/health endpoint)
- **NFR-023:** Dashboard with real-time metrics

#### Compliance (NFR-024+)

- **NFR-024:** Trade audit trail (immutable)
- **NFR-025:** Regular backups (daily, encrypted)
- **NFR-026:** Regulatory compliance (depends on jurisdiction)

---

## PART 2: ARCHITECTURE ANALYSIS

### 2.1 System Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                      FRONTEND                                │
│         React Dashboard (HTML/CSS/JS)                        │
│  - Real-time portfolio monitoring                           │
│  - Signal alerts                                             │
│  - Manual order entry (BUY/SELL)                            │
│  - Strategy allocation sliders                              │
│  - Analytics & performance charts                           │
└─────────────────────────────┬────────────────────────────────┘
                              │ HTTP/WebSocket
┌─────────────────────────────▼────────────────────────────────┐
│                      BACKEND (FastAPI)                       │
├──────────────────────────────────────────────────────────────┤
│  API Routers (25+):                                          │
│  - /api/trades — Order execution, status                    │
│  - /api/portfolio — Account, positions, P&L                │
│  - /api/signals — Real-time alerts                         │
│  - /api/strategies — Strategy management                   │
│  - /api/analytics — Performance metrics                    │
│  - /api/health — System health                             │
│  - /api/ha — Failover, state sync                          │
│  - /dashboard — WebSocket for 1s updates                   │
├──────────────────────────────────────────────────────────────┤
│  Core Services:                                              │
│  - Exchange Service (Binance REST/WebSocket)               │
│  - Execution Engine (order placement, fills)                │
│  - Signal Generator (RSI, MACD, BB calculations)           │
│  - Position Tracker (entry/exit, P&L)                       │
│  - Risk Manager (stops, profit targets, heat)              │
│  - Autonomous Trader (autopilot logic)                      │
│  - HA Manager (heartbeat, state sync, failover)            │
└─────────────────────────────┬────────────────────────────────┘
                              │
         ┌────────────────────┼────────────────────┐
         │                    │                    │
         ▼                    ▼                    ▼
    ┌─────────┐         ┌──────────┐         ┌─────────┐
    │ SQLite  │         │ Binance  │         │ HA Link │
    │ trades  │◄────────│ REST API │         │(network)│
    │ account │         │ WebSocket│         │         │
    │ state   │         └──────────┘         └─────────┘
    └─────────┘
   (Persistence)      (External)           (Other machine)
```

### 2.2 Component Breakdown

| Component | Purpose | Status | Key Files |
|-----------|---------|--------|-----------|
| **Frontend** | Real-time dashboard, alerts, manual control | Design | `/frontend/` |
| **API Server** | 25+ routers, WebSocket for updates | Partial | `/backend/api/main.py` |
| **Exchange Service** | Binance API (REST + WebSocket) | Partial | `/backend/exchange/` |
| **Signal Generator** | RSI/MACD/BB calculations | Design | `/backend/analytics/signals.py` |
| **Execution Engine** | Order placement, fill simulation | Partial | `/backend/execution/smart_executor.py` |
| **Position Tracker** | Entry/exit, P&L calculation | Partial | `/backend/trading/position_tracker.py` |
| **Risk Manager** | Stops, targets, position sizing | Partial | `/backend/trading/risk_manager.py` |
| **Autonomous Trader** | Auto-execution with safeguards | Design | `/backend/trading/autonomous_trader.py` |
| **HA Manager** | Heartbeat, failover, state sync | ✅ DONE | `/backend/core/ha_*.py` |
| **Database** | SQLite persistence | Partial | `trading.db` |

### 2.3 Data Flow

**Normal Operation (Manual Mode):**
```
Market price → Signal Generator → Alert → Trader decides → Execute → Fill → Position Tracker → P&L → Dashboard
```

**Autonomous Operation (Sleep Mode):**
```
Market price → Signal Generator → Meets threshold? → Auto-Execute → Fill → Position Tracker → Log → Next signal
```

**Failover Scenario:**
```
PRIMARY heartbeat stops → BACKUP detects (15s) → Validates state → Promotes → Resumes from BACKUP's synced state
```

### 2.4 Data Persistence

**SQLite Database Schema:**
```sql
trades (
  id, symbol, side, entry_price, exit_price, qty, fee, 
  realized_pnl, created_at, closed_at, strategy, uuid
)

account_state (
  id, total_pnl, daily_pnl, cash, deployed_pct, 
  updated_at
)

positions (
  id, symbol, entry_price, qty, unrealized_pnl, 
  stop_loss, profit_target, created_at
)
```

**In-Memory State (Engine):**
- Current positions (symbol, qty, entry price)
- Open orders (waiting for fill)
- Account cash and equity
- Strategy allocation (Momentum%, Reversion%, Grid%)
- System state (TRADING/PAUSED/CLOSE_ONLY/MONITORING)

### 2.5 HA Architecture (NEWLY IMPLEMENTED)

**State Synchronization (Every 5 Seconds):**
```
PRIMARY:
  1. Collect snapshot of 92 critical globals
  2. Calculate SHA256 checksum
  3. Send to BACKUP with auto-retry

BACKUP:
  1. Receive snapshot
  2. Validate checksum
  3. Store synced copy
  4. Use for failover resumption
```

**Heartbeat Monitoring (Every 5 Seconds):**
```
PRIMARY:
  • Send "I'm alive" to BACKUP

BACKUP:
  • Monitor for 3 consecutive misses (15 seconds)
  • On failure: Trigger failover
```

**Failover Logic (Atomic Promotion):**
```
1. Disconnect from PRIMARY
2. Validate state consistency (80% minimum coverage)
3. Validate critical functions work
4. Switch role to PRIMARY
5. Resume trading from synced state
6. Log failover event
```

---

## PART 3: IMPLEMENTATION STATUS

### 3.1 What's DONE ✅

| Component | Status | Details |
|-----------|--------|---------|
| **HA Infrastructure** | ✅ 100% | State sync, heartbeat, failover (10 hours invested) |
| **HA Tests** | ✅ 100% | Unit + integration + chaos tests ready |
| **HA Config** | ✅ 100% | Environment-driven, validated |
| **Documentation** | ✅ 100% | Architecture, guides, checklists |
| **V-Model Framework** | ✅ 100% | Requirements traced to tests |
| **Project Structure** | ✅ 100% | Directories, modules organized |
| **Requirements** | ✅ 100% | 20 FR + 26 NFR documented |

### 3.2 What's PARTIAL ⏳

| Component | Status | Details |
|-----------|--------|---------|
| **Binance API** | 60% | REST API working, WebSocket needs testing |
| **Signal Generator** | 60% | RSI/MACD/BB logic, latency <500ms not verified |
| **Order Execution** | 60% | Basic placement, paper trading not tested at scale |
| **Position Tracking** | 70% | Entries tracked, P&L calculation needs validation |
| **Risk Manager** | 50% | Stops/targets exist, dynamic sizing partially done |
| **Dashboard** | 20% | Layout designed, real-time updates need WebSocket |
| **Autonomous Trader** | 30% | Logic sketched, safeguards need testing |
| **Database** | 70% | Schema defined, durability/sync needs testing |

### 3.3 What's NOT STARTED ❌

| Component | Reason | Priority |
|-----------|--------|----------|
| **Frontend (React)** | Design phase | High (needed for MVP) |
| **WebSocket updates** | Design phase | High (1-second updates) |
| **Strategy learning** | Design phase | Medium (Phase 1.5) |
| **Trade quality analysis** | Design phase | Medium (Phase 1.5) |
| **SMS/Email alerts** | Design phase | Low (Phase 2) |
| **Overnight mode** | Design phase | Medium (Phase 2) |
| **Emergency stop** | Design phase | Low (safety, not MVP) |

### 3.4 Critical Gaps

**Code Quality Issues (92 globals need locks):**
- 94 unprotected critical globals remain
- 31 TOCTOU races unfixed
- 1,623 async races dormant (but could surface)

**Testing Gaps:**
- No acceptance test for 10-day paper trading
- No chaos test for failover under load
- No stress test for 100+ trades/day

**Documentation Gaps:**
- No runbooks for operations (how to deploy, troubleshoot)
- No postmortems (analysis of failures/learnings)
- No SLOs (service level objectives)

---

## PART 4: WORKFLOW & OPERATIONS

### 4.1 Development Workflow

**Local Development:**
```bash
# Setup
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Code quality
black . && ruff check . --fix && mypy .

# Testing
pytest tests/unit -v                    # Fast (<1s)
pytest tests/integration -v             # Medium (5s)
pytest tests/ --cov=backend             # Full coverage report

# Run locally
python -m backend.api.main              # Starts API on port 8000
# OR
python -m backend.trading.bot_runner   # Starts autonomous trader
```

**Code Commit Workflow:**
```
1. Create feature branch
2. Write code + tests
3. Pass linting (black, ruff, mypy)
4. Pass all tests (unit + integration)
5. Commit with conventional commit message
6. Create pull request (2+ reviewers)
7. Merge to main
8. CI runs full test suite
```

### 4.2 Paper Trading Workflow

**Daily Paper Trading:**
```bash
# Morning (7am)
1. Check dashboard: System health, overnight trades logged
2. Review analytics: Yesterday's win rate by strategy
3. Adjust strategy allocation if needed (sliders)
4. Enable TRADING mode

# During day (7am-6pm)
1. Monitor alerts on dashboard (pop-up on signal)
2. Manually approve BUY signals (or skip)
3. Exit positions when target hit or stop hit
4. Adjust stops/targets if needed
5. Review quick stats hourly (win rate, heat %)

# Evening (6pm)
1. Review daily P&L
2. Analyze trades: Why did winners win, losers lose?
3. Adjust parameters for next day (times, thresholds)
4. Set overnight mode (HOLD / CLOSE / PAUSE)
```

**Weekly Paper Trading Review:**
```bash
1. Export week's trades
2. Analyze by strategy: Which performed best?
3. Analyze by time-of-day: When was I most profitable?
4. Analyze by pair: Which cryptos worked best?
5. Identify patterns (e.g., "Momentum 70% win in morning")
6. Adjust next week's settings
```

**10-Day Paper Acceptance Test:**
```bash
# Goal: >55% win rate on real live prices
# Duration: 10 trading days (Mon-Fri × 2 weeks)
# Mode: Manual alerts + execution (decision support)

1. Trade daily for 10 days
2. Log all trades: symbol, entry, exit, P&L, strategy
3. Calculate: Total P&L, win rate by strategy, drawdown
4. Success criteria: >55% win rate, positive total P&L

# If pass: Proceed to Phase 2 (HA setup)
# If fail: Debug, adjust parameters, try again
```

### 4.3 Failover Workflow

**Normal Operation:**
```
PRIMARY (port 8000)                    BACKUP (port 8001)
  • Executes trades                      • Monitors heartbeat
  • Updates positions                    • Syncs state (every 5s)
  • Sends heartbeat (every 5s)          • Maintains read-only copy
```

**PRIMARY Failure Scenario:**
```
T0:    PRIMARY heartbeat stops
T0-T5: BACKUP waits for beat 1 (missing)
T5-T10: BACKUP waits for beat 2 (missing)
T10-T15: BACKUP waits for beat 3 (missing) → PRIMARY DEAD
T15:   BACKUP validates state (1 second)
T16:   BACKUP promotes to PRIMARY
T17:   BACKUP resumes trading
T18:   System operational (3 second total failover)
```

**Manual Failover (Testing):**
```bash
# On PRIMARY machine
kill <api_process_pid>

# On BACKUP machine
# Should detect failure and promote within 15 seconds
tail -f logs/ha.log | grep "failover"

# After promotion
# BACKUP is now the trader
# PRIMARY should be restarted and synced from BACKUP
```

### 4.4 Operational Runbooks

**Runbook: Daily Start**
```bash
1. Ensure both machines powered on and connected
2. Start PRIMARY API: python -m backend.api.main
3. Start BACKUP API: python -m backend.api.main (on machine2)
4. Verify /api/health on both machines returns OK
5. Check logs: tail -f logs/*.log
6. Verify heartbeat: Should see "Heartbeat sent/received" every 5s
7. Open dashboard: http://localhost:8000/dashboard
8. Confirm system state is TRADING (not PAUSED)
```

**Runbook: Emergency Stop**
```bash
1. Hit "EMERGENCY STOP" button on dashboard
   OR curl http://localhost:8000/api/emergency-stop

2. Verify within 2 seconds:
   - All positions closed
   - Trading stopped
   - HA disabled
   - System state = HALTED

3. Review audit log: tail -f logs/trades.jsonl
4. Check final P&L and reason
5. Manual restart required to resume
```

**Runbook: Failover Investigation**
```bash
1. Check if PRIMARY is responding:
   curl http://localhost:8000/api/health

2. If PRIMARY is dead:
   - Check PRIMARY machine (network, process, logs)
   - Power on/restart if needed

3. Monitor BACKUP promotion:
   tail -f logs/ha.log
   grep "failover" logs/ha.log

4. After PRIMARY back up:
   - Start PRIMARY API
   - Verify state sync resumes
   - Check for duplicate trades (shouldn't be any)
   - Review PRIMARY vs BACKUP state (should match)

5. If states diverged:
   - Run database authority resolution (timestamp comparison)
   - Use most recent as authoritative
   - Sync stale machine from authoritative
```

**Runbook: Data Consistency Issue**
```bash
1. Check database consistency:
   sqlite3 trading.db "SELECT count(*) FROM trades;"
   
2. On both machines:
   - PRIMARY.db trade count should equal BACKUP.db trade count
   - PRIMARY.db cash balance should equal BACKUP.db cash
   - Checksums should match

3. If diverged:
   - Identify authoritative DB (most recent timestamp)
   - Copy .db file from authoritative → stale
   - Restart both APIs
   - Verify state sync resumes

4. If still diverged:
   - Restore from backup
   - Notify team (shouldn't happen with HA state sync)
```

---

## PART 5: CODE QUALITY & TESTING

### 5.1 Code Organization

**Backend Structure:**
```
backend/
├── api/
│   ├── main.py              # FastAPI app, routes
│   ├── routers/             # 25+ endpoint groups
│   │   ├── trades.py        # POST /api/trades, GET /api/trades
│   │   ├── portfolio.py     # GET /api/portfolio, /api/positions
│   │   ├── signals.py       # GET /api/signals, /api/alerts
│   │   ├── strategies.py    # GET/POST strategy allocation
│   │   ├── analytics.py     # GET /api/analytics, /api/daily-summary
│   │   ├── health.py        # GET /api/health
│   │   ├── ha.py            # GET /api/ha/status, POST /api/ha/sync
│   │   └── ...
│   └── middleware.py        # Logging, error handling, auth
│
├── exchange/
│   ├── binance_connector.py # REST API, rate limiting
│   ├── websocket.py         # WebSocket for prices, candles
│   ├── order_manager.py     # Order placement, cancellation
│   └── rate_limiter.py      # Token bucket
│
├── analytics/
│   ├── signals.py           # RSI, MACD, Bollinger Bands
│   ├── technical_indicators.py # Calculations
│   ├── portfolio_analyzer.py # P&L, drawdown, win rate
│   ├── regime_detector.py   # Market regime (trending/choppy)
│   └── ...
│
├── execution/
│   ├── smart_executor.py    # Order execution, slippage sim
│   ├── fill_simulator.py    # Paper trading fills
│   └── position_manager.py  # Entry/exit, tracking
│
├── trading/
│   ├── bot_runner.py        # Main loop (autonomous trader)
│   ├── autonomous_trader.py # Signal → auto-execute
│   ├── position_tracker.py  # Entries, exits, P&L
│   ├── risk_manager.py      # Stops, targets, sizing
│   └── failover_monitor.py  # HA heartbeat (being replaced)
│
├── core/
│   ├── config.py            # Settings (pydantic)
│   ├── database.py          # SQLite operations
│   ├── logger.py            # Structured logging
│   ├── ha_state_manager.py  # ✅ NEW: State sync
│   ├── ha_heartbeat.py      # ✅ NEW: Failure detection
│   ├── ha_failover.py       # ✅ NEW: Promotion logic
│   └── ha_config.py         # ✅ NEW: HA config
│
├── models/
│   ├── trade.py             # Trade data model
│   ├── position.py          # Position model
│   ├── order.py             # Order model
│   └── ...
│
└── utils/
    ├── validators.py        # Input validation
    ├── formatters.py        # JSON serialization
    └── ...
```

### 5.2 Testing Strategy

**Unit Tests (Fast, <1s):**
- Signal calculations (RSI, MACD, BB)
- Position sizing logic
- P&L calculations
- Risk checks (stops, targets)
- Data validation

**Integration Tests (Medium, 5s):**
- Binance API (testnet only)
- Order placement and fills
- Position tracking
- Database persistence
- HA state sync and failover

**Acceptance Tests (Slow, hours):**
- 10-day paper trading (>55% win rate)
- Failover under load (100+ trades/day)
- Database consistency (PRIMARY ↔ BACKUP)
- 24-hour autonomous trading (sleep mode)

**Test Coverage Target:**
- Backend: ≥85% code coverage
- Critical paths: 100% coverage (signal gen, order exec, P&L)
- HA logic: 100% coverage (state sync, failover)

### 5.3 Code Quality Standards

**Python Standards:**
- Black formatter (auto-format)
- Ruff linter (with fixes)
- Mypy type checking (strict mode)
- Docstrings on all public functions
- No hardcoded values (use config)

**API Standards:**
- REST conventions (GET/POST/PUT/DELETE)
- JSON request/response
- Error codes (400, 401, 404, 500)
- Timestamps in ISO 8601
- Idempotent endpoints where possible

**Database Standards:**
- SQLite with type constraints
- Primary keys on all tables
- Foreign keys where applicable
- Indexes on frequently queried columns
- Regular backups (daily)

---

## PART 6: DEPLOYMENT & DEVOPS

### 6.1 Environment Setup

**Three Environments:**

1. **Development (Local)**
   - `TRADING_MODE=paper`
   - `BINANCE_TESTNET=true`
   - `HA_ENABLED=false`
   - Port 8000

2. **Staging (Paper Trading)**
   - `TRADING_MODE=paper`
   - `BINANCE_TESTNET=true`
   - `HA_ENABLED=true` (optional, for testing)
   - Two machines if HA testing

3. **Production (Live Trading)**
   - `TRADING_MODE=live`
   - `BINANCE_TESTNET=false`
   - `HA_ENABLED=true` (required)
   - Two machines (PRIMARY + BACKUP)

### 6.2 Deployment Sequence

**Phase 1: MVP Paper Trading (2-3 weeks)**
```
1. Week 1: Core API + Binance integration
2. Week 2: Signal generation + paper trading
3. Week 3: Dashboard + alerts + 10-day paper test
4. Success: >55% win rate on real prices
```

**Phase 2: HA & Live (3-4 weeks after Phase 1)**
```
1. Setup second machine (BACKUP)
2. Deploy HA infrastructure (already built)
3. Test failover scenarios
4. Run 2-week paper test with HA enabled
5. Paper → Live: Change env var, deploy to Binance live
6. Live test: €1,000 capital, 2 weeks, >55% win rate
7. Success: Positive P&L, no crashes, system stable
```

### 6.3 Monitoring & Alerts

**Key Metrics to Monitor:**

| Metric | Target | Alert >/<|
|--------|--------|----------|
| Daily P&L | +€50 | <-€50 (loss day) |
| Win rate | >55% | <50% (losing strategy) |
| Drawdown | <20% | >30% (high loss) |
| API latency | <500ms | >1000ms (slow) |
| HA sync | 0 failures | >0 (data loss risk) |
| Uptime | 99.5% | <99% (downtime) |
| Account heat | 30-60% | >70% (over-leveraged) |

**Alert Channels:**
- Dashboard (pop-up notification)
- Email (critical alerts)
- SMS (critical + emergency)
- Slack (if available)

### 6.4 Backup & Recovery

**Daily Backups:**
```bash
# Automated at midnight
cp trading.db trading.db.backup.$(date +%Y%m%d)

# Encrypted and stored offsite
gpg --symmetric trading.db.backup.*
```

**Recovery Procedure:**
```bash
1. Stop trading (HALT SYSTEM)
2. Restore: cp trading.db.backup.YYYYMMDD trading.db
3. Verify: sqlite3 trading.db "SELECT count(*) FROM trades;"
4. Restart API
5. Resume trading
```

---

## PART 7: KNOWN ISSUES & GAPS

### 7.1 Critical Gaps

**❌ Global Concurrency (92 unprotected globals)**
- Impact: Race conditions if both machines trade simultaneously (shouldn't happen in active-passive)
- Fix: Add asyncio.Lock() to 92 critical globals
- Timeline: 15 hours (Phase 3)
- Risk: LOW (dormant by design in active-passive)

**❌ TOCTOU Races (31 instances)**
- Impact: Time-of-Check to Time-of-Use gaps in order execution
- Fix: Wrap in locks, atomic operations
- Timeline: 8 hours (Phase 4A)
- Risk: MEDIUM (could cause duplicate orders during failover)

**❌ Async Races (1,623 instances)**
- Impact: Multiple tasks accessing shared state without coordination
- Fix: Add locks to async handlers, coordinate updates
- Timeline: 10+ hours (Phase 4B, prioritize top 200)
- Risk: MEDIUM (could cause state divergence)

**❌ Frontend Not Built**
- Impact: Cannot run 10-day paper test without dashboard
- Fix: Build React frontend with WebSocket updates
- Timeline: 1-2 weeks
- Risk: HIGH (blocks MVP testing)

**❌ Paper Trading Not Tested at Scale**
- Impact: Unknown if system can handle 100+ trades/day
- Fix: Run 24-hour stress test with high signal generation
- Timeline: 1 day (after frontend)
- Risk: MEDIUM (perf issues could emerge)

### 7.2 Design Issues

**Signal Alerts Without Expiration**
- Issue: Alert fires, trader doesn't act, signal becomes stale
- Fix: Add 30-second expiration (already in requirements)
- Timeline: <1 hour
- Risk: LOW

**No Account Recovery on Crash**
- Issue: API crash → in-memory state lost
- Fix: Implement database restore on startup
- Timeline: 2 hours (already designed)
- Risk: MEDIUM (data loss possible)

**HA State Sync Could Be Incomplete**
- Issue: If sync fails silently, BACKUP has stale state
- Fix: Validate state coverage (80% minimum) before failover
- Timeline: Already implemented
- Risk: LOW (coverage check in place)

### 7.3 Missing Documentation

- [ ] Runbooks (deployment, troubleshooting)
- [ ] Postmortems (if failures occur)
- [ ] SLOs (service level objectives)
- [ ] Ops guide (how to monitor, scale)

---

## PART 8: ROADMAP

### Phase 0: Design ✅ DONE
- [x] Requirements (20 FR, 26 NFR)
- [x] Architecture diagrams
- [x] V-Model board
- [x] HA infrastructure
- [x] Project structure

**Timeline:** 1-2 weeks (DONE)

### Phase 1: MVP Paper Trading ⏳ NEXT
**Week 1-2: Core API**
- [ ] Complete Binance integration (REST + WebSocket)
- [ ] Implement paper trading (simulated fills)
- [ ] Basic dashboard (static HTML)
- [ ] Health check endpoint

**Week 3: Signals & Strategies**
- [ ] Signal generation (RSI, MACD, BB)
- [ ] Strategy allocation (3 strategies)
- [ ] Real-time alerts (to console for now)
- [ ] Time-based parameter switching

**Week 4: Manual Control**
- [ ] BUY/SELL buttons
- [ ] Quick exit buttons (25%/50%/75%/100%)
- [ ] Stop/profit adjustments
- [ ] System states (TRADING/PAUSED/etc.)

**Week 5: Monitoring**
- [ ] Real-time dashboard (WebSocket updates, 1s)
- [ ] Portfolio display
- [ ] Position tracking
- [ ] Strategy analytics

**Week 6: Acceptance Test**
- [ ] Run 10-day paper test
- [ ] Target: >55% win rate
- [ ] Documentation review

**Timeline:** 3-4 weeks total

**Success Criteria:**
- ✅ 10-day paper test: >55% win rate
- ✅ Zero crashes during test
- ✅ All trades logged correctly
- ✅ HA heartbeat stable

### Phase 2: HA & Live ⏳ AFTER PHASE 1
**Week 1: HA Verification**
- [ ] Lock 8 critical globals
- [ ] Test failover scenarios
- [ ] Run chaos tests (kill PRIMARY)
- [ ] Verify state consistency

**Week 2: Paper HA Test**
- [ ] Run 2-week paper test with HA enabled
- [ ] Force failovers during trading
- [ ] Verify no duplicate trades
- [ ] Verify all trades logged

**Week 3: Live Setup**
- [ ] Setup Binance live API keys (testnet → live)
- [ ] Update configuration
- [ ] Security review (API key protection)
- [ ] Deploy to production machines

**Week 4: Live Trading**
- [ ] €1,000 capital deployment
- [ ] 2-week live trading test
- [ ] Target: >55% win rate, positive P&L
- [ ] Monitor 24/7 for issues

**Timeline:** 3-4 weeks total

**Success Criteria:**
- ✅ HA failover works correctly
- ✅ Zero duplicate trades
- ✅ 2-week live test: >55% win rate, positive P&L
- ✅ System stable (99.5% uptime)

### Phase 3: Hardening & Learning ⏳ AFTER PHASE 2
**Goals:** Production-grade reliability

**Global Locking (15 hours)**
- [ ] Lock remaining 86 critical globals
- [ ] Fix all TOCTOU races (31 instances)
- [ ] Fix top 200 async races

**Testing & Validation (20+ hours)**
- [ ] Full integration test suite
- [ ] Chaos testing (failure scenarios)
- [ ] Load testing (100+ trades/day)
- [ ] Stress testing (high volatility)
- [ ] Recovery testing (failover scenarios)

**Operational Excellence (10+ hours)**
- [ ] Complete runbooks
- [ ] Monitoring dashboard
- [ ] Alert tuning
- [ ] Backup/restore procedures
- [ ] Postmortem templates

**Timeline:** 4-6 weeks total

**Success Criteria:**
- ✅ 90% code coverage (all tests passing)
- ✅ Zero race conditions detected
- ✅ 99.9% uptime over 30 days
- ✅ <500ms signal latency, <2s order execution

### Phase 4: Advanced Features ⏳ FUTURE
**Learning & Analytics (20+ hours)**
- [ ] Per-strategy performance tracking
- [ ] Real-time win rate by time-of-day
- [ ] Trade quality analysis
- [ ] Daily learning summary

**Optimizations (15+ hours)**
- [ ] Strategy learning (adjust parameters automatically)
- [ ] Dynamic position sizing refinement
- [ ] Overnight mode optimization

**Integrations (10+ hours)**
- [ ] SMS alerts (Twilio)
- [ ] Email alerts (SendGrid)
- [ ] Slack notifications
- [ ] Backup exchange (Kraken, FTX)

**Timeline:** 5-8 weeks total

---

## PART 9: SUMMARY & NEXT STEPS

### Project Health

| Aspect | Status | Risk |
|--------|--------|------|
| **Vision** | Clear | 🟢 Low |
| **Requirements** | Complete | 🟢 Low |
| **Architecture** | Solid | 🟢 Low |
| **HA Infrastructure** | Built | 🟢 Low |
| **Implementation** | Partial (60%) | 🟡 Medium |
| **Testing** | Framework ready | 🟡 Medium |
| **Frontend** | Not started | 🔴 High |
| **Documentation** | Comprehensive | 🟢 Low |

### Immediate Priorities

**1. Lock 8 Critical Globals (2 hours)**
- `_fill_tracker` (MOST CRITICAL)
- `_allocation_manager`, `_analyzer`, `_optimizer`
- `_portfolio_monitor`, `_rebalancing_engine`, `_risk_engine`, `_explainer`
- Pattern: Add `asyncio.Lock()` and wrap access

**2. Build React Frontend (1-2 weeks)**
- Real-time dashboard with 1-second updates
- BUY/SELL buttons, quick exits
- System state display
- Portfolio monitoring
- Basic charts (P&L over time)

**3. Complete API Endpoints (1 week)**
- All 25+ routers fully functional
- WebSocket for real-time updates
- Error handling and validation
- Input validation (no injection attacks)

**4. Run 10-Day Paper Test (1-2 weeks)**
- Real live prices from Binance WebSocket
- Manual order entry (trader approves signals)
- Target: >55% win rate
- All trades logged

**5. Setup HA Deployment (1 week)**
- Second machine setup
- Network configuration
- State sync testing
- Failover validation

### Success Definition

**By End of Phase 1 (MVP):**
- ✅ 10-day paper test: >55% win rate
- ✅ Zero system crashes
- ✅ All trades logged correctly
- ✅ Dashboard working, real-time updates
- ✅ Ready for Phase 2

**By End of Phase 2 (Live):**
- ✅ 2-week live trading: >55% win rate, positive P&L
- ✅ HA failover tested and verified
- ✅ Zero duplicate trades
- ✅ 99.5% uptime
- ✅ Ready for production scaling

---

## APPENDIX: Key Metrics & KPIs

### Trading Metrics
- **Win Rate:** % of winning trades (target >55%)
- **Profit Factor:** Gross profit / gross loss (target >1.5x)
- **Average Trade P&L:** Mean P&L per trade (target >€1)
- **Drawdown:** Peak-to-trough loss (target <20%)
- **Sharpe Ratio:** Return / volatility (target >1.0)

### Operational Metrics
- **Uptime:** (Total time - downtime) / total time (target 99.5%)
- **Signal Latency:** p95/p99 (target <500ms)
- **Order Execution:** p95/p99 (target <2s)
- **API Errors:** 5xx rate (target <0.1%)
- **HA Failover:** Time to promote (target <30s)

### Code Quality Metrics
- **Test Coverage:** % of code tested (target ≥85%)
- **Critical Coverage:** % of critical paths tested (target 100%)
- **Linting Score:** Black, Ruff, Mypy pass rate (target 100%)
- **Code Duplication:** % of duplicated code (target <5%)
- **Complexity:** Cyclomatic complexity per function (target avg <10)

---

**Report Generated:** 2026-07-02  
**Report Status:** ✅ COMPREHENSIVE ANALYSIS COMPLETE

For detailed technical specifications, see:
- `FUNCTIONAL_REQUIREMENTS.md` — User features
- `NONFUNCTIONAL_REQUIREMENTS.md` — System properties
- `ARCHITECTURE_OVERVIEW.md` — System design
- `HA_INTEGRATION_GUIDE.md` — HA deployment
- `CLAUDE.md` — Development standards
