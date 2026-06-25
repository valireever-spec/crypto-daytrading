"""Historical backtesting engine for strategy performance analysis (Phase 2 Week 6)."""

import logging
from typing import List
from dataclasses import dataclass, field
from datetime import datetime
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class BacktestTrade:
    """A completed trade from backtesting."""

    entry_date: datetime
    exit_date: datetime
    symbol: str
    entry_price: float
    exit_price: float
    quantity: float
    pnl: float
    pnl_pct: float
    holding_days: int


@dataclass
class BacktestMetrics:
    """Comprehensive backtest performance metrics."""

    strategy_name: str
    symbol: str
    start_date: datetime
    end_date: datetime
    starting_capital: float = 10000.0
    ending_capital: float = 0.0
    total_pnl: float = 0.0
    total_pnl_pct: float = 0.0

    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate_pct: float = 0.0

    avg_win: float = 0.0
    avg_loss: float = 0.0
    expectancy: float = 0.0
    profit_factor: float = 0.0

    largest_win: float = 0.0
    largest_loss: float = 0.0
    max_drawdown_pct: float = 0.0

    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    recovery_factor: float = 0.0

    consecutive_wins: int = 0
    consecutive_losses: int = 0
    max_consecutive_losses: int = 0

    avg_holding_days: float = 0.0
    trades: List[BacktestTrade] = field(default_factory=list)


