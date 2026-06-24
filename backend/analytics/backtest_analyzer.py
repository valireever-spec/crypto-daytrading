"""
Phase 323: Backtest Results Analyzer

Analyze and compare backtest results, identify best strategies, visualize metrics.
"""

import logging
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import pandas as pd
import numpy as np

from backend.analytics.portfolio_backtest_engine_v2 import BacktestResult, AllocationComparison

logger = logging.getLogger(__name__)


@dataclass
class PerformanceRanking:
    """Ranking of strategies by performance metric."""
    metric: str
    rankings: List[Tuple[str, float]]  # [(strategy_name, metric_value), ...]


class BacktestAnalyzer:
    """Analyze and compare backtest results."""

    @staticmethod
    def compare_allocations(comparison: AllocationComparison) -> Dict:
        """
        Get comprehensive comparison of allocations.

        Returns:
        --------
        {
            "best_performers": {...},
            "risk_analysis": {...},
            "return_analysis": {...},
            "recommendations": [...]
        }
        """
        results = comparison.results

        if not results:
            return {}

        # Rank by key metrics
        by_sharpe = sorted(results, key=lambda r: r.sharpe_ratio, reverse=True)
        by_return = sorted(results, key=lambda r: r.total_return_pct, reverse=True)
        by_drawdown = sorted(results, key=lambda r: r.max_drawdown_pct)  # Ascending = better
        by_volatility = sorted(results, key=lambda r: r.volatility_pct)

        return {
            "best_performers": {
                "sharpe_ratio": {
                    "strategy": by_sharpe[0].strategy_name,
                    "value": round(by_sharpe[0].sharpe_ratio, 2),
                },
                "total_return": {
                    "strategy": by_return[0].strategy_name,
                    "value": round(by_return[0].total_return_pct, 2),
                },
                "lowest_drawdown": {
                    "strategy": by_drawdown[0].strategy_name,
                    "value": round(by_drawdown[0].max_drawdown_pct, 2),
                },
                "lowest_volatility": {
                    "strategy": by_volatility[0].strategy_name,
                    "value": round(by_volatility[0].volatility_pct, 2),
                },
            },
            "all_rankings": comparison.comparison_metrics,
            "risk_adjusted_winner": comparison.best_risk_adjusted,
        }

    @staticmethod
    def analyze_rolling_performance(result: BacktestResult, period: str = "monthly") -> Dict:
        """
        Analyze rolling performance (monthly, quarterly returns).

        Parameters:
        -----------
        result : BacktestResult
            Backtest result with daily returns
        period : str
            Period for rolling analysis: monthly, quarterly, annual

        Returns:
        --------
        {
            "periods": [...],
            "returns_pct": [...],
            "positive_periods": int,
            "average_positive_return": float,
            "average_negative_return": float
        }
        """
        if period == "monthly":
            period_returns = result.daily_returns.resample("M").sum()
        elif period == "quarterly":
            period_returns = result.daily_returns.resample("Q").sum()
        elif period == "annual":
            period_returns = result.daily_returns.resample("A").sum()
        else:
            return {}

        positive = (period_returns > 0).sum()
        negative = (period_returns < 0).sum()

        positive_returns = period_returns[period_returns > 0]
        negative_returns = period_returns[period_returns < 0]

        avg_positive = positive_returns.mean() if len(positive_returns) > 0 else 0
        avg_negative = negative_returns.mean() if len(negative_returns) > 0 else 0

        return {
            "period_type": period,
            "num_periods": len(period_returns),
            "positive_periods": int(positive),
            "negative_periods": int(negative),
            "positive_rate_pct": round(positive / len(period_returns) * 100, 2) if len(period_returns) > 0 else 0,
            "average_positive_return_pct": round(avg_positive, 2),
            "average_negative_return_pct": round(avg_negative, 2),
            "best_period_return_pct": round(period_returns.max(), 2),
            "worst_period_return_pct": round(period_returns.min(), 2),
            "period_returns_pct": [round(r, 2) for r in period_returns.values],
        }

    @staticmethod
    def calculate_metrics(daily_returns: pd.Series) -> Dict:
        """
        Calculate comprehensive performance metrics from returns series.

        Parameters:
        -----------
        daily_returns : pd.Series
            Daily returns (%)

        Returns:
        --------
        {
            "return_metrics": {...},
            "risk_metrics": {...},
            "distribution": {...}
        }
        """
        equity_curve = (1 + daily_returns / 100).cumprod()

        # Returns
        total_return = (equity_curve.iloc[-1] - 1) * 100
        years = len(daily_returns) / 252
        annualized_return = ((equity_curve.iloc[-1]) ** (1 / years) - 1) * 100 if years > 0 else 0

        # Risk metrics
        daily_vol = daily_returns.std()
        annual_vol = daily_vol * np.sqrt(252)

        # Sharpe
        excess_return = daily_returns.mean() - (0.02 / 252)
        sharpe = (excess_return / daily_vol) * np.sqrt(252) if daily_vol > 0 else 0

        # Sortino
        downside_vol = daily_returns[daily_returns < 0].std()
        sortino = (excess_return / downside_vol) * np.sqrt(252) if downside_vol > 0 else 0

        # Drawdown
        running_max = equity_curve.expanding().max()
        drawdown = (equity_curve - running_max) / running_max * 100
        max_dd = drawdown.min()

        # Calmar
        calmar = annualized_return / abs(max_dd) if abs(max_dd) > 0 else 0

        # Distribution
        skew = daily_returns.skew()
        kurt = daily_returns.kurtosis()

        return {
            "return_metrics": {
                "total_return_pct": round(total_return, 2),
                "annualized_return_pct": round(annualized_return, 2),
                "average_daily_return_pct": round(daily_returns.mean(), 3),
            },
            "risk_metrics": {
                "volatility_pct": round(annual_vol * 100, 2),
                "max_drawdown_pct": round(max_dd, 2),
                "sharpe_ratio": round(sharpe, 2),
                "sortino_ratio": round(sortino, 2),
                "calmar_ratio": round(calmar, 2),
            },
            "distribution": {
                "skewness": round(skew, 2),
                "kurtosis": round(kurt, 2),
                "min_return_pct": round(daily_returns.min(), 2),
                "max_return_pct": round(daily_returns.max(), 2),
                "median_return_pct": round(daily_returns.median(), 3),
            },
        }

    @staticmethod
    def generate_recommendations(comparison: AllocationComparison) -> List[str]:
        """
        Generate recommendations based on backtest results.

        Returns:
        --------
        List of recommendations
        """
        recommendations = []

        results = comparison.results
        if not results:
            return []

        best_sharpe = max(results, key=lambda r: r.sharpe_ratio)
        best_return = max(results, key=lambda r: r.total_return_pct)
        best_drawdown = min(results, key=lambda r: r.max_drawdown_pct)

        # Recommendation 1: Best risk-adjusted return
        recommendations.append(
            f"Best risk-adjusted returns: {best_sharpe.strategy_name} "
            f"(Sharpe {best_sharpe.sharpe_ratio:.2f}, Return {best_sharpe.total_return_pct:.2f}%)"
        )

        # Recommendation 2: Best absolute returns
        if best_return.strategy_name != best_sharpe.strategy_name:
            recommendations.append(
                f"Highest absolute returns: {best_return.strategy_name} "
                f"({best_return.total_return_pct:.2f}%, but vol {best_return.volatility_pct:.2f}%)"
            )

        # Recommendation 3: Most conservative
        if best_drawdown.strategy_name != best_sharpe.strategy_name:
            recommendations.append(
                f"Most conservative: {best_drawdown.strategy_name} "
                f"(Max DD {best_drawdown.max_drawdown_pct:.2f}%, Sharpe {best_drawdown.sharpe_ratio:.2f})"
            )

        # Recommendation 4: Volatility analysis
        all_vols = [r.volatility_pct for r in results]
        vol_range = max(all_vols) - min(all_vols)
        if vol_range > 10:
            recommendations.append(
                f"High volatility variance detected (range: {vol_range:.1f}%). "
                f"Choose based on risk tolerance."
            )

        # Recommendation 5: Consistency
        best_win_rate = max(results, key=lambda r: r.win_rate_pct)
        recommendations.append(
            f"Most consistent: {best_win_rate.strategy_name} "
            f"(Win rate {best_win_rate.win_rate_pct:.1f}%)"
        )

        return recommendations

    @staticmethod
    def compare_to_benchmark(result: BacktestResult, benchmark_return: float, benchmark_vol: float) -> Dict:
        """
        Compare backtest result to a benchmark.

        Parameters:
        -----------
        result : BacktestResult
            Backtest result
        benchmark_return : float
            Benchmark annual return (%)
        benchmark_vol : float
            Benchmark annual volatility (%)

        Returns:
        --------
        {
            "excess_return_pct": float,
            "tracking_error_pct": float,
            "information_ratio": float,
            "outperformance": str
        }
        """
        excess_return = result.annualized_return_pct - benchmark_return
        tracking_error = result.volatility_pct - benchmark_vol
        information_ratio = excess_return / abs(tracking_error) if abs(tracking_error) > 0 else 0

        outperformance = "BETTER" if excess_return > 0 else "WORSE"

        return {
            "excess_return_pct": round(excess_return, 2),
            "tracking_error_pct": round(tracking_error, 2),
            "information_ratio": round(information_ratio, 2),
            "outperformance": outperformance,
            "vs_benchmark": {
                "strategy_return_pct": round(result.annualized_return_pct, 2),
                "benchmark_return_pct": round(benchmark_return, 2),
                "strategy_volatility_pct": round(result.volatility_pct, 2),
                "benchmark_volatility_pct": round(benchmark_vol, 2),
            },
        }
