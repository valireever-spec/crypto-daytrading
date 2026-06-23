# Crypto Daytrading Platform — Functional Requirements (REDESIGNED)

**Version:** 2.0 (Path A: Decision Support System)  
**Project:** Crypto Daytrading HA System  
**Target Launch:** 2026-08-01 (6-7 weeks, was 4 weeks)  
**Maturity Target:** Production-Ready (60-80% by Phase 1)

---

## Design Philosophy (REVISED)

**OLD (Autopilot):** "Signal → Auto-execute every 15 min → Profit/Loss → Next signal"  
(Trader is passive observer)

**NEW (Decision Support):** "Signal → Real-time alert → Trader decides → Execute → Monitor → Manual adjustments → Analytics → Learn"  
(Trader is active manager, system is intelligent tool)

---

## V-Model Left Side: Requirements Definition

### FR-001: Binance API Integration
- **Description:** Connect to Binance REST API for live price data, order placement, and account status
- **Acceptance Criteria:**
  - GET ticker data (BTCUSDT, ETHUSDT, etc.) with <1s latency
  - POST market and limit orders with execution confirmation
  - GET order status in real-time (pending → filled → cancelled)
  - GET account balance and position status
  - Handle rate limits (1200 req/min for user API)
  - Testnet support for paper trading (no real money)
  - Fallback to backup exchange if Binance unavailable (TBD: second exchange)
  
**Trace:** Design → Unit Test (5 tests) → Integration Test (5 tests)

---

### FR-002: Paper Trading Engine (Real Live Prices via Binance WebSocket)
- **Description:** Fully functional paper trading API using real Binance WebSocket prices (no testnet mock data). Simulates order fills at live market prices without risking capital.
- **Key Insight:** Uses same code path as live trading (FR-001); only difference is simulated fills vs real Binance orders
- **Acceptance Criteria:**
  
  **WebSocket Connection:**
  - Subscribe to Binance WebSocket streams (100% free)
  - Streams: klines (1m, 5m, 15m, 1h), trades, book depth
  - Maintain persistent connection with auto-reconnect
  - Handle connection drops gracefully (pause paper trading until reconnected)
  - Latency: <500ms from price update to fill simulation
  
  **Paper Account Management:**
  - Maintain virtual cash and positions in-memory
  - Starting balance: Configurable (default €10,000 for paper test)
  - Track all transactions: buys, sells, fees, P&L
  - No persistence needed (reset between tests)
  
  **Simulated Order Fills:**
  - When trader clicks BUY (via FR-005):
    - Get current price from WebSocket
    - Calculate fill price: market price × (1 + slippage)
    - Add realistic slippage (0.05-0.1% for limit, 0.1-0.2% for market)
    - Deduct 0.1% trading fee (same as Binance)
    - Mark order as "FILLED"
    - Add to positions
  - When trader clicks SELL:
    - Same process (subtract position, add cash back)
    - Calculate realized P&L
    - Log to audit trail
  
  **Realistic Price Simulation:**
  - Use WebSocket best bid/ask (spread modeling)
  - Market orders fill at ask (buying) or bid (selling)
  - Limit orders fill only within spread (not guaranteed)
  - Slippage increases with volatility (optional: ATR-based)
  
  **Mode Toggle (Paper ↔ Live):**
  - Same codebase for both modes
  - Mode controlled by env var: `TRADING_MODE=paper|live`
  - Switch modes without code change
  - Paper → Live: Just change env var and deploy
  - All logic identical (only WHERE orders are sent differs)
  
  **Paper Trading Endpoints:**
  - `GET /api/paper/account` — Get paper account balance, equity, P&L
  - `POST /api/paper/order` — Place simulated order (calls simulate_fill, not Binance)
  - `GET /api/paper/positions` — Get open positions (simulated)
  - `GET /api/paper/trades` — Get trade history (simulated)
  - `POST /api/paper/reset` — Clear all positions, reset to starting balance
  - `GET /api/paper/status` — Connection status, mode (paper/live), last price update
  
  **Validation & Assertions:**
  - Cash never goes negative (orders rejected if insufficient)
  - Position sizes never exceed account × max position pct
  - Fees deducted correctly (0.1% per trade)
  - P&L calculation correct (realized on close, unrealized on mark-to-market)
  - All trades logged to audit trail
  - Can run 10-day paper test on real market prices (no backtest, real-time)
  
  **Support 24/7 Operation:**
  - Binance WebSocket is 24/7 (crypto never closes)
  - Paper trading runs 24/7 (no market hours)
  - Different parameters per time-of-day (handled by FR-003C)
  
  **Cost:**
  - Binance WebSocket: 100% FREE (no subscription needed)
  - Your system: $0/month operating cost for paper trading
  
