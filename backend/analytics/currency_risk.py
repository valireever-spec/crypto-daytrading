"""Currency risk management for multi-asset portfolios."""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class CurrencyExposure:
    """Currency exposure in portfolio."""
    currency: str
    exposure_amount: float
    exposure_pct: float
    hedged_amount: float = 0.0
    hedge_ratio: float = 0.0  # 0 = no hedge, 1 = fully hedged


class CurrencyRiskCalculator:
    """Calculate and manage currency risk."""

    def __init__(self):
        self.fx_rates: Dict[str, float] = {
            "USD": 1.0,
            "EUR": 1.08,
            "GBP": 1.25,
            "JPY": 0.0067,
            "CHF": 1.10,
            "CAD": 0.74,
            "AUD": 0.67,
            "SGD": 0.75,
            "HKD": 0.128,
            "CNY": 0.138,
        }

        self.volatility: Dict[str, float] = {
            "EUR": 0.10,
            "GBP": 0.12,
            "JPY": 0.08,
            "CHF": 0.09,
            "CAD": 0.07,
            "AUD": 0.13,
            "SGD": 0.06,
            "HKD": 0.05,
            "CNY": 0.08,
        }

    def update_fx_rate(self, currency: str, rate: float):
        """Update FX rate."""
        self.fx_rates[currency] = rate

    def convert_to_usd(self, amount: float, from_currency: str) -> float:
        """Convert amount from any currency to USD."""
        if from_currency == "USD":
            return amount

        rate = self.fx_rates.get(from_currency)
        if rate is None:
            logger.warning(f"FX rate not available for {from_currency}")
            return amount

        return amount * rate

    def convert_from_usd(self, amount: float, to_currency: str) -> float:
        """Convert amount from USD to another currency."""
        if to_currency == "USD":
            return amount

        rate = self.fx_rates.get(to_currency)
        if rate is None:
            logger.warning(f"FX rate not available for {to_currency}")
            return amount

        return amount / rate

    def calculate_currency_exposure(
        self,
        positions: Dict[str, Dict]
    ) -> Dict[str, CurrencyExposure]:
        """
        Calculate exposure by currency.

        Args:
            positions: Dict of {symbol: {currency, value, ...}}

        Returns:
            Dict of {currency: CurrencyExposure}
        """
        total_value_usd = 0.0
        currency_values = {}

        # Calculate exposure in each currency
        for symbol, pos in positions.items():
            currency = pos.get("currency", "USD")
            value = pos.get("value", 0.0)

            if currency not in currency_values:
                currency_values[currency] = 0.0

            currency_values[currency] += value
            total_value_usd += self.convert_to_usd(value, currency)

        # Create exposures
        exposures = {}
        for currency, value in currency_values.items():
            usd_value = self.convert_to_usd(value, currency)
            exposure_pct = (usd_value / total_value_usd * 100) if total_value_usd > 0 else 0

            exposures[currency] = CurrencyExposure(
                currency=currency,
                exposure_amount=usd_value,
                exposure_pct=exposure_pct
            )

        return exposures

    def calculate_currency_var(
        self,
        exposure_amount: float,
        currency: str,
        confidence: float = 0.95,
        days: int = 1
    ) -> float:
        """
        Calculate Value at Risk due to currency movement.

        Args:
            exposure_amount: Exposure amount in USD
            currency: Currency code
            confidence: Confidence level
            days: Number of days

        Returns:
            VaR in USD
        """
        if currency == "USD":
            return 0.0

        vol = self.volatility.get(currency, 0.10)
        vol_days = vol * np.sqrt(days)

        # Assume normal distribution for FX
        z_score = 1.645 if confidence == 0.95 else 2.326  # 95% or 99%

        var_usd = exposure_amount * vol_days * z_score
        return var_usd

    def calculate_total_currency_var(
        self,
        exposures: Dict[str, CurrencyExposure],
        confidence: float = 0.95
    ) -> float:
        """Calculate total portfolio currency VaR."""
        total_var = 0.0

        for currency, exposure in exposures.items():
            if currency != "USD":
                var = self.calculate_currency_var(
                    exposure.exposure_amount,
                    currency,
                    confidence
                )
                total_var += var

        return total_var

    def suggest_hedges(
        self,
        exposures: Dict[str, CurrencyExposure],
        max_total_fx_risk_pct: float = 2.0
    ) -> List[Dict]:
        """
        Suggest currency hedges based on exposures.

        Args:
            exposures: Currency exposures
            max_total_fx_risk_pct: Max acceptable FX risk as % of portfolio

        Returns:
            List of hedge suggestions
        """
        suggestions = []

        for currency, exposure in exposures.items():
            if currency == "USD":
                continue

            var = self.calculate_currency_var(exposure.exposure_amount, currency)
            total_portfolio_value = sum(e.exposure_amount for e in exposures.values())
            var_pct = (var / total_portfolio_value * 100) if total_portfolio_value > 0 else 0

            # Suggest hedge if risk > 1% of portfolio
            if var_pct > 1.0:
                suggestions.append({
                    "currency": currency,
                    "exposure_usd": exposure.exposure_amount,
                    "exposure_pct": exposure.exposure_pct,
                    "currency_var_usd": var,
                    "currency_var_pct": var_pct,
                    "recommendation": self._get_hedge_recommendation(var_pct),
                    "hedge_ratio": min(var_pct / max_total_fx_risk_pct, 1.0) if var_pct > max_total_fx_risk_pct else 0.5
                })

        return sorted(suggestions, key=lambda x: x["currency_var_pct"], reverse=True)

    def _get_hedge_recommendation(self, var_pct: float) -> str:
        """Get hedge recommendation based on risk level."""
        if var_pct > 2.0:
            return "Strongly recommend hedging 75-100%"
        elif var_pct > 1.5:
            return "Recommend hedging 50-75%"
        elif var_pct > 1.0:
            return "Consider hedging 25-50%"
        else:
            return "Monitor, hedging optional"

    def calculate_correlation_matrix(
        self,
        currencies: List[str]
    ) -> Dict[Tuple[str, str], float]:
        """
        Get correlation between currency pairs.

        Default: Major developed currencies moderately correlated.
        """
        # Simplified correlation matrix for common pairs
        correlations = {
            ("EUR", "GBP"): 0.75,
            ("EUR", "JPY"): -0.30,
            ("EUR", "CHF"): 0.85,
            ("GBP", "JPY"): -0.25,
            ("GBP", "CHF"): 0.70,
            ("JPY", "CHF"): -0.20,
            ("USD", "JPY"): -0.10,
            ("USD", "EUR"): -0.80,
            ("USD", "GBP"): -0.70,
            ("USD", "CHF"): 0.50,
        }

        matrix = {}
        for curr1 in currencies:
            for curr2 in currencies:
                if curr1 == curr2:
                    matrix[(curr1, curr2)] = 1.0
                elif curr1 == "USD" or curr2 == "USD":
                    # USD correlation
                    key = (curr2, curr1) if (curr1, curr2) not in correlations else (curr1, curr2)
                    matrix[(curr1, curr2)] = correlations.get(key, 0.0)
                else:
                    # Direct correlation
                    key = (curr1, curr2) if (curr1, curr2) in correlations else (curr2, curr1)
                    matrix[(curr1, curr2)] = correlations.get(key, 0.5)

        return matrix


