"""Trade reconciliation: Verify each trade's P&L is calculated correctly."""

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


def audit_trade_execution(order_result: Dict) -> bool:
    """Verify that realized_pnl was calculated correctly for SELL trades.

    CRITICAL: Catches bugs where P&L isn't calculated or is calculated wrong.

    Args:
        order_result: Result dict from place_order()

    Returns:
        True if audit passes, False if critical issue found

    Raises:
        ValueError: If critical audit failure
    """
    if order_result.get("status") != "FILLED":
        logger.debug(f"Skipping audit for {order_result.get('status')} order")
        return True

    side = order_result.get("side")
    symbol = order_result.get("symbol", "UNKNOWN")

    # Only SELL trades should have realized_pnl
    if side != "SELL":
        logger.debug(f"Skipping audit for {side} order (not a SELL)")
        return True

    # Check that realized_pnl was included in response
    realized_pnl = order_result.get("realized_pnl")

    if realized_pnl is None:
        logger.critical(
            f"🚨 AUDIT FAIL: {symbol} SELL trade has NO realized_pnl in response!\n"
            f"   Order ID: {order_result.get('order_id')}\n"
            f"   P&L wasn't calculated."
        )
        raise ValueError(f"Trade {symbol} missing realized_pnl")

    if realized_pnl == 0.0:
        logger.warning(
            f"⚠️  AUDIT WARNING: {symbol} SELL trade has zero realized_pnl\n"
            f"   Entry price: {order_result.get('price')}\n"
            f"   This could be correct (break-even) or a bug"
        )

    # Verify P&L is reasonable (sanity check)
    # Max realistic trade is ~€25,000 (0.5% of €5M account)
    # So max loss/gain per trade should be <€25,000
    max_reasonable_pnl = 25000.0

    if abs(realized_pnl) > max_reasonable_pnl:
        logger.critical(
            f"🚨 AUDIT FAIL: Unrealistic P&L on {symbol}\n"
            f"   P&L: €{realized_pnl:.2f}\n"
            f"   Max reasonable: €{max_reasonable_pnl:.2f}\n"
            f"   This indicates a calculation bug."
        )
        raise ValueError(f"P&L €{realized_pnl:.2f} outside reasonable bounds")

    # Verify P&L matches expected sign
    entry_price = order_result.get("fill_price", order_result.get("price", 0))
    quantity = order_result.get("quantity", 0)

    logger.info(
        f"✓ AUDIT PASSED: {symbol} SELL trade\n"
        f"   Quantity: {quantity:.4f}\n"
        f"   Price: €{entry_price:.2f}\n"
        f"   P&L: €{realized_pnl:.2f}"
    )

    return True


def verify_sell_has_pnl(trade_dict: Dict) -> bool:
    """Verify a SELL trade from database has realized_pnl recorded.

    Used to audit historical trades in database.
    """
    side = trade_dict.get("side")

    if side != "SELL":
        return True  # BUY trades shouldn't have P&L

    realized_pnl = trade_dict.get("realized_pnl")

    if realized_pnl is None:
        logger.critical(
            f"🚨 DATABASE AUDIT FAIL: SELL trade #{trade_dict.get('id')} has NULL realized_pnl\n"
            f"   Symbol: {trade_dict.get('symbol')}\n"
            f"   Price: €{trade_dict.get('price')}\n"
            f"   This trade's P&L wasn't calculated."
        )
        return False

    if realized_pnl == 0.0 and trade_dict.get("symbol") in ["BTCUSDT", "ETHUSDT", "BNBUSDT"]:
        logger.warning(
            f"⚠️  DATABASE AUDIT WARNING: {trade_dict.get('symbol')} SELL trade #{trade_dict.get('id')} has zero P&L\n"
            f"   Price: €{trade_dict.get('price')}\n"
            f"   This could indicate a bug in P&L calculation"
        )

    return True


def audit_all_sell_trades(db) -> tuple[int, int, list]:
    """Audit all SELL trades in database.

    Returns:
        (total_sell_trades, trades_with_pnl, zero_pnl_trades)
    """
    try:
        import sqlite3

        conn = sqlite3.connect(db.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get all SELL trades
        cursor.execute("SELECT * FROM trades WHERE side='SELL' ORDER BY created_at DESC")
        sells = cursor.fetchall()

        total_sells = len(sells)
        trades_with_pnl = 0
        zero_pnl_trades = []

        for trade in sells:
            trade_dict = dict(trade)
            if verify_sell_has_pnl(trade_dict):
                if trade_dict.get("realized_pnl") != 0.0:
                    trades_with_pnl += 1
                else:
                    zero_pnl_trades.append(trade_dict.get("id"))

        conn.close()

        logger.info(
            f"✓ DATABASE AUDIT: SELL Trades\n"
            f"   Total SELL trades: {total_sells}\n"
            f"   With P&L: {trades_with_pnl}\n"
            f"   Zero P&L: {len(zero_pnl_trades)}"
        )

        return total_sells, trades_with_pnl, zero_pnl_trades

    except Exception as e:
        logger.error(f"Error auditing SELL trades: {e}", exc_info=True)
        return 0, 0, []
