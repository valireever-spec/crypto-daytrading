"""
Phase 329: Cost Model Calibration

Learn symbol-specific cost patterns from actual execution data.
"""

import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime, timezone
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ExecutionRecord:
    """Single execution record."""
    symbol: str
    side: str  # BUY or SELL
    planned_cost_pct: float  # Estimated cost
    actual_cost_pct: float  # Realized cost (slippage + commission)
    volume_pct: float
    timestamp: str  # ISO format


@dataclass
class SymbolCostProfile:
    """Symbol-specific cost profile."""
    symbol: str
    execution_count: int
    avg_estimated_cost_pct: float
    avg_actual_cost_pct: float
    cost_estimation_error_pct: float  # How far off were we?
    volatility_sensitivity: float  # Cost vs volatility correlation
    volume_sensitivity: float  # Cost vs volume correlation
    suggested_tier: str


class CostModelCalibrator:
    """Learn and calibrate cost models from execution data."""

    def __init__(self):
        """Initialize calibrator."""
        self.executions: List[ExecutionRecord] = []
        self.last_update = datetime.now(timezone.utc).isoformat()

    def record_execution(
        self,
        symbol: str,
        side: str,
        planned_cost_pct: float,
        actual_cost_pct: float,
        volume_pct: float,
    ) -> ExecutionRecord:
        """
        Record execution for learning.

        Parameters:
        -----------
        symbol : str
            Trading symbol
        side : str
            "BUY" or "SELL"
        planned_cost_pct : float
            Estimated cost %
        actual_cost_pct : float
            Realized cost % (spread + slippage + commission)
        volume_pct : float
            Volume as % of portfolio

        Returns:
        --------
        ExecutionRecord
        """
        record = ExecutionRecord(
            symbol=symbol,
            side=side,
            planned_cost_pct=planned_cost_pct,
            actual_cost_pct=actual_cost_pct,
            volume_pct=volume_pct,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        self.executions.append(record)
        logger.info(
            f"Recorded execution {symbol}: planned {planned_cost_pct:.2f}% "
            f"vs actual {actual_cost_pct:.2f}%"
        )
        return record

    def get_symbol_profile(self, symbol: str) -> Optional[SymbolCostProfile]:
        """
        Get cost profile for symbol.

        Parameters:
        -----------
        symbol : str
            Trading symbol

        Returns:
        --------
        SymbolCostProfile or None if insufficient data
        """
        matching = [e for e in self.executions if e.symbol == symbol]

        if not matching or len(matching) < 3:
            return None

        # Calculate metrics
        avg_planned = np.mean([e.planned_cost_pct for e in matching])
        avg_actual = np.mean([e.actual_cost_pct for e in matching])

        estimation_error = abs(avg_actual - avg_planned) / max(avg_planned, 0.001) * 100

        # Volume sensitivity: correlation between volume and cost
        volumes = np.array([e.volume_pct for e in matching])
        actuals = np.array([e.actual_cost_pct for e in matching])

        if len(volumes) > 1 and volumes.std() > 0 and actuals.std() > 0:
            volume_sensitivity = np.corrcoef(volumes, actuals)[0, 1]
            # Guard against NaN from edge cases
            if np.isnan(volume_sensitivity) or np.isinf(volume_sensitivity):
                volume_sensitivity = 0.0
            else:
                volume_sensitivity = max(-1.0, min(1.0, volume_sensitivity))
        else:
            volume_sensitivity = 0.0

        # Suggest tier based on actual costs
        if avg_actual < 0.05:
            suggested_tier = "crypto_major"
        elif avg_actual < 0.15:
            suggested_tier = "equity_large_cap"
        elif avg_actual < 0.30:
            suggested_tier = "equity_mid_cap"
        else:
            suggested_tier = "equity_small_cap"

        return SymbolCostProfile(
            symbol=symbol,
            execution_count=len(matching),
            avg_estimated_cost_pct=round(avg_planned, 4),
            avg_actual_cost_pct=round(avg_actual, 4),
            cost_estimation_error_pct=round(estimation_error, 1),
            volatility_sensitivity=round(volume_sensitivity, 2),
            volume_sensitivity=round(volume_sensitivity, 2),
            suggested_tier=suggested_tier,
        )

    def get_all_profiles(self) -> Dict[str, SymbolCostProfile]:
        """Get profiles for all traded symbols."""
        symbols = set(e.symbol for e in self.executions)
        profiles = {}

        for symbol in symbols:
            profile = self.get_symbol_profile(symbol)
            if profile:
                profiles[symbol] = profile

        return profiles

    def identify_tier_mismatches(self) -> Dict[str, Dict]:
        """
        Identify symbols with cost tier mismatches.

        Returns:
        --------
        {symbol: {current_tier, suggested_tier, error_pct}}
        """
        profiles = self.get_all_profiles()
        mismatches = {}

        for symbol, profile in profiles.items():
            # This would be compared against the cost model's current tier
            # For now, just flag if error is significant (>50%)
            if profile.cost_estimation_error_pct > 50:
                mismatches[symbol] = {
                    "execution_count": profile.execution_count,
                    "suggested_tier": profile.suggested_tier,
                    "error_pct": profile.cost_estimation_error_pct,
                    "avg_actual_cost": profile.avg_actual_cost_pct,
                }

        return mismatches

    def estimate_total_portfolio_cost(
        self,
        planned_trades: List[Dict],  # [{symbol, volume_pct}]
    ) -> Dict:
        """
        Estimate total portfolio cost using learned profiles.

        Parameters:
        -----------
        planned_trades : list
            List of {symbol, volume_pct}

        Returns:
        --------
        {symbol: cost%, total: cost%}
        """
        costs_by_symbol = {}
        total_cost = 0.0

        for trade in planned_trades:
            symbol = trade["symbol"]
            volume = trade["volume_pct"]

            profile = self.get_symbol_profile(symbol)

            if profile:
                # Use historical average as estimate
                estimated_cost = profile.avg_actual_cost_pct
            else:
                # Fallback: assume 0.2% for unknown symbols
                estimated_cost = 0.2

            costs_by_symbol[symbol] = round(estimated_cost, 4)
            total_cost += estimated_cost

        return {
            "costs_by_symbol": costs_by_symbol,
            "total_portfolio_cost_pct": round(total_cost, 4),
            "num_learned_symbols": len(self.get_all_profiles()),
        }

    def get_calibration_status(self) -> Dict:
        """Get calibration status."""
        profiles = self.get_all_profiles()
        mismatches = self.identify_tier_mismatches()

        return {
            "total_executions_recorded": len(self.executions),
            "symbols_with_profiles": len(profiles),
            "tier_mismatches_identified": len(mismatches),
            "mismatches": mismatches,
            "last_update": self.last_update,
            "readiness": "ready" if len(profiles) >= 5 else "learning",
        }


# Global instance
_calibrator: CostModelCalibrator = None


def get_cost_model_calibrator() -> CostModelCalibrator:
    """Get or create cost model calibrator."""
    global _calibrator
    if _calibrator is None:
        _calibrator = CostModelCalibrator()
    return _calibrator


def get_learned_costs_for_trade(symbol: str, volume_pct: float) -> Optional[Dict[str, float]]:
    """
    Get learned cost estimate for a trade.

    For use in Phase 325-327 when making allocation decisions.

    Parameters:
    -----------
    symbol : str
        Trading symbol
    volume_pct : float
        Volume as % of portfolio

    Returns:
    --------
    {execution_cost, slippage_cost, total_cost} or None if not enough data
    """
    calibrator = get_cost_model_calibrator()
    profile = calibrator.get_symbol_profile(symbol)

    if profile:
        # Use historical average as estimate
        return {
            "execution_cost_pct": profile.avg_actual_cost_pct * 0.6,
            "slippage_cost_pct": profile.avg_actual_cost_pct * 0.4,
            "total_cost_pct": profile.avg_actual_cost_pct,
            "confidence": "learned",
            "samples": profile.execution_count,
        }
    else:
        # Return None to trigger fallback to static tier
        return None
