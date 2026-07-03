# Traceability Matrix

**Generated:** 2026-07-03 17:30:21

## Summary

| Category | Total | Complete | Partial | Not Found |
|----------|-------|----------|---------|-----------|
| Functional Requirements | 20 | 0 | 0 | 0 |
| Non-Functional Requirements | 27 | 0 | 27 | 0 |
| **Total** | **47** | **0** | **27** | **0** |

## Functional Requirements

### FR-001: Binance API Integration

| Aspect | Status | Details |
|--------|--------|---------|
| Implementation | ✅ IMPLEMENTED | 5 file(s) found |
| Test Coverage | ✅ 0/0 PASSED | 5 test file(s) |
| Acceptance Criteria | ✅ 7 criteria | See below |
| Gaps | ✅ 0 gaps | See below |

**Code Files:**
- ./backend/skills_integration.py
- ./backend/exchange/binance_websocket.py
- ./backend/exchange/binance_stream.py
- ./backend/exchange/binance_stream_resilience.py
- ./venv/lib/python3.12/site-packages/binance/api.py

**Test Files:**
- ./venv/lib/python3.12/site-packages/pandas/tests/extension/base/reshaping.py
- ./venv/lib/python3.12/site-packages/pytest/__init__.py
- ./venv/lib/python3.12/site-packages/_pytest/assertion/rewrite.py
- ./venv/lib/python3.12/site-packages/_pytest/assertion/util.py
- ./venv/lib/python3.12/site-packages/_pytest/logging.py

**Acceptance Criteria:**
- [ ] GET ticker data (BTCUSDT, ETHUSDT, etc.) with <1s latency
- [ ] POST market and limit orders with execution confirmation
- [ ] GET order status in real-time (pending → filled → cancelled)
- [ ] GET account balance and position status
- [ ] Handle rate limits (1200 req/min for user API)
- [ ] Testnet support for paper trading (no real money)
- [ ] Fallback to backup exchange if Binance unavailable (TBD: second exchange)

---

### FR-002: Paper Trading Engine (Real Live Prices via Binance WebSocket)

| Aspect | Status | Details |
|--------|--------|---------|
| Implementation | ✅ IMPLEMENTED | 5 file(s) found |
| Test Coverage | ✅ 0/0 PASSED | 5 test file(s) |
| Acceptance Criteria | ✅ 0 criteria | See below |
| Gaps | ✅ 0 gaps | See below |

**Code Files:**
- ./backend/exchange/paper_trading.py
- ./backend/api/routers/trading_control.py
- ./backend/analytics/risk_metrics_engine.py
- ./backend/analytics/portfolio_rebalancing_engine.py
- ./backend/analytics/attribution_engine.py

**Test Files:**
- ./tests/test_paper_trading.py
- ./venv/lib/python3.12/site-packages/pandas/tests/extension/base/io.py
- ./venv/lib/python3.12/site-packages/pytest_cov/plugin.py
- ./venv/lib/python3.12/site-packages/pytest_asyncio/plugin.py
- ./venv/lib/python3.12/site-packages/mypyc/test/config.py

---

### FR-003: Real-Time Signal Generation (REDESIGNED)

| Aspect | Status | Details |
|--------|--------|---------|
| Implementation | ✅ IMPLEMENTED | 5 file(s) found |
| Test Coverage | ✅ 0/0 PASSED | 5 test file(s) |
| Acceptance Criteria | ✅ 9 criteria | See below |
| Gaps | ✅ 0 gaps | See below |

**Code Files:**
- ./backend/analytics/signal_explainer.py
- ./backend/analytics/signals.py
- ./backend/core/signal_validation.py
- ./venv/lib/python3.12/site-packages/anyio/_core/_signals.py
- ./venv/lib/python3.12/site-packages/scipy/signal/_signal_api.py

**Test Files:**
- ./venv/lib/python3.12/site-packages/_pytest/config/__init__.py
- ./venv/lib/python3.12/site-packages/pytest_cov/embed.py
- ./venv/lib/python3.12/site-packages/scipy/signal/tests/mpsig.py
- ./venv/lib/python3.12/site-packages/mypyc/test-data/fixtures/ir.py
- ./venv/lib/python3.12/site-packages/_pytest/_code/__init__.py

**Acceptance Criteria:**
- [ ] Calculate RSI (14-period), MACD, Bollinger Bands on OHLCV candles
- [ ] Support multiple timeframes: 1m, 5m, 15m, 1h (user selects which to watch)
- [ ] Return signal score: -100 (strong sell) to +100 (strong buy)
- [ ] Update signal every time candle closes (not every 15 minutes)
- [ ] Latency: <500ms from candle close to signal available
- [ ] Handle edge cases: NaN on insufficient candles, gaps in data
- [ ] WebSocket feed for real-time price updates (sub-second)
- [ ] Three strategies available:
- [ ] Define parameter sets per time block (can edit without restart):

---

### FR-004: Real-Time Signal Alerts (NEW — CRITICAL)

| Aspect | Status | Details |
|--------|--------|---------|
| Implementation | ✅ IMPLEMENTED | 5 file(s) found |
| Test Coverage | ✅ 0/0 PASSED | 5 test file(s) |
| Acceptance Criteria | ✅ 2 criteria | See below |
| Gaps | ⚠️ 1 gap(s) | See below |

