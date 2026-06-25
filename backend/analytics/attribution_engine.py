"""
Phase 324: Portfolio Performance Attribution

Decompose portfolio returns by position, factor exposure, and regime.
Analyze drift vs benchmark and identify return drivers.
"""

import logging
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class PositionContribution:
    """Contribution of a single position to portfolio return."""

    symbol: str
    weight_pct: float
    period_return_pct: float
    contribution_pct: float  # weight * return
    profit_loss_eur: float


@dataclass
class FactorAttribution:
    """Factor-based return attribution."""

    factor_name: str
    factor_exposure: float  # exposure to this factor
    factor_return_pct: float  # factor's return during period
    contribution_pct: float  # exposure * factor_return
    ranking: int  # rank by contribution (1 = highest)


@dataclass
class AttributionResult:
    """Complete attribution analysis."""

    period_start: datetime
    period_end: datetime
    total_return_pct: float

    # Position-level
    position_contributions: List[PositionContribution]
    top_positive_contributor: Optional[str]
    top_negative_contributor: Optional[str]

    # Factor-level
    factor_contributions: List[FactorAttribution]

    # Regime
    regime: str
    regime_return_pct: float

    # Drift
    drift_vs_benchmark_pct: float
    drift_explanation: str


@dataclass
class DriftAnalysis:
    """Drift analysis vs benchmark."""

    benchmark_weight_pct: Dict[str, float]
    portfolio_weight_pct: Dict[str, float]
    active_weight_pct: Dict[str, float]  # portfolio - benchmark
    active_return_contribution: Dict[str, float]

    total_drift_pct: float
    tracking_error_pct: float
    information_ratio: float


