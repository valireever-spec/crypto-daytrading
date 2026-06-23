# Paper Trading API Specification — Real Live Prices (Binance WebSocket)

**FR-002 Complete Specification**  
**Status:** Ready for Phase 1 implementation  
**Cost:** $0/month (Binance WebSocket is 100% free)

---

## Overview

We're building a **fully functional paper trading API** that:
- ✅ Connects to Binance WebSocket (real-time prices, 100% free)
- ✅ Simulates order fills at live market prices
- ✅ Uses identical code path as live trading (zero risk during validation)
- ✅ Supports 10-day acceptance test on REAL market conditions
- ✅ Trades 24/7 (crypto markets never close)

---

## Architecture

```
Binance WebSocket (Real Prices)
    ↓ (free subscription)
Paper Trading Engine (Python)
    ├─ Mode: PAPER
    │  └─ Simulates fills (no real orders)
    └─ Mode: LIVE
       └─ Sends real orders to Binance

Same code, different execution path
Flip mode via: TRADING_MODE=paper|live
```

---

## How It Works (Step-by-Step)

### Scenario: Trader Clicks BUY

```
1. Trader sees alert: "BTCUSDT signal 78/100"
2. Trader clicks [BUY] button (FR-005)
3. System calls: /api/paper/order (FR-002)
4. Paper trading engine receives order:
   {
     "symbol": "BTCUSDT",
     "side": "BUY",
     "quantity": 0.05,
     "order_type": "MARKET",
     "mode": "paper"  ← Key difference
   }
5. Engine checks: TRADING_MODE env var
6. If TRADING_MODE="paper":
   - Get current BTC price from WebSocket: $45,500
   - Calculate fill price: $45,500 × 1.001 (0.1% slippage) = $45,545.50
   - Deduct fee: 0.05 × $45,545.50 × 0.1% = €22.77 fee
   - Deduct from cash: €2,277 + €22.77 = €2,299.77
   - Add position: 0.05 BTC @ $45,545.50
   - Log to audit trail: "PAPER_FILL: BTC 0.05 @ $45,545.50"
   - Return: {"status": "FILLED", "price": $45,545.50, "fee": €22.77}
7. If TRADING_MODE="live":
   - Same code, but:
   - Send real order to Binance API (FR-001)
   - Wait for Binance confirmation
   - Log to audit trail: "LIVE_FILL: BTC 0.05 @ $45,XXX"
```

---

## WebSocket Connection

### What We Subscribe To

```python
# Real-time market data (100% FREE)
streams = [
    "btcusdt@kline_1m",      # 1-min candles
    "btcusdt@kline_5m",      # 5-min candles
    "btcusdt@kline_15m",     # 15-min candles
    "btcusdt@trade",         # Trades (for best bid/ask)
    
    # Same for other pairs (ETHUSDT, SOLUSDT, etc.)
    "ethusdt@kline_1m",
    "ethusdt@trade",
    # ... etc
]

# Typical rate: 1 message per second per pair
# For 5 pairs × 4 streams = 20 messages/second
# Binance limit: Millions of messages/second
# Your usage: Negligible
```

### Cost Analysis
```
Binance WebSocket subscription: FREE
API key needed: FREE (generated in your account)
Rate limits: Generous (no cost limits)
Monthly cost: $0

Compared to:
- Stock market data APIs: $50-500/month
- Crypto data providers: $100-1000/month
- Binance premium services: Not needed
```

---

## Execution Flow Diagram

### Paper Mode (Simulation)
```
Trader clicks [BUY]
    ↓
Paper Trading Engine
    ├─ Get current price from WebSocket
    ├─ Simulate fill (add slippage 0.1%)
    ├─ Deduct fee (0.1%)
    ├─ Update virtual positions
    ├─ Log simulated trade
    └─ Return fill confirmation

Reality: Position exists only in memory
         No real order sent to Binance
         Risk: $0
```

### Live Mode (Real Trading)
```
Trader clicks [BUY]
    ↓
Live Trading Engine
    ├─ Get current price from WebSocket
    ├─ Send REAL order to Binance API
    ├─ Wait for Binance confirmation
    ├─ Update real positions
    ├─ Log real trade
    └─ Return fill confirmation

Reality: Position exists on your Binance account
         Real €1,000 at risk
         Risk: Potential loss up to 5% daily cap
```

---

