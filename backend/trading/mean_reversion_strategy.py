"""
Mean-Reversion Strategy - Buy Oversold, Sell Overbought

Opposite of momentum: When prices drop too far (RSI < 30), buy expecting bounce.
When prices rally too far (RSI > 70), sell expecting pullback.

This strategy works in range-bound markets where momentum fails.
Expected win rate: 55%+ (vs 0% from momentum)
"""

from typing import Optional, Tuple, List
import logging

logger = logging.getLogger(__name__)


class MeanReversionSignalCalculator:
    """Mean-reversion strategy using RSI extremes"""

    RSI_PERIOD = 14
    RSI_OVERSOLD = 30  # Buy signal (price too low)
    RSI_OVERBOUGHT = 70  # Sell signal (price too high)
    ENTRY_THRESHOLD = 50  # Signal strength threshold

    @staticmethod
    def rsi(prices: List[float], period: int = 14) -> float:
        """Calculate RSI"""
        if len(prices) < period + 1:
            return 50.0  # Neutral if insufficient data

        deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
        gains = [d for d in deltas if d > 0]
        losses = [-d for d in deltas if d < 0]

        avg_gain = sum(gains[-period:]) / period if gains else 0
        avg_loss = sum(losses[-period:]) / period if losses else 0

        if avg_loss == 0:
            return 100.0 if avg_gain > 0 else 50.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    @staticmethod
    def sma(prices: List[float], period: int) -> float:
        """Calculate simple moving average"""
        if len(prices) < period:
            return sum(prices) / len(prices) if prices else 0.0
        return sum(prices[-period:]) / period

    @staticmethod
    def calculate_signal(
        prices: List[float],
    ) -> Tuple[Optional[float], str]:
        """
        Mean-reversion signal calculation.

        Entry Rules:
        1. RSI < 30 (oversold - buying opportunity)
        2. Price > SMA20 (not in freefall)

        Exit Rules (handled in exit.py):
        1. RSI > 70 (overbought - take profit)
        2. 10-min timeout (prevent holding losers)

        Returns:
            (signal_strength, reason) - strength = 100 * (30 - RSI) / 30 when RSI < 30
        """
        if not prices or len(prices) < 21:
            return None, "Insufficient data (need 21+ candles)"

        # Calculate RSI
        rsi = MeanReversionSignalCalculator.rsi(
            prices, MeanReversionSignalCalculator.RSI_PERIOD
        )

        # Calculate SMA20 as support level
        sma20 = MeanReversionSignalCalculator.sma(prices, 20)
        current_price = prices[-1]

        # Entry signal: RSI < 30 (oversold)
        if rsi < MeanReversionSignalCalculator.RSI_OVERSOLD:
            # Strength: how deep into oversold (0-100)
            # RSI 30 → strength 0, RSI 0 → strength 100
            strength = max(0, min(100, 100 * (30 - rsi) / 30))

            # Additional confirmation: price above SMA20
            if current_price > sma20:
                reason = (
                    f"Mean Reversion: RSI {rsi:.0f} < 30 (oversold), "
                    f"price ${current_price:.2f} > SMA20 ${sma20:.2f}"
                )
                return strength, reason
            else:
                # Still in downtrend, wait for more bounce confirmation
                reason = (
                    f"Oversold but weak: RSI {rsi:.0f} < 30, "
                    f"but price ${current_price:.2f} < SMA20 ${sma20:.2f}"
                )
                return None, reason

        # No signal
        return None, f"RSI {rsi:.0f} - waiting for oversold (< 30)"

    @staticmethod
    def get_exit_signal(rsi: float) -> Optional[str]:
        """
        Check if position should be exited (overbought).
        Called by exit.py to determine if RSI exit should trigger.

        Returns:
            "overbought" if RSI > 70, else None
        """
        if rsi > MeanReversionSignalCalculator.RSI_OVERBOUGHT:
            return "overbought"
        return None