**Trace:** Design → Unit Test (15 tests) → Integration Test (8 tests)
- UT-001: Price update arrives via WebSocket, fills are simulated correctly
- UT-002: Buy order → cash decreases, position added, fee deducted
- UT-003: Sell order → position removed, cash increased, fee deducted
- UT-004: Insufficient cash → order rejected
- UT-005: P&L calculation (realized on close, unrealized on mark)
- UT-006: Mode toggle (paper vs live) doesn't break order logic
- UT-007: Reset clears positions, restores starting balance
- UT-008-015: Edge cases (zero price, network drop, rapid fills, etc.)
- IT-001: WebSocket connection established, prices streaming
- IT-002: Full day of paper trading on live prices (no crashes)
- IT-003: 100 simulated trades, all logged correctly
- IT-004: Paper mode fills simulated, live mode sends real orders
- IT-005: 10-day paper acceptance test (>55% win rate on real prices)
- IT-006-008: Stress tests (high volatility, rapid orders, etc.)

---

### FR-003: Real-Time Signal Generation (REDESIGNED)
- **Description:** Generate trading signals in real-time (<500ms latency) using crypto-specific technical indicators
- **Acceptance Criteria:**
  - Calculate RSI (14-period), MACD, Bollinger Bands on OHLCV candles
  - Support multiple timeframes: 1m, 5m, 15m, 1h (user selects which to watch)
  - Return signal score: -100 (strong sell) to +100 (strong buy)
  - Update signal every time candle closes (not every 15 minutes)
  - Latency: <500ms from candle close to signal available
  - Handle edge cases: NaN on insufficient candles, gaps in data
  - WebSocket feed for real-time price updates (sub-second)
  
**Trace:** Design → Unit Test (12 tests) → Integration Test (3 tests)

---

### FR-003B: Dynamic Strategy Allocation (NEW — CRITICAL)
- **Description:** Trader can adjust strategy mix in real-time based on market conditions
- **Acceptance Criteria:**
  - Three strategies available:
    1. **Momentum Scalper:** Fast entry/exit, works in trending markets (7-11am, 3-5pm)
    2. **Mean Reversion:** Bounce trading, works in choppy markets (11am-3pm)
    3. **Grid Trading:** Mechanical, consistent (always 20-30%)
  
  - Trader can adjust allocation via dashboard sliders:
    - Momentum: 0-100% (default: 50% morning, 20% afternoon)
    - Mean Reversion: 0-100% (default: 10% morning, 50% afternoon)
    - Grid: 0-100% (default: 30% always)
    - Sum must equal 100%
  
  - Time-of-day presets:
    - Morning mode (7am-11am): Momentum 60%, Reversion 10%, Grid 30%
    - Afternoon mode (11am-3pm): Momentum 20%, Reversion 60%, Grid 20%
    - Close-out mode (3pm+): Momentum 30%, Reversion 0%, Grid 70%
  
  - Change allocation without restarting system
  - See allocation % on dashboard in real-time
  
**Trace:** Design → Unit Test (8 tests) → Integration Test (3 tests)

---

### FR-003C: Time-Based Parameter Switching (NEW — CRITICAL)
- **Description:** Automatically switch trading parameters based on time of day (no config restart)
- **Acceptance Criteria:**
  - Define parameter sets per time block (can edit without restart):
    ```
    Morning (7am-11am):
      Profit target: +2%
      Stop loss: -2%
      Position size: +3% base
      Signal threshold: ≥70
    
    Afternoon (11am-3pm):
      Profit target: +0.8%
      Stop loss: -1%
      Position size: +1% base
      Signal threshold: ≥60
    
    Close-out (3pm-6pm):
      Profit target: +0.5%
      Stop loss: -0.5%
      Position size: -50% (reduce)
      No new entries: YES
    ```
  
  - Apply parameters automatically when time boundary crossed
  - Show current active parameters on dashboard
  - Allow manual override (trader can change any parameter)
  
