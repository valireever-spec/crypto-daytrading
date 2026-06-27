"""HA Deduplication: Prevent duplicate orders on failover"""

import logging
from typing import Dict, Optional, Set
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class HADeduplicator:
    """Prevent duplicate orders when PRIMARY→BACKUP failover occurs."""

    def __init__(self, retention_hours: int = 24):
        self.retention_hours = retention_hours
        self.seen_orders: Dict[str, datetime] = {}  # idempotency_key → timestamp

    def register_order(self, idempotency_key: str) -> None:
        """Register an order (executed successfully on Binance).

        Args:
            idempotency_key: Order's idempotency key
        """
        self.seen_orders[idempotency_key] = datetime.utcnow()
        logger.debug(f"📝 Order registered for dedup: {idempotency_key[:8]}...")

    def is_duplicate(self, idempotency_key: str) -> bool:
        """Check if order already executed (prevent retry on failover).

        Args:
            idempotency_key: Order's idempotency key

        Returns:
            True if order already executed, False if new
        """
        if idempotency_key in self.seen_orders:
            logger.warning(f"⚠️  Duplicate detected on failover: {idempotency_key[:8]}...")
            return True

        return False

    def cleanup_old_entries(self) -> int:
        """Remove old entries to prevent memory leak.

        Returns:
            Number of entries cleaned up
        """
        cutoff = datetime.utcnow() - timedelta(hours=self.retention_hours)
        old_count = len(self.seen_orders)

        self.seen_orders = {
            k: v for k, v in self.seen_orders.items()
            if v > cutoff
        }

        cleaned = old_count - len(self.seen_orders)
        if cleaned > 0:
            logger.info(f"🧹 Cleaned up {cleaned} old order entries")

        return cleaned

    def get_status(self) -> Dict:
        """Get deduplication status."""
        return {
            "registered_orders": len(self.seen_orders),
            "retention_hours": self.retention_hours,
        }


# Global instance
_ha_deduplicator: Optional[HADeduplicator] = None


def get_ha_deduplicator() -> HADeduplicator:
    global _ha_deduplicator
    if _ha_deduplicator is None:
        _ha_deduplicator = HADeduplicator()
    return _ha_deduplicator
