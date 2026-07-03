# Component Interaction Flows

## 1. Normal Trading Loop (Every 100ms)

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         TRADING TICK (100ms)                             │
└──────────────────────────────────────────────────────────────────────────┘

T+0ms    ┌─────────────────────┐
         │ AutonomousTrader    │
         │ Main Loop           │
         └────────┬────────────┘
                  │
                  ▼
T+5ms    ┌─────────────────────┐
         │ Get Latest Prices   │◄────── WebSocketManager
         │ prices = {          │        ├─ BTCUSDT: 61730.65 (age: 0.2s)
         │   'BTCUSDT': 61730  │        ├─ ETHUSDT: 1717.22  (age: 0.1s)
         │   'ETHUSDT': 1717   │        └─ BNBUSDT: 562.74   (age: 0.3s)
         │ }                   │
         └────────┬────────────┘
                  │
                  ▼
T+10ms   ┌─────────────────────┐
         │ Generate Signals    │◄────── Historical candles from DB
         │ for each symbol     │        RSI, MACD, Bollinger Bands
         │ signals = {         │        ML prediction score
         │   BTCUSDT: HIGH,    │        Sentiment analysis
         │   ETHUSDT: MEDIUM   │
         │ }                   │
         └────────┬────────────┘
                  │
                  ▼
T+20ms   ┌─────────────────────┐
         │ Evaluate Risk Gates │◄────── RiskGateManager
         │ ✓ Drawdown OK       │        ├─ Max Drawdown: -2% (OK < -5%)
         │ ✓ Position size OK  │        ├─ Notional: $8k (OK < $10k)
         │ ✓ Correlation OK    │        └─ Correlation: 0.6 (OK < 0.8)
         │ ✓ Circuit breaker   │
         │   CLOSED            │        CircuitBreaker status:
         │                     │        ├─ State: CLOSED (normal trading)
         └────────┬────────────┘        └─ Trips: 0 (today)
                  │
                  ▼
T+30ms   ┌─────────────────────┐
         │ Decision Logic      │
         │                     │
         │ if (BTCUSDT signal  │
         │  high) && all       │
         │  gates pass:        │
         │   action = BUY      │
         │   size = 0.1 BTC    │
         │                     │
         └────────┬────────────┘
                  │
                  ▼
T+40ms   ┌─────────────────────┐
         │ SmartExecutor       │◄────── Safety checks:
         │ Place Order         │        ├─ Verify prices <10s old
         │                     │        ├─ Verify position valid
         │ Pre-flight:         │        └─ Verify account balance
         │ ✓ Prices fresh      │
         │ ✓ Position valid    │        Then simulate in:
         │ ✓ Account OK        │        PaperTradingEngine
         │                     │        └─ APPROVED: Order placed
         └────────┬────────────┘
                  │
                  ▼
T+50ms   ┌─────────────────────┐
         │ Log Decision        │◄────── Database (async write)
         │ {                   │        StructuredLogger (JSON)
         │  timestamp,         │        Metrics collected
         │  symbol,            │
         │  direction,         │        Decision recorded:
         │  size,              │        ├─ Symbol: BTCUSDT
         │  price,             │        ├─ Direction: BUY
         │  confidence,        │        ├─ Size: 0.1
         │  reason             │        ├─ Price: 61730
         │ }                   │        ├─ Confidence: 0.85
         │                     │        └─ Reason: RSI+MACD aligned
         └────────┬────────────┘
                  │
                  ▼
T+100ms  ┌─────────────────────┐
         │ Update Metrics      │
         │ orders_placed += 1  │
         │ pnl += realized     │
         │                     │
         │ Next Tick           │
         │ (loop continues)    │
         └─────────────────────┘
```

---

## 2. WebSocket Price Update Flow

```
Binance API
    │
    ├─ Stream: BTCUSDT@trade
    │  Message: {
    │    "stream": "btcusdt@trade",
    │    "data": {
    │      "p": "61730.65",    ◄─── price
    │      "q": "0.001",       ◄─── quantity
    │      "T": 1720000000000  ◄─── timestamp
    │    }
    │  }
    │
    ▼
