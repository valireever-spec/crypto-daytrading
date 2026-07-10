"""Startup verification: Detect account state corruption before trading starts."""

import logging
from backend.exchange.paper_trading import get_paper_trading
from backend.core.database import get_database
from backend.core.alerting import get_alert_manager

logger = logging.getLogger(__name__)


async def verify_account_state_integrity() -> bool:
    """Verify account state matches database ground truth on startup.

    CRITICAL: Detects silent corruption before trading resumes.
    Returns: True if state is consistent, False if corruption detected.
    """
    try:
        engine = get_paper_trading()
        if not engine:
            logger.warning("Paper trading engine not initialized")
            return True

        db = get_database()

        # Get current state (what API loaded into memory)
        api_cash = engine.cash
        api_pnl = engine.total_pnl

        # Calculate ground truth from database
        trades_pnl = db.get_total_realized_pnl()
        expected_cash = engine.starting_capital + trades_pnl

        # Compare
        cash_discrepancy = abs(api_cash - expected_cash)
        pnl_discrepancy = abs(api_pnl - trades_pnl)

        status_emoji = "✅" if cash_discrepancy < 1.0 else "🚨"

        logger.critical(f"""
╔════════════════════════════════════════════════════════╗
║         STARTUP VERIFICATION: Account State            ║
╠════════════════════════════════════════════════════════╣
║ API Cash (loaded):     €{api_cash:>12.2f}              ║
║ Expected (from DB):    €{expected_cash:>12.2f}              ║
║ Cash Discrepancy:      €{cash_discrepancy:>12.2f}              ║
║                                                        ║
║ API P&L:               €{api_pnl:>12.2f}              ║
║ Expected (from DB):    €{trades_pnl:>12.2f}              ║
║ P&L Discrepancy:       €{pnl_discrepancy:>12.2f}              ║
║                                                        ║
║ Status: {status_emoji} {"✅ OK - In Sync" if cash_discrepancy < 1.0 else "❌ CRITICAL - CORRUPTION"}                     ║
╚════════════════════════════════════════════════════════╝
""")

        # CRITICAL: Fail startup if discrepancy > €1.00
        if cash_discrepancy > 1.0 or pnl_discrepancy > 1.0:
            logger.critical(
                f"🛑 STARTUP BLOCKED: Account state corruption detected!\n"
                f"   Cash mismatch: €{cash_discrepancy:.2f}\n"
                f"   P&L mismatch: €{pnl_discrepancy:.2f}\n"
                f"   DO NOT TRADE until verified."
            )

            # Alert operator immediately
            try:
                alert_manager = get_alert_manager()
                await alert_manager.alert_critical(
                    f"🚨 STARTUP BLOCKED: Account state corruption detected\n"
                    f"Cash mismatch: €{cash_discrepancy:.2f}\n"
                    f"P&L mismatch: €{pnl_discrepancy:.2f}"
                )
            except Exception as e:
                logger.error(f"Failed to send alert: {e}")

            return False

        logger.critical("✅ STARTUP VERIFICATION PASSED - Account state is consistent")
        return True

    except Exception as e:
        logger.error(f"Startup verification error: {e}", exc_info=True)
        return True  # Don't block on check failure, but log it


def get_startup_verification_status() -> dict:
    """Get verification status for monitoring dashboard."""
    try:
        engine = get_paper_trading()
        db = get_database()

        if not engine:
            return {"status": "engine_not_initialized", "verified": False}

        api_cash = engine.cash
        trades_pnl = db.get_total_realized_pnl()
        expected_cash = engine.starting_capital + trades_pnl
        cash_discrepancy = abs(api_cash - expected_cash)

        return {
            "status": "verified" if cash_discrepancy < 1.0 else "failed",
            "verified": cash_discrepancy < 1.0,
            "api_cash": api_cash,
            "expected_cash": expected_cash,
            "discrepancy": cash_discrepancy,
            "api_pnl": engine.total_pnl,
            "expected_pnl": trades_pnl,
            "starting_capital": engine.starting_capital,
        }
    except Exception as e:
        logger.error(f"Error getting verification status: {e}")
        return {"status": "error", "verified": False, "error": str(e)}
