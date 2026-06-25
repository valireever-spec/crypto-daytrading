"""
GARP Value Strategy - Growth At Reasonable Price

Adapted from investing-platform for stock trading in crypto-daytrading.
Works with stocks (EQ_AAPL, EQ_MSFT, EQ_TSLA, etc.)

Entry: GARP score >= 70 AND momentum improving
Exit: Stop-loss (8%) or profit target (15%)
"""

import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)


class GARPValueStrategy:
    """GARP Value Strategy for stock trading."""

    def __init__(self, params: dict = None):
        """Initialize with configurable parameters."""
        self.params = params or {
            "garp_threshold": 70.0,  # Score 0-100
            "momentum_window": 20,  # Days for momentum calc
            "exit_stop_loss": 0.08,  # 8% stop loss
            "exit_profit_target": 0.15,  # 15% profit target
        }

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Apply GARP strategy to OHLCV data.

        Returns DataFrame with 'position' column (0.0-1.0)
        """
        result = df.copy()
        logger.debug(f"GARP: applying strategy to {len(result)} rows")

        # Handle empty data
        if result.empty or len(result) < 50:
            result["position"] = 0.0
            logger.warning(
                f"GARP: insufficient data ({len(result)} rows), returning zeros"
            )
            return result[["Open", "High", "Low", "Close", "Volume", "position"]]

        # Merge defaults with provided params
        params = {
            "garp_threshold": 50.0,  # Lowered from 70 to account for technical trading
            "momentum_window": 10,  # Faster momentum for short-term trading
            "exit_stop_loss": 0.08,
            "exit_profit_target": 0.15,
        }
        if self.params:
            params.update(self.params)

        threshold = params["garp_threshold"]
        window = int(params["momentum_window"])
        stop_loss = params["exit_stop_loss"]
        profit_target = params["exit_profit_target"]

        # GARP for technical trading: simplified quality-based entry
        # Avoid deprecated pct_change() default
        daily_returns = result["Close"].pct_change(fill_method=None)
        volatility = daily_returns.rolling(window=20).std()

        # Quality criterion 1: Price above short-term MA (20-day trend)
        ma_20 = result["Close"].rolling(window=20).mean()
        above_ma = result["Close"] > ma_20

        # Quality criterion 2: Not overextended (price not too far from 20-day MA)
        # Within 5% of MA = good entry zone
        price_pct_from_ma = ((result["Close"] - ma_20) / ma_20 * 100).fillna(0)
        not_overbought = price_pct_from_ma <= 5.0

        # Quality criterion 3: Moderate volatility (not crashing, not too calm)
        # Reasonable range: 0.5% to 3% daily volatility
        vol_reasonable = (volatility >= 0.005) & (volatility <= 0.03)
        vol_reasonable = vol_reasonable.fillna(False)

        # Momentum: 5-day price rate of change
        momentum_5d = result["Close"].pct_change(5, fill_method=None)
        momentum_positive = momentum_5d > 0

        # Volume check (GAP #11 fix): reject illiquid symbols
        # Minimum volume: 100K units (reasonable for most crypto/stocks)
        min_volume = 100_000
        has_volume = result["Volume"] >= min_volume

        # Entry signal: All quality criteria met + positive momentum + sufficient volume
        entry_signal = (
            above_ma & not_overbought & vol_reasonable & momentum_positive & has_volume
        )

        # GARP quality score (0-100) based on criteria
        garp_scores = (
            above_ma.astype(float) * 35
            + not_overbought.astype(float) * 25  # 35 pts for above MA
            + vol_reasonable.astype(float) * 25  # 25 pts for good entry zone
            + has_volume.astype(float)  # 25 pts for healthy volatility
            * 15  # 15 pts for sufficient volume
        ).fillna(0)

        # Position tracking with stop-loss and profit target
        position = np.zeros(len(result))
        entry_price = None
        in_position = False

        for i in range(len(result)):
            close = result["Close"].iloc[i]

            if not in_position and entry_signal.iloc[i]:
                position[i] = 1.0
                entry_price = close
                in_position = True
            elif in_position and entry_price:
                pnl_pct = (close - entry_price) / entry_price

                # Exit on stop-loss or profit target
                if pnl_pct <= -stop_loss or pnl_pct >= profit_target:
                    position[i] = 0.0
                    in_position = False
                    entry_price = None
                else:
                    position[i] = 1.0
            else:
                position[i] = 0.0

        result["position"] = position
        rows_before = len(result)
        result = result.dropna()
        rows_after = len(result)

        if rows_before != rows_after:
            logger.warning(
                f"GARP: dropped {rows_before - rows_after} rows ({100*(rows_before-rows_after)/rows_before:.1f}%) due to NaN values"
            )

        return result[["Open", "High", "Low", "Close", "Volume", "position"]]


def apply_garp_value_strategy(df: pd.DataFrame, params: dict = None) -> pd.DataFrame:
    """Convenience function to apply GARP strategy."""
    strategy = GARPValueStrategy(params)
    return strategy.apply(df)
