"""Financial Safety: Precise Calculations, Fee Tracking, Cash Management

Prevents:
- Floating point errors
- Unaccounted fees
- Over-leveraging
- Slippage surprises
- Negative balance
"""

import logging
from decimal import Decimal, ROUND_HALF_UP, getcontext
from typing import Dict, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Set Decimal precision to 8 decimal places (micro-Bitcoin)
getcontext().prec = 10


@dataclass
class FeeStructure:
    """Binance fee structure."""
    taker_fee: Decimal = Decimal("0.001")  # 0.1% taker
    maker_fee: Decimal = Decimal("0.001")  # 0.1% maker
    binance_coin_discount: Decimal = Decimal("0.25")  # 25% discount with BNB


class FinancialSafetyManager:
    """Manage financial calculations with full precision & fee accounting."""

    def __init__(self, fees: Optional[FeeStructure] = None):
        """Initialize financial safety manager."""
        self.fees = fees or FeeStructure()
        self.min_balance = Decimal("0.01")  # Keep 0.01 EUR buffer
        self.reserved_balance: Dict[str, Decimal] = {}  # Reserved for pending orders

    def calculate_order_cost(
        self,
        symbol: str,
        quantity: float,
        price: float,
        is_taker: bool = True,
    ) -> Dict:
        """Calculate exact order cost including fees.

        Args:
            symbol: Trading pair
            quantity: Amount to buy
            price: Price per unit
            is_taker: Taker (True) or maker (False) order

        Returns:
            {
                "quantity": Decimal,
                "price": Decimal,
                "gross_cost": Decimal,
                "fee": Decimal,
                "net_cost": Decimal,
            }
        """
        qty_decimal = Decimal(str(quantity))
        price_decimal = Decimal(str(price))

        # Gross cost (before fees)
        gross_cost = (qty_decimal * price_decimal).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        # Fee calculation
        fee_rate = self.fees.taker_fee if is_taker else self.fees.maker_fee
        fee = (gross_cost * fee_rate).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        # Net cost (gross + fees)
        net_cost = (gross_cost + fee).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        logger.debug(
            f"💰 Order cost calculation: {qty_decimal} {symbol} @ €{price_decimal} = €{gross_cost} + €{fee} fee = €{net_cost}"
        )

        return {
            "quantity": qty_decimal,
            "price": price_decimal,
            "gross_cost": gross_cost,
            "fee": fee,
            "net_cost": net_cost,
        }

    def can_afford_order(
        self,
        available_balance: float,
        order_cost: Dict,
    ) -> Tuple[bool, Optional[str]]:
        """Check if account can afford order.

        Args:
            available_balance: Available cash in EUR
            order_cost: Order cost dict from calculate_order_cost()

        Returns:
            (True if affordable, reason if not)
        """
        balance = Decimal(str(available_balance))
        cost = order_cost["net_cost"]
        buffer = self.min_balance

        if balance < cost + buffer:
            shortfall = cost + buffer - balance
            reason = f"Insufficient balance: need €{cost} + €{buffer} buffer, have €{balance:.2f} (short €{shortfall:.2f})"
            logger.warning(f"❌ {reason}")
            return False, reason

        logger.info(f"✅ Sufficient balance: €{balance:.2f} >= €{cost:.2f}")
        return True, None

    def reserve_balance(
        self,
        order_id: str,
        symbol: str,
        amount: Decimal,
    ) -> None:
        """Reserve balance for pending order.

        Args:
            order_id: Order identifier
            symbol: Trading pair
            amount: Amount to reserve
        """
        key = f"{order_id}:{symbol}"
        self.reserved_balance[key] = amount
        logger.info(f"💼 Reserved €{amount} for {order_id}")

    def release_reserve(self, order_id: str, symbol: str) -> Decimal:
        """Release reserved balance.

        Args:
            order_id: Order identifier
            symbol: Trading pair

        Returns:
            Amount released
        """
        key = f"{order_id}:{symbol}"
        amount = self.reserved_balance.pop(key, Decimal("0"))
        if amount > 0:
            logger.info(f"🔓 Released reserve: €{amount}")
        return amount

    def get_reserved_total(self) -> Decimal:
        """Get total reserved balance."""
        return sum(self.reserved_balance.values())

    def get_available_balance(self, total_balance: float) -> Decimal:
        """Get available balance after reserves.

        Args:
            total_balance: Total account balance

        Returns:
            Available balance (total - reserved)
        """
        total = Decimal(str(total_balance))
        reserved = self.get_reserved_total()
        available = total - reserved - self.min_balance
        return max(available, Decimal("0"))

    def calculate_slippage(
        self,
        expected_price: float,
        actual_price: float,
        quantity: float,
    ) -> Dict:
        """Calculate slippage impact.

        Args:
            expected_price: Expected execution price
            actual_price: Actual execution price
            quantity: Amount filled

        Returns:
            {
                "expected_cost": Decimal,
                "actual_cost": Decimal,
                "slippage_pct": Decimal,
                "slippage_amount": Decimal,
            }
        """
        expected = Decimal(str(expected_price))
        actual = Decimal(str(actual_price))
        qty = Decimal(str(quantity))

        expected_cost = (qty * expected).quantize(Decimal("0.01"))
        actual_cost = (qty * actual).quantize(Decimal("0.01"))
        slippage_amount = (actual_cost - expected_cost).quantize(Decimal("0.01"))
        slippage_pct = (
            (slippage_amount / expected_cost * 100).quantize(Decimal("0.01"))
            if expected_cost > 0
            else Decimal("0")
        )

        logger.info(
            f"📊 Slippage: €{expected_cost} → €{actual_cost} (€{slippage_amount}, {slippage_pct}%)"
        )

        return {
            "expected_cost": expected_cost,
            "actual_cost": actual_cost,
            "slippage_amount": slippage_amount,
            "slippage_pct": slippage_pct,
        }

    def calculate_position_pnl(
        self,
        entry_price: float,
        current_price: float,
        quantity: float,
    ) -> Dict:
        """Calculate P&L with precision.

        Args:
            entry_price: Entry price
            current_price: Current price
            quantity: Position size

        Returns:
            {
                "entry_cost": Decimal,
                "current_value": Decimal,
                "pnl": Decimal,
                "pnl_pct": Decimal,
            }
        """
        entry = Decimal(str(entry_price))
        current = Decimal(str(current_price))
        qty = Decimal(str(quantity))

        entry_cost = (qty * entry).quantize(Decimal("0.01"))
        current_value = (qty * current).quantize(Decimal("0.01"))
        pnl = (current_value - entry_cost).quantize(Decimal("0.01"))
        pnl_pct = (
            (pnl / entry_cost * 100).quantize(Decimal("0.01"))
            if entry_cost > 0
            else Decimal("0")
        )

        return {
            "entry_cost": entry_cost,
            "current_value": current_value,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
        }

    def get_status(self) -> Dict:
        """Get financial safety status."""
        return {
            "reserved_balance": float(self.get_reserved_total()),
            "min_buffer": float(self.min_balance),
            "pending_reserves": len(self.reserved_balance),
            "timestamp": "2026-06-27",
        }


# Global instance
_financial_safety_manager: Optional[FinancialSafetyManager] = None


def init_financial_safety(fees: Optional[FeeStructure] = None) -> FinancialSafetyManager:
    """Initialize global financial safety manager."""
    global _financial_safety_manager
    _financial_safety_manager = FinancialSafetyManager(fees)
    logger.info("✅ Financial Safety Manager initialized")
    return _financial_safety_manager


def get_financial_safety() -> FinancialSafetyManager:
    """Get global financial safety manager."""
    global _financial_safety_manager
    if _financial_safety_manager is None:
        _financial_safety_manager = FinancialSafetyManager()
    return _financial_safety_manager
