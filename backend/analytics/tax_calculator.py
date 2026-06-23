"""Tax tracking and liability calculation for crypto trading."""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from enum import Enum

import pandas as pd

logger = logging.getLogger(__name__)


class Jurisdiction(Enum):
    """Supported tax jurisdictions."""
    GERMANY = "DE"
    USA = "US"
    UK = "GB"
    NETHERLANDS = "NL"
    FRANCE = "FR"


class TaxStatus(Enum):
    """Tax classification for gains."""
    LONG_TERM = "long_term"  # Held >1 year
    SHORT_TERM = "short_term"  # Held ≤1 year
    UNKNOWN = "unknown"


@dataclass
class Trade:
    """Single trade record for tax purposes."""
    trade_id: str
    symbol: str
    side: str  # BUY or SELL
    quantity: float
    price: float
    timestamp: datetime
    fees: float = 0.0


@dataclass
class TaxableEvent:
    """A complete buy-sell pair (taxable event)."""
    buy_trade: Trade
    sell_trade: Trade
    quantity: float
    cost_basis: float  # Total cost including fees
    proceeds: float  # Total sale price minus fees
    gain_loss: float  # Gross P&L before tax
    holding_period_days: int
    tax_status: TaxStatus
    realized_gain: float  # After-tax P&L (calculated later)


@dataclass
class TaxLiability:
    """Calculated tax liability."""
    jurisdiction: Jurisdiction
    total_realized_gains: float
    total_realized_losses: float
    net_gain_loss: float
    tax_rate: float
    deductible_expenses: float
    taxable_income: float
    estimated_tax: float
    long_term_gains: float
    short_term_gains: float


