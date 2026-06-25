"""Paper Trading Engine - Simulate order fills at real Binance prices (FR-002)."""

import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Literal
from dataclasses import dataclass, asdict
import json
from pathlib import Path

from backend.core.database import get_database

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """Open trading position."""

    symbol: str
    side: Literal["LONG", "SHORT"]
    quantity: float
    entry_price: float
    entry_time: datetime
    current_price: float
    unrealized_pnl: float = 0.0
    db_id: Optional[int] = None  # Database ID for persistence


@dataclass
class Trade:
    """Completed trade record."""

    timestamp: datetime
    symbol: str
    side: Literal["BUY", "SELL"]
    quantity: float
    price: float
    fee: float
    realized_pnl: float
    order_id: str
    mode: Literal["PAPER", "LIVE"]
    status: Literal["FILLED", "CANCELLED"]

    def to_dict(self) -> Dict:
        """Convert to dictionary (JSON serializable)."""
        d = asdict(self)
        d["timestamp"] = self.timestamp.isoformat()
        return d


class PaperTradingEngine:
    """Simulate trading with real Binance prices, zero risk."""

    SLIPPAGE_MARKET = 0.001  # 0.1% for market orders
    SLIPPAGE_LIMIT = 0.0005  # 0.05% for limit orders
    FEE_RATE = 0.001  # 0.1% trading fee (Binance)
    AUDIT_LOG = Path("logs/trades.jsonl")

    def __init__(self, starting_capital: float = 10000.0):
        """Initialize paper trading engine.

        Args:
            starting_capital: Starting balance in EUR
        """
        self.starting_capital = starting_capital
        self.cash = starting_capital
        self.positions: Dict[str, Position] = {}
        self.trade_history: List[Trade] = []
        self.daily_pnl = 0.0
        self.total_pnl = 0.0
        self.last_daily_reset = datetime.utcnow().date()

        # Ensure logs directory exists
        self.AUDIT_LOG.parent.mkdir(exist_ok=True)

        # Restore positions from database (Pillar #5: State Persistence)
        self._restore_positions_from_db()

    async def place_order(
        self,
        symbol: str,
        side: Literal["BUY", "SELL"],
        quantity: float,
        current_price: float,
        order_type: Literal["MARKET", "LIMIT"] = "MARKET",
        limit_price: Optional[float] = None,
        strategy_name: Optional[str] = None,
    ) -> Dict:
        """Place a simulated order at real Binance price.

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            side: BUY or SELL
            quantity: Order quantity
            current_price: Current market price from WebSocket
            order_type: MARKET or LIMIT
            limit_price: Limit price if LIMIT order
            strategy_name: Optional name of strategy that generated the signal (e.g., 'momentum', 'reversion')

        Returns:
            Order confirmation with fill details
        """
        try:
            # Validate inputs
            if quantity <= 0:
                return {
                    "status": "REJECTED",
                    "reason": "Quantity must be positive",
                }

            if side == "BUY" and self.cash < quantity * current_price:
                return {
                    "status": "REJECTED",
                    "reason": "Insufficient cash",
                }

            # Calculate fill price with slippage
            slippage = self.SLIPPAGE_MARKET if order_type == "MARKET" else self.SLIPPAGE_LIMIT
            if side == "BUY":
                fill_price = current_price * (1 + slippage)
            else:  # SELL
                fill_price = current_price * (1 - slippage)

            # Calculate fee
            gross_amount = quantity * fill_price
            fee = gross_amount * self.FEE_RATE

            # HARDENING: Validate order fill (Pillar #4: Order Execution)
            # Verify: 1) Fill quantity matches requested, 2) Fill price in bounds, 3) Log discrepancies
            fill_quantity = quantity  # Paper trading always fills the entire order
            slippage_pct = abs(fill_price - current_price) / current_price * 100

            if fill_quantity != quantity:
                logger.error(
                    f"PARTIAL FILL DETECTED: {symbol} requested {quantity} but filled {fill_quantity}"
                )
                return {
                    "status": "PARTIAL",
                    "reason": f"Requested {quantity}, filled {fill_quantity}",
                }

            expected_min = current_price * (1 - slippage - 0.001)  # Slippage + 0.1% tolerance
            expected_max = current_price * (1 + slippage + 0.001)
            if not (expected_min < fill_price < expected_max):
                logger.warning(
                    f"UNEXPECTED SLIPPAGE: {symbol} {side} @ {fill_price:.2f} "
                    f"vs expected {current_price:.2f} (slippage {slippage_pct:.2f}%)"
                )

            logger.debug(
                f"ORDER_FILL_VALIDATED: {symbol} {side} {fill_quantity} "
                f"@ {fill_price:.2f} (slippage {slippage_pct:.2f}%)"
            )

            # Update positions and cash
            entry_price_for_analytics = None
            now = datetime.utcnow()
            if side == "BUY":
                self.cash -= gross_amount + fee

                # Save position to database first (Pillar #5: State Persistence)
                db_id = None
                try:
                    db = get_database()
                    db_id = db.insert_position(symbol, quantity, fill_price, now)
                except Exception as e:
                    logger.error(f"Failed to save position to DB: {e}")

                position = Position(
                    symbol=symbol,
                    side="LONG",
                    quantity=quantity,
                    entry_price=fill_price,
                    entry_time=now,
                    current_price=fill_price,
                    db_id=db_id,
                )
                self.positions[symbol] = position
                realized_pnl = 0.0

            else:  # SELL
                if symbol not in self.positions:
                    return {
                        "status": "REJECTED",
                        "reason": f"No position in {symbol}",
                    }

                position = self.positions[symbol]
                entry_price_for_analytics = position.entry_price
                realized_pnl = (fill_price - position.entry_price) * quantity - fee
                self.total_pnl += realized_pnl
                self.daily_pnl += realized_pnl
                self.cash += gross_amount - fee

                # Mark position as closed in database (Pillar #5: State Persistence)
                if position.db_id:
                    try:
                        db = get_database()
                        db.close_position(position.db_id)
                    except Exception as e:
                        logger.error(f"Failed to close position in DB: {e}")

                del self.positions[symbol]

            # Create trade record
            order_id = str(uuid.uuid4())
            trade = Trade(
                timestamp=datetime.utcnow(),
                symbol=symbol,
                side=side,
                quantity=quantity,
                price=fill_price,
                fee=fee,
                realized_pnl=realized_pnl,
                order_id=order_id,
                mode="PAPER",
                status="FILLED",
            )

            self.trade_history.append(trade)
            self._log_trade(trade)

            # Log trade to database (Pillar #5: State Persistence - audit trail)
            try:
                db = get_database()
                db.insert_trade(
                    symbol=symbol,
                    side=side,
                    quantity=quantity,
                    price=fill_price,
                    trade_time=now,
                    order_id=order_id,
                    slippage_pct=(abs(fill_price - current_price) / current_price * 100),
                )
            except Exception as e:
                logger.error(f"Failed to log trade to DB: {e}")

            # Record to strategy analytics if strategy_name provided
            if strategy_name and side == "SELL" and entry_price_for_analytics:
                try:
                    from backend.analytics.strategy_analytics import get_analytics
                    analytics = get_analytics()
                    if analytics:
                        analytics.record_trade(
                            strategy_name=strategy_name,
                            pnl=realized_pnl,
                            quantity=quantity,
                            entry_price=entry_price_for_analytics,
                            exit_price=fill_price,
                        )
                        logger.info(f"Recorded {strategy_name} trade for {symbol}: P&L ${realized_pnl:.2f}")
                except Exception as e:
                    logger.warning(f"Could not record strategy analytics: {e}")

            logger.info(
                f"PAPER FILLED: {side} {quantity} {symbol} @ {fill_price:.2f} | "
                f"Fee: {fee:.2f} | P&L: {realized_pnl:.2f}"
            )

            return {
                "status": "FILLED",
                "order_id": order_id,
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "fill_price": fill_price,
                "fee": fee,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error placing order: {e}")
            return {"status": "ERROR", "reason": str(e)}

    def mark_to_market(self, prices: Dict[str, float]) -> None:
        """Update position values at current market prices.

        Args:
            prices: Dict of {symbol: current_price}
        """
        for symbol, position in self.positions.items():
            if symbol in prices:
                position.current_price = prices[symbol]
                position.unrealized_pnl = (
                    prices[symbol] - position.entry_price
                ) * position.quantity

    def _check_and_reset_daily_pnl(self) -> None:
        """Reset daily P&L at UTC midnight (00:00)."""
        today = datetime.utcnow().date()
        if today > self.last_daily_reset:
            logger.info(
                f"Daily reset: Daily P&L was {self.daily_pnl:.2f}, now reset to 0.0"
            )
            self.daily_pnl = 0.0
            self.last_daily_reset = today

    def get_account_state(self) -> Dict:
        """Get current account state."""
        self._check_and_reset_daily_pnl()

        positions_value = sum(
            p.current_price * p.quantity for p in self.positions.values()
        )
        total_equity = self.cash + positions_value

        return {
            "mode": "PAPER",
            "cash": round(self.cash, 2),
            "positions_value": round(positions_value, 2),
            "total_equity": round(total_equity, 2),
            "daily_pnl": round(self.daily_pnl, 2),
            "total_pnl": round(self.total_pnl, 2),
            "active_positions": len(self.positions),
            "trades_today": len(
                [t for t in self.trade_history if self._is_today(t.timestamp)]
            ),
            "last_update": datetime.utcnow().isoformat(),
        }

    def get_positions(self) -> List[Dict]:
        """Get list of open positions."""
        return [
            {
                "symbol": p.symbol,
                "quantity": p.quantity,
                "entry_price": round(p.entry_price, 2),
                "current_price": round(p.current_price, 2),
                "unrealized_pnl": round(p.unrealized_pnl, 2),
                "unrealized_pnl_pct": round(
                    (p.unrealized_pnl / (p.entry_price * p.quantity)) * 100, 2
                ),
            }
            for p in self.positions.values()
        ]

    def get_trades(self, limit: int = 100) -> List[Dict]:
        """Get trade history."""
        return [t.to_dict() for t in self.trade_history[-limit:]]

    def reset(self) -> None:
        """Reset account to starting state."""
        self.cash = self.starting_capital
        self.positions.clear()
        self.trade_history.clear()
        self.daily_pnl = 0.0
        self.total_pnl = 0.0
        logger.info("Paper trading account reset")

    def _log_trade(self, trade: Trade) -> None:
        """Log trade to audit trail (append-only)."""
        try:
            with open(self.AUDIT_LOG, "a") as f:
                f.write(json.dumps(trade.to_dict()) + "\n")
        except Exception as e:
            logger.error(f"Failed to log trade: {e}")

    @staticmethod
    def _is_today(dt: datetime) -> bool:
        """Check if datetime is today."""
        today = datetime.utcnow().date()
        return dt.date() == today

    def _restore_positions_from_db(self) -> None:
        """Restore open positions from database on startup (Pillar #5 hardening).

        This prevents orphaned positions if the API crashes while holding positions.
        """
        try:
            db = get_database()
            db_positions = db.get_open_positions()

            if not db_positions:
                logger.info("No orphaned positions to restore from database")
                return

            logger.critical(f"RECOVERING {len(db_positions)} ORPHANED POSITIONS FROM DATABASE!")

            for db_pos in db_positions:
                symbol = db_pos["symbol"]
                quantity = db_pos["quantity"]
                entry_price = db_pos["entry_price"]
                pos_id = db_pos["id"]

                # Parse entry_time if it's a string
                entry_time = db_pos["entry_time"]
                if isinstance(entry_time, str):
                    entry_time = datetime.fromisoformat(entry_time)

                # Restore position to in-memory state
                self.positions[symbol] = Position(
                    symbol=symbol,
                    side="LONG",
                    quantity=quantity,
                    entry_price=entry_price,
                    entry_time=entry_time,
                    current_price=entry_price,  # Will be updated at next mark-to-market
                    db_id=pos_id,
                )

                logger.critical(f"RESTORED: {symbol} {quantity} @ {entry_price} (db_id={pos_id})")

        except Exception as e:
            logger.error(f"Failed to restore positions from DB: {e}")


# Global paper trading engine
_paper_engine: Optional[PaperTradingEngine] = None


def init_paper_trading(
    starting_capital: float = 10000.0,
) -> PaperTradingEngine:
    """Initialize global paper trading engine."""
    global _paper_engine
    _paper_engine = PaperTradingEngine(starting_capital)
    return _paper_engine


def get_paper_trading() -> Optional[PaperTradingEngine]:
    """Get global paper trading engine."""
    return _paper_engine
