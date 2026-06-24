"""Tax tracking and reporting API endpoints."""

import logging
from datetime import datetime
from typing import List, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.analytics.tax_calculator import (
    init_tax_calculator,
    get_tax_calculator,
    Jurisdiction,
    Trade,
    TaxCalculator,
)
from backend.exchange.paper_trading import get_paper_trading

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/tax", tags=["Tax Tracking"])


# ==================== Pydantic Models ====================

class TradeInput(BaseModel):
    """Input model for adding a trade."""
    symbol: str
    side: str  # BUY or SELL
    quantity: float
    price: float
    timestamp: str  # ISO format
    fees: float = 0.0


class ExpenseInput(BaseModel):
    """Input model for deductible expense."""
    category: str  # trading_fees, software, hardware, etc.
    amount: float
    description: str = ""


class TaxReportResponse(BaseModel):
    """Tax report response."""
    jurisdiction: str
    report_date: str
    summary: Dict
    tax_events: List[Dict]
    deductible_expenses: Dict
    recommendations: List[str]


# ==================== API Endpoints ====================

@router.post("/initialize")
async def initialize_tax_tracking(jurisdiction: str = "DE") -> Dict:
    """Initialize tax tracker for a specific jurisdiction.

    Args:
        jurisdiction: Tax jurisdiction code (DE, US, GB, NL, FR)

    Returns:
        Initialization status
    """
    try:
        # Map jurisdiction codes to enum names
        code_to_enum = {j.value: j for j in Jurisdiction}
        juris_upper = jurisdiction.upper()

        # Try to find by value (e.g., "DE" -> GERMANY)
        if juris_upper in code_to_enum:
            juris = code_to_enum[juris_upper]
        else:
            # Try to find by name (e.g., "GERMANY")
            juris = Jurisdiction[juris_upper]

        calc = init_tax_calculator(juris)
        return {
            "status": "initialized",
            "jurisdiction": juris.value,
            "message": f"Tax tracker initialized for {juris.value}",
        }
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Unknown jurisdiction: {jurisdiction}")
    except Exception as e:
        logger.error(f"Error initializing tax tracker: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/add-trade")
