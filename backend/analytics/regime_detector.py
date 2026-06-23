"""Market regime detection and analysis (Phase 2 Week 7)."""

import logging
from typing import Dict, Optional, List, Literal
from dataclasses import dataclass
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

RegimeType = Literal["BULL", "BEAR", "SIDEWAYS", "VOLATILE"]


@dataclass
class RegimeMetrics:
    """Market regime characteristics."""
    regime: RegimeType
    confidence: float  # 0-1, how confident in the classification
    volatility_pct: float  # Current market volatility
    trend_strength: float  # -1 to 1, negative=downtrend, positive=uptrend
    support_level: float  # Current support price
    resistance_level: float  # Current resistance price
    ma_20: float  # 20-day moving average
    ma_50: float  # 50-day moving average
    rsi: float  # Relative strength index (0-100)
    atr: float  # Average true range (volatility measure)


class RegimeDetector:
    """Detect and analyze market regimes."""

    def __init__(self, lookback_periods: int = 60):
        """Initialize regime detector.

        Args:
            lookback_periods: Number of periods for regime analysis (default 60 days)
        """
        self.lookback_periods = lookback_periods

    def detect_regime(self, ohlcv_df: pd.DataFrame, symbol: str = "") -> RegimeMetrics:
        """Detect current market regime.

        Args:
            ohlcv_df: DataFrame with OHLCV data
            symbol: Trading symbol (for logging)

        Returns:
            RegimeMetrics with current regime analysis
        """
        if ohlcv_df.empty or len(ohlcv_df) < 20:
            logger.warning(f"Insufficient data for regime detection ({symbol})")
            return self._default_regime()

        try:
            df = ohlcv_df.copy()

            # Calculate indicators
            df["MA_20"] = df["Close"].rolling(20).mean()
            df["MA_50"] = df["Close"].rolling(50).mean()
            df["RSI"] = self._calculate_rsi(df["Close"])
            df["ATR"] = self._calculate_atr(df)
            df["Volatility"] = df["Close"].pct_change().rolling(20).std() * 100

            # Get current values
            current = df.iloc[-1]
            ma_20 = current["MA_20"]
            ma_50 = current["MA_50"]
            rsi = current["RSI"]
            atr = current["ATR"]
            volatility = current["Volatility"]
            close = current["Close"]

            # Detect regime
            regime, confidence = self._classify_regime(
                close=close,
                ma_20=ma_20,
                ma_50=ma_50,
                rsi=rsi,
                volatility=volatility,
                df=df
            )

            # Calculate trend strength (-1 to 1)
            if ma_50 > 0:
                trend_strength = (close - ma_50) / ma_50
                trend_strength = np.clip(trend_strength, -1, 1)
            else:
                trend_strength = 0.0

            # Calculate support/resistance
            support, resistance = self._calculate_support_resistance(df)

            metrics = RegimeMetrics(
                regime=regime,
                confidence=confidence,
                volatility_pct=volatility,
                trend_strength=float(trend_strength),
                support_level=float(support),
                resistance_level=float(resistance),
                ma_20=float(ma_20),
                ma_50=float(ma_50),
                rsi=float(rsi),
                atr=float(atr),
            )

            logger.info(f"Regime: {regime} (conf={confidence:.1%}) - Vol={volatility:.2f}% | Trend={trend_strength:.2f}")
            return metrics

        except Exception as e:
            logger.error(f"Regime detection error: {e}")
            return self._default_regime()

    def _classify_regime(
        self,
        close: float,
        ma_20: float,
        ma_50: float,
        rsi: float,
        volatility: float,
        df: pd.DataFrame,
    ) -> tuple:
        """Classify market regime.

        Returns:
            Tuple of (regime_type, confidence)
        """
        # Volatility thresholds
        high_vol_threshold = 3.0
        low_vol_threshold = 1.5

        # Price position relative to moving averages
        above_ma20 = close > ma_20
        above_ma50 = close > ma_50
        ma20_above_ma50 = ma_20 > ma_50

        # RSI thresholds
        rsi_overbought = rsi > 70
        rsi_oversold = rsi < 30

        # Calculate recent trend
        recent_change = (close - df["Close"].iloc[-20]) / df["Close"].iloc[-20] if len(df) >= 20 else 0
        uptrend = recent_change > 0.02
        downtrend = recent_change < -0.02

        # Classify regime
        if volatility > high_vol_threshold:
            # High volatility regime
            regime = "VOLATILE"
            confidence = min(0.9, volatility / 5.0)
        elif ma20_above_ma50 and above_ma20 and uptrend:
            # Bull regime
            regime = "BULL"
            confidence = 0.8 if above_ma50 else 0.6
        elif not ma20_above_ma50 and not above_ma20 and downtrend:
            # Bear regime
            regime = "BEAR"
            confidence = 0.8 if not above_ma50 else 0.6
        else:
            # Sideways regime
            regime = "SIDEWAYS"
            confidence = 0.7

        return regime, float(np.clip(confidence, 0, 1))

    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate Relative Strength Index."""
        if len(prices) < period + 1:
            return pd.Series(50.0, index=prices.index)

        delta = prices.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)

        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi.fillna(50.0)

    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Average True Range."""
        if len(df) < period:
            return pd.Series(0.0, index=df.index)

        high_low = df["High"] - df["Low"]
        high_close = (df["High"] - df["Close"].shift()).abs()
        low_close = (df["Low"] - df["Close"].shift()).abs()

        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()

        return atr.fillna(0.0)

    def _calculate_support_resistance(self, df: pd.DataFrame) -> tuple:
        """Calculate support and resistance levels.

        Returns:
            Tuple of (support_level, resistance_level)
        """
        if len(df) < 20:
            close = df["Close"].iloc[-1]
            return close * 0.95, close * 1.05

        # Use 20-period highs and lows
        recent = df.tail(20)
        support = recent["Low"].min()
        resistance = recent["High"].max()

        return float(support), float(resistance)

    def _default_regime(self) -> RegimeMetrics:
        """Return default neutral regime."""
        return RegimeMetrics(
            regime="SIDEWAYS",
            confidence=0.0,
            volatility_pct=0.0,
            trend_strength=0.0,
            support_level=0.0,
            resistance_level=0.0,
            ma_20=0.0,
            ma_50=0.0,
            rsi=50.0,
            atr=0.0,
        )

    def analyze_regime_impact(
        self,
        regime: RegimeType,
        strategy_returns: Dict[str, List[float]],
    ) -> Dict[str, float]:
        """Analyze how strategies perform in different regimes.

        Args:
            regime: Current market regime
            strategy_returns: Dict mapping strategy name to list of returns

        Returns:
            Dict mapping strategy name to expected performance adjustment
        """
        adjustments = {
            "momentum": self._get_strategy_adjustment("momentum", regime),
            "reversion": self._get_strategy_adjustment("reversion", regime),
            "grid": self._get_strategy_adjustment("grid", regime),
        }
        return adjustments

    def _get_strategy_adjustment(self, strategy: str, regime: RegimeType) -> float:
        """Get performance adjustment for strategy in regime.

        Returns:
            Multiplier (1.0 = no change, >1.0 = better, <1.0 = worse)
        """
        adjustments = {
            "BULL": {
                "momentum": 1.3,  # Momentum thrives in bull markets
                "reversion": 0.7,  # Reversion struggles
                "grid": 0.9,       # Grid trades less effectively
            },
            "BEAR": {
                "momentum": 0.6,   # Momentum struggles
                "reversion": 1.2,  # Reversion works well
                "grid": 0.8,       # Grid trades less effectively
            },
            "SIDEWAYS": {
                "momentum": 0.7,   # Momentum struggles
                "reversion": 1.3,  # Reversion thrives
                "grid": 1.2,       # Grid works best here
            },
            "VOLATILE": {
                "momentum": 0.8,   # Whipsaws
                "reversion": 0.9,  # More unpredictable
                "grid": 0.6,       # Tight ranges disappear
            },
        }

        return adjustments.get(regime, {}).get(strategy, 1.0)

    def get_regime_trading_rules(self, regime: RegimeType) -> Dict:
        """Get recommended trading rules for current regime.

        Returns:
            Dict with position sizing, stops, and targets
        """
        rules = {
            "BULL": {
                "position_size_multiplier": 1.3,
                "stop_loss_pct": 2.0,
                "take_profit_pct": 5.0,
                "recommended_strategies": ["momentum"],
            },
            "BEAR": {
                "position_size_multiplier": 0.8,
                "stop_loss_pct": 2.5,
                "take_profit_pct": 3.0,
                "recommended_strategies": ["reversion"],
            },
            "SIDEWAYS": {
                "position_size_multiplier": 1.0,
                "stop_loss_pct": 1.5,
                "take_profit_pct": 2.0,
                "recommended_strategies": ["grid", "reversion"],
            },
            "VOLATILE": {
                "position_size_multiplier": 0.6,
                "stop_loss_pct": 3.0,
                "take_profit_pct": 2.5,
                "recommended_strategies": [],
            },
        }

        return rules.get(regime, rules["SIDEWAYS"])


# Global instance
_regime_detector: Optional[RegimeDetector] = None


def init_regime_detector(lookback_periods: int = 60) -> RegimeDetector:
    """Initialize global regime detector."""
    global _regime_detector
    _regime_detector = RegimeDetector(lookback_periods=lookback_periods)
    logger.info("Regime detector initialized")
    return _regime_detector


def get_regime_detector() -> Optional[RegimeDetector]:
    """Get global regime detector."""
    return _regime_detector
