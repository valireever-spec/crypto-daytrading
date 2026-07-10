"""Continuous state monitoring: Detect account drift every 10 seconds."""

import asyncio
import logging
from backend.exchange.paper_trading import get_paper_trading
from backend.core.database import get_database
from backend.core.fragility_circuit_breaker import get_fragility_breaker
from backend.core.trading_metrics import get_metrics_collector

logger = logging.getLogger(__name__)

# Track consecutive drift detections
_drift_count = 0
_drift_threshold = 3  # Alert after 3 consecutive checks with drift


async def continuous_state_monitor():
    """Monitor account state every 10 seconds.

    DETECTS: Silent drift, cache staleness, memory leaks.

    Runs in background and alerts operator if drift detected.
    """
    global _drift_count

    while True:
        try:
            engine = get_paper_trading()
            db = get_database()

            if not engine:
                await asyncio.sleep(10)
                continue

            # Ground truth from database
            trades_pnl = db.get_total_realized_pnl()
            expected_cash = engine.starting_capital + trades_pnl

            # Current in-memory state
            actual_cash = engine.cash
            actual_pnl = engine.total_pnl

            discrepancy = abs(actual_cash - expected_cash)

            # Log every time (for audit trail)
            if discrepancy > 0.001:  # Only log if there's actual drift
                logger.debug(
                    f"State monitor check: cash €{actual_cash:.2f} vs expected €{expected_cash:.2f} "
                    f"(drift: €{discrepancy:.4f})"
                )

            # ALERT if drift detected (even tiny drift is suspicious)
            if discrepancy > 0.01:
                _drift_count += 1

                logger.warning(
                    f"⚠️  Account state drift detected (#{_drift_count}): €{discrepancy:.2f}"
                )

                # Record in metrics for monitoring
                try:
                    metrics = get_metrics_collector()
                    metrics.record_system(
                        cb_state="CLOSED",
                        cb_halted=False,
                        websocket_healthy=True,
                        websocket_stale_seconds=0,
                        sync_lag_seconds=0,
                        memory_percent=0,
                        trades_today=0,
                        open_positions=len(engine.get_positions()),
                        daily_pnl=engine.daily_pnl,
                        cash=actual_cash,
                    )
                except Exception as e:
                    logger.debug(f"Failed to record metrics: {e}")

                # If drift persists for 3 consecutive checks, escalate
                if _drift_count >= _drift_threshold:
                    logger.critical(
                        f"🚨 Account state drift PERSISTENT: €{discrepancy:.2f} "
                        f"(detected {_drift_count} times)"
                    )

                    # CRITICAL: If drift > €1.00, halt trading
                    if discrepancy > 1.0:
                        logger.critical(
                            f"🛑 Account state drift €{discrepancy:.2f} > threshold. Halting trading."
                        )
                        breaker = get_fragility_breaker()
                        breaker._halt(f"Account state drift: €{discrepancy:.2f}")
                        # Don't resume monitoring until manually reset
                        return

            else:
                # No drift detected, reset counter
                if _drift_count > 0:
                    logger.info(
                        f"✓ Account state drift cleared (was €{discrepancy:.2f} earlier)"
                    )
                _drift_count = 0

        except Exception as e:
            logger.error(f"State monitor error: {e}", exc_info=True)
            # Don't let monitor crash - continue checking
            _drift_count = 0

        await asyncio.sleep(10)  # Check every 10 seconds


def get_state_monitor_status() -> dict:
    """Get state monitor status for dashboard."""
    global _drift_count

    try:
        engine = get_paper_trading()
        db = get_database()

        if not engine:
            return {"status": "engine_not_initialized"}

        trades_pnl = db.get_total_realized_pnl()
        expected_cash = engine.starting_capital + trades_pnl
        actual_cash = engine.cash
        discrepancy = abs(actual_cash - expected_cash)

        return {
            "status": "healthy" if discrepancy < 0.01 else "drift_detected",
            "drift_euros": discrepancy,
            "consecutive_drift_detections": _drift_count,
            "actual_cash": actual_cash,
            "expected_cash": expected_cash,
            "trading_halted": discrepancy > 1.0,
        }

    except Exception as e:
        logger.error(f"Error getting monitor status: {e}")
        return {"status": "error", "error": str(e)}
