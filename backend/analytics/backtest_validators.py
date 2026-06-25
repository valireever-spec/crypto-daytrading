"""
Phase 319: Backtest Validators

Validate portfolio decision quality through historical analysis:
- Regime detection accuracy
- Exit decision profitability
- Sector rotation performance
- Rebalancing effectiveness
"""

import logging
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class RegimeAccuracy:
    """Regime detection accuracy metrics."""

    total_regime_observations: int
    correct_regime_calls: int
    accuracy_pct: float
    bull_accuracy_pct: float
    bear_accuracy_pct: float
    sideways_accuracy_pct: float
    false_positive_exits: int  # Exited but regime didn't flip
    missed_exits: int  # Regime flipped but didn't exit


@dataclass
class ExitProfitability:
    """Analysis of exit decision profitability."""

    total_exits: int
    profitable_exits: int
    unprofitable_exits: int
    win_rate_pct: float
    avg_days_held: float
    avg_return_if_held_1_week: float
    avg_return_if_held_1_month: float
    avg_return_if_held_3_months: float
    opportunity_cost: float  # Average gain if stayed in position


@dataclass
class RotationPerformance:
    """Sector rotation performance analysis."""

    total_rotations: int
    profitable_rotations: int
    win_rate_pct: float
    avg_outperformance_pct: float
    best_rotation_pct: float
    worst_rotation_pct: float
    vs_buy_hold_comparison: float  # Rotation return - buy/hold return