class CurrencyHedgingStrategy:
    """Strategy for currency hedging."""

    def __init__(self):
        self.calc = CurrencyRiskCalculator()
        self.active_hedges: Dict[str, Dict] = {}

    def create_hedge(
        self,
        currency: str,
        hedge_amount: float,
        hedge_ratio: float = 1.0
    ) -> Dict:
        """
        Create a currency hedge.

        Args:
            currency: Currency to hedge
            hedge_amount: Amount to hedge
            hedge_ratio: Ratio to hedge (0-1)

        Returns:
            Hedge specification
        """
        hedge = {
            "currency": currency,
            "target_amount": hedge_amount,
            "hedge_ratio": hedge_ratio,
            "hedged_amount": hedge_amount * hedge_ratio,
            "type": "forward",  # or "options", "currency_basket"
            "status": "active"
        }

        self.active_hedges[currency] = hedge
        logger.info(f"Created hedge for {currency}: {hedge_ratio*100:.0f}% of {hedge_amount:.2f}")

        return hedge

    def calculate_hedge_cost(
        self,
        hedged_amount: float,
        currency: str,
        days: int = 30
    ) -> float:
        """
        Estimate cost of hedging.

        Cost based on volatility and time:
        Cost = notional * volatility * sqrt(days) * 0.005
        """
        vol = self.calc.volatility.get(currency, 0.10)
        cost = hedged_amount * vol * np.sqrt(days / 252) * 0.005

        return cost

    def evaluate_hedges(self) -> Dict:
        """Evaluate effectiveness of active hedges."""
        evaluation = {
            "active_hedges": len(self.active_hedges),
            "total_hedged": sum(h.get("hedged_amount", 0) for h in self.active_hedges.values()),
            "hedges": []
        }

        for currency, hedge in self.active_hedges.items():
            cost = self.calculate_hedge_cost(hedge["hedged_amount"], currency)
            evaluation["hedges"].append({
                "currency": currency,
                "hedged_amount": hedge["hedged_amount"],
                "hedge_ratio": hedge["hedge_ratio"],
                "estimated_cost": cost,
                "status": hedge["status"]
            })

        return evaluation


# Global calculator instance
_currency_risk_calc: Optional[CurrencyRiskCalculator] = None


def init_currency_risk() -> CurrencyRiskCalculator:
    """Initialize currency risk calculator."""
    global _currency_risk_calc
    if _currency_risk_calc is None:
        _currency_risk_calc = CurrencyRiskCalculator()
        logger.info("Currency risk calculator initialized")
    return _currency_risk_calc


def get_currency_risk() -> Optional[CurrencyRiskCalculator]:
    """Get currency risk calculator."""
    return _currency_risk_calc
