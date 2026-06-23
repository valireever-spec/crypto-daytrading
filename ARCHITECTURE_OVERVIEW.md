# Architecture Overview — Crypto Daytrading HA System

**Phase:** 0 (Design)  
**Status:** Design complete, ready for Phase 1 implementation

---

## System Architecture (High Level)

```
┌──────────────────────────────────────────────────────────────┐
│                     BINANCE EXCHANGE (24/7)                   │
│         Testnet (Paper) or Mainnet (Live Trading)            │
└────────────────────┬─────────────────────────────────────────┘
                     │
        ┌────────────┼────────────┐
        │                         │
        ▼                         ▼
   ┌─────────────┐          ┌─────────────┐
   │ MAIN BOX    │◄────────►│  BACKUP BOX │
   │  (Active)   │heartbeat │  (Standby)  │
   └─────────────┘ 10s      └─────────────┘
        │                         │
        │                         │
   EXECUTES ◄─ Failover on ───► MONITORS
   TRADES   3 missed hbeats      MAIN
```

---

## Main Machine (Active Trading)

```
MAIN MACHINE (Active)
═══════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────┐
│                   FASTAPI HTTP SERVER                        │
│  (API: /trades, /positions, /signals, /health, /execute)    │
└─────────────────┬───────────────────────────────────────────┘
                  │
    ┌─────────────┴─────────────┐
    │                           │
┌───▼─────────────┐     ┌──────▼────────────────┐
│ EXCHANGE LAYER  │     │ EXECUTION ENGINE      │
│ (Binance API)   │     │ ────────────────────  │
├─────────────────┤     │ • Order Manager       │
│ • Testnet       │     │ • Position Tracker    │
│ • Market data   │     │ • P&L Calculator      │
│ • Order mgmt    │     │ • Risk Enforcer       │
│ • Rate limiting │     │ • Audit Trail         │
│ • Retry logic   │     │                       │
└─────────────────┘     └──────────────────────┘
        ▲                        ▲
        │                        │
        └────────┬───────────────┘
                 │
    ┌────────────▼────────────┐
    │  STRATEGY LAYER         │
    │  ────────────────────   │
    │ • Momentum Scalper      │
    │ • Mean Reversion        │
    │ • Grid Trading          │
    │ • Custom strategies     │
    │                         │
    │ Signal generation:      │
    │ • RSI (14-period)       │
    │ • MACD                  │
    │ • Bollinger Bands       │
    │ • Multi-timeframe       │
    └────────────────────────┘
        ▲           │
        │           │ Candles
        │           │ (OHLCV)
        └───────────┘

Execution Loop (Every 15 min):
  1. Fetch latest OHLCV candles (1m, 5m, 15m, 1h)
  2. Calculate indicators (RSI, MACD, Bollinger)
  3. Generate signals per strategy
  4. Mark existing positions to market
  5. Check exit conditions (profit/stop/time)
  6. Close positions if conditions met
  7. Scan for entry signals on available symbols
  8. Open new positions if capital available
  9. Log all trades to audit trail
  10. Update P&L, send heartbeat to backup
```

---

## Backup Machine (Standby → Failover)

```
BACKUP MACHINE (Standby)
═══════════════════════════════════════════════════════════

MONITORING:
  • Listens for heartbeat from main
  • Every 10 seconds: "Is main alive?"
  • Tracks: 3 consecutive missed heartbeats

FAILOVER TRIGGER (30 seconds):
  • Miss 1: Still OK
  • Miss 2: Still OK
  • Miss 3: FAILOVER!

WHEN MAIN FAILS:
  1. Backup reads last audit trail
  2. Reconstructs current positions
  3. Uses UUID deduplication to prevent double trades
  4. Takes over execution at next candle
  5. Logs all actions to same audit trail
  6. Operates identically to main

RECOVERY:
  When main comes back:
  1. Main checks audit trail
  2. Syncs positions with backup
  3. Resumes as primary
  4. Backup returns to standby
```

---

## Data Flow — Single Trade Execution

