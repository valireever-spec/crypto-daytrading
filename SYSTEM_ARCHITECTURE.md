# Crypto-DayTrading: System Architecture

## High-Level Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         CRYPTO-DAYTRADING PLATFORM                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ EXTERNAL DATA SOURCES                                            │  │
│  │  • Binance WebSocket (Real-time ticks)                           │  │
│  │  • Binance REST API (Fallback prices)                            │  │
│  │  • Exchange metadata (symbols, fees)                             │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│           │                                                               │
│           ▼                                                               │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ INGESTION LAYER (Exchange Integration)                          │  │
│  │  • WebSocketManager: Real-time price feeds                       │  │
│  │  ✨ WebSocketStalenessMonitor (Skill #1): Early detection       │  │
│  │  • BinanceStream: Legacy feed (fallback)                         │  │
│  │  • PaperTradingEngine: Simulated execution                       │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│           │                                                               │
│           ▼                                                               │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ CORE INFRASTRUCTURE                                              │  │
│  │  • Database Layer (SQLite WAL mode + HA sync)                    │  │
│  │  • Config Manager (Runtime reloadable)                           │  │
│  │  • Structured Logging (JSON output for analysis)                 │  │
│  │  • Metrics Collection (Prometheus-ready)                         │  │
│  │  • Health Monitoring (Multi-service checker)                     │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│           │                                                               │
│           ▼                                                               │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ DECISION ENGINE (Trading Logic)                                  │  │
│  │  • Autonomous Trader: Main loop                                  │  │
│  │  • Strategy Selector: Choose strategy per symbol                 │  │
│  │  • Signal Generation: Technical + ML + Sentiment                 │  │
│  │  • Risk Management: Stop-loss, position sizing, limits           │  │
│  │  • Order Execution: Entry/exit logic + safety gates              │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│           │                                                               │
│           ▼                                                               │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ SAFETY LAYER (Hardened Execution)                               │  │
│  │  • Circuit Breaker v2: Graceful degradation                      │  │
│  │  • Emergency Stop: Manual halt + auto-recover                    │  │
│  │  • Risk Gates: Max drawdown, position limits, correlation        │  │
│  │  • Data Validation: Sanity checks on all inputs                  │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│           │                                                               │
│           ▼                                                               │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ FAILOVER LAYER (High Availability)                              │  │
│  │  • HA Heartbeat: PRIMARY → BACKUP monitoring                     │  │
│  │  • State Sync: Bidirectional DB + config sync                    │  │
│  │  • Split-Brain Prevention: Quorum-based decisions                │  │
│  │  • Automatic Failover: Switchover on PRIMARY failure             │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│           │                                                               │
│           ▼                                                               │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ API LAYER (External Interface)                                   │  │
│  │  • 30+ REST endpoints for control/monitoring                     │  │
│  │  • Dashboard wrapper (frontend proxy)                            │  │
│  │  • WebSocket health endpoint (Skill #1 metrics)                  │  │
│  │  • Admin controls (emergency stop, config reload)                │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│           │                                                               │
│           ▼                                                               │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ OBSERVABILITY (Monitoring & Analysis)                           │  │
│  │  • Real-time dashboards (browser)                                │  │
│  │  • Prometheus metrics export                                     │  │
│  │  • Performance analytics (Sharpe, drawdown, win rate)            │  │
│  │  • Post-mortem logging (every decision + rationale)              │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow Paths

### Critical Path 1: Real-Time Trading (Sub-Second)

```
Binance WebSocket
       │
       ▼
WebSocketManager ─┬─→ Price Cache
                  │
                  └─→ Callbacks
                      ↓
                 ✨ WebSocketStalenessMonitor
                      │ (Skill #1: Detect stale every 1s)
                      │ (Reconnect at 15s staleness)
                      ▼
                 AutonomousTrader.start()
                      │
                      ├─→ Fetch latest prices
                      ├─→ Generate signals
                      ├─→ Evaluate risk gates
                      ├─→ Decide: BUY/SELL/HOLD
                      │
                      ▼
                 SmartExecutor
                      │
                      ├─→ Order validation
                      ├─→ Simulate execution
                      └─→ Update portfolio
                           │
                           ▼
                      Database (Async write)
                           │
                           ▼
                      Dashboard/Metrics
```

**Latency Budget:** ~100ms from price to decision  
**Failure Handling:** If WebSocket stale >15s, reconnect via Skill #1 (recovery <20s)

### Critical Path 2: HA Failover (Seconds)

```
PRIMARY Bot Running
       │
       ├─→ Sends heartbeat every 5s to BACKUP
       │
       ├─→ If heartbeat fails 3x (15s total)
       │         │
       │         ▼
       │    BACKUP detects PRIMARY dead
       │         │
       │         ▼
       │    BACKUP auto-promotes
       │         │
       │         ├─→ Reads authoritative DB
       │         ├─→ Syncs state (trades, positions)
       │         └─→ Starts trading autonomously
       │
       └─→ If PRIMARY recovers
              │
              ▼
           PRIMARY demotes to BACKUP
           (Reads DB, syncs state, goes standby)
```

**Failover Time:** <20 seconds  
**Data Loss:** Zero (all state in DB)

### Critical Path 3: Safety Net (Emergency)

```
AutonomousTrader Loop
       │
       ├─→ Check Circuit Breaker status
       │    ├─ CLOSED: Normal trading
       │    ├─ OPEN: Stop new entries (already open)
       │    └─ HALF_OPEN: Try limited entries (recovery mode)
       │
       ├─→ Check Risk Gates
       │    ├─ Max Drawdown exceeded? HALT
       │    ├─ Position size too large? REDUCE
       │    └─ Correlation risk high? PAUSE
       │
       └─→ Execute trade
            ├─ Pre-flight checks
            ├─ Order placement
            └─ Post-flight validation
```

---

## Component Details

### 1. Ingestion Layer

**Files:** `backend/exchange/`

```
websocket_manager.py
├── WebSocketManager
│   ├── start() → Connect to Binance, subscribe streams
│   ├── _ws_listen() → Async loop reading messages
│   ├── _monitor_loop() → Health check every 1s (detect staleness)
│   ├── register_callback(fn) → Register price update handlers
│   └── reconnect(symbol) → Triggered by Skill #1 on staleness
│
├── ✨ websocket_staleness_monitor.py (NEW - Skill #1)
│   ├── WebSocketStalenessMonitor
│   │   ├── start_monitoring() → Background task, checks every 1s
│   │   ├── _check_all_streams() → Detect staleness threshold
│   │   ├── _attempt_reconnect() → Exponential backoff + retries
│   │   ├── on_price_update() → Called on each price tick
│   │   └── get_status() → Health metrics (staleness, reconnects)
│   │
│   └── StreamHealth
│       ├── symbol, last_update_time, staleness_secs
│       ├── reconnect_attempts, is_healthy
│       └── metrics tracking
│
binance_stream.py
├── BinanceStream (Legacy)
│   ├── connect() → Alternative WebSocket connection
│   └── subscribe() → For specific streams
│
paper_trading.py
├── PaperTradingEngine
│   ├── place_buy_order(price, quantity)
│   ├── place_sell_order(price, quantity)
│   └── get_position(symbol)
```

**Data Format:**
```python
PriceUpdate:
  symbol: str          # "BTCUSDT"
  price: float         # 61730.65
  timestamp: datetime  # when Binance sent it
  source: str          # "websocket" or "rest"
  age_seconds: float   # how stale is this data?
```

---

### 2. Decision Engine

**Files:** `backend/trading/autonomous_trader/`

```
core.py
├── AutonomousTrader (Main class)
│   ├── __init__()
│   │   ├── Load TradingConfig
│   │   ├── Initialize all 10 hardening managers
│   │   └── Setup database connections
│   │
│   ├── async start()
│   │   └── Main trading loop (runs forever)
│   │       ├── Every tick (100ms):
│   │       │   ├── Fetch prices from WebSocketManager
│   │       │   ├── Generate signals
│   │       │   ├── Evaluate risk gates
│   │       │   ├── Decide: BUY/SELL/HOLD
│   │       │   └── Execute via SmartExecutor
│   │       │
│   │       └── Error handling:
│   │           ├── Log every decision + rationale
│   │           ├── Catch exceptions gracefully
│   │           └── Update circuit breaker state
│   │
│   ├── async stop()
│   │   ├── Cancel all pending orders
│   │   ├── Close all positions (if emergency)
│   │   └─→ Write final state to DB
│   │
│   └── _evaluate_signals()
│       ├── RSI, MACD, Bollinger Bands (technical)
│       ├── Random Forest (ML prediction)
│       ├── Sentiment analysis (news/social)
│       └─→ Composite signal: 0-100 score
│
entry.py
├── generate_entry_signals()
│   ├── Take latest prices
│   ├── Generate entry opportunities
│   └─→ Return entry_signals[] with confidence
│
exit.py
├── generate_exit_signals()
│   ├── Check stop-loss triggers
│   ├── Check take-profit levels
│   └─→ Return exit_signals[] with reason
│
portfolio.py
├── PortfolioManager
│   ├── get_current_positions()
│   ├── get_unrealized_pnl()
│   ├── calculate_position_size()
│   └─→ Track all open trades
│
validation.py
├── validate_entry(signal)
│   ├── Check max positions
│   ├── Check correlation
│   ├── Check account balance
│   └─→ APPROVE or REJECT
```

**Decision Cycle (50-100ms):**
```python
while running:
    # 1. FETCH (10ms)
    prices = ws_manager.get_prices(['BTCUSDT', 'ETHUSDT', 'BNBUSDT'])
    
    # 2. ANALYZE (30ms)
    signals = generate_signals(prices, historical_data)
    
    # 3. DECIDE (10ms)
    actions = []
    for symbol, signal in signals.items():
        if signal.confidence > 0.7 and validate_entry(symbol):
            actions.append(Order(symbol, signal.direction, signal.size))
    
    # 4. EXECUTE (20ms)
    for order in actions:
        executor.place_order(order)
        db.log_decision(symbol, order, signal, rationale)
    
    await asyncio.sleep(0.1)  # Next cycle in 100ms
```

---

### 3. Safety Layer

**Files:** `backend/core/` and `backend/execution/`

```
circuit_breaker_v2.py
├── CircuitBreakerV2
│   ├── State: CLOSED → OPEN → HALF_OPEN → CLOSED
│   │
│   ├── CLOSED: Normal trading (all entry types allowed)
│   │   └─ On failure threshold met → OPEN
│   │
│   ├── OPEN: Stop new entries (protection mode)
│   │   ├─ Log reason (WebSocket stale, risk gate, error)
│   │   ├─ Allow exits (close existing positions)
│   │   └─ After timeout (20s) → HALF_OPEN
│   │
│   ├── HALF_OPEN: Try limited entries (recovery test)
│   │   ├─ Allow small entries (10% of normal size)
│   │   ├─ If successful → CLOSED (fully recovered)
│   │   └─ If fail → OPEN (not yet ready)
│   │
│   └── Metrics
│       ├── trips_total: count of times opened
│       ├── time_open_seconds: how long in OPEN state
│       └─→ Exported to Prometheus
│
risk_gate_enforcement.py
├── RiskGateManager
│   ├── max_drawdown_gate (current equity drop from peak)
│   │   └─ If drawdown > -5%, stop new entries
│   │
│   ├── position_size_gate (total notional exposure)
│   │   └─ If exposure > $10k, reduce new orders
│   │
│   ├── correlation_gate (symbol correlation check)
│   │   └─ If corr(BTC,ETH) > 0.8 and both holding, reduce
│   │
│   └─→ All decisions logged with rationale
│
smart_executor.py
├── SmartExecutor
│   ├── place_order(order)
│   │   ├─ Pre-flight checks:
│   │   │  ├─ Verify prices fresh (<10s old)
│   │   │  ├─ Verify position still valid
│   │   │  └─ Verify account balance
│   │   │
│   │   ├─ Simulate in paper trading
│   │   │
│   │   ├─ Log decision with timestamp + prices
│   │   │
│   │   └─→ Return execution result
│   │
│   └─→ All orders go through paper trading engine
```

**Safety Decision Tree:**
```
Order Placement Request
    │
    ├─→ Circuit Breaker OPEN? → REJECT (in protection mode)
    │
    ├─→ WebSocket stale >15s? → REJECT (Skill #1 reconnecting)
    │
    ├─→ Drawdown > -5%? → REJECT (risk gate)
    │
    ├─→ Position size violated? → REDUCE order size
    │
    ├─→ Prices stale? → REJECT (use recent tick only)
    │
    └─→ APPROVE → Place in paper trading engine
            │
            ├─→ Simulate execution
            ├─→ Update portfolio
            └─→ Log to DB
```

---

### 4. HA Failover Layer

**Files:** `backend/failover/` and `backend/core/ha_*.py`

```
heartbeat.py (BACKUP monitoring PRIMARY)
├── PRIMARY_Heartbeat
│   ├── _send_heartbeat() every 5s
│   │   ├─ GET /api/health from PRIMARY
│   │   ├─ POST /api/ha/heartbeat (tell PRIMARY we're alive)
│   │   └─ Return: "healthy" or "error"
│   │
│   ├── _handle_failure()
│   │   ├─ Count consecutive failures (threshold: 3)
│   │   ├─ After 3 failures (15s timeout):
│   │   │  ├─ Mark PRIMARY dead
│   │   │  ├─ Run split-brain check (SSH to PRIMARY)
│   │   │  └─ If confirmed dead, trigger failover
│   │   │
│   │   └─→ _trigger_failover()
│   │       ├─ Read authoritative DB (check authority)
│   │       ├─ Sync PRIMARY → BACKUP state
│   │       ├─ Stop BACKUP standby mode
│   │       ├─ Start BACKUP as PRIMARY
│   │       └─→ Resume autonomous trading
│   │
│   └─ Metrics: failures_count, last_check_time
│
database_sync.py
├── DatabaseSyncer
│   ├── sync_from_authoritative()
│   │   ├─ Primary DB (PRIMARY machine): always source of truth
│   │   ├─ Backup DB (BACKUP machine): synced every 5s
│   │   └─→ Uses rsync + verification
│   │
│   └─→ Bidirectional on startup (detect which is authoritative)
│
split_brain_prevention.py
├── SplitBrainPrevention
│   ├── On BACKUP failure detection:
│   │   ├─ Reach out to PRIMARY via SSH
│   │   ├─ Confirm PRIMARY is actually dead
│   │   └─ Only failover if confirmed
│   │
│   └─→ Quorum-based: SSH to both, check who's running
```

**Failover Sequence:**
```
T+0s:  PRIMARY heartbeat healthy
T+5s:  PRIMARY heartbeat → timeout (network issue)
       BACKUP: Failure count = 1/3

T+10s: Retry heartbeat → timeout
       BACKUP: Failure count = 2/3

T+15s: Retry heartbeat → timeout
       BACKUP: Failure count = 3/3 → TRIGGER FAILOVER
       
       ├─ SSH to PRIMARY: "Are you running?" → No response
       ├─ Confirmed: PRIMARY is dead
       ├─ Read authoritative DB
       ├─ Sync state from PRIMARY → BACKUP
       ├─ Stop BACKUP heartbeat task
       ├─ Start BACKUP autonomous trader
       └─→ BACKUP is now PRIMARY

T+16s: Customers directed to BACKUP endpoint
       Trading resumes on new PRIMARY
```

---

### 5. Core Infrastructure

**Files:** `backend/core/`

```
database_persistence.py
├── DatabaseManager
│   ├── SQLite with WAL mode (allows concurrent reads/writes)
│   ├── Tables:
│   │   ├─ trades (entry, exit, pnl, status)
│   │   ├─ positions (open trades)
│   │   ├─ signals (generated every tick)
│   │   ├─ candles (OHLCV data)
│   │   └─ portfolio_metrics (daily snapshots)
│   │
│   └─→ All writes async (doesn't block trading)
│
config_manager.py
├── RuntimeConfigManager
│   ├── Load config from JSON file
│   ├── Hot reload: /api/config/reload endpoint
│   ├─ Tunable:
│   │   ├─ WARN_THRESHOLD: 5s (Skill #1)
│   │   ├─ CRITICAL_THRESHOLD: 15s (Skill #1)
│   │   ├─ MAX_DRAWDOWN_PCT: -5%
│   │   ├─ MAX_POSITION_SIZE: $10k
│   │   └─ Risk gate thresholds
│   │
│   └─→ No restart needed to change behavior
│
structured_logging.py
├── StructuredLogger
│   ├── Output: JSON (not human-readable text)
│   ├─ Fields:
│   │   ├─ timestamp, level, logger, message
│   │   ├─ function, module, line (code location)
│   │   ├─ symbol, price, direction (trade context)
│   │   └─ stack_trace (if error)
│   │
│   └─→ Parseable by log analysis tools
│
health_checker.py
├── HealthChecker
│   ├─ Checks every service:
│   │   ├─ WebSocket connection status
│   │   ├─ Database latency
│   │   ├─ API responsiveness
│   │   ├─ HA heartbeat status
│   │   └─ Disk/CPU/Memory resources
│   │
│   └─→ /api/monitoring/health endpoint
│
metrics.py
├── MetricsCollector
│   ├─ Prometheus format metrics:
│   │   ├─ trading_decisions_total
│   │   ├─ orders_placed_total
│   │   ├─ websocket_reconnect_attempts_total
│   │   ├─ circuit_breaker_trips_total
│   │   └─ portfolio_equity
│   │
│   └─→ /metrics endpoint (Prometheus scrape)
```

---

### 6. API Layer

**Files:** `backend/api/main.py` and `backend/api/routers/`

```
30+ REST Endpoints organized by function:

TRADING CONTROL
├── POST /api/autonomous/start → Start bot
├── POST /api/autonomous/stop → Stop bot
├── POST /api/autonomous/pause → Pause entries (keep exits open)
└── POST /api/autonomous/resume → Resume trading

MONITORING
├── GET /api/monitoring/health → Overall system health
├── GET /api/monitoring/health/websocket → Skill #1 metrics
├── GET /api/monitoring/metrics → Prometheus-format metrics
└── GET /api/monitoring/status → Current state snapshot

RISK & EMERGENCY
├── POST /api/emergency/stop → Hard halt (close all positions)
├── POST /api/emergency/reset → Reset circuit breaker
├── GET /api/risk/gates → Current risk limits
└── POST /api/risk/gates/{gate}/adjust → Change limits on-the-fly

PORTFOLIO
├── GET /api/portfolio/positions → Current open trades
├── GET /api/portfolio/performance → PnL, Sharpe, drawdown
├── GET /api/portfolio/allocation → Notional exposure by symbol
└── GET /api/portfolio/history → All historical trades

HA FAILOVER
├── GET /api/ha/status → PRIMARY or BACKUP?
├── POST /api/ha/heartbeat → Heartbeat from other instance
├── POST /api/ha/sync-from-primary → Sync state
└── GET /api/ha/authority → Which DB is authoritative?

CONFIGURATION
├── GET /api/config/current → Current config
├── POST /api/config/update → Change config
└── POST /api/config/reload → Hot reload without restart

ANALYTICS
├── GET /api/analytics/signals → Generated signals history
├── GET /api/analytics/backtest → Run backtest on strategy
└── GET /api/analytics/sharpe → Sharpe ratio, metrics
```

---

## Where Skill #1 Fits

```
                    INGEST                    DECISION                  SAFETY
                    -----                     --------                  ------
                    
Binance WebSocket   ┌─────────────┐          ┌──────────────┐      ┌──────────┐
       │            │ WebSocket   │          │ Autonomous   │      │ Circuit  │
       └───────────→│ Manager     │─────────→│ Trader       │─────→│ Breaker  │
                    │             │          │              │      │          │
                    │ ✨ Skill #1 │          │ Signal       │      │ Risk     │
                    │   Staleness │          │ Generation   │      │ Gates    │
                    │   Monitor   │          │              │      │          │
                    │             │          │ Order        │      │ Smart    │
         Every 1s:  │ • Detect    │          │ Placement    │      │ Executor │
         • Check    │   staleness │          │              │      │          │
           ages     │ • If >15s   │          │              │      │          │
         • Log      │   reconnect │          │              │      │          │
           metrics  │             │          │              │      │          │
         • Try      │ Metrics:    │          │              │      │          │
           recovery │ • Stale     │          │              │      │          │
                    │   warnings  │          │              │      │          │
                    │ • Reconnect │          │              │      │          │
                    │   attempts  │          │              │      │          │
                    │ • Success   │          │              │      │          │
                    │   rate      │          │              │      │          │
                    └─────────────┘          └──────────────┘      └──────────┘
                         │                         │                    │
                         └─────────────────────────┴────────────────────┘
                                      │
                                      ▼
                                  Database
                                  (history)
```

**Skill #1 prevents this flow:**
```
WebSocket dies → [No Skill #1: 30s passes silently]
             → Prices stale (trader using old data)
             → Circuit breaker trips too late
             → Trading halted
             → 3am manual restart needed

With Skill #1:
WebSocket dies → [Skill #1: Detects at 15s]
             → Tries reconnect (backoff: 2s, 4s, 8s)
             → Connected within 20s
             → Prices fresh again
             → Autonomous trader never sees stale data
             → Circuit breaker never needed
             → No trading halt
```

---

## Deployment Architecture

```
┌─────────────────────────┐         ┌─────────────────────────┐
│   PRIMARY MACHINE       │         │   BACKUP MACHINE        │
│   192.168.3.1           │◄─────────┤   192.168.3.25          │
│                         │   Sync   │                         │
│  ┌─────────────────┐    │   every  │  ┌─────────────────┐    │
│  │ Autonomous Bot  │    │   5s     │  │  Standby Mode   │    │
│  │ • Trading       │    │          │  │  • Monitor HB   │    │
│  │ • Real-time     │    │          │  │  • Sync DB      │    │
│  │                 │    │          │  │                 │    │
│  └─────────────────┘    │          │  └─────────────────┘    │
│         │               │          │         │               │
│  ┌─────────────────┐    │          │  ┌─────────────────┐    │
│  │ Database        │◄───┼──────────┼─→│ Database        │    │
│  │ (trading.db)    │    │  Sync    │  │ (trading.db)    │    │
│  └─────────────────┘    │          │  └─────────────────┘    │
│         │               │          │         │               │
│  ┌─────────────────┐    │          │  ┌─────────────────┐    │
│  │ WebSocket +     │    │          │  │ WebSocket +     │    │
│  │ Skill #1        │    │          │  │ Skill #1        │    │
│  │ (Monitoring)    │    │          │  │ (Disconnected)  │    │
│  └─────────────────┘    │          │  └─────────────────┘    │
│         │               │          │         │               │
│    :8000 (API)          │          │    :8002 (Sync API)     │
└─────────────────────────┘          └─────────────────────────┘
         ▲                                      │
         │ Requests from                       │
         │ Dashboard/CLI                       │ Receives heartbeat,
         │                                     │ syncs state
         └─────────────────────────────────────┘

If PRIMARY dies:
  1. BACKUP detects no heartbeat (3 failures = 15s timeout)
  2. BACKUP checks: is PRIMARY really dead? (SSH verify)
  3. BACKUP syncs final state from PRIMARY DB
  4. BACKUP stops accepting sync requests
  5. BACKUP starts autonomous trading
  6. Dashboard redirected to BACKUP :8002 → :8000
  7. Customers are served by new PRIMARY (BACKUP)
  8. Seamless failover, <20s downtime
```

---

## Critical Dependencies

### External
- **Binance:** WebSocket feed (ticks), REST API (fallback)
- **PostgreSQL/SQLite:** Order history, positions, candles
- **Time:** NTP sync (for order timestamps, logic)

### Internal Interdependencies

```
AutonomousTrader depends on:
  • WebSocketManager (prices)
  • SmartExecutor (order placement)
  • PaperTradingEngine (simulation)
  • CircuitBreaker (safety gate)
  • RiskGateManager (risk checks)
  • Database (read history, write decisions)

CircuitBreaker depends on:
  • Metrics (trip count, uptime)
  • Database (reason for trip)

HA Failover depends on:
  • Database (source of truth)
  • Heartbeat monitoring (detect PRIMARY down)
  • SplitBrainPrevention (avoid both trading)

Skill #1 (WebSocketStalenessMonitor) depends on:
  • WebSocketManager (access to stream ages)
  • Logging (output metrics + errors)
  • (Nothing else - very minimal coupling)
```

---

## Performance Characteristics

| Layer | Latency | Throughput | Notes |
|-------|---------|-----------|-------|
| **WebSocket Ingest** | 10ms | 1000 ticks/sec | Real-time feed |
| **Skill #1 Detection** | 1000ms (1s check interval) | N/A | Async, background |
| **Signal Generation** | 30ms | 10 signals/sec | Per symbol, per tick |
| **Risk Evaluation** | 10ms | 100 checks/sec | Gate enforcement |
| **Order Execution** | 20ms | 50 orders/sec | Paper trading |
| **Database Write** | 5ms (async) | 100 writes/sec | Doesn't block trading |
| **HA Heartbeat** | <1s round-trip | 0.2 Hz (every 5s) | Health monitoring |

**Bottleneck:** WebSocket feed (if network is slow)  
**Skill #1 Impact:** Detects bottleneck within 15s, triggers recovery

---

## Summary: System Health

A healthy system looks like:

```
✅ WebSocket: Prices flowing every 1-2s
✅ Skill #1: 0 reconnects (or 1-2 per hour on flaky networks)
✅ Bot: Making 10-50 decisions per day
✅ Circuit Breaker: CLOSED state (never OPEN)
✅ Risk Gates: All passing (no violations)
✅ HA: PRIMARY active, BACKUP standby
✅ Database: Latest trade written <100ms ago
✅ Uptime: >99% (only brief maintenance restarts)
```

An unhealthy system shows:

```
❌ WebSocket: No prices for >30s (stale)
❌ Skill #1: 10+ reconnects/hour (network issues)
❌ Bot: Making 0 decisions (paused/crashed)
❌ Circuit Breaker: OPEN state (something went wrong)
❌ Risk Gates: Violations, positions being limited
❌ HA: Both PRIMARY and BACKUP trying to trade (split-brain!)
❌ Database: Last trade >1 minute ago (lagged/crashed)
❌ Uptime: <95% (frequent restarts)
```

---

## Next Steps

1. **Monitor real-time:** Check `/api/monitoring/health/websocket` every hour
2. **Validate Skill #1:** Run 24-hour test (see MONITORING_PLAN_24H.md)
3. **Review logs:** Check `logs/` for staleness events and recovery attempts
4. **Implement Phase 2:** Add circuit breaker reset endpoint (manual recovery)
5. **Scale:** Replicate Skill #1 to investing-platform

**Skill #1 success = No more 3am manual restarts!** 🚀