**Code Files:**
- ./backend/analytics/signal_explainer.py
- ./backend/analytics/signals.py
- ./backend/core/signal_validation.py
- ./venv/lib/python3.12/site-packages/anyio/_core/_signals.py
- ./venv/lib/python3.12/site-packages/scipy/signal/_signal_api.py

**Test Files:**
- ./venv/lib/python3.12/site-packages/_pytest/config/__init__.py
- ./venv/lib/python3.12/site-packages/pytest_cov/embed.py
- ./venv/lib/python3.12/site-packages/scipy/signal/tests/mpsig.py
- ./venv/lib/python3.12/site-packages/pytest_asyncio/plugin.py
- ./venv/lib/python3.12/site-packages/mypyc/test-data/fixtures/ir.py

**Acceptance Criteria:**
- [ ] Alert when signal ≥ configured threshold (e.g., ≥70 for strong buy)
- [ ] Alert channels:

**Gaps Identified:**
- Acceptance criterion may not be implemented: 'Alert channels:...'

---

### FR-005: Manual Order Entry & Execution (NEW — CRITICAL)

| Aspect | Status | Details |
|--------|--------|---------|
| Implementation | ✅ IMPLEMENTED | 5 file(s) found |
| Test Coverage | ✅ 0/0 PASSED | 5 test file(s) |
| Acceptance Criteria | ✅ 1 criteria | See below |
| Gaps | ✅ 0 gaps | See below |

**Code Files:**
- ./venv/lib/python3.12/site-packages/IPython/core/magics/execution.py
- ./venv/lib/python3.12/site-packages/numpy/core/_add_newdocs.py
- ./backend/trading/autonomous_trader/entry.py
- ./backend/core/order_safety.py
- ./venv/lib/python3.12/site-packages/dateparser_scripts/order_languages.py

**Test Files:**
- ./venv/lib/python3.12/site-packages/_pytest/recwarn.py
- ./venv/lib/python3.12/site-packages/_pytest/python_api.py
- ./venv/lib/python3.12/site-packages/pytest_cov/plugin.py
- ./venv/lib/python3.12/site-packages/mypy/test/helpers.py
- ./venv/lib/python3.12/site-packages/pytest_asyncio/plugin.py

**Acceptance Criteria:**
- [ ] **BUY button** on dashboard:

---

### FR-006: Manual Stop & Profit Override (NEW — CRITICAL)

| Aspect | Status | Details |
|--------|--------|---------|
| Implementation | ✅ IMPLEMENTED | 5 file(s) found |
| Test Coverage | ✅ 0/0 PASSED | 5 test file(s) |
| Acceptance Criteria | ✅ 1 criteria | See below |
| Gaps | ✅ 0 gaps | See below |

**Code Files:**
- ./backend/core/emergency_stop.py
- ./backend/core/stop_loss_safety.py
- ./venv/lib/python3.12/site-packages/numpy/core/_add_newdocs.py
- ./backend/analytics/stop_loss.py
- ./venv/lib/python3.12/site-packages/pip/_vendor/tenacity/stop.py

**Test Files:**
- ./venv/lib/python3.12/site-packages/numpy/testing/overrides.py
- ./venv/lib/python3.12/site-packages/_pytest/recwarn.py
- ./venv/lib/python3.12/site-packages/_pytest/python_api.py
- ./venv/lib/python3.12/site-packages/pytest_cov/plugin.py
- ./venv/lib/python3.12/site-packages/mypy/test/helpers.py

**Acceptance Criteria:**
- [ ] On each active position, show:

---

### FR-007: System States & Pause Mechanism (NEW — CRITICAL)

| Aspect | Status | Details |
|--------|--------|---------|
| Implementation | ✅ IMPLEMENTED | 5 file(s) found |
| Test Coverage | ✅ 0/0 PASSED | 5 test file(s) |
| Acceptance Criteria | ✅ 1 criteria | See below |
| Gaps | ⚠️ 1 gap(s) | See below |

**Code Files:**
- ./venv/lib/python3.12/site-packages/prompt_toolkit/contrib/completers/system.py
- ./venv/lib/python3.12/site-packages/numpy/core/_add_newdocs_scalars.py
- ./venv/lib/python3.12/site-packages/numpy/core/_add_newdocs.py
- ./venv/lib/python3.12/site-packages/scipy/sparse/linalg/_dsolve/_add_newdocs.py
- ./venv/lib/python3.12/site-packages/markdown_it/rules_inline/newline.py

**Test Files:**
- ./venv/lib/python3.12/site-packages/IPython/testing/globalipapp.py
- ./venv/lib/python3.12/site-packages/IPython/testing/plugin/dtexample.py
- ./venv/lib/python3.12/site-packages/_pytest/hookspec.py
- ./venv/lib/python3.12/site-packages/_pytest/monkeypatch.py
- ./venv/lib/python3.12/site-packages/_pytest/nodes.py

**Acceptance Criteria:**
- [ ] Four system states (toggle via dashboard):

**Gaps Identified:**
- No logging found in code

---

### FR-008: Dynamic Position Sizing (NEW — CRITICAL)

| Aspect | Status | Details |
|--------|--------|---------|
| Implementation | ✅ IMPLEMENTED | 5 file(s) found |
| Test Coverage | ✅ 0/0 PASSED | 5 test file(s) |
| Acceptance Criteria | ✅ 1 criteria | See below |
| Gaps | ✅ 0 gaps | See below |

