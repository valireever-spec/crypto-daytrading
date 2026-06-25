"""Stock trading analysis with tax-optimized exit strategies."""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class ExitStrategy(Enum):
    """Exit strategy recommendations."""

    HOLD_LONG_TERM = "hold_long_term"  # Wait for 365 days (0% tax)
    SELL_NOW = "sell_now"  # Sell immediately (high profit worth the tax)
    WAIT_BREAKEVEN = "wait_breakeven"  # Hold until breakeven or 365 days
    TRAILING_STOP = "trailing_stop"  # Use technical stop loss


@dataclass
class StockPosition:
    """Open stock position."""

    symbol: str
    quantity: float
    entry_price: float
    entry_date: datetime
    current_price: float
    current_date: datetime = None

    def __post_init__(self):
        if self.current_date is None:
            self.current_date = datetime.utcnow()

    @property
    def cost_basis(self) -> float:
        """Total cost of position."""
        return self.quantity * self.entry_price

    @property
    def current_value(self) -> float:
        """Current market value."""
        return self.quantity * self.current_price

    @property
    def unrealized_gain(self) -> float:
        """Unrealized P&L in EUR."""
        return self.current_value - self.cost_basis

    @property
    def unrealized_gain_pct(self) -> float:
        """Unrealized P&L as percentage."""
        if self.cost_basis == 0:
            return 0
        return (self.unrealized_gain / self.cost_basis) * 100

    @property
    def days_held(self) -> int:
        """Days position has been held."""
        return (self.current_date - self.entry_date).days

    @property
    def long_term_status(self) -> str:
        """Tax status in Germany."""
        if self.days_held >= 365:
            return "LONG_TERM"  # 0% tax
        else:
            return "SHORT_TERM"  # 42% + 5.5% tax


@dataclass
class ExitAnalysis:
    """Analysis of exit options."""

    symbol: str
    current_gain: float
    days_held: int

    # Sell now option
    sell_now_profit: float  # After 42% tax
    sell_now_tax: float

    # Hold to 365 days option
    hold_tax_free_profit: float
    days_to_long_term: int

    # Financial comparison
    additional_profit_if_hold: float  # Extra EUR by waiting
    additional_profit_pct: float  # Extra % by waiting

    # Recommendation
    recommendation: ExitStrategy
    reason: str

    # Risk metrics
    volatility_pct: float  # Daily volatility
    estimated_daily_loss_risk: float  # EUR at risk per day
    time_value: float  # EUR per day by holding


