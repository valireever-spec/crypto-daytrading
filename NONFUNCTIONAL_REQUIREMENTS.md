# Crypto Daytrading Platform — Non-Functional Requirements

**Project:** Crypto Daytrading HA System  
**Target Launch:** 2026-07-15 (live with €1,000)

---

## Performance Requirements

### NFR-001: Signal Latency
- **Requirement:** Signal generation must complete in <500ms per symbol
- **Why:** Crypto moves fast (1-2% per minute); slow signals = missed trades
- **Measurement:** Time from price update to buy/sell signal output
- **Test:** Process 1,000 historical candles, measure p95/p99 latency
- **Acceptance:** ≥95% of signals <500ms

---

### NFR-002: Order Execution Speed
- **Requirement:** Order must be placed to Binance within 2 seconds of signal
- **Why:** Slippage increases with delay; market can gap
- **Measurement:** Time from signal generation to Binance API response
- **Test:** Place 10 market orders, measure p50/p95 latency
- **Acceptance:** ≥95% of orders placed <2s

---

### NFR-003: Candle Fetch Latency
- **Requirement:** Fetch latest candles from Binance in <2 seconds
- **Why:** Real-time trading needs fresh data
- **Measurement:** Time from request to receiving full OHLCV data
- **Test:** Fetch 100 symbols × 4 timeframes = 400 candles in parallel
- **Acceptance:** <2s for full batch, <100ms per symbol

---

### NFR-004: Throughput
- **Requirement:** Support ≥100 trades/day (crypto volatility is high)
- **Why:** Need capacity for multiple strategies or scaled trading
- **Measurement:** Trades processed per day without CPU/memory degradation
- **Test:** Run strategy for 30 days, measure avg trades/day
- **Acceptance:** ≥100 trades/day with <5% CPU utilization

---

### NFR-005: Memory Usage
- **Requirement:** Keep memory footprint <500MB during normal operation
- **Why:** HA backup machine may have limited resources
- **Measurement:** Peak memory during 24h trading window
- **Test:** Monitor memory for 24h, capture peak usage
- **Acceptance:** Peak <500MB, no memory leaks over 7 days

---

## Reliability Requirements

### NFR-006: Availability (HA)
- **Requirement:** 99.5% uptime (≤3.6h downtime/month)
- **Why:** Crypto markets 24/7; downtime = missed trades = lost profit
- **Measurement:** (Total time - downtime) / total time
- **Test:** Run for 30 days, monitor both machines for crashes
- **Acceptance:** ≥99.5% without manual intervention

---

### NFR-007: Data Consistency (No Duplicate Trades)
- **Requirement:** No duplicate orders even during failover
- **Why:** Dual machines could both execute same signal if not careful
- **Measurement:** Audit trail shows no identical (symbol, time, qty, side) pairs
- **Test:** Force failover during trade execution, verify only 1 order created
- **Acceptance:** 0 duplicate trades in 30-day test run

---

### NFR-008: Recovery Time Objective (RTO)
- **Requirement:** Backup machine must take over within 30 seconds
- **Why:** Crypto can move 1-2% in 30s; longer = lost opportunity/loss
- **Measurement:** Time from main machine failure to first backup trade
- **Test:** Kill main machine process, measure time to backup executing signals
- **Acceptance:** ≤30s RTO, measured 5 times, avg <25s

---

### NFR-009: Recovery Point Objective (RPO)
- **Requirement:** Lose ≤1 trade on failover (≤€10 in lost opportunity)
- **Why:** Perfect sync is impossible; accept small loss during handover
- **Measurement:** Trades executed by main but not backup in final 2 seconds
- **Test:** Analyze logs during forced failover
- **Acceptance:** ≤1 trade lost, impact <€10

---