┌──────────────────────────────┐
│ WebSocketManager             │
│ _ws_listen() async loop      │
└──────────────────────────────┘
    │
    ├─→ Parse JSON message
    │
    ├─→ Extract: symbol, price, timestamp
    │
    ├─→ Update prices cache
    │   prices['BTCUSDT'] = {
    │     price: 61730.65,
    │     timestamp: datetime.utcnow(),
    │     age: 0.1s,
    │     source: 'websocket'
    │   }
    │
    ├─→ Update last_ws_message timestamp
    │
    └─→ Call all registered callbacks
            │
            ├─→ Callback 1: ✨ WebSocketStalenessMonitor
            │              on_price_update('BTCUSDT')
            │              └─→ Update StreamHealth
            │                  └─→ Reset: last_update_time, is_healthy
            │                  └─→ Reset reconnect_attempts to 0
            │
            ├─→ Callback 2: Dashboard WebSocket push
            │              └─→ Notify browser: new BTCUSDT price
            │
            └─→ Callback 3: AutonomousTrader
                           └─→ Wakeup signal (trigger next tick)
```

---

## 3. Skill #1: Staleness Detection & Recovery

```
┌─────────────────────────────────────────────────────────────────────┐
│  ✨ WebSocketStalenessMonitor (Background task, every 1s)          │
└─────────────────────────────────────────────────────────────────────┘

T+0s     Check BTCUSDT stream
         ├─ last_update: 0.5s ago
         ├─ staleness: 0.5s
         └─ Status: ✅ HEALTHY (< 5s)
         
T+1s     Check BTCUSDT stream
         ├─ last_update: 1.5s ago
         ├─ staleness: 1.5s
         └─ Status: ✅ HEALTHY (< 5s)

T+2s     Check BTCUSDT stream
         ├─ last_update: 2.5s ago
         ├─ staleness: 2.5s
         └─ Status: ✅ HEALTHY (< 5s)

         [... WebSocket dies ...]

T+10s    Check BTCUSDT stream
         ├─ last_update: 10.0s ago (last tick was 10s ago)
         ├─ staleness: 10.0s
         └─ Status: ⚠️  WARN (> 5s but < 15s)
         
         Log: "⚠️  [BTCUSDT] Price stale: 10.0s"
         metrics.staleness_warnings += 1

T+15s    Check BTCUSDT stream
         ├─ last_update: 15.0s ago
         ├─ staleness: 15.0s
         ├─ Status: 🚨 CRITICAL (>= 15s)
         │
         └─→ Mark stream as unhealthy
             └─→ Call _attempt_reconnect('BTCUSDT', stream)

T+15s    RECONNECT ATTEMPT 1/3
         ├─ Calculate backoff: 2^0 * 2.0 = 2.0s
         ├─ Log: "🔄 Reconnect attempt 1/3, waiting 2.0s"
         ├─ metrics.reconnect_attempts += 1
         │
         ├─ [Sleep 2.0s]
         │
         └─→ Call ws_manager.reconnect('BTCUSDT')
             ├─ Close WebSocket
             ├─ Reset connection state
             └─ Try _connect_websocket()
                 ├─ Reconnect to Binance
                 ├─ Re-subscribe to BTCUSDT@trade
                 ├─ Start _ws_listen() again
                 └─→ IF SUCCESS:
                     ├─ Log: "✅ Reconnect successful after 1 attempts"
                     ├─ stream.is_healthy = True
                     ├─ stream.reconnect_attempts = 0
                     ├─ stream.last_update_time = now()
                     └─ metrics.reconnect_successes += 1
                     
                     [Prices start flowing again]

T+17s    Next check: prices flowing again (age: 2s)
         └─→ Status: ✅ HEALTHY
             └─→ No further action needed
```

**What if reconnect fails?**

```
T+15s    RECONNECT ATTEMPT 1/3 → FAIL
         [wait 2s]
         
T+17s    RECONNECT ATTEMPT 2/3 (attempt 2 of 3)
         ├─ Calculate backoff: 2^1 * 2.0 = 4.0s
         ├─ Log: "🔄 Reconnect attempt 2/3, waiting 4.0s"
         │
         ├─ [Sleep 4.0s]
         │
         └─→ Try reconnect → FAIL (Binance still unreachable)
         