class TaxCalculator:
    """Calculate tax liability across jurisdictions."""

    def __init__(self, jurisdiction: Jurisdiction = Jurisdiction.GERMANY):
        """Initialize tax calculator.

        Args:
            jurisdiction: Country for tax rules (default: Germany)
        """
        self.jurisdiction = jurisdiction
        self.trades: List[Trade] = []
        self.tax_events: List[TaxableEvent] = []
        self.deductible_expenses: Dict[str, float] = {}

        # Tax rates by jurisdiction
        self.tax_rates = {
            Jurisdiction.GERMANY: {
                "short_term": 0.42,  # 42% ordinary income
                "long_term": 0.0,   # 0% if held >1 year
                "holding_period_days": 365,
                "solidarity_tax": 0.055,  # Additional 5.5%
            },
            Jurisdiction.USA: {
                "short_term": 0.37,  # Top bracket (varies by income)
                "long_term": 0.20,   # Top bracket (0%, 15%, or 20%)
                "holding_period_days": 365,
                "wash_sale_days": 30,  # Can't claim losses if repurchase within 30 days
            },
            Jurisdiction.UK: {
                "short_term": 0.20,
                "long_term": 0.20,
                "holding_period_days": 0,  # No distinction
                "annual_exemption": 3000,  # First £3k tax-free
            },
            Jurisdiction.NETHERLANDS: {
                "wealth_tax": 0.32,  # Tax on holdings, not gains
                "holding_period_days": 0,
                "wealth_threshold": 50000,
            },
            Jurisdiction.FRANCE: {
                "short_term": 0.45,
                "long_term": 0.19,
                "holding_period_days": 365,
                "social_tax": 0.173,  # Additional social security tax
            },
        }

    def add_trade(self, trade: Trade) -> None:
        """Add a trade to the tracking list."""
        self.trades.append(trade)
        logger.info(f"Added {trade.side} {trade.quantity} {trade.symbol} @ {trade.price}")

    def add_trades_from_csv(self, trades_list: List[Dict]) -> None:
        """Import trades from Binance CSV export.

        Args:
            trades_list: List of dicts with keys: date, symbol, side, quantity, price, fee
        """
        for t in trades_list:
            trade = Trade(
                trade_id=t.get("order_id", f"{t['date']}-{t['symbol']}"),
                symbol=t["symbol"],
                side=t["side"],
                quantity=float(t["quantity"]),
                price=float(t["price"]),
                timestamp=datetime.fromisoformat(t["date"]),
                fees=float(t.get("fee", 0))
            )
            self.add_trade(trade)

    def add_deductible_expense(self, category: str, amount: float) -> None:
        """Add a deductible expense (fees, tools, etc.).

        Args:
            category: Type of expense (trading_fees, software, etc.)
            amount: Amount in EUR/USD
        """
        if category not in self.deductible_expenses:
            self.deductible_expenses[category] = 0
        self.deductible_expenses[category] += amount
        logger.info(f"Added {category} expense: €{amount:.2f}")

    def match_trades_fifo(self) -> List[TaxableEvent]:
        """Match buy/sell trades using FIFO (First In, First Out) method.

        Returns:
            List of taxable events (buy-sell pairs)
        """
        self.tax_events = []

        # Separate buys and sells
        buys = [t for t in self.trades if t.side == "BUY"]
        sells = [t for t in self.trades if t.side == "SELL"]

        # Track remaining quantities (don't modify original trades)
        remaining_quantities = {i: buy.quantity for i, buy in enumerate(buys)}
        buy_index = 0

        for sell in sells:
            remaining_qty = sell.quantity

            while remaining_qty > 0 and buy_index < len(buys):
                buy = buys[buy_index]
                remaining_buy_qty = remaining_quantities[buy_index]

                # Match as much as possible
                matched_qty = min(remaining_qty, remaining_buy_qty)

                # Create taxable event
                cost_basis = matched_qty * buy.price + (matched_qty / buy.quantity) * buy.fees
                proceeds = matched_qty * sell.price - (matched_qty / sell.quantity) * sell.fees
                gain_loss = proceeds - cost_basis

                holding_days = (sell.timestamp - buy.timestamp).days
                tax_status = self._classify_holding_period(holding_days)

                event = TaxableEvent(
                    buy_trade=buy,
                    sell_trade=sell,
                    quantity=matched_qty,
                    cost_basis=cost_basis,
                    proceeds=proceeds,
                    gain_loss=gain_loss,
                    holding_period_days=holding_days,
                    tax_status=tax_status,
                    realized_gain=0.0  # Calculated later
                )

                self.tax_events.append(event)
                logger.debug(f"Matched {matched_qty} {sell.symbol}: "
                           f"P&L={gain_loss:.2f}, holding={holding_days}d, status={tax_status.value}")

                # Update quantities
                remaining_qty -= matched_qty
                remaining_quantities[buy_index] -= matched_qty

                if remaining_quantities[buy_index] <= 0.0001:  # Floating point tolerance
                    buy_index += 1

        return self.tax_events

    def _classify_holding_period(self, days: int) -> TaxStatus:
        """Classify holding period based on jurisdiction rules."""
        threshold = self.tax_rates[self.jurisdiction].get("holding_period_days", 365)
        if days >= threshold:
            return TaxStatus.LONG_TERM
        return TaxStatus.SHORT_TERM

    def calculate_liability(self) -> TaxLiability:
        """Calculate tax liability for all trades.

        Returns:
            TaxLiability with detailed breakdown
        """
        if not self.tax_events:
            self.match_trades_fifo()

        # Separate by holding status
        long_term_events = [e for e in self.tax_events if e.tax_status == TaxStatus.LONG_TERM]
        short_term_events = [e for e in self.tax_events if e.tax_status == TaxStatus.SHORT_TERM]

        long_term_gains = sum(e.gain_loss for e in long_term_events)
        short_term_gains = sum(e.gain_loss for e in short_term_events)
        long_term_losses = sum(e.gain_loss for e in long_term_events if e.gain_loss < 0)
        short_term_losses = sum(e.gain_loss for e in short_term_events if e.gain_loss < 0)

        total_realized_gains = long_term_gains + short_term_gains
        total_realized_losses = long_term_losses + short_term_losses
        net_gain_loss = total_realized_gains + total_realized_losses

        total_deductible = sum(self.deductible_expenses.values())

        # Apply jurisdiction-specific rules
        if self.jurisdiction == Jurisdiction.GERMANY:
            # Germany: long-term is tax-free, short-term is ordinary income
            taxable_short_term = max(0, short_term_gains + short_term_losses - total_deductible)
            estimated_tax = taxable_short_term * self.tax_rates[self.jurisdiction]["short_term"]
            estimated_tax *= (1 + self.tax_rates[self.jurisdiction]["solidarity_tax"])
            tax_rate = self.tax_rates[self.jurisdiction]["short_term"]

        elif self.jurisdiction == Jurisdiction.USA:
            # USA: separate rates for short-term and long-term
            taxable_short_term = max(0, short_term_gains + short_term_losses - total_deductible)
            taxable_long_term = max(0, long_term_gains + long_term_losses)
            estimated_tax = (taxable_short_term * self.tax_rates[self.jurisdiction]["short_term"] +
                            taxable_long_term * self.tax_rates[self.jurisdiction]["long_term"])
            tax_rate = self.tax_rates[self.jurisdiction]["short_term"]

        elif self.jurisdiction == Jurisdiction.UK:
            # UK: annual exemption of £3,000
            annual_exemption = self.tax_rates[self.jurisdiction].get("annual_exemption", 0)
            taxable = max(0, net_gain_loss - annual_exemption - total_deductible)
            estimated_tax = taxable * self.tax_rates[self.jurisdiction]["short_term"]
            tax_rate = self.tax_rates[self.jurisdiction]["short_term"]

        else:
            # Default calculation
            taxable = max(0, net_gain_loss - total_deductible)
            tax_rate = self.tax_rates[self.jurisdiction]["short_term"]
            estimated_tax = taxable * tax_rate

        liability = TaxLiability(
            jurisdiction=self.jurisdiction,
            total_realized_gains=total_realized_gains,
            total_realized_losses=total_realized_losses,
            net_gain_loss=net_gain_loss,
            tax_rate=tax_rate,
            deductible_expenses=total_deductible,
            taxable_income=max(0, net_gain_loss - total_deductible),
            estimated_tax=estimated_tax,
            long_term_gains=long_term_gains,
            short_term_gains=short_term_gains,
        )

        logger.info(f"Tax liability ({self.jurisdiction.value}): €{estimated_tax:.2f}")
        logger.info(f"  Long-term gains: €{long_term_gains:.2f} (0% tax)")
        logger.info(f"  Short-term gains: €{short_term_gains:.2f} ({tax_rate*100:.0f}% tax)")
        logger.info(f"  Deductible expenses: €{total_deductible:.2f}")

        return liability

    def generate_report(self) -> Dict:
        """Generate comprehensive tax report.

        Returns:
            Dict with all tax information
        """
        if not self.tax_events:
            self.match_trades_fifo()

        liability = self.calculate_liability()

        return {
            "jurisdiction": self.jurisdiction.value,
            "report_date": datetime.utcnow().isoformat(),
            "summary": {
                "total_trades": len(self.trades),
                "taxable_events": len(self.tax_events),
                "total_realized_gains": round(liability.total_realized_gains, 2),
                "total_realized_losses": round(liability.total_realized_losses, 2),
                "net_gain_loss": round(liability.net_gain_loss, 2),
                "long_term_gains": round(liability.long_term_gains, 2),
                "short_term_gains": round(liability.short_term_gains, 2),
                "deductible_expenses": round(liability.deductible_expenses, 2),
                "taxable_income": round(liability.taxable_income, 2),
                "estimated_tax_liability": round(liability.estimated_tax, 2),
                "effective_tax_rate": round((liability.estimated_tax / max(liability.taxable_income, 1)) * 100, 2),
            },
            "tax_events": [
                {
                    "buy_date": e.buy_trade.timestamp.isoformat(),
                    "sell_date": e.sell_trade.timestamp.isoformat(),
                    "symbol": e.sell_trade.symbol,
                    "quantity": round(e.quantity, 8),
                    "cost_basis": round(e.cost_basis, 2),
                    "proceeds": round(e.proceeds, 2),
                    "gain_loss": round(e.gain_loss, 2),
                    "holding_period_days": e.holding_period_days,
                    "tax_status": e.tax_status.value,
                    "estimated_tax": round(e.gain_loss * liability.tax_rate, 2) if e.tax_status == TaxStatus.SHORT_TERM else 0,
                }
                for e in sorted(self.tax_events, key=lambda x: x.sell_trade.timestamp)
            ],
            "deductible_expenses": self.deductible_expenses,
            "recommendations": self._get_recommendations(liability),
        }

    def _get_recommendations(self, liability: TaxLiability) -> List[str]:
        """Get tax optimization recommendations."""
        recommendations = []

        if self.jurisdiction == Jurisdiction.GERMANY:
            # Check if user could benefit from long-term holding
            short_term_tax = liability.short_term_gains * 0.42
            if short_term_tax > 1000:
                recommendations.append(
                    f"GERMANY: Consider holding positions >1 year to avoid {short_term_tax:.0f}€ in taxes"
                )

        if liability.net_gain_loss > 0 and liability.deductible_expenses < 100:
            recommendations.append(
                "Tracking more deductible expenses (software, hardware, fees) could reduce tax liability"
            )

        if len([e for e in self.tax_events if e.holding_period_days < 30]) > 5:
            recommendations.append(
                "High frequency trading detected - consider holding period strategy to optimize taxes"
            )

        if not recommendations:
            recommendations.append("Tax situation appears optimized for your jurisdiction")

        return recommendations

    def export_for_tax_advisor(self, format: str = "json") -> str:
        """Export data for tax advisor review.

        Args:
            format: "json" or "csv"

        Returns:
            Formatted string for export
        """
        report = self.generate_report()

        if format == "json":
            import json
            return json.dumps(report, indent=2, default=str)

        elif format == "csv":
            import csv
            from io import StringIO

            output = StringIO()
            writer = csv.DictWriter(
                output,
                fieldnames=["buy_date", "sell_date", "symbol", "quantity", "cost_basis",
                           "proceeds", "gain_loss", "holding_period_days", "tax_status"]
            )
            writer.writeheader()
            for event in report["tax_events"]:
                writer.writerow(event)

            return output.getvalue()

        return str(report)


# Global instance
_tax_calculator: Optional[TaxCalculator] = None


def init_tax_calculator(jurisdiction: Jurisdiction = Jurisdiction.GERMANY) -> TaxCalculator:
    """Initialize global tax calculator."""
    global _tax_calculator
    _tax_calculator = TaxCalculator(jurisdiction)
    logger.info(f"Tax calculator initialized ({jurisdiction.value})")
    return _tax_calculator


def get_tax_calculator() -> Optional[TaxCalculator]:
    """Get global tax calculator."""
    return _tax_calculator
