"""Stock trading API endpoints with tax-optimized exit strategies."""

import logging
from datetime import datetime
from typing import Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.analytics.stock_analyzer import (
    init_stock_optimizer,
    get_stock_optimizer,
    StockPosition,
)
from backend.exchange.paper_trading import get_paper_trading

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/stocks", tags=["Stock Trading"])


# ==================== Pydantic Models ====================


class StockOrderInput(BaseModel):
    """Input model for stock order."""

    symbol: str  # EQ_AAPL, EQ_MSFT, etc.
    side: str  # BUY or SELL
    quantity: float
    price: float
    timestamp: str = None  # ISO format (default: now)


class PositionAnalysisInput(BaseModel):
    """Input model for exit analysis."""

    symbol: str
    quantity: float
    entry_price: float
    entry_date: str  # ISO format
    current_price: float
    volatility_pct: float = 1.0  # Daily volatility


class BreakevenAnalysisInput(BaseModel):
    """Input model for breakeven analysis."""

    symbol: str
    quantity: float
    entry_price: float
    entry_date: str  # ISO format
    target_profit_pct: float = 10.0


# ==================== API Endpoints ====================


@router.post("/initialize")
async def initialize_stock_trading(jurisdiction: str = "DE") -> Dict:
    """Initialize stock trading with tax optimization.

    Args:
        jurisdiction: Tax jurisdiction (DE, US, GB)

    Returns:
        Initialization status
    """
    try:
        optimizer = init_stock_optimizer(jurisdiction)
        return {
            "status": "initialized",
            "jurisdiction": jurisdiction,
            "features": [
                "Tax-optimized exit analysis",
                "Break-even hold period calculator",
                "FIFO tax tracking",
                "Multi-jurisdiction support",
            ],
        }
    except Exception as e:
        logger.error(f"Error initializing stock trading: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/buy")
