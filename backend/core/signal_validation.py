"""Signal Validation: Pre-execution checks prevent invalid orders"""

import logging
from typing import Tuple, Optional
from decimal import Decimal

logger = logging.getLogger(__name__)


class SignalValidator:
    """Validate trading signals before execution."""

    def __init__(self, min_order_size: float = 0.001, max_order_size: float = 100.0):
        self.min_order_size = Decimal(str(min_order_size))
        self.max_order_size = Decimal(str(max_order_size))

    def validate_signal(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: Optional[float],
        available_balance: float,
    ) -> Tuple[bool, Optional[str]]:
        """Validate a trading signal.

        Args:
            symbol: Trading pair (BTCUSDT)
            side: BUY or SELL
            quantity: Order size
            price: Limit price (None for market)
            available_balance: Available cash

        Returns:
            (Valid, error message if invalid)
        """
        qty = Decimal(str(quantity))
        balance = Decimal(str(available_balance))

        # Check symbol format
        if not symbol or len(symbol) < 6:
            return False, f"Invalid symbol: {symbol}"

        # Check side
        if side not in ["BUY", "SELL"]:
            return False, f"Invalid side: {side}, must be BUY or SELL"

        # Check quantity range
        if qty < self.min_order_size:
            return False, f"Quantity {qty} < minimum {self.min_order_size}"

        if qty > self.max_order_size:
            return False, f"Quantity {qty} > maximum {self.max_order_size}"

        # Check price for limit orders
        if price is not None:
            if price <= 0:
                return False, f"Invalid price: {price}"

        # Check balance for BUY orders
        if side == "BUY" and price is not None:
            required = (qty * Decimal(str(price))).quantize(Decimal("0.01"))
            if required > balance:
                return False, f"Insufficient balance: need €{required}, have €{balance}"

        logger.info(f"✅ Signal valid: {side} {qty} {symbol} @ {price}")
        return True, None


# Global instance
_signal_validator: Optional[SignalValidator] = None


def get_signal_validator() -> SignalValidator:
    global _signal_validator
    if _signal_validator is None:
        _signal_validator = SignalValidator()
    return _signal_validator
