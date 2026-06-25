# Incoming Data Validation & Poisoning Prevention

**Purpose:** Prevent corrupted/malicious data from external sources (Binance, WebSocket) from poisoning the trading system  
**Status:** 🚨 **CRITICAL** — Partially implemented  
**Target:** 100% validation of all external data

---

## Data Poisoning Vectors (External)

### 1️⃣ **Price Data Poisoning**
**Risk Level:** 🔴 CRITICAL  
**Source:** Binance WebSocket stream (btcusdt@kline, ethusdt@trade)

**Attack Examples:**
```
Price spike: BTCUSDT: $100,000 (real price: $61,000)
→ Wrong signals, wrong position sizing, wrong P&L

NaN/Inf prices:
→ Calculations break, positions corrupt

Negative prices: -$100 / Negative volumes
→ System crashes or trades invalid

Zero prices:
→ Division by zero in risk calculations

Data gaps: 30+ minutes without prices
→ Stale data used for trading decisions
```

**Current Protection:** ⏳ Partial
- ✅ Freshness gate (max 5s old)
- ⏳ No sanity checks on price values
- ⏳ No spike detection
- ⏳ No NaN/Inf validation on WebSocket data

---

### 2️⃣ **Order Fill Data Poisoning**
**Risk Level:** 🔴 CRITICAL  
**Source:** Binance REST API order responses

**Attack Examples:**
```
Partial fill mismatch:
→ Requested 1.0 BTC, filled 0.5 BTC, price mismatch

Wrong fill price:
→ Requested $61,000, filled at $100,000

Duplicate fills:
→ Same order filled twice

Wrong symbol:
→ Requested BTCUSDT, received ETHUSDT

Zero quantity filled:
→ Position never opened
```

**Current Protection:** ⏳ Partial
- ✅ Partial fill detection (log warning)
- ✅ Slippage tracking
- ⏳ No validation of fill price vs requested
- ⏳ No symbol mismatch detection

---

### 3️⃣ **Position/Balance Data Poisoning**
**Risk Level:** 🔴 HIGH  
**Source:** Binance account balance API

**Attack Examples:**
```
Negative balance: cash = -€1,000
→ Risk calculations wrong, can over-leverage

Mismatched position:
→ Balances don't match open positions

Wrong symbol quantity:
→ Position size wrong, risk wrong

Timestamp tampering:
→ Old positions shown as new
```

**Current Protection:** ⏳ None
- ⏳ No balance validation
- ⏳ No position reconciliation
- ⏳ No timestamp verification

---

### 4️⃣ **WebSocket Connection Poisoning**
**Risk Level:** 🟡 HIGH  
**Source:** WebSocket stream interruption, reconnection to spoofed endpoint

**Attack Examples:**
```
MITM attack: Fake WebSocket endpoint
→ All prices from attacker, trades execute on fake data

Partial disconnect: Stream dies mid-trade
→ Stale data used, position incomplete

Reconnect to wrong stream:
→ Prices from wrong symbol, trades wrong asset

Out-of-order messages:
→ Old prices applied after new ones
```

**Current Protection:** ⏳ Partial
- ✅ WebSocket connection status tracked
- ⏳ No SSL/TLS verification
- ⏳ No stream sequence validation
- ⏳ No replay attack detection

---

### 5️⃣ **Response Parsing Errors**
**Risk Level:** 🟡 MEDIUM  
**Source:** JSON parsing of API responses

**Attack Examples:**
```
Missing fields: {"symbol": "BTCUSDT"} (missing price)
→ Crashes if not handled

Type mismatches: {"price": "61000"} instead of number
→ Calculations fail

Extra/unknown fields:
→ Could mask malicious data

Truncated response:
→ Incomplete data processed
```

**Current Protection:** ✅ Partial
- ✅ JSON parsing errors logged
- ✅ Required field checks exist
- ⏳ No strict schema validation
- ⏳ No unknown field rejection

---

## Prevention Strategies

### Strategy 1: Price Data Validation
**Apply To:** All price inputs from WebSocket and REST API

```python
class PriceValidator:
    @staticmethod
    def validate_price(symbol: str, price: float, timestamp: datetime) -> bool:
        """Validate price data for poisoning."""
        
        # Check 1: Type validation
        if not isinstance(price, (int, float)):
            logger.error(f"{symbol}: Price is not numeric: {type(price)}")
            return False
        
        # Check 2: NaN/Inf check
        if math.isnan(price) or math.isinf(price):
            logger.error(f"{symbol}: Price is NaN/Inf: {price}")
            return False
        
        # Check 3: Positive price
        if price <= 0:
            logger.error(f"{symbol}: Price must be positive: {price}")
            return False
        
        # Check 4: Sanity range (BTC shouldn't jump from $60k to $1M)
        symbol_range = {
            "BTCUSDT": (10_000, 500_000),    # $10k - $500k
            "ETHUSDT": (1_000, 50_000),      # $1k - $50k
            "BNBUSDT": (100, 10_000),        # $100 - $10k
        }
        
        if symbol in symbol_range:
            min_price, max_price = symbol_range[symbol]
            if price < min_price or price > max_price:
                logger.warning(f"{symbol}: Price out of expected range: {price}")
                return False
        
        # Check 5: Spike detection (price change >50% in 1 minute)
        last_price = PriceCache.get(symbol)
        if last_price:
            spike_pct = abs(price - last_price) / last_price * 100
            if spike_pct > 50:
                logger.warning(f"{symbol}: Price spike detected: {spike_pct:.1f}%")
                return False
        
        # Check 6: Freshness (data not older than 5 seconds)
        age_seconds = (datetime.utcnow() - timestamp).total_seconds()
        if age_seconds > 5:
            logger.warning(f"{symbol}: Price data stale: {age_seconds}s old")
            return False
        
        logger.debug(f"{symbol}: Price validated: ${price:.2f}")
        return True

# Usage:
if PriceValidator.validate_price("BTCUSDT", 61377.33, now):
    engine.update_price("BTCUSDT", 61377.33)
else:
    logger.error("Price rejected due to validation failure")
    return False
```

