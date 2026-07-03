# Crypto-DayTrading API Contract

**Generated:** 2026-07-03 09:48:42 UTC

**Version:** 1.0.0

**Status:** Complete

**Total Endpoints:** 197

**Categories:** 19


## Executive Summary


The Crypto-DayTrading platform provides a comprehensive REST API for autonomous trading, 
portfolio management, risk monitoring, and high-availability operations. 
This contract documents all 197 endpoints across 19 functional categories.


## API Overview


### Connection Information

- **Base URL:** `http://localhost:8000`

- **Protocol:** HTTP/1.1 REST with JSON

- **Default Port:** 8000

- **Authentication:** None (local deployment)

- **Rate Limit:** 100 requests/minute

- **Content-Type:** `application/json`

- **Character Encoding:** UTF-8


### Response Format

All responses are JSON:


```json
{
  "status": "success",
  "data": {},
  "timestamp": "2026-07-03T17:30:00Z"
}
```


## Quick Reference


### Endpoint Summary by Category


| Category | Count | Examples |

|----------|-------|----------|

| Autonomous Trading Control | 8 | /api/autonomous/status, /api/autonomous/start... |

| Configuration Management | 1 | /config... |

| Dashboard Integration | 5 | /api/dashboard, /dashboard/summary... |

| General API | 108 | /favicon.ico, /... |

| High Availability & Failover | 8 | /api/ha/heartbeat, /api/ha/heartbeat-status... |

| Market Regime Detection | 1 | /regime-profile/{regime}... |

| Monitoring & Health Checks | 19 | /api/health, /health/production-readiness... |

| Portfolio Allocation & Optimization | 7 | /current-allocation, /allocation... |

| Portfolio Analysis | 3 | /portfolio-drift, /portfolio-var... |

| PostgreSQL HA | 2 | /pg-lag, /pg-status... |

| Rebalancing | 1 | /optimization/rebalancing-plan... |

| Recommendations & Scenarios | 3 | /recommendations, /recommendations/record... |

| Redundancy Management | 4 | /api/failover/sync-position, /api/failover/receive-position... |

| Risk Management | 6 | /risk-return-profile, /risk-metrics... |

| System Metrics | 4 | /metrics, /metrics... |

| Tax Management | 1 | /tax-summary... |

| Trading Account Management | 6 | /api/paper/account, /api/paper/positions... |

| Trading Control | 6 | /pause, /resume... |

| User Management | 4 | /profile, /settings... |



## Table of Contents


