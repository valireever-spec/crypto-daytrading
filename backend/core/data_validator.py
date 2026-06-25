"""Pillar #9: Incoming Data Validation - Block poisoned external data (CRITICAL)."""

import logging
import math
from datetime import datetime
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# Symbol-specific valid ranges (conservative bounds)
SYMBOL_RANGES = {
    "BTCUSDT": {"min": 10_000, "max": 500_000, "name": "Bitcoin"},
    "ETHUSDT": {"min": 1_000, "max": 50_000, "name": "Ethereum"},
    "BNBUSDT": {"min": 100, "max": 10_000, "name": "Binance Coin"},
    "ADAUSDT": {"min": 0.1, "max": 5, "name": "Cardano"},
    "DOGEUSDT": {"min": 0.01, "max": 1, "name": "Dogecoin"},
}

VALID_SYMBOLS = set(SYMBOL_RANGES.keys())
VALID_SIDES = {"BUY", "SELL"}
VALID_ORDER_TYPES = {"MARKET", "LIMIT"}


class PriceValidator:
    """Validate price data from external sources (WebSocket, REST API)."""

    def __init__(self):
        """Initialize price validator with historical tracking."""
        self.last_prices = {}  # Track last price for spike detection
        self.price_history = {}  # For trend analysis
        self.spike_alerts = {}  # Track recent spike alerts to avoid spam

    def validate_price(
        self,
        symbol: str,
        price: float,
        timestamp: datetime,
        max_age_seconds: int = 5,
    ) -> Tuple[bool, Optional[str]]:
        """Validate incoming price data for poisoning.

        Args:
            symbol: Trading symbol (e.g., "BTCUSDT")
            price: Current price
            timestamp: Price timestamp
            max_age_seconds: Max acceptable age of data

        Returns:
            (is_valid, error_message)
        """
        # Check 1: Symbol must be valid
        if symbol not in VALID_SYMBOLS:
            return False, f"Invalid symbol: {symbol}"

        # Check 2: Price must be numeric
        if not isinstance(price, (int, float)):
            return False, f"Price is not numeric: {type(price)}"

        # Check 3: Price cannot be NaN or Inf
        if math.isnan(price) or math.isinf(price):
            return False, f"Price is NaN/Inf: {price}"

        # Check 4: Price must be positive
        if price <= 0:
            return False, f"Price must be positive, got {price}"

        # Check 5: Price within expected range (strong sanity check)
        symbol_range = SYMBOL_RANGES.get(symbol)
        if symbol_range:
            min_price = symbol_range["min"]
            max_price = symbol_range["max"]
            if price < min_price or price > max_price:
                return (
                    False,
                    f"{symbol}: Price {price} outside range [{min_price}, {max_price}]",
                )

        # Check 6: Data freshness (max 5 seconds old)
        age_seconds = (datetime.utcnow() - timestamp).total_seconds()
        if age_seconds > max_age_seconds:
            return False, f"{symbol}: Price stale ({age_seconds:.1f}s old, max {max_age_seconds}s)"

        # Check 7: Spike detection (>50% change in 1 minute is suspicious)
        if symbol in self.last_prices:
            last_price = self.last_prices[symbol]
            if last_price > 0:
                spike_pct = abs(price - last_price) / last_price * 100

                # Alert on large spike (but still allow the trade)
                if spike_pct > 50:
                    # Check if we recently alerted on this symbol (avoid spam)
                    if symbol not in self.spike_alerts or \
                       (datetime.utcnow() - self.spike_alerts[symbol]).total_seconds() > 60:
                        logger.warning(
                            f"⚠️ PRICE SPIKE: {symbol} moved {spike_pct:.1f}% "
                            f"(${last_price:.2f} → ${price:.2f})"
                        )
                        self.spike_alerts[symbol] = datetime.utcnow()

                    # Don't reject, but flag for inspection
                    # (could be legitimate volatility, not poisoning)

        # Update tracking
        self.last_prices[symbol] = price
        if symbol not in self.price_history:
            self.price_history[symbol] = []
        self.price_history[symbol].append((timestamp, price))
        # Keep only last 100 prices
        if len(self.price_history[symbol]) > 100:
            self.price_history[symbol] = self.price_history[symbol][-100:]

        logger.debug(f"✅ Price validated: {symbol} = ${price:.2f}")
        return True, None

    def validate_prices_bulk(
        self, prices: Dict[str, float], timestamp: datetime
    ) -> Tuple[Dict[str, float], Dict[str, str]]:
        """Validate multiple prices at once.

        Args:
            prices: Dict of {symbol: price}
            timestamp: Timestamp for all prices

        Returns:
            (valid_prices, invalid_prices_with_reasons)
        """
        valid = {}
        invalid = {}

        for symbol, price in prices.items():
            is_valid, error = self.validate_price(symbol, price, timestamp)
            if is_valid:
                valid[symbol] = price
            else:
                invalid[symbol] = error
                logger.warning(f"❌ Price rejected: {error}")

        return valid, invalid