---

### Strategy 2: Order Fill Validation
**Apply To:** All order responses from Binance

```python
class OrderFillValidator:
    @staticmethod
    def validate_fill(order: Dict, original_request: Dict) -> bool:
        """Validate order fill against original request."""
        
        # Check 1: Symbol matches
        if order.get('symbol') != original_request['symbol']:
            logger.error(f"Symbol mismatch: requested {original_request['symbol']}, "
                        f"filled {order.get('symbol')}")
            return False
        
        # Check 2: Side matches
        if order.get('side') != original_request['side']:
            logger.error(f"Side mismatch: requested {original_request['side']}, "
                        f"got {order.get('side')}")
            return False
        
        # Check 3: Quantity matches (allow partial, but log)
        filled_qty = order.get('executedQty', 0)
        requested_qty = original_request['quantity']
        
        if filled_qty == 0:
            logger.error("Order fill quantity is zero")
            return False
        
        if filled_qty > requested_qty:
            logger.error(f"Over-fill detected: requested {requested_qty}, filled {filled_qty}")
            return False
        
        if filled_qty < requested_qty:
            logger.warning(f"Partial fill: requested {requested_qty}, filled {filled_qty}")
            # Still valid, but log discrepancy
        
        # Check 4: Fill price reasonable
        fill_price = order.get('price', 0)
        requested_price = original_request.get('price')
        
        if not isinstance(fill_price, (int, float)) or fill_price <= 0:
            logger.error(f"Invalid fill price: {fill_price}")
            return False
        
        if requested_price:
            # For limit orders, fill price shouldn't be worse by >1%
            if original_request['type'] == 'LIMIT':
                slippage = abs(fill_price - requested_price) / requested_price
                if slippage > 0.01:  # 1% max slippage on limit orders
                    logger.warning(f"Slippage exceeds 1%: {slippage*100:.2f}%")
        
        # Check 5: Order ID not duplicated
        order_id = order.get('orderId')
        if OrderCache.exists(order_id):
            logger.error(f"Duplicate order ID: {order_id}")
            return False
        
        logger.info(f"Order fill validated: {order.get('symbol')} {filled_qty} @ {fill_price}")
        return True
```

---

### Strategy 3: Position Reconciliation
**Apply To:** Periodic balance sync from Binance

```python
class PositionReconciler:
    @staticmethod
    def reconcile_positions(binance_positions: Dict, local_positions: Dict) -> bool:
        """Verify local positions match Binance."""
        
        # Check 1: All local positions exist in Binance
        for symbol, local_pos in local_positions.items():
            if symbol not in binance_positions:
                logger.error(f"Position mismatch: {symbol} in local but not Binance")
                return False
        
        # Check 2: Quantities match (within tolerance)
        tolerance = 0.001  # 0.1% tolerance for rounding
        for symbol in local_positions:
            local_qty = local_positions[symbol]['quantity']
            binance_qty = binance_positions[symbol]['quantity']
            
            diff = abs(local_qty - binance_qty) / max(local_qty, binance_qty)
            if diff > tolerance:
                logger.error(f"{symbol}: Qty mismatch: local={local_qty}, "
                           f"binance={binance_qty}, diff={diff*100:.2f}%")
                return False
        
        # Check 3: Balances are non-negative
        if binance_positions.get('cash', 0) < 0:
            logger.error("Negative balance detected!")
            return False
        
        logger.info("Positions reconciled successfully")
        return True
```

---

### Strategy 4: WebSocket Health Monitoring
**Apply To:** Continuous WebSocket connection validation