class BacktestEngine:
    """Backtest trading strategies on historical data."""

    def __init__(self, initial_capital: float = 10000.0, slippage_pct: float = 0.1):
        """Initialize backtest engine.

        Args:
            initial_capital: Starting account balance
            slippage_pct: Slippage percentage per trade (default 0.1%)
        """
        self.initial_capital = initial_capital
        self.slippage_pct = slippage_pct

    def backtest_strategy(
        self,
        ohlcv_df: pd.DataFrame,
        strategy_func,
        symbol: str,
        strategy_name: str,
    ) -> BacktestMetrics:
        """Run backtest for a strategy on historical data.

        Args:
            ohlcv_df: DataFrame with OHLCV data (Open, High, Low, Close, Volume)
            strategy_func: Function that returns position (0.0-1.0) for each row
            symbol: Trading symbol
            strategy_name: Name of strategy being tested

        Returns:
            BacktestMetrics with full performance analysis
        """
        if ohlcv_df.empty:
            logger.warning(f"Empty OHLCV data for {symbol}")
            return self._empty_metrics(symbol, strategy_name)

        # Ensure required columns exist
        required_cols = ["Open", "High", "Low", "Close", "Volume"]
        if not all(col in ohlcv_df.columns for col in required_cols):
            raise ValueError(f"Missing OHLCV columns. Required: {required_cols}")

        # Make a copy and add signal column
        df = ohlcv_df.copy()

        try:
            # Apply strategy to get positions
            df["position"] = df.apply(
                lambda row: strategy_func(df.loc[: row.name]), axis=1
            )
        except Exception as e:
            logger.error(f"Error applying strategy: {e}")
            return self._empty_metrics(symbol, strategy_name)

        # Detect entry/exit signals
        df["position_change"] = df["position"].diff()
        df["entry"] = df["position_change"] > 0.1  # New position
        df["exit"] = df["position_change"] < -0.1  # Exit position

        # Run simulation
        trades = self._simulate_trades(df)

        # Calculate metrics
        metrics = self._calculate_metrics(
            trades=trades,
            symbol=symbol,
            strategy_name=strategy_name,
            start_date=df.index[0],
            end_date=df.index[-1],
        )

        logger.info(
            f"Backtest {strategy_name} {symbol}: "
            f"{metrics.total_trades} trades, "
            f"{metrics.win_rate_pct:.1f}% WR, "
            f"${metrics.total_pnl:.2f} PNL"
        )

        return metrics

    def _simulate_trades(self, df: pd.DataFrame) -> List[BacktestTrade]:
        """Simulate trades from entry/exit signals.

        Args:
            df: DataFrame with entry/exit signals

        Returns:
            List of completed trades
        """
        trades = []
        position = None
        entry_date = None
        entry_price = None

        for idx, row in df.iterrows():
            # Check for entry signal
            if row["entry"]:
                # Close previous position if open
                if position is not None:
                    exit_price = row["Close"]
                    trades.append(
                        self._calculate_trade(
                            entry_date=entry_date,
                            exit_date=idx,
                            entry_price=entry_price,
                            exit_price=exit_price,
                        )
                    )

                # Open new position
                position = row["position"]
                entry_date = idx
                entry_price = row["Close"] * (1 + self.slippage_pct / 100)

            # Check for exit signal
            elif row["exit"] and position is not None:
                exit_price = row["Close"] * (1 - self.slippage_pct / 100)
                trades.append(
                    self._calculate_trade(
                        entry_date=entry_date,
                        exit_date=idx,
                        entry_price=entry_price,
                        exit_price=exit_price,
                    )
                )
                position = None
                entry_date = None
                entry_price = None

        # Close final position if open
        if position is not None and len(df) > 0:
            last_close = df.iloc[-1]["Close"]
            trades.append(
                self._calculate_trade(
                    entry_date=entry_date,
                    exit_date=df.index[-1],
                    entry_price=entry_price,
                    exit_price=last_close * (1 - self.slippage_pct / 100),
                )
            )

        return trades

    def _calculate_trade(
        self,
        entry_date: datetime,
        exit_date: datetime,
        entry_price: float,
        exit_price: float,
    ) -> BacktestTrade:
        """Calculate individual trade metrics.

        Args:
            entry_date: Entry datetime
            exit_date: Exit datetime
            entry_price: Entry price
            exit_price: Exit price

        Returns:
            BacktestTrade with PNL calculations
        """
        pnl = exit_price - entry_price
        pnl_pct = (pnl / entry_price) * 100
        holding_days = (exit_date - entry_date).days

        return BacktestTrade(
            entry_date=entry_date,
            exit_date=exit_date,
            symbol="",
            entry_price=entry_price,
            exit_price=exit_price,
            quantity=1.0,
            pnl=pnl,
            pnl_pct=pnl_pct,
            holding_days=max(holding_days, 1),
        )

    def _calculate_metrics(
        self,
        trades: List[BacktestTrade],
        symbol: str,
        strategy_name: str,
        start_date: datetime,
        end_date: datetime,
    ) -> BacktestMetrics:
        """Calculate comprehensive metrics from trades.

        Args:
            trades: List of BacktestTrade objects
            symbol: Trading symbol
            strategy_name: Strategy name
            start_date: Backtest start date
            end_date: Backtest end date

        Returns:
            BacktestMetrics with all statistics
        """
        metrics = BacktestMetrics(
            strategy_name=strategy_name,
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            starting_capital=self.initial_capital,
            trades=trades,
        )

        if not trades:
            metrics.ending_capital = self.initial_capital
            return metrics

        # Basic trade stats
        metrics.total_trades = len(trades)
        metrics.winning_trades = sum(1 for t in trades if t.pnl > 0)
        metrics.losing_trades = sum(1 for t in trades if t.pnl < 0)

        if metrics.total_trades > 0:
            metrics.win_rate_pct = (metrics.winning_trades / metrics.total_trades) * 100

        # Win/loss averages
        winning_trades = [t for t in trades if t.pnl > 0]
        losing_trades = [t for t in trades if t.pnl < 0]

        if winning_trades:
            metrics.avg_win = sum(t.pnl for t in winning_trades) / len(winning_trades)
            metrics.largest_win = max(t.pnl for t in winning_trades)

        if losing_trades:
            metrics.avg_loss = sum(t.pnl for t in losing_trades) / len(losing_trades)
            metrics.largest_loss = min(t.pnl for t in losing_trades)

        # Total PNL
        metrics.total_pnl = sum(t.pnl for t in trades)
        metrics.ending_capital = self.initial_capital + metrics.total_pnl
        metrics.total_pnl_pct = (metrics.total_pnl / self.initial_capital) * 100

        # Expectancy
        if metrics.total_trades > 0:
            metrics.expectancy = metrics.total_pnl / metrics.total_trades

        # Profit factor
        if metrics.avg_loss != 0:
            gross_profit = metrics.avg_win * metrics.winning_trades
            gross_loss = abs(metrics.avg_loss) * metrics.losing_trades
            if gross_loss > 0:
                metrics.profit_factor = gross_profit / gross_loss

        # Consecutive wins/losses
        consecutive_wins = 0
        consecutive_losses = 0
        for trade in trades:
            if trade.pnl > 0:
                consecutive_wins += 1
                consecutive_losses = 0
                metrics.consecutive_wins = max(
                    metrics.consecutive_wins, consecutive_wins
                )
            else:
                consecutive_losses += 1
                consecutive_wins = 0
                metrics.max_consecutive_losses = max(
                    metrics.max_consecutive_losses, consecutive_losses
                )

        # Holding period
        if trades:
            metrics.avg_holding_days = sum(t.holding_days for t in trades) / len(trades)

        # Risk metrics (simplified)
        pnls = [t.pnl for t in trades]
        if pnls and len(pnls) > 1:
            metrics.sharpe_ratio = self._calculate_sharpe_ratio(pnls)
            metrics.sortino_ratio = self._calculate_sortino_ratio(pnls)
            metrics.max_drawdown_pct = self._calculate_max_drawdown(pnls)
            metrics.recovery_factor = self._calculate_recovery_factor(metrics)

        return metrics

    def _calculate_sharpe_ratio(
        self, pnls: List[float], risk_free_rate: float = 0.02
    ) -> float:
        """Calculate Sharpe ratio.

        Args:
            pnls: List of PNL values
            risk_free_rate: Annual risk-free rate (default 2%)

        Returns:
            Sharpe ratio (annualized)
        """
        if len(pnls) < 2:
            return 0.0

        returns = np.array(pnls)
        mean_return = np.mean(returns)
        std_return = np.std(returns)

        if std_return == 0:
            return 0.0

        # Annualize (assuming daily returns)
        sharpe = ((mean_return - risk_free_rate / 252) / std_return) * np.sqrt(252)
        return float(sharpe)

    def _calculate_sortino_ratio(
        self, pnls: List[float], risk_free_rate: float = 0.02
    ) -> float:
        """Calculate Sortino ratio (focuses on downside volatility).

        Args:
            pnls: List of PNL values
            risk_free_rate: Annual risk-free rate

        Returns:
            Sortino ratio (annualized)
        """
        if len(pnls) < 2:
            return 0.0

        returns = np.array(pnls)
        mean_return = np.mean(returns)

        # Downside deviation (only losses)
        downside = returns[returns < 0]
        if len(downside) == 0:
            return float("inf")

        downside_std = np.std(downside)
        if downside_std == 0:
            return 0.0

        # Annualize
        sortino = ((mean_return - risk_free_rate / 252) / downside_std) * np.sqrt(252)
        return float(sortino)

    def _calculate_max_drawdown(self, pnls: List[float]) -> float:
        """Calculate maximum drawdown percentage.

        Args:
            pnls: List of PNL values

        Returns:
            Maximum drawdown as percentage
        """
        if not pnls:
            return 0.0

        cumulative = np.cumsum(pnls)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max) / np.maximum(running_max, 1)

        return float(np.min(drawdown) * 100) if len(drawdown) > 0 else 0.0

    def _calculate_recovery_factor(self, metrics: BacktestMetrics) -> float:
        """Calculate recovery factor (profit / max drawdown).

        Args:
            metrics: BacktestMetrics object

        Returns:
            Recovery factor
        """
        if metrics.max_drawdown_pct == 0:
            return 0.0

        return abs(metrics.total_pnl_pct / metrics.max_drawdown_pct)

    def _empty_metrics(self, symbol: str, strategy_name: str) -> BacktestMetrics:
        """Return empty metrics for failed backtest.

        Args:
            symbol: Trading symbol
            strategy_name: Strategy name

        Returns:
            Empty BacktestMetrics
        """
        return BacktestMetrics(
            strategy_name=strategy_name,
            symbol=symbol,
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow(),
            starting_capital=self.initial_capital,
            ending_capital=self.initial_capital,
        )
