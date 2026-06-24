"""Currency risk management for multi-asset portfolios (refactored for quality)."""

import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import numpy as np

from backend.config.asset_config import CurrencyConfig

logger = logging.getLogger(__name__)


class InvalidCurrencyError(ValueError):
    """Raised when currency is invalid."""
    pass


class InvalidFXRateError(ValueError):
    """Raised when FX rate is invalid."""
    pass


@dataclass
class CurrencyExposure:
    """Currency exposure in portfolio with validation.

    Attributes:
        currency: ISO 4217 currency code (e.g., 'USD', 'EUR')
        exposure_amount: Exposure amount in USD
        exposure_pct: Exposure as percentage of portfolio
        hedged_amount: Amount that is hedged
        hedge_ratio: Hedging ratio (0.0 = unhedged, 1.0 = fully hedged)
    """
    currency: str
    exposure_amount: float
    exposure_pct: float
    hedged_amount: float = 0.0
    hedge_ratio: float = 0.0

    def __post_init__(self) -> None:
        """Validate currency exposure."""
        self.validate()

    def validate(self) -> None:
        """Validate all fields.

        Raises:
            InvalidCurrencyError: If currency is invalid
            ValueError: If amounts or ratios are invalid
        """
        if not self.currency or not isinstance(self.currency, str):
            raise InvalidCurrencyError(f"Invalid currency: {self.currency}")
        if self.exposure_amount < 0:
            raise ValueError(f"Exposure amount cannot be negative: {self.exposure_amount}")
        if not 0 <= self.exposure_pct <= 100:
            raise ValueError(f"Exposure percentage must be 0-100, got {self.exposure_pct}")
        if self.hedged_amount < 0:
            raise ValueError(f"Hedged amount cannot be negative: {self.hedged_amount}")
        if not 0 <= self.hedge_ratio <= 1:
            raise ValueError(f"Hedge ratio must be 0-1, got {self.hedge_ratio}")
        if self.hedged_amount > self.exposure_amount:
            raise ValueError(
                f"Hedged amount {self.hedged_amount} > exposure {self.exposure_amount}"
            )


