# Binance WebSocket UI Guide

## Quick Answer: Where to See Live Prices & WebSocket Status

**📍 Location: Market Status Tab (📈) on http://127.0.0.1:8001/**

Two main cards show all WebSocket activity:

1. **🌐 WebSocket Connection Card** - Shows connection health
2. **💹 Live Prices Table** - Shows real-time symbol prices

---

## Visual Layout

```
http://127.0.0.1:8001/ → Click "Market Status" tab (📈)
                              ↓ ↓ ↓
┌─────────────────────────────────────────────────┐
│  Market Regime Card                             │
│  - Current regime, volatility, RSI              │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│  🌐 WebSocket Connection (NEW!)                 │
│  - Status: ✓ Connected                          │
│  - Subscriptions: 3                             │
│  - Cached Prices: 0                             │
│  - Active Streams:                              │
│    • btcusdt@kline_1m                           │
│    • ethusdt@kline_1m                           │
│    • bnbusdt@kline_1m                           │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│  Trading Rules & Strategy Impact Cards          │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│  💹 Live Prices Table                           │
│  ┌──────────────────────────────────────────┐   │
│  │ Symbol  │ Price      │ Last Update      │   │
│  │─────────┼────────────┼──────────────────│   │
│  │ BTCUSDT │ $62,315.00 │ 18:55:32         │   │
│  │ ETHUSDT │ $1,657.52  │ 18:55:32         │   │
│  │ BNBUSDT │ $574.30    │ 18:55:32         │   │
│  └──────────────────────────────────────────┘   │
│  Updates every 5 seconds (auto-refresh ON)      │
└─────────────────────────────────────────────────┘
```

---

## What Each Card Shows

### 🌐 WebSocket Connection Card

**Purpose:** Monitor your Binance WebSocket streaming connection

| Field | Shows | Meaning |
|-------|-------|---------|
| **Status** | ✓ Connected | WebSocket is active |
| **Subscriptions** | 3 | 3 price streams are active |
| **Cached Prices** | 0 | Waiting for first price tick |
| **Active Streams** | List | Which symbols are being streamed |

**What it means:**
- ✓ Connected = WebSocket is online
- Subscriptions = How many price streams are running
- Stream names = btcusdt@kline_1m (1-minute candles for BTCUSDT), etc.

### 💹 Live Prices Table

**Purpose:** Display real-time prices from Binance WebSocket

| Column | Shows | Updates |
|--------|-------|---------|
| **Symbol** | Trading pair (BTCUSDT, ETHUSDT, etc.) | Fixed |
| **Price** | Latest price | When new candle closes |
| **Last Update** | Timestamp of price | Every update |

**Auto-refresh:**
- Dashboard auto-refreshes every 5 seconds
- Toggle with ⏸ button in header
- Prices update as Binance sends new data

---

## Binance WebSocket Streams

You're subscribed to **3 streams**:

```
btcusdt@kline_1m     → Bitcoin 1-minute candles
ethusdt@kline_1m     → Ethereum 1-minute candles
bnbusdt@kline_1m     → Binance Coin 1-minute candles
```

Each stream sends:
- Open, High, Low, Close prices
- Trading volume
- Timestamp

---

## API Endpoints (Behind the UI)

The dashboard fetches WebSocket data from these endpoints:

### GET /api/prices
Returns latest WebSocket prices and connection status:
```json
{
  "prices": {
    "BTCUSDT": 62315.50,
    "ETHUSDT": 1657.52,
    "BNBUSDT": 574.30
  },
  "stream_status": {
    "connected": true,
    "subscriptions": 3,
    "cached_prices": 3,
    "last_update": "2026-06-23T20:55:32.123456+00:00"
  }
}
```

### GET /api/health
Returns full system health including WebSocket:
```json
{
  "status": "ok",
  "mode": "paper",
  "websocket": {
    "connected": true,
    "subscribed_streams": 3,
    "streams": ["btcusdt@kline_1m", "ethusdt@kline_1m", "bnbusdt@kline_1m"],
    "last_price_update": "2026-06-23T20:55:32.123456+00:00"
  }
}
```

---

## Troubleshooting

### "Waiting for Binance price ticks..."
**Why:** WebSocket is connected but hasn't received prices yet
**What to do:** 
- Wait 5-10 seconds (Binance takes time to send first candle)
- Check Live Prices table auto-refreshes
- Verify WebSocket says "Connected"

### "Disconnected" status
**Why:** WebSocket connection lost
**What to do:**
- Check network connectivity
- Restart dashboard: Refresh page (F5)
- Restart bot: `pkill -f uvicorn && uvicorn backend.api.main:app --port 8001`

### Prices show $0.00
**Why:** Prices haven't been received yet
**What to do:**
- Wait for first Binance data tick (usually 5-10 seconds)
- Auto-refresh will update when data arrives
- Check WebSocket Connection card shows status

### Only 2 symbols show, missing one
**Why:** Binance hasn't sent all candles yet
**What to do:**
- Wait - streams stagger their deliveries
- Check "Cached Prices" counter in WebSocket card
- All 3 should appear within 10 seconds

---

## Key Features

✅ **Real-time prices** from Binance WebSocket
✅ **Connection monitoring** - see if streams are active
✅ **Auto-refresh** - updates every 5 seconds
✅ **No polling delays** - WebSocket is push-based (instant)
✅ **Stream details** - see which symbols are being tracked
✅ **Health status** - know when connection is lost

---

## Dashboard Controls

| Button | Effect | Location |
|--------|--------|----------|
| 🔄 Refresh All | Manual refresh all data | Header |
| ⏸ Auto-Refresh | Toggle 5-sec auto-refresh | Header |
| 💾 Export | Download data as JSON | Header |
| [📈] Market Status | Switch to this tab | Top nav |
| [🏥] Health | View full system health | Top nav |

---

## Live Example

When everything is working:

```
Dashboard Header
├─ Status: Online (green dot)
├─ Last Update: 20:55:43
└─ Mode: Paper Trading

Market Status Tab
├─ Market Regime Card
│  ├─ BULL / BEAR / SIDEWAYS / VOLATILE
│  └─ Confidence: 85%
│
├─ 🌐 WebSocket Connection (THIS SHOWS BINANCE STATUS)
│  ├─ Status: ✓ Connected
│  ├─ Subscriptions: 3
│  ├─ Cached Prices: 3
│  └─ Active Streams:
│     ├─ btcusdt@kline_1m
│     ├─ ethusdt@kline_1m
│     └─ bnbusdt@kline_1m
│
├─ Trading Rules
├─ Strategy Impact
│
└─ 💹 Live Prices (THIS SHOWS LIVE PRICES)
   ├─ BTCUSDT │ $62,315.00 │ 20:55:32
   ├─ ETHUSDT │ $1,657.52  │ 20:55:32
   └─ BNBUSDT │ $574.30    │ 20:55:32
```

---

## Summary

| What | Where | Updates |
|------|-------|---------|
| WebSocket Status | Market Status → WebSocket Card | Every 5s |
| Live Prices | Market Status → Live Prices Table | Every 5s |
| Connection Health | Health Tab → WebSocket section | Every 5s |
| API Docs | API Reference Tab → All endpoints | Static |

**Bottom line:** Everything you need is in the **Market Status tab** (📈) of the unified dashboard!