### NFR-010A: Platform-Wide Data Consistency
- **Requirement:** All platform components (PRIMARY API, BACKUP API, SQLite database, in-memory engine) MUST have identical state
- **Why:** Data divergence causes trading errors, incorrect P&L, failed failover
- **Scope:** Every trade, cash balance, P&L, position must be identical across:
  - `PRIMARY.memory` (in-memory engine state)
  - `PRIMARY.database` (SQLite on PRIMARY machine)
  - `BACKUP.memory` (in-memory engine state)
  - `BACKUP.database` (SQLite on BACKUP machine)
- **Implementation:**
  - Every field persisted to database MUST be loaded on restart
  - Sync endpoint transmits ALL state including trade details and P&L
  - Database schema includes all required fields (realized_pnl, fee, etc.)
- **Measurement:**
  - Execute 10 trades on PRIMARY
  - Compare PRIMARY.memory with BACKUP.memory: 100% match
  - Compare PRIMARY.database with BACKUP.database: 100% match
  - Kill BACKUP, restart, verify state recovered exactly
- **Test:** Automated consistency checks in CI
- **Acceptance:** ✅ All fields match across all components

---

### NFR-010: Database Durability (API-Database Sync)
- **Requirement:** In-memory state MUST sync permanently with SQLite database
- **Why:** API crashes/restarts would lose account state (cash, P&L) without this
- **Scope:**
  - Every trade execution → write to `trades` table ✅
  - Every trade execution → update `account_state` row (cash, total_pnl, daily_pnl) ✅
  - Every position change → persist to database ✅
  - On API startup → restore state from database ✅
- **Implementation:**
  - `db.insert_trade()` called after order fills
  - `db.save_account_state()` called immediately after `insert_trade()`
  - `_restore_trades_from_db()` called on engine init
  - `_restore_account_state_from_db()` called on engine init
- **Measurement:** 
  - Before: Execute 10 trades, kill API, restart → state lost
  - After: Execute 10 trades, kill API, restart → state recovered exactly
- **Test:** 
  1. Execute trade (BUY BTCUSDT, €5,000 cost)
  2. Verify in-memory: €4,790 cash (€10,000 - €5,000 - fee)
  3. Kill API process
  4. Restart API
  5. Verify restored state: €4,790 cash, 1 trade in history
  6. Execute SELL order
  7. Repeat 5 times with different trades
- **Acceptance:** 
  - ✅ Cash survives restart (within €0.01)
  - ✅ P&L survives restart (within €0.01)
  - ✅ Trade count survives restart (must match)
  - ✅ Trade details match database exactly

---

## Security Requirements

### NFR-010: API Key Protection
- **Requirement:** Binance API keys never stored in code, logs, or version control
- **Why:** Stolen keys = complete account compromise
- **Measurement:** Audit code + logs + git history for plaintext keys
- **Test:** `grep -r "BINANCE.*KEY\|api.*key" --include="*.py" --include="*.txt"`
- **Acceptance:** 0 keys found in codebase, all in environment variables

---

### NFR-011: Input Validation
- **Requirement:** All user inputs validated (strategy parameters, order quantities)
- **Why:** Bad inputs could cause loss or security issues
- **Examples:**
  - Strategy thresholds: must be 0-100
  - Order quantity: must be >0, <account balance
  - Symbols: must match Binance notation (BTCUSDT, ETHUSDT)
- **Test:** Unit tests for 50+ invalid inputs
- **Acceptance:** All inputs validated, clear error messages

---

### NFR-012: Audit Trail Immutability
- **Requirement:** Trade audit trail is append-only, never deleted or modified
- **Why:** Regulatory requirement for live trading, forensics on losses
- **Measurement:** Audit trail file has no overwrites, only appends
- **Test:** Verify file only grows, verify all trades logged
- **Acceptance:** 100% of trades logged, audit trail integrity verified

---

## Observability Requirements