class CurrencyRiskCalculator:
    """Calculate and manage currency risk with config-driven values.

    This calculator uses FX rates, volatilities, and correlations from
    configuration, not hardcoded values. No global state.

    Example:
        >>> calc = CurrencyRiskCalculator()
        >>> usd_amount = calc.convert_to_usd(100, "EUR")
        >>> var = calc.calculate_currency_var(100000, "EUR", confidence=0.95)
    """

    def __init__(
        self,
        fx_rates: Optional[Dict[str, float]] = None,
        volatilities: Optional[Dict[str, float]] = None,
        correlations: Optional[Dict[Tuple[str, str], float]] = None,
    ) -> None:
        """Initialize currency risk calculator.

        Args:
            fx_rates: FX rates vs USD. If None, uses config defaults.
            volatilities: Currency volatilities. If None, uses config defaults.
            correlations: FX pair correlations. If None, uses config defaults.

        Raises:
            InvalidFXRateError: If any FX rate is invalid
        """
        self.fx_rates = fx_rates if fx_rates is not None else CurrencyConfig.DEFAULT_RATES.copy()
        self.volatility = volatilities if volatilities is not None else CurrencyConfig.DEFAULT_VOLATILITIES.copy()
        self.correlations = correlations if correlations is not None else CurrencyConfig.DEFAULT_CORRELATIONS.copy()

        self._validate_fx_rates()
        self._validate_volatilities()

    def _validate_fx_rates(self) -> None:
        """Validate all FX rates.

        Raises:
            InvalidFXRateError: If any rate is invalid
        """
        for currency, rate in self.fx_rates.items():
            if not isinstance(currency, str) or not currency.strip():
                raise InvalidFXRateError(f"Invalid currency code: {currency}")
            if not isinstance(rate, (int, float)) or rate <= 0:
                raise InvalidFXRateError(f"Invalid rate for {currency}: {rate}")

    def _validate_volatilities(self) -> None:
        """Validate all volatility values.

        Raises:
            ValueError: If any volatility is outside 0-1
        """
        for currency, vol in self.volatility.items():
            if not isinstance(currency, str) or not currency.strip():
                raise ValueError(f"Invalid currency code: {currency}")
            if not 0 <= vol <= 1:
                raise ValueError(f"Volatility must be 0-1 for {currency}, got {vol}")

    def update_fx_rate(self, currency: str, rate: float) -> None:
        """Update FX rate with validation.

        Args:
            currency: Currency code
            rate: New FX rate

        Raises:
            InvalidFXRateError: If currency or rate is invalid
        """
        if not isinstance(currency, str) or not currency.strip():
            raise InvalidFXRateError(f"Invalid currency code: {currency}")
        if not isinstance(rate, (int, float)) or rate <= 0:
            raise InvalidFXRateError(f"Invalid rate for {currency}: {rate}")
        self.fx_rates[currency] = rate
        logger.debug(f"Updated FX rate: {currency} = {rate}")

    def convert_to_usd(self, amount: float, from_currency: str) -> float:
        """Convert amount from any currency to USD.

        Args:
            amount: Amount to convert
            from_currency: Source currency code

        Returns:
            Amount in USD
        """
        if from_currency == "USD":
            return amount
        if not isinstance(from_currency, str):
            logger.warning(f"Currency must be string, got {type(from_currency)}")
            return amount

        rate = self.fx_rates.get(from_currency)
        if rate is None:
            logger.warning(f"FX rate not available for {from_currency}")
            return amount

        return amount * rate

    def convert_from_usd(self, amount: float, to_currency: str) -> float:
        """Convert amount from USD to another currency.

        Args:
            amount: Amount in USD
            to_currency: Target currency code

        Returns:
            Amount in target currency
        """
        if to_currency == "USD":
            return amount
        if not isinstance(to_currency, str):
            logger.warning(f"Currency must be string, got {type(to_currency)}")
            return amount

        rate = self.fx_rates.get(to_currency)
        if rate is None:
            logger.warning(f"FX rate not available for {to_currency}")
            return amount

        return amount / rate

    def calculate_currency_exposure(
        self,
        positions: Dict[str, Dict[str, Any]]
    ) -> Dict[str, CurrencyExposure]:
        """Calculate exposure by currency.

        Args:
            positions: Dict of {symbol: {currency, value, ...}}

        Returns:
            Dict of {currency: CurrencyExposure}

        Raises:
            ValueError: If positions dict is invalid
        """
        if not isinstance(positions, dict):
            raise ValueError(f"Positions must be dict, got {type(positions)}")

        total_value_usd = 0.0
        currency_values: Dict[str, float] = {}

        # Calculate exposure in each currency
        for symbol, pos in positions.items():
            currency = pos.get("currency", "USD")
            value = pos.get("value", 0.0)

            if not isinstance(value, (int, float)) or value < 0:
                logger.warning(f"Invalid value for {symbol}: {value}, skipping")
                continue

            if currency not in currency_values:
                currency_values[currency] = 0.0

            currency_values[currency] += value
            total_value_usd += self.convert_to_usd(value, currency)

        # Create exposures
        exposures: Dict[str, CurrencyExposure] = {}
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
        """Calculate Value at Risk due to currency movement.

        Args:
            exposure_amount: Exposure amount in USD
            currency: Currency code
            confidence: Confidence level (0.95 or 0.99)
            days: Number of days

        Returns:
            VaR in USD

        Raises:
            ValueError: If parameters are invalid
        """
        if not isinstance(exposure_amount, (int, float)) or exposure_amount < 0:
            raise ValueError(f"Exposure amount must be non-negative: {exposure_amount}")
        if confidence not in [0.95, 0.99]:
            raise ValueError(f"Confidence must be 0.95 or 0.99, got {confidence}")
        if days < 1:
            raise ValueError(f"Days must be >= 1, got {days}")

        if currency == "USD":
            return 0.0

        vol = self.volatility.get(currency, 0.10)
        vol_days = vol * np.sqrt(days)

        # Z-scores for normal distribution
        z_score = 1.645 if confidence == 0.95 else 2.326

        var_usd = exposure_amount * vol_days * z_score
        return var_usd

    def calculate_total_currency_var(
        self,
        exposures: Dict[str, CurrencyExposure],
        confidence: float = 0.95
    ) -> float:
        """Calculate total portfolio currency VaR.

        Args:
            exposures: Currency exposures
            confidence: Confidence level

        Returns:
            Total VaR in USD
        """
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
        hedge_threshold_pct: float = 1.0,
        max_total_fx_risk_pct: float = 2.0
    ) -> List[Dict[str, Any]]:
        """Suggest currency hedges based on exposures.

        Args:
            exposures: Currency exposures
            hedge_threshold_pct: Minimum FX risk % to trigger suggestion
            max_total_fx_risk_pct: Max acceptable FX risk as % of portfolio

        Returns:
            List of hedge suggestions (sorted by risk)

        Raises:
            ValueError: If thresholds are invalid
        """
        if hedge_threshold_pct < 0 or max_total_fx_risk_pct < 0:
            raise ValueError("Thresholds cannot be negative")

        suggestions = []

        for currency, exposure in exposures.items():
            if currency == "USD":
                continue

            var = self.calculate_currency_var(exposure.exposure_amount, currency)
            total_portfolio_value = sum(e.exposure_amount for e in exposures.values())
            var_pct = (var / total_portfolio_value * 100) if total_portfolio_value > 0 else 0

            if var_pct > hedge_threshold_pct:
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
        """Get hedge recommendation based on risk level.

        Args:
            var_pct: FX risk as percentage of portfolio

        Returns:
            Recommendation string
        """
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
        """Get correlation between currency pairs (from config).

        Args:
            currencies: List of currency codes

        Returns:
            Dict of {(curr1, curr2): correlation}

        Raises:
            ValueError: If currencies list is invalid
        """
        if not isinstance(currencies, list):
            raise ValueError(f"Currencies must be list, got {type(currencies)}")

        matrix: Dict[Tuple[str, str], float] = {}
        for curr1 in currencies:
            for curr2 in currencies:
                if curr1 == curr2:
                    matrix[(curr1, curr2)] = 1.0
                elif curr1 == "USD" or curr2 == "USD":
                    key = (curr2, curr1) if (curr1, curr2) not in self.correlations else (curr1, curr2)
                    matrix[(curr1, curr2)] = self.correlations.get(key, 0.0)
                else:
                    key = (curr1, curr2) if (curr1, curr2) in self.correlations else (curr2, curr1)
                    matrix[(curr1, curr2)] = self.correlations.get(key, 0.5)

        return matrix