**Code Files:**
- ./backend/analytics/position_sizing.py
- ./venv/lib/python3.12/site-packages/coverage/disposition.py
- ./venv/lib/python3.12/site-packages/jedi/inference/value/dynamic_arrays.py
- ./venv/lib/python3.12/site-packages/jedi/inference/dynamic_params.py
- ./backend/core/position_reconciliation.py

**Test Files:**
- ./tests/test_position_sizing.py
- ./venv/lib/python3.12/site-packages/IPython/testing/decorators.py
- ./venv/lib/python3.12/site-packages/_pytest/monkeypatch.py
- ./venv/lib/python3.12/site-packages/_pytest/assertion/util.py
- ./venv/lib/python3.12/site-packages/_pytest/fixtures.py

**Acceptance Criteria:**
- [ ] **Base position size:** 1.5% of account (configurable, default)

---

### FR-009: Real-Time Portfolio Monitoring (REDESIGNED)

| Aspect | Status | Details |
|--------|--------|---------|
| Implementation | ✅ IMPLEMENTED | 5 file(s) found |
| Test Coverage | ✅ 0/0 PASSED | 5 test file(s) |
| Acceptance Criteria | ✅ 1 criteria | See below |
| Gaps | ✅ 0 gaps | See below |

**Code Files:**
- ./backend/api/routers/monitoring.py
- ./backend/analytics/portfolio_analyzer.py
- ./backend/analytics/portfolio_rebalancing_engine.py
- ./backend/analytics/portfolio_regime_monitor.py
- ./backend/analytics/portfolio_optimizer.py

**Test Files:**
- ./backend/analytics/portfolio_backtest_engine_v2.py
- ./backend/backtesting/portfolio_backtest_engine.py
- ./tests/unit/test_portfolio_rebalancing_engine.py
- ./tests/unit/test_portfolio_regime_monitor.py
- ./tests/test_portfolio_orchestrator.py

**Acceptance Criteria:**
- [ ] **Account summary** (update every 1 second):

---

### FR-010: Per-Strategy Analytics (NEW — CRITICAL)

| Aspect | Status | Details |
|--------|--------|---------|
| Implementation | ✅ IMPLEMENTED | 5 file(s) found |
| Test Coverage | ✅ 0/0 PASSED | 5 test file(s) |
| Acceptance Criteria | ✅ 1 criteria | See below |
| Gaps | ✅ 0 gaps | See below |

**Code Files:**
- ./backend/analytics/strategy_analytics.py
- ./backend/api/routers/backup_analytics.py
- ./backend/api/routers/dashboard_wrapper.py
- ./venv/lib/python3.12/site-packages/markdown_it/rules_inline/newline.py
- ./venv/lib/python3.12/site-packages/mypy/semanal_newtype.py

**Test Files:**
- ./venv/lib/python3.12/site-packages/pytest_asyncio/plugin.py
- ./venv/lib/python3.12/site-packages/mypyc/test-data/fixtures/ir.py
- ./venv/lib/python3.12/site-packages/IPython/testing/decorators.py
- ./venv/lib/python3.12/site-packages/IPython/testing/globalipapp.py
- ./venv/lib/python3.12/site-packages/radon/tests/run.py

**Acceptance Criteria:**
- [ ] **Win rate by strategy** (today):

---

### FR-011: Critical Alerts & Runbooks (REDESIGNED)

| Aspect | Status | Details |
|--------|--------|---------|
| Implementation | ✅ IMPLEMENTED | 5 file(s) found |
| Test Coverage | ✅ 0/0 PASSED | 5 test file(s) |
| Acceptance Criteria | ✅ 1 criteria | See below |
| Gaps | ✅ 0 gaps | See below |

**Code Files:**
- ./backend/core/alerting.py
- ./scripts/resource_monitor.py
- ./scripts/failover_monitor.py
- ./scripts/check_ha_status.py
- ./backend/analytics/risk_limits.py

**Test Files:**
- ./venv/lib/python3.12/site-packages/numpy/core/tests/test_array_coercion.py
- ./venv/lib/python3.12/site-packages/scipy/stats/_hypotests.py
- ./venv/lib/python3.12/site-packages/scipy/stats/_binomtest.py
- ./venv/lib/python3.12/site-packages/scipy/stats/tests/test_multicomp.py
- ./venv/lib/python3.12/site-packages/scipy/stats/tests/test_fit.py

**Acceptance Criteria:**
- [ ] **CRITICAL alerts** (SMS + push + email + sound):

---

### FR-012: Trade Quality Analysis (NEW — CRITICAL)

| Aspect | Status | Details |
|--------|--------|---------|
| Implementation | ✅ IMPLEMENTED | 5 file(s) found |
| Test Coverage | ✅ 0/0 PASSED | 5 test file(s) |
| Acceptance Criteria | ✅ 1 criteria | See below |
| Gaps | ✅ 0 gaps | See below |

**Code Files:**
- ./scripts/archive_old_trades.py
- ./venv/lib/python3.12/site-packages/binance/websocket/spot/websocket_api/_trade.py
- ./venv/lib/python3.12/site-packages/binance/spot/_trade.py
- ./backend/core/data_quality.py
- ./venv/lib/python3.12/site-packages/scipy/optimize/_trustregion_constr/equality_constrained_sqp.py

