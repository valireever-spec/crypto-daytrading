"""Stop Loss Safety: Retry + Escalation + Circuit Breaker

Prevents:
- Stop loss failures going silent
- Position losses exceeding limits
- Cascading failures (one SL fail → many)
- Manual intervention delays
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class StopLossOrder:
    """Tracks a single stop loss order."""
    order_id: str
    symbol: str
    position_size: float
    trigger_price: float
    limit_price: float
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    execution_attempts: int = 0
    max_attempts: int = 5
    status: str = "PENDING"  # PENDING → TRIGGERED → FILLED → FAILED → ESCALATED
    last_failure_reason: Optional[str] = None
    last_attempt_time: Optional[str] = None
    filled_price: Optional[float] = None
    filled_quantity: Optional[float] = None


class StopLossSafetyManager:
    """Manage stop loss execution with retry & escalation."""

    def __init__(self):
        """Initialize stop loss safety manager."""
        self.active_orders: Dict[str, StopLossOrder] = {}
        self.execution_history: List[StopLossOrder] = []
        self.circuit_breaker_open = False
        self.consecutive_failures = 0
        self.failure_threshold = 3
        self.escalation_queue: List[StopLossOrder] = []

    def create_stop_loss(
        self,
        symbol: str,
        position_size: float,
        trigger_price: float,
        limit_price: float,
    ) -> StopLossOrder:
        """Create a stop loss order.

        Args:
            symbol: Trading pair
            position_size: Size of position to close
            trigger_price: Price at which to trigger
            limit_price: Price to sell at (minimum)

        Returns:
            StopLossOrder
        """
        import uuid
        order_id = str(uuid.uuid4())[:8]

        order = StopLossOrder(
            order_id=order_id,
            symbol=symbol,
            position_size=position_size,
            trigger_price=trigger_price,
            limit_price=limit_price,
        )

        self.active_orders[order_id] = order
        logger.info(
            f"🛑 Stop loss created: {order_id} ({symbol} {position_size} @ €{trigger_price})"
        )

        return order

    async def execute_stop_loss(
        self,
        order_id: str,
        execute_fn,
    ) -> bool:
        """Execute stop loss with retry logic.

        Args:
            order_id: Stop loss order ID
            execute_fn: Async function to execute trade (price → success)

        Returns:
            True if executed, False if failed/escalated
        """
        if order_id not in self.active_orders:
            logger.error(f"❌ Stop loss not found: {order_id}")
            return False

        order = self.active_orders[order_id]

        # Check circuit breaker
        if self.circuit_breaker_open:
            logger.critical(
                f"🚨 Circuit breaker OPEN - stop loss {order_id} ESCALATED without retry"
            )
            order.status = "ESCALATED"
            self.escalation_queue.append(order)
            await self._escalate_stop_loss(order)
            return False

        # Retry loop
        while order.execution_attempts < order.max_attempts:
            try:
                order.execution_attempts += 1
                order.last_attempt_time = datetime.utcnow().isoformat()

                logger.info(
                    f"▶️  Stop loss execution attempt {order.execution_attempts}/{order.max_attempts}: {order_id}"
                )

                # Execute with current price
                success, filled_price, filled_qty = await execute_fn(
                    order.symbol,
                    "SELL",
                    order.position_size,
                    order.limit_price,
                )

                if success:
                    order.status = "FILLED"
                    order.filled_price = filled_price
                    order.filled_quantity = filled_qty
                    self.consecutive_failures = 0
                    self.execution_history.append(order)

                    logger.info(
                        f"✅ Stop loss FILLED: {order_id} - {filled_qty} @ €{filled_price:.2f}"
                    )
                    return True

                else:
                    # Execution failed, will retry
                    order.last_failure_reason = "Execution failed"
                    await asyncio.sleep(1)  # Brief wait before retry

            except Exception as e:
                order.last_failure_reason = str(e)
                logger.warning(
                    f"⚠️  Stop loss attempt {order.execution_attempts} failed: {e}"
                )
                await asyncio.sleep(1)

        # Max retries exceeded
        self.consecutive_failures += 1
        order.status = "FAILED"
        self.execution_history.append(order)

        logger.error(
            f"❌ Stop loss FAILED after {order.max_attempts} attempts: {order_id}"
        )

        # Check if circuit breaker should open
        if self.consecutive_failures >= self.failure_threshold:
            await self._open_circuit_breaker()

        # Escalate
        await self._escalate_stop_loss(order)

        return False

    async def _open_circuit_breaker(self) -> None:
        """Open circuit breaker to prevent cascading failures."""
        self.circuit_breaker_open = True
        logger.critical(
            f"🚨 CIRCUIT BREAKER OPEN: {self.consecutive_failures} consecutive stop loss failures"
        )

        # Alert user
        from backend.core.alerting import get_alert_manager
        alert_mgr = get_alert_manager()
        await alert_mgr.alert_circuit_breaker_open(
            f"Stop loss failures: {self.consecutive_failures} consecutive failures, trading HALTED"
        )

    async def _escalate_stop_loss(self, order: StopLossOrder) -> None:
        """Escalate failed stop loss to manual intervention.

        Args:
            order: Failed stop loss order
        """
        self.escalation_queue.append(order)

        logger.critical(
            f"🚨 ESCALATING stop loss {order.order_id} to manual intervention queue"
        )

        from backend.core.alerting import get_alert_manager
        alert_mgr = get_alert_manager()
        await alert_mgr.alert_primary_unhealthy(
            f"Stop loss escalation: {order.symbol} {order.position_size} position needs manual close"
        )

    def check_triggers(self, current_prices: Dict[str, float]) -> List[str]:
        """Check which stop losses should trigger.

        Args:
            current_prices: {symbol: price}

        Returns:
            List of order_ids that should trigger
        """
        triggered = []

        for order_id, order in self.active_orders.items():
            if order.status != "PENDING":
                continue

            current_price = current_prices.get(order.symbol)
            if current_price is None:
                continue

            # Check if price hit trigger
            if current_price <= order.trigger_price:
                logger.warning(
                    f"⚠️  Stop loss triggered: {order_id} ({order.symbol} @ €{current_price:.2f})"
                )
                triggered.append(order_id)

        return triggered

    def get_pending_orders(self) -> List[StopLossOrder]:
        """Get all pending stop losses."""
        return [o for o in self.active_orders.values() if o.status == "PENDING"]

    def get_escalation_queue(self) -> List[StopLossOrder]:
        """Get orders needing manual intervention."""
        return self.escalation_queue

    def reset_circuit_breaker(self) -> None:
        """Reset circuit breaker (after manual intervention)."""
        self.circuit_breaker_open = False
        self.consecutive_failures = 0
        self.escalation_queue.clear()
        logger.info("🟢 Circuit breaker RESET")

    def get_status(self) -> Dict:
        """Get stop loss safety status."""
        return {
            "pending": len(self.get_pending_orders()),
            "executed": len([o for o in self.execution_history if o.status == "FILLED"]),
            "failed": len([o for o in self.execution_history if o.status == "FAILED"]),
            "circuit_breaker_open": self.circuit_breaker_open,
            "consecutive_failures": self.consecutive_failures,
            "escalations_pending": len(self.escalation_queue),
            "timestamp": datetime.utcnow().isoformat(),
        }


# Global instance
_stop_loss_safety_manager: Optional[StopLossSafetyManager] = None


def init_stop_loss_safety() -> StopLossSafetyManager:
    """Initialize global stop loss safety manager."""
    global _stop_loss_safety_manager
    _stop_loss_safety_manager = StopLossSafetyManager()
    logger.info("✅ Stop Loss Safety Manager initialized")
    return _stop_loss_safety_manager


def get_stop_loss_safety() -> StopLossSafetyManager:
    """Get global stop loss safety manager."""
    global _stop_loss_safety_manager
    if _stop_loss_safety_manager is None:
        _stop_loss_safety_manager = StopLossSafetyManager()
    return _stop_loss_safety_manager
