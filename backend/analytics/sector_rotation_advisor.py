"""
Phase 317: Sector Rotation Advisor

Recommend sector shifts based on market regime and sector-level signals.
Implements automated sector rotation strategy.
"""

import logging
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class SectorRotationRecommendation:
    """Recommendation to rotate between sectors."""
    from_sector: str
    to_sector: str
    confidence: float  # 0-1
    expected_outperformance: float  # Expected return difference (%)
    rationale: str
    action_symbols: Dict[str, str]  # symbol → action (BUY/SELL/HOLD)
    urgency: int  # 1-10


@dataclass
class SectorAllocationTarget:
    """Target allocation for a sector given current regime."""
    sector: str
    target_pct: float  # 0-100
    current_pct: float
    drift: float  # current - target
    action: str  # INCREASE/DECREASE/HOLD
    rationale: str


class SectorRotationAdvisor:
    """Recommend sector allocations based on market regime."""

    def __init__(self):
        """Initialize sector rotation advisor."""
        # Symbol to sector mapping (can be extended)
        self.symbol_sectors = {
            # Crypto
            'BTCUSDT': 'cryptocurrency',
            'ETHUSDT': 'cryptocurrency',
            'BNBUSDT': 'cryptocurrency',

            # Technology
            'EQ_AAPL': 'technology',
            'EQ_MSFT': 'technology',
            'EQ_NVDA': 'technology',
            'EQ_TSLA': 'technology',

            # Healthcare
            'EQ_JNJ': 'healthcare',
            'EQ_UNH': 'healthcare',

            # Finance
            'EQ_JPM': 'finance',
            'EQ_BAC': 'finance',

            # Energy
            'EQ_XOM': 'energy',
            'EQ_CVX': 'energy',

            # Utilities
            'EQ_NEE': 'utilities',
            'EQ_DUK': 'utilities',

            # Consumer
            'EQ_AMZN': 'consumer',
            'EQ_WMT': 'consumer',
        }

        # Regime-based sector allocations (target %)
        self.regime_allocations = {
            "bull": {
                "technology": 30,      # Overweight growth
                "cryptocurrency": 15,   # Overweight risk assets
                "consumer": 20,
                "finance": 15,
                "healthcare": 10,
                "energy": 5,
                "utilities": 5,
            },
            "sideways": {
                "technology": 20,      # Balanced
                "cryptocurrency": 10,
                "consumer": 20,
                "finance": 20,
                "healthcare": 15,
                "energy": 10,
                "utilities": 5,
            },
            "bear": {
                "technology": 10,      # Underweight risk
                "cryptocurrency": 5,
                "consumer": 10,
                "finance": 15,
                "healthcare": 25,      # Overweight defensive
                "energy": 15,
                "utilities": 20,       # Overweight defensive
            },
            "volatile": {
                "technology": 15,      # Reduce risk
                "cryptocurrency": 5,
                "consumer": 15,
                "finance": 15,
                "healthcare": 25,
                "energy": 12,
                "utilities": 13,
            },
        }

        # Sector performance history for momentum
        self.sector_momentum = {}  # sector → recent return (%)

    def get_sector_rotation_recommendation(
        self,
        portfolio_regime: str,  # bull/bear/sideways/volatile
        current_allocation: Dict[str, float],  # sector → % (0-100)
        symbol_regimes: Dict[str, Any],  # symbol → regime_info
        symbol_prices: Dict[str, float],  # For momentum calculation
    ) -> Optional[SectorRotationRecommendation]:
        """
        Get sector rotation recommendation based on regime.

        Parameters:
        -----------
        portfolio_regime : str
            Portfolio-level regime (bull/bear/mixed/volatile)
        current_allocation : dict
            Current sector allocation percentages
        symbol_regimes : dict
            Regime info for each symbol
        symbol_prices : dict
            Current prices for momentum calculation

        Returns:
        --------
        SectorRotationRecommendation or None if no rotation needed
        """
        if portfolio_regime not in self.regime_allocations:
            return None

        target_allocation = self.regime_allocations[portfolio_regime]

        # Find largest drift between current and target
        max_drift = 0
        from_sector = None
        to_sector = None

        for sector in target_allocation.keys():
            current = current_allocation.get(sector, 0)
            target = target_allocation[sector]
            drift = current - target

            # Find overweight sector (from_sector) and underweight sector (to_sector)
            if drift > max_drift:
                max_drift = drift
                from_sector = sector

            if -drift > max_drift:
                max_drift = -drift
                to_sector = sector

        # Only recommend rotation if drift is significant (>10%)
        if max_drift < 10:
            return None

        # Calculate confidence based on sector-level regime strength
        confidence = self._calculate_rotation_confidence(
            from_sector, to_sector, symbol_regimes
        )

        # Calculate expected outperformance
        expected_outperformance = self._calculate_expected_outperformance(
            from_sector, to_sector
        )

        # Generate action symbols
        action_symbols = self._generate_action_symbols(
            from_sector, to_sector, symbol_regimes
        )

        return SectorRotationRecommendation(
            from_sector=from_sector,
            to_sector=to_sector,
            confidence=confidence,
            expected_outperformance=expected_outperformance,
            rationale=f"Rotate from {from_sector} (overweight) to {to_sector} "
                     f"(underweight) for {portfolio_regime} market",
            action_symbols=action_symbols,
            urgency=min(int(max_drift / 5), 10),  # 1-10 scale
        )

    def get_sector_allocation_targets(
        self,
        portfolio_regime: str,
        current_allocation: Dict[str, float],
    ) -> List[SectorAllocationTarget]:
        """
        Get target sector allocations for current regime.

        Returns list of allocation targets with drift analysis.
        """
        if portfolio_regime not in self.regime_allocations:
            return []

        target_allocation = self.regime_allocations[portfolio_regime]
        targets = []

        for sector, target_pct in target_allocation.items():
            current_pct = current_allocation.get(sector, 0)
            drift = current_pct - target_pct

            if drift > 2:
                action = "DECREASE"
                rationale = f"Overweight in {sector}, reduce to {target_pct}%"
            elif drift < -2:
                action = "INCREASE"
                rationale = f"Underweight in {sector}, increase to {target_pct}%"
            else:
                action = "HOLD"
                rationale = f"Allocation in line with {portfolio_regime} target"

            targets.append(SectorAllocationTarget(
                sector=sector,
                target_pct=target_pct,
                current_pct=current_pct,
                drift=drift,
                action=action,
                rationale=rationale,
            ))

        return targets

    def _calculate_rotation_confidence(
        self,
        from_sector: str,
        to_sector: str,
        symbol_regimes: Dict[str, Any],
    ) -> float:
        """
        Calculate confidence in rotation based on sector-level regime strength.

        Higher confidence if:
          - From sector is consistently in bear/volatile
          - To sector is consistently in bull
        """
        from_regimes = [
            r.get("regime") for s, r in symbol_regimes.items()
            if self.symbol_sectors.get(s) == from_sector
        ]
        to_regimes = [
            r.get("regime") for s, r in symbol_regimes.items()
            if self.symbol_sectors.get(s) == to_sector
        ]

        if not from_regimes or not to_regimes:
            return 0.5

        # Strength of divergence
        from_bear_ratio = sum(1 for r in from_regimes if r in ["bear", "volatile"]) / len(from_regimes)
        to_bull_ratio = sum(1 for r in to_regimes if r in ["bull", "sideways"]) / len(to_regimes)

        confidence = (from_bear_ratio + to_bull_ratio) / 2
        return min(confidence, 1.0)

    def _calculate_expected_outperformance(
        self,
        from_sector: str,
        to_sector: str,
    ) -> float:
        """
        Estimate expected outperformance from rotation.

        Returns percentage point difference in expected returns.
        """
        # Base outperformance estimates (simplified)
        outperformance_matrix = {
            ("cryptocurrency", "utilities"): 8.0,
            ("technology", "healthcare"): 6.0,
            ("energy", "technology"): 5.0,
            ("cryptocurrency", "healthcare"): 10.0,
            ("consumer", "utilities"): 4.0,
        }

        # Check both directions
        key1 = (from_sector, to_sector)
        key2 = (to_sector, from_sector)

        if key1 in outperformance_matrix:
            return outperformance_matrix[key1]
        elif key2 in outperformance_matrix:
            return -outperformance_matrix[key2]
        else:
            # Default estimate based on historical patterns
            return 3.0

    def _generate_action_symbols(
        self,
        from_sector: str,
        to_sector: str,
        symbol_regimes: Dict[str, Any],
    ) -> Dict[str, str]:
        """Generate SELL/BUY actions for specific symbols in rotation."""
        actions = {}

        # SELL: symbols in from_sector that are weak
        for symbol, sector in self.symbol_sectors.items():
            if sector == from_sector:
                regime = symbol_regimes.get(symbol, {}).get("regime", "unknown")
                if regime in ["bear", "volatile"]:
                    actions[symbol] = "SELL"
                else:
                    actions[symbol] = "REDUCE"

            # BUY: symbols in to_sector that are strong
            elif sector == to_sector:
                regime = symbol_regimes.get(symbol, {}).get("regime", "unknown")
                if regime in ["bull"]:
                    actions[symbol] = "BUY"
                else:
                    actions[symbol] = "HOLD"

        return actions

    def get_sector_momentum(
        self,
        symbol_prices: Dict[str, float],
        price_history: Dict[str, List[float]],  # symbol → [prices]
    ) -> Dict[str, float]:
        """
        Calculate momentum for each sector.

        Returns dict of {sector: momentum} where momentum is % change.
        """
        sector_momentum = {}

        for symbol, sector in self.symbol_sectors.items():
            if symbol not in price_history or len(price_history[symbol]) < 2:
                continue

            prices = price_history[symbol]
            momentum = ((prices[-1] - prices[0]) / prices[0]) * 100

            if sector not in sector_momentum:
                sector_momentum[sector] = []

            sector_momentum[sector].append(momentum)

        # Average momentum per sector
        result = {}
        for sector, momentums in sector_momentum.items():
            result[sector] = sum(momentums) / len(momentums) if momentums else 0

        return result

    def should_increase_sector_exposure(
        self,
        sector: str,
        current_allocation: Dict[str, float],
        portfolio_regime: str,
    ) -> bool:
        """Check if portfolio should increase exposure to a sector."""
        if portfolio_regime not in self.regime_allocations:
            return False

        target = self.regime_allocations[portfolio_regime].get(sector, 0)
        current = current_allocation.get(sector, 0)

        # Increase if underweight by >5%
        return (target - current) > 5

    def should_decrease_sector_exposure(
        self,
        sector: str,
        current_allocation: Dict[str, float],
        portfolio_regime: str,
    ) -> bool:
        """Check if portfolio should decrease exposure to a sector."""
        if portfolio_regime not in self.regime_allocations:
            return False

        target = self.regime_allocations[portfolio_regime].get(sector, 0)
        current = current_allocation.get(sector, 0)

        # Decrease if overweight by >5%
        return (current - target) > 5

    def get_summary(self, portfolio_regime: str) -> str:
        """Get human-readable summary of sector allocation."""
        if portfolio_regime not in self.regime_allocations:
            return f"📊 Unknown regime: {portfolio_regime}"

        allocations = self.regime_allocations[portfolio_regime]
        summary = f"📊 {portfolio_regime.upper()} regime sector targets:\n"

        for sector, target in sorted(allocations.items(), key=lambda x: x[1], reverse=True)[:5]:
            summary += f"  • {sector}: {target}%\n"

        return summary


# Global instance
_sector_advisor: SectorRotationAdvisor = None


def get_sector_rotation_advisor() -> SectorRotationAdvisor:
    """Get or create sector rotation advisor instance."""
    global _sector_advisor
    if _sector_advisor is None:
        _sector_advisor = SectorRotationAdvisor()
    return _sector_advisor