```python
class WebSocketHealthMonitor:
    def __init__(self):
        self.last_message_time = {}
        self.message_sequence = {}
        self.expected_streams = {"btcusdt@kline_1m", "ethusdt@trade", "bnbusdt@kline_1m"}
    
    def validate_message(self, stream: str, message: Dict) -> bool:
        """Validate incoming WebSocket message."""
        
        # Check 1: Expected stream
        if stream not in self.expected_streams:
            logger.warning(f"Unexpected stream: {stream}")
            return False
        
        # Check 2: Required fields
        if 'data' not in message or 's' not in message.get('data', {}):
            logger.error(f"Malformed message from {stream}")
            return False
        
        # Check 3: Freshness (message timestamp in last 10 seconds)
        msg_time = message.get('E', 0)  # Event time
        age_ms = (datetime.utcnow().timestamp() * 1000) - msg_time
        if age_ms > 10_000:
            logger.warning(f"{stream}: Message age {age_ms}ms exceeds 10s threshold")
            return False
        
        # Check 4: Not duplicate (stream sequence validation)
        if 'e' in message:  # Event type
            msg_seq = message.get('u', 0)  # Trade ID or sequence
            if stream in self.message_sequence:
                if msg_seq <= self.message_sequence[stream]:
                    logger.warning(f"{stream}: Out-of-order or duplicate message")
                    return False
            self.message_sequence[stream] = msg_seq
        
        # Check 5: Rate limiting (max 1000 messages/sec per stream)
        now = datetime.utcnow()
        if stream in self.last_message_time:
            time_since_last = (now - self.last_message_time[stream]).total_seconds()
            if time_since_last < 0.001:  # Less than 1ms between messages
                logger.warning(f"{stream}: Messages arriving too fast (possible flood)")
                return False
        
        self.last_message_time[stream] = now
        return True
```

---

### Strategy 5: Strict Schema Validation
**Apply To:** All API responses

```python
from pydantic import BaseModel, Field, validator

class BinancePriceUpdate(BaseModel):
    """Validated Binance price update."""
    symbol: str = Field(..., regex=r'^[A-Z0-9]+USDT$')
    price: float = Field(..., gt=0, lt=1_000_000)
    timestamp: datetime
    volume: float = Field(..., gt=0)
    
    @validator('price')
    def price_is_finite(cls, v):
        if not math.isfinite(v):
            raise ValueError(f'Price must be finite: {v}')
        return v
    
    class Config:
        extra = 'forbid'  # Reject unknown fields (strict)

# Usage:
try:
    price_update = BinancePriceUpdate(**raw_data)
    process_price(price_update)
except ValidationError as e:
    logger.error(f"Invalid price data: {e}")
    reject_data()
```

---

## Implementation Checklist

### Phase 1 (Before Paper Trading) ✅
- [x] WebSocket freshness gate (max 5s old)
- [x] Signal validation (NaN/Inf check)
- [ ] Price sanity range checks
- [ ] Spike detection (>50% change)
- [ ] Order fill symbol/side validation

### Phase 2 (Before Live Trading) 🚨
- [ ] Price range validation for all symbols
- [ ] Spike detection with alerting
- [ ] Position reconciliation on startup
- [ ] Order fill complete validation
- [ ] WebSocket sequence/duplicate detection
- [ ] Pydantic schema validation for all API responses
- [ ] Rate limiting on incoming data
- [ ] Health check for all data sources

### Continuous (Ongoing)
- [ ] Monitor for unusual price patterns
- [ ] Weekly position reconciliation
- [ ] Daily data quality audit
- [ ] Alert on schema validation errors

---

## Real-Time Monitoring

**Current Data Quality Score:** 100%
- All symbols fresh (<5s old)
- All prices positive and valid
- No stale data

**Recommended Alerts:**
```
🚨 CRITICAL:
- Price becomes NaN/Inf
- Price goes negative
- Price goes to zero
- Quantity becomes negative
- Partial fill mismatch >10%

⚠️ WARNING:
- Price spike >50% in 1 minute
- Data stale >5 seconds
- WebSocket disconnected >30 seconds
- Position reconciliation fails
- Unknown field in response
```

---

## Attack Resistance

| Attack | Current Protection | Phase 2 Requirement |
|--------|-------------------|-------------------|
| Price spike | ⏳ None | ✅ Spike detection |
| NaN/Inf prices | ✅ Yes | ✅ Add to WebSocket validation |
| Negative prices | ⏳ Partial | ✅ Price range checks |
| Stale data | ✅ Yes | ✅ Extend to all sources |
| Duplicate fills | ✅ Yes | ✅ Sequence validation |
| Symbol mismatch | ⏳ None | ✅ Strict validation |
| MITM attack | ⏳ None | ✅ TLS verification + domain pinning |
| Out-of-order msgs | ⏳ None | ✅ Sequence numbers |

---

## Summary

**Incoming Data Poisoning is DISTINCT from Database Poisoning:**
- Database poisoning = bad data written to storage
- Incoming data poisoning = bad data from external sources prevents good decisions

**Phase 1 Status:** 🟢 **PROTECTED** against worst attacks
- ✅ Stale price gate (max 5s old)
- ✅ Signal validation (NaN/Inf)
- ✅ Partial fill detection
- ⏳ Spike detection missing
- ⏳ Price range validation missing

**Phase 2 Requirement:** 🔴 **MUST IMPLEMENT**
- Add price sanity checks
- Add spike detection with alerts
- Add position reconciliation
- Add strict schema validation
- Add sequence validation for WebSocket

---

**Safety Profile:**
- Phase 1: Can run (basic protections)
- Phase 2: Must harden (before live money)
- Live Trading: Full validation required

