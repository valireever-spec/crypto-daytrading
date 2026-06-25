# ADR-002: Binance API Integration Strategy

**Date:** 2026-06-25  
**Status:** ACCEPTED  
**Phase:** 1 (Paper Trading)

## Context

Need to integrate with Binance for:
- Real-time price feeds (WebSocket streaming)
- Historical OHLCV data for backtesting
- Paper trading simulation (testnet)
- Eventually: Live trading execution

Two main approaches:
1. **Use existing library** (`python-binance`, `binance-connector-python`)
   - Pros: Pre-built, tested, community-maintained
   - Cons: May have limitations, harder to customize

2. **Build custom wrapper** around Binance REST/WebSocket APIs
   - Pros: Full control, lightweight, exactly what we need
   - Cons: More code to maintain, must handle edge cases

## Decision

**Use hybrid approach:**
- **WebSocket prices:** Custom lightweight wrapper for real-time streaming
- **REST data:** Use `python-binance` library for OHLCV and historical data
- **Paper trading:** Custom implementation (no real API calls)

## Rationale

### WebSocket (Custom)
- Real-time price updates critical for trading
- Need low-latency stream with auto-reconnect
- Simple to implement: just parse JSON from WebSocket
- Binance testnet WebSocket works without authentication
- Custom gives us control over reconnection logic and error handling

### Historical Data (Library)
- Backtesting requires historical OHLCV data
- `python-binance` has mature implementation
- Rate limiting already handled
- Time frame conversions already done
- Don't need to rewrite this

### Paper Trading (Custom)
- No actual API calls to Binance
- Simulate fills at real prices with fixed slippage
- Append-only trade log
- Must work reliably (core to Phase 1)

## Architecture

```
Client Request
    ↓
Autonomous Trader
    ├─ WebSocket (custom) ← Real-time prices
    ├─ Paper Engine (custom) ← Order simulation
    └─ Historical Service (python-binance) ← Backtesting data
    ↓
Binance Mainnet
```

## Integration Points

### 1. Real-Time Prices (Custom WebSocket)
File: `backend/exchange/binance_websocket.py`
- Stream prices for BTCUSDT, ETHUSDT, BNBUSDT
- Auto-reconnect with exponential backoff (max 30s)
- Heartbeat monitoring (>2min → circuit break)

### 2. Historical Data (python-binance)
File: `backend/analytics/historical_data.py`
- Fetch OHLCV for backtesting (days/weeks)
- Cached to avoid repeated API calls
- Supports timeframes: 1m, 5m, 15m, 1h, 4h, 1d

### 3. Paper Trading (Custom)
File: `backend/exchange/paper_trading.py`
- Simulates fills at real prices + slippage
- Fixed slippage: 0.1% market, 0.05% limit
- Append-only trade log
- Position tracking with DB persistence

## Consequences

### Positive
- ✅ Real-time prices with full control over reconnection
- ✅ Leverage battle-tested OHLCV library
- ✅ Lightweight custom code (low maintenance)
- ✅ Paper trading 100% reliable (no API dependency)

### Negative
- ❌ Must maintain WebSocket reconnection logic
- ❌ Slippage is fixed (real slippage varies)
- ❌ Testnet/mainnet switch requires code change (not env var)

## Migration Path (Future)

**Phase 2:** If need live trading
- Add REST wrapper for order placement
- Use `python-binance` for live orders
- Same paper engine logic, just route orders to exchange

**Phase 3:** If need multiple exchanges
- Abstract WebSocket interface
- Implement for Kraken, FTX, Coinbase
- Same paper engine works for any exchange

## References
- Binance Testnet WebSocket: `wss://stream.testnet.binance.vision:9443`
- Binance Mainnet WebSocket: `wss://stream.binance.com:9443`
- python-binance GitHub: https://github.com/sammchardy/python-binance
- binance-connector-python: https://github.com/binance/binance-connector-python