**Test Files:**
- ./venv/lib/python3.12/site-packages/_pytest/_code/code.py
- ./venv/lib/python3.12/site-packages/_pytest/python_api.py
- ./venv/lib/python3.12/site-packages/pandas/_testing/asserters.py
- ./venv/lib/python3.12/site-packages/numpy/testing/_private/utils.py
- ./venv/lib/python3.12/site-packages/mypy/test/data.py

**Acceptance Criteria:**
- [ ] On each closed trade, analyze:

---

### FR-013: HA Redundancy (Dual Machine) (SAME AS BEFORE)

| Aspect | Status | Details |
|--------|--------|---------|
| Implementation | ✅ IMPLEMENTED | 5 file(s) found |
| Test Coverage | ✅ 0/0 PASSED | 5 test file(s) |
| Acceptance Criteria | ✅ 6 criteria | See below |
| Gaps | ✅ 0 gaps | See below |

**Code Files:**
- ./backend/api/routers/redundancy.py
- ./venv/lib/python3.12/site-packages/scipy/optimize/_remove_redundancy.py
- ./venv/lib/python3.12/site-packages/scipy/optimize/_dual_annealing.py
- ./venv/lib/python3.12/site-packages/pip/_vendor/chardet/codingstatemachine.py
- ./venv/lib/python3.12/site-packages/pygments/lexers/robotframework.py

**Test Files:**
- ./venv/lib/python3.12/site-packages/_pytest/hookspec.py
- ./venv/lib/python3.12/site-packages/_pytest/monkeypatch.py
- ./venv/lib/python3.12/site-packages/_pytest/assertion/util.py
- ./venv/lib/python3.12/site-packages/_pytest/python_api.py
- ./venv/lib/python3.12/site-packages/pandas/tests/series/methods/__init__.py

**Acceptance Criteria:**
- [ ] Heartbeat check every 10 seconds (main → backup)
- [ ] Failover trigger after 3 consecutive missed heartbeats (30s)
- [ ] Backup has read-only copy of positions and P&L
- [ ] No duplicate trades during failover
- [ ] UUID per trade order (inherited by backup)
- [ ] Network tolerant: handle 5-10s latency, temporary disconnects

---

### FR-014: Overnight Mode (NEW — NEEDED BEFORE LIVE)

| Aspect | Status | Details |
|--------|--------|---------|
| Implementation | ✅ IMPLEMENTED | 5 file(s) found |
| Test Coverage | ✅ 0/0 PASSED | 5 test file(s) |
| Acceptance Criteria | ✅ 1 criteria | See below |
| Gaps | ✅ 0 gaps | See below |

**Code Files:**
- ./backend/analytics/cost_model_calibrator.py
- ./backend/analytics/realistic_cost_model.py
- ./venv/lib/python3.12/site-packages/pydantic/root_model.py
- ./venv/lib/python3.12/site-packages/pydantic/_internal/_model_construction.py
- ./venv/lib/python3.12/site-packages/requests/models.py

**Test Files:**
- ./venv/lib/python3.12/site-packages/pytest_asyncio/plugin.py
- ./venv/lib/python3.12/site-packages/IPython/core/tests/simpleerr.py
- ./venv/lib/python3.12/site-packages/_pytest/pastebin.py
- ./venv/lib/python3.12/site-packages/_pytest/hookspec.py
- ./venv/lib/python3.12/site-packages/_pytest/assertion/truncate.py

**Acceptance Criteria:**
- [ ] At market close (6pm ET), ask trader:

---

### FR-015: Automatic Database Authority Resolution (HA Recovery)

| Aspect | Status | Details |
|--------|--------|---------|
| Implementation | ✅ IMPLEMENTED | 5 file(s) found |
| Test Coverage | ✅ 0/0 PASSED | 5 test file(s) |
| Acceptance Criteria | ✅ 0 criteria | See below |
| Gaps | ✅ 0 gaps | See below |

**Code Files:**
- ./backend/core/database_authority.py
- ./backend/core/database_integrity.py
- ./backend/core/database_persistence.py
- ./backend/core/database.py
- ./backend/core/database_sync.py

**Test Files:**
- ./tests/test_database_authority.py
- ./venv/lib/python3.12/site-packages/pytest_asyncio/plugin.py
- ./venv/lib/python3.12/site-packages/pytest_mock/plugin.py
- ./venv/lib/python3.12/site-packages/_pytest/hookspec.py
- ./venv/lib/python3.12/site-packages/_pytest/monkeypatch.py

---

### FR-016: Autonomous 24/7 Trading (Sleep Mode)

| Aspect | Status | Details |
|--------|--------|---------|
| Implementation | ✅ IMPLEMENTED | 5 file(s) found |
| Test Coverage | ✅ 0/0 PASSED | 5 test file(s) |
| Acceptance Criteria | ✅ 7 criteria | See below |
| Gaps | ✅ 0 gaps | See below |

**Code Files:**
- ./backend/api/routers/trading_control.py
- ./backend/api/routers/autonomous.py
- ./backend/exchange/paper_trading.py
- ./venv/lib/python3.12/site-packages/pip/_vendor/tenacity/before_sleep.py
- ./backend/analytics/cost_model_calibrator.py

**Test Files:**
- ./venv/lib/python3.12/site-packages/_pytest/timing.py
- ./venv/lib/python3.12/site-packages/mypy/test/helpers.py
- ./venv/lib/python3.12/site-packages/numpy/testing/_private/utils.py
- ./venv/lib/python3.12/site-packages/pytest_asyncio/plugin.py
- ./venv/lib/python3.12/site-packages/IPython/core/tests/simpleerr.py

