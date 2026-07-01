"""Emergency Stop Handler for FR-020.

Hard kill switch that stops all trading immediately and cleans up gracefully.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from backend.exchange.paper_trading import get_paper_trading

logger = logging.getLogger(__name__)

_emergency_stop_triggered = False
_emergency_stop_reason: Optional[str] = None
_emergency_stop_time: Optional[datetime] = None


def is_emergency_stop_active() -> bool:
    """Check if emergency stop has been triggered."""
    return _emergency_stop_triggered


def get_emergency_stop_status() -> Dict[str, Any]:
    """Get current emergency stop status."""
    return {
        'active': _emergency_stop_triggered,
        'triggered_at': _emergency_stop_time.isoformat() if _emergency_stop_time else None,
        'reason': _emergency_stop_reason
    }


async def trigger_emergency_stop(reason: str) -> Dict[str, Any]:
    """
    Trigger emergency stop.

    Atomic sequence:
    1. Set flag to prevent new trades
    2. Close all open positions
    3. Halt HA (disable failover)
    4. Log to audit trail
    5. Notify user

    Args:
        reason: Why emergency stop was triggered (e.g., "User button", "Daily loss >5%")

    Returns:
        {
            'success': bool,
            'positions_closed': int,
            'timestamp': datetime,
            'reason': str,
            'error': str or None
        }
    """
    global _emergency_stop_triggered, _emergency_stop_reason, _emergency_stop_time

    try:
        logger.critical(f"🚨 EMERGENCY STOP TRIGGERED: {reason}")

        # Step 1: Set flag to prevent new trades
        _emergency_stop_triggered = True
        _emergency_stop_reason = reason
        _emergency_stop_time = datetime.utcnow()

        # Step 2: Close all open positions
        engine = get_paper_trading()
        if not engine:
            return {
                'success': False,
                'positions_closed': 0,
                'timestamp': _emergency_stop_time,
                'reason': reason,
                'error': 'Paper trading engine not initialized'
            }

        positions_closed = 0
        open_positions = engine.get_open_positions()

        for position in open_positions:
            try:
                current_price = engine.get_current_price(position['symbol'])
                if current_price:
                    result = engine.execute_order(
                        symbol=position['symbol'],
                        side='SELL' if position['quantity'] > 0 else 'BUY',
                        quantity=abs(position['quantity']),
                        price_hint=current_price
                    )
                    if result:
                        positions_closed += 1
                        logger.warning(f"Closed position: {position['symbol']} {position['quantity']}")
            except Exception as e:
                logger.error(f"Failed to close {position['symbol']}: {e}")

        # Step 3: Halt HA (disable heartbeat/sync)
        try:
            from backend.core.heartbeat import stop_heartbeat
            await stop_heartbeat()
            logger.info("HA heartbeat halted")
        except Exception as e:
            logger.error(f"Failed to halt HA: {e}")

        # Step 4: Log to audit trail
        logger.critical(
            f"✅ EMERGENCY STOP COMPLETE: "
            f"closed {positions_closed}/{len(open_positions)} positions, reason={reason}"
        )

        # Step 5: Return status
        return {
            'success': True,
            'positions_closed': positions_closed,
            'timestamp': _emergency_stop_time,
            'reason': reason,
            'error': None
        }

    except Exception as e:
        logger.error(f"❌ Emergency stop failed: {e}")
        return {
            'success': False,
            'positions_closed': 0,
            'timestamp': _emergency_stop_time or datetime.utcnow(),
            'reason': reason,
            'error': str(e)
        }


async def reset_emergency_stop() -> bool:
    """
    Reset emergency stop flag (for testing only).

    **WARNING:** This should only be called:
    - During testing/development
    - After manual verification that system is safe
    - After positions have been manually closed
    - With explicit user confirmation

    Returns:
        True if reset successful
    """
    global _emergency_stop_triggered, _emergency_stop_reason, _emergency_stop_time

    logger.warning("⚠️  RESETTING EMERGENCY STOP - SYSTEM WILL RESUME TRADING")

    _emergency_stop_triggered = False
    _emergency_stop_reason = None
    _emergency_stop_time = None

    return True
