"""
Phase 317: Portfolio Regime Monitor

Track market regime per symbol, detect regime flips (bull→bear, bear→bull),
and generate correlated exit signals across portfolio.
"""

import logging
from typing import Dict, List, Tuple, Any
from datetime import datetime
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RegimeFlip:
    """Detected regime change for a symbol."""

    symbol: str
    from_regime: str
    to_regime: str
    severity: float  # 0-1, how big is the flip (bear→bull is high severity)
    timestamp: datetime
    should_exit: bool  # True if flipping to bear/volatile (exit recommended)


@dataclass
class PortfolioRegimeState:
    """Current regime state for entire portfolio."""

    timestamp: datetime
    symbol_regimes: Dict[str, str]  # symbol → regime name
    regime_flips: List[RegimeFlip]  # Detected changes this check
    portfolio_regime: str  # Bull/Bear/Mixed/Volatile (portfolio-level)
    exit_signals: List[str]  # Symbols to exit (regime flip triggered)
    entry_signals: List[str]  # Symbols to enter (favorable regime shift)
    allocation_adjustment: Dict[str, float]  # symbol → size multiplier


class PortfolioRegimeMonitor:
    """Monitor and coordinate regime-based trading decisions across portfolio."""

    def __init__(self):
        """Initialize portfolio regime monitor."""
        self.last_regime_state: Dict[str, str] = {}  # symbol → last regime
        self.regime_change_history: List[RegimeFlip] = []
        self.portfolio_regime_history: List[Tuple[datetime, str]] = []

    def check_portfolio_regime(
        self,
        symbol_regimes: Dict[str, Any],  # symbol → regime_info dict
        current_positions: List[str],  # Symbols currently held
    ) -> PortfolioRegimeState:
        """
        Check portfolio regime state and detect regime flips.

        Parameters:
        -----------
        symbol_regimes : dict
            Dict of {symbol: regime_info} where regime_info is output from
            RegimeDetector.detect_regime()
        current_positions : list
            List of symbols currently in portfolio

        Returns:
        --------
        PortfolioRegimeState with flips detected and exit signals generated
        """
        now = datetime.utcnow()
        flips: List[RegimeFlip] = []
        exit_signals: List[str] = []
        entry_signals: List[str] = []

        # Detect regime flips for each symbol
        for symbol, regime_info in symbol_regimes.items():
            current_regime = regime_info.get("regime", "unknown")
            previous_regime = self.last_regime_state.get(symbol)

            # Update state
            self.last_regime_state[symbol] = current_regime

            # Detect flip if we have previous state
            if previous_regime and previous_regime != current_regime:
                severity = self._calculate_flip_severity(
                    previous_regime, current_regime
                )
                flip = RegimeFlip(
                    symbol=symbol,
                    from_regime=previous_regime,
                    to_regime=current_regime,
                    severity=severity,
                    timestamp=now,
                    should_exit=current_regime in ["bear", "volatile"],
                )
                flips.append(flip)
                self.regime_change_history.append(flip)

                logger.info(
                    f"🔄 REGIME FLIP: {symbol} {previous_regime} → {current_regime} (severity: {severity:.2f})"
                )

                # Generate exit signal if flipping to bear/volatile
                if flip.should_exit and symbol in current_positions:
                    exit_signals.append(symbol)
                    logger.warning(
                        f"⚠️ EXIT SIGNAL: {symbol} flipped to {current_regime}, recommend closing position"
                    )

                # Generate entry signal if flipping to bull/sideways
                if (
                    current_regime in ["bull", "sideways"]
                    and symbol not in current_positions
                ):
                    entry_signals.append(symbol)
                    logger.info(
                        f"✅ ENTRY SIGNAL: {symbol} flipped to {current_regime}, favorable for entry"
                    )

        # Calculate portfolio-level regime
        portfolio_regime = self._calculate_portfolio_regime(symbol_regimes)

        # Determine position size adjustments per symbol
        allocation_adjustment = self._calculate_allocation_adjustments(
            symbol_regimes, current_positions
        )

        state = PortfolioRegimeState(
            timestamp=now,
            symbol_regimes={
                s: r.get("regime", "unknown") for s, r in symbol_regimes.items()
            },
            regime_flips=flips,
            portfolio_regime=portfolio_regime,
            exit_signals=exit_signals,
            entry_signals=entry_signals,
            allocation_adjustment=allocation_adjustment,
        )

        # Log portfolio-level regime
        logger.info(
            f"📊 Portfolio regime: {portfolio_regime} | "
            f"Exits: {len(exit_signals)} | Entries: {len(entry_signals)}"
        )

        return state

    def _calculate_flip_severity(self, from_regime: str, to_regime: str) -> float:
        """
        Calculate severity of regime flip (0-1, higher = more severe).

        Severity = how far the flip is on the risk spectrum:
          - bull → sideways = 0.3 (mild)
          - bull → volatile = 0.7 (moderate)
          - bull → bear = 1.0 (severe)
          - bear → bull = 1.0 (severe upside)
          - etc.
        """
        regime_risk_level = {
            "bull": 0,
            "sideways": 1,
            "volatile": 2,
            "bear": 3,
            "unknown": 2,
        }

        from_level = regime_risk_level.get(from_regime, 2)
        to_level = regime_risk_level.get(to_regime, 2)
        distance = abs(to_level - from_level)

        # Normalize to 0-1 scale (max distance is 3)
        return min(distance / 3.0, 1.0)

    def _calculate_portfolio_regime(self, symbol_regimes: Dict[str, Any]) -> str:
        """
        Calculate portfolio-level regime classification.

        Logic:
          - If >50% of positions are in bear/volatile → Bear
          - If >50% of positions are in bull → Bull
          - If >50% of positions are in sideways → Sideways
          - Otherwise → Mixed
        """
        if not symbol_regimes:
            return "unknown"

        regime_counts = {}
        for regime_info in symbol_regimes.values():
            regime = regime_info.get("regime", "unknown")
            regime_counts[regime] = regime_counts.get(regime, 0) + 1

        total = len(symbol_regimes)
        threshold = total * 0.5

        # Check dominant regime
        for regime, count in regime_counts.items():
            if count >= threshold:
                return regime

        # No dominant regime = mixed
        return "mixed"

    def _calculate_allocation_adjustments(
        self,
        symbol_regimes: Dict[str, Any],
        current_positions: List[str],
    ) -> Dict[str, float]:
        """
        Calculate position size adjustments based on regime.

        Returns dict of {symbol: multiplier} where:
          - Bull symbols: 1.2x (increase position)
          - Sideways symbols: 1.0x (neutral)
          - Volatile symbols: 0.7x (reduce position)
          - Bear symbols: 0.5x (reduce position significantly)
        """
        adjustments = {}

        for symbol, regime_info in symbol_regimes.items():
            regime = regime_info.get("regime", "unknown")

            # Only adjust existing positions
            if symbol in current_positions:
                if regime == "bull":
                    multiplier = 1.2
                elif regime == "sideways":
                    multiplier = 1.0
                elif regime == "volatile":
                    multiplier = 0.7
                elif regime == "bear":
                    multiplier = 0.5
                else:
                    multiplier = 1.0

                adjustments[symbol] = multiplier

        return adjustments

    def get_correlated_exits(
        self,
        current_positions: List[Dict],  # List of {symbol, quantity, entry_price}
        portfolio_value: float,
    ) -> List[Dict]:
        """
        Generate coordinated exit recommendations when regime flips.

        Returns list of {symbol, reason, urgency, expected_loss_if_stay}
        """
        exits = []

        for flip in self.regime_change_history[-10:]:  # Check recent flips
            if flip.should_exit and flip.symbol in [
                p["symbol"] for p in current_positions
            ]:
                pos = next(
                    (p for p in current_positions if p["symbol"] == flip.symbol), None
                )
                if pos:
                    exits.append(
                        {
                            "symbol": flip.symbol,
                            "reason": f"Regime flip: {flip.from_regime} → {flip.to_regime}",
                            "urgency": min(flip.severity * 10, 10),  # 0-10 scale
                            "detected_at": flip.timestamp,
                            "recommendation": "CLOSE"
                            if flip.severity > 0.7
                            else "REDUCE",
                        }
                    )

        return exits

    def detect_sector_rotation_opportunity(
        self,
        current_allocation: Dict[str, float],  # sector → % allocation
        symbol_sectors: Dict[str, str],  # symbol → sector mapping
        symbol_regimes: Dict[str, Any],
    ) -> Dict:
        """
        Detect if portfolio should rotate between sectors based on regime.

        Returns:
        --------
        {
            "should_rotate": bool,
            "from_sector": str,
            "to_sector": str,
            "confidence": float,  # 0-1
            "rationale": str,
        }
        """
        # Calculate sector-level regimes
        sector_regimes = self._calculate_sector_regimes(symbol_sectors, symbol_regimes)

        # Identify strong and weak sectors
        strong_sectors = [s for s, r in sector_regimes.items() if r == "bull"]
        weak_sectors = [s for s, r in sector_regimes.items() if r == "bear"]

        # Check if rotation is beneficial
        if strong_sectors and weak_sectors:
            # Find sectors we're currently overweight in weak areas
            overweight_weak = [
                s for s in weak_sectors if current_allocation.get(s, 0) > 0.15
            ]

            underweight_strong = [
                s for s in strong_sectors if current_allocation.get(s, 0) < 0.20
            ]

            if overweight_weak and underweight_strong:
                return {
                    "should_rotate": True,
                    "from_sector": overweight_weak[0],
                    "to_sector": underweight_strong[0],
                    "confidence": 0.8,
                    "rationale": f"Rotate from {overweight_weak[0]} (bear) to {underweight_strong[0]} (bull)",
                }

        return {
            "should_rotate": False,
            "from_sector": None,
            "to_sector": None,
            "confidence": 0.0,
            "rationale": "No rotation opportunity detected",
        }

    def _calculate_sector_regimes(
        self,
        symbol_sectors: Dict[str, str],
        symbol_regimes: Dict[str, Any],
    ) -> Dict[str, str]:
        """Calculate regime for each sector based on constituent symbols."""
        sector_regimes = {}

        for symbol, sector in symbol_sectors.items():
            regime_info = symbol_regimes.get(symbol, {})
            regime = regime_info.get("regime", "unknown")

            if sector not in sector_regimes:
                sector_regimes[sector] = []

            sector_regimes[sector].append(regime)

        # Determine sector regime (majority vote)
        result = {}
        for sector, regimes in sector_regimes.items():
            regime_counts = {}
            for r in regimes:
                regime_counts[r] = regime_counts.get(r, 0) + 1

            # Majority regime for sector
            dominant = max(regime_counts, key=regime_counts.get)
            result[sector] = dominant

        return result

    def get_portfolio_stress_level(
        self,
        symbol_regimes: Dict[str, Any],
    ) -> float:
        """
        Calculate portfolio stress level (0-1).

        High stress when:
          - Many symbols in bear/volatile
          - Recent rapid regime flips
          - Volatility elevated across board
        """
        bear_volatile_count = sum(
            1
            for r in symbol_regimes.values()
            if r.get("regime") in ["bear", "volatile"]
        )

        stress_from_regimes = (
            bear_volatile_count / len(symbol_regimes) if symbol_regimes else 0
        )

        # Add stress from recent flips
        recent_flips = [
            f
            for f in self.regime_change_history
            if (datetime.utcnow() - f.timestamp).total_seconds() < 86400
        ]
        stress_from_flips = min(
            len(recent_flips) / 5, 1.0
        )  # Max stress at 5+ flips/day

        # Combined stress level (weighted average)
        stress_level = (stress_from_regimes * 0.6) + (stress_from_flips * 0.4)

        return min(stress_level, 1.0)

    def get_summary(self) -> str:
        """Get human-readable summary of portfolio regime state."""
        if not self.regime_change_history:
            return "📊 No regime changes detected yet"

        recent_flips = self.regime_change_history[-5:]
        summary = "📊 Recent regime flips:\n"

        for flip in recent_flips:
            emoji = "⚠️" if flip.should_exit else "✅"
            summary += (
                f"  {emoji} {flip.symbol}: {flip.from_regime} → {flip.to_regime}\n"
            )

        return summary


# Global instance
_portfolio_monitor: PortfolioRegimeMonitor = None


def get_portfolio_regime_monitor() -> PortfolioRegimeMonitor:
    """Get or create portfolio regime monitor instance."""
    global _portfolio_monitor
    if _portfolio_monitor is None:
        _portfolio_monitor = PortfolioRegimeMonitor()
    return _portfolio_monitor