**Acceptance Criteria:**
- [ ] Bot continuously monitors signals while PRIMARY or BACKUP is running
- [ ] Executes BUY/SELL orders without user approval
- [ ] Respects entry threshold (min signal strength to trigger trade)
- [ ] Respects position limits (max concurrent positions)
- [ ] All trades logged with timestamp, price, P&L
- [ ] HA ensures trading continues if one machine fails
- [ ] Can run 8+ hours uninterrupted (overnight test)

---

### FR-017: Emergency Market Crash Response

| Aspect | Status | Details |
|--------|--------|---------|
| Implementation | ✅ IMPLEMENTED | 5 file(s) found |
| Test Coverage | ✅ 0/0 PASSED | 5 test file(s) |
| Acceptance Criteria | ✅ 5 criteria | See below |
| Gaps | ✅ 0 gaps | See below |

**Code Files:**
- ./backend/api/routers/emergency.py
- ./backend/core/emergency_stop.py
- ./backend/core/crash_detector.py
- ./venv/lib/python3.12/site-packages/yfinance/domain/market.py
- ./venv/lib/python3.12/site-packages/binance/spot/_market.py

**Test Files:**
- ./venv/lib/python3.12/site-packages/_pytest/assertion/util.py
- ./venv/lib/python3.12/site-packages/_pytest/mark/structures.py
- ./venv/lib/python3.12/site-packages/_pytest/runner.py
- ./venv/lib/python3.12/site-packages/_pytest/terminal.py
- ./venv/lib/python3.12/site-packages/_pytest/_code/code.py

**Acceptance Criteria:**
- [ ] "CLOSE ALL" endpoint: Closes all open positions immediately at market price
- [ ] "PAUSE ALL" endpoint: Stops new entry signals, holds existing positions with active stops
- [ ] "HALT SYSTEM" endpoint: Kills all trading, stops HA, freezes all state
- [ ] Each endpoint takes <2 seconds to execute
- [ ] Can be triggered via:

---

### FR-018: Manual Signal Override

| Aspect | Status | Details |
|--------|--------|---------|
| Implementation | ✅ IMPLEMENTED | 5 file(s) found |
| Test Coverage | ✅ 0/0 PASSED | 5 test file(s) |
| Acceptance Criteria | ✅ 6 criteria | See below |
| Gaps | ✅ 0 gaps | See below |

**Code Files:**
- ./backend/analytics/signal_explainer.py
- ./backend/analytics/signals.py
- ./backend/api/routers/user.py
- ./backend/core/signal_validation.py
- ./venv/lib/python3.12/site-packages/anyio/_core/_signals.py

**Test Files:**
- ./venv/lib/python3.12/site-packages/numpy/testing/overrides.py
- ./venv/lib/python3.12/site-packages/_pytest/recwarn.py
- ./venv/lib/python3.12/site-packages/_pytest/python_api.py
- ./venv/lib/python3.12/site-packages/pytest_cov/plugin.py
- ./venv/lib/python3.12/site-packages/mypy/test/helpers.py

**Acceptance Criteria:**
- [ ] "OVERRIDE SIGNAL" endpoint: Ignores current signal, prevent trade execution
- [ ] "FORCE ENTRY" endpoint: Force trade even if signal <threshold (with warning)
- [ ] "FORCE EXIT" endpoint: Close specific position immediately
- [ ] Each override logged with reason (e.g., "Fed announcement", "Earnings", "Bad sentiment")
- [ ] User can adjust entry threshold +/- 5 points for rest of day
- [ ] Overrides reset at midnight (daily reset)

---

### FR-019: Real-Time Strategy Learning & Feedback

| Aspect | Status | Details |
|--------|--------|---------|
| Implementation | ✅ IMPLEMENTED | 5 file(s) found |
| Test Coverage | ✅ 0/0 PASSED | 5 test file(s) |
| Acceptance Criteria | ✅ 1 criteria | See below |
| Gaps | ✅ 0 gaps | See below |

**Code Files:**
- ./backend/api/routers/learning_feedback.py
- ./backend/analytics/strategy_analytics.py
- ./backend/strategies/garp_value_strategy.py
- ./venv/lib/python3.12/site-packages/scipy/optimize/_hessian_update_strategy.py
- ./backend/api/routers/learning_automation.py

**Test Files:**
- ./venv/lib/python3.12/site-packages/pandas/_testing/_hypothesis.py
- ./venv/lib/python3.12/site-packages/scipy/optimize/tests/test_hessian_update_strategy.py
- ./tests/unit/test_garp_strategy.py
- ./tests/test_strategy_analytics.py
- ./tests/test_strategy_analytics_api.py

**Acceptance Criteria:**
- [ ] **Daily Summary:** After market close, show:

---

### FR-020: Emergency Stop (Hard Kill Switch)

| Aspect | Status | Details |
|--------|--------|---------|
| Implementation | ✅ IMPLEMENTED | 5 file(s) found |
| Test Coverage | ✅ 0/0 PASSED | 5 test file(s) |
| Acceptance Criteria | ✅ 2 criteria | See below |
| Gaps | ✅ 0 gaps | See below |

**Code Files:**
- ./backend/core/emergency_stop.py
- ./backend/analytics/stop_loss.py
- ./backend/api/routers/emergency.py
- ./backend/skills_integration.py
- ./backend/core/stop_loss_safety.py

