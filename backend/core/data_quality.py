"""Data Quality Measurement - Pillar #3 Hardening (Critical)."""

import logging
from datetime import datetime
from typing import Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class DataQualityScore:
    """Data quality assessment results."""

    price_sanity: float  # 0-100
    symbol_coverage: float  # 0-100
    websocket_health: float  # 0-100
    age_variance: float  # 0-100
    volume_validity: float  # 0-100
    volatility_reasonableness: float  # 0-100
    overall_score: float  # 0-100
    pass_gate: bool  # True if >= 90%
    failures: list  # What failed

    def __repr__(self) -> str:
        emoji = "✅" if self.pass_gate else "❌"
        return (
            f"{emoji} Data Quality: {self.overall_score:.0f}% "
            f"(sanity={self.price_sanity:.0f}, coverage={self.symbol_coverage:.0f}, "
            f"ws={self.websocket_health:.0f}, age_var={self.age_variance:.0f}, "
            f"volume={self.volume_validity:.0f}, vol_spike={self.volatility_reasonableness:.0f})"
        )


class DataQualityMeasurer:
    """Measure data quality across 6 dimensions."""

    def __init__(self):
        """Initialize data quality measurer."""
        self.previous_prices: Dict[str, float] = {}
        self.previous_timestamp: Optional[datetime] = None

    def measure(
        self,
        current_prices: Dict[str, float],
        required_symbols: list,
        websocket_health: Dict,
        last_updates: Dict[str, datetime],
        historical_volatility: Dict[str, float],
    ) -> DataQualityScore:
        """Measure data quality across all dimensions.

        Args:
            current_prices: Dict of symbol -> price
            required_symbols: List of required symbols
            websocket_health: Dict with 'connected', 'reconnect_attempts', etc.
            last_updates: Dict of symbol -> last update timestamp
            historical_volatility: Dict of symbol -> 20-day volatility %

        Returns:
            DataQualityScore with all measurements
        """
        now = datetime.utcnow()
        failures = []

        # Dimension 1: Price Sanity (25%)
        price_sanity = self._measure_price_sanity(current_prices)
        if price_sanity < 100:
            failures.append("price_sanity")

        # Dimension 2: Symbol Coverage (25%)
        symbol_coverage = self._measure_symbol_coverage(
            current_prices, required_symbols
        )
        if symbol_coverage < 100:
            failures.append("symbol_coverage")

        # Dimension 3: WebSocket Health (25%)
        websocket_health_score = self._measure_websocket_health(websocket_health)
        if websocket_health_score < 90:
            failures.append("websocket_health")

        # Dimension 4: Age Variance (15%)
        age_variance = self._measure_age_variance(last_updates, now)
        if age_variance < 100:
            failures.append("age_variance")

        # Dimension 5: Volume Validity (5%)
        volume_validity = self._measure_volume_validity(current_prices)
        if volume_validity < 100:
            failures.append("volume_validity")

        # Dimension 6: Volatility Reasonableness (5%)
        vol_reasonableness = self._measure_volatility_reasonableness(
            current_prices, historical_volatility
        )
        if vol_reasonableness < 100:
            failures.append("volatility_reasonableness")

        # Calculate weighted overall score
        overall_score = (
            price_sanity * 0.25
            + symbol_coverage * 0.25
            + websocket_health_score * 0.25
            + age_variance * 0.15
            + volume_validity * 0.05
            + vol_reasonableness * 0.05
        )

        # Store prices for next measurement
        self.previous_prices = current_prices.copy()
        self.previous_timestamp = now

        pass_gate = overall_score >= 90.0

        score = DataQualityScore(
            price_sanity=price_sanity,
            symbol_coverage=symbol_coverage,
            websocket_health=websocket_health_score,
            age_variance=age_variance,
            volume_validity=volume_validity,
            volatility_reasonableness=vol_reasonableness,
            overall_score=overall_score,
            pass_gate=pass_gate,
            failures=failures,
        )

        return score

    def _measure_price_sanity(self, current_prices: Dict[str, float]) -> float:
        """Dimension 1: Check if prices have unreasonable jumps.

        Rule: Reject if price changes >20% in 1 minute
        """
        if not self.previous_prices:
            return 100.0  # First measurement, no baseline

        failures = 0
        checked = 0

        for symbol, current_price in current_prices.items():
            if symbol not in self.previous_prices:
                continue

            prev_price = self.previous_prices[symbol]
            if prev_price <= 0:
                continue

            checked += 1
            pct_change = abs((current_price - prev_price) / prev_price * 100)

            MAX_1MIN_CHANGE = 20.0
            if pct_change > MAX_1MIN_CHANGE:
                logger.error(
                    f"{symbol}: Price spike rejected: {prev_price:.2f} → {current_price:.2f} "
                    f"({pct_change:.1f}% change > {MAX_1MIN_CHANGE}% limit)"
                )
                failures += 1

        if checked == 0:
            return 100.0

        score = max(0, 100 * (1 - failures / checked))
        return score

    def _measure_symbol_coverage(
        self, current_prices: Dict[str, float], required_symbols: list
    ) -> float:
        """Dimension 2: Check if all required symbols have data."""
        if not required_symbols:
            return 100.0

        coverage = len(current_prices) / len(required_symbols) * 100
        if coverage < 100:
            missing = len(required_symbols) - len(current_prices)
            logger.warning(
                f"Symbol coverage: {coverage:.0f}% ({missing} symbols missing)"
            )

        return min(100, coverage)

    def _measure_websocket_health(self, websocket_health: Dict) -> float:
        """Dimension 3: Check WebSocket connection and stability."""
        connected = websocket_health.get("connected", False)
        reconnect_attempts = websocket_health.get("reconnect_attempts", 0)
        last_update = websocket_health.get("last_update")

        # Check 1: Connected (0 or 100)
        connection_score = 100 if connected else 0

        # Check 2: Stability (deduct 20 per reconnect attempt)
        stability_score = max(0, 100 - (reconnect_attempts * 20))

        # Check 3: Active (receiving data)
        if last_update:
            try:
                now = datetime.utcnow()
                # Try to parse ISO format
                if isinstance(last_update, str):
                    last_ts = datetime.fromisoformat(last_update.replace("Z", "+00:00"))
                else:
                    last_ts = last_update
                age_seconds = (now - last_ts).total_seconds()
                active_score = (
                    100 if age_seconds < 5 else max(0, 100 - (age_seconds * 10))
                )
            except:
                active_score = 50
        else:
            active_score = 0

        # Weighted health score
        health_score = (
            (connection_score * 0.5) + (stability_score * 0.3) + (active_score * 0.2)
        )

        if health_score < 90:
            logger.warning(
                f"WebSocket health: {health_score:.0f}% (connected={connected}, "
                f"reconnect_attempts={reconnect_attempts})"
            )

        return health_score

    def _measure_age_variance(
        self, last_updates: Dict[str, datetime], now: datetime
    ) -> float:
        """Dimension 4: Check if all prices have similar freshness.

        Rule: Max variance should be <5 seconds
        """
        if not last_updates:
            return 100.0

        try:
            ages = []
            for symbol, last_update in last_updates.items():
                if isinstance(last_update, str):
                    ts = datetime.fromisoformat(last_update.replace("Z", "+00:00"))
                else:
                    ts = last_update
                age = (now - ts).total_seconds()
                ages.append((symbol, age))

            if not ages:
                return 100.0

            max_age = max(age for _, age in ages)
            min_age = min(age for _, age in ages)
            variance = max_age - min_age

            MAX_ACCEPTABLE_VARIANCE = 5.0
            if variance > MAX_ACCEPTABLE_VARIANCE:
                oldest = max(ages, key=lambda x: x[1])
                logger.warning(
                    f"Age variance too high: {variance:.1f}s "
                    f"({oldest[0]} is {oldest[1]:.1f}s old, others ~{min_age:.1f}s)"
                )
                return 0.0

            return 100.0
        except:
            return 50.0

    def _measure_volume_validity(self, current_prices: Dict[str, float]) -> float:
        """Dimension 5: Check for zero-volume symbols (not implemented in paper trading).

        Placeholder for future: would check actual volume from candles.
        For now, just log that we can't measure volume in paper trading.
        """
        # Paper trading doesn't provide volume data in price_cache
        # In live trading, would fetch volume from Binance
        return 100.0

    def _measure_volatility_reasonableness(
        self, current_prices: Dict[str, float], historical_volatility: Dict[str, float]
    ) -> float:
        """Dimension 6: Check if volatility is not spiking (indicates error or flash crash).

        Rule: Current volatility should not be >10x historical
        """
        if not historical_volatility:
            return 100.0

        # Note: Current volatility can't be calculated from single price point
        # This check would need intra-minute volatility data
        # For now, return 100 (would fail if we had volatility spikes)
        return 100.0


_data_quality_measurer: Optional[DataQualityMeasurer] = None


def get_data_quality_measurer() -> DataQualityMeasurer:
    """Get or create global data quality measurer."""
    global _data_quality_measurer
    if _data_quality_measurer is None:
        _data_quality_measurer = DataQualityMeasurer()
    return _data_quality_measurer