async def add_trade(trade: TradeInput) -> Dict:
    """Add a single trade to tax tracking.

    Args:
        trade: Trade details

    Returns:
        Confirmation with trade ID
    """
    try:
        calc = get_tax_calculator()
        if not calc:
            raise HTTPException(status_code=400, detail="Tax tracker not initialized. Call /tax/initialize first.")

        trade_obj = Trade(
            trade_id=f"{trade.symbol}-{datetime.fromisoformat(trade.timestamp).timestamp()}",
            symbol=trade.symbol,
            side=trade.side.upper(),
            quantity=trade.quantity,
            price=trade.price,
            timestamp=datetime.fromisoformat(trade.timestamp),
            fees=trade.fees,
        )

        calc.add_trade(trade_obj)

        return {
            "status": "added",
            "trade_id": trade_obj.trade_id,
            "symbol": trade.symbol,
            "side": trade.side,
            "quantity": trade.quantity,
            "price": trade.price,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error adding trade: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/add-expense")
async def add_deductible_expense(expense: ExpenseInput) -> Dict:
    """Add a deductible expense.

    Args:
        expense: Expense details

    Returns:
        Confirmation
    """
    try:
        calc = get_tax_calculator()
        if not calc:
            raise HTTPException(status_code=400, detail="Tax tracker not initialized.")

        calc.add_deductible_expense(expense.category, expense.amount)

        return {
            "status": "added",
            "category": expense.category,
            "amount": expense.amount,
            "description": expense.description,
        }
    except Exception as e:
        logger.error(f"Error adding expense: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sync-from-paper-trading")
async def sync_from_paper_trading() -> Dict:
    """Sync trades from paper trading engine to tax tracker.

    Returns:
        Number of trades synced
    """
    try:
        calc = get_tax_calculator()
        if not calc:
            raise HTTPException(status_code=400, detail="Tax tracker not initialized.")

        engine = get_paper_trading()
        if not engine:
            raise HTTPException(status_code=400, detail="Paper trading engine not initialized.")

        # Get all trades from paper trading
        trades_data = engine.get_trades()
        if not trades_data:
            return {"status": "synced", "trades_synced": 0}

        # Convert to tax tracker format
        for trade_dict in trades_data:
            trade = Trade(
                trade_id=trade_dict.get("order_id", "unknown"),
                symbol=trade_dict["symbol"],
                side=trade_dict["side"],
                quantity=float(trade_dict["quantity"]),
                price=float(trade_dict["price"]),
                timestamp=datetime.fromisoformat(trade_dict["timestamp"]),
                fees=float(trade_dict.get("fee", 0)),
            )
            calc.add_trade(trade)

        # Add trading fees as deductible expense
        total_fees = sum(float(t.get("fee", 0)) for t in trades_data)
        if total_fees > 0:
            calc.add_deductible_expense("binance_trading_fees", total_fees)

        return {
            "status": "synced",
            "trades_synced": len(trades_data),
            "total_fees_deductible": round(total_fees, 2),
        }
    except Exception as e:
        logger.error(f"Error syncing trades: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/liability")
async def get_tax_liability() -> Dict:
    """Calculate and return tax liability.

    Returns:
        Detailed tax liability breakdown
    """
    try:
        calc = get_tax_calculator()
        if not calc:
            raise HTTPException(status_code=400, detail="Tax tracker not initialized.")

        liability = calc.calculate_liability()

        return {
            "jurisdiction": liability.jurisdiction.value,
            "total_realized_gains": round(liability.total_realized_gains, 2),
            "total_realized_losses": round(liability.total_realized_losses, 2),
            "net_gain_loss": round(liability.net_gain_loss, 2),
            "long_term_gains": round(liability.long_term_gains, 2),
            "short_term_gains": round(liability.short_term_gains, 2),
            "deductible_expenses": round(liability.deductible_expenses, 2),
            "taxable_income": round(liability.taxable_income, 2),
            "estimated_tax": round(liability.estimated_tax, 2),
            "effective_tax_rate_pct": round((liability.estimated_tax / max(liability.taxable_income, 1)) * 100, 2),
            "tax_rate": round(liability.tax_rate * 100, 1),
        }
    except Exception as e:
        logger.error(f"Error calculating liability: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/report")
async def get_tax_report() -> TaxReportResponse:
    """Generate comprehensive tax report.

    Returns:
        Complete tax report with all details
    """
    try:
        calc = get_tax_calculator()
        if not calc:
            raise HTTPException(status_code=400, detail="Tax tracker not initialized.")

        report = calc.generate_report()
        return TaxReportResponse(**report)
    except Exception as e:
        logger.error(f"Error generating report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/export/{format}")
async def export_tax_data(format: str = "json") -> Dict:
    """Export tax data for tax advisor.

    Args:
        format: "json" or "csv"

    Returns:
        Exported data
    """
    try:
        if format not in ["json", "csv"]:
            raise HTTPException(status_code=400, detail="Format must be 'json' or 'csv'")

        calc = get_tax_calculator()
        if not calc:
            raise HTTPException(status_code=400, detail="Tax tracker not initialized.")

        data = calc.export_for_tax_advisor(format)

        return {
            "status": "exported",
            "format": format,
            "data": data,
        }
    except Exception as e:
        logger.error(f"Error exporting data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary")
async def get_tax_summary() -> Dict:
    """Get quick tax summary (simple dashboard view).

    Returns:
        Key tax metrics
    """
    try:
        calc = get_tax_calculator()
        if not calc:
            raise HTTPException(status_code=400, detail="Tax tracker not initialized.")

        if not calc.tax_events:
            calc.match_trades_fifo()

        liability = calc.calculate_liability()
        jurisdiction = calc.jurisdiction.value

        # Jurisdiction-specific tips
        tips = {
            "DE": "🇩🇪 Hold positions >1 year to avoid 42% tax. Currently holding period matters!",
            "US": "🇺🇸 Long-term capital gains taxed at 15-20%, short-term at ordinary income rates.",
            "GB": "🇬🇧 First £3,000 of gains are tax-free each year.",
            "NL": "🇳🇱 Wealth tax applies to holdings >€50,000 on Jan 1.",
            "FR": "🇫🇷 Check local rules; gains taxed at 19% + 17.2% social tax.",
        }

        return {
            "jurisdiction": jurisdiction,
            "net_position": round(liability.net_gain_loss, 2),
            "estimated_tax": round(liability.estimated_tax, 2),
            "net_after_tax": round(liability.net_gain_loss - liability.estimated_tax, 2),
            "effective_tax_rate_pct": round((liability.estimated_tax / max(liability.net_gain_loss, 1)) * 100, 2),
            "trades_analyzed": len(calc.tax_events),
            "long_term_gains": round(liability.long_term_gains, 2),
            "short_term_gains": round(liability.short_term_gains, 2),
            "jurisdiction_tip": tips.get(jurisdiction, ""),
        }
    except Exception as e:
        logger.error(f"Error getting summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))
