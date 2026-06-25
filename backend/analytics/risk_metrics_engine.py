"""
Phase 320: Risk Metrics Engine

Calculate comprehensive risk metrics: VaR, expected shortfall, max drawdown,
volatility, and regime-specific risk profiles.
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class RiskMetrics:
    """Comprehensive risk metrics for portfolio."""

    timestamp: datetime
    value_at_risk_95: float  # 95% VaR
    value_at_risk_99: float  # 99% VaR
    expected_shortfall_95: float  # Expected loss beyond 95% VaR
    expected_shortfall_99: float  # Expected loss beyond 99% VaR
    max_drawdown_pct: float
    volatility_pct: float  # Annualized
    sharpe_ratio: float
    sortino_ratio: float
    var_ratio: float  # VaR / Expected Shortfall
    skewness: float
    kurtosis: float


@dataclass
class RegimeRiskProfile:
    """Risk metrics specific to market regime."""

    regime: str  # bull/bear/sideways/volatile
    volatility_pct: float
    var_95_pct: float
    es_95_pct: float
    max_historical_drawdown_pct: float
    avg_daily_loss_pct: float
    worst_day_loss_pct: float
    prob_loss_above_1pct: float  # P(loss > 1% on any day)
    sharpe_ratio: float


class RiskMetricsEngine:
    """Calculate comprehensive portfolio risk metrics."""

    def __init__(self, confidence_level: float = 0.95):
        """
        Initialize risk metrics engine.

        Parameters:
        -----------
        confidence_level : float
            Confidence level for VaR/ES calculation (0.95 = 95%)
        """
        self.confidence_level = confidence_level
        self.risk_cache: Dict[str, RiskMetrics] = {}

    def calculate_risk_metrics(
        self,
        returns: pd.Series,  # Daily returns (%)
        confidence_level: Optional[float] = None,
    ) -> RiskMetrics:
        """
        Calculate comprehensive risk metrics from returns series.

        Parameters:
        -----------
        returns : pd.Series
            Daily returns as percentage
        confidence_level : float
            Override default confidence level

        Returns:
        --------
        RiskMetrics object with all risk measures
        """
        conf = confidence_level or self.confidence_level

        # VaR calculations (historical method)
        var_95 = np.percentile(returns.dropna(), (1 - 0.95) * 100)
        var_99 = np.percentile(returns.dropna(), (1 - 0.99) * 100)

        # Expected Shortfall (CVaR): average loss beyond VaR
        es_95 = (
            returns[returns <= var_95].mean()
            if len(returns[returns <= var_95]) > 0
            else var_95
        )
        es_99 = (
            returns[returns <= var_99].mean()
            if len(returns[returns <= var_99]) > 0
            else var_99
        )

        # Volatility (annualized)
        daily_vol = returns.std()
        annual_vol = daily_vol * np.sqrt(252)

        # Max drawdown
        cumulative = (1 + returns / 100).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        max_dd = drawdown.min() * 100

        # Sharpe ratio (assuming 2% risk-free rate)
        excess_return = returns.mean() - 0.02 / 252
        sharpe = (excess_return / daily_vol) * np.sqrt(252) if daily_vol > 0 else 0

        # Sortino ratio (only downside volatility)
        downside_returns = returns[returns < 0]
        downside_vol = downside_returns.std()
        sortino = (
            (excess_return / downside_vol) * np.sqrt(252) if downside_vol > 0 else 0
        )

        # Distribution metrics (using numpy)
        returns_clean = returns.dropna()
        if len(returns_clean) > 0:
            mean = returns_clean.mean()
            std = returns_clean.std()
            # Skewness
            skew = ((returns_clean - mean) ** 3).mean() / (std**3) if std > 0 else 0
            # Kurtosis (excess)
            kurt = (
                ((returns_clean - mean) ** 4).mean() / (std**4) - 3 if std > 0 else 0
            )
        else:
            skew = 0
            kurt = 0

        metrics = RiskMetrics(
            timestamp=datetime.utcnow(),
            value_at_risk_95=var_95,
            value_at_risk_99=var_99,
            expected_shortfall_95=es_95,
            expected_shortfall_99=es_99,
            max_drawdown_pct=max_dd,
            volatility_pct=annual_vol * 100,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            var_ratio=abs(var_95) / abs(es_95) if es_95 != 0 else 0,
            skewness=skew,
            kurtosis=kurt,
        )

        return metrics

    def get_regime_risk_profile(
        self,
        symbol_returns: Dict[str, pd.Series],  # symbol → daily returns
        symbol_regimes: Dict[
            str, List[Tuple[datetime, str]]
        ],  # symbol → [(date, regime)]
        regime: str = "bull",
    ) -> RegimeRiskProfile:
        """
        Calculate risk profile specific to market regime.

        Parameters:
        -----------
        symbol_returns : dict
            {symbol: Series of daily returns (%)}
        symbol_regimes : dict
            {symbol: [(date, regime), ...]}
        regime : str
            Regime to analyze (bull/bear/sideways/volatile)

        Returns:
        --------
        RegimeRiskProfile with regime-specific metrics
        """
        regime_returns = []

        # Collect returns during specified regime
        for symbol, returns in symbol_returns.items():
            if symbol not in symbol_regimes:
                continue

            regimes = symbol_regimes[symbol]
            for i, (date, reg) in enumerate(regimes):
                if reg == regime:
                    # Get returns during this regime
                    if i < len(regimes) - 1:
                        end_date = regimes[i + 1][0]
                    else:
                        end_date = returns.index[-1]

                    regime_rets = returns[
                        (returns.index >= date) & (returns.index < end_date)
                    ]
                    regime_returns.extend(regime_rets.values)

        if not regime_returns:
            return RegimeRiskProfile(
                regime=regime,
                volatility_pct=0,
                var_95_pct=0,
                es_95_pct=0,
                max_historical_drawdown_pct=0,
                avg_daily_loss_pct=0,
                worst_day_loss_pct=0,
                prob_loss_above_1pct=0,
                sharpe_ratio=0,
            )

        regime_rets_array = np.array(regime_returns)

        # Calculate metrics
        vol = np.std(regime_rets_array) * np.sqrt(252) * 100
        var_95 = np.percentile(regime_rets_array, 5)
        es_95 = np.mean(regime_rets_array[regime_rets_array <= var_95])

        # Drawdown
        cumulative = np.cumprod(1 + regime_rets_array / 100)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max) / running_max
        max_dd = np.min(drawdown) * 100

        # Loss metrics
        losses = regime_rets_array[regime_rets_array < 0]
        avg_loss = np.mean(losses) if len(losses) > 0 else 0
        worst_day = np.min(regime_rets_array) if len(regime_rets_array) > 0 else 0
        prob_loss_1pct = (
            (np.sum(regime_rets_array < -1) / len(regime_rets_array) * 100)
            if len(regime_rets_array) > 0
            else 0
        )

        # Sharpe
        avg_ret = np.mean(regime_rets_array)
        daily_vol_std = np.std(regime_rets_array)
        sharpe = (
            ((avg_ret - 0.02 / 252) / daily_vol_std) * np.sqrt(252)
            if daily_vol_std > 0
            else 0
        )

        return RegimeRiskProfile(
            regime=regime,
            volatility_pct=vol,
            var_95_pct=var_95,
            es_95_pct=es_95,
            max_historical_drawdown_pct=max_dd,
            avg_daily_loss_pct=avg_loss,
            worst_day_loss_pct=worst_day,
            prob_loss_above_1pct=prob_loss_1pct,
            sharpe_ratio=sharpe,
        )

    def calculate_marginal_var(
        self,
        position_values: Dict[str, float],  # symbol → position value
        returns_correlation: pd.DataFrame,  # correlation matrix
        confidence_level: Optional[float] = None,
    ) -> Dict[str, float]:
        """
        Calculate Marginal VaR for each position (contribution to portfolio VaR).

        Parameters:
        -----------
        position_values : dict
            {symbol: value in EUR}
        returns_correlation : pd.DataFrame
            Correlation matrix of returns
        confidence_level : float
            Confidence level for VaR

        Returns:
        --------
        {symbol: marginal_var_contribution}
        """
        conf = confidence_level or self.confidence_level
        total_value = sum(position_values.values())

        if total_value <= 0:
            return {}

        marginal_vars = {}

        for symbol in position_values.keys():
            if symbol not in returns_correlation.columns:
                marginal_vars[symbol] = 0
                continue

            # Marginal VaR = change in portfolio VaR if position increases by 1%
            weight = position_values[symbol] / total_value
            correlation_to_portfolio = returns_correlation[symbol].mean()

            # Simplified: marginal VaR ≈ weight × correlation × portfolio volatility
            marginal_var = weight * correlation_to_portfolio

            marginal_vars[symbol] = marginal_var

        return marginal_vars

    def get_risk_summary(self, metrics: RiskMetrics) -> str:
        """Get human-readable risk summary."""
        summary = "📊 RISK METRICS SUMMARY:\n"
        summary += f"  Value at Risk (95%): {metrics.value_at_risk_95:.2f}%\n"
        summary += f"  Expected Shortfall (95%): {metrics.expected_shortfall_95:.2f}%\n"
        summary += f"  Max Drawdown: {metrics.max_drawdown_pct:.2f}%\n"
        summary += f"  Volatility (annualized): {metrics.volatility_pct:.2f}%\n"
        summary += f"  Sharpe Ratio: {metrics.sharpe_ratio:.2f}\n"
        summary += f"  Sortino Ratio: {metrics.sortino_ratio:.2f}\n"
        summary += f"  Skewness: {metrics.skewness:.2f}\n"
        summary += f"  Kurtosis: {metrics.kurtosis:.2f}\n"

        return summary

    def risk_classification(self, metrics: RiskMetrics) -> str:
        """Classify portfolio risk level."""
        var_95 = abs(metrics.value_at_risk_95)

        if var_95 < 1.0:
            return "CONSERVATIVE"
        elif var_95 < 2.0:
            return "MODERATE"
        elif var_95 < 3.0:
            return "BALANCED"
        elif var_95 < 5.0:
            return "AGGRESSIVE"
        else:
            return "EXTREME"


# Global instance
_risk_engine: RiskMetricsEngine = None


def get_risk_metrics_engine() -> RiskMetricsEngine:
    """Get or create risk metrics engine."""
    global _risk_engine
    if _risk_engine is None:
        _risk_engine = RiskMetricsEngine()
    return _risk_engine