T+21s    RECONNECT ATTEMPT 3/3
         ├─ Calculate backoff: 2^2 * 2.0 = 8.0s
         ├─ Log: "🔄 Reconnect attempt 3/3, waiting 8.0s"
         │
         ├─ [Sleep 8.0s]
         │
         └─→ Try reconnect → FAIL (Persistent issue)
         
T+29s    GIVE UP - Exhausted all retries
         ├─ Log: "❌ [BTCUSDT] WebSocket unrecoverable after 3 attempts"
         ├─ Log: "Deferring to circuit breaker"
         ├─ metrics.reconnect_failures += 1
         │
         └─→ Return to main loop
             └─→ AutonomousTrader sees stale prices >30s
                 ├─ Circuit Breaker detects stale data
                 └─→ OPENS: Stop new entries (protection mode)
```

---

## 4. Circuit Breaker State Transitions

```
                      NORMAL OPERATION
                            │
                            ▼
                      ┌──────────────┐
                      │   CLOSED     │  ✅ Normal trading
                      │              │  ├─ Allow BUY/SELL
                      └───────┬──────┘  ├─ Check all gates
                              │        └─ Make decisions
          Failure triggered   │
          (WebSocket stale    │
           >30s, or risk      │
           gate violated)     │
                      │
                      ▼
                ┌──────────────┐
                │     OPEN     │  🚨 Protection mode
                │              │  ├─ STOP new entries
                ├─ Reason:     │  ├─ ALLOW exits (close positions)
                │   "WebSocket │  └─ Log reason + timestamp
                │    stale>30s"│
                ├─ Trip count: │  Wait for recovery timeout
                │   (incremented)
                └───────┬──────┘  (default: 20s)
                        │
          After timeout │
          OR manual     │
          reset via     │
          /admin/reset  │
                        ▼
                ┌──────────────┐
                │  HALF_OPEN   │  🟡 Recovery test
                │              │  ├─ Allow small entries (10% size)
                ├─ Testing:    │  ├─ Monitor success rate
                │   Can we     │  └─ Log test results
                │   trade?     │
                └───────┬──────┘
                        │
          If recovery   │
          test          │
          succeeds      │
          (no errors)   │
                        ▼ (Success)
                      CLOSED (fully recovered)
                      
          If recovery   ▲
          test fails    │
          (error)       │ (Failure)
                        │
                        └─ Back to OPEN
```

---

## 5. HA Failover Detection & Switchover

```
PRIMARY: Trading normally          BACKUP: Standby mode
    │                                  │
    ├─→ Send heartbeat            ◄─── Monitor
       every 5s to BACKUP             │
    │                                  │
    ├─→ /api/ha/heartbeat         ◄─── Success: Record timestamp
       Response: "healthy"            │
    │                                  │
    │  [Network issue]                 │
    │  PRIMARY still running           │
    │  But BACKUP can't reach it       │
    │                                  │
    ├─→ Send heartbeat            ◄─── FAIL #1
       /api/ha/heartbeat              │
       Response: timeout              │
    │                                  │
    │  [5s pass]                       │
    │                                  │
    ├─→ Send heartbeat            ◄─── FAIL #2
       /api/ha/heartbeat              │
       Response: timeout              │
    │                                  │
    │  [5s pass]                       │
    │                                  │
    ├─→ Send heartbeat            ◄─── FAIL #3
       /api/ha/heartbeat              │
       Response: timeout              │
    │                                  │
    │  BACKUP fails 3 times = 15s      │
    │  BACKUP concludes:               ▼
    │  PRIMARY is DEAD                 ┌─────────────────────┐
    │                                   │ SPLIT-BRAIN CHECK   │
    │                                   │                     │
    │                                   │ SSH to PRIMARY      │
    │                                   │ Command:            │
    │                                   │ "ps aux | grep bot" │
    │                                   │                     │
    │                                   │ Response:           │
    │                                   │ "Connection denied" │
    │                                   │                     │
    │                                   │ Confirmed: PRIMARY  │
    │                                   │ is actually dead    │
    │                                   └──────────┬──────────┘
    │                                              │
    │                                              ▼
    │                                   ┌─────────────────────┐
    │                                   │ FAILOVER SEQUENCE   │
    │                                   │                     │
    │                                   │ 1. Read PRIMARY DB  │
    │                                   │    (authoritative)  │
    │                                   │                     │
    │                                   │ 2. Sync to BACKUP   │
    │                                   │    DB               │
    │                                   │                     │
    │                                   │ 3. Stop BACKUP      │
    │                                   │    heartbeat task   │
    │                                   │                     │
    │                                   │ 4. Start BACKUP     │
    │                                   │    autonomous       │
    │                                   │    trader           │
    │                                   │                     │
    │                                   │ 5. BACKUP becomes   │
    │                                   │    PRIMARY          │
    │                                   └──────────┬──────────┘
    │                                              │
    │                                              ▼
    │                                   Trading resumes
    │                                   on BACKUP (now PRIMARY)
    │
    │  PRIMARY comes back online
    │  [Network restored]
    │  
    └─→ Notices:
       ├─ HA state shows BACKUP=PRIMARY
       ├─ Reads BACKUP DB (now authoritative)
       └─ Syncs state from BACKUP → PRIMARY
           ├─ Updates its DB with latest trades
           ├─ Stops autonomous trader
           └─→ Becomes standby (new BACKUP)
