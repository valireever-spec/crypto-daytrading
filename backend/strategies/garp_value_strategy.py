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
            "momentum_window": 20,   # Days for momentum calc
            "exit_stop_loss": 0.08,  # 8% stop loss
            "exit_profit_target": 0.15,  # 15% profit target
        }

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Apply GARP strategy to OHLCV data.

        Returns DataFrame with 'position' column (0.0-1.0)
        """
        result = df.copy()

        # Handle empty data
        if result.empty or len(result) < 50:
            result["position"] = 0.0
            return result[["Open", "High", "Low", "Close", "Volume", "position"]]

        # Merge defaults with provided params
        params = {
            "garp_threshold": 70.0,
            "momentum_window": 20,
            "exit_stop_loss": 0.08,
            "exit_profit_target": 0.15,
        }
        if self.params:
            params.update(self.params)

        threshold = params["garp_threshold"]
        window = int(params["momentum_window"])
        stop_loss = params["exit_stop_loss"]
        profit_target = params["exit_profit_target"]

        # Calculate GARP score components
        # Score based on: trend quality, volatility, momentum
        daily_returns = result["Close"].pct_change()
        volatility = daily_returns.rolling(window=20).std()

        # Trend strength: price vs 50-day MA
        ma_50 = result["Close"].rolling(window=50).mean()
        price_trend = (result["Close"] / ma_50 - 1) * 100

        # GARP Score: quality (low vol) + reasonable price (good trend)
        # Higher trend + lower volatility = higher GARP score
        garp_scores = (70 - volatility * 50 + price_trend).clip(0, 100)

        # Momentum: is GARP improving?
        garp_momentum = garp_scores.diff(window).fillna(0)

        # Entry: GARP >= threshold AND momentum improving
        entry_signal = (garp_scores >= threshold) & (garp_momentum > 0)

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
        result = result.dropna()

        return result[["Open", "High", "Low", "Close", "Volume", "position"]]


def apply_garp_value_strategy(df: pd.DataFrame, params: dict = None) -> pd.DataFrame:
    """Convenience function to apply GARP strategy."""
    strategy = GARPValueStrategy(params)
    return strategy.apply(df)