class PerformanceAttributionEngine:
    """Analyze and attribute portfolio performance."""

    def __init__(self):
        """Initialize attribution engine."""
        pass

    def analyze_position_contribution(
        self,
        positions: Dict[str, float],  # symbol -> position value EUR
        position_returns: Dict[str, float],  # symbol -> return %
        portfolio_value: float,
    ) -> Tuple[List[PositionContribution], float]:
        """
        Calculate contribution of each position to total return.

        Parameters:
        -----------
        positions : dict
            {symbol: value in EUR}
        position_returns : dict
            {symbol: return %}
        portfolio_value : float
            Total portfolio value

        Returns:
        --------
        (List of contributions, total portfolio return %)
        """
        contributions = []
        total_return = 0

        for symbol, value in positions.items():
            weight = (value / portfolio_value) * 100 if portfolio_value > 0 else 0
            ret = position_returns.get(symbol, 0)
            contribution = (weight / 100) * ret

            total_return += contribution

            contributions.append(
                PositionContribution(
                    symbol=symbol,
                    weight_pct=weight,
                    period_return_pct=ret,
                    contribution_pct=contribution,
                    profit_loss_eur=value * (ret / 100),
                )
            )

        # Sort by contribution
        contributions.sort(key=lambda c: abs(c.contribution_pct), reverse=True)

        return contributions, total_return

    def calculate_factor_attribution(
        self,
        returns: pd.Series,  # daily returns %
        factors: Dict[str, pd.Series],  # factor -> daily exposure
        factor_returns: Dict[str, float],  # factor -> period return %
    ) -> List[FactorAttribution]:
        """
        Calculate factor-based attribution using linear regression.

        Parameters:
        -----------
        returns : pd.Series
            Daily portfolio returns (%)
        factors : dict
            {factor_name: Series of daily factor exposure}
        factor_returns : dict
            {factor_name: period return %}

        Returns:
        --------
        List of factor attributions sorted by contribution
        """
        contributions = []

        for factor_name, exposure in factors.items():
            # Calculate average exposure during period
            avg_exposure = exposure.mean()

            # Factor return during period
            factor_ret = factor_returns.get(factor_name, 0)

            # Contribution = exposure * factor_return
            contribution = avg_exposure * factor_ret

            contributions.append(
                FactorAttribution(
                    factor_name=factor_name,
                    factor_exposure=avg_exposure,
                    factor_return_pct=factor_ret,
                    contribution_pct=contribution,
                    ranking=0,  # Will set after sorting
                )
            )

        # Sort by contribution and rank
        contributions.sort(key=lambda f: abs(f.contribution_pct), reverse=True)
        for i, c in enumerate(contributions, 1):
            c.ranking = i

        return contributions

    def analyze_regime_attribution(
        self,
        returns: pd.Series,
        regime: str,  # bull/bear/sideways/volatile
        regime_periods: List[Tuple[datetime, datetime]],  # periods in this regime
    ) -> Tuple[float, str]:
        """
        Analyze returns during specific market regime.

        Parameters:
        -----------
        returns : pd.Series
            Daily returns (%) with DatetimeIndex
        regime : str
            Market regime name
        regime_periods : list
            [(start_date, end_date), ...] for this regime

        Returns:
        --------
        (regime_return_pct, explanation)
        """
        regime_returns = []

        for start, end in regime_periods:
            mask = (returns.index >= start) & (returns.index <= end)
            period_returns = returns[mask]
            if len(period_returns) > 0:
                period_total = (1 + period_returns / 100).prod() - 1
                regime_returns.append(period_total * 100)

        if not regime_returns:
            return 0, f"No data for {regime} regime"

        avg_return = np.mean(regime_returns)
        std_dev = np.std(regime_returns)

        explanation = (
            f"{regime} regime: avg return {avg_return:.2f}%, "
            f"std dev {std_dev:.2f}%, periods: {len(regime_returns)}"
        )

        return avg_return, explanation

    def calculate_drift_analysis(
        self,
        portfolio_positions: Dict[str, float],  # symbol -> value EUR
        benchmark_positions: Dict[str, float],  # symbol -> value EUR
        portfolio_value: float,
        benchmark_value: float,
        position_returns: Dict[str, float],  # symbol -> return %
    ) -> DriftAnalysis:
        """
        Calculate drift vs benchmark and active return contribution.

        Parameters:
        -----------
        portfolio_positions : dict
            {symbol: portfolio value EUR}
        benchmark_positions : dict
            {symbol: benchmark value EUR}
        portfolio_value : float
            Total portfolio value
        benchmark_value : float
            Total benchmark value
        position_returns : dict
            {symbol: return %}

        Returns:
        --------
        DriftAnalysis with active weights and returns
        """
        # Get all symbols
        all_symbols = set(portfolio_positions.keys()) | set(benchmark_positions.keys())

        # Calculate weights
        portfolio_weights = {}
        benchmark_weights = {}
        active_weights = {}
        active_contributions = {}

        for symbol in all_symbols:
            p_val = portfolio_positions.get(symbol, 0)
            b_val = benchmark_positions.get(symbol, 0)

            p_weight = (p_val / portfolio_value * 100) if portfolio_value > 0 else 0
            b_weight = (b_val / benchmark_value * 100) if benchmark_value > 0 else 0

            portfolio_weights[symbol] = p_weight
            benchmark_weights[symbol] = b_weight
            active_weights[symbol] = p_weight - b_weight

            # Active return = active_weight * return
            ret = position_returns.get(symbol, 0)
            active_contributions[symbol] = (active_weights[symbol] / 100) * ret

        # Calculate total drift metrics
        total_active_return = sum(active_contributions.values())
        tracking_error = np.sqrt(sum(w**2 for w in active_weights.values())) / 100
        information_ratio = (
            total_active_return / tracking_error if tracking_error > 0 else 0
        )

        return DriftAnalysis(
            benchmark_weight_pct=benchmark_weights,
            portfolio_weight_pct=portfolio_weights,
            active_weight_pct=active_weights,
            active_return_contribution=active_contributions,
            total_drift_pct=total_active_return,
            tracking_error_pct=tracking_error * 100,
            information_ratio=information_ratio,
        )

    def generate_attribution_summary(
        self,
        position_contributions: List[PositionContribution],
        factor_contributions: List[FactorAttribution],
        regime: str,
        regime_return: float,
        drift: DriftAnalysis,
        total_return: float,
    ) -> AttributionResult:
        """
        Generate comprehensive attribution report.

        Returns:
        --------
        AttributionResult with all attribution details
        """
        # Find top contributors
        positive_contribs = [
            c for c in position_contributions if c.contribution_pct > 0
        ]
        negative_contribs = [
            c for c in position_contributions if c.contribution_pct < 0
        ]

        top_positive = (
            max(positive_contribs, key=lambda c: c.contribution_pct).symbol
            if positive_contribs
            else None
        )
        top_negative = (
            min(negative_contribs, key=lambda c: c.contribution_pct).symbol
            if negative_contribs
            else None
        )

        return AttributionResult(
            period_start=datetime.utcnow() - pd.Timedelta(days=252),
            period_end=datetime.utcnow(),
            total_return_pct=total_return,
            position_contributions=position_contributions,
            top_positive_contributor=top_positive,
            top_negative_contributor=top_negative,
            factor_contributions=factor_contributions,
            regime=regime,
            regime_return_pct=regime_return,
            drift_vs_benchmark_pct=drift.total_drift_pct,
            drift_explanation=f"Active return: {drift.total_drift_pct:.2f}%, "
            f"Information Ratio: {drift.information_ratio:.2f}",
        )


# Global instance
_attribution_engine: PerformanceAttributionEngine = None


def get_attribution_engine() -> PerformanceAttributionEngine:
    """Get or create attribution engine."""
    global _attribution_engine
    if _attribution_engine is None:
        _attribution_engine = PerformanceAttributionEngine()
    return _attribution_engine
