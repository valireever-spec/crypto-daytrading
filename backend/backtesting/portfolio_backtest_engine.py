"""
Phase 319: Portfolio Backtest Engine

Backtest portfolio-level regime decisions (exits, rotations, rebalancing)
against historical price data to validate accuracy and profitability.
"""

import logging
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class BacktestTrade:
    """Record of a trade executed during backtest."""
    entry_date: datetime
    exit_date: Optional[datetime]
    symbol: str
    entry_price: float
    exit_price: Optional[float]
    quantity: float
    entry_reason: str
    exit_reason: Optional[str]
    pnl: float
    pnl_pct: float
    duration_days: int
    trade_type: str  # ENTRY, EXIT, ROTATION, REBALANCE


@dataclass
class BacktestMetrics:
    """Summary metrics from backtest."""
    total_return_pct: float
    annualized_return_pct: float
    max_drawdown_pct: float
    sharpe_ratio: float
    win_rate_pct: float
    profit_factor: float  # Gross profit / gross loss
    total_trades: int
    winning_trades: int
    losing_trades: int
    avg_win_pct: float
    avg_loss_pct: float
    best_trade_pct: float
    worst_trade_pct: float


@dataclass
class DecisionValidation:
    """Validation of a specific decision type (exits, rotations, etc.)."""
    decision_type: str
    decision_count: int
    correct_decisions: int
    accuracy_pct: float
    avg_profit_if_followed: float
    avg_loss_if_ignored: float
    avg_days_to_reversal: float