async def buy_stock(order: StockOrderInput) -> Dict:
    """Buy a stock on Binance Equities (EQ_SYMBOL).

    Args:
        order: Stock order details

    Returns:
        Order confirmation
    """
    try:
        engine = get_paper_trading()
        if not engine:
            raise HTTPException(
                status_code=400, detail="Paper trading engine not initialized"
            )

        # Validate stock symbol format
        if not order.symbol.startswith("EQ_"):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid stock symbol: {order.symbol}. Use format EQ_AAPL, EQ_MSFT, etc.",
            )

        timestamp = order.timestamp or datetime.utcnow().isoformat()

        # Place order via paper trading engine
        result = await engine.place_order(
            symbol=order.symbol.upper(),
            side="BUY",
            quantity=order.quantity,
            current_price=order.price,
            order_type="MARKET",
            strategy_name="stock_trading",
        )

        return {
            "status": "success",
            "order_type": "BUY",
            "symbol": order.symbol,
            "quantity": order.quantity,
            "price": order.price,
            "total_cost": round(order.quantity * order.price, 2),
            "timestamp": timestamp,
            "order_id": result.get("order_id"),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error placing stock order: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sell")
async def sell_stock(order: StockOrderInput) -> Dict:
    """Sell a stock on Binance Equities.

    Args:
        order: Stock order details

    Returns:
        Order confirmation with tax summary
    """
    try:
        engine = get_paper_trading()
        if not engine:
            raise HTTPException(
                status_code=400, detail="Paper trading engine not initialized"
            )

        # Validate stock symbol
        if not order.symbol.startswith("EQ_"):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid stock symbol: {order.symbol}. Use format EQ_AAPL, EQ_MSFT, etc.",
            )

        timestamp = order.timestamp or datetime.utcnow().isoformat()

        # Get current positions to find cost basis
        positions = engine.get_positions()
        matching_pos = next((p for p in positions if p["symbol"] == order.symbol), None)

        if not matching_pos:
            raise HTTPException(
                status_code=400, detail=f"No position found for {order.symbol}"
            )

        # Calculate P&L
        cost_basis = matching_pos["quantity"] * matching_pos["entry_price"]
        proceeds = order.quantity * order.price
        gain = proceeds - cost_basis

        # Tax calculation (Germany: 42% short-term, 0% long-term >365 days)
        days_held = matching_pos.get("days_held", 0)
        if days_held >= 365:
            tax = 0  # Long-term = tax-free in Germany
            tax_status = "TAX_FREE"
        else:
            tax = gain * 0.42 * 1.055  # 42% + 5.5% solidarity
            tax_status = "TAXABLE"

        # Place order
        result = await engine.place_order(
            symbol=order.symbol.upper(),
            side="SELL",
            quantity=order.quantity,
            current_price=order.price,
            order_type="MARKET",
            strategy_name="stock_trading",
        )

        return {
            "status": "success",
            "order_type": "SELL",
            "symbol": order.symbol,
            "quantity": order.quantity,
            "price": order.price,
            "proceeds": round(proceeds, 2),
            "cost_basis": round(cost_basis, 2),
            "gain": round(gain, 2),
            "tax_status": tax_status,
            "estimated_tax": round(tax, 2),
            "net_profit": round(gain - tax, 2),
            "days_held": days_held,
            "timestamp": timestamp,
            "order_id": result.get("order_id"),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error selling stock: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze-exit")
async def analyze_exit(analysis: PositionAnalysisInput) -> Dict:
    """Analyze whether to sell now or hold for tax benefits.

    Args:
        analysis: Current position details

    Returns:
        Exit recommendation with financial analysis
    """
    try:
        optimizer = get_stock_optimizer()
        if not optimizer:
            raise HTTPException(status_code=400, detail="Stock trading not initialized")

        position = StockPosition(
            symbol=analysis.symbol,
            quantity=analysis.quantity,
            entry_price=analysis.entry_price,
            entry_date=datetime.fromisoformat(analysis.entry_date),
            current_price=analysis.current_price,
        )

        exit_analysis = optimizer.analyze_exit(position, analysis.volatility_pct)

        return {
            "symbol": exit_analysis.symbol,
            "days_held": exit_analysis.days_held,
            "current_gain": round(exit_analysis.current_gain, 2),
            "gain_percentage": round(position.unrealized_gain_pct, 2),
            "scenarios": {
                "sell_now": {
                    "profit_after_tax": round(exit_analysis.sell_now_profit, 2),
                    "tax_paid": round(exit_analysis.sell_now_tax, 2),
                    "tax_rate": "42% + 5.5% solidarity",
                },
                "hold_to_long_term": {
                    "days_remaining": exit_analysis.days_to_long_term,
                    "profit_after_tax": round(exit_analysis.hold_tax_free_profit, 2),
                    "tax_paid": 0,
                    "tax_rate": "0% (tax-free)",
                },
            },
            "financial_comparison": {
                "additional_profit_if_hold": round(
                    exit_analysis.additional_profit_if_hold, 2
                ),
                "additional_profit_pct": round(exit_analysis.additional_profit_pct, 2),
                "eur_per_day_to_hold": round(exit_analysis.time_value, 2),
            },
            "recommendation": {
                "action": exit_analysis.recommendation.value,
                "reason": exit_analysis.reason,
                "confidence": "high"
                if exit_analysis.recommendation.value == "hold_long_term"
                else "medium",
            },
            "risk_metrics": {
                "estimated_daily_loss_risk": round(
                    exit_analysis.estimated_daily_loss_risk, 2
                ),
                "volatility_pct": exit_analysis.volatility_pct,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing exit: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/breakeven-hold-period")
async def calculate_breakeven(analysis: BreakevenAnalysisInput) -> Dict:
    """Calculate optimal hold period to reach target profit.

    Args:
        analysis: Position details and target profit

    Returns:
        Timing recommendation
    """
    try:
        optimizer = get_stock_optimizer()
        if not optimizer:
            raise HTTPException(status_code=400, detail="Stock trading not initialized")

        position = StockPosition(
            symbol=analysis.symbol,
            quantity=analysis.quantity,
            entry_price=analysis.entry_price,
            entry_date=datetime.fromisoformat(analysis.entry_date),
            current_price=analysis.entry_price,  # Use entry price as baseline
        )

        breakeven = optimizer.calculate_breakeven_hold_period(
            position, analysis.target_profit_pct
        )

        return {
            "symbol": breakeven["symbol"],
            "target": {
                "profit_percentage": breakeven["target_profit_pct"],
                "target_price": breakeven["target_price"],
                "current_price": breakeven["current_price"],
                "price_to_gain": breakeven["price_to_go"],
            },
            "timing": {
                "days_held": breakeven["days_held"],
                "days_to_long_term": breakeven["days_to_long_term"],
                "recommendation": breakeven["recommendation"],
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating breakeven: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/supported-stocks")
async def get_supported_stocks() -> Dict:
    """Get list of supported Binance stock symbols.

    Returns:
        List of available stocks with details
    """
    stocks = {
        "US_LARGE_CAP": [
            {"symbol": "EQ_AAPL", "name": "Apple", "sector": "Technology"},
            {"symbol": "EQ_MSFT", "name": "Microsoft", "sector": "Technology"},
            {"symbol": "EQ_GOOGL", "name": "Alphabet (Google)", "sector": "Technology"},
            {"symbol": "EQ_AMZN", "name": "Amazon", "sector": "Consumer"},
            {"symbol": "EQ_META", "name": "Meta (Facebook)", "sector": "Technology"},
            {"symbol": "EQ_TSLA", "name": "Tesla", "sector": "Automotive"},
            {"symbol": "EQ_NVDA", "name": "Nvidia", "sector": "Technology"},
            {"symbol": "EQ_JPM", "name": "JPMorgan Chase", "sector": "Finance"},
            {"symbol": "EQ_JNJ", "name": "Johnson & Johnson", "sector": "Healthcare"},
            {"symbol": "EQ_WMT", "name": "Walmart", "sector": "Retail"},
        ],
        "EUROPEAN": [
            {"symbol": "EQ_SAP", "name": "SAP", "sector": "Technology"},
            {"symbol": "EQ_ASML", "name": "ASML", "sector": "Technology"},
            {"symbol": "EQ_NVO", "name": "Novo Nordisk", "sector": "Healthcare"},
            {"symbol": "EQ_DB1", "name": "Deutsche Börse", "sector": "Finance"},
        ],
        "ASIAN": [
            {
                "symbol": "EQ_TSM",
                "name": "Taiwan Semiconductor",
                "sector": "Technology",
            },
            {"symbol": "EQ_9618", "name": "JD.com", "sector": "E-Commerce"},
        ],
    }

    return {
        "status": "available",
        "total_stocks": sum(len(v) for v in stocks.values()),
        "stocks_by_region": stocks,
        "features": [
            "Tax-optimized exit recommendations",
            "Multi-jurisdiction support (Germany, US, UK)",
            "FIFO accounting for tax reporting",
            "Integrated with paper trading engine",
        ],
    }


@router.get("/tax-summary")
async def get_stock_tax_summary() -> Dict:
    """Get tax summary for all stock positions.

    Returns:
        Tax liability across all stocks
    """
    try:
        engine = get_paper_trading()
        if not engine:
            raise HTTPException(
                status_code=400, detail="Paper trading engine not initialized"
            )

        positions = engine.get_positions()
        stock_positions = [
            p for p in positions if p.get("symbol", "").startswith("EQ_")
        ]

        if not stock_positions:
            return {
                "total_positions": 0,
                "total_value": 0,
                "unrealized_gain": 0,
                "estimated_tax": 0,
                "positions": [],
            }

        total_gain = 0
        total_tax = 0
        details = []

        for pos in stock_positions:
            cost = pos.get("quantity", 0) * pos.get("entry_price", 0)
            value = pos.get("quantity", 0) * pos.get("current_price", 0)
            gain = value - cost
            days_held = pos.get("days_held", 0)

            # Tax calculation (Germany)
            if days_held >= 365:
                tax = 0
                status = "TAX_FREE"
            else:
                tax = gain * 0.42 * 1.055
                status = "TAXABLE"

            total_gain += gain
            total_tax += tax

            details.append(
                {
                    "symbol": pos.get("symbol"),
                    "quantity": pos.get("quantity"),
                    "entry_price": pos.get("entry_price"),
                    "current_price": pos.get("current_price"),
                    "gain": round(gain, 2),
                    "days_held": days_held,
                    "tax_status": status,
                    "estimated_tax": round(tax, 2),
                }
            )

        return {
            "total_positions": len(stock_positions),
            "total_value": round(
                sum(
                    p.get("quantity", 0) * p.get("current_price", 0)
                    for p in stock_positions
                ),
                2,
            ),
            "unrealized_gain": round(total_gain, 2),
            "estimated_tax": round(total_tax, 2),
            "net_after_tax": round(total_gain - total_tax, 2),
            "positions": details,
        }
    except Exception as e:
        logger.error(f"Error getting tax summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))
