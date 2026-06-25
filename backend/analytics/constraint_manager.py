"""
Phase 326: Constraint Manager

Manage multiple constraint types for portfolio allocation optimization.
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ConstraintSpec:
    """Portfolio constraint specification."""

    constraint_type: str  # "sector", "concentration", "min_position", "max_position", "asset_class"
    target: str  # sector name, "all", etc.
    min_value: Optional[float] = None  # For min position
    max_value: Optional[float] = None  # For max position/sector


@dataclass
class SectorAssignment:
    """Symbol to sector mapping."""

    symbol: str
    sector: str
    weight_pct: float = 0.0


class ConstraintManager:
    """Manage portfolio constraints."""

    def __init__(self):
        """Initialize constraint manager."""
        self.constraints: List[ConstraintSpec] = []
        self.sector_map: Dict[str, str] = {}  # symbol -> sector
        self.asset_class_map: Dict[str, str] = {}  # symbol -> asset class

    def add_sector_limit(self, sector: str, max_weight_pct: float) -> None:
        """
        Add sector exposure limit.

        Parameters:
        -----------
        sector : str
            Sector name (e.g., "Technology", "Healthcare")
        max_weight_pct : float
            Maximum sector weight (%)
        """
        constraint = ConstraintSpec(
            constraint_type="sector",
            target=sector,
            max_value=max_weight_pct,
        )
        self.constraints.append(constraint)
        logger.info(f"Added sector constraint: {sector} max {max_weight_pct}%")

    def add_concentration_limit(self, max_single_position_pct: float) -> None:
        """
        Add concentration limit (single position max).

        Parameters:
        -----------
        max_single_position_pct : float
            Maximum position size (%)
        """
        constraint = ConstraintSpec(
            constraint_type="concentration",
            target="all",
            max_value=max_single_position_pct,
        )
        self.constraints.append(constraint)
        logger.info(f"Added concentration limit: {max_single_position_pct}%")

    def add_position_bounds(self, symbol: str, min_pct: float, max_pct: float) -> None:
        """
        Add min/max bounds for a specific position.

        Parameters:
        -----------
        symbol : str
            Symbol to constrain
        min_pct : float
            Minimum position weight (%)
        max_pct : float
            Maximum position weight (%)
        """
        min_constraint = ConstraintSpec(
            constraint_type="min_position",
            target=symbol,
            min_value=min_pct,
        )
        max_constraint = ConstraintSpec(
            constraint_type="max_position",
            target=symbol,
            max_value=max_pct,
        )
        self.constraints.append(min_constraint)
        self.constraints.append(max_constraint)
        logger.info(f"Added position bounds for {symbol}: {min_pct}% - {max_pct}%")

    def add_asset_class_limit(self, asset_class: str, max_weight_pct: float) -> None:
        """
        Add asset class exposure limit.

        Parameters:
        -----------
        asset_class : str
            Asset class (e.g., "crypto", "equities", "bonds")
        max_weight_pct : float
            Maximum exposure (%)
        """
        constraint = ConstraintSpec(
            constraint_type="asset_class",
            target=asset_class,
            max_value=max_weight_pct,
        )
        self.constraints.append(constraint)
        logger.info(f"Added asset class limit: {asset_class} max {max_weight_pct}%")

    def set_sector_map(self, sector_map: Dict[str, str]) -> None:
        """
        Set symbol to sector mapping.

        Parameters:
        -----------
        sector_map : dict
            {symbol: sector}
        """
        self.sector_map = sector_map
        logger.info(f"Set sector map for {len(sector_map)} symbols")

    def set_asset_class_map(self, asset_class_map: Dict[str, str]) -> None:
        """
        Set symbol to asset class mapping.

        Parameters:
        -----------
        asset_class_map : dict
            {symbol: asset_class}
        """
        self.asset_class_map = asset_class_map
        logger.info(f"Set asset class map for {len(asset_class_map)} symbols")

    def validate_allocation(
        self, allocation: Dict[str, float]
    ) -> Tuple[bool, List[str]]:
        """
        Validate allocation against constraints.

        Parameters:
        -----------
        allocation : dict
            {symbol: weight %}

        Returns:
        --------
        (is_valid, list of violation descriptions)
        """
        violations = []

        # Check sum = 100%
        total = sum(allocation.values())
        if abs(total - 100.0) > 0.1:
            violations.append(f"Portfolio sum {total:.1f}% != 100%")

        for constraint in self.constraints:
            if constraint.constraint_type == "concentration":
                # Check no single position exceeds limit
                for symbol, weight in allocation.items():
                    if weight > constraint.max_value:
                        violations.append(
                            f"{symbol} {weight:.1f}% exceeds concentration limit {constraint.max_value}%"
                        )

            elif constraint.constraint_type == "sector":
                # Check sector exposure
                sector_weight = 0.0
                for symbol, weight in allocation.items():
                    if self.sector_map.get(symbol) == constraint.target:
                        sector_weight += weight

                if sector_weight > constraint.max_value:
                    violations.append(
                        f"Sector {constraint.target} {sector_weight:.1f}% exceeds limit {constraint.max_value}%"
                    )

            elif constraint.constraint_type == "asset_class":
                # Check asset class exposure
                ac_weight = 0.0
                for symbol, weight in allocation.items():
                    if self.asset_class_map.get(symbol) == constraint.target:
                        ac_weight += weight

                if ac_weight > constraint.max_value:
                    violations.append(
                        f"Asset class {constraint.target} {ac_weight:.1f}% exceeds limit {constraint.max_value}%"
                    )

            elif constraint.constraint_type == "min_position":
                # Check minimum position
                weight = allocation.get(constraint.target, 0.0)
                if weight > 0 and weight < constraint.min_value:
                    violations.append(
                        f"{constraint.target} {weight:.1f}% below minimum {constraint.min_value}%"
                    )

            elif constraint.constraint_type == "max_position":
                # Check maximum position
                weight = allocation.get(constraint.target, 0.0)
                if weight > constraint.max_value:
                    violations.append(
                        f"{constraint.target} {weight:.1f}% exceeds maximum {constraint.max_value}%"
                    )

        return len(violations) == 0, violations

    def get_scipy_constraints(self, symbols: List[str]) -> List[Dict]:
        """
        Convert to scipy constraint format for optimizer.

        Parameters:
        -----------
        symbols : list
            List of symbols in optimization

        Returns:
        --------
        List of scipy constraint dicts
        """
        scipy_constraints = []

        # Sum to 1 (100%)
        scipy_constraints.append(
            {
                "type": "eq",
                "fun": lambda w: np.sum(w) - 1.0,
            }
        )

        for constraint in self.constraints:
            if constraint.constraint_type == "concentration":
                # Each weight <= max
                scipy_constraints.append(
                    {
                        "type": "ineq",
                        "fun": lambda w: constraint.max_value / 100 - np.max(w),
                    }
                )

            elif constraint.constraint_type == "sector":
                # Sector weight <= max
                def sector_constraint(w, constraint=constraint, symbols=symbols):
                    sector_weight = 0.0
                    for i, symbol in enumerate(symbols):
                        if self.sector_map.get(symbol) == constraint.target:
                            sector_weight += w[i]
                    return constraint.max_value / 100 - sector_weight

                scipy_constraints.append(
                    {
                        "type": "ineq",
                        "fun": sector_constraint,
                    }
                )

            elif constraint.constraint_type == "asset_class":
                # Asset class weight <= max
                def ac_constraint(w, constraint=constraint, symbols=symbols):
                    ac_weight = 0.0
                    for i, symbol in enumerate(symbols):
                        if self.asset_class_map.get(symbol) == constraint.target:
                            ac_weight += w[i]
                    return constraint.max_value / 100 - ac_weight

                scipy_constraints.append(
                    {
                        "type": "ineq",
                        "fun": ac_constraint,
                    }
                )

            elif constraint.constraint_type == "min_position":
                # Position >= min (if held)
                idx = (
                    symbols.index(constraint.target)
                    if constraint.target in symbols
                    else -1
                )
                if idx >= 0:

                    def min_constraint(w, idx=idx, min_val=constraint.min_value):
                        if w[idx] > 0:
                            return w[idx] - min_val / 100
                        return 0.1  # Allow zero

                    scipy_constraints.append(
                        {
                            "type": "ineq",
                            "fun": min_constraint,
                        }
                    )

            elif constraint.constraint_type == "max_position":
                # Position <= max
                idx = (
                    symbols.index(constraint.target)
                    if constraint.target in symbols
                    else -1
                )
                if idx >= 0:

                    def max_constraint(w, idx=idx, max_val=constraint.max_value):
                        return max_val / 100 - w[idx]

                    scipy_constraints.append(
                        {
                            "type": "ineq",
                            "fun": max_constraint,
                        }
                    )

        return scipy_constraints

    def get_bounds(
        self, symbols: List[str], default_max_pct: float = 25.0
    ) -> List[Tuple[float, float]]:
        """
        Get weight bounds for each symbol.

        Parameters:
        -----------
        symbols : list
            List of symbols
        default_max_pct : float
            Default max position if not constrained

        Returns:
        --------
        List of (min, max) tuples for each symbol
        """
        bounds = []

        for symbol in symbols:
            min_bound = 0.0
            max_bound = default_max_pct / 100

            # Check for explicit min/max constraints
            for constraint in self.constraints:
                if (
                    constraint.constraint_type == "min_position"
                    and constraint.target == symbol
                ):
                    min_bound = max(min_bound, constraint.min_value / 100)
                elif (
                    constraint.constraint_type == "max_position"
                    and constraint.target == symbol
                ):
                    max_bound = min(max_bound, constraint.max_value / 100)

            bounds.append((min_bound, max_bound))

        return bounds

    def clear_constraints(self) -> None:
        """Clear all constraints."""
        self.constraints = []
        logger.info("Cleared all constraints")


# Global instance
_constraint_manager: ConstraintManager = None


def get_constraint_manager() -> ConstraintManager:
    """Get or create constraint manager."""
    global _constraint_manager
    if _constraint_manager is None:
        _constraint_manager = ConstraintManager()
    return _constraint_manager