**Trace:** Design → Unit Test (6 tests) → Integration Test (2 tests)

---

### FR-004: Real-Time Signal Alerts (NEW — CRITICAL)
- **Description:** Alert trader immediately when signal reaches threshold (<500ms)
- **Acceptance Criteria:**
  - Alert when signal ≥ configured threshold (e.g., ≥70 for strong buy)
  - Alert channels:
    - Dashboard notification (pop-up, visual indicator)
    - Browser push notification (if enabled)
    - Email alert (optional, configurable)
    - SMS alert (optional, configurable)
  
  - Alert includes:
    - Symbol (BTCUSDT, ETHUSDT, etc.)
    - Signal score (78/100)
    - Trend (↑ up, ↓ down, → sideways)
    - Suggested position size (based on account heat)
    - Price at alert time (trader compares to current)
  
  - No automatic execution: Alert only, trader must approve
  - Alert expires after 30 seconds if not acted on (signal may have changed)
  
**Trace:** Design → Unit Test (8 tests) → Integration Test (4 tests)

---

### FR-005: Manual Order Entry & Execution (NEW — CRITICAL)
- **Description:** Trader can click to enter/exit positions manually
- **Acceptance Criteria:**
  - **BUY button** on dashboard:
    - Click → Show entry form
    - Form shows: Symbol, signal score, current price, suggested size
    - Trader can override size (0.5% to 3% of account)
    - Select order type: Market (fast) or Limit (cheaper fees)
    - Click "CONFIRM" → Order placed
    - Execution: <2 seconds from confirm to Binance
  
  - **SELL/EXIT buttons** on active positions:
    - Quick exit options: CLOSE 25% / CLOSE 50% / CLOSE 75% / CLOSE 100%
    - Reason field: "Take profit early" / "Stop loss" / "Exit opportunity"
    - Execution: <2 seconds
  
  - **Order confirmation screen:**
    - Shows order details
    - Shows estimated fee (0.1% × size)
    - Shows impact on account (new cash, new positions)
    - "PLACE ORDER" button to confirm
  
  - **Order status tracking:**
    - Pending: Show in "Orders" panel
    - Filled: Move to "Positions" panel
    - Cancelled: Remove and log
  
**Trace:** Design → Unit Test (10 tests) → Integration Test (5 tests)

---

### FR-006: Manual Stop & Profit Override (NEW — CRITICAL)
- **Description:** Trader can manually adjust or close stops/profit targets
- **Acceptance Criteria:**
  - On each active position, show:
    - Entry price
    - Current price
    - Unrealized P&L
    - Current stop loss (e.g., -2%)
    - Current profit target (e.g., +2%)
  
  - Trader can:
    - **Tighten stop:** "-2% → -1%" (protect gain)
    - **Widen stop:** "-2% → -3%" (give room to recover)
    - **Take profit early:** Close at +1.5% instead of waiting for +2%
    - **Hit stop early:** Close losing trade before -2%
  
  - Use cases:
    - "I know this stop is wrong" → widen stop
    - "Price is at resistance, take profit now" → close early
    - "This trade is choppy, close it before it stops" → close at break-even
  
**Trace:** Design → Unit Test (6 tests) → Integration Test (3 tests)

---

### FR-007: System States & Pause Mechanism (NEW — CRITICAL)
- **Description:** Trader can pause, resume, or change trading mode without restarting
- **Acceptance Criteria:**
  - Four system states (toggle via dashboard):
    1. **TRADING:** Normal mode, all signals generate alerts
    2. **PAUSED:** No new alerts, existing positions hold with active stops
    3. **CLOSE_ONLY:** No new entry alerts, only exit existing positions
    4. **MONITORING:** System watches but no automatic alerts (trader monitors manually)
  
  - Use cases:
    - PAUSED: "Taking lunch break, don't alert me for 1 hour"
    - CLOSE_ONLY: "End of day, close all profitable trades, hold losing ones"
    - MONITORING: "Market is very choppy, I'll watch manually for next 30 min"
    - Back to TRADING: Resume when ready
  
  - No system restart required (state change instant)
  - Show current state on dashboard prominently
  