## Key Features

### 1. Real Live Prices (Not Mock or Historical)
```
✅ Every price is from Binance WebSocket (right now)
✅ Fills simulate at actual market conditions
✅ No backtesting (real market, real slippage)
✅ 10-day acceptance test is on LIVE DATA
❌ No testnet mock prices (they're fake)
```

### 2. Same Code Path as Live
```
Paper:
  order → simulate_fill() → log trade → return

Live:
  order → send_to_binance() → log trade → return

Only difference:
  simulate_fill() vs send_to_binance()

Everything else: identical
```

### 3. Realistic Slippage
```
Market order:  +0.1-0.2% slippage
Limit order:   +0.05-0.1% slippage
High volatility: +0.5-1% slippage (optional ATR-based)

Example:
  Price: $45,500
  Market order: $45,500 × 1.001 = $45,545.50 (0.1%)
  High vol: $45,500 × 1.005 = $45,727.50 (0.5%)
```

### 4. Fee Modeling
```
Binance fees: 0.1% (standard)
Paper trading: Same 0.1% deducted
Live trading: Same 0.1% deducted

Example €2,300 order:
  Fee: €2,300 × 0.1% = €2.30
  Net cost: €2,302.30
```

### 5. 24/7 Operation
```
Crypto markets never close
WebSocket streams 24/7
Paper trading runs 24/7
Live trading runs 24/7

Different parameters per time-of-day:
  7-11am: Aggressive
  11am-3pm: Conservative
  3pm-6pm: Close-out
  6pm-7am: Overnight mode
```

---

## API Endpoints (FR-002)

### GET /api/paper/account
```
Returns: {
  "mode": "paper",
  "cash": 7701.23,
  "positions_value": 2298.77,
  "total_equity": 10000.00,
  "daily_pnl": 0.00,
  "total_pnl": 0.00,
  "trades_today": 1,
  "last_update": "2026-06-24T09:30:15Z"
}
```

### POST /api/paper/order
```
Request: {
  "symbol": "BTCUSDT",
  "side": "BUY",
  "quantity": 0.05,
  "order_type": "MARKET",  // or "LIMIT"
  "limit_price": null      // if LIMIT order
}

Response: {
  "order_id": "uuid-abc123",
  "status": "FILLED",
  "filled_price": 45545.50,
  "filled_qty": 0.05,
  "fee": 22.77,
  "timestamp": "2026-06-24T09:30:15Z"
}
```

### GET /api/paper/positions
```
Returns: [
  {
    "symbol": "BTCUSDT",
    "side": "LONG",
    "qty": 0.05,
    "entry_price": 45545.50,
    "current_price": 45500.00,
    "unrealized_pnl": -22.75,
    "unrealized_pnl_pct": -0.05%
  }
]
```

### GET /api/paper/trades
```
Returns: [
  {
    "timestamp": "2026-06-24T09:30:15Z",
    "symbol": "BTCUSDT",
    "side": "BUY",
    "qty": 0.05,
    "price": 45545.50,
    "fee": 22.77,
    "mode": "PAPER",
    "status": "FILLED"
  }
]
```

### POST /api/paper/reset
```
Clears all positions, restores starting balance to €10,000
Used between paper trading test runs
```

### GET /api/paper/status
```
Returns: {
  "mode": "paper",
  "websocket_connected": true,
  "last_price_update": "2026-06-24T09:30:15Z",
  "pairs_subscribed": 5,
  "messages_received_today": 45000
}
```

---

## Test Plan (23 tests total)

### Unit Tests (15 tests)
```
UT-001: WebSocket price arrives → fill simulated correctly
UT-002: BUY order → cash decreases, position added
UT-003: SELL order → position removed, cash increased
UT-004: Fee deduction → 0.1% per trade
UT-005: P&L calculation → realized and unrealized
UT-006: Insufficient cash → order rejected
UT-007: Position size limit → max 5 positions enforced
UT-008: Reset function → clears all, restores balance
UT-009: Mode toggle → paper vs live don't conflict
UT-010: Slippage calculation → matches model (0.1% ± 0.05%)
UT-011: Multiple trades → all logged, P&L correct
UT-012: Negative balance check → never allowed
UT-013: Price edge cases → zero, very high, NaN handling
UT-014: Concurrent orders → queue and process correctly
UT-015: Order cancellation → removes unfilled orders
```