class StockExitOptimizer:
    """Optimize exit timing for tax efficiency."""

    def __init__(self, jurisdiction: str = "DE"):
        """Initialize optimizer.

        Args:
            jurisdiction: Tax jurisdiction (DE, US, GB, etc.)
        """
        self.jurisdiction = jurisdiction

        # Tax rates by jurisdiction
        self.tax_config = {
            "DE": {
                "short_term_rate": 0.42,  # 42% + 5.5% solidarity
                "solidarity_tax": 0.055,
                "long_term_rate": 0.0,  # 0% if held >365 days
                "holding_threshold": 365,
            },
            "US": {
                "short_term_rate": 0.37,
                "long_term_rate": 0.20,
                "holding_threshold": 365,
            },
            "GB": {
                "short_term_rate": 0.20,
                "long_term_rate": 0.20,
                "holding_threshold": 0,
                "annual_exemption": 3000,
            },
        }

    def analyze_exit(
        self,
        position: StockPosition,
        volatility_pct: float = 0.0,
    ) -> ExitAnalysis:
        """Analyze whether to sell now or hold for tax benefits.

        Args:
            position: Open position to analyze
            volatility_pct: Historical daily volatility (for risk)

        Returns:
            ExitAnalysis with recommendation
        """
        config = self.tax_config.get(self.jurisdiction, self.tax_config["DE"])

        # Calculate sell-now scenario
        unrealized_gain = position.unrealized_gain
        short_term_tax_rate = config["short_term_rate"] * (
            1 + config.get("solidarity_tax", 0)
        )
        sell_now_tax = unrealized_gain * short_term_tax_rate
        sell_now_profit = unrealized_gain - sell_now_tax

        # Calculate hold-to-long-term scenario
        hold_tax_free_profit = unrealized_gain * (1 - config["long_term_rate"])
        days_to_long_term = max(0, config["holding_threshold"] - position.days_held)

        # Financial comparison
        additional_profit_if_hold = hold_tax_free_profit - sell_now_profit
        additional_profit_pct = (
            additional_profit_if_hold / max(sell_now_profit, 1)
        ) * 100

        # Risk metrics
        daily_loss_risk = position.current_value * (volatility_pct / 100)
        time_value = additional_profit_if_hold / max(
            days_to_long_term, 1
        )  # EUR per day

        # Determine recommendation
        recommendation, reason = self._determine_recommendation(
            unrealized_gain,
            unrealized_gain_pct=position.unrealized_gain_pct,
            days_held=position.days_held,
            additional_profit_if_hold=additional_profit_if_hold,
            additional_profit_pct=additional_profit_pct,
            daily_loss_risk=daily_loss_risk,
            time_value=time_value,
            config=config,
        )

        return ExitAnalysis(
            symbol=position.symbol,
            current_gain=unrealized_gain,
            days_held=position.days_held,
            sell_now_profit=sell_now_profit,
            sell_now_tax=sell_now_tax,
            hold_tax_free_profit=hold_tax_free_profit,
            days_to_long_term=days_to_long_term,
            additional_profit_if_hold=additional_profit_if_hold,
            additional_profit_pct=additional_profit_pct,
            recommendation=recommendation,
            reason=reason,
            volatility_pct=volatility_pct,
            estimated_daily_loss_risk=daily_loss_risk,
            time_value=time_value,
        )

    def _determine_recommendation(
        self,
        gain: float,
        unrealized_gain_pct: float,
        days_held: int,
        additional_profit_if_hold: float,
        additional_profit_pct: float,
        daily_loss_risk: float,
        time_value: float,
        config: Dict,
    ) -> Tuple[ExitStrategy, str]:
        """Determine exit recommendation based on multiple factors."""

        # Already long-term? Always hold!
        if days_held >= config["holding_threshold"]:
            return (
                ExitStrategy.HOLD_LONG_TERM,
                "✅ Already long-term (0% tax) - hold for tax-free gains",
            )

        # Loss position? Hold unless too risky
        if gain <= 0:
            return (
                ExitStrategy.HOLD_LONG_TERM,
                "📉 Position in loss - hold to long-term or breakeven",
            )

        # Small gain? Almost always better to wait
        if unrealized_gain_pct < 10:
            days_remaining = config["holding_threshold"] - days_held
            return (
                ExitStrategy.HOLD_LONG_TERM,
                f"📊 Small gain ({unrealized_gain_pct:.1f}%) - wait {days_remaining} days for 0% tax"
                f" (+€{additional_profit_if_hold:.2f} extra)",
            )

        # Moderate gain? Definitely wait
        if unrealized_gain_pct < 30:
            return (
                ExitStrategy.HOLD_LONG_TERM,
                f"💰 Moderate gain ({unrealized_gain_pct:.1f}%) - holding saves €{additional_profit_if_hold:.2f}"
                f" in taxes ({additional_profit_pct:.0f}% more profit)",
            )

        # Large gain (>30%)? Still better to hold in Germany
        if unrealized_gain_pct >= 30:
            days_remaining = config["holding_threshold"] - days_held
            daily_tax_savings = additional_profit_if_hold / max(days_remaining, 1)
            return (
                ExitStrategy.HOLD_LONG_TERM,
                f"🚀 Large gain ({unrealized_gain_pct:.1f}%) - even so, holding {days_remaining} days"
                f" saves €{daily_tax_savings:.2f}/day (total: €{additional_profit_if_hold:.2f})",
            )

    def calculate_breakeven_hold_period(
        self,
        position: StockPosition,
        target_profit_pct: float = 10.0,
    ) -> Dict:
        """Calculate how long to hold to reach target profit while minimizing tax.

        Args:
            position: Open position
            target_profit_pct: Target profit percentage (default 10%)

        Returns:
            Dict with timing analysis
        """
        config = self.tax_config.get(self.jurisdiction, self.tax_config["DE"])

        target_value = position.cost_basis * (1 + target_profit_pct / 100)
        target_price = target_value / position.quantity

        days_to_long_term = max(0, config["holding_threshold"] - position.days_held)

        return {
            "symbol": position.symbol,
            "target_profit_pct": target_profit_pct,
            "target_price": round(target_price, 2),
            "current_price": round(position.current_price, 2),
            "price_to_go": round(target_price - position.current_price, 2),
            "days_held": position.days_held,
            "days_to_long_term": days_to_long_term,
            "recommendation": (
                "Hold until price reaches €{:.2f} or {} days (whichever comes first) "
                "for optimal tax efficiency".format(target_price, days_to_long_term)
            ),
        }


# Global instance
_stock_optimizer: Optional[StockExitOptimizer] = None


def init_stock_optimizer(jurisdiction: str = "DE") -> StockExitOptimizer:
    """Initialize global stock exit optimizer."""
    global _stock_optimizer
    _stock_optimizer = StockExitOptimizer(jurisdiction)
    logger.info(f"Stock exit optimizer initialized ({jurisdiction})")
    return _stock_optimizer


def get_stock_optimizer() -> Optional[StockExitOptimizer]:
    """Get global stock exit optimizer."""
    return _stock_optimizer