**Trace:** Design → Unit Test (5 tests) → Integration Test (3 tests)

---

### FR-008: Dynamic Position Sizing (NEW — CRITICAL)
- **Description:** Position size varies (0.5-3%) based on risk, account heat, and streak
- **Acceptance Criteria:**
  - **Base position size:** 1.5% of account (configurable, default)
  
  - **Adjustment factors:**
    1. **Signal strength:** 
       - ≥90 strong signal: +50% size (2.25%)
       - 70-89 normal signal: 1.5% (base)
       - 50-69 weak signal: -50% size (0.75%)
    
    2. **Account heat** (% of account deployed):
       - <30% deployed: +0% size (normal)
       - 30-60% deployed: -25% size
       - >60% deployed: -50% size or reject trade
    
    3. **Win streak:**
       - 1-2 wins: +0% (normal)
       - 3+ wins: +20% per win (up to +100% max)
       - 1+ loss resets streak
    
    4. **Time of day (from FR-003C):**
       - Morning 7-11am: +50% size (aggressive)
       - Afternoon 11am-3pm: -25% size (conservative)
       - Close-out 3pm+: -50% size (reduce)
    
    5. **Volatility adjustment:**
       - High vol (>2% daily move): -25% size
       - Normal vol: 0% (base)
       - Low vol (<0.5% daily move): +15% size
  
  - **Calculation:** base × signal × heat × streak × time × volatility
    - Example: 1.5% × 1.5 × 0.75 × 1.2 × 0.75 × 1.0 = 1.01% final size
  
  - Show recommended size on BUY alert
  - Trader can override (but system shows warning if >3%)
  
**Trace:** Design → Unit Test (12 tests) → Integration Test (4 tests)

---

### FR-009: Real-Time Portfolio Monitoring (REDESIGNED)
- **Description:** Dashboard shows live account state with 1-second updates
- **Acceptance Criteria:**
  - **Account summary** (update every 1 second):
    - Total equity: $11,775
    - Cash: $9,500
    - Positions value: $2,275
    - Deployed %: 19.3% (heat indicator)
    - Daily P&L: +€127 (+1.08%)
    - Total P&L: +€625 (+6.25%)
  
  - **Active positions panel:**
    - Symbol | Entry | Current | Qty | Unrealized P&L | % Gain | Days
    - BTCUSDT | $45,000 | $45,500 | 0.05 | +$25 | +0.56% | 0d
    - ETHUSDT | $2,500 | $2,475 | 1.0 | -$25 | -1% | 1d
    - Quick action: [CLOSE 25%] [CLOSE 50%] [CLOSE 100%]
  
  - **Recent trades panel:**
    - Time | Symbol | Type | Price | Qty | P&L | Duration | Strategy
    - 09:30 | BTC | BUY | 45,000 | 0.05 | — | — | Momentum
    - 09:45 | ETH | BUY | 2,500 | 1.0 | — | — | Reversion
    - 10:15 | BTC | SELL | 45,500 | 0.05 | +$25 | 45 min | Momentum
  
  - **Strategy allocation (live):**
    - Momentum: 50% (Target 60% morning)
    - Reversion: 30% (Target 10% morning)
    - Grid: 20% (Target 30%)
    - Sliders to adjust in real-time
  
  - **System health:**
    - ✓ Binance API: Connected
    - ✓ Main machine: Healthy (last ping 2s ago)
    - ✓ Backup machine: Standby (synced)
    - Last execution: 3s ago
  
**Trace:** Design → Unit Test (8 tests) → Integration Test (6 tests)

---

