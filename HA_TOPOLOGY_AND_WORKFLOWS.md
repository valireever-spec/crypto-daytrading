# HA Topology & Workflows: PRIMARY/BACKUP Architecture

## Part 1: Physical Topology

### Network Layout

```
┌──────────────────────────────────────────────────────────────────────┐
│                           NETWORK DIAGRAM                             │
├──────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  INTERNET                                                             │
│     │                                                                 │
│     ├─ Binance API (WebSocket + REST)                               │
│     │  wss://stream.binance.com                                     │
│     │                                                                 │
│     └─ External Dashboard (browser clients)                         │
│                                                                        │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    LOCAL NETWORK 192.168.3.0/24              │   │
│  │                                                               │   │
│  │  ┌────────────────────────────┐  ┌──────────────────────┐  │   │
│  │  │  PRIMARY MACHINE           │  │  BACKUP MACHINE      │  │   │
│  │  │  192.168.3.1               │  │  192.168.3.25        │  │   │
│  │  │                            │  │                      │  │   │
│  │  │  ┌──────────────────────┐  │  │ ┌──────────────────┐ │  │   │
│  │  │  │ Autonomous Trader    │  │  │ │   STANDBY MODE   │ │  │   │
│  │  │  │ (ACTIVE)             │  │  │ │                  │ │  │   │
│  │  │  │                      │  │  │ │ • Monitor HB     │ │  │   │
│  │  │  │ Trading loop:        │  │  │ │ • Sync DB        │ │  │   │
│  │  │  │ • Get prices         │  │  │ │ • Wait for call  │ │  │   │
│  │  │  │ • Generate signals   │  │  │ │                  │ │  │   │
│  │  │  │ • Place orders       │  │  │ │ If PRIMARY dies: │ │  │   │
│  │  │  │ • Update portfolio   │  │  │ │ → Take over      │ │  │   │
│  │  │  │                      │  │  │ │                  │ │  │   │
│  │  │  └──────────────────────┘  │  │ └──────────────────┘ │  │   │
│  │  │         │                   │  │         │            │  │   │
│  │  │         └─────┬─────────────┼──┼─────────┘            │  │   │
│  │  │               │             │  │                      │  │   │
│  │  │               ▼             │  │                      │  │   │
│  │  │  ┌──────────────────────┐  │  │ ┌──────────────────┐ │  │   │
│  │  │  │ WebSocket Manager    │  │  │ │ WebSocket Mgr    │ │  │   │
│  │  │  │ ✨ Skill #1          │  │  │ │ ✨ Skill #1      │ │  │   │
│  │  │  │                      │  │  │ │ (disconnected)   │ │  │   │
│  │  │  │ • Real-time prices   │  │  │ │                  │ │  │   │
│  │  │  │ • Binance ticks      │  │  │ │ Offline (no      │ │  │   │
│  │  │  │ • Detect staleness   │  │  │ │ Binance feed)    │ │  │   │
│  │  │  │ • Auto-reconnect     │  │  │ │                  │ │  │   │
│  │  │  └──────────────────────┘  │  │ └──────────────────┘ │  │   │
│  │  │         │                   │  │         │            │  │   │
│  │  │         ▼ (to Binance)      │  │         │            │  │   │
│  │  │                            │  │                      │  │   │
│  │  │  ┌──────────────────────┐  │  │ ┌──────────────────┐ │  │   │
│  │  │  │ SQLite Database      │  │◄─┼─┤ SQLite Database  │ │  │   │
│  │  │  │ (PRIMARY DB)         │◄──┼──┤ (BACKUP DB)      │ │  │   │
│  │  │  │                      │  │  │ │                  │ │  │   │
│  │  │  │ • trades table       │  │  │ │ • trades table   │ │  │   │
│  │  │  │ • positions table    │  │  │ │ • positions      │ │  │   │
│  │  │  │ • signals table      │  │  │ │ • signals        │ │  │   │
│  │  │  │ • candles table      │  │  │ │ • candles        │ │  │   │
│  │  │  │                      │  │  │ │ (synced every 5s)│ │  │   │
│  │  │  └──────────────────────┘  │  │ └──────────────────┘ │  │   │
│  │  │         │                   │  │         │            │  │   │
│  │  │         ▼                   │  │         ▼            │  │   │
│  │  │  ┌──────────────────────┐  │  │ ┌──────────────────┐ │  │   │
│  │  │  │ FastAPI Server       │  │  │ │ FastAPI Server   │ │  │   │
│  │  │  │ :8000 (Main API)     │  │  │ │ :8002 (HA sync)  │ │  │   │
│  │  │  │                      │  │  │ │                  │ │  │   │
│  │  │  │ Endpoints:           │  │  │ │ Endpoints:       │ │  │   │
│  │  │  │ • /api/autonomous/*  │  │  │ │ • /api/ha/*      │ │  │   │
│  │  │  │ • /api/monitoring/*  │  │  │ │ • /api/health    │ │  │   │
│  │  │  │ • /api/portfolio/*   │  │  │ │ • /api/sync      │ │  │   │
│  │  │  │ • /api/risk/*        │  │  │ │                  │ │  │   │
│  │  │  │ • /api/ha/heartbeat  │  │  │ │                  │ │  │   │
│  │  │  └──────────────────────┘  │  │ └──────────────────┘ │  │   │
│  │  │         │                   │  │         ▲            │  │   │
│  │  │         │ (main endpoint)    │  │         │ (HA ops)  │  │   │
│  │  │         │                   │  │         │            │  │   │
│  │  └─────────┼───────────────────┼──┼─────────┼────────────┘  │   │
│  │            │                   │  │         │                │   │
│  └────────────┼───────────────────┼──┼─────────┼────────────────┘   │
│               │                   │  │         │                    │
│               │ HTTP/REST         │  │         │                    │
│               │ (user requests)   │  │         │ Heartbeat every 5s  │
│               │                   │  │         │                    │
│               ▼                   ▼  ▼         ▼                    │
│          DASHBOARD                                                  │
│          (Browser)                                                  │
│          • Control panel                                            │
│          • View positions                                           │
│          • See real-time metrics                                    │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Machine Details

#### PRIMARY Machine (192.168.3.1)
```
┌─────────────────────────────────────────────────────┐
│  PRIMARY (ACTIVE - Trading)                         │
│  192.168.3.1                                        │
│  Status: TRADING BOT RUNNING                        │
├─────────────────────────────────────────────────────┤
│                                                     │
│  Core Processes:                                    │
│  ✅ AutonomousTrader (PID: 2847)                   │
│     └─→ Makes trading decisions                   │
│     └─→ Sends heartbeat to BACKUP every 5s        │
│                                                     │
│  ✅ WebSocketManager                              │
│     └─→ Connected to Binance (live prices)        │
│     └─→ ✨ Skill #1 monitoring (detect stale)    │
│                                                     │
│  ✅ FastAPI Server (:8000)                        │
│     └─→ Main API endpoint                         │
│     └─→ Receives user requests                    │
│     └─→ Sends /api/ha/heartbeat to BACKUP        │
│                                                     │
│  ✅ Database (SQLite)                             │
│     └─→ All trades written here                  │
│     └─→ Synced to BACKUP every 5s               │
│                                                     │
│  ✅ Structured Logging                            │
│     └─→ All decisions logged to JSON             │
│     └─→ Stored in /logs/crypto-daytrading.log    │
│                                                     │
│  Connections:                                      │
│  • To Binance: wss://stream.binance.com (live)    │
│  • To BACKUP: HTTP POST to 192.168.3.25:8002     │
│  • To Dashboard: HTTP GET from browser            │
│                                                     │
│  Heartbeat Status:                                │
│  • Sends: POST /api/ha/heartbeat to BACKUP       │
│  • Every: 5 seconds                              │
│  • Expects: 200 OK response                      │
│                                                     │
│  If BACKUP doesn't respond:                      │
│  • PRIMARY ignores (not critical)                │
│  • PRIMARY keeps trading                         │
│  • BACKUP detects PRIMARY is alive (sees HB)    │
│                                                     │
└─────────────────────────────────────────────────────┘
```

#### BACKUP Machine (192.168.3.25)
```
┌─────────────────────────────────────────────────────┐
│  BACKUP (STANDBY - Monitoring)                      │
│  192.168.3.25                                       │
│  Status: MONITORING PRIMARY                        │
├─────────────────────────────────────────────────────┤
│                                                     │
│  Core Processes:                                   │
│  ✅ Heartbeat Monitor (ACTIVE)                    │
│     └─→ Sends GET /api/health to PRIMARY         │
│     └─→ Sends POST /api/ha/heartbeat to PRIMARY  │
│     └─→ Tracks: Last successful heartbeat time   │
│     └─→ Tracks: Failure count (0-3)              │
│     └─→ Every: 5 seconds                         │
│                                                     │
│  ⏸️  AutonomousTrader (PAUSED)                    │
│     └─→ Code loaded but NOT running              │
│     └─→ Threads created but sleeping             │
│     └─→ Ready to start if PRIMARY dies           │
│                                                     │
│  ⏸️  WebSocketManager (DISCONNECTED)              │
│     └─→ Not connected to Binance                 │
│     └─→ ✨ Skill #1 running but unused           │
│     └─→ Prices cache empty                       │
│                                                     │
│  ✅ FastAPI Server (:8002)                        │
│     └─→ HA-only endpoint (for sync)              │
│     └─→ Endpoints: /api/ha/*, /api/health       │
│     └─→ Receives heartbeat from PRIMARY         │
│     └─→ Receives DB sync requests               │
│                                                     │
│  ✅ Database (SQLite - MIRROR)                    │
│     └─→ Receives sync from PRIMARY every 5s     │
│     └─→ Stays in sync with PRIMARY              │
│     └─→ Ready to take over instantly             │
│                                                     │
│  ⏸️  Structured Logging                           │
│     └─→ Can log if needed                        │
│     └─→ Mostly idle (PRIMARY logs everything)   │
│                                                     │
│  Connections:                                      │
│  • To Binance: NONE (disconnected)               │
│  • To PRIMARY: HTTP GET/POST to 192.168.3.1:8000│
│  • To Dashboard: HTTP GET from browser           │
│                                                     │
│  Heartbeat Monitoring:                           │
│  • Sends: GET /api/health to PRIMARY            │
│  • Every: 5 seconds                             │
│  • Expects: 200 OK response with health data    │
│  • If fails: Increment failure_count            │
│  • If failure_count == 3 (15s timeout):         │
│    └─→ Trigger failover sequence                │
│                                                     │
│  If PRIMARY dies:                                │
│  • SSH to PRIMARY: "ps aux | grep bot"          │
│  • Confirm PRIMARY is really dead               │
│  • Read PRIMARY DB (authoritative)              │
│  • Sync to BACKUP DB                            │
│  • START AutonomousTrader                       │
│  • CONNECT WebSocketManager to Binance          │
│  • Switch port: 8002 → 8000 (or DNS update)     │
│  • Resume trading                               │
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

## Part 2: Normal Functional Workflow (PRIMARY Active)

### Timeline: 5-Second Heartbeat Cycle

```
T+0s    PRIMARY starts its work                     BACKUP waits
        ├─→ Get prices from Binance
        ├─→ ✨ Skill #1: Check staleness (every 1s in background)
        ├─→ Generate signals
        ├─→ Evaluate risk gates
        ├─→ Make trading decision
        ├─→ Place order (or hold)
        └─→ Write to database

        Meanwhile (every 5s):
        └─→ Send heartbeat to BACKUP
            POST http://192.168.3.25:8002/api/ha/heartbeat
            Body: {
              "timestamp": "2026-07-03T10:00:00Z",
              "machine_id": "primary",
              "status": "healthy",
              "trading_active": true,
              "last_trade": "2026-07-03T09:59:55Z"
            }

T+0.1s  PRIMARY heartbeat sent                     BACKUP gets request
                                                    ├─→ Record timestamp
                                                    ├─→ Verify PRIMARY alive
                                                    ├─→ Reset failure_count to 0
                                                    └─→ Return 200 OK

T+0-5s  PRIMARY: Continuous trading loop           BACKUP: Standby
        ├─→ Tick 1: Prices in, decision out        ├─→ Monitor heartbeat
        ├─→ Tick 2: Next cycle                     ├─→ Check database
        ├─→ Tick 3: Repeat                         ├─→ Verify sync status
        ├─→ Tick 4: ...                            └─→ Ready to failover
        └─→ Tick 5: Database async writes

T+5s    PRIMARY heartbeat again                    BACKUP verifies
        POST http://192.168.3.25:8002/api/ha/heartbeat
                                                    ├─→ Got response within 2s
                                                    ├─→ Reset failure_count: 0/3
                                                    ├─→ Log: "PRIMARY healthy"
                                                    └─→ Continue monitoring

T+5-10s PRIMARY: Repeat trading cycles             BACKUP: Repeat verification

T+10s   PRIMARY heartbeat (cycle repeats)          BACKUP processes response

[Pattern continues every 5 seconds indefinitely as long as PRIMARY is healthy]

DATABASE SYNC (Every 5s):
  PRIMARY → BACKUP (rsync or DB copy)
  ├─→ Send all new trades written in last 5s
  ├─→ Send updated positions
  ├─→ Send latest signals
  └─→ BACKUP applies to its local DB
      └─→ Now in perfect sync

SKILL #1 BACKGROUND (Every 1s, both PRIMARY & BACKUP):
  
  PRIMARY:
  ├─→ Check WebSocket feed age
  ├─→ If <5s: ✅ Healthy, continue
  ├─→ If 5-15s: ⚠️ Warn, mark stream
  ├─→ If >15s: 🚨 CRITICAL
  │   └─→ Trigger auto-reconnect
  │   └─→ Attempt 1: wait 2s, try
  │   └─→ Attempt 2: wait 4s, try
  │   └─→ Attempt 3: wait 8s, try
  │   └─→ If success: Reset, continue
  │   └─→ If fail 3x: Let circuit breaker know
  │
  BACKUP:
  └─→ Skill #1 runs but no Binance feed
      └─→ Nothing to detect (disconnected)
```

### State Diagram: Normal Operation

```
┌─────────────────────────────────────────────────────────────┐
│  NORMAL WORKFLOW (PRIMARY Healthy, BACKUP Standby)          │
└─────────────────────────────────────────────────────────────┘

PRIMARY Machine State:
┌─────────────────────┐
│  ACTIVE             │
│                     │
│  ✅ Trading        │
│  ✅ WebSocket      │
│  ✅ Sending HB     │
│  ✅ Writing DB     │
└─────────────────────┘

BACKUP Machine State:
┌─────────────────────┐
│  STANDBY            │
│                     │
│  ⏸️  Bot paused     │
│  ⏸️  No WebSocket  │
│  ✅ Receiving HB   │
│  ✅ Syncing DB     │
└─────────────────────┘

Communication Flow (every 5s):
PRIMARY → (HB sent) → BACKUP
PRIMARY → (DB sync) → BACKUP
PRIMARY ← (200 OK) ← BACKUP

Both machines see Binance:
PRIMARY: ✅ Real-time ticks
BACKUP:  ⏸️  Disconnected

Dashboard:
├─→ Points to PRIMARY:8000 (main endpoint)
├─→ User commands go to PRIMARY
├─→ Can view BACKUP status via PRIMARY API
└─→ Can manually failover via API
```

---

## Part 3: Non-Functional Workflow (Failure Scenario)

### Scenario: PRIMARY Dies (Network Partition)

```
┌─────────────────────────────────────────────────────────────┐
│  FAILURE SCENARIO: PRIMARY NETWORK GOES DOWN                │
└─────────────────────────────────────────────────────────────┘

T+0s    PRIMARY still trading normally
        └─→ Autonomous trader running, placing orders

T+5s    BACKUP sends heartbeat to PRIMARY
        POST http://192.168.3.1:8000/api/ha/heartbeat
        └─→ PRIMARY should respond within 2s
        └─→ But PRIMARY is UNREACHABLE (network down)
        
        BACKUP receives: Connection timeout
        └─→ failure_count = 1/3
        └─→ Log: "PRIMARY HB failed, 1/3"
        └─→ Continue monitoring

T+10s   BACKUP sends heartbeat to PRIMARY (retry)
        POST http://192.168.3.1:8000/api/ha/heartbeat
        └─→ Timeout again (PRIMARY still unreachable)
        
        BACKUP receives: Connection timeout
        └─→ failure_count = 2/3
        └─→ Log: "PRIMARY HB failed, 2/3"
        └─→ Still standby (give PRIMARY more time)

T+15s   BACKUP sends heartbeat to PRIMARY (final retry)
        POST http://192.168.3.1:8000/api/ha/heartbeat
        └─→ Timeout again (PRIMARY CONFIRMED DEAD)
        
        BACKUP receives: Connection timeout
        └─→ failure_count = 3/3 (THRESHOLD MET)
        └─→ Log: "🚨 PRIMARY DECLARED DEAD after 3 failures"
        
        BACKUP: Trigger failover sequence
        └─→ Type: NETWORK PARTITION DETECTED
```

### Failover Sequence (T+15s to T+35s)

```
T+15s   BACKUP detects PRIMARY dead (failure_count = 3)
        │
        ├─→ STEP 1: Split-Brain Prevention Check (5s)
        │   ├─ SSH to PRIMARY: "ps aux | grep autonomous"
        │   ├─ Response: Connection refused
        │   ├─ Confirmed: PRIMARY process is really gone
        │   └─→ SAFE TO FAILOVER
        │
        └─→ STEP 2: Read Authoritative Database (5s)
            ├─ PRIMARY DB is source of truth
            ├─ SSH copy PRIMARY DB to BACKUP
            ├─ Verify: All trades, positions, signals copied
            └─→ BACKUP DB now has latest state

T+20s   BACKUP: State sync complete
        │
        └─→ STEP 3: Prepare to Trade (5s)
            ├─ Stop sending heartbeats to PRIMARY
            ├─ Update role: BACKUP → PRIMARY
            ├─ Load trading config
            ├─ Initialize AutonomousTrader (was paused)
            ├─ Initialize WebSocketManager
            ├─ Connect to Binance WebSocket
            └─→ READY TO TRADE

T+25s   BACKUP: Start Trading (5s)
        │
        ├─→ STEP 4: Resume Autonomous Trading
        │   ├─ Start: AutonomousTrader.start()
        │   ├─ Connect: WebSocketManager to Binance
        │   ├─ Subscribe: All symbols
        │   └─→ First prices received
        │
        └─→ STEP 5: Notify Customers
            ├─ Log: "🔄 BACKUP is now PRIMARY"
            ├─ Update metrics: failover_count += 1
            ├─ API endpoint: Moved to BACKUP:8002
            └─→ OR DNS updated to point to BACKUP

T+30s   BACKUP now trading as new PRIMARY
        │
        ├─→ Autonomous trader running
        ├─→ Placing orders on Binance
        ├─→ Writing to database
        └─→ CUSTOMERS NOTICE: Brief lag (~30s) then trading resumes

T+35s   Status: FAILOVER COMPLETE ✅
        │
        ├─→ DATA LOSS: ZERO
        │   └─→ All trades/positions/signals in database
        │
        ├─→ TRADING INTERRUPTED: ~30s
        │   └─→ No orders executed during failover
        │   └─→ Positions held, no forced liquidation
        │
        └─→ SYSTEM STATUS: NEW PRIMARY (ex-BACKUP) RUNNING

T+35s-∞ New PRIMARY (ex-BACKUP) operates normally
         ├─→ Trades autonomously
         ├─→ ✨ Skill #1 monitors WebSocket
         ├─→ Makes decisions
         ├─→ Writes to database
         └─→ Sends logs/metrics

         If original PRIMARY comes back online:
         ├─→ PRIMARY detects it's not the active one
         ├─→ Reads BACKUP DB (now authoritative)
         ├─→ Stops AutonomousTrader
         ├─→ Syncs state from new PRIMARY
         └─→ Becomes new BACKUP (monitoring original PRIMARY-turned-new-PRIMARY)
```

---

## Part 4: Detailed Message Flows

### Heartbeat Exchange (Normal)

```
BACKUP (192.168.3.25)              PRIMARY (192.168.3.1)
        │                                  │
        │  (T+0s)                         │
        │  Send Heartbeat                 │
        ├─────────────────────────────────>
        │  POST /api/ha/heartbeat         │
        │  {                              │
        │    "machine_id": "backup",      │
        │    "timestamp": "2026-07-03...", │
        │    "last_heartbeat_ok": true    │
        │  }                              │
        │                                  │ Process request
        │                                  │ (verify we're alive)
        │                                  │
        │                  (T+0.1s)        │
        │  Response                        │
        │<─────────────────────────────────
        │  200 OK                          │
        │  {                               │
        │    "status": "healthy",         │
        │    "trading": true,             │
        │    "uptime_seconds": 86400      │
        │  }                              │
        │                                  │
        Record timestamp                  │
        failure_count = 0                 │
        Status: PRIMARY ALIVE             │
        │
        └─ Wait 5 seconds, repeat
```

### Heartbeat Failure Sequence

```
BACKUP (192.168.3.25)              PRIMARY (192.168.3.1)
        │                                  │
        │  (T+5s)                         │  [Network partition occurs]
        │  Send Heartbeat                 │  [PRIMARY still running but unreachable]
        ├─────────────────────────────────>
        │  (timeout after 2s)             │  [No response]
        │                                  │
        │<─────────────────────────────────
        │  Connection timeout             │
        │  (no response)                  │
        │                                  │
        Record failure                     │
        failure_count = 1/3               │
        │
        ├─ Log: "PRIMARY unreachable"
        ├─ Status: PRIMARY POSSIBLY DEAD (retrying)
        └─ Wait 5 seconds, retry
           │
           │  (T+10s)
           ├────────────────────────────→ [timeout again]
           │<────────────────────────────
           │  Connection timeout
           │
           failure_count = 2/3
           │
           └─ Wait 5 seconds, final retry
              │
              │  (T+15s)
              ├────────────────────────────→ [timeout again]
              │<────────────────────────────
              │  Connection timeout
              │
              failure_count = 3/3
              │
              └─ TRIGGER FAILOVER SEQUENCE
                 ├─ SSH to PRIMARY (to verify really dead)
                 ├─ Confirmed: PRIMARY unreachable
                 ├─ Begin sync from PRIMARY DB
                 ├─ Start autonomous trading
                 └─ BACKUP becomes PRIMARY
```

### Database Sync Flow (Every 5 seconds)

```
PRIMARY (192.168.3.1)              BACKUP (192.168.3.25)
Database changes:                  Database (mirror):
├─ New trade: BUY BTCUSDT          │
├─ Position: +0.1 BTC              │ Waiting for sync
├─ Signal: RSI=70, action=SELL    │
└─ Candle: 1m OHLCV updated        │
   │                                │
   │ (T+5s sync starts)             │
   │ Send database copy             │
   ├───────────────────────────────>
   │ All trades since last sync     │
   │ All positions updated          │
   │ All signals                    │
   │ All candles (incremental)      │
   │                                │ Apply to mirror DB
   │                                │ Verify integrity
   │                                │ Update local cache
   │                                │
   │<───────────────────────────────
   │ 200 OK - Sync complete
   │
   Both databases now in sync ✅
   │
   └─ Wait 5 seconds, repeat
```

---

## Part 5: Complete State Matrix

### States and Transitions

```
┌──────────────────────────────────────────────────────────────────┐
│                     STATE MATRIX                                  │
├──────────────────────┬──────────────────┬────────────────────────┤
│ PRIMARY STATE        │ BACKUP STATE     │ SYSTEM STATUS          │
├──────────────────────┼──────────────────┼────────────────────────┤
│                                                                    │
│ ✅ ACTIVE           │ ⏸️  STANDBY      │ ✅ NORMAL              │
│   • Trading         │   • Monitoring   │   • Trading happening  │
│   • HB every 5s     │   • Failure=0    │   • DB syncing 5s      │
│   • WebSocket ✅    │   • DB synced    │   • No failover needed │
│   • DB writes       │   • Paused bot   │   • Customer can trade │
│                     │                  │                         │
├──────────────────────┼──────────────────┼────────────────────────┤
│                                                                    │
│ ✅ ACTIVE           │ ⏸️  STANDBY      │ ⚠️  DEGRADED            │
│   • Trading         │   • Monitoring   │   • HB latency high    │
│   • HB delayed      │   • Waiting      │   • One late HB        │
│   • WebSocket ✅    │   • DB sync OK   │   • No action yet      │
│   • DB writes       │   • Ready        │   • Might recover      │
│                     │                  │                         │
├──────────────────────┼──────────────────┼────────────────────────┤
│                                                                    │
│ ❌ UNREACHABLE      │ ⏸️  MONITORING   │ 🚨 CRITICAL FAILURE    │
│   (Network down)    │   • HB failed 1x │   • Failover starting  │
│   • No HB response  │   • Checking...  │   • DB sync in-flight  │
│   • Trading paused? │   • Ready to act │   • ~5-15s no trading  │
│   • WebSocket live? │                  │                        │
│   (but isolated)    │                  │                        │
│                     │                  │                        │
├──────────────────────┼──────────────────┼────────────────────────┤
│                                                                    │
│ ❌ DEAD             │ ✅ PROMOTED      │ ✅ FAILOVER COMPLETE   │
│   (Confirmed down)  │   • Now trading  │   • Trading resumed    │
│   • No SSH response │   • Connected    │   • No data loss       │
│   • HB failed 3x    │   • HB every 5s  │   • ~30s interruption  │
│   • Processes gone  │   • New PRIMARY  │   • Customers active   │
│                     │                  │                        │
├──────────────────────┼──────────────────┼────────────────────────┤
│                                                                    │
│ ✅ RECOVERED        │ ✅ NEW BACKUP    │ ✅ DUAL ACTIVE         │
│   (Came back)       │   • Monitoring   │   • Both available     │
│   • HB responding   │   • New role     │   • New PRIMARY leads  │
│   • WebSocket OK    │   • Sync from    │   • Original PRIMARY   │
│   • Now BACKUP      │     new PRIMARY  │     is standby         │
│   • Monitoring      │                  │                        │
│     new PRIMARY     │                  │                        │
│                     │                  │                        │
└──────────────────────┴──────────────────┴────────────────────────┘
```

---

## Part 6: Decision Trees

### PRIMARY: Health Decision Tree

```
Every 5 seconds, PRIMARY asks itself:

START
  │
  ├─ Am I able to trade?
  │   ├─ YES → Continue trading
  │   │        ├─ Get prices
  │   │        ├─ Generate signals
  │   │        ├─ Check risk gates
  │   │        ├─ Place orders (or hold)
  │   │        └─ Write to database
  │   │
  │   └─ NO → Pause trading
  │           ├─ Log reason
  │           ├─ Still send heartbeat
  │           └─ Wait for recovery
  │
  ├─ Is BACKUP responding?
  │   ├─ YES → ✅ Normal
  │   │        ├─ Send next HB in 5s
  │   │        └─ Continue
  │   │
  │   └─ NO → Not critical
  │           ├─ Keep trading anyway
  │           ├─ DB might not be syncing
  │           ├─ But doesn't matter if I'm alive
  │           └─ Continue
  │
  └─ Should I check anything else?
      ├─ Circuit breaker state?
      │   └─ If OPEN: log, allow exits, deny new entries
      │
      ├─ Skill #1: WebSocket staleness?
      │   └─ If stale >15s: auto-reconnect
      │
      └─ Risk gates?
          └─ If violated: reject new orders
```

### BACKUP: Failover Decision Tree

```
Every 5 seconds, BACKUP checks PRIMARY:

START
  │
  ├─ Can I reach PRIMARY?
  │   ├─ YES → ✅ Primary alive
  │   │        ├─ Record HB success
  │   │        ├─ Reset failure_count = 0
  │   │        ├─ Verify PRIMARY status
  │   │        ├─ Sync database
  │   │        └─ Continue monitoring
  │   │
  │   └─ NO → ⚠️  Connection failed
  │           ├─ Increment failure_count
  │           │
  │           ├─ If failure_count < 3:
  │           │   └─ Retry in 5s (wait for recovery)
  │           │
  │           └─ If failure_count == 3:
  │               ├─ 15s timeout reached
  │               ├─ PRIMARY likely dead
  │               ├─ Verify via SSH (split-brain check)
  │               │
  │               ├─ If SSH also fails:
  │               │   └─ CONFIRMED DEAD → FAILOVER
  │               │       ├─ Copy PRIMARY DB
  │               │       ├─ Start AutonomousTrader
  │               │       ├─ Connect WebSocket
  │               │       └─ Resume trading
  │               │
  │               └─ If SSH succeeds:
  │                   └─ PRIMARY is alive but network split
  │                       ├─ Wait for recovery
  │                       ├─ Don't failover (both might trade!)
  │                       └─ Alert ops team
  │
  └─ Should I take over?
      ├─ YES: PRIMARY dead + SSH confirms + DB synced
      │       └─ Start trading immediately
      │
      └─ NO: Anything uncertain
             └─ Wait for next heartbeat cycle
```

---

## Part 7: Example Timeline: 1 Hour in Normal Operation

```
T+00:00  PRIMARY boots up
         ├─→ Load config
         ├─→ Connect to Binance
         ├─→ ✨ Skill #1 starts monitoring
         ├─→ Start AutonomousTrader
         └─→ First HB sent to BACKUP

T+00:05  Heartbeat 1
         ├─→ PRIMARY: HB response 200 OK
         ├─→ BACKUP: failure_count = 0, alive
         ├─→ DB sync: 3 new trades synced
         └─→ Status: ✅ NORMAL

T+00:10  Trading continues
         ├─→ Price: BTC $61730, ETH $1717
         ├─→ Signal: Strong buy on ETH
         ├─→ Order: Buy 0.1 ETH
         ├─→ PnL: +$15.30 (unrealized)
         └─→ Status: ✅ NORMAL

T+00:15  Heartbeat 2
         ├─→ PRIMARY: HB response 200 OK
         ├─→ BACKUP: failure_count = 0, alive
         ├─→ DB sync: 1 new trade, 2 positions
         └─→ Status: ✅ NORMAL

T+00:20  Skill #1 detects network blip
         ├─→ WebSocket stale for 5s
         ├─→ ✨ Auto-reconnect triggered
         ├─→ Attempt 1: Success
         ├─→ Prices flow again
         └─→ Status: ✅ RECOVERED (no trading halt)

T+00:25  Heartbeat 3
         ├─→ PRIMARY: HB response 200 OK
         ├─→ BACKUP: failure_count = 0, alive
         ├─→ DB sync: 2 new trades, updated positions
         └─→ Status: ✅ NORMAL

T+01:00  End of hour
         ├─→ Total trades: 12
         ├─→ Wins: 8
         ├─→ Losses: 4
         ├─→ Realized PnL: +$127.45
         ├─→ Unrealized PnL: +$89.20
         ├─→ Heartbeats received: 12 (all OK)
         ├─→ Skill #1 reconnects: 0 (network stable)
         ├─→ Circuit breaker trips: 0 (no issues)
         ├─→ Data synced: ✅ All trades in both DBs
         └─→ Status: ✅ HEALTHY (1 hour uptime)
```

---

## Summary: PRIMARY/BACKUP in Crypto-DayTrading

### Geographic/Network Layout
- **PRIMARY**: 192.168.3.1 (main trading machine)
- **BACKUP**: 192.168.3.25 (monitoring/failover machine)
- **Network**: Local LAN (192.168.3.0/24)
- **External**: Binance API (WebSocket + REST)

### Role Assignment
- **PRIMARY**: Active trading bot (makes all decisions)
- **BACKUP**: Standby monitor (watches PRIMARY, ready to take over)

### Normal Functional Workflow
1. PRIMARY generates prices from Binance WebSocket
2. ✨ Skill #1 monitors staleness (background, every 1s)
3. PRIMARY makes trading decisions (every 100ms)
4. PRIMARY writes trades to database
5. PRIMARY sends heartbeat to BACKUP (every 5s)
6. BACKUP receives heartbeat, increments sync
7. BACKUP syncs database from PRIMARY (every 5s)
8. **LOOP:** Repeat steps 1-7 indefinitely

### Non-Functional Workflow (Failover)
1. PRIMARY network dies (or process crashes)
2. BACKUP misses heartbeat #1 (5s timeout)
3. BACKUP misses heartbeat #2 (10s timeout)
4. BACKUP misses heartbeat #3 (15s timeout) → failure_count = 3/3
5. BACKUP runs split-brain check (SSH to PRIMARY)
6. Confirmed: PRIMARY is really dead
7. BACKUP syncs latest database from PRIMARY
8. BACKUP starts AutonomousTrader
9. BACKUP connects to Binance WebSocket
10. **BACKUP now PRIMARY** - resumes trading
11. Total failover time: ~30 seconds

### Result
- ✅ Zero data loss (DB is source of truth)
- ✅ Zero trading strategies needed (automatic)
- ✅ ~30s trading interruption on failover
- ✅ No manual intervention required
- ✅ Customers see brief lag, then trading continues
