"""Signal generation using technical indicators (FR-003, FR-004)."""

import logging
from typing import Dict, Optional
import pandas as pd
import numpy as np

from backend.analytics.allocation import get_allocation

logger = logging.getLogger(__name__)


class SignalGenerator:
    """Generate trading signals using technical indicators."""

    def __init__(self):
        """Initialize signal generator."""
        self.rsi_period = 14
        self.macd_fast = 12
        self.macd_slow = 26
        self.macd_signal = 9
        self.bb_period = 20
        self.bb_std = 2

    def calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate Relative Strength Index (RSI).

        Args:
            prices: Series of closing prices
            period: RSI period (default 14)

        Returns:
            RSI values (0-100)
        """
        if len(prices) < period + 1:
            return pd.Series(50.0, index=prices.index)  # Default to neutral

        delta = prices.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)

        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi.fillna(50.0)

    def calculate_macd(
        self, prices: pd.Series
    ) -> tuple[pd.Series, pd.Series, pd.Series]:
        """Calculate MACD (Moving Average Convergence Divergence).

        Args:
            prices: Series of closing prices

        Returns:
            (MACD line, Signal line, Histogram)
        """
        if len(prices) < self.macd_slow + 1:
            return (
                pd.Series(0.0, index=prices.index),
                pd.Series(0.0, index=prices.index),
                pd.Series(0.0, index=prices.index),
            )

        ema_12 = prices.ewm(span=self.macd_fast).mean()
        ema_26 = prices.ewm(span=self.macd_slow).mean()

        macd_line = ema_12 - ema_26
        signal_line = macd_line.ewm(span=self.macd_signal).mean()
        histogram = macd_line - signal_line

        return macd_line, signal_line, histogram

    def calculate_bollinger_bands(
        self, prices: pd.Series, period: int = 20, std_dev: float = 2.0
    ) -> tuple[pd.Series, pd.Series, pd.Series]:
        """Calculate Bollinger Bands.

        Args:
            prices: Series of closing prices
            period: MA period
            std_dev: Standard deviation multiplier

        Returns:
            (Upper band, Middle band (MA), Lower band)
        """
        if len(prices) < period:
            return (
                prices,
                prices,
                prices,
            )

        sma = prices.rolling(window=period).mean()
        std = prices.rolling(window=period).std()

        upper_band = sma + (std * std_dev)
        lower_band = sma - (std * std_dev)

        return upper_band, sma, lower_band

    async def generate_signal(
        self, symbol: str, prices: pd.Series
    ) -> Dict:
        """Generate composite signal for a symbol.

        Args:
            symbol: Trading symbol
            prices: Series of closing prices (OHLCV or close prices)

        Returns:
            Signal dict with score (-100 to +100), grade, indicators
        """
        if prices is None or len(prices) < 20:
            return {
                "symbol": symbol,
                "score": 50,
                "grade": "NEUTRAL",
                "reason": "Insufficient data",
                "rsi": None,
                "macd_histogram": None,
                "bb_position": None,
                "timestamp": pd.Timestamp.now().isoformat(),
            }

        try:
            # Calculate indicators
            rsi = self.calculate_rsi(prices).iloc[-1]
            macd_line, signal_line, histogram = self.calculate_macd(prices)
            upper_bb, middle_bb, lower_bb = self.calculate_bollinger_bands(prices)

            macd_hist = histogram.iloc[-1]
            current_price = prices.iloc[-1]

            # Bollinger Bands position (0 = lower, 1 = upper)
            bb_range = upper_bb.iloc[-1] - lower_bb.iloc[-1]
            if bb_range > 0:
                bb_position = (
                    current_price - lower_bb.iloc[-1]
                ) / bb_range
            else:
                bb_position = 0.5

            # Calculate components (0-100 each, then combine)
            # RSI: >70 = overbought (sell), <30 = oversold (buy)
            rsi_score = (rsi - 50) * 2  # Convert 0-100 to -100 to +100

            # MACD: positive = bullish, negative = bearish
            macd_score = 50 if pd.isna(macd_hist) else (
                np.tanh(macd_hist * 100) * 100  # Normalize to -100 to +100
            )

            # Bollinger Bands: <0.3 = near lower (buy), >0.7 = near upper (sell)
            if bb_position < 0.3:
                bb_score = 50  # Buy signal
            elif bb_position > 0.7:
                bb_score = -50  # Sell signal
            else:
                bb_score = 0  # Neutral

            # Apply user allocation weights or use defaults
            allocation_mgr = get_allocation()
            if allocation_mgr:
                composite_score = allocation_mgr.apply_to_signal(
                    rsi_score, macd_score, bb_score
                )
            else:
                # Fallback: default weights (RSI 40%, MACD 35%, BB 25%)
                composite_score = (rsi_score * 0.4) + (macd_score * 0.35) + (bb_score * 0.25)

            # Validate signal score is not NaN (GAP-5 fix)
            if pd.isna(composite_score) or np.isnan(composite_score):
                logger.warning(f"{symbol}: Signal score is NaN, defaulting to NEUTRAL")
                composite_score = 50.0
            if pd.isna(rsi):
                rsi = 50.0
            if pd.isna(bb_position):
                bb_position = 0.5

            # Determine grade
            if composite_score >= 70:
                grade = "STRONG BUY"
            elif composite_score >= 50:
                grade = "BUY"
            elif composite_score >= 30:
                grade = "WEAK BUY"
            elif composite_score >= -30:
                grade = "NEUTRAL"
            elif composite_score >= -50:
                grade = "WEAK SELL"
            elif composite_score >= -70:
                grade = "SELL"
            else:
                grade = "STRONG SELL"

            # Determine reason
            if rsi > 70:
                reason = "RSI overbought"
            elif rsi < 30:
                reason = "RSI oversold"
            elif macd_hist > 0:
                reason = "MACD bullish crossover"
            elif macd_hist < 0:
                reason = "MACD bearish crossover"
            elif bb_position < 0.3:
                reason = "Price near lower Bollinger Band"
            elif bb_position > 0.7:
                reason = "Price near upper Bollinger Band"
            else:
                reason = "Composite technical setup"

            return {
                "symbol": symbol,
                "score": round(composite_score, 1),
                "grade": grade,
                "reason": reason,
                "rsi": round(rsi, 1),
                "macd_histogram": round(macd_hist, 6) if not pd.isna(macd_hist) else None,
                "bb_position": round(bb_position, 2),
                "current_price": round(current_price, 2),
                "timestamp": pd.Timestamp.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error generating signal for {symbol}: {e}")
            return {
                "symbol": symbol,
                "score": 50,
                "grade": "ERROR",
                "reason": str(e),
                "timestamp": pd.Timestamp.now().isoformat(),
            }


# Global signal generator instance
_signal_generator: Optional[SignalGenerator] = None


def init_signal_generator() -> SignalGenerator:
    """Initialize global signal generator."""
    global _signal_generator
    _signal_generator = SignalGenerator()
    return _signal_generator


def get_signal_generator() -> Optional[SignalGenerator]:
    """Get global signal generator."""
    return _signal_generator