### FR-010: Per-Strategy Analytics (NEW — CRITICAL)
- **Description:** Dashboard shows which strategies work best (daily learning)
- **Acceptance Criteria:**
  - **Win rate by strategy** (today):
    - Momentum: 5 trades, 4 wins = 80% win rate
    - Reversion: 3 trades, 1 win = 33% win rate
    - Grid: 2 trades, 2 wins = 100% win rate
  
  - **Average trade metrics:**
    - Momentum: Avg win +€12, Avg loss -€8, Profit factor 1.5x
    - Reversion: Avg win +€6, Avg loss -€9, Profit factor 0.67x
    - Grid: Avg win +€3, Avg loss $0, Profit factor infinite
  
  - **Win rate by time of day:**
    - 7-11am: 68% win rate (best)
    - 11am-3pm: 50% win rate (choppy)
    - 3pm-6pm: 75% win rate (evening reversal)
    - Recommendation: Focus on morning & evening, avoid lunch
  
  - **Win rate by pair:**
    - BTCUSDT: 63% win rate
    - ETHUSDT: 59% win rate
    - SOLUSDT: 68% win rate
    - Recommendation: Focus on SOL & BTC
  
  - **Fee analysis:**
    - Total profit (gross): €295
    - Total fees paid: €45 (0.1% per trade × 89 trades)
    - Net profit: €250
    - Recommendation: Fee cost is 15%, consider fewer, bigger trades
  
  - **Update frequency:** Every trade closes (or every 5 minutes)
  
**Trace:** Design → Unit Test (10 tests) → Integration Test (4 tests)

---

### FR-011: Critical Alerts & Runbooks (REDESIGNED)
- **Description:** Alert trader to critical events with actionable runbooks
- **Acceptance Criteria:**
  - **CRITICAL alerts** (SMS + push + email + sound):
    - Exchange down (Binance API timeout >30s)
      - Runbook: Check Binance status page, switch to backup exchange
    - Backup machine failover triggered
      - Runbook: Check main machine, verify no duplicate trades
    - Daily loss >5% (auto-stop all new entries)
      - Runbook: Review losing trades, close shakiest positions, pause trading
    - Position gap (price jumped >5%)
      - Runbook: Check for news, manually review position, consider exit
  
  - **WARNING alerts** (push + email):
    - Account heat >60% (too much deployed)
      - Runbook: Close some positions to reduce exposure
    - Consecutive losses >3 (losing streak)
      - Runbook: Review trade quality, consider pausing strategy
    - Signal quality dropped (strategy <50% win today)
      - Runbook: Switch to different strategy mix
  
  - **INFO alerts** (dashboard notification):
    - Trade filled
    - Position hit profit target
    - Strategy mix changed
    - Mode changed (TRADING → PAUSED)
  
**Trace:** Design → Unit Test (6 tests) → Integration Test (4 tests)

---

### FR-012: Trade Quality Analysis (NEW — CRITICAL)
- **Description:** Understand WHY each trade won or lost (learning)
- **Acceptance Criteria:**
  - On each closed trade, analyze:
    - **Entry quality:** Signal was 78/100 (high quality) ✓
    - **Exit quality:** Exited at +1.2% of +2% possible (60% of max) ~
    - **Hold duration:** Held 45 minutes (matched strategy target) ✓
    - **Fee cost:** Paid €1.80 fees, profit was €6.50 (27% fee ratio)
    - **Alternative exits:** If had held 10 min longer: +€2 more, if exit 5 min earlier: -€1 less
    - **Verdict:** "Good entry, good exit timing, fees reasonable"
  
  - Use for learning:
    - "Which trades am I exiting too early?"
    - "Which times of day do I exit best?"
    - "Do my stops get hit too often?"
    - "Which strategies have best exit timing?"
  
**Trace:** Design → Unit Test (8 tests) → Integration Test (3 tests)

---

### FR-013: HA Redundancy (Dual Machine) (SAME AS BEFORE)
- **Description:** Sentinel Bot HA pattern: main machine trades, backup monitors and takes over
- **Acceptance Criteria:**
  - Heartbeat check every 10 seconds (main → backup)
  - Failover trigger after 3 consecutive missed heartbeats (30s)
  - Backup has read-only copy of positions and P&L
  - No duplicate trades during failover
  - UUID per trade order (inherited by backup)
  - Network tolerant: handle 5-10s latency, temporary disconnects
  
**Trace:** Design → Unit Test (5 tests) → Integration Test (4 tests)

---

### FR-014: Overnight Mode (NEW — NEEDED BEFORE LIVE)
- **Description:** Different parameters and behavior for overnight trading
- **Acceptance Criteria:**
  - At market close (6pm ET), ask trader:
    - "HOLD winners overnight?" (yes/no)
    - "CLOSE all positions?" (yes/no)
    - "PAUSE until morning?" (yes/no)
  
  - If HOLD overnight:
    - Use wider stops: -5% instead of -2%
    - Use wider targets: +5% instead of +2%
    - Maximum 2 positions (reduce overnight risk)
    - Grid trading only (no momentum/reversion overnight)
    - Trader still has manual buttons if needed
  
  - Mode switches back to morning parameters at 7am
  
