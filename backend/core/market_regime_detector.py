"""
Market regime detection for Phase 3 fine-tuning.

Identifies: RANGING (optimal for mean-reversion) vs TRENDING (dangerous)

Implements:
- ATR (Average True Range) volatility calculation
- Trend direction detection
- Regime classification
- Proactive trading pause logic
"""

import logging
from typing import List, Tuple, Dict
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class MarketRegime(Enum):
    """Market regime classification."""
    RANGING = "RANGING"  # Optimal for mean-reversion
    TRENDING_UP = "TRENDING_UP"  # Risky for mean-reversion
    TRENDING_DOWN = "TRENDING_DOWN"  # Risky for mean-reversion
    UNKNOWN = "UNKNOWN"  # Insufficient data


@dataclass
class RegimeAnalysis:
    """Market regime analysis result."""
    regime: MarketRegime
    volatility_pct: float  # ATR / SMA as percentage
    trend_strength: float  # (current - oldest) / oldest as percentage
    atr: float
    sma_close: float
    confidence: str  # "HIGH", "MEDIUM", "LOW"
    should_trade: bool  # Trading recommendation


class MarketRegimeDetector:
    """Detect market regime (ranging vs trending)."""

    # Volatility thresholds (ATR / SMA)
    HIGH_VOLATILITY_THRESHOLD = 2.5  # > 2.5% = high volatility
    LOW_VOLATILITY_THRESHOLD = 1.5  # < 1.5% = low volatility

    # Trend strength thresholds
    STRONG_TREND_THRESHOLD = 2.0  # > 2.0% move = strong trend
    WEAK_TREND_THRESHOLD = 0.5  # < 0.5% move = weak/no trend

    @staticmethod
    def calculate_atr(candles: List[Dict], period: int = 14) -> float:
        """Calculate Average True Range (ATR).

        ATR measures volatility over period.
        TR = max(H-L, |H-C_prev|, |L-C_prev|)
        ATR = average of TR over period
        """
        if len(candles) < period + 1:
            return 0.0

        true_ranges = []
        for i in range(1, len(candles)):
            high = candles[i]["high"]
            low = candles[i]["low"]
            close_prev = candles[i - 1]["close"]

            tr = max(
                high - low,
                abs(high - close_prev),
                abs(low - close_prev)
            )
            true_ranges.append(tr)

        atr = sum(true_ranges[-period:]) / period
        return atr

    @staticmethod
    def calculate_sma(closes: List[float], period: int = 20) -> float:
        """Calculate Simple Moving Average of close prices."""
        if len(closes) < period:
            return closes[-1] if closes else 0.0

        sma = sum(closes[-period:]) / period
        return sma

    @staticmethod
    def detect_trend_direction(
        closes: List[float],
        period: int = 5
    ) -> Tuple[str, float]:
        """Detect trend direction and strength.

        Uses last N closes to determine direction.
        Strength = (current - oldest) / oldest as percentage
        """
        if len(closes) < period:
            return "UNKNOWN", 0.0

        oldest = closes[-period]
        current = closes[-1]

        if oldest == 0:
            return "UNKNOWN", 0.0

        strength = ((current - oldest) / oldest) * 100

        if strength > MarketRegimeDetector.STRONG_TREND_THRESHOLD:
            return "UP", strength
        elif strength < -MarketRegimeDetector.STRONG_TREND_THRESHOLD:
            return "DOWN", strength
        else:
            return "RANGING", strength

    @staticmethod
    def analyze_regime(
        candles: List[Dict],
        closes: List[float]
    ) -> RegimeAnalysis:
        """Analyze market regime.

        Args:
            candles: List of OHLC candles with {'high', 'low', 'close'}
            closes: List of close prices

        Returns:
            RegimeAnalysis with classification and trading recommendation
        """
        if len(candles) < 5 or len(closes) < 5:
            return RegimeAnalysis(
                regime=MarketRegime.UNKNOWN,
                volatility_pct=0.0,
                trend_strength=0.0,
                atr=0.0,
                sma_close=0.0,
                confidence="LOW",
                should_trade=True  # Default: trade if insufficient data
            )

        # Calculate volatility
        atr = MarketRegimeDetector.calculate_atr(candles)
        sma_close = MarketRegimeDetector.calculate_sma(closes)

        if sma_close == 0:
            volatility_pct = 0.0
        else:
            volatility_pct = (atr / sma_close) * 100

        # Detect trend
        trend_dir, trend_strength = MarketRegimeDetector.detect_trend_direction(closes)

        # Classify regime
        if volatility_pct > MarketRegimeDetector.HIGH_VOLATILITY_THRESHOLD:
            # High volatility + strong trend = risky for mean-reversion
            if trend_dir == "UP":
                regime = MarketRegime.TRENDING_UP
                should_trade = False
                confidence = "HIGH"
            elif trend_dir == "DOWN":
                regime = MarketRegime.TRENDING_DOWN
                should_trade = False
                confidence = "HIGH"
            else:
                # High volatility but no clear trend = uncertain
                regime = MarketRegime.RANGING
                should_trade = True
                confidence = "MEDIUM"

        elif volatility_pct < MarketRegimeDetector.LOW_VOLATILITY_THRESHOLD:
            # Low volatility = ideal for mean-reversion
            regime = MarketRegime.RANGING
            should_trade = True
            confidence = "HIGH"

        else:
            # Normal volatility
            if trend_dir == "UP" or trend_dir == "DOWN":
                # Trending in normal volatility = caution
                regime = MarketRegime.TRENDING_UP if trend_dir == "UP" else MarketRegime.TRENDING_DOWN
                should_trade = False
                confidence = "MEDIUM"
            else:
                regime = MarketRegime.RANGING
                should_trade = True
                confidence = "MEDIUM"

        analysis = RegimeAnalysis(
            regime=regime,
            volatility_pct=volatility_pct,
            trend_strength=trend_strength,
            atr=atr,
            sma_close=sma_close,
            confidence=confidence,
            should_trade=should_trade
        )

        # Log analysis
        status = "✅ TRADE" if should_trade else "⏸️ PAUSE"
        logger.info(
            f"📈 Market Regime Analysis: {regime.value} {status}\n"
            f"  Volatility: {volatility_pct:.2f}% (ATR/SMA)\n"
            f"  Trend: {trend_dir} ({trend_strength:+.2f}%)\n"
            f"  Confidence: {confidence}"
        )

        return analysis