**Test Files:**
- ./tests/test_emergency_stop.py
- ./venv/lib/python3.12/site-packages/pytest_asyncio/plugin.py
- ./venv/lib/python3.12/site-packages/pytest_mock/plugin.py
- ./venv/lib/python3.12/site-packages/_pytest/hookspec.py
- ./venv/lib/python3.12/site-packages/_pytest/outcomes.py

**Acceptance Criteria:**
- [ ] "EMERGENCY STOP" endpoint: Immediate execution, no confirmation
- [ ] Action sequence (atomic, all-or-nothing):

---

## Non-Functional Requirements

### NFR-001: Signal Latency

| Aspect | Status | Details |
|--------|--------|---------|
| Implementation | ⚠️ PARTIAL | 5 file(s) found |
| Test Coverage | ⚠️ Tests found but not run | 5 test file(s) |
| Acceptance | ≥95% of signals <500ms | Signal generation must complete in <500ms per symbol |

**Requirement:** Signal generation must complete in <500ms per symbol

**Why:** Crypto moves fast (1-2% per minute); slow signals = missed trades

**Measurement:** Time from price update to buy/sell signal output

**Test:** Process 1,000 historical candles, measure p95/p99 latency

---

### NFR-002: Order Execution Speed

| Aspect | Status | Details |
|--------|--------|---------|
| Implementation | ⚠️ PARTIAL | 5 file(s) found |
| Test Coverage | ⚠️ Tests found but not run | 5 test file(s) |
| Acceptance | ≥95% of orders placed <2s | Order must be placed to Binance within 2 seconds of signal |

**Requirement:** Order must be placed to Binance within 2 seconds of signal

**Why:** Slippage increases with delay; market can gap

**Measurement:** Time from signal generation to Binance API response

**Test:** Place 10 market orders, measure p50/p95 latency

---

### NFR-003: Candle Fetch Latency

| Aspect | Status | Details |
|--------|--------|---------|
| Implementation | ⚠️ PARTIAL | 5 file(s) found |
| Test Coverage | ⚠️ Tests found but not run | 5 test file(s) |
| Acceptance | <2s for full batch, <100ms per symbol | Fetch latest candles from Binance in <2 seconds |

**Requirement:** Fetch latest candles from Binance in <2 seconds

**Why:** Real-time trading needs fresh data

**Measurement:** Time from request to receiving full OHLCV data

**Test:** Fetch 100 symbols × 4 timeframes = 400 candles in parallel

---

### NFR-004: Throughput

| Aspect | Status | Details |
|--------|--------|---------|
| Implementation | ⚠️ PARTIAL | 3 file(s) found |
| Test Coverage | ❌ NO TESTS | 0 test file(s) |
| Acceptance | ≥100 trades/day with <5% CPU utilization | Support ≥100 trades/day (crypto volatility is high) |

**Requirement:** Support ≥100 trades/day (crypto volatility is high)

**Why:** Need capacity for multiple strategies or scaled trading

**Measurement:** Trades processed per day without CPU/memory degradation

**Test:** Run strategy for 30 days, measure avg trades/day

---

### NFR-005: Memory Usage

| Aspect | Status | Details |
|--------|--------|---------|
| Implementation | ⚠️ PARTIAL | 5 file(s) found |
| Test Coverage | ⚠️ Tests found but not run | 5 test file(s) |
| Acceptance | Peak <500MB, no memory leaks over 7 days | Keep memory footprint <500MB during normal operation |

**Requirement:** Keep memory footprint <500MB during normal operation

**Why:** HA backup machine may have limited resources

**Measurement:** Peak memory during 24h trading window

**Test:** Monitor memory for 24h, capture peak usage

---

### NFR-006: Availability (HA)

| Aspect | Status | Details |
|--------|--------|---------|
| Implementation | ⚠️ PARTIAL | 5 file(s) found |
| Test Coverage | ⚠️ Tests found but not run | 2 test file(s) |
| Acceptance | ≥99.5% without manual intervention | 99.5% uptime (≤3.6h downtime/month) |

**Requirement:** 99.5% uptime (≤3.6h downtime/month)

**Why:** Crypto markets 24/7; downtime = missed trades = lost profit

**Measurement:** (Total time - downtime) / total time

**Test:** Run for 30 days, monitor both machines for crashes

---

### NFR-007: Data Consistency (No Duplicate Trades)

| Aspect | Status | Details |
|--------|--------|---------|
| Implementation | ⚠️ PARTIAL | 5 file(s) found |
| Test Coverage | ⚠️ Tests found but not run | 5 test file(s) |
| Acceptance | 0 duplicate trades in 30-day test run | No duplicate orders even during failover |

**Requirement:** No duplicate orders even during failover

**Why:** Dual machines could both execute same signal if not careful

**Measurement:** Audit trail shows no identical (symbol, time, qty, side) pairs

**Test:** Force failover during trade execution, verify only 1 order created

---

### NFR-008: Recovery Time Objective (RTO)

| Aspect | Status | Details |
|--------|--------|---------|
| Implementation | ⚠️ PARTIAL | 5 file(s) found |
| Test Coverage | ⚠️ Tests found but not run | 5 test file(s) |
| Acceptance | ≤30s RTO, measured 5 times, avg <25s | Backup machine must take over within 30 seconds |

