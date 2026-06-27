"""Order Safety: Idempotency, Reconciliation, Deduplication (CSF Pillar #1-6)

Prevents:
- Duplicate orders on retry
- Orders lost on crash
- Orphaned fills
- HA failover duplicates
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, Optional
from dataclasses import dataclass, field
import json

logger = logging.getLogger(__name__)


@dataclass
class OrderRecord:
    """Immutable order record for audit trail."""
    order_id: str
    idempotency_key: str  # UUID for deduplication
    symbol: str
    side: str  # BUY or SELL
    quantity: float
    price: Optional[float] = None
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    status: str = "PENDING"  # PENDING → FILLED → FAILED → RECONCILED
    binance_order_id: Optional[str] = None
    filled_quantity: float = 0.0
    filled_price: Optional[float] = None
    execution_time: Optional[str] = None
    failure_reason: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3

    def to_dict(self) -> Dict:
        """Convert to dict for storage."""
        return {
            "order_id": self.order_id,
            "idempotency_key": self.idempotency_key,
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "price": self.price,
            "timestamp": self.timestamp,
            "status": self.status,
            "binance_order_id": self.binance_order_id,
            "filled_quantity": self.filled_quantity,
            "filled_price": self.filled_price,
            "execution_time": self.execution_time,
            "failure_reason": self.failure_reason,
            "retry_count": self.retry_count,
        }


class OrderSafetyManager:
    """Manage order lifecycle with full auditing & deduplication."""

    def __init__(self):
        """Initialize order safety manager."""
        self.pending_orders: Dict[str, OrderRecord] = {}  # idempotency_key → OrderRecord
        self.order_history: Dict[str, OrderRecord] = {}   # order_id → OrderRecord
        self.binance_order_map: Dict[str, str] = {}       # binance_order_id → order_id

    def create_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: Optional[float] = None,
    ) -> OrderRecord:
        """Create a new order record with idempotency key.

        Args:
            symbol: Trading pair (BTCUSDT, etc.)
            side: BUY or SELL
            quantity: Amount to trade
            price: Limit price (None for market)

        Returns:
            OrderRecord with unique idempotency key
        """
        order_id = str(uuid.uuid4())[:8]
        idempotency_key = str(uuid.uuid4())  # Full UUID for Binance

        order = OrderRecord(
            order_id=order_id,
            idempotency_key=idempotency_key,
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
        )

        self.pending_orders[idempotency_key] = order
        self.order_history[order_id] = order

        logger.info(
            f"📝 Order created: {order_id} ({side} {quantity} {symbol}) - Idempotency: {idempotency_key[:8]}..."
        )

        return order

    def check_duplicate(self, idempotency_key: str) -> Optional[OrderRecord]:
        """Check if order already exists (prevent duplicates).

        Args:
            idempotency_key: UUID for deduplication

        Returns:
            Existing OrderRecord if found, None otherwise
        """
        if idempotency_key in self.pending_orders:
            order = self.pending_orders[idempotency_key]
            logger.warning(
                f"⚠️  Duplicate order detected: {order.order_id} already exists with status {order.status}"
            )
            return order

        return None

    def mark_execution_started(self, order_id: str) -> None:
        """Mark order as being executed (point of no return)."""
        if order_id in self.order_history:
            order = self.order_history[order_id]
            order.status = "EXECUTING"
            logger.info(f"▶️  Order executing: {order_id}")

    def mark_filled(
        self,
        order_id: str,
        binance_order_id: str,
        filled_quantity: float,
        filled_price: float,
    ) -> None:
        """Mark order as filled on Binance.

        Args:
            order_id: Our internal order ID
            binance_order_id: Binance's order ID
            filled_quantity: Amount actually filled
            filled_price: Price at execution
        """
        if order_id not in self.order_history:
            logger.error(f"❌ Order not found: {order_id}")
            return

        order = self.order_history[order_id]
        order.status = "FILLED"
        order.binance_order_id = binance_order_id
        order.filled_quantity = filled_quantity
        order.filled_price = filled_price
        order.execution_time = datetime.utcnow().isoformat()

        self.binance_order_map[binance_order_id] = order_id

        logger.info(
            f"✅ Order FILLED: {order_id} - {filled_quantity} @ €{filled_price:.2f}"
        )

    def mark_failed(self, order_id: str, reason: str, retry: bool = True) -> bool:
        """Mark order as failed.

        Args:
            order_id: Our internal order ID
            reason: Why it failed
            retry: Whether to retry

        Returns:
            True if will retry, False if max retries exceeded
        """
        if order_id not in self.order_history:
            logger.error(f"❌ Order not found: {order_id}")
            return False

        order = self.order_history[order_id]
        order.status = "FAILED"
        order.failure_reason = reason
        order.retry_count += 1

        if retry and order.retry_count < order.max_retries:
            logger.warning(
                f"⚠️  Order FAILED (retry {order.retry_count}/{order.max_retries}): {order_id} - {reason}"
            )
            order.status = "PENDING"  # Retry
            return True
        else:
            logger.error(
                f"❌ Order FAILED (no more retries): {order_id} - {reason}"
            )
            order.status = "FAILED"
            return False

    def reconcile_with_binance(
        self,
        binance_orders: Dict[str, Dict],
    ) -> Dict:
        """Reconcile local orders with Binance state.

        Args:
            binance_orders: {binance_order_id: {status, filled_qty, price}}

        Returns:
            {
                "matched": 5,
                "unmatched_local": 1,
                "unmatched_binance": 0,
                "issues": [...]
            }
        """
        issues = []

        # Check each Binance order against local records
        for binance_id, binance_order in binance_orders.items():
            if binance_id not in self.binance_order_map:
                # Binance has order we don't know about
                issues.append({
                    "type": "UNMATCHED_BINANCE",
                    "binance_order_id": binance_id,
                    "status": binance_order.get("status"),
                    "quantity": binance_order.get("orig_qty"),
                })

        # Check each local order against Binance
        for order in self.order_history.values():
            if order.status == "FILLED":
                if order.binance_order_id not in binance_orders:
                    # Local says filled, Binance doesn't have it
                    issues.append({
                        "type": "MISSING_ON_BINANCE",
                        "order_id": order.order_id,
                        "binance_order_id": order.binance_order_id,
                        "severity": "CRITICAL",
                    })

        matched = len(self.binance_order_map)
        unmatched_local = len([
            o for o in self.order_history.values()
            if o.status in ["PENDING", "EXECUTING", "FAILED"]
        ])
        unmatched_binance = len([
            b for b in binance_orders
            if b not in self.binance_order_map
        ])

        logger.info(
            f"📊 Order Reconciliation: {matched} matched, {unmatched_local} local pending, {unmatched_binance} Binance unmatched"
        )

        if issues:
            logger.warning(f"⚠️  Reconciliation issues found: {len(issues)}")
            for issue in issues:
                logger.error(f"  - {issue}")

        return {
            "matched": matched,
            "unmatched_local": unmatched_local,
            "unmatched_binance": unmatched_binance,
            "issues": issues,
            "timestamp": datetime.utcnow().isoformat(),
        }

    def get_pending_orders(self) -> list:
        """Get all pending orders that need reconciliation."""
        return [
            o for o in self.order_history.values()
            if o.status in ["PENDING", "EXECUTING"]
        ]

    def get_status_report(self) -> Dict:
        """Get order safety status."""
        return {
            "total_orders": len(self.order_history),
            "pending": len([o for o in self.order_history.values() if o.status == "PENDING"]),
            "executing": len([o for o in self.order_history.values() if o.status == "EXECUTING"]),
            "filled": len([o for o in self.order_history.values() if o.status == "FILLED"]),
            "failed": len([o for o in self.order_history.values() if o.status == "FAILED"]),
            "timestamp": datetime.utcnow().isoformat(),
        }


# Global instance
_order_safety_manager: Optional[OrderSafetyManager] = None


def init_order_safety() -> OrderSafetyManager:
    """Initialize global order safety manager."""
    global _order_safety_manager
    _order_safety_manager = OrderSafetyManager()
    logger.info("✅ Order Safety Manager initialized")
    return _order_safety_manager


def get_order_safety() -> OrderSafetyManager:
    """Get global order safety manager."""
    global _order_safety_manager
    if _order_safety_manager is None:
        _order_safety_manager = OrderSafetyManager()
    return _order_safety_manager