class PortfolioBacktestEngine:
    """Backtest portfolio-level regime decisions."""

    def __init__(self):
        """Initialize backtest engine."""
        self.trades: List[BacktestTrade] = []
        self.equity_curve: List[Tuple[datetime, float]] = []
        self.portfolio_values: Dict[datetime, float] = {}

    def backtest_regime_exits(
        self,
        symbol_price_history: Dict[str, pd.DataFrame],  # symbol → OHLCV DataFrame
        regime_history: Dict[str, List[Tuple[datetime, str]]],  # symbol → [(date, regime)]
        initial_capital: float = 100000,
        position_size_pct: float = 0.05,
    ) -> Tuple[BacktestMetrics, List[BacktestTrade]]:
        """
        Backtest correlated exits: exit when regime flips to bear/volatile.

        Parameters:
        -----------
        symbol_price_history : dict
            {symbol: DataFrame with OHLCV and dates as index}
        regime_history : dict
            {symbol: [(date, regime), ...]}
        initial_capital : float
            Starting capital for backtest
        position_size_pct : float
            Position size per symbol (% of capital)

        Returns:
        --------
        (BacktestMetrics, List[BacktestTrade])
        """
        self.trades = []
        portfolio_value = initial_capital
        positions: Dict[str, Dict] = {}  # symbol → {entry_price, entry_date, quantity}
        previous_regimes: Dict[str, str] = {}

        # Get all dates in chronological order
        all_dates = set()
        for df in symbol_price_history.values():
            all_dates.update(df.index)
        all_dates = sorted(all_dates)

        for date in all_dates:
            # Check for regime flips and execute trades
            for symbol, price_df in symbol_price_history.items():
                if date not in price_df.index:
                    continue

                current_price = float(price_df.loc[date, 'Close'])
                current_regime = self._get_regime_at_date(symbol, date, regime_history)

                previous_regime = previous_regimes.get(symbol)

                # ENTRY: Regime flips to bull/sideways → open position
                if previous_regime and previous_regime != current_regime:
                    if current_regime in ['bull', 'sideways'] and symbol not in positions:
                        position_value = portfolio_value * position_size_pct
                        quantity = position_value / current_price

                        positions[symbol] = {
                            'entry_price': current_price,
                            'entry_date': date,
                            'quantity': quantity,
                        }

                        logger.debug(f"ENTRY: {symbol} @ {current_price:.2f} ({current_regime})")

                    # EXIT: Regime flips to bear/volatile → close position
                    elif current_regime in ['bear', 'volatile'] and symbol in positions:
                        pos = positions[symbol]
                        pnl = (current_price - pos['entry_price']) * pos['quantity']
                        pnl_pct = ((current_price - pos['entry_price']) / pos['entry_price']) * 100

                        self.trades.append(BacktestTrade(
                            entry_date=pos['entry_date'],
                            exit_date=date,
                            symbol=symbol,
                            entry_price=pos['entry_price'],
                            exit_price=current_price,
                            quantity=pos['quantity'],
                            entry_reason=f"Regime flip to {previous_regime}",
                            exit_reason=f"Regime flip to {current_regime}",
                            pnl=pnl,
                            pnl_pct=pnl_pct,
                            duration_days=(date - pos['entry_date']).days,
                            trade_type="EXIT",
                        ))

                        portfolio_value += pnl
                        del positions[symbol]

                        logger.debug(f"EXIT: {symbol} @ {current_price:.2f} → PnL: {pnl_pct:.2f}%")

                previous_regimes[symbol] = current_regime

            # Record equity curve
            self.equity_curve.append((date, portfolio_value))

        # Calculate metrics
        metrics = self._calculate_metrics(initial_capital, portfolio_value)

        return metrics, self.trades

    def backtest_sector_rotations(
        self,
        symbol_price_history: Dict[str, pd.DataFrame],
        symbol_sectors: Dict[str, str],
        regime_history: Dict[str, List[Tuple[datetime, str]]],
        initial_capital: float = 100000,
        position_size_pct: float = 0.10,
    ) -> Tuple[BacktestMetrics, List[BacktestTrade]]:
        """
        Backtest sector rotations: rotate when sectors become over/underweight.

        Parameters:
        -----------
        symbol_price_history : dict
            {symbol: DataFrame}
        symbol_sectors : dict
            {symbol: sector}
        regime_history : dict
            {symbol: [(date, regime)]}
        initial_capital : float
            Starting capital
        position_size_pct : float
            Position size per symbol

        Returns:
        --------
        (BacktestMetrics, List[BacktestTrade])
        """
        self.trades = []
        portfolio_value = initial_capital
        positions: Dict[str, Dict] = {}
        current_allocation: Dict[str, float] = {}

        # Get all dates
        all_dates = set()
        for df in symbol_price_history.values():
            all_dates.update(df.index)
        all_dates = sorted(all_dates)

        for date in all_dates:
            # Update prices and calculate current sector allocation
            sector_allocation = self._calculate_sector_allocation(
                date, symbol_price_history, symbol_sectors, positions
            )

            # Get portfolio regime
            portfolio_regime = self._get_portfolio_regime(date, regime_history)

            # Get target allocation for current regime
            target_allocation = self._get_regime_allocation_targets(portfolio_regime)

            # Identify rotations (significant drift from target)
            for sector, current_pct in sector_allocation.items():
                target_pct = target_allocation.get(sector, 10)
                drift = current_pct - target_pct

                # Rotate if drift > 10%
                if abs(drift) > 10:
                    # Find underperforming symbols in overweight sector to sell
                    if drift > 0:
                        symbols_in_sector = [s for s, sec in symbol_sectors.items() if sec == sector]
                        for symbol in symbols_in_sector:
                            if symbol in positions and date in symbol_price_history[symbol].index:
                                pos = positions[symbol]
                                exit_price = float(symbol_price_history[symbol].loc[date, 'Close'])
                                pnl = (exit_price - pos['entry_price']) * pos['quantity']
                                pnl_pct = ((exit_price - pos['entry_price']) / pos['entry_price']) * 100

                                self.trades.append(BacktestTrade(
                                    entry_date=pos['entry_date'],
                                    exit_date=date,
                                    symbol=symbol,
                                    entry_price=pos['entry_price'],
                                    exit_price=exit_price,
                                    quantity=pos['quantity'],
                                    entry_reason=f"Entry in {sector}",
                                    exit_reason=f"Sector rotation: {sector} overweight",
                                    pnl=pnl,
                                    pnl_pct=pnl_pct,
                                    duration_days=(date - pos['entry_date']).days,
                                    trade_type="ROTATION",
                                ))

                                portfolio_value += pnl
                                del positions[symbol]
                                break

            # Record equity curve
            self.equity_curve.append((date, portfolio_value))

        metrics = self._calculate_metrics(initial_capital, portfolio_value)
        return metrics, self.trades

    def backtest_rebalancing(
        self,
        symbol_price_history: Dict[str, pd.DataFrame],
        target_allocation: Dict[str, float],
        initial_capital: float = 100000,
        rebalance_frequency_days: int = 30,
    ) -> Tuple[BacktestMetrics, List[BacktestTrade]]:
        """
        Backtest periodic rebalancing to target allocation.

        Parameters:
        -----------
        symbol_price_history : dict
            {symbol: DataFrame}
        target_allocation : dict
            {symbol: target %}
        initial_capital : float
            Starting capital
        rebalance_frequency_days : int
            Days between rebalances

        Returns:
        --------
        (BacktestMetrics, List[BacktestTrade])
        """
        self.trades = []
        portfolio_value = initial_capital
        positions: Dict[str, Dict] = {}
        last_rebalance_date = None

        # Get all dates
        all_dates = set()
        for df in symbol_price_history.values():
            all_dates.update(df.index)
        all_dates = sorted(all_dates)

        for date in all_dates:
            # Check if rebalancing is needed
            if last_rebalance_date is None or (date - last_rebalance_date).days >= rebalance_frequency_days:
                # Calculate current allocation
                current_allocation = {}
                for symbol in symbol_price_history.keys():
                    if date in symbol_price_history[symbol].index and symbol in positions:
                        price = float(symbol_price_history[symbol].loc[date, 'Close'])
                        value = positions[symbol]['quantity'] * price
                        current_allocation[symbol] = (value / portfolio_value) * 100
                    else:
                        current_allocation[symbol] = 0

                # Rebalance to target
                for symbol, target_pct in target_allocation.items():
                    current_pct = current_allocation.get(symbol, 0)
                    drift = current_pct - target_pct

                    if abs(drift) > 2:  # Only rebalance if drift > 2%
                        if date in symbol_price_history[symbol].index:
                            price = float(symbol_price_history[symbol].loc[date, 'Close'])

                            if drift > 0 and symbol in positions:
                                # Sell
                                pos = positions[symbol]
                                pnl = (price - pos['entry_price']) * pos['quantity']
                                pnl_pct = ((price - pos['entry_price']) / pos['entry_price']) * 100

                                self.trades.append(BacktestTrade(
                                    entry_date=pos['entry_date'],
                                    exit_date=date,
                                    symbol=symbol,
                                    entry_price=pos['entry_price'],
                                    exit_price=price,
                                    quantity=pos['quantity'],
                                    entry_reason="Entry for rebalancing",
                                    exit_reason=f"Rebalance: sell {abs(drift):.1f}% drift",
                                    pnl=pnl,
                                    pnl_pct=pnl_pct,
                                    duration_days=(date - pos['entry_date']).days,
                                    trade_type="REBALANCE",
                                ))

                                portfolio_value += pnl
                                del positions[symbol]

                            elif drift < 0:
                                # Buy
                                target_value = portfolio_value * (target_pct / 100)
                                current_value = positions.get(symbol, {}).get('quantity', 0) * price
                                buy_value = target_value - current_value

                                if buy_value > 0:
                                    quantity = buy_value / price
                                    positions[symbol] = {
                                        'entry_price': price,
                                        'entry_date': date,
                                        'quantity': quantity,
                                    }

                last_rebalance_date = date

            # Record equity curve
            self.equity_curve.append((date, portfolio_value))

        metrics = self._calculate_metrics(initial_capital, portfolio_value)
        return metrics, self.trades

    def _get_regime_at_date(
        self,
        symbol: str,
        date: datetime,
        regime_history: Dict[str, List[Tuple[datetime, str]]],
    ) -> str:
        """Get regime for symbol at specific date."""
        if symbol not in regime_history:
            return "unknown"

        regimes = regime_history[symbol]
        for i, (reg_date, regime) in enumerate(regimes):
            if reg_date > date:
                return regimes[i - 1][1] if i > 0 else "unknown"

        return regimes[-1][1] if regimes else "unknown"

    def _get_portfolio_regime(
        self,
        date: datetime,
        regime_history: Dict[str, List[Tuple[datetime, str]]],
    ) -> str:
        """Get dominant portfolio regime at date."""
        regimes = []
        for symbol_regimes in regime_history.values():
            for reg_date, regime in symbol_regimes:
                if reg_date <= date:
                    regimes.append(regime)

        if not regimes:
            return "unknown"

        # Count regimes
        regime_counts = {}
        for r in regimes:
            regime_counts[r] = regime_counts.get(r, 0) + 1

        return max(regime_counts, key=regime_counts.get)

    def _calculate_sector_allocation(
        self,
        date: datetime,
        symbol_price_history: Dict[str, pd.DataFrame],
        symbol_sectors: Dict[str, str],
        positions: Dict[str, Dict],
    ) -> Dict[str, float]:
        """Calculate current sector allocation as % of portfolio."""
        sector_values = {}
        total_value = 0

        for symbol, pos in positions.items():
            if symbol not in symbol_price_history or date not in symbol_price_history[symbol].index:
                continue

            price = float(symbol_price_history[symbol].loc[date, 'Close'])
            value = pos['quantity'] * price
            sector = symbol_sectors.get(symbol, 'other')

            sector_values[sector] = sector_values.get(sector, 0) + value
            total_value += value

        if total_value <= 0:
            return {}

        return {s: (v / total_value) * 100 for s, v in sector_values.items()}

    def _get_regime_allocation_targets(self, regime: str) -> Dict[str, float]:
        """Get target sector allocation for regime."""
        targets = {
            "bull": {
                "technology": 30,
                "cryptocurrency": 15,
                "consumer": 20,
                "finance": 15,
                "healthcare": 10,
                "energy": 5,
                "utilities": 5,
            },
            "bear": {
                "technology": 10,
                "cryptocurrency": 5,
                "consumer": 10,
                "finance": 15,
                "healthcare": 25,
                "energy": 15,
                "utilities": 20,
            },
        }

        return targets.get(regime, {k: 14 for k in ["technology", "cryptocurrency", "consumer", "finance", "healthcare", "energy", "utilities"]})

    def _calculate_metrics(
        self,
        initial_capital: float,
        final_capital: float,
    ) -> BacktestMetrics:
        """Calculate backtest performance metrics."""
        # Returns
        total_return = final_capital - initial_capital
        total_return_pct = (total_return / initial_capital) * 100

        # Annualized return (assuming 252 trading days)
        days = len(self.equity_curve)
        years = max(days / 252, 0.01)
        annualized_return = (((final_capital / initial_capital) ** (1 / years)) - 1) * 100

        # Drawdown
        if self.equity_curve:
            peak = max(v for _, v in self.equity_curve)
            trough = min(v for _, v in self.equity_curve)
            max_drawdown = ((trough - peak) / peak) * 100
        else:
            max_drawdown = 0

        # Sharpe Ratio (simplified, assuming 2% risk-free rate)
        if len(self.equity_curve) > 1:
            returns = []
            for i in range(1, len(self.equity_curve)):
                ret = (self.equity_curve[i][1] - self.equity_curve[i - 1][1]) / self.equity_curve[i - 1][1]
                returns.append(ret * 100)

            avg_return = np.mean(returns) if returns else 0
            std_return = np.std(returns) if returns else 1
            sharpe = (avg_return - 2) / std_return if std_return > 0 else 0
        else:
            sharpe = 0

        # Trade statistics
        winning_trades = [t for t in self.trades if t.pnl > 0]
        losing_trades = [t for t in self.trades if t.pnl < 0]
        win_rate = (len(winning_trades) / len(self.trades) * 100) if self.trades else 0

        gross_profit = sum(t.pnl for t in winning_trades)
        gross_loss = abs(sum(t.pnl for t in losing_trades))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

        avg_win = np.mean([t.pnl_pct for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([t.pnl_pct for t in losing_trades]) if losing_trades else 0
        best_trade = max([t.pnl_pct for t in self.trades]) if self.trades else 0
        worst_trade = min([t.pnl_pct for t in self.trades]) if self.trades else 0

        return BacktestMetrics(
            total_return_pct=total_return_pct,
            annualized_return_pct=annualized_return,
            max_drawdown_pct=max_drawdown,
            sharpe_ratio=sharpe,
            win_rate_pct=win_rate,
            profit_factor=profit_factor,
            total_trades=len(self.trades),
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            avg_win_pct=avg_win,
            avg_loss_pct=avg_loss,
            best_trade_pct=best_trade,
            worst_trade_pct=worst_trade,
        )

    def get_summary(self, metrics: BacktestMetrics) -> str:
        """Get human-readable backtest summary."""
        summary = "📊 BACKTEST RESULTS:\n"
        summary += f"  Return: {metrics.total_return_pct:+.2f}% (annualized: {metrics.annualized_return_pct:+.2f}%)\n"
        summary += f"  Drawdown: {metrics.max_drawdown_pct:.2f}%\n"
        summary += f"  Sharpe Ratio: {metrics.sharpe_ratio:.2f}\n"
        summary += f"  Win Rate: {metrics.win_rate_pct:.1f}% ({metrics.winning_trades}/{metrics.total_trades})\n"
        summary += f"  Profit Factor: {metrics.profit_factor:.2f}x\n"
        summary += f"  Avg Win: {metrics.avg_win_pct:+.2f}% | Avg Loss: {metrics.avg_loss_pct:+.2f}%\n"
        summary += f"  Best Trade: {metrics.best_trade_pct:+.2f}% | Worst Trade: {metrics.worst_trade_pct:+.2f}%\n"

        return summary


# Global instance
_backtest_engine: PortfolioBacktestEngine = None


def get_portfolio_backtest_engine() -> PortfolioBacktestEngine:
    """Get or create portfolio backtest engine."""
    global _backtest_engine
    if _backtest_engine is None:
        _backtest_engine = PortfolioBacktestEngine()
    return _backtest_engine