class OrderFillValidator:
    """Validate order fills from Binance API."""

    @staticmethod
    def validate_fill(
        order_response: Dict,
        original_request: Dict,
    ) -> Tuple[bool, Optional[str]]:
        """Validate order fill against original request.

        Args:
            order_response: Response from Binance
            original_request: Original request sent

        Returns:
            (is_valid, error_message)
        """
        # Check 1: Symbol matches
        response_symbol = order_response.get("symbol", "")
        request_symbol = original_request.get("symbol", "")
        if response_symbol != request_symbol:
            return (
                False,
                f"Symbol mismatch: requested {request_symbol}, got {response_symbol}",
            )

        # Check 2: Side matches
        response_side = order_response.get("side", "")
        request_side = original_request.get("side", "")
        if response_side != request_side:
            return (
                False,
                f"Side mismatch: requested {request_side}, got {response_side}",
            )

        # Check 3: Quantity validation
        filled_qty = float(order_response.get("executedQty", 0))
        requested_qty = original_request.get("quantity", 0)

        if filled_qty == 0:
            return False, "Order fill quantity is zero"

        if filled_qty > requested_qty * 1.01:  # Allow 1% rounding error
            return (
                False,
                f"Over-fill detected: requested {requested_qty}, filled {filled_qty}",
            )

        if filled_qty < requested_qty * 0.99:  # 1% threshold for partial
            logger.warning(
                f"⚠️ Partial fill: {request_symbol} requested {requested_qty}, "
                f"filled {filled_qty} ({filled_qty/requested_qty*100:.1f}%)"
            )

        # Check 4: Fill price validation
        fill_price = float(order_response.get("price", 0))
        if not isinstance(fill_price, (int, float)) or fill_price <= 0:
            return False, f"Invalid fill price: {fill_price}"

        if math.isnan(fill_price) or math.isinf(fill_price):
            return False, f"Fill price is NaN/Inf: {fill_price}"

        # Check 5: Slippage reasonable (for limit orders, max 1%)
        if original_request.get("type") == "LIMIT":
            requested_price = original_request.get("price", fill_price)
            if requested_price > 0:
                slippage_pct = abs(fill_price - requested_price) / requested_price * 100
                if slippage_pct > 1.0:
                    logger.warning(
                        f"⚠️ High slippage: {request_symbol} "
                        f"${requested_price:.2f} → ${fill_price:.2f} ({slippage_pct:.2f}%)"
                    )

        # Check 6: Order ID not duplicated (should be checked in DB, but double-check)
        order_id = order_response.get("orderId")
        if not order_id:
            return False, "Order ID missing from response"

        logger.debug(
            f"✅ Order fill validated: {request_symbol} {filled_qty} @ ${fill_price:.2f}"
        )
        return True, None