### NFR-013: Structured Logging
- **Requirement:** All events logged as JSON (timestamp, level, event, context)
- **Why:** Easy parsing for monitoring, alerting, debugging
- **Format:** `{"timestamp": "2026-07-15T09:30:00Z", "level": "INFO", "event": "ORDER_FILLED", "symbol": "BTCUSDT", "qty": 0.5, "price": 45000.50}`
- **Test:** Parse logs into JSON, verify all events captured
- **Acceptance:** 100% of events loggable as JSON, <5KB per trade

---

### NFR-014: Metrics & Dashboard
- **Requirement:** Real-time dashboard shows P&L, win rate, Sharpe, system health
- **Why:** User must know if strategy is working and system is healthy
- **Metrics:**
  - Daily P&L (USD and %)
  - Win rate (profitable trades / total trades)
  - Profit factor (avg winning trade / avg losing trade)
  - Sharpe ratio (risk-adjusted return)
  - Consecutive wins/losses
  - Binance API status
  - Backup machine status
- **Test:** Dashboard displays all metrics after 10 trades
- **Acceptance:** All 8 metrics visible, update every 10 seconds

---

### NFR-015: Alerts & Runbooks
- **Requirement:** Critical events trigger alerts with runbooks for action
- **Why:** 24/7 trading requires automation; user can't monitor constantly
- **Alert Triggers:**
  - Daily loss >5% account → **Runbook:** Stop all new positions, close if bounce
  - Binance connectivity lost for >60s → **Runbook:** Wait 30s, retry, alert
  - Backup failover detected → **Runbook:** Investigate main machine, verify backup health
  - Order stuck >5min unfilled → **Runbook:** Cancel and retry, or manual intervention
- **Test:** Simulate each alert condition, verify runbook output
- **Acceptance:** All 4 alerts tested, runbooks documented

---

## Maintainability Requirements

### NFR-016: Code Organization
- **Requirement:** Single-responsibility modules, max 500 lines per file
- **Why:** Crypto market moves fast; bugs must be found and fixed quickly
- **Structure:**
  - `exchange/` — Binance API wrapper only
  - `strategies/` — Signal generation only
  - `execution/` — Order placement only
  - `portfolio/` — Position tracking only
  - `api/` — HTTP endpoints only
- **Test:** Measure file sizes, check module coupling
- **Acceptance:** No file >500 lines, <3 dependencies per module

---

### NFR-017: Type Hints & Linting
- **Requirement:** 100% type hints, mypy 0 errors, black formatted
- **Why:** Catches bugs at dev time, not production
- **Test:** `mypy . && black --check . && ruff check .`
- **Acceptance:** All checks pass, 0 warnings

---

### NFR-016A: Code Quality Excellence (Lifetime Commitment)
- **Requirement:** Code quality must be maintained at highest standards throughout entire project lifetime
- **Why:** Technical debt spirals; high quality prevents bugs, reduces maintenance cost, enables rapid iteration
- **Standards:**
  - Type hints: 100% (mypy 0 errors, not optional)
  - Linting: black + ruff 0 issues (auto-format on every commit)
  - Cyclomatic complexity: <10 per function
  - File size: <300 lines (split at 400 lines)
  - Duplication: <5% (DRY principle)
  - Test coverage: ≥85% on critical paths
  - Documentation: Every public function has docstring
  - Dependencies: <20 external packages (lean)
- **Implementation:**
  - Pre-commit hook runs mypy + black + ruff (blocks bad code)
  - CI/CD rejects pull requests if:
    - mypy finds errors
    - Coverage drops below 85%
    - File exceeds 500 lines
    - Duplicate code detected
  - Weekly code review for quality (not just functionality)
  - Refactor debt logged and prioritized
- **Measurement:**
  - Codacy/SonarQube score ≥A grade
  - No warnings in any linting tool
  - Test coverage always ≥85%
  - Zero "tech debt" debt warnings in PR reviews
- **Acceptance:** Code passes ALL quality gates before merge
- **Lifetime Enforcement:** These standards apply to EVERY commit, EVERY PR, for entire project lifetime