```

---

## 6. Request Flow: Dashboard to Bot

```
BROWSER Dashboard
    │
    ├─ User clicks: "Place BUY order for BTCUSDT"
    │
    ▼
┌──────────────────────────────┐
│ JavaScript sends HTTP request │
│ POST /api/autonomous/order   │
│ {                            │
│   symbol: 'BTCUSDT',        │
│   direction: 'BUY',         │
│   quantity: 0.1             │
│ }                            │
└─────────────┬────────────────┘
              │
              ▼
        [API Load Balancer]
        (Routes to PRIMARY:8000)
              │
              ▼
┌──────────────────────────────┐
│ FastAPI Router               │
│ /api/autonomous/order        │
└─────────────┬────────────────┘
              │
              ├─→ Verify auth token
              │
              ├─→ Validate request:
              │   ├─ symbol exists
              │   ├─ quantity > 0
              │   └─ direction in [BUY, SELL]
              │
              ▼
┌──────────────────────────────┐
│ AutonomousTrader             │
│ queue_manual_order()         │
└─────────────┬────────────────┘
              │
              ├─→ Add to pending orders queue
              │
              ▼
        [Next trading tick, 100ms later]
              │
              ├─→ Process queue
              ├─→ Run through SmartExecutor
              └─→ Execute (or reject with reason)
              │
              ▼
┌──────────────────────────────┐
│ Database                     │
│ INSERT into orders table     │
│ status: 'pending' → 'filled' │
└──────────────────────────────┘
              │
              ▼
┌──────────────────────────────┐
│ HTTP Response to Dashboard   │
│ {                            │
│   "status": "success",      │
│   "order_id": 12345,        │
│   "price_executed": 61730.5,│
│   "quantity": 0.1,          │
│   "pnl": 0                  │
│ }                            │
└──────────────────────────────┘
              │
              ▼
        BROWSER Dashboard
        ├─ Update portfolio view
        ├─ Show new position: 0.1 BTC @ 61730.5
        └─ Refresh PnL display
```

---

## Summary: Component Dependency Graph

```
User/Dashboard
    │
    ▼
    API Layer (30+ endpoints)
    │
    ├─→ Monitoring Router
    │   └─→ HealthChecker
    │       └─→ Multiple health checks
    │
    ├─→ Autonomous Router
    │   └─→ AutonomousTrader
    │       │
    │       ├─→ WebSocketManager
    │       │   └─→ ✨ WebSocketStalenessMonitor (Skill #1)
    │       │
    │       ├─→ Signal generators (Strategy, ML, Sentiment)
    │       │   └─→ Database (candles, history)
    │       │
    │       ├─→ SmartExecutor
    │       │   └─→ PaperTradingEngine
    │       │
    │       ├─→ CircuitBreakerV2
    │       │
    │       └─→ RiskGateManager
    │
    ├─→ HA Router
    │   └─→ Heartbeat monitor
    │       ├─→ Database (sync state)
    │       └─→ SplitBrainPrevention
    │
    └─→ Risk Router
        └─→ RiskGateManager
            └─→ Database

Everything writes to:
├─ Database (SQLite)
├─ Structured Logging (JSON)
└─ Metrics Collector
```

This maps the data flows, decision points, and safety gates throughout the system.