- [Autonomous Trading Control](#autonomous-trading-control) (8)

- [Configuration Management](#configuration-management) (1)

- [Dashboard Integration](#dashboard-integration) (5)

- [General API](#general-api) (108)

- [High Availability & Failover](#high-availability-and-failover) (8)

- [Market Regime Detection](#market-regime-detection) (1)

- [Monitoring & Health Checks](#monitoring-and-health-checks) (19)

- [Portfolio Allocation & Optimization](#portfolio-allocation-and-optimization) (7)

- [Portfolio Analysis](#portfolio-analysis) (3)

- [PostgreSQL HA](#postgresql-ha) (2)

- [Rebalancing](#rebalancing) (1)

- [Recommendations & Scenarios](#recommendations-and-scenarios) (3)

- [Redundancy Management](#redundancy-management) (4)

- [Risk Management](#risk-management) (6)

- [System Metrics](#system-metrics) (4)

- [Tax Management](#tax-management) (1)

- [Trading Account Management](#trading-account-management) (6)

- [Trading Control](#trading-control) (6)

- [User Management](#user-management) (4)



## HTTP Status Codes


| Code | Name | Meaning |

|------|------|----------|

| 200 | OK | Request successful |

| 201 | Created | Resource created |

| 204 | No Content | Success, no body |

| 400 | Bad Request | Invalid parameters |

| 401 | Unauthorized | Auth required |

| 403 | Forbidden | Access denied |

| 404 | Not Found | Resource missing |

| 429 | Too Many Requests | Rate limit |

| 500 | Server Error | Internal error |

| 503 | Service Unavailable | Service down |


## Autonomous Trading Control


**Total Endpoints:** 8


| Method | Endpoint | Description |

|--------|----------|-------------|

| `GET` | `/api/autonomous/config` | N/A |

| `GET` | `/api/autonomous/status` | N/A |

| `GET` | `/api/autonomous/trades` | N/A |

| `POST` | `/api/autonomous/config/sync` | N/A |

| `POST` | `/api/autonomous/config/update` | N/A |

| `POST` | `/api/autonomous/positions/close` | N/A |

| `POST` | `/api/autonomous/start` | N/A |

| `POST` | `/api/autonomous/stop` | N/A |



### GET `/api/autonomous/config`


**Implementation:** `routers/autonomous.py` (get_trading_config)


---


### GET `/api/autonomous/status`


**Implementation:** `routers/autonomous.py` (get_autonomous_status)


---


### GET `/api/autonomous/trades`


**Implementation:** `routers/autonomous.py` (get_trade_history)


---


### POST `/api/autonomous/config/sync`


**Implementation:** `routers/autonomous.py` (sync_config_from_backup)


---


### POST `/api/autonomous/config/update`


**Implementation:** `routers/autonomous.py` (update_trading_config)


---


### POST `/api/autonomous/positions/close`


**Implementation:** `routers/autonomous.py` (close_position)


---


### POST `/api/autonomous/start`


**Implementation:** `routers/autonomous.py` (start_autonomous_trading)


---


### POST `/api/autonomous/stop`


**Implementation:** `routers/autonomous.py` (stop_autonomous_trading)


---


## Configuration Management


**Total Endpoints:** 1


| Method | Endpoint | Description |

|--------|----------|-------------|

| `GET` | `/config` | N/A |



### GET `/config`


**Implementation:** `routers/redundancy.py` (get_redundancy_config)


---


## Dashboard Integration


**Total Endpoints:** 5


| Method | Endpoint | Description |

|--------|----------|-------------|

| `GET` | `/api/dashboard` | N/A |

| `GET` | `/dashboard/accuracy-metrics` | N/A |

| `GET` | `/dashboard/cost-calibration` | N/A |

| `GET` | `/dashboard/scenario-heatmap` | N/A |

| `GET` | `/dashboard/summary` | N/A |



### GET `/api/dashboard`


**Implementation:** `routers/dashboard_integration.py` (get_dashboard)


---


### GET `/dashboard/accuracy-metrics`


**Implementation:** `routers/learning_automation.py` (get_dashboard_accuracy_metrics)


---


### GET `/dashboard/cost-calibration`


**Implementation:** `routers/learning_automation.py` (get_dashboard_cost_calibration)


---


### GET `/dashboard/scenario-heatmap`


**Implementation:** `routers/learning_automation.py` (get_dashboard_scenario_heatmap)


---


### GET `/dashboard/summary`


**Implementation:** `routers/risk_metrics.py` (get_risk_dashboard_summary)


---


## General API


**Total Endpoints:** 108


| Method | Endpoint | Description |

|--------|----------|-------------|

| `GET` | `/` | return {"status": "Crypto daytrading platform online ✅"} |

| `GET` | `/api/immutable-log/status` | N/A |

| `GET` | `/api/signals/calculate` | N/A |

| `GET` | `/assets` | N/A |

| `GET` | `/assets/by-class/{asset_class}` | N/A |

| `GET` | `/assets/by-region/{region}` | N/A |

| `GET` | `/assets/{symbol}` | N/A |

| `GET` | `/circuit-breaker/stats` | N/A |

| `GET` | `/cleanup/status` | N/A |

| `GET` | `/costs/calibration-status` | N/A |

| `GET` | `/costs/learned-estimates` | N/A |

| `GET` | `/costs/symbol-profiles` | N/A |

| `GET` | `/currency/exposure` | N/A |

| `GET` | `/currency/hedge-suggestions` | N/A |

| `GET` | `/daemon/last-run` | Get last daemon run timestamp and status. |

| `GET` | `/daily-report` | Get comprehensive daily portfolio report |

| `GET` | `/detect` | N/A |

| `GET` | `/diversification` | N/A |

| `GET` | `/efficient-frontier` | N/A |

| `GET` | `/events` | monitor = get_redundancy_monitor() |

| `GET` | `/export/{format}` | N/A |

| `GET` | `/favicon.ico` | N/A |

| `GET` | `/feedback/calibration-report` | N/A |

| `GET` | `/history` | N/A |

| `GET` | `/history` | monitor = get_redundancy_monitor() |

| `GET` | `/liability` | N/A |

| `GET` | `/limits` | N/A |

| `GET` | `/optimization/efficient-frontier` | N/A |

| `GET` | `/optimization/optimal-portfolio` | N/A |

| `GET` | `/optimize` | N/A |

| `GET` | `/parameters` | N/A |

| `GET` | `/performance/summary` | N/A |

| `GET` | `/pnl` | N/A |

| `GET` | `/prices` | N/A |

| `GET` | `/recommended-rebalancing` | N/A |

| `GET` | `/replication-lag` | N/A |

| `GET` | `/report` | N/A |

| `GET` | `/results/{result_id}` | N/A |

| `GET` | `/scenarios/performance` | N/A |

| `GET` | `/scenarios/weights` | N/A |

| `GET` | `/scheduler/history` | N/A |

| `GET` | `/scheduler/status` | N/A |

| `GET` | `/signal-quality` | Analyze signal quality by entry signal type |

| `GET` | `/status` | Get backup status: Running in analytics mode or active tradi |

| `GET` | `/status` | monitor = get_redundancy_monitor() |

| `GET` | `/status` | N/A |

| `GET` | `/status` | Get current emergency system status. |

| `GET` | `/status` | N/A |

| `GET` | `/strategies/all-stats` | N/A |

| `GET` | `/strategy-impact` | N/A |

| `GET` | `/stress-tests` | N/A |

| `GET` | `/stress-tests/{scenario}` | N/A |

| `GET` | `/summary` | N/A |

| `GET` | `/summary` | Get summary of all backtests. |

| `GET` | `/summary` | N/A |

| `GET` | `/summary` | N/A |

| `GET` | `/supported-stocks` | N/A |

| `GET` | `/sync-from-paper-trading` | N/A |

| `GET` | `/transactions` | N/A |

| `GET` | `/uptime` | N/A |

| `POST` | `/add-expense` | N/A |

| `POST` | `/add-trade` | N/A |

| `POST` | `/admin/circuit-breaker/reset` | N/A |

| `POST` | `/analyze` | N/A |

| `POST` | `/analyze-drift` | N/A |

| `POST` | `/analyze-exit` | N/A |

| `POST` | `/break-into-tranches` | N/A |

| `POST` | `/breakeven-hold-period` | N/A |

| `POST` | `/buy` | N/A |

| `POST` | `/cleanup/execute-rebalancing` | N/A |

| `POST` | `/close-all` | N/A |

| `POST` | `/compare` | N/A |

| `POST` | `/constraints/add-concentration-limit` | N/A |

| `POST` | `/constraints/add-sector-limit` | N/A |

| `POST` | `/constraints/validate` | N/A |

| `POST` | `/costs/estimate` | N/A |

| `POST` | `/costs/estimate-portfolio` | N/A |

| `POST` | `/costs/record-execution` | N/A |

| `POST` | `/daemon/sync-recommendations` | N/A |

| `POST` | `/detect` | N/A |

| `POST` | `/drift-analysis` | N/A |

| `POST` | `/factor-attribution` | N/A |

| `POST` | `/feedback/recalibrate` | Trigger model recalibration based on feedback. |

| `POST` | `/generate-plan` | N/A |

| `POST` | `/initialize` | N/A |

| `POST` | `/initialize` | N/A |

| `POST` | `/limits/update` | N/A |

| `POST` | `/outcomes/record` | N/A |

| `POST` | `/performance/record-outcome` | N/A |

| `POST` | `/performance/record-recommendation` | N/A |

| `POST` | `/position-check/{symbol}` | N/A |

| `POST` | `/position-contribution` | N/A |

| `POST` | `/preset` | N/A |

| `POST` | `/reload` | N/A |

| `POST` | `/reset` | N/A |

| `POST` | `/rolling-optimization` | N/A |

| `POST` | `/save` | N/A |

| `POST` | `/scenario-analysis` | N/A |

| `POST` | `/scenario/list` | N/A |

| `POST` | `/scenario/predefined` | N/A |

| `POST` | `/scenarios/learn` | N/A |

| `POST` | `/scheduler/reweight-scenarios` | N/A |

| `POST` | `/sell` | N/A |

| `POST` | `/set-crash-threshold` | Configure crash detection threshold. |

| `POST` | `/stop` | N/A |

| `POST` | `/strategy-impact` | N/A |

| `POST` | `/stress-test` | N/A |

| `POST` | `/trigger-analysis` | Trigger complete analysis suite |



### GET `/`


**Summary:** return {"status": "Crypto daytrading platform online ✅"}


**Implementation:** `main.py` (root)


---


### GET `/api/immutable-log/status`


**Implementation:** `routers/autonomous.py` (get_immutable_log_status)


---


### GET `/api/signals/calculate`


**Implementation:** `routers/autonomous.py` (calculate_signal)


---


### GET `/assets`


**Implementation:** `routers/multi_asset.py` (list_all_assets)


---


### GET `/assets/by-class/{asset_class}`


**Implementation:** `routers/multi_asset.py` (list_assets_by_class)


---


### GET `/assets/by-region/{region}`


**Implementation:** `routers/multi_asset.py` (list_assets_by_region)


---


### GET `/assets/{symbol}`


**Implementation:** `routers/multi_asset.py` (get_asset)


---


### GET `/circuit-breaker/stats`


**Implementation:** `routers/monitoring.py` (get_circuit_breaker_stats)


---


### GET `/cleanup/status`


**Implementation:** `routers/production_hardening.py` (get_cleanup_status)


---


### GET `/costs/calibration-status`


**Implementation:** `routers/learning_feedback.py` (get_cost_calibration_status)


---


### GET `/costs/learned-estimates`


**Implementation:** `routers/learning_automation.py` (get_learned_cost_estimates)


---


### GET `/costs/symbol-profiles`


**Implementation:** `routers/learning_feedback.py` (get_symbol_cost_profiles)


---


### GET `/currency/exposure`


**Implementation:** `routers/multi_asset.py` (get_currency_exposure)


---


### GET `/currency/hedge-suggestions`


**Implementation:** `routers/multi_asset.py` (get_hedge_suggestions)


---


### GET `/daemon/last-run`


**Summary:** Get last daemon run timestamp and status.


**Implementation:** `routers/learning_automation.py` (get_daemon_last_run)


---


### GET `/daily-report`


**Summary:** Get comprehensive daily portfolio report


**Implementation:** `routers/backup_analytics.py` (get_daily_report)


---


### GET `/detect`


**Implementation:** `routers/regime.py` (detect_market_regime_router)


---


### GET `/diversification`


**Implementation:** `routers/portfolio.py` (get_portfolio_diversification)


---


### GET `/efficient-frontier`


**Implementation:** `routers/portfolio_allocation.py` (get_efficient_frontier)


---


### GET `/events`


**Summary:** monitor = get_redundancy_monitor()


**Implementation:** `routers/redundancy.py` (get_failover_events)


---


### GET `/export/{format}`


**Implementation:** `routers/tax.py` (export_tax_data)


---


### GET `/favicon.ico`


**Implementation:** `main.py` (favicon)


---


### GET `/feedback/calibration-report`


**Implementation:** `routers/production_hardening.py` (get_calibration_report)


---


### GET `/history`


**Implementation:** `routers/rebalancing.py` (get_rebalancing_history)


---


### GET `/history`


**Summary:** monitor = get_redundancy_monitor()


**Implementation:** `routers/redundancy.py` (get_health_check_history)


---


### GET `/liability`


**Implementation:** `routers/tax.py` (get_tax_liability)


---


### GET `/limits`


**Implementation:** `routers/risk_management.py` (get_risk_limits)


---


### GET `/optimization/efficient-frontier`


**Implementation:** `routers/multi_asset.py` (get_efficient_frontier)


---


### GET `/optimization/optimal-portfolio`


**Implementation:** `routers/multi_asset.py` (get_optimal_portfolio)


---


### GET `/optimize`


**Implementation:** `routers/portfolio_allocation.py` (get_optimal_allocation)


---


### GET `/parameters`


**Implementation:** `routers/config.py` (get_parameters)


---


### GET `/performance/summary`


**Implementation:** `routers/recommendation_advanced.py` (get_performance_summary)


---


### GET `/pnl`


**Implementation:** `routers/backup_analytics.py` (get_daily_pnl)


---


### GET `/prices`


**Implementation:** `routers/dashboard_wrapper.py` (get_prices)


---


### GET `/recommended-rebalancing`


**Implementation:** `routers/portfolio_allocation.py` (get_recommended_rebalancing)


---


### GET `/replication-lag`


**Implementation:** `routers/redundancy.py` (get_replication_lag)


---


### GET `/report`


**Implementation:** `routers/tax.py` (get_tax_report)


---


### GET `/results/{result_id}`


**Implementation:** `routers/backtest_allocation.py` (get_backtest_results)


---


### GET `/scenarios/performance`


**Implementation:** `routers/learning_feedback.py` (get_scenario_performance)


---


### GET `/scenarios/weights`


**Implementation:** `routers/learning_feedback.py` (get_scenario_weights)


---


### GET `/scheduler/history`


**Implementation:** `routers/learning_automation.py` (get_reweighting_history)


---


### GET `/scheduler/status`


**Implementation:** `routers/learning_automation.py` (get_scheduler_status)


---


### GET `/signal-quality`


**Summary:** Analyze signal quality by entry signal type


**Implementation:** `routers/backup_analytics.py` (get_signal_quality)


---


### GET `/status`


**Summary:** Get backup status: Running in analytics mode or active trading


**Implementation:** `routers/backup_analytics.py` (get_backup_status)


---


### GET `/status`


**Summary:** monitor = get_redundancy_monitor()


**Implementation:** `routers/redundancy.py` (get_redundancy_status)


---


### GET `/status`


**Implementation:** `routers/monitoring.py` (get_system_status)


---


### GET `/status`


**Summary:** Get current emergency system status.


**Implementation:** `routers/emergency.py` (get_emergency_status)


---


### GET `/status`


**Implementation:** `routers/risk_management.py` (get_risk_status)


---


### GET `/strategies/all-stats`


**Implementation:** `routers/dashboard_wrapper.py` (get_strategies_stats)


---


### GET `/strategy-impact`


**Implementation:** `routers/regime.py` (get_strategy_impact)


---


### GET `/stress-tests`


**Implementation:** `routers/risk_metrics.py` (get_stress_test_results)


---


### GET `/stress-tests/{scenario}`


**Implementation:** `routers/risk_metrics.py` (get_single_stress_test)


---


### GET `/summary`


**Implementation:** `routers/attribution.py` (get_attribution_summary)


---


### GET `/summary`


**Summary:** Get summary of all backtests.


**Implementation:** `routers/backtest_allocation.py` (get_backtest_summary)


---


### GET `/summary`


**Implementation:** `routers/tax.py` (get_tax_summary)


---


### GET `/summary`


**Implementation:** `routers/portfolio.py` (get_portfolio_summary)


---


### GET `/supported-stocks`


**Implementation:** `routers/stocks.py` (get_supported_stocks)


---


### GET `/sync-from-paper-trading`


**Implementation:** `routers/tax.py` (sync_from_paper_trading)


---


### GET `/transactions`


**Implementation:** `main.py` (get_transactions_page)


---


### GET `/uptime`


**Implementation:** `routers/redundancy.py` (get_uptime)


---


### POST `/add-expense`


**Implementation:** `routers/tax.py` (add_deductible_expense)


---


### POST `/add-trade`


**Implementation:** `routers/tax.py` (add_trade)


---


### POST `/admin/circuit-breaker/reset`


**Implementation:** `routers/monitoring.py` (reset_circuit_breaker)


---


### POST `/analyze`


**Implementation:** `routers/backtest_allocation.py` (analyze_results)


---


### POST `/analyze-drift`


**Implementation:** `routers/rebalancing.py` (analyze_drift)


---


### POST `/analyze-exit`


**Implementation:** `routers/stocks.py` (analyze_exit)


---


### POST `/break-into-tranches`


**Implementation:** `routers/rebalancing.py` (break_into_tranches)


---


### POST `/breakeven-hold-period`


**Implementation:** `routers/stocks.py` (calculate_breakeven)


---


### POST `/buy`


**Implementation:** `routers/stocks.py` (buy_stock)


---


### POST `/cleanup/execute-rebalancing`


**Implementation:** `routers/production_hardening.py` (execute_rebalancing_cleanup)


---


### POST `/close-all`


**Implementation:** `routers/emergency.py` (close_all_positions)


---


### POST `/compare`


**Implementation:** `routers/backtest_allocation.py` (compare_allocations)


---


### POST `/constraints/add-concentration-limit`


**Implementation:** `routers/recommendation_advanced.py` (add_concentration_limit)


---


### POST `/constraints/add-sector-limit`


**Implementation:** `routers/recommendation_advanced.py` (add_sector_limit)


---


### POST `/constraints/validate`


**Implementation:** `routers/recommendation_advanced.py` (validate_allocation)


---


### POST `/costs/estimate`


**Implementation:** `routers/production_hardening.py` (estimate_execution_costs)


---


### POST `/costs/estimate-portfolio`


**Implementation:** `routers/learning_feedback.py` (estimate_portfolio_costs)


---


### POST `/costs/record-execution`


**Implementation:** `routers/learning_feedback.py` (record_execution)


---


### POST `/daemon/sync-recommendations`


**Implementation:** `routers/learning_automation.py` (sync_recommendations_to_outcomes)


---


### POST `/detect`


**Implementation:** `routers/regime.py` (detect_market_regime_router)


---


### POST `/drift-analysis`


**Implementation:** `routers/attribution.py` (analyze_drift)


---


### POST `/factor-attribution`


**Implementation:** `routers/attribution.py` (analyze_factor_attribution)


---


### POST `/feedback/recalibrate`


**Summary:** Trigger model recalibration based on feedback.


**Implementation:** `routers/production_hardening.py` (recalibrate_models)


---


### POST `/generate-plan`


**Implementation:** `routers/rebalancing.py` (generate_rebalancing_plan)


---


### POST `/initialize`


**Implementation:** `routers/stocks.py` (initialize_stock_trading)


---


### POST `/initialize`


**Implementation:** `routers/tax.py` (initialize_tax_tracking)


---


### POST `/limits/update`


**Implementation:** `routers/risk_management.py` (update_risk_limits)


---


### POST `/outcomes/record`


**Implementation:** `routers/learning_feedback.py` (record_outcome)


---


### POST `/performance/record-outcome`


**Implementation:** `routers/recommendation_advanced.py` (record_outcome)


---


### POST `/performance/record-recommendation`


**Implementation:** `routers/recommendation_advanced.py` (record_recommendation)


---


### POST `/position-check/{symbol}`


**Implementation:** `routers/risk_management.py` (check_position_risk)


---


### POST `/position-contribution`


**Implementation:** `routers/attribution.py` (analyze_position_contribution)


---


### POST `/preset`


**Implementation:** `routers/allocation_management.py` (load_preset)


---


### POST `/reload`


**Implementation:** `routers/config.py` (reload_config)


---


### POST `/reset`


**Implementation:** `routers/emergency.py` (reset_emergency_system)


---


### POST `/rolling-optimization`


**Implementation:** `routers/backtest_allocation.py` (backtest_rolling_optimization)


---


### POST `/save`


**Implementation:** `routers/allocation_management.py` (save_allocation)


---


### POST `/scenario-analysis`


**Implementation:** `routers/recommendation.py` (scenario_analysis)


---


### POST `/scenario/list`


**Implementation:** `routers/recommendation_advanced.py` (list_scenarios)


---


### POST `/scenario/predefined`


**Implementation:** `routers/recommendation_advanced.py` (analyze_predefined_scenario)


---


### POST `/scenarios/learn`


**Implementation:** `routers/learning_feedback.py` (learn_scenario_weights)


---


### POST `/scheduler/reweight-scenarios`


**Implementation:** `routers/learning_automation.py` (trigger_scenario_reweighting)


---


### POST `/sell`


**Implementation:** `routers/stocks.py` (sell_stock)


---


### POST `/set-crash-threshold`


**Summary:** Configure crash detection threshold.


**Implementation:** `routers/emergency.py` (configure_crash_threshold)


---


### POST `/stop`


**Implementation:** `routers/emergency.py` (emergency_stop)


---


### POST `/strategy-impact`


**Implementation:** `routers/regime.py` (get_strategy_impact)


---


### POST `/stress-test`


**Implementation:** `routers/rebalancing.py` (stress_test_rebalancing)


---


### POST `/trigger-analysis`


**Summary:** Trigger complete analysis suite


**Implementation:** `routers/backup_analytics.py` (trigger_full_analysis)


---


## High Availability & Failover


**Total Endpoints:** 8


| Method | Endpoint | Description |

|--------|----------|-------------|

| `GET` | `/api/ha/heartbeat-status` | N/A |

| `GET` | `/api/ha/split-brain-status` | N/A |

| `GET` | `/api/ha/status` | N/A |

| `GET` | `/ha/explicit-heartbeat/stats` | N/A |

| `POST` | `/api/ha/heartbeat` | N/A |

| `POST` | `/api/ha/sync-from-backup` | N/A |

| `POST` | `/api/ha/sync-from-primary` | N/A |

| `POST` | `/ha/explicit-heartbeat` | N/A |



### GET `/api/ha/heartbeat-status`


**Implementation:** `main.py` (get_heartbeat_status)


---


### GET `/api/ha/split-brain-status`


**Implementation:** `main.py` (get_split_brain_status)


---


### GET `/api/ha/status`


**Implementation:** `main.py` (get_ha_status)


---


### GET `/ha/explicit-heartbeat/stats`


**Implementation:** `routers/monitoring.py` (get_explicit_heartbeat_stats)


---


### POST `/api/ha/heartbeat`


**Implementation:** `main.py` (receive_heartbeat)


---


### POST `/api/ha/sync-from-backup`


**Implementation:** `main.py` (sync_state_from_backup)


---


### POST `/api/ha/sync-from-primary`


**Implementation:** `main.py` (sync_state_from_primary)


---


### POST `/ha/explicit-heartbeat`


**Implementation:** `routers/monitoring.py` (receive_explicit_heartbeat)


---


## Market Regime Detection


**Total Endpoints:** 1


| Method | Endpoint | Description |

|--------|----------|-------------|

| `GET` | `/regime-profile/{regime}` | N/A |



### GET `/regime-profile/{regime}`


**Implementation:** `routers/risk_metrics.py` (get_regime_risk_profile)


---


## Monitoring & Health Checks


**Total Endpoints:** 19


| Method | Endpoint | Description |

|--------|----------|-------------|

| `GET` | `/alerts` | N/A |

| `GET` | `/alerts/active` | N/A |

| `GET` | `/alerts/service/{service_name}` | N/A |

| `GET` | `/alerts/severity/{severity}` | N/A |

| `GET` | `/alerts/status` | N/A |

| `GET` | `/api/health` | N/A |

| `GET` | `/backup/health` | monitor = get_redundancy_monitor() |

| `GET` | `/health` | N/A |

| `GET` | `/health/history/{service_name}` | N/A |

| `GET` | `/health/learning-pipeline` | N/A |

| `GET` | `/health/production-readiness` | N/A |

| `GET` | `/health/service/{service_name}` | N/A |

| `GET` | `/health/websocket` | N/A |

| `GET` | `/primary/health` | monitor = get_redundancy_monitor() |

| `GET` | `/process/health` | N/A |

| `POST` | `/alerts/configure` | N/A |

| `POST` | `/alerts/create` | N/A |

| `POST` | `/alerts/thresholds` | N/A |

| `POST` | `/alerts/{alert_id}/resolve` | N/A |



### GET `/alerts`


**Implementation:** `routers/monitoring.py` (get_alerts)


---


### GET `/alerts/active`


**Implementation:** `routers/monitoring.py` (get_active_alerts)


---


### GET `/alerts/service/{service_name}`


**Implementation:** `routers/monitoring.py` (get_service_alerts)


---


### GET `/alerts/severity/{severity}`


**Implementation:** `routers/monitoring.py` (get_alerts_by_severity)


---


### GET `/alerts/status`


**Implementation:** `routers/risk_metrics.py` (get_risk_alert_status)


---


### GET `/api/health`


**Implementation:** `main.py` (health_check)


---


### GET `/backup/health`


**Summary:** monitor = get_redundancy_monitor()


**Implementation:** `routers/redundancy.py` (get_backup_health)


---


### GET `/health`


**Implementation:** `routers/monitoring.py` (get_health_status)


---


### GET `/health/history/{service_name}`


**Implementation:** `routers/monitoring.py` (get_health_history)


---


### GET `/health/learning-pipeline`


**Implementation:** `routers/learning_automation.py` (get_learning_pipeline_health)


---


### GET `/health/production-readiness`


**Implementation:** `routers/production_hardening.py` (get_production_readiness)


---


### GET `/health/service/{service_name}`


**Implementation:** `routers/monitoring.py` (get_service_health)


---


### GET `/health/websocket`


**Implementation:** `routers/monitoring.py` (get_websocket_staleness)


---


### GET `/primary/health`


**Summary:** monitor = get_redundancy_monitor()


**Implementation:** `routers/redundancy.py` (get_primary_health)


---


### GET `/process/health`


**Implementation:** `routers/monitoring.py` (get_process_health)


---


### POST `/alerts/configure`


**Implementation:** `routers/redundancy.py` (configure_alerts)


---


### POST `/alerts/create`


**Implementation:** `routers/monitoring.py` (create_alert)


---


### POST `/alerts/thresholds`


**Implementation:** `routers/risk_metrics.py` (set_risk_alert_thresholds)


---


### POST `/alerts/{alert_id}/resolve`


**Implementation:** `routers/monitoring.py` (resolve_alert)


---


## Portfolio Allocation & Optimization


**Total Endpoints:** 7


| Method | Endpoint | Description |

|--------|----------|-------------|

| `GET` | `/allocation` | N/A |

| `GET` | `/allocation` | N/A |

| `GET` | `/allocation/recommended` | N/A |

| `GET` | `/allocation/signal-weights/{asset_class}` | N/A |

| `GET` | `/current-allocation` | N/A |

| `POST` | `/allocation` | N/A |

| `POST` | `/allocation-solver` | N/A |



### GET `/allocation`


**Implementation:** `routers/dashboard_wrapper.py` (get_allocation_compat)


---


### GET `/allocation`


**Implementation:** `routers/portfolio.py` (get_portfolio_allocation)


---


### GET `/allocation/recommended`


**Implementation:** `routers/multi_asset.py` (get_recommended_allocation)


---


### GET `/allocation/signal-weights/{asset_class}`


**Implementation:** `routers/multi_asset.py` (get_signal_weights)


---


### GET `/current-allocation`


**Implementation:** `routers/portfolio_allocation.py` (get_current_allocation)


---


### POST `/allocation`


**Implementation:** `routers/backtest_allocation.py` (backtest_allocation)


---


### POST `/allocation-solver`


**Implementation:** `routers/recommendation.py` (solve_allocation)


---


## Portfolio Analysis


**Total Endpoints:** 3


| Method | Endpoint | Description |

|--------|----------|-------------|

| `GET` | `/portfolio-drift` | Detect portfolio drift from target allocation |

| `GET` | `/portfolio-summary` | N/A |

| `GET` | `/portfolio-var` | N/A |



### GET `/portfolio-drift`


**Summary:** Detect portfolio drift from target allocation


**Implementation:** `routers/backup_analytics.py` (get_portfolio_drift)


---


### GET `/portfolio-summary`


**Implementation:** `routers/multi_asset.py` (get_portfolio_summary)


---


### GET `/portfolio-var`


**Implementation:** `routers/risk_management.py` (get_portfolio_var)


---


## PostgreSQL HA


**Total Endpoints:** 2


| Method | Endpoint | Description |

|--------|----------|-------------|

| `GET` | `/pg-lag` | N/A |

| `GET` | `/pg-status` | N/A |



### GET `/pg-lag`


**Implementation:** `routers/ha_postgres.py` (get_postgresql_replication_lag)


---


### GET `/pg-status`


**Implementation:** `routers/ha_postgres.py` (get_postgresql_status)


---


## Rebalancing


**Total Endpoints:** 1


| Method | Endpoint | Description |

|--------|----------|-------------|

| `POST` | `/optimization/rebalancing-plan` | N/A |



### POST `/optimization/rebalancing-plan`


**Implementation:** `routers/multi_asset.py` (calculate_rebalancing_plan)


---


## Recommendations & Scenarios


**Total Endpoints:** 3


| Method | Endpoint | Description |

|--------|----------|-------------|

| `GET` | `/recommendations` | N/A |

| `GET` | `/recommendations/accuracy` | N/A |

| `POST` | `/recommendations/record` | N/A |



### GET `/recommendations`


**Implementation:** `routers/risk_management.py` (get_risk_recommendations)


---


### GET `/recommendations/accuracy`


**Implementation:** `routers/learning_feedback.py` (get_recommendation_accuracy)


---


### POST `/recommendations/record`


**Implementation:** `routers/learning_feedback.py` (record_recommendation)


---


## Redundancy Management


**Total Endpoints:** 4


| Method | Endpoint | Description |

|--------|----------|-------------|

| `GET` | `/failover/ready` | monitor = get_redundancy_monitor() |

| `POST` | `/api/failover/receive-position` | N/A |

| `POST` | `/api/failover/sync-position` | N/A |

| `POST` | `/failover/simulate` | N/A |



### GET `/failover/ready`


**Summary:** monitor = get_redundancy_monitor()


**Implementation:** `routers/redundancy.py` (check_failover_readiness)


---


### POST `/api/failover/receive-position`


**Implementation:** `routers/failover.py` (receive_position_from_primary)


---


### POST `/api/failover/sync-position`


**Implementation:** `routers/failover.py` (sync_position_to_backup)


---


### POST `/failover/simulate`


**Implementation:** `routers/redundancy.py` (simulate_failover)


---


## Risk Management


**Total Endpoints:** 6


| Method | Endpoint | Description |

|--------|----------|-------------|

| `GET` | `/concentration` | N/A |

| `GET` | `/currency/var` | N/A |

| `GET` | `/drawdown` | N/A |

| `GET` | `/risk-metrics` | Get risk metrics: Sharpe ratio, drawdown, VaR, volatility |

| `GET` | `/risk-metrics` | N/A |

| `GET` | `/risk-return-profile` | N/A |



### GET `/concentration`


**Implementation:** `routers/risk_management.py` (get_concentration_risk)


---


### GET `/currency/var`


**Implementation:** `routers/multi_asset.py` (get_currency_var)


---


### GET `/drawdown`


**Implementation:** `routers/risk_management.py` (get_portfolio_drawdown)


---


### GET `/risk-metrics`


**Summary:** Get risk metrics: Sharpe ratio, drawdown, VaR, volatility


**Implementation:** `routers/backup_analytics.py` (get_risk_metrics)


---


### GET `/risk-metrics`


**Implementation:** `routers/portfolio.py` (get_portfolio_risk_metrics)


---


### GET `/risk-return-profile`


**Implementation:** `routers/portfolio_allocation.py` (get_risk_return_profile)


---


## System Metrics


**Total Endpoints:** 4


| Method | Endpoint | Description |

|--------|----------|-------------|

| `GET` | `/metrics` | N/A |

| `GET` | `/metrics` | N/A |

| `GET` | `/metrics` | N/A |

| `GET` | `/performance/metrics` | N/A |



### GET `/metrics`


**Implementation:** `main.py` (get_current_metrics)


---


### GET `/metrics`


**Implementation:** `routers/monitoring.py` (get_metrics)


---


### GET `/metrics`


**Implementation:** `routers/risk_metrics.py` (get_risk_metrics)


---


### GET `/performance/metrics`


**Implementation:** `routers/recommendation_advanced.py` (get_performance_metrics)


---


## Tax Management


**Total Endpoints:** 1


| Method | Endpoint | Description |

|--------|----------|-------------|

| `GET` | `/tax-summary` | N/A |



### GET `/tax-summary`


**Implementation:** `routers/stocks.py` (get_stock_tax_summary)


---


## Trading Account Management


**Total Endpoints:** 6


| Method | Endpoint | Description |

|--------|----------|-------------|

| `GET` | `/api/paper/account` | N/A |

| `GET` | `/api/paper/positions` | N/A |

| `GET` | `/api/paper/status` | N/A |

| `GET` | `/api/paper/trades` | N/A |

| `POST` | `/api/paper/order` | N/A |

| `POST` | `/api/paper/reset` | N/A |



### GET `/api/paper/account`


**Implementation:** `main.py` (get_paper_account)


---


### GET `/api/paper/positions`


**Implementation:** `main.py` (get_paper_positions)


---


### GET `/api/paper/status`


**Implementation:** `main.py` (get_paper_status)


---


### GET `/api/paper/trades`


**Implementation:** `main.py` (get_paper_trades)


---


### POST `/api/paper/order`


**Implementation:** `routers/dashboard_integration.py` (place_paper_order)


---


### POST `/api/paper/reset`


**Implementation:** `main.py` (reset_paper_trading)


---


## Trading Control


**Total Endpoints:** 6


| Method | Endpoint | Description |

|--------|----------|-------------|

| `GET` | `/trading/status` | N/A |

| `POST` | `/exit` | N/A |

| `POST` | `/pause` | N/A |

| `POST` | `/resume` | N/A |

| `POST` | `/trading/disable` | N/A |

| `POST` | `/trading/enable` | N/A |



### GET `/trading/status`


**Implementation:** `routers/config.py` (get_trading_status)


---


### POST `/exit`


**Implementation:** `routers/trading_control.py` (partial_exit)


---


### POST `/pause`


**Implementation:** `routers/trading_control.py` (pause_trading)


---


### POST `/resume`


**Implementation:** `routers/trading_control.py` (resume_trading)


---


### POST `/trading/disable`


**Implementation:** `routers/config.py` (disable_trading)


---


### POST `/trading/enable`


**Implementation:** `routers/config.py` (enable_trading)


---


## User Management


**Total Endpoints:** 4


| Method | Endpoint | Description |

|--------|----------|-------------|

| `GET` | `/preferences` | N/A |

| `GET` | `/profile` | N/A |

| `GET` | `/settings` | return JSONResponse(user_settings) |

| `PUT` | `/settings` | N/A |



### GET `/preferences`


**Implementation:** `routers/user.py` (get_user_preferences)


---


### GET `/profile`


**Implementation:** `routers/user.py` (get_user_profile)


---


### GET `/settings`


**Summary:** return JSONResponse(user_settings)


**Implementation:** `routers/user.py` (get_user_settings)


---


### PUT `/settings`


**Implementation:** `routers/user.py` (update_user_settings)


---


## Documentation Guidelines


### Error Responses


All errors follow this format:


```json

{

  "error": "ERROR_CODE",

  "detail": "Human-readable message",

  "status_code": 400

}
```


### Request Validation


- All string inputs are trimmed of whitespace

- Numbers must be valid JSON numbers

- Booleans must be `true` or `false`

- Arrays must be valid JSON arrays

- Required fields must be present


### Rate Limiting


- **Limit:** 100 requests/minute per client

- **Window:** Rolling 60-second window

- **Header:** `X-RateLimit-Remaining` (remaining requests)

- **Status:** 429 when limit exceeded


### Security Headers


The API includes these security headers:

- `X-Content-Type-Options: nosniff`

- `X-Frame-Options: DENY`

- `X-XSS-Protection: 1; mode=block`

- `Strict-Transport-Security: max-age=31536000`


## Common Use Cases


### Example 1: Check System Health


```bash

curl -s http://localhost:8000/api/health | jq .

```


### Example 2: Get Account Status


```bash

curl http://localhost:8000/api/paper/account | jq '.cash, .equity'

```


### Example 3: Start Autonomous Trading


```bash

curl -X POST http://localhost:8000/api/autonomous/start | jq .

```


### Example 4: Update Trading Configuration


```bash

curl -X POST http://localhost:8000/api/autonomous/config/update \

  -H 'Content-Type: application/json' \

  -d '{

    "position_size_pct": 2.0,

    "max_positions": 5

  }' | jq .

```


### Example 5: Pause Trading


```bash

curl -X POST http://localhost:8000/api/trading/pause | jq .

```


## Architecture


### High Availability


The API supports PRIMARY/BACKUP failover for production deployments:


- **PRIMARY:** Main trading instance

- **BACKUP:** Hot standby instance

- **Heartbeat:** Every 5 seconds (PRIMARY → BACKUP)

- **Failover:** Automatic on heartbeat loss

- **Sync:** State synchronization during failover


### Endpoint Categories


1. **Trading Account Management** - Account balance, positions, trade history

2. **Autonomous Trading** - Enable/disable, configuration, status

3. **Monitoring & Health** - System health, alerts, metrics

4. **High Availability** - Heartbeats, state sync, failover

5. **Portfolio Management** - Allocation, optimization, analysis

6. **Risk Management** - Limits, VaR, drawdown, concentration

7. **Configuration** - Settings, parameters, persistence

8. **Trading Control** - Pause, resume, partial exits


## Version History


### Version 1.0.0 (Current)

- Released: 2026-07-03

- Total Endpoints: 197

- Features: Full trading control, autonomous mode, HA support



## Detailed Endpoint Reference

### Core Parameters & Types

All endpoints use these standard parameter types:

**Common Query Parameters:**
- `limit` (integer): Maximum number of results (default: 100, max: 1000)
- `offset` (integer): Skip N results (default: 0)
- `sort` (string): Sort field and direction (e.g., "timestamp:desc")
- `filter` (string): Filter expression (varies by endpoint)

**Common Path Parameters:**
- `{symbol}` (string): Crypto/stock symbol (e.g., "BTC/USDT", "AAPL")
- `{service_name}` (string): Service identifier
- `{result_id}` (string): Result/record ID
- `{alert_id}` (string): Alert identifier
- `{regime}` (string): Market regime label

**Common Response Fields:**
- `status` (string): "success" or error code
- `timestamp` (string): ISO 8601 UTC timestamp
- `data` (object): Response payload
- `error` (string): Error message (if error)
- `detail` (string): Error details (if error)

### Request/Response Examples

#### Example 1: Get Account Status
```bash
curl -X GET http://localhost:8000/api/paper/account \
  -H "Accept: application/json"
```

Response (200 OK):
```json
{
  "cash": 1220.41,
  "equity": 1441.97,
  "pnl": 221.56,
  "pnl_percent": 15.4,
  "currency": "EUR",
  "starting_capital": 1000.0,
  "timestamp": "2026-07-03T17:30:00Z"
}
```

#### Example 2: Update Trading Config
```bash
curl -X POST http://localhost:8000/api/autonomous/config/update \
  -H "Content-Type: application/json" \
  -d '{
    "entry_threshold": 0.65,
    "exit_profit_target": 0.025,
    "position_size_pct": 2.5,
    "max_positions": 4
  }'
```

Response (200 OK):
```json
{
  "status": "updated",
  "persisted": true,
  "synced": true,
  "config": {
    "entry_threshold": 0.65,
    "exit_profit_target": 0.025,
    "position_size_pct": 2.5,
    "max_positions": 4,
    "enabled": true,
    "loop_sleep_seconds": 5.0,
    "quality_gate_entry": 85.0,
    "quality_gate_exit": 80.0
  }
}
```

#### Example 3: Get Monitoring Alerts
```bash
curl "http://localhost:8000/api/monitoring/alerts?status=active&limit=50" \
  -H "Accept: application/json"
```

Response (200 OK):
```json
{
  "count": 3,
  "status": "active",
  "alerts": [
    {
      "id": "alert_001",
      "severity": "warning",
      "service": "paper_trading",
      "title": "High position concentration",
      "message": "BTC position is 45% of portfolio",
      "created_at": "2026-07-03T17:25:00Z",
      "resolved": false
    }
  ]
}
```

#### Example 4: Place Paper Order (via Dashboard)
```bash
curl -X POST http://localhost:8000/api/paper/order \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTC/USDT",
    "side": "BUY",
    "quantity": 0.01,
    "order_type": "MARKET"
  }'
```

Response (200 OK):
```json
{
  "order_id": "order_12345",
  "symbol": "BTC/USDT",
  "side": "BUY",
  "quantity": 0.01,
  "price": 42500.0,
  "status": "FILLED",
  "timestamp": "2026-07-03T17:30:00Z"
}
```

### Error Response Examples

#### Missing Required Parameter
```json
{
  "error": "INVALID_REQUEST",
  "detail": "Required parameter 'symbol' missing",
  "status_code": 400
}
```

#### Resource Not Found
```json
{
  "error": "NOT_FOUND",
  "detail": "Service 'unknown_service' not found",
  "status_code": 404
}
```

#### Service Unavailable
```json
{
  "error": "SERVICE_UNAVAILABLE",
  "detail": "Paper trading engine not initialized",
  "status_code": 503
}
```

#### Rate Limit Exceeded
```json
{
  "error": "RATE_LIMITED",
  "detail": "100 requests per minute limit exceeded",
  "status_code": 429
}
```

## Integration Guide

### Python Example: Monitor Account
```python
import requests
import json
import time

API_BASE = "http://localhost:8000"

def monitor_account():
    """Monitor account status continuously."""
    while True:
        # Get account status
        resp = requests.get(f"{API_BASE}/api/paper/account")
        if resp.status_code == 200:
            account = resp.json()
            print(f"Account | Cash: €{account['cash']:.2f} | Equity: €{account['equity']:.2f} | P&L: {account['pnl_percent']:.1f}%")
        
        # Get positions
        resp = requests.get(f"{API_BASE}/api/paper/positions")
        if resp.status_code == 200:
            positions = resp.json()
            print(f"Positions: {len(positions)} open")
            for pos in positions:
                print(f"  - {pos['symbol']}: {pos['quantity']:.4f} @ €{pos['entry_price']:.2f}")
        
        time.sleep(30)

if __name__ == "__main__":
    monitor_account()
```

### JavaScript/Node.js Example: Start Trading
```javascript
const axios = require('axios');

const API_BASE = 'http://localhost:8000';

async function startTrading() {
  try {
    // Check current status
    const status = await axios.get(`${API_BASE}/api/autonomous/status`);
    console.log('Autonomous Trader Status:', status.data);
    
    // Update config
    const config = await axios.post(
      `${API_BASE}/api/autonomous/config/update`,
      {
        entry_threshold: 0.65,
        max_positions: 5,
        position_size_pct: 2.0
      }
    );
    console.log('Config Updated:', config.data);
    
    // Start trading
    const start = await axios.post(`${API_BASE}/api/autonomous/start`);
    console.log('Trading Started:', start.data);
  } catch (error) {
    console.error('Error:', error.response.data);
  }
}

startTrading();
```

### cURL Cheat Sheet
```bash
# Health check
curl http://localhost:8000/api/health | jq .

# Account info
curl http://localhost:8000/api/paper/account | jq .

# Trading status
curl http://localhost:8000/api/paper/status | jq .

# Start autonomous trading
curl -X POST http://localhost:8000/api/autonomous/start | jq .

# Get metrics
curl http://localhost:8000/metrics | head -20

# Pause trading
curl -X POST http://localhost:8000/api/trading/pause | jq .

# Resume trading
curl -X POST http://localhost:8000/api/trading/resume | jq .

# Get trades (last 50)
curl "http://localhost:8000/api/paper/trades?limit=50" | jq .

# Get alerts
curl "http://localhost:8000/api/monitoring/alerts?status=active" | jq .

# Check HA status
curl http://localhost:8000/api/ha/status | jq .

# Reset paper trading (DANGEROUS)
curl -X POST http://localhost:8000/api/paper/reset | jq .
```

## Deployment Considerations

### Production Recommendations

1. **Authentication:** Add JWT/OAuth2 before production deployment
2. **HTTPS:** Use TLS/SSL certificates for all endpoints
3. **Rate Limiting:** Implement stricter limits (10-50 req/min)
4. **Logging:** Enable structured JSON logging for all requests
5. **Monitoring:** Set up alerts for 5xx errors and high latency
6. **CORS:** Restrict origins to known frontend domains
7. **API Versioning:** Implement versioned endpoints (/api/v1/...)
8. **Documentation:** Keep OpenAPI spec synchronized

### Performance Tuning

- Connection pooling for internal services
- Response caching for read-only endpoints
- Database indexing on frequently queried fields
- Load balancing for high-traffic endpoints
- Circuit breakers for dependent services

### Security Checklist

- [ ] No hardcoded credentials in responses
- [ ] Input validation on all endpoints
- [ ] Rate limiting implemented
- [ ] CORS configured correctly
- [ ] Security headers added
- [ ] Error messages don't leak sensitive info
- [ ] SQL injection prevention (if using DB)
- [ ] CSRF protection enabled
- [ ] Audit logging enabled
- [ ] Dependency vulnerabilities checked

## Troubleshooting

### Common API Issues

**Issue: 503 Service Unavailable**
- Likely cause: Paper trading engine not initialized
- Solution: Check `/api/health` endpoint
- Action: Restart API server

**Issue: 400 Bad Request**
- Likely cause: Invalid parameters or malformed JSON
- Solution: Validate request format and parameters
- Debug: Check request Content-Type and body

**Issue: 429 Too Many Requests**
- Likely cause: Rate limit exceeded (100 req/min)
- Solution: Implement exponential backoff
- Debug: Check X-RateLimit-Remaining header

**Issue: Authentication Failed**
- Likely cause: Missing/invalid auth token (future)
- Solution: Ensure token in Authorization header
- Debug: Check token expiration and format

**Issue: Slow Response Times**
- Likely cause: Slow backend service or database
- Solution: Check `/metrics` for resource usage
- Debug: Monitor CPU, memory, and database latency

## Next Steps

1. **Integrate with Frontend:** Use documented endpoints in web UI
2. **Build Client Library:** Generate SDK from OpenAPI spec
3. **Add More Monitoring:** Implement custom dashboards
4. **Automate Testing:** Set up API contract tests
5. **Document Webhooks:** When event streaming is added

## Support & Debugging


### Common Issues


**503 Service Unavailable**

- Paper trading engine not initialized

- Check `/api/health` endpoint


**400 Bad Request**

- Missing required parameters

- Invalid parameter types

- Check request format


**429 Too Many Requests**

- Rate limit exceeded (100 req/min)

- Implement exponential backoff


---


**Last Updated:** 2026-07-03 09:48:42 UTC

**Format:** OpenAPI-compatible REST