---

### NFR-017A: Implementation Testing (No Claims Without Tests)
- **Requirement:** EVERY code change must have passing tests BEFORE claiming success
- **Why:** Prevents false claims (e.g., "realized_pnl is persisted" when it wasn't)
- **Rule:** If you can't show a test that verifies it, it's NOT implemented
- **Scope:**
  - New feature → unit test + integration test
  - Bug fix → test that reproduces bug, then test that fix works
  - Refactor → all existing tests must pass
  - Data change → verify before + after state in database
- **Verification Checklist Before Claiming "Done":**
  - [ ] Write test case that would fail without this change
  - [ ] Implement the change
  - [ ] Run test: VERIFY IT PASSES
  - [ ] If on HA system: test on PRIMARY
  - [ ] If on HA system: test on BACKUP (restart if needed)
  - [ ] If database involved: dump schema and verify data actually persisted
  - [ ] Screenshot or output showing test passing
  - [ ] NO claims of "implementation complete" without test proof
- **Test:** Every commit must have associated tests in CI/CD
- **Acceptance:** Zero "false positives" (claimed features that don't work)

---

### NFR-018: Test Coverage
- **Requirement:** ≥85% test coverage for critical paths
- **Critical paths:**
  - Signal generation (must be accurate)
  - Order execution (must not lose money to bugs)
  - Position tracking (must not over-leverage)
  - HA failover (must not duplicate trades)
- **Test:** `coverage run -m pytest && coverage report`
- **Acceptance:** ≥85% coverage, <50 lines uncovered in critical modules

---

### NFR-019: Documentation
- **Requirement:** Every strategy and API endpoint documented with examples
- **Why:** Easy onboarding, understand why trades happened
- **Contents:**
  - Architecture diagram (high-level)
  - Strategy guide (how each strategy works, parameters, use cases)
  - API reference (endpoints, parameters, responses)
  - Runbooks (5 most common issues and fixes)
- **Test:** New user can run strategy without asking questions
- **Acceptance:** Docs explain 5W (what, why, when, who, how) for each feature

---

## Cost Requirements

### NFR-020: Operational Cost Coverage
- **Requirement:** Strategy must be profitable enough to cover costs with 2x safety margin
- **Why:** Otherwise, even if strategy works, losses to fees eat profit
- **Costs:**
  - Binance trading fees: 0.1% per trade (maker) to 0.1% (taker) = ~€1-2/day
  - AWS/hosting (if live): ~€0 (running on local hardware)
  - Monitoring/monitoring tools: €0 (open source)
- **Target:** Daily profit ≥€3 (covers €2 fees + €1 buffer)
- **Test:** 10-day paper test must show avg +€3/day profit
- **Acceptance:** Paper trading shows +€30+ profit for 10 days

---

## Scalability Requirements

### NFR-021: Asset Expansion
- **Requirement:** Support adding new trading pairs without code changes
- **Why:** Want to trade BTCUSDT, ETHUSDT, DOGEUSDT, etc.
- **Implementation:** Config file or database for pairs + strategy mapping
- **Test:** Add 5 new pairs, verify all trade correctly
- **Acceptance:** Can add pair in <5 minutes, no code changes

---

### NFR-022: Strategy Expansion
- **Requirement:** Support adding new strategies without modifying core system
- **Why:** Want to test momentum, mean reversion, grid trading, etc.
- **Implementation:** Strategy interface (entry/exit methods), registry
- **Test:** Add 2 new strategies in <30 minutes
- **Acceptance:** Can plug in new strategy, all existing tests pass

---

## Deployment Requirements

### NFR-023: Zero-Downtime Deployment
- **Requirement:** Deploy code updates without stopping trading
- **Why:** Crypto markets 24/7; downtime = missed trades
- **Approach:** Blue-green deployment or rolling restart with backup takeover
- **Test:** Deploy during trading hours, verify no orders missed
- **Acceptance:** Code updated, 0 trades lost, <5s pause in execution

---

### NFR-024: Configuration Management
- **Requirement:** All settings via environment variables (no hardcoding)
- **Why:** Same code runs on dev, testnet, mainnet with different configs
- **Variables:**
  - `TRADING_MODE`: paper | live
  - `BINANCE_TESTNET`: true | false
  - `INITIAL_CAPITAL`: €1000
  - `STRATEGY`: momentum | meanreversion | grid
  - `MAX_DAILY_LOSS_PCT`: 5.0
- **Test:** Verify each var controls behavior correctly
- **Acceptance:** Code works with 0 hardcoded values

---

## Acceptance Testing

### NFR-025: Paper Trading Acceptance
- **Requirement:** Pass 10-day paper trading run with >55% win rate and positive P&L
- **Setup:** €10,000 virtual capital, best strategy from testing
- **Acceptance Criteria:**
  - ≥50 trades (diverse scenarios)
  - Win rate ≥55%
  - Profit factor ≥1.2 (avg win ≥ 1.2 × avg loss)
  - Daily max drawdown ≤5%
  - Sharpe ≥0.5 (acceptable risk-adjusted return)
- **Timeline:** 10 trading days (or when criteria met)

---

### NFR-026: Live Trading Acceptance
- **Requirement:** Pass 2-week live trading with €1,000 without losses >5%
- **Setup:** Real Binance, best strategy, €1,000 starting capital
- **Acceptance Criteria:**
  - ≥100 trades (5-10/day typical for crypto)
  - Win rate ≥55% (same as paper)
  - Total P&L ≥€50 (covers fees and proves system works)
  - No daily loss >5% (daily stop enforced)
  - Slippage vs paper <2% (real market conditions acceptable)
- **Timeline:** 10-14 trading days (or when criteria met)

---

## Trading Configuration Requirements (Phase 1 - Paper Trading)

### Overview
The following 9 parameters define the autonomous trading system's behavior during Phase 1. These are stored in `.env` file and synced between primary and backup machines via SSH tunnel. All parameters are dynamically configurable via API without requiring system restart.

---

### CFR-001: Entry Signal Threshold
- **Current Value:** 60.0 (on scale 0-100)
- **Requirement:** Minimum signal strength (technical quality score) required to open a new position
- **Rationale:** Crypto signals are noisy; 60 = balanced between capturing opportunities and filtering noise
- **Source of Truth:** `ENTRY_THRESHOLD` in `.env`
- **Sync Method:** SSH to backup machine when changed via API
- **Validation:** 0 ≤ value ≤ 100
- **Acceptance:** System only opens new positions when signal strength ≥ configured threshold

---

### CFR-002: Position Size Per Trade
- **Current Value:** 2.5% (of total equity)
- **Requirement:** Maximum risk per individual trade
- **Rationale:** 2.5% × €10,000 initial = €250 per trade; improved from 1.5% for better learning signal
- **Source of Truth:** `POSITION_SIZE_PCT` in `.env`
- **Sync Method:** SSH to backup machine when changed via API
- **Validation:** 0.1 ≤ value ≤ 20 (%)
- **Format:** Stored as percentage (e.g., 2.5 = 2.5%), not decimal
- **Linkage:** Auto-linked to Max Positions to keep total portfolio risk ≤25%
- **Acceptance:** Position size always matches configured percentage

---

### CFR-003: Maximum Concurrent Positions
- **Current Value:** 8 (simultaneous open trades)
- **Requirement:** Limit concentration risk and capital drawdown
- **Rationale:** 8 positions × 2.5% = 20% total portfolio risk; leaves 80% capital for margin/volatility; improved from 5 for more learning activity
- **Source of Truth:** `MAX_POSITIONS` in `.env`
- **Sync Method:** SSH to backup machine when changed via API
- **Validation:** 1 ≤ value ≤ 10
- **Linkage:** Auto-linked to Position Size to keep total portfolio risk ≤25%
- **Acceptance:** System never opens >8 positions simultaneously

---

### CFR-004: Exit Stop Loss
- **Current Value:** 3.0% (loss per trade)
- **Requirement:** Maximum acceptable loss before automatically closing position
- **Rationale:** 3% loss per trade (improved from 2%) reduces whipsaws from crypto noise while maintaining risk control
- **Source of Truth:** `EXIT_STOP_LOSS` in `.env`
- **Sync Method:** SSH to backup machine when changed via API
- **Validation:** 0.1 ≤ value ≤ 50 (%)
- **Format:** Stored as percentage (e.g., 3.0 = 3%), not decimal
- **Linkage:** Auto-linked to Exit Profit Target to maintain 1:1.5 risk/reward ratio
- **Acceptance:** All positions have stop loss ≤ configured value

---

### CFR-005: Exit Profit Target
- **Current Value:** 4.5% (profit per trade)
- **Requirement:** Automatic profit-taking level
- **Rationale:** Maintains 1:1.5 risk/reward ratio (3% stop loss × 1.5 = 4.5% profit target)
- **Source of Truth:** `EXIT_PROFIT_TARGET` in `.env`
- **Sync Method:** SSH to backup machine when changed via API
- **Validation:** 0.1 ≤ value ≤ 50 (%)
- **Format:** Stored as percentage (e.g., 4.5 = 4.5%), not decimal
- **Linkage:** Auto-linked to Exit Stop Loss to maintain 1:1.5 risk/reward ratio (always maintained at stop_loss × 1.5)
- **Acceptance:** Exit profit target / stop loss = 1.5 (within 0.01 tolerance)

---

### CFR-006: Entry Quality Gate
- **Current Value:** 90.0 (percent, 0-100%)
- **Requirement:** Minimum data quality required to open new positions
- **Rationale:** 90% = strict gate; only opens positions when price data is extremely fresh and reliable
- **Source of Truth:** `QUALITY_GATE_ENTRY` in `.env`
- **Sync Method:** SSH to backup machine when changed via API
- **Validation:** 0 ≤ value ≤ 100
- **Behavior:** If data quality drops below 90%, system refuses to open NEW positions (but exits are still allowed)
- **Acceptance:** New positions only opened when quality ≥ configured threshold

---

### CFR-007: Exit Quality Gate
- **Current Value:** 60.0 (percent, 0-100%)
- **Requirement:** Minimum data quality required to close existing positions
- **Rationale:** 60% = permissive gate; allows exits even on degraded data (safety measure for stop losses)
- **Source of Truth:** `QUALITY_GATE_EXIT` in `.env`
- **Sync Method:** SSH to backup machine when changed via API
- **Validation:** 0 ≤ value ≤ 100
- **Behavior:** If data quality drops below 60%, system cannot exit (orders rejected); waits for data recovery
- **Note:** Exit gate is lower than entry gate (prioritize closing losses over opening new positions)
- **Acceptance:** Positions exitable only when quality ≥ configured threshold

---

### CFR-008: Loop Sleep Seconds
- **Current Value:** 10.0 (seconds)
- **Requirement:** Time between consecutive trading loop iterations
- **Rationale:** 10 seconds = ~6 trades/minute maximum; prevents excessive Binance API calls
- **Source of Truth:** `LOOP_SLEEP_SECONDS` in `.env`
- **Sync Method:** SSH to backup machine when changed via API
- **Validation:** 1 ≤ value ≤ 300 (seconds)
- **Binance Constraint:** Stays well below 1200 req/min rate limit
- **Acceptance:** System sleeps exactly configured seconds between trading cycle iterations

---

### CFR-009: Maximum Daily Loss Circuit Breaker
- **Current Value:** 5.0 (percent of initial equity)
- **Requirement:** Auto-stop trading if daily loss exceeds this percentage
- **Rationale:** 5% of €10,000 = €500 max loss/day; protects capital from catastrophic streaks
- **Source of Truth:** `MAX_DAILY_LOSS_PCT` in `.env`
- **Sync Method:** SSH to backup machine when changed via API
- **Validation:** 0.1 ≤ value ≤ 50 (%)
- **Behavior:** Once triggered, system enters "circuit breaker" mode (no new trades) until next trading day resets
- **Acceptance:** All trading halts if daily P&L < -(configured percentage × equity)

---

## HA Synchronization Requirements (Phase 1)

### CFR-010: Automatic Config Sync (Primary → Backup)
- **Requirement:** All parameter changes on primary automatically sync to backup when SSH connection available
- **Mechanism:**
  1. API config change triggers `ConfigManager.sync_to_backup()` immediately
  2. Attempts direct connection: `ssh backup` (192.168.3.25 via LAN)
  3. If direct fails: Falls back to reverse SSH tunnel: `ssh r33v3r.ddns.net` (internet-accessible)
  4. Uses SSH alias `backup` for passwordless authentication (openhab_claude key)
  5. Updates `.env` file on backup machine
  6. Triggers backup API reload to apply new config
  7. Retries with exponential backoff (1s, 2s, 4s) if connection fails
- **Validation:** Both machines always have identical parameter values
- **Sync Method:** SSH with automatic fallback (LAN first, then reverse tunnel)
- **Architecture:** Backup is NOT internet-exposed on 192.168.3.25; reverse SSH tunnel via r33v3r.ddns.net is only access from internet
- **Acceptance:** Config mismatch between primary and backup ≤0 (no tolerance)

### CFR-011: Startup Config Sync
- **Requirement:** After git pull or .env file change, both machines must manually sync
- **Current Process:**
  1. Primary: Update `.env` file (or git pull)
  2. Primary: Restart API (`pkill -9 uvicorn` + restart)
  3. Backup: Manual `ssh backup 'cat > .env...'` to update `.env`
  4. Backup: Restart API
  5. Verify: Both machines respond with identical config
- **Future Improvement:** Add automatic file sync from primary to backup on git pull
- **Acceptance:** Both machines have identical `.env` + `trading_config.json` after startup

### CFR-012: Critical Data Sync (Optional - Phase 2)
- **In Scope (Phase 1):** Parameters only (CFR-001 to CFR-009)
- **Future (Phase 2):** Also sync:
  - Trade history (immutable append-only logs)
  - Active positions (synced every 10s)
  - P&L snapshots (synced every 1h)
  - Circuit breaker status
- **Note:** Can be added as background task using existing SSH tunnel

---

## Success Metrics (Overall)

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Availability** | 99.5% | Uptime over 30 days |
| **Win Rate** | ≥55% | Profitable trades / total trades |
| **Sharpe Ratio** | ≥0.5 | Risk-adjusted return |
| **Daily Profit** | +€3 to €10 | Avg daily P&L |
| **Slippage** | <2% | Live vs paper difference |
| **Latency (signals)** | <500ms | p95 signal generation |
| **Latency (orders)** | <2s | p95 order placement |
| **Uptime (HA)** | 99.5% | Failover working, RTO <30s |
| **Test Coverage** | ≥85% | Coverage on critical paths |

---

## Trade-offs & Constraints

| Constraint | Implication |
|-----------|------------|
| **Live trading starts with €1,000** | Max position size €20 (2%); limits daily P&L to €3-10 |
| **Crypto volatility 5-10x stocks** | Strategy signals must be more selective (fewer false signals) |
| **24/7 market (no market hours)** | System must be always-on; HA mandatory |
| **Binance rate limit 1200 req/min** | Can't check every 1 second; 15s minimum candle interval |
| **No real-time news data** | Can't trade on breaking news; limited to technical signals only |
| **Paper testing only 2 weeks** | Must validate profitability quickly; sample size small |