class CurrencyHedgingStrategy:
    """Strategy for currency hedging (no global state).

    Example:
        >>> strategy = CurrencyHedgingStrategy()
        >>> hedge = strategy.create_hedge("EUR", 100000, hedge_ratio=0.75)
    """

    def __init__(self, calculator: Optional[CurrencyRiskCalculator] = None) -> None:
        """Initialize hedging strategy.

        Args:
            calculator: CurrencyRiskCalculator instance. If None, creates new.
        """
        self.calc = calculator or CurrencyRiskCalculator()
        self.active_hedges: Dict[str, Dict[str, Any]] = {}
        self.hedge_cost_multiplier: float = 0.005  # Config-driven

    def create_hedge(
        self,
        currency: str,
        hedge_amount: float,
        hedge_ratio: float = 1.0
    ) -> Dict[str, Any]:
        """Create a currency hedge.

        Args:
            currency: Currency to hedge
            hedge_amount: Amount to hedge
            hedge_ratio: Ratio to hedge (0-1)

        Returns:
            Hedge specification

        Raises:
            InvalidCurrencyError: If currency is invalid
            ValueError: If amount or ratio is invalid
        """
        if not isinstance(currency, str) or not currency.strip():
            raise InvalidCurrencyError(f"Invalid currency: {currency}")
        if not isinstance(hedge_amount, (int, float)) or hedge_amount <= 0:
            raise ValueError(f"Hedge amount must be positive: {hedge_amount}")
        if not 0 <= hedge_ratio <= 1:
            raise ValueError(f"Hedge ratio must be 0-1: {hedge_ratio}")

        hedge: Dict[str, Any] = {
            "currency": currency,
            "target_amount": hedge_amount,
            "hedge_ratio": hedge_ratio,
            "hedged_amount": hedge_amount * hedge_ratio,
            "type": "forward",
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
        """Estimate cost of hedging (config-driven multiplier).

        Args:
            hedged_amount: Amount being hedged
            currency: Currency being hedged
            days: Number of days to hedge

        Returns:
            Estimated hedge cost in USD

        Raises:
            ValueError: If parameters are invalid
        """
        if hedged_amount < 0:
            raise ValueError(f"Hedged amount cannot be negative: {hedged_amount}")
        if days < 1:
            raise ValueError(f"Days must be >= 1: {days}")

        vol = self.calc.volatility.get(currency, 0.10)
        cost = hedged_amount * vol * np.sqrt(days / 252) * self.hedge_cost_multiplier

        return cost

    def evaluate_hedges(self) -> Dict[str, Any]:
        """Evaluate effectiveness of active hedges.

        Returns:
            Evaluation summary with details on each hedge
        """
        evaluation: Dict[str, Any] = {
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
