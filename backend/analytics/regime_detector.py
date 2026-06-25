"""
Phase 315: Market Regime Detection

Classify market as Bull/Bear/Sideways/Volatile and adjust trading thresholds.
"""

import pandas as pd
import numpy as np
import logging
from typing import Dict, Tuple, Any
from enum import Enum

logger = logging.getLogger(__name__)


class MarketRegime(Enum):
    """Market regime classification."""
    BULL = "bull"
    BEAR = "bear"
    SIDEWAYS = "sideways"
    VOLATILE = "volatile"


class RegimeDetector:
    """Detect market regime and provide adaptive thresholds."""

    def __init__(
        self,
        lookback_trend: int = 50,
        lookback_vol: int = 20,
        rsi_window: int = 14,
        ma_window: int = 200,
    ):
        """Initialize regime detector."""
        self.lookback_trend = lookback_trend
        self.lookback_vol = lookback_vol
        self.rsi_window = rsi_window
        self.ma_window = ma_window

    def detect_regime(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Detect market regime from OHLCV data."""
        try:
            if df.empty or len(df) < max(self.lookback_trend, self.ma_window):
                return {
                    "regime": "unknown",
                    "trend_strength": 0.0,
                    "trend_pct": 0.0,
                    "volatility_level": "unknown",
                    "volatility_ratio": 1.0,
                    "rsi_value": 50.0,
                    "support": None,
                    "resistance": None,
                    "recommendation": "Insufficient data",
                }

            closes = df["Close"]

            # Calculate trend
            close_current = float(closes.iloc[-1])
            close_lookback = float(closes.iloc[-self.lookback_trend])
            trend_pct = (close_current - close_lookback) / close_lookback
            trend_strength = np.tanh(trend_pct * 3)

            # Calculate volatility
            returns = closes.pct_change().dropna()
            vol_recent = returns.iloc[-20:].std() if len(returns) >= 20 else returns.std()
            vol_historical = returns.std()
            vol_ratio = vol_recent / vol_historical if vol_historical > 0 else 1.0

            if vol_ratio > 1.5:
                volatility_level = "extreme"
            elif vol_ratio > 1.2:
                volatility_level = "high"
            elif vol_ratio > 0.8:
                volatility_level = "medium"
            else:
                volatility_level = "low"

            # Calculate RSI
            rsi_value = self._calculate_rsi(closes)

            # Calculate support and resistance
            support, resistance = self._calculate_support_resistance(df)

            # Determine regime
            if volatility_level == "extreme":
                regime = "volatile"
                recommendation = "⚠️ Extreme volatility: reduce position size, tighten stops"
            elif trend_strength > 0.3 and volatility_level in ["low", "medium"]:
                regime = "bull"
                recommendation = "✅ Bull market: aggressive entry, wider stops"
            elif trend_strength < -0.3 and volatility_level in ["low", "medium"]:
                regime = "bear"
                recommendation = "⛔ Bear market: conservative entry, tight stops"
            else:
                regime = "sideways"
                recommendation = "↔️ Sideways market: mean-reversion strategy"

            return {
                "regime": regime,
                "trend_strength": round(trend_strength, 3),
                "trend_pct": round(trend_pct * 100, 1),
                "volatility_level": volatility_level,
                "volatility_ratio": round(vol_ratio, 2),
                "rsi_value": round(rsi_value, 1),
                "support": round(support, 2) if support else None,
                "resistance": round(resistance, 2) if resistance else None,
                "recommendation": recommendation,
            }
        except Exception as e:
            logger.error(f"Regime detection error: {e}")
            return {
                "regime": "unknown",
                "trend_strength": 0.0,
                "trend_pct": 0.0,
                "volatility_level": "unknown",
                "volatility_ratio": 1.0,
                "rsi_value": 50.0,
                "support": None,
                "resistance": None,
                "recommendation": "Error during calculation",
            }

    def get_adaptive_thresholds(self, regime_info: Dict[str, Any], base_entry: float = 55.0) -> Dict[str, float]:
        """Get regime-aware entry and exit thresholds."""
        regime = regime_info.get("regime", "sideways")
        vol_level = regime_info.get("volatility_level", "medium")
        rsi = regime_info.get("rsi_value", 50.0)

        thresholds = {
            "entry_threshold": base_entry,
            "profit_target": 0.05,
            "stop_loss": 0.02,
            "position_size_adjustment": 1.0,
        }

        regime_adjustments = {
            "bull": {"entry_threshold": base_entry - 5, "profit_target": 0.08, "stop_loss": 0.03, "position_size_adjustment": 1.2},
            "bear": {"entry_threshold": base_entry + 10, "profit_target": 0.03, "stop_loss": 0.015, "position_size_adjustment": 0.6},
            "sideways": {"entry_threshold": base_entry, "profit_target": 0.04, "stop_loss": 0.02, "position_size_adjustment": 1.0},
            "volatile": {"entry_threshold": base_entry + 5, "profit_target": 0.06, "stop_loss": 0.025, "position_size_adjustment": 0.7},
        }

        regime_adj = regime_adjustments.get(regime, {})
        for key, value in regime_adj.items():
            thresholds[key] = value

        vol_adjustments = {"low": 1.1, "medium": 1.0, "high": 0.85, "extreme": 0.7}
        vol_mult = vol_adjustments.get(vol_level, 1.0)
        thresholds["position_size_adjustment"] *= vol_mult

        if rsi > 75:
            thresholds["entry_threshold"] += 2
            thresholds["position_size_adjustment"] *= 0.8
        elif rsi < 25:
            thresholds["entry_threshold"] -= 2
            thresholds["position_size_adjustment"] *= 1.2

        thresholds["entry_threshold"] = max(40, min(80, thresholds["entry_threshold"]))
        thresholds["position_size_adjustment"] = max(0.5, min(1.5, thresholds["position_size_adjustment"]))

        return {
            "entry_threshold": round(thresholds["entry_threshold"], 1),
            "profit_target": round(thresholds["profit_target"], 4),
            "stop_loss": round(thresholds["stop_loss"], 4),
            "position_size_adjustment": round(thresholds["position_size_adjustment"], 2),
            "regime": regime,
            "vol_level": vol_level,
        }

    def _calculate_rsi(self, closes: pd.Series, window: int = 14) -> float:
        """Calculate RSI."""
        if len(closes) < window:
            return 50.0
        try:
            delta = closes.diff()
            gain = delta.where(delta > 0, 0).rolling(window=window).mean()
            loss = -delta.where(delta < 0, 0).rolling(window=window).mean()
            # Ensure index alignment before division
            gain = gain.fillna(0)
            loss = loss.fillna(0)
            rs = gain / loss.where(loss != 0, 0.0001)
            rsi = 100 - (100 / (1 + rs.where(rs > 0, 0.0001)))
            return float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50.0
        except Exception as e:
            logger.debug(f"RSI calculation failed: {e}")
            return 50.0

    def _calculate_support_resistance(self, df: pd.DataFrame, window: int = 20) -> Tuple[float, float]:
        """Calculate support and resistance levels."""
        if len(df) < window:
            return None, None
        recent = df["Close"].iloc[-window:]
        support = float(recent.min())
        resistance = float(recent.max())
        return support, resistance

    def get_regime_summary(self, regime_info: Dict[str, Any]) -> str:
        """Get human-readable regime summary."""
        regime = regime_info.get("regime", "unknown")
        trend = regime_info.get("trend_pct", 0)
        vol = regime_info.get("volatility_level", "unknown")
        rsi = regime_info.get("rsi_value", 50)
        summary = f"{regime.upper()} market | Trend: {trend:+.1f}% | Vol: {vol} | RSI: {rsi:.0f}"
        return summary


_regime_detector: RegimeDetector = None


def init_regime_detector() -> None:
    """Initialize regime detector (no-op, detector is lazily initialized)."""
    global _regime_detector
    if _regime_detector is None:
        _regime_detector = RegimeDetector()


def get_regime_detector() -> RegimeDetector:
    """Get or create regime detector instance."""
    global _regime_detector
    if _regime_detector is None:
        _regime_detector = RegimeDetector()
    return _regime_detector