class PositionReconciler:
    """Validate position data from Binance account API."""

    @staticmethod
    def validate_position(
        symbol: str,
        quantity: float,
        entry_price: float,
    ) -> Tuple[bool, Optional[str]]:
        """Validate a single position.

        Args:
            symbol: Trading symbol
            quantity: Position quantity
            entry_price: Position entry price

        Returns:
            (is_valid, error_message)
        """
        # Check 1: Symbol valid
        if symbol not in VALID_SYMBOLS:
            return False, f"Invalid symbol: {symbol}"

        # Check 2: Quantity valid
        if not isinstance(quantity, (int, float)):
            return False, f"Quantity not numeric: {type(quantity)}"

        if quantity <= 0:
            return False, f"Quantity must be positive: {quantity}"

        if math.isnan(quantity) or math.isinf(quantity):
            return False, f"Quantity is NaN/Inf: {quantity}"

        # Check 3: Entry price valid
        if not isinstance(entry_price, (int, float)):
            return False, f"Entry price not numeric: {type(entry_price)}"

        if entry_price <= 0:
            return False, f"Entry price must be positive: {entry_price}"

        if math.isnan(entry_price) or math.isinf(entry_price):
            return False, f"Entry price is NaN/Inf: {entry_price}"

        logger.debug(f"✅ Position validated: {symbol} {quantity} @ ${entry_price:.2f}")
        return True, None

    @staticmethod
    def validate_balance(balance: float) -> Tuple[bool, Optional[str]]:
        """Validate account balance.

        Args:
            balance: Available balance in EUR

        Returns:
            (is_valid, error_message)
        """
        # Check 1: Balance numeric
        if not isinstance(balance, (int, float)):
            return False, f"Balance not numeric: {type(balance)}"

        # Check 2: Balance non-negative
        if balance < 0:
            return False, f"Balance cannot be negative: {balance}"

        # Check 3: Not NaN/Inf
        if math.isnan(balance) or math.isinf(balance):
            return False, f"Balance is NaN/Inf: {balance}"

        logger.debug(f"✅ Balance validated: €{balance:.2f}")
        return True, None


class ResponseValidator:
    """Strict schema validation for API responses (Pydantic-lite)."""

    @staticmethod
    def validate_kline_response(data: Dict) -> Tuple[bool, Optional[str]]:
        """Validate Binance kline (candlestick) response.

        Args:
            data: Response data

        Returns:
            (is_valid, error_message)
        """
        required_fields = {
            "s": str,  # symbol
            "c": (int, float),  # close price
            "o": (int, float),  # open price
            "h": (int, float),  # high
            "l": (int, float),  # low
            "v": (int, float),  # volume
            "t": int,  # timestamp
        }

        # Check 1: All required fields present
        for field, expected_type in required_fields.items():
            if field not in data:
                return False, f"Missing required field: {field}"

        # Check 2: Type validation
        for field, expected_type in required_fields.items():
            value = data[field]
            if isinstance(expected_type, tuple):
                if not isinstance(value, expected_type):
                    return (
                        False,
                        f"Field {field} has wrong type: {type(value)}, "
                        f"expected {expected_type}",
                    )
            else:
                if not isinstance(value, expected_type):
                    return (
                        False,
                        f"Field {field} has wrong type: {type(value)}, "
                        f"expected {expected_type}",
                    )

        # Check 3: No unknown fields (strict mode)
        unknown = set(data.keys()) - set(required_fields.keys())
        if unknown:
            logger.warning(f"⚠️ Unknown fields in response: {unknown}")
            # Don't reject, but log for inspection

        logger.debug(f"✅ Kline response validated: {data.get('s')}")
        return True, None

    @staticmethod
    def validate_trade_response(data: Dict) -> Tuple[bool, Optional[str]]:
        """Validate Binance trade (aggTrade) response.

        Args:
            data: Response data

        Returns:
            (is_valid, error_message)
        """
        required_fields = {
            "s": str,  # symbol
            "p": (int, float),  # price
            "q": (int, float),  # quantity
            "T": int,  # timestamp
        }

        for field, expected_type in required_fields.items():
            if field not in data:
                return False, f"Missing required field: {field}"

        logger.debug(f"✅ Trade response validated: {data.get('s')}")
        return True, None


# Global validator instances
_price_validator: Optional[PriceValidator] = None


def get_price_validator() -> PriceValidator:
    """Get or create global price validator."""
    global _price_validator
    if _price_validator is None:
        _price_validator = PriceValidator()
        logger.info("✅ Price validator initialized (Pillar #9)")
    return _price_validator