**Trace:** Design → Unit Test (4 tests) → Integration Test (2 tests)

---

## V-Model: Use Cases & Scenarios

### UC-1: Morning Trading (Trader Learning)
```
User: Wants to learn daytrading with real crypto
System: Provides decision support (alerts, buttons, analytics)
Result: After 2 weeks, trader sees strategy performance, learns what works
```

### UC-2: Daily Optimization
```
User: Reviews morning results at lunch
System: Shows "Momentum 80% win, Reversion 30% win, Grid 100% win"
User: Adjusts allocation: Momentum 70%, Reversion 5%, Grid 25%
Result: Afternoon trading optimized based on live data
```

### UC-3: Crisis Management
```
User: Fed announces rate decision at 2pm
Market: Gaps down 5%
System: Alerts trader (CRITICAL), shows positions, gives runbook
User: Hits "CLOSE ALL" button or reviews each position individually
Result: Can react in seconds, not batch-executed in 15 minutes
```

### UC-4: Weekend Review
```
User: Reviews week's trades Sunday evening
System: Dashboard shows:
- Win rate by strategy (Momentum 68%, Reversion 54%, Grid 61%)
- Best hours (7-11am 68%, 11am-3pm 50%, 3pm-6pm 75%)
- Best pairs (BTC 63%, ETH 59%, SOL 68%)
- Fee impact (45 fees = 15% of profit)
User: Plans next week: Use momentum more, skip lunch hour, focus on SOL
Result: Data-driven optimization, continuous improvement
```

---

## Requirements Count (REDESIGNED)

| Category | Count | Change |
|----------|-------|--------|
| **Core APIs** | 2 (FR-001, FR-002) | Same |
| **Signal & Strategy** | 3 (FR-003, FR-003B, FR-003C) | +1 (was 1) |
| **Order Execution** | 3 (FR-004, FR-005, FR-006) | +2 (was 1) |
| **Risk & Control** | 2 (FR-007, FR-008) | +2 (new) |
| **Monitoring** | 2 (FR-009, FR-010) | +1 (was 1) |
| **Learning** | 1 (FR-012) | +1 (new) |
| **Alerts** | 1 (FR-011) | Same |
| **HA** | 1 (FR-013) | Same |
| **Overnight** | 1 (FR-014) | +1 (new) |
| **TOTAL** | **14** | +8 (was 6) |

---

## Definition of Done

Each requirement is complete when:
- [ ] Design doc reviewed & approved
- [ ] Unit tests written and passing (100% of code paths)
- [ ] Integration tests validate real behavior (Binance testnet)
- [ ] Acceptance criteria met (verified manually)
- [ ] Dashboard updated (if UI requirement)
- [ ] Documentation updated (code comments, runbooks)
- [ ] Security review done (input validation, API key handling)
- [ ] Performance validated (latency <500ms for signals, <2s for orders)

---

## Timeline Impact

| Phase | Week | What's New |
|-------|------|-----------|
| **MVP Core** | 1 | Binance API, paper trading, signal generation (<500ms) |
| **Manual Interface** | 2 | BUY/SELL buttons, manual override, partial exits |
| **Strategy Control** | 2.5 | Multi-strategy, dynamic allocation, time-based params |
| **Portfolio Monitoring** | 3 | Real-time dashboard, live P&L, positions panel |
| **Real-Time Alerts** | 3.5 | <500ms alerts to trader, pause/resume, modes |
| **Dynamic Sizing** | 4 | Account heat tracking, dynamic position sizing |
| **Analytics** | 4.5 | Per-strategy win rate, time-of-day analysis, trade quality |
| **Paper Acceptance** | 5 | 10-day paper test: >55% win rate required |
| **HA Setup** | 5.5 | Dual machine, failover, heartbeat, UUID dedup |
| **Overnight & Live** | 6 | Overnight mode, SMS alerts, fallback exchange |
| **Live Acceptance** | 6.5 | 2-week paper test with €1,000 |

**Timeline: 6-7 weeks (realistic, was 4 weeks**