```
┌─────────────────┐
│  Get candle     │
│  price data     │
│  (OHLCV)        │
└────────┬────────┘
         │
┌────────▼────────┐
│  Calculate      │
│  indicators     │
│  (RSI, MACD,    │
│  Bollinger)     │
└────────┬────────┘
         │
┌────────▼────────┐
│  Strategy       │
│  generates      │
│  signal         │
│  (-100 to +100) │
└────────┬────────┘
         │
┌────────▼────────────────────┐
│  Check conditions:          │
│  • Signal strength > 70?    │
│  • Cash available?          │
│  • Positions < max (5)?     │
│  • Position size OK (<2%)?  │
└────────┬───────────────────┘
         │
    ┌────┴────┐
    │ YES/NO? │
    └────┬────┘
    NO   │   YES
        │
    SKIP│ ┌─────────────────────┐
        │ │ Place order on      │
        │ │ Binance API         │
        │ │ (market order)      │
        │ │                     │
        │ │ Wait for fill       │
        │ │ (usually <1s)       │
        └─┤                     │
          │ ORDER FILLED        │
          └──────────┬──────────┘
                     │
          ┌──────────▼──────────┐
          │  Log to audit trail │
          │  {                  │
          │   timestamp,        │
          │   symbol,           │
          │   qty,              │
          │   price,            │
          │   side,             │
          │   entry_signal,     │
          │   uuid              │
          │  }                  │
          └──────────┬──────────┘
                     │
          ┌──────────▼──────────┐
          │  Send to backup     │
          │  (via heartbeat)    │
          │  for dedup check    │
          └─────────────────────┘

          ┌──────────────────────┐
          │  Next candle (15min) │
          │                      │
          │  Check exit:         │
          │  • Price > +1.5%?    │
          │    → SELL (profit)   │
          │  • Price < -2.0%?    │
          │    → SELL (stop)     │
          │  • Held 3+ days?     │
          │    → SELL (time)     │
          └──────────────────────┘
```

---

## State Management & Failover

```
MAIN MACHINE CRASHES
┌──────────────────────────────────────────────┐
│  Backup reads audit trail from file          │
│                                              │
│  trades.jsonl (append-only):                 │
│  {timestamp, symbol, qty, price, uuid}       │
│  {timestamp, symbol, qty, price, uuid}       │
│  {timestamp, symbol, qty, price, uuid}       │
│  [LAST LINE = most recent trade]             │
│                                              │
│  Reconstruct state:                          │
│  ✓ Position 1: BTCUSDT 0.5 (from trade 1)  │
│  ✓ Position 2: ETHUSDT 2.0 (from trade 2)  │
│  ✓ Cash: $9,500 (remaining)                 │
└──────────────────────────────────────────────┘

NEXT CANDLE (15 min)
┌──────────────────────────────────────────────┐
│  Backup executes trade on best signal        │
│  • Generates same signal (same data)         │
│  • Places order on Binance                   │
│  • Generates UUID v4                         │
│  • Logs: {timestamp, symbol, uuid}           │
│                                              │
│  If main ALSO placed same trade:             │
│  • Backup checks UUID in audit trail         │
│  • UUID already there? SKIP (duplicate)      │
│  • UUID new? EXECUTE                         │
└──────────────────────────────────────────────┘

MAIN MACHINE RECOVERS
┌──────────────────────────────────────────────┐
│  Main boots, reads audit trail               │
│  • Sees trades from backup (UUID markers)    │
│  • Syncs positions with what backup did      │
│  • Resumes as primary                        │
│  • Sends "I'm back" signal                   │
│  • Backup returns to passive                 │
└──────────────────────────────────────────────┘
```

---

## Module Dependencies

```
CORE LAYER
├─ exchange/binance.py         (Binance API)
├─ exchange/paper.py           (Paper trading simulator)
└─ core/config.py              (Configuration, validation)

STRATEGY LAYER
├─ strategies/base.py          (Base strategy class)
├─ strategies/momentum.py       (Momentum scalper)
├─ strategies/mean_reversion.py (Mean reversion)
├─ strategies/grid.py          (Grid trading)
└─ strategies/registry.py       (Strategy loader)

EXECUTION LAYER
├─ execution/order_manager.py   (Order placement, tracking)
├─ execution/portfolio.py       (Position tracking, P&L)
└─ execution/risk.py            (Risk enforcement, daily cap)

FAILOVER LAYER
├─ failover/ha_monitor.py       (Heartbeat, failover)
└─ failover/state_sync.py       (Position/audit sync)

API LAYER
├─ api/main.py                 (FastAPI app)
├─ api/routers/trades.py       (GET /api/trades)
├─ api/routers/positions.py    (GET /api/positions)
├─ api/routers/signals.py      (GET /api/signals)
├─ api/routers/health.py       (GET /api/health)
└─ api/schemas.py              (Pydantic models)

LOGGING LAYER
└─ core/logging.py             (JSON logging, audit trail)
```

---

## Data Models

### Trade (Immutable, Append-Only)

```python
{
  "timestamp": "2026-07-15T09:30:15Z",
  "symbol": "BTCUSDT",
  "side": "BUY",              # BUY or SELL
  "qty": 0.05,
  "price": 45000.50,
  "order_type": "MARKET",     # MARKET or LIMIT
  "order_id": "uuid-abc123",  # Unique per order
  "strategy": "momentum",
  "signal_score": 78,         # -100 to +100
  "reason": "RSI > 70",
  "machine_id": "main",       # main or backup
  "filled_at": "2026-07-15T09:30:16Z",
  "status": "FILLED"
}
```

