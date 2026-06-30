"""Integrated dashboard endpoint combining account, positions, and trades data."""

import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Dashboard"])


@router.get("/api/dashboard")
async def get_dashboard() -> JSONResponse:
    """Get comprehensive dashboard data (account, positions, trades, strategies)."""
    try:
        from backend.exchange.paper_trading import get_paper_trading

        engine = get_paper_trading()
        if not engine:
            raise HTTPException(status_code=500, detail="Paper trading engine not initialized")

        # Get account data
        cash = getattr(engine, 'cash', 0)

        # Get positions safely
        try:
            all_positions = engine.get_positions() if hasattr(engine, 'get_positions') else []
            positions = [p for p in all_positions if isinstance(p, dict) and p.get('status') == 'open']
        except Exception as pos_err:
            logger.warning(f"Could not fetch positions: {pos_err}")
            positions = []

        # Get trades safely
        try:
            all_trades = engine.get_all_trades() if hasattr(engine, 'get_all_trades') else []
            recent_trades = all_trades[-20:] if all_trades else []
        except Exception as trade_err:
            logger.warning(f"Could not fetch trades: {trade_err}")
            all_trades = []
            recent_trades = []

        # Calculate portfolio metrics safely
        try:
            invested = sum(p.get('quantity', 0) * p.get('current_price', 0) for p in positions if isinstance(p, dict))
            total_balance = cash + invested
            total_pnl = sum(p.get('unrealized_pnl', 0) for p in positions if isinstance(p, dict))
            total_pnl += sum(t.get('realized_pnl', 0) for t in all_trades if isinstance(t, dict))
            daily_pnl = sum(t.get('realized_pnl', 0) for t in recent_trades if isinstance(t, dict))
            pnl_pct = (total_pnl / total_balance * 100) if total_balance > 0 else 0
        except Exception as calc_err:
            logger.warning(f"Could not calculate metrics: {calc_err}")
            invested = 0
            total_balance = cash
            total_pnl = 0
            daily_pnl = 0
            pnl_pct = 0

        return {
            "cash": cash,
            "total_pnl": total_pnl,
            "daily_pnl": daily_pnl,
            "positions": positions,
            "recent_trades": recent_trades,
            "account": {
                "total_balance": total_balance,
                "cash": cash,
                "invested": invested,
                "pnl": total_pnl,
                "pnl_pct": pnl_pct
            }
        }
    except Exception as e:
        logger.error(f"Error getting dashboard data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/paper/order")
async def place_paper_order(symbol: str, side: str, quantity: float) -> JSONResponse:
    """Place a market order in paper trading."""
    try:
        if side not in ['buy', 'sell']:
            raise HTTPException(status_code=400, detail="Side must be 'buy' or 'sell'")

        from backend.exchange.paper_trading import get_paper_trading

        engine = get_paper_trading()
        if not engine:
            raise HTTPException(status_code=500, detail="Paper trading engine not initialized")

        order = engine.place_market_order(
            symbol=symbol,
            side=side,
            quantity=quantity,
            source='manual_order'
        )

        logger.info(f"✅ Order placed: {side.upper()} {quantity:.4f} {symbol}")

        return {
            "status": "success",
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "order_id": order.get('id') if order else None,
            "price": order.get('price') if order else None
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error placing order: {e}")
        raise HTTPException(status_code=500, detail=str(e))