**Requirement:** Backup machine must take over within 30 seconds

**Why:** Crypto can move 1-2% in 30s; longer = lost opportunity/loss

**Measurement:** Time from main machine failure to first backup trade

**Test:** Kill main machine process, measure time to backup executing signals

---

### NFR-009: Recovery Point Objective (RPO)

| Aspect | Status | Details |
|--------|--------|---------|
| Implementation | ⚠️ PARTIAL | 5 file(s) found |
| Test Coverage | ⚠️ Tests found but not run | 5 test file(s) |
| Acceptance | ≤1 trade lost, impact <€10 | Lose ≤1 trade on failover (≤€10 in lost opportunity) |

**Requirement:** Lose ≤1 trade on failover (≤€10 in lost opportunity)

**Why:** Perfect sync is impossible; accept small loss during handover

**Measurement:** Trades executed by main but not backup in final 2 seconds

**Test:** Analyze logs during forced failover

---

### NFR-010: Platform-Wide Data Consistency

| Aspect | Status | Details |
|--------|--------|---------|
| Implementation | ⚠️ PARTIAL | 5 file(s) found |
| Test Coverage | ⚠️ Tests found but not run | 5 test file(s) |
| Acceptance |  | In-memory state MUST sync permanently with SQLite database |

**Requirement:** In-memory state MUST sync permanently with SQLite database

**Why:** API crashes/restarts would lose account state (cash, P&L) without this

---

### NFR-011: API Key Protection

| Aspect | Status | Details |
|--------|--------|---------|
| Implementation | ⚠️ PARTIAL | 5 file(s) found |
| Test Coverage | ⚠️ Tests found but not run | 5 test file(s) |
| Acceptance | 0 keys found in codebase, all in environment variables | Binance API keys never stored in code, logs, or version control |

**Requirement:** Binance API keys never stored in code, logs, or version control

**Why:** Stolen keys = complete account compromise

**Measurement:** Audit code + logs + git history for plaintext keys

**Test:** `grep -r "BINANCE.*KEY\|api.*key" --include="*.py" --include="*.txt"`

---

### NFR-012: Input Validation

| Aspect | Status | Details |
|--------|--------|---------|
| Implementation | ⚠️ PARTIAL | 5 file(s) found |
| Test Coverage | ⚠️ Tests found but not run | 5 test file(s) |
| Acceptance | All inputs validated, clear error messages | All user inputs validated (strategy parameters, order quantities) |

**Requirement:** All user inputs validated (strategy parameters, order quantities)

**Why:** Bad inputs could cause loss or security issues

**Test:** Unit tests for 50+ invalid inputs

---

### NFR-013: Audit Trail Immutability

| Aspect | Status | Details |
|--------|--------|---------|
| Implementation | ⚠️ PARTIAL | 5 file(s) found |
| Test Coverage | ⚠️ Tests found but not run | 5 test file(s) |
| Acceptance | 100% of trades logged, audit trail integrity verified | Trade audit trail is append-only, never deleted or modified |

**Requirement:** Trade audit trail is append-only, never deleted or modified

**Why:** Regulatory requirement for live trading, forensics on losses

**Measurement:** Audit trail file has no overwrites, only appends

**Test:** Verify file only grows, verify all trades logged

---

### NFR-014: Structured Logging

| Aspect | Status | Details |
|--------|--------|---------|
| Implementation | ⚠️ PARTIAL | 5 file(s) found |
| Test Coverage | ⚠️ Tests found but not run | 5 test file(s) |
| Acceptance | 100% of events loggable as JSON, <5KB per trade | All events logged as JSON (timestamp, level, event, context) |

**Requirement:** All events logged as JSON (timestamp, level, event, context)

**Why:** Easy parsing for monitoring, alerting, debugging

**Test:** Parse logs into JSON, verify all events captured

---

### NFR-015: Code Organization

| Aspect | Status | Details |
|--------|--------|---------|
| Implementation | ⚠️ PARTIAL | 5 file(s) found |
| Test Coverage | ⚠️ Tests found but not run | 5 test file(s) |
| Acceptance | No file >500 lines, <3 dependencies per module | Single-responsibility modules, max 500 lines per file |

**Requirement:** Single-responsibility modules, max 500 lines per file

**Why:** Crypto market moves fast; bugs must be found and fixed quickly

**Test:** Measure file sizes, check module coupling

---

### NFR-016: Type Hints & Linting

| Aspect | Status | Details |
|--------|--------|---------|
| Implementation | ⚠️ PARTIAL | 5 file(s) found |
| Test Coverage | ⚠️ Tests found but not run | 5 test file(s) |
| Acceptance | All checks pass, 0 warnings | 100% type hints, mypy 0 errors, black formatted |

**Requirement:** 100% type hints, mypy 0 errors, black formatted

**Why:** Catches bugs at dev time, not production

**Test:** `mypy . && black --check . && ruff check .`

---

### NFR-017: Code Quality Excellence (Lifetime Commitment)

| Aspect | Status | Details |
|--------|--------|---------|
| Implementation | ⚠️ PARTIAL | 5 file(s) found |
| Test Coverage | ⚠️ Tests found but not run | 5 test file(s) |
| Acceptance | Code passes ALL quality gates before merge | Code quality must be maintained at highest standards throughout entire project lifetime |

**Requirement:** Code quality must be maintained at highest standards throughout entire project lifetime