class BacktestValidator:
    """Validate portfolio decisions historically."""

    def __init__(self):
        """Initialize backtest validator."""
        pass

    def validate_regime_accuracy(
        self,
        actual_regimes: Dict[str, List[Tuple[datetime, str]]],  # Actual regime history
        detected_regimes: Dict[str, List[Tuple[datetime, str]]],  # What was detected
        symbol_price_history: Dict[str, pd.DataFrame],
    ) -> RegimeAccuracy:
        """
        Validate regime detection accuracy against price reversals.

        Checks if detected regimes align with actual price movements:
        - Bull: prices rising
        - Bear: prices falling
        - Sideways: prices stable

        Parameters:
        -----------
        actual_regimes : dict
            Ground truth regimes derived from price action
        detected_regimes : dict
            Regimes detected by detector
        symbol_price_history : dict
            Historical price data

        Returns:
        --------
        RegimeAccuracy metrics
        """
        total_observations = 0
        correct_calls = 0
        regime_correct_calls = {"bull": 0, "bear": 0, "sideways": 0}
        regime_total_calls = {"bull": 0, "bear": 0, "sideways": 0}
        false_positive_exits = 0
        missed_exits = 0

        for symbol in actual_regimes.keys():
            if symbol not in detected_regimes or symbol not in symbol_price_history:
                continue

            actual = actual_regimes[symbol]
            detected = detected_regimes[symbol]
            prices = symbol_price_history[symbol]

            # Compare detected vs actual regimes at each point
            for det_date, det_regime in detected:
                # Find actual regime at this date
                actual_regime = None
                for act_date, act_regime in actual:
                    if act_date <= det_date:
                        actual_regime = act_regime
                    else:
                        break

                if actual_regime:
                    total_observations += 1

                    # Check if detection matches reality
                    if det_regime == actual_regime:
                        correct_calls += 1
                        regime_correct_calls[actual_regime] = (
                            regime_correct_calls.get(actual_regime, 0) + 1
                        )

                    regime_total_calls[actual_regime] = (
                        regime_total_calls.get(actual_regime, 0) + 1
                    )

                    # Check for false positive exits (detected bear but market was bull)
                    if det_regime in ["bear", "volatile"] and actual_regime in [
                        "bull",
                        "sideways",
                    ]:
                        false_positive_exits += 1

                    # Check for missed exits (market was bear but detected bull)
                    if det_regime in ["bull", "sideways"] and actual_regime in [
                        "bear",
                        "volatile",
                    ]:
                        missed_exits += 1

        # Calculate per-regime accuracy
        overall_accuracy = (
            (correct_calls / total_observations * 100) if total_observations > 0 else 0
        )
        bull_total = regime_total_calls.get("bull", 0)
        bear_total = regime_total_calls.get("bear", 0)
        sideways_total = regime_total_calls.get("sideways", 0)

        bull_accuracy = (
            (regime_correct_calls.get("bull", 0) / bull_total * 100)
            if bull_total > 0
            else 0
        )
        bear_accuracy = (
            (regime_correct_calls.get("bear", 0) / bear_total * 100)
            if bear_total > 0
            else 0
        )
        sideways_accuracy = (
            (regime_correct_calls.get("sideways", 0) / sideways_total * 100)
            if sideways_total > 0
            else 0
        )

        return RegimeAccuracy(
            total_regime_observations=total_observations,
            correct_regime_calls=correct_calls,
            accuracy_pct=overall_accuracy,
            bull_accuracy_pct=bull_accuracy,
            bear_accuracy_pct=bear_accuracy,
            sideways_accuracy_pct=sideways_accuracy,
            false_positive_exits=false_positive_exits,
            missed_exits=missed_exits,
        )

    def validate_exit_profitability(
        self,
        exit_decisions: List[Dict],  # List of {date, symbol, exit_price, reason}
        symbol_price_history: Dict[str, pd.DataFrame],
    ) -> ExitProfitability:
        """
        Analyze profitability of exit decisions.

        For each exit, calculate:
        - Did price go up or down after exit?
        - What was the opportunity cost?
        - How long was the holding period?

        Parameters:
        -----------
        exit_decisions : list
            List of exit decisions with timestamp, symbol, price
        symbol_price_history : dict
            Historical price data

        Returns:
        --------
        ExitProfitability metrics
        """
        profitable_exits = 0
        unprofitable_exits = 0
        holding_periods = []
        future_returns_1w = []
        future_returns_1m = []
        future_returns_3m = []
        opportunity_costs = []

        for exit_decision in exit_decisions:
            symbol = exit_decision["symbol"]
            exit_date = exit_decision["date"]
            exit_price = exit_decision["price"]
            entry_date = exit_decision.get("entry_date")

            if symbol not in symbol_price_history:
                continue

            prices = symbol_price_history[symbol]
            if exit_date not in prices.index:
                continue

            # Holding period
            if entry_date:
                holding_days = (exit_date - entry_date).days
                holding_periods.append(holding_days)

            # Check future prices (1 week, 1 month, 3 months after exit)
            future_dates = [
                (exit_date + timedelta(days=7), future_returns_1w),
                (exit_date + timedelta(days=30), future_returns_1m),
                (exit_date + timedelta(days=90), future_returns_3m),
            ]

            for future_date, future_list in future_dates:
                # Find closest future date in price history
                future_price = None
                for date in prices.index:
                    if date >= future_date:
                        future_price = float(prices.loc[date, "Close"])
                        break

                if future_price:
                    future_return = ((future_price - exit_price) / exit_price) * 100
                    future_list.append(future_return)

                    if future_return > 0:
                        opportunity_costs.append(future_return)

        # Profitability: was exit timely? (price went down after exit = profitable)
        if future_returns_1m:
            for ret in future_returns_1m:
                if ret < 0:
                    profitable_exits += 1
                else:
                    unprofitable_exits += 1

        win_rate = (
            (profitable_exits / (profitable_exits + unprofitable_exits) * 100)
            if (profitable_exits + unprofitable_exits) > 0
            else 0
        )

        return ExitProfitability(
            total_exits=len(exit_decisions),
            profitable_exits=profitable_exits,
            unprofitable_exits=unprofitable_exits,
            win_rate_pct=win_rate,
            avg_days_held=np.mean(holding_periods) if holding_periods else 0,
            avg_return_if_held_1_week=np.mean(future_returns_1w)
            if future_returns_1w
            else 0,
            avg_return_if_held_1_month=np.mean(future_returns_1m)
            if future_returns_1m
            else 0,
            avg_return_if_held_3_months=np.mean(future_returns_3m)
            if future_returns_3m
            else 0,
            opportunity_cost=np.mean(opportunity_costs) if opportunity_costs else 0,
        )

    def validate_rotation_performance(
        self,
        rotation_decisions: List[Dict],  # {date, from_sector, to_sector, trades}
        sector_price_history: Dict[str, pd.DataFrame],  # sector → aggregated price
        benchmark_returns: float,  # Buy and hold return
    ) -> RotationPerformance:
        """
        Analyze sector rotation performance.

        For each rotation:
        - Calculate return of sector rotated to vs. from
        - Compare to buy-and-hold benchmark

        Parameters:
        -----------
        rotation_decisions : list
            List of rotation decisions
        sector_price_history : dict
            {sector: price DataFrame}
        benchmark_returns : float
            Buy-and-hold return (%)

        Returns:
        --------
        RotationPerformance metrics
        """
        profitable_rotations = 0
        rotation_returns = []

        for rotation in rotation_decisions:
            from_sector = rotation["from_sector"]
            to_sector = rotation["to_sector"]
            rotation_date = rotation["date"]

            if (
                from_sector not in sector_price_history
                or to_sector not in sector_price_history
            ):
                continue

            from_prices = sector_price_history[from_sector]
            to_prices = sector_price_history[to_sector]

            if (
                rotation_date not in from_prices.index
                or rotation_date not in to_prices.index
            ):
                continue

            # Get prices at rotation date
            from_price = float(from_prices.loc[rotation_date, "Close"])
            to_price = float(to_prices.loc[rotation_date, "Close"])

            # Get prices 1 month later
            future_date = rotation_date + timedelta(days=30)
            from_future = None
            to_future = None

            for date in from_prices.index:
                if date >= future_date:
                    from_future = float(from_prices.loc[date, "Close"])
                    break

            for date in to_prices.index:
                if date >= future_date:
                    to_future = float(to_prices.loc[date, "Close"])
                    break

            if from_future and to_future:
                # Return if stayed in original sector
                from_return = ((from_future - from_price) / from_price) * 100
                # Return from rotation
                to_return = ((to_future - to_price) / to_price) * 100
                # Outperformance of rotation
                outperformance = to_return - from_return
                rotation_returns.append(outperformance)

                if outperformance > 0:
                    profitable_rotations += 1

        win_rate = (
            (profitable_rotations / len(rotation_decisions) * 100)
            if rotation_decisions
            else 0
        )

        return RotationPerformance(
            total_rotations=len(rotation_decisions),
            profitable_rotations=profitable_rotations,
            win_rate_pct=win_rate,
            avg_outperformance_pct=np.mean(rotation_returns) if rotation_returns else 0,
            best_rotation_pct=max(rotation_returns) if rotation_returns else 0,
            worst_rotation_pct=min(rotation_returns) if rotation_returns else 0,
            vs_buy_hold_comparison=np.mean(rotation_returns) - benchmark_returns
            if rotation_returns
            else 0,
        )

    def get_validation_summary(
        self,
        regime_accuracy: Optional[RegimeAccuracy] = None,
        exit_profitability: Optional[ExitProfitability] = None,
        rotation_performance: Optional[RotationPerformance] = None,
    ) -> str:
        """Get human-readable validation summary."""
        summary = "✅ DECISION VALIDATION RESULTS:\n\n"

        if regime_accuracy:
            summary += "📊 Regime Detection Accuracy:\n"
            summary += f"  Overall: {regime_accuracy.accuracy_pct:.1f}%\n"
            summary += f"  Bull: {regime_accuracy.bull_accuracy_pct:.1f}%\n"
            summary += f"  Bear: {regime_accuracy.bear_accuracy_pct:.1f}%\n"
            summary += f"  Sideways: {regime_accuracy.sideways_accuracy_pct:.1f}%\n"
            summary += f"  False exits: {regime_accuracy.false_positive_exits}\n"
            summary += f"  Missed exits: {regime_accuracy.missed_exits}\n\n"

        if exit_profitability:
            summary += "💰 Exit Decision Profitability:\n"
            summary += f"  Win rate: {exit_profitability.win_rate_pct:.1f}%\n"
            summary += f"  Avg hold: {exit_profitability.avg_days_held:.0f} days\n"
            summary += (
                f"  Opportunity cost: {exit_profitability.opportunity_cost:+.2f}%\n"
            )
            summary += f"  1m return if held: {exit_profitability.avg_return_if_held_1_month:+.2f}%\n\n"

        if rotation_performance:
            summary += "🔄 Sector Rotation Performance:\n"
            summary += f"  Win rate: {rotation_performance.win_rate_pct:.1f}%\n"
            summary += f"  Avg outperformance: {rotation_performance.avg_outperformance_pct:+.2f}%\n"
            summary += (
                f"  vs Buy-Hold: {rotation_performance.vs_buy_hold_comparison:+.2f}%\n"
            )

        return summary


# Global instance
_backtest_validator: BacktestValidator = None


def get_backtest_validator() -> BacktestValidator:
    """Get or create backtest validator."""
    global _backtest_validator
    if _backtest_validator is None:
        _backtest_validator = BacktestValidator()
    return _backtest_validator