### Position (Current State)

```python
{
  "symbol": "BTCUSDT",
  "side": "LONG",             # LONG or SHORT
  "qty": 0.05,
  "entry_price": 45000.50,
  "entry_time": "2026-07-15T09:30:16Z",
  "current_price": 45500.00,
  "unrealized_pnl": 24.98,
  "unrealized_pnl_pct": 0.56,
  "days_held": 0,
  "signal_at_entry": 78
}
```

### Account (Current Balance)

```python
{
  "cash": 9500.00,
  "positions_value": 2275.00,
  "total_equity": 11775.00,
  "daily_pnl": 25.00,
  "daily_pnl_pct": 0.21,
  "total_pnl": 625.50,
  "total_pnl_pct": 6.25,
  "daily_loss_pct": 0.0,
  "trades_today": 3,
  "trades_total": 127,
  "win_rate": 0.56,
  "max_concurrent_positions": 3,
  "max_position_size": 0.02
}
```

---

## Execution Timeline (Example Day)

```
2026-07-15 (Monday)

00:00 — Crypto markets open (24/7)
09:30 — Market data fetches begin
09:30:00 Execution #1
  • Fetch candles for all 5 trading pairs
  • Calculate signals (RSI, MACD, Bollinger)
  • Scan for entry opportunities
  • Scores: BTC=78 (Strong Buy), ETH=45 (Hold), BNB=72 (Strong Buy)
  • Action: BUY 0.05 BTC (signal=78), BUY 1.0 BNB (signal=72)
  • Log both trades to audit trail
  • Send heartbeat to backup (status OK)

09:45:00 Execution #2
  • Mark existing positions to market
  • BTC: +0.5% (unrealized gain $22.50)
  • BNB: -0.3% (unrealized loss $7.20)
  • Check exit conditions: none triggered
  • Scan for new signals: DOGE=65 (Buy), DOT=38 (Hold)
  • Cash still available, positions < 5
  • Action: BUY 100 DOGE (signal=65)
  • No exits

10:00:00 Execution #3
  • BTC: +1.2% (unrealized gain $54)
  • BNB: +0.2% (unrealized gain $2)
  • DOGE: +0.8% (unrealized gain $5)
  • Scan for exits: BTC signal now 55 (below 60 exit threshold)
  • Action: SELL 0.05 BTC at market (got $45,540) → realized P&L +$20
  • Action: BUY 0.03 ADA (new signal=71)
  • Daily running P&L: +$20 (from BTC exit) + $54 (BNB unrealized) = +$74

10:15:00 Execution #4
  ...continue every 15 minutes...

16:00:00 Execution #32 (Market close for US stocks, but crypto continues)
  ...continue through night...

23:45:00 Execution #96
  ...still trading...

DAILY SUMMARY
├─ Total executions: 96 (24h × 4 per hour)
├─ Total trades: 38 (opens + closes)
├─ Positions closed: 18 (profits, stops, time)
├─ Positions opened: 20
├─ Daily P&L: +$127
├─ Win rate (closed positions): 58%
├─ Largest win: +$45
├─ Largest loss: -$18
└─ Ending positions: 5 (at max)
```

---

## Monitoring & Observability

```
METRICS DASHBOARD (Updated every 10 seconds)
┌──────────────────────────────────────────┐
│  CRYPTO DAYTRADING — LIVE DASHBOARD      │
├──────────────────────────────────────────┤
│                                          │
│  Account:                                │
│    Equity: $11,775.00                    │
│    Cash: $9,500                          │
│    Daily P&L: +$127 (+1.1%)              │
│    Total P&L: +$625 (+6.3%)              │
│                                          │
│  Trading:                                │
│    Positions: 5 active                   │
│    Today: 38 trades (18 open, 20 closed) │
│    Win rate: 58% (11/19 closed)          │
│    Profit factor: 1.8x                   │
│                                          │
│  Strategy Performance:                   │
│    Momentum: 12 trades, 62% win          │
│    Mean Reversion: 15 trades, 55% win    │
│    Grid: 11 trades, 64% win              │
│                                          │
│  System Health:                          │
│    ✓ Binance API: Connected              │
│    ✓ Main machine: Healthy               │
│    ✓ Backup machine: Monitoring          │
│    ✓ Heartbeat: 10 seconds ago           │
│    ✓ Last trade: 3 seconds ago           │
│                                          │
└──────────────────────────────────────────┘
```

---

**Phase 1 Implementation** will build each component to spec.

