"""
Phase 323: Portfolio Backtesting v2

Backtest allocation strategies with rolling window optimization,
transaction costs, and comprehensive performance metrics.
"""

import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class BacktestResult:
    """Backtest results for an allocation strategy."""

    strategy_name: str
    allocation: Dict[str, float]  # symbol -> weight %
    start_date: datetime
    end_date: datetime
    period_days: int

    # Returns
    total_return_pct: float
    annualized_return_pct: float

    # Risk metrics
    volatility_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown_pct: float
    calmar_ratio: float

    # Win metrics
    win_rate_pct: float  # % of positive days
    best_day_return_pct: float
    worst_day_return_pct: float
    positive_months: int
    total_months: int

    # Transaction costs
    num_rebalances: int
    total_transaction_cost_pct: float
    total_tax_cost_pct: float

    # Returns series
    daily_returns: pd.Series
    equity_curve: pd.Series


@dataclass
class AllocationComparison:
    """Comparison between multiple allocation strategies."""

    results: List[BacktestResult]
    best_sharpe: str  # strategy_name with best Sharpe
    best_return: str
    best_risk_adjusted: str
    comparison_metrics: Dict[str, Dict[str, float]]


class PortfolioBacktestEngineV2:
    """Backtest portfolio allocation strategies."""

    def __init__(self):
        """Initialize backtest engine."""
        self.risk_free_rate = 0.02

    def backtest_allocation(
        self,
        historical_returns: Dict[str, pd.Series],  # symbol -> daily returns (%)
        allocation: Dict[str, float],  # symbol -> weight %
        strategy_name: str = "allocation",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        transaction_cost_pct: float = 0.001,  # 10 bps execution
        tax_rate: float = 0.27,
    ) -> BacktestResult:
        """
        Backtest a fixed allocation.

        Parameters:
        -----------
        historical_returns : dict
            {symbol: Series of daily returns (%)}
        allocation : dict
            {symbol: weight %}
        strategy_name : str
            Name for this strategy
        start_date : datetime
            Backtest start date (defaults to earliest data)
        end_date : datetime
            Backtest end date (defaults to latest data)
        transaction_cost_pct : float
            Execution cost per trade (10 bps = 0.001)
        tax_rate : float
            Capital gains tax rate (27% for Germany)

        Returns:
        --------
        BacktestResult with performance metrics
        """
        # Normalize allocation
        total_weight = sum(allocation.values())
        normalized_allocation = {
            s: w / total_weight * 100 for s, w in allocation.items()
        }

        # Align returns to common dates
        all_dates = set()
        for returns in historical_returns.values():
            all_dates.update(returns.index)
        all_dates = sorted(all_dates)

        if not all_dates:
            raise ValueError("No data available for backtest")

        # Create aligned returns DataFrame
        returns_df = pd.DataFrame(index=all_dates)
        for symbol, ret_series in historical_returns.items():
            returns_df[symbol] = ret_series

        returns_df = returns_df.ffill().dropna()

        # Apply date filters
        if start_date:
            returns_df = returns_df[returns_df.index >= start_date]
        if end_date:
            returns_df = returns_df[returns_df.index <= end_date]

        if returns_df.empty:
            raise ValueError("No data in date range")

        # Calculate portfolio returns
        portfolio_returns = pd.Series(0.0, index=returns_df.index)
        weights_in_data = 0
        for symbol, weight in normalized_allocation.items():
            if symbol in returns_df.columns:
                portfolio_returns += returns_df[symbol] * (weight / 100)
                weights_in_data += weight

        # Renormalize weights to only those with data
        if weights_in_data > 0 and weights_in_data < 100:
            portfolio_returns = portfolio_returns * (100 / weights_in_data)

        # Build equity curve (assuming 1.0 initial value)
        equity_curve = (1 + portfolio_returns / 100).cumprod()

        # Calculate metrics
        result = self._calculate_metrics(
            daily_returns=portfolio_returns,
            equity_curve=equity_curve,
            strategy_name=strategy_name,
            allocation=normalized_allocation,
            start_date=returns_df.index[0],
            end_date=returns_df.index[-1],
            transaction_cost_pct=transaction_cost_pct,
            tax_rate=tax_rate,
            num_rebalances=0,  # Fixed allocation = no rebalances
        )

        return result

    def backtest_rolling_optimization(
        self,
        historical_returns: Dict[str, pd.Series],
        risk_level: str = "balanced",
        rebalance_freq: str = "monthly",  # monthly, quarterly, annual
        initial_allocation: Optional[Dict[str, float]] = None,
        strategy_name: str = "rolling_optimization",
        transaction_cost_pct: float = 0.001,
        tax_rate: float = 0.27,
    ) -> BacktestResult:
        """
        Backtest with rolling window optimization and periodic rebalancing.

        Parameters:
        -----------
        historical_returns : dict
            {symbol: Series of daily returns (%)}
        risk_level : str
            Target risk level for optimization
        rebalance_freq : str
            Rebalancing frequency: monthly, quarterly, or annual
        initial_allocation : dict
            Starting allocation (defaults to equal weight)
        strategy_name : str
            Name for this strategy
        transaction_cost_pct : float
            Execution cost per trade
        tax_rate : float
            Capital gains tax rate

        Returns:
        --------
        BacktestResult with rolling optimization performance
        """
        from backend.analytics.portfolio_optimizer import get_portfolio_optimizer

        optimizer = get_portfolio_optimizer()

        # Align returns
        all_dates = set()
        for returns in historical_returns.values():
            all_dates.update(returns.index)
        all_dates = sorted(all_dates)

        returns_df = pd.DataFrame(index=all_dates)
        for symbol, ret_series in historical_returns.items():
            returns_df[symbol] = ret_series

        returns_df = returns_df.ffill().dropna()

        # Initial allocation
        n_symbols = len(historical_returns)
        if not initial_allocation:
            initial_allocation = {s: 100 / n_symbols for s in historical_returns.keys()}

        # Rebalancing schedule
        rebalance_dates = self._get_rebalance_dates(returns_df.index, rebalance_freq)

        portfolio_values = []
        rebalance_count = 0
        current_allocation = initial_allocation.copy()
        lookback_window = 252  # 1 year

        for date in returns_df.index:
            # Rebalance if needed
            if date in rebalance_dates and date != returns_df.index[0]:
                # Get returns up to this date for optimization
                window_start = max(0, returns_df.index.get_loc(date) - lookback_window)
                window_returns = {}

                for symbol in historical_returns.keys():
                    sym_data = returns_df[symbol].iloc[
                        window_start : returns_df.index.get_loc(date)
                    ]
                    if len(sym_data) > 20:
                        window_returns[symbol] = sym_data

                if window_returns:
                    # Optimize
                    target = optimizer.optimize_portfolio(
                        returns=window_returns,
                        risk_level=risk_level,
                    )
                    current_allocation = target.allocation.copy()
                    rebalance_count += 1

            # Calculate portfolio return on this day
            daily_return = 0
            for symbol, weight in current_allocation.items():
                if symbol in returns_df.columns:
                    daily_return += returns_df[symbol].loc[date] * (weight / 100)

            portfolio_values.append(daily_return)

        portfolio_returns = pd.Series(portfolio_values, index=returns_df.index)
        equity_curve = (1 + portfolio_returns / 100).cumprod()

        result = self._calculate_metrics(
            daily_returns=portfolio_returns,
            equity_curve=equity_curve,
            strategy_name=strategy_name,
            allocation=current_allocation,
            start_date=returns_df.index[0],
            end_date=returns_df.index[-1],
            transaction_cost_pct=transaction_cost_pct,
            tax_rate=tax_rate,
            num_rebalances=rebalance_count,
        )

        return result

    def backtest_multiple_allocations(
        self,
        historical_returns: Dict[str, pd.Series],
        allocations: Dict[str, Dict[str, float]],  # name -> allocation
        **kwargs,
    ) -> AllocationComparison:
        """
        Backtest multiple allocation strategies and compare.

        Parameters:
        -----------
        historical_returns : dict
            {symbol: Series of daily returns (%)}
        allocations : dict
            {strategy_name: {symbol: weight %}}
        **kwargs : Additional args for backtest_allocation

        Returns:
        --------
        AllocationComparison with all results
        """
        results = []

        for name, allocation in allocations.items():
            try:
                result = self.backtest_allocation(
                    historical_returns=historical_returns,
                    allocation=allocation,
                    strategy_name=name,
                    **kwargs,
                )
                results.append(result)
            except Exception as e:
                logger.error(f"Error backtesting {name}: {e}")
                continue

        if not results:
            raise ValueError("No successful backtests")

        # Find best performers
        best_sharpe_result = max(results, key=lambda r: r.sharpe_ratio)
        best_return_result = max(results, key=lambda r: r.total_return_pct)

        # Risk-adjusted: Sharpe ratio
        best_risk_adjusted_result = best_sharpe_result

        # Build comparison metrics
        comparison = {}
        for result in results:
            comparison[result.strategy_name] = {
                "total_return_pct": round(result.total_return_pct, 2),
                "annualized_return_pct": round(result.annualized_return_pct, 2),
                "volatility_pct": round(result.volatility_pct, 2),
                "sharpe_ratio": round(result.sharpe_ratio, 2),
                "sortino_ratio": round(result.sortino_ratio, 2),
                "max_drawdown_pct": round(result.max_drawdown_pct, 2),
                "calmar_ratio": round(result.calmar_ratio, 2),
                "win_rate_pct": round(result.win_rate_pct, 2),
            }

        return AllocationComparison(
            results=results,
            best_sharpe=best_sharpe_result.strategy_name,
            best_return=best_return_result.strategy_name,
            best_risk_adjusted=best_risk_adjusted_result.strategy_name,
            comparison_metrics=comparison,
        )

    def _calculate_metrics(
        self,
        daily_returns: pd.Series,
        equity_curve: pd.Series,
        strategy_name: str,
        allocation: Dict[str, float],
        start_date: datetime,
        end_date: datetime,
        transaction_cost_pct: float,
        tax_rate: float,
        num_rebalances: int,
    ) -> BacktestResult:
        """Calculate performance metrics."""
        period_days = (end_date - start_date).days

        # Returns
        total_return = (equity_curve.iloc[-1] - 1) * 100
        years = period_days / 365.25
        annualized_return = (
            ((equity_curve.iloc[-1]) ** (1 / years) - 1) * 100 if years > 0 else 0
        )

        # Volatility
        daily_vol = daily_returns.std()
        annual_vol = daily_vol * np.sqrt(252)

        # Sharpe ratio
        excess_return = daily_returns.mean() - (self.risk_free_rate / 252)
        sharpe = (excess_return / daily_vol) * np.sqrt(252) if daily_vol > 0 else 0

        # Sortino ratio (downside volatility)
        downside_returns = daily_returns[daily_returns < 0]
        downside_vol = downside_returns.std() if len(downside_returns) > 0 else 0
        sortino = (
            (excess_return / downside_vol) * np.sqrt(252) if downside_vol > 0 else 0
        )

        # Max drawdown
        running_max = equity_curve.expanding().max()
        drawdown = (equity_curve - running_max) / running_max * 100
        max_dd = drawdown.min()

        # Calmar ratio
        calmar = annualized_return / abs(max_dd) if abs(max_dd) > 0 else 0

        # Win rate
        positive_days = (daily_returns > 0).sum()
        win_rate = (
            (positive_days / len(daily_returns) * 100) if len(daily_returns) > 0 else 0
        )

        # Best/worst days
        best_day = daily_returns.max()
        worst_day = daily_returns.min()

        # Monthly returns
        monthly_returns = daily_returns.resample("M").sum()
        positive_months = (monthly_returns > 0).sum()
        total_months = len(monthly_returns)

        # Transaction costs (estimate)
        total_transaction_cost = num_rebalances * transaction_cost_pct
        tax_cost = max(0, total_return * tax_rate / 100) if total_return > 0 else 0

        return BacktestResult(
            strategy_name=strategy_name,
            allocation=allocation,
            start_date=start_date,
            end_date=end_date,
            period_days=period_days,
            total_return_pct=total_return,
            annualized_return_pct=annualized_return,
            volatility_pct=annual_vol * 100,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            max_drawdown_pct=max_dd,
            calmar_ratio=calmar,
            win_rate_pct=win_rate,
            best_day_return_pct=best_day,
            worst_day_return_pct=worst_day,
            positive_months=int(positive_months),
            total_months=int(total_months),
            num_rebalances=num_rebalances,
            total_transaction_cost_pct=total_transaction_cost,
            total_tax_cost_pct=tax_cost,
            daily_returns=daily_returns,
            equity_curve=equity_curve,
        )

    def _get_rebalance_dates(
        self,
        dates: pd.DatetimeIndex,
        frequency: str,
    ) -> set:
        """Get rebalancing dates based on frequency."""
        rebalance_dates = set()

        if frequency == "monthly":
            # Last trading day of each month
            for date in dates:
                # Check if next date is in different month
                if date.month != (date + timedelta(days=1)).month or date == dates[-1]:
                    rebalance_dates.add(date)

        elif frequency == "quarterly":
            # Last trading day of each quarter
            for date in dates:
                if date.month in [3, 6, 9, 12]:
                    if (
                        date.month != (date + timedelta(days=1)).month
                        or date == dates[-1]
                    ):
                        rebalance_dates.add(date)

        elif frequency == "annual":
            # Last trading day of year
            for date in dates:
                if date.month == 12:
                    if (
                        date.month != (date + timedelta(days=1)).month
                        or date == dates[-1]
                    ):
                        rebalance_dates.add(date)

        return rebalance_dates


# Global instance
_backtest_engine: PortfolioBacktestEngineV2 = None


def get_backtest_engine() -> PortfolioBacktestEngineV2:
    """Get or create backtest engine."""
    global _backtest_engine
    if _backtest_engine is None:
        _backtest_engine = PortfolioBacktestEngineV2()
    return _backtest_engine