**Why:** Technical debt spirals; high quality prevents bugs, reduces maintenance cost, enables rapid iteration

---

### NFR-018: Implementation Testing (No Claims Without Tests)

| Aspect | Status | Details |
|--------|--------|---------|
| Implementation | ⚠️ PARTIAL | 5 file(s) found |
| Test Coverage | ⚠️ Tests found but not run | 5 test file(s) |
| Acceptance | Zero "false positives" (claimed features that don't work) | EVERY code change must have passing tests BEFORE claiming success |

**Requirement:** EVERY code change must have passing tests BEFORE claiming success

**Why:** Prevents false claims (e.g., "realized_pnl is persisted" when it wasn't)

**Test:** Every commit must have associated tests in CI/CD

---

### NFR-019: Test Coverage

| Aspect | Status | Details |
|--------|--------|---------|
| Implementation | ⚠️ PARTIAL | 5 file(s) found |
| Test Coverage | ⚠️ Tests found but not run | 5 test file(s) |
| Acceptance | ≥85% coverage, <50 lines uncovered in critical modules | ≥85% test coverage for critical paths |

**Requirement:** ≥85% test coverage for critical paths

**Test:** `coverage run -m pytest && coverage report`

---

### NFR-020: Documentation

| Aspect | Status | Details |
|--------|--------|---------|
| Implementation | ⚠️ PARTIAL | 5 file(s) found |
| Test Coverage | ⚠️ Tests found but not run | 5 test file(s) |
| Acceptance | Docs explain 5W (what, why, when, who, how) for each feature | Every strategy and API endpoint documented with examples |

**Requirement:** Every strategy and API endpoint documented with examples

**Why:** Easy onboarding, understand why trades happened

**Test:** New user can run strategy without asking questions

---

### NFR-021: Operational Cost Coverage

| Aspect | Status | Details |
|--------|--------|---------|
| Implementation | ⚠️ PARTIAL | 5 file(s) found |
| Test Coverage | ⚠️ Tests found but not run | 5 test file(s) |
| Acceptance | Paper trading shows +€30+ profit for 10 days | Strategy must be profitable enough to cover costs with 2x safety margin |

**Requirement:** Strategy must be profitable enough to cover costs with 2x safety margin

**Why:** Otherwise, even if strategy works, losses to fees eat profit

**Test:** 10-day paper test must show avg +€3/day profit

---

### NFR-022: Asset Expansion

| Aspect | Status | Details |
|--------|--------|---------|
| Implementation | ⚠️ PARTIAL | 5 file(s) found |
| Test Coverage | ⚠️ Tests found but not run | 5 test file(s) |
| Acceptance | Can add pair in <5 minutes, no code changes | Support adding new trading pairs without code changes |

**Requirement:** Support adding new trading pairs without code changes

**Why:** Want to trade BTCUSDT, ETHUSDT, DOGEUSDT, etc.

**Test:** Add 5 new pairs, verify all trade correctly

---

### NFR-023: Strategy Expansion

| Aspect | Status | Details |
|--------|--------|---------|
| Implementation | ⚠️ PARTIAL | 5 file(s) found |
| Test Coverage | ⚠️ Tests found but not run | 5 test file(s) |
| Acceptance | Can plug in new strategy, all existing tests pass | Support adding new strategies without modifying core system |

**Requirement:** Support adding new strategies without modifying core system

**Why:** Want to test momentum, mean reversion, grid trading, etc.

**Test:** Add 2 new strategies in <30 minutes

---

### NFR-024: Zero-Downtime Deployment

| Aspect | Status | Details |
|--------|--------|---------|
| Implementation | ⚠️ PARTIAL | 2 file(s) found |
| Test Coverage | ❌ NO TESTS | 0 test file(s) |
| Acceptance | Code updated, 0 trades lost, <5s pause in execution | Deploy code updates without stopping trading |

**Requirement:** Deploy code updates without stopping trading

**Why:** Crypto markets 24/7; downtime = missed trades

**Test:** Deploy during trading hours, verify no orders missed

---

### NFR-025: Configuration Management

| Aspect | Status | Details |
|--------|--------|---------|
| Implementation | ⚠️ PARTIAL | 5 file(s) found |
| Test Coverage | ⚠️ Tests found but not run | 5 test file(s) |
| Acceptance | Code works with 0 hardcoded values | All settings via environment variables (no hardcoding) |

**Requirement:** All settings via environment variables (no hardcoding)

**Why:** Same code runs on dev, testnet, mainnet with different configs

**Test:** Verify each var controls behavior correctly

---

### NFR-026: Paper Trading Acceptance

| Aspect | Status | Details |
|--------|--------|---------|
| Implementation | ⚠️ PARTIAL | 5 file(s) found |
| Test Coverage | ⚠️ Tests found but not run | 5 test file(s) |
| Acceptance |  | Pass 10-day paper trading run with >55% win rate and positive P&L |

**Requirement:** Pass 10-day paper trading run with >55% win rate and positive P&L

---

### NFR-027: Live Trading Acceptance

| Aspect | Status | Details |
|--------|--------|---------|
| Implementation | ⚠️ PARTIAL | 5 file(s) found |
| Test Coverage | ⚠️ Tests found but not run | 5 test file(s) |
| Acceptance | Both machines have identical `.env` + `trading_config.json` after startup | After git pull or .env file change, both machines must manually sync |

**Requirement:** After git pull or .env file change, both machines must manually sync

---
