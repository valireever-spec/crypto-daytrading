"""
Phase 314: Volatility-Based Position Sizing & Dynamic Stops

Calculates position size via volatility-adjusted Kelly Criterion
and ATR-based stop-loss levels.
"""

import math
import pandas as pd
import logging
from typing import Dict, Tuple, Any

logger = logging.getLogger(__name__)


class VolatilityManager:
    """Manage position sizing and stops based on realized volatility."""

    def __init__(
        self,
        lookback_vol: int = 20,  # Rolling window for volatility calc
        lookback_atr: int = 14,  # ATR lookback window
        risk_per_trade: float = 0.02,  # 2% max loss per trade
        kelly_fraction: float = 0.25,  # Kelly fraction (conservative)
    ):
        """
        Initialize volatility manager.

        Parameters:
        -----------
        lookback_vol : int
            Days for rolling volatility calculation
        lookback_atr : int
            Days for ATR calculation
        risk_per_trade : float
            Maximum acceptable loss per trade (0.02 = 2%)
        kelly_fraction : float
            Fraction of Kelly criterion to use (0.25 = 25% Kelly, conservative)
        """
        self.lookback_vol = lookback_vol
        self.lookback_atr = lookback_atr
        self.risk_per_trade = risk_per_trade
        self.kelly_fraction = kelly_fraction

    def calculate_volatility(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Calculate realized volatility metrics.

        Parameters:
        -----------
        df : pd.DataFrame
            OHLCV DataFrame with Close prices

        Returns:
        --------
        dict with:
          - vol_20d: rolling 20-day annualized volatility (%)
          - current_vol: most recent volatility
          - vol_percentile: where current vol sits in history (0-100)
          - regime: "low" | "medium" | "high" | "extreme"
          - trend: "expanding" | "contracting" | "stable"
        """
        if df.empty or len(df) < self.lookback_vol:
            return {
                "vol_20d": None,
                "current_vol": None,
                "vol_percentile": 50.0,
                "regime": "unknown",
                "trend": "stable",
            }

        closes = df["Close"]
        returns = closes.pct_change().dropna()

        # Rolling annualized volatility (252 trading days)
        vol_20 = returns.rolling(self.lookback_vol).std() * math.sqrt(252) * 100

        if len(vol_20.dropna()) == 0:
            return {
                "vol_20d": None,
                "current_vol": None,
                "vol_percentile": 50.0,
                "regime": "unknown",
                "trend": "stable",
            }

        current_vol = float(vol_20.iloc[-1])

        # Percentile rank
        vol_history = vol_20.dropna()
        if len(vol_history) >= 20:
            pct_rank = float((vol_history < current_vol).mean() * 100)
        else:
            pct_rank = 50.0

        # Regime classification
        if pct_rank >= 90:
            regime = "extreme"
        elif pct_rank >= 75:
            regime = "high"
        elif pct_rank >= 25:
            regime = "medium"
        else:
            regime = "low"

        # Trend: compare recent 5-day avg to prior 5 days
        if len(vol_20.dropna()) >= 10:
            recent_avg = float(vol_20.dropna().iloc[-5:].mean())
            prior_avg = float(vol_20.dropna().iloc[-10:-5].mean())
            trend_pct = (
                (recent_avg - prior_avg) / prior_avg * 100 if prior_avg > 0 else 0.0
            )
        else:
            trend_pct = 0.0

        if trend_pct > 5:
            trend = "expanding"
        elif trend_pct < -5:
            trend = "contracting"
        else:
            trend = "stable"

        return {
            "vol_20d": round(current_vol, 2),
            "current_vol": current_vol,
            "vol_percentile": round(pct_rank, 1),
            "regime": regime,
            "trend": trend,
            "trend_pct": round(trend_pct, 1),
        }

    def calculate_atr(self, df: pd.DataFrame) -> Tuple[float, float, float]:
        """
        Calculate Average True Range and stop-loss levels.

        Returns:
        --------
        (atr_value, stop_loss_pct, stop_loss_pips)
        """
        if df.empty or len(df) < self.lookback_atr:
            return 0.0, 0.02, 0.0

        high = df["High"]
        low = df["Low"]
        close = df["Close"]

        # True Range
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        # ATR
        atr = tr.rolling(self.lookback_atr).mean()
        atr_value = float(atr.iloc[-1]) if not atr.iloc[-1] != atr.iloc[-1] else 0.0

        current_price = float(close.iloc[-1])
        if current_price <= 0:
            return 0.0, 0.02, 0.0

        # Stop loss as % of price
        stop_loss_pct = atr_value / current_price
        stop_loss_pcts = float(min(stop_loss_pct, 0.10))  # Cap at 10%

        return atr_value, stop_loss_pcts, atr_value

    def calculate_position_size(
        self,
        account_equity: float,
        current_price: float,
        vol_metrics: Dict[str, Any],
        entry_signal_strength: float = 50.0,
    ) -> Dict[str, Any]:
        """
        Calculate position size using Kelly Criterion adjusted for volatility.

        Parameters:
        -----------
        account_equity : float
            Total account equity (€)
        current_price : float
            Current asset price
        vol_metrics : dict
            Output from calculate_volatility()
        entry_signal_strength : float
            Signal strength 0-100 (affects aggressiveness)

        Returns:
        --------
        dict with:
          - position_size_pct: % of account to risk (0.01-0.10)
          - position_quantity: number of units to buy
          - position_value_eur: EUR value of position
          - kelly_recommendation: raw Kelly % (before conservative adjustment)
          - vol_adjustment: multiplier applied for current regime
        """
        if current_price <= 0 or account_equity <= 0:
            return {
                "position_size_pct": 0.01,
                "position_quantity": 0,
                "position_value_eur": 0.0,
                "kelly_recommendation": 0.0,
                "vol_adjustment": 1.0,
                "reason": "Invalid price or equity",
            }

        current_vol = vol_metrics.get("current_vol", 0.05)
        regime = vol_metrics.get("regime", "medium")

        # Base Kelly Criterion: f* = (W*p - L*(1-p)) / W
        # Simplified assumption: 55% win rate, 2:1 reward:risk
        win_rate = 0.55
        reward_risk_ratio = 2.0

        # Kelly formula
        kelly_pct = (win_rate * reward_risk_ratio - (1 - win_rate)) / reward_risk_ratio
        kelly_pct = max(0.0, min(kelly_pct, 0.25))  # Clip 0-25%

        # Volatility adjustment (lower vol = more aggressive, higher vol = more conservative)
        baseline_vol = 0.30  # 30% annualized
        if current_vol > 0:
            vol_multiplier = baseline_vol / current_vol
        else:
            vol_multiplier = 1.0

        # Regime adjustment
        regime_multiplier = {
            "low": 1.2,  # Low vol: aggressive (120%)
            "medium": 1.0,  # Medium: normal (100%)
            "high": 0.7,  # High vol: conservative (70%)
            "extreme": 0.4,  # Extreme: very conservative (40%)
            "unknown": 1.0,
        }.get(regime, 1.0)

        # Signal strength adjustment (weak signals = smaller positions)
        signal_multiplier = 0.5 + (entry_signal_strength / 100.0) * 0.5
        signal_multiplier = max(0.5, min(signal_multiplier, 1.5))

        # Combine adjustments
        total_multiplier = vol_multiplier * regime_multiplier * signal_multiplier
        position_pct = kelly_pct * self.kelly_fraction * total_multiplier
        position_pct = max(0.01, min(position_pct, 0.10))  # Clip 1%-10%

        position_value = account_equity * position_pct
        quantity = position_value / current_price

        return {
            "position_size_pct": round(position_pct, 4),
            "position_quantity": round(quantity, 8),
            "position_value_eur": round(position_value, 2),
            "kelly_recommendation": round(kelly_pct, 4),
            "vol_adjustment": round(vol_multiplier, 2),
            "regime_adjustment": round(regime_multiplier, 2),
            "signal_adjustment": round(signal_multiplier, 2),
            "total_multiplier": round(total_multiplier, 2),
            "regime": regime,
            "reason": f"Vol={current_vol:.1f}% ({regime}), Signal={entry_signal_strength:.0f}, Kelly={kelly_pct*100:.1f}%",
        }

    def calculate_stops(
        self,
        entry_price: float,
        df: pd.DataFrame,
        atr_multiplier: float = 2.0,
    ) -> Dict[str, float]:
        """
        Calculate dynamic stop-loss and take-profit levels.

        Parameters:
        -----------
        entry_price : float
            Entry price (usually market price at time of order)
        df : pd.DataFrame
            OHLCV data
        atr_multiplier : float
            Multiplier for ATR (e.g., 2.0 = 2x ATR as stop)

        Returns:
        --------
        dict with stop-loss and take-profit levels
        """
        atr_value, _, _ = self.calculate_atr(df)

        if atr_value <= 0 or entry_price <= 0:
            return {
                "stop_loss_price": entry_price * 0.98,  # Fallback to 2%
                "stop_loss_pct": 0.02,
                "take_profit_price": entry_price * 1.05,  # 5% profit target
                "take_profit_pct": 0.05,
                "reason": "Using fallback stops (ATR not available)",
            }

        # ATR-based stop loss
        stop_distance = atr_value * atr_multiplier
        stop_loss_price = entry_price - stop_distance
        stop_loss_pct = stop_distance / entry_price

        # Take profit: 2-3x the stop distance (favorable risk:reward)
        profit_distance = stop_distance * 2.5
        take_profit_price = entry_price + profit_distance
        take_profit_pct = profit_distance / entry_price

        return {
            "stop_loss_price": round(stop_loss_price, 2),
            "stop_loss_pct": round(stop_loss_pct, 4),
            "take_profit_price": round(take_profit_price, 2),
            "take_profit_pct": round(take_profit_pct, 4),
            "atr_value": round(atr_value, 2),
            "reason": f"ATR={atr_value:.2f}, Stop={stop_loss_pct*100:.2f}%, TP={take_profit_pct*100:.2f}%",
        }


# Global instance
_vol_manager: VolatilityManager = None


def get_volatility_manager() -> VolatilityManager:
    """Get or create volatility manager instance."""
    global _vol_manager
    if _vol_manager is None:
        _vol_manager = VolatilityManager()
    return _vol_manager
