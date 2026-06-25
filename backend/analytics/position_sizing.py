"""Dynamic position sizing based on Kelly Criterion (Phase 1 Week 3.5)."""

import logging
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PositionSizeMetrics:
    """Position sizing calculation results."""

    kelly_size: float  # Optimal Kelly size (0.0 - 1.0)
    half_kelly: float  # Conservative half-Kelly (0.5x)
    volatility_adjusted: float  # Half-Kelly adjusted by volatility
    min_size: float  # Minimum 0.5% of capital
    max_size: float  # Maximum 3.0% of capital
    recommended: float  # Final recommendation (within min/max bounds)


class PositionSizer:
    """Calculate optimal position sizes using Kelly Criterion."""

    def __init__(self, min_percent: float = 0.5, max_percent: float = 3.0):
        """Initialize position sizer.

        Args:
            min_percent: Minimum position size as % of capital (default 0.5%)
            max_percent: Maximum position size as % of capital (default 3.0%)
        """
        self.min_percent = min_percent
        self.max_percent = max_percent

    def calculate_kelly_size(
        self,
        win_rate: float,
        avg_win: float,
        avg_loss: float,
    ) -> float:
        """Calculate optimal Kelly fraction.

        Formula: f* = (bp - q) / b
        Where:
            b = ratio of win amount to loss amount
            p = probability of winning
            q = probability of losing (1 - p)

        Args:
            win_rate: Probability of winning (0.0 - 1.0)
            avg_win: Average win amount (positive)
            avg_loss: Average loss amount (positive)

        Returns:
            Kelly fraction (0.0 - 1.0, where 1.0 = 100% of capital)
        """
        if avg_win <= 0 or avg_loss <= 0:
            return 0.0

        if win_rate <= 0 or win_rate >= 1.0:
            return 0.0

        # b = avg_win / avg_loss (benefit-to-loss ratio)
        b = avg_win / avg_loss

        # p = win_rate, q = 1 - win_rate
        p = win_rate
        q = 1.0 - win_rate

        # f* = (bp - q) / b
        kelly = (b * p - q) / b if b > 0 else 0.0

        # Clamp to [0, 1]
        return max(0.0, min(1.0, kelly))

    def adjust_for_volatility(
        self,
        base_size: float,
        volatility_pct: float,
    ) -> float:
        """Adjust position size based on market volatility.

        Higher volatility → smaller positions (protect capital)
        Lower volatility → larger positions (take advantage)

        Args:
            base_size: Base position size (0.0 - 1.0)
            volatility_pct: Recent volatility as % (e.g., 2.5 for 2.5%)

        Returns:
            Volatility-adjusted size (0.0 - 1.0)
        """
        if volatility_pct <= 0:
            return base_size

        # Assume 2% volatility is "normal"
        normal_vol = 2.0
        volatility_ratio = normal_vol / volatility_pct

        # Size adjustment: 1/3 of volatility adjustment
        # (don't overreact to vol changes)
        adjustment = 1.0 + (volatility_ratio - 1.0) / 3.0
        adjustment = max(0.5, min(1.5, adjustment))  # Clamp to 0.5x - 1.5x

        return base_size * adjustment

    def calculate_size(
        self,
        capital: float,
        signal_strength: float,
        win_rate: float,
        avg_win: float,
        avg_loss: float,
        volatility_pct: float = 2.0,
    ) -> PositionSizeMetrics:
        """Calculate recommended position size.

        Args:
            capital: Total available capital (e.g., $10,000)
            signal_strength: Signal score (0.0 - 100.0, scaled to 0.0-1.0)
            win_rate: Historical win rate (0.0 - 1.0)
            avg_win: Average winning trade amount (positive)
            avg_loss: Average losing trade amount (positive)
            volatility_pct: Current volatility as percentage

        Returns:
            PositionSizeMetrics with various sizing recommendations
        """
        # Ensure inputs are valid
        if capital <= 0:
            return PositionSizeMetrics(0, 0, 0, 0, 0, 0)

        # Calculate Kelly fraction
        kelly_frac = self.calculate_kelly_size(win_rate, avg_win, avg_loss)

        # Half-Kelly (more conservative)
        half_kelly = kelly_frac / 2.0

        # Adjust for volatility
        vol_adjusted = self.adjust_for_volatility(half_kelly, volatility_pct)

        # Signal strength adjustment (0-1 scale)
        # Weak signal → smaller position; strong signal → larger position
        signal_factor = max(0.1, min(1.0, signal_strength / 100.0))
        vol_adjusted_with_signal = vol_adjusted * signal_factor

        # Convert to dollar amounts
        min_size_dollars = capital * self.min_percent / 100.0
        max_size_dollars = capital * self.max_percent / 100.0

        # Calculate recommended size as dollar amount
        recommended_fraction = vol_adjusted_with_signal
        recommended_dollars = capital * recommended_fraction

        # Clamp to min/max bounds
        recommended_bounded = max(
            min_size_dollars, min(max_size_dollars, recommended_dollars)
        )

        return PositionSizeMetrics(
            kelly_size=kelly_frac,
            half_kelly=half_kelly,
            volatility_adjusted=vol_adjusted_with_signal,
            min_size=min_size_dollars,
            max_size=max_size_dollars,
            recommended=recommended_bounded,
        )

    def calculate_shares(
        self,
        position_dollars: float,
        price_per_share: float,
    ) -> int:
        """Convert dollar amount to number of shares.

        Args:
            position_dollars: Position size in dollars
            price_per_share: Current price per unit (e.g., BTC price)

        Returns:
            Number of shares/units to buy (rounded down for safety)
        """
        if price_per_share <= 0:
            return 0

        shares = position_dollars / price_per_share
        return int(shares)  # Round down to be conservative


# Global position sizer instance
_position_sizer: Optional[PositionSizer] = None


def init_position_sizer(
    min_percent: float = 0.5,
    max_percent: float = 3.0,
) -> PositionSizer:
    """Initialize global position sizer.

    Args:
        min_percent: Minimum position size as % of capital
        max_percent: Maximum position size as % of capital
    """
    global _position_sizer
    _position_sizer = PositionSizer(min_percent=min_percent, max_percent=max_percent)
    logger.info(
        f"Position sizer initialized: {min_percent}% - {max_percent}% of capital"
    )
    return _position_sizer


def get_position_sizer() -> Optional[PositionSizer]:
    """Get global position sizer."""
    return _position_sizer