### Integration Tests (8 tests)
```
IT-001: WebSocket connection → established, streaming prices
IT-002: 100 simulated trades → all filled, logged, P&L correct
IT-003: 10-day paper run → >50 trades, >55% win rate (acceptance)
IT-004: Paper vs Live mode → same code path, different output
IT-005: Fee accuracy → 0.1% deducted on every trade
IT-006: Real market conditions → handles gaps, spikes, volatility
IT-007: Network drop → reconnects, resumes without data loss
IT-008: Stress test → 1000 orders in rapid succession
```

---

## Timeline Impact

| Week | Phase | Change |
|------|-------|--------|
| **1** | MVP Core | Build Binance WebSocket + paper engine (this FR-002) |
| **2** | Manual Interface | BUY/SELL buttons use paper engine |
| **2.5** | Strategy Control | Paper engine with strategy allocation |
| **3** | Real-Time | Alerts + paper engine updates in real-time |
| **4** | Analytics | Paper engine logs to analytics |
| **4.5** | Paper Acceptance | 10-day test on REAL Binance prices via WebSocket |
| **5.5-6.5** | HA + Live | Switch to live (TRADING_MODE=live) |

---

## Risk Analysis

### Paper Trading Risk
```
Mode: TRADING_MODE=paper
Execution: Simulated fills in memory
Real money: $0 at risk
Acceptance: 10-day test proves strategy on real prices
```

### Live Trading Risk
```
Mode: TRADING_MODE=live
Execution: Real Binance orders
Real money: €1,000 at risk
Daily cap: -5% maximum loss (€50)
Safety: Same code validated in paper for 10 days first
```

---

## Advantages Over Testnet

| Aspect | Binance Testnet | Our Paper Engine |
|--------|-----------------|-----------------|
| **Prices** | Mock/stale | Real live (WebSocket) |
| **Market conditions** | Unrealistic | Actual (real volatility) |
| **10-day test** | Can't do | Yes, on real prices |
| **Code path** | Different | Identical to live |
| **Switching to live** | Rewrite needed | Flip env var |
| **Cost** | Free | Free (WebSocket) |

---

## Success Criteria

### Phase 1 Acceptance (Week 4.5)
```
✅ WebSocket connection stable 10 days
✅ ≥50 simulated trades
✅ Win rate ≥55%
✅ Positive total P&L
✅ All 23 tests passing
✅ Fee deductions correct
✅ P&L calculations verified
✅ Zero crashes or data loss
```

### Code Quality
```
✅ 100% type hints (mypy 0 errors)
✅ All tests passing
✅ <500ms price-to-alert latency
✅ <100ms order-to-fill latency
✅ Zero hardcoded values
```

---

## Implementation Priority

**CRITICAL PATH (Must ship):**
1. Binance WebSocket connection
2. Paper order simulation
3. Position tracking
4. Fee deduction
5. P&L calculation

**IMPORTANT (For acceptance test):**
6. Trade logging
7. Reset functionality
8. Mode toggle (paper/live)

**NICE-TO-HAVE (Can add later):**
9. Limit order timeout handling
10. Advanced slippage modeling (ATR-based)

---

## Next Steps

**Week 1 implementation:**
1. ✅ Set up Binance WebSocket client (using python-binance library)
2. ✅ Create PaperTradingEngine class with order simulation
3. ✅ Build /api/paper/* endpoints
4. ✅ Write 15 unit tests
5. ✅ Integration test with real WebSocket

**Week 2+:**
- Integrate with manual order buttons (FR-005)
- Add real-time alerts (FR-004)
- Build analytics (FR-010)

---

## Cost Summary

| Component | Cost | Notes |
|-----------|------|-------|
| Binance WebSocket | $0 | 100% free, unlimited |
| Binance API | $0 | 1200 req/min free tier |
| Paper trading | $0 | Simulated only |
| Live trading | 0.1% per trade | Only when you execute real orders |
| **Total monthly (paper)** | **$0** | Risk-free learning |
| **Total monthly (live)** | ~€3-10 | Covers Binance fees only |

---

## Ready to Build? ✅

This specification makes FR-002 crystal clear:
- Real live prices from Binance (free WebSocket)
- Simulated fills (no real money)
- Same code as live (zero risk during validation)
- Full 10-day acceptance test on real market data

**Go time.** 🚀

