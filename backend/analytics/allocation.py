"""Strategy allocation management with persistence (Phase 1 Week 2.5)."""

import json
import logging
from pathlib import Path
from typing import Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

ALLOCATION_FILE = Path("logs/allocation_config.json")

# Default allocations
DEFAULT_ALLOCATION = {
    "momentum": 40,
    "reversion": 35,
    "grid": 25,
}

TIME_PRESETS = {
    "morning": {"momentum": 50, "reversion": 30, "grid": 20},
    "afternoon": {"momentum": 30, "reversion": 40, "grid": 30},
    "evening": {"momentum": 40, "reversion": 35, "grid": 25},
}


@dataclass
class AllocationState:
    """Current allocation state."""

    momentum: float
    reversion: float
    grid: float
    preset: str = "custom"  # morning, afternoon, evening, or custom


class AllocationManager:
    """Manage strategy allocation preferences."""

    def __init__(self):
        """Initialize allocation manager."""
        self.current_allocation = DEFAULT_ALLOCATION.copy()
        self.preset = "evening"  # Default preset
        self._load_from_disk()

    def _ensure_dir(self) -> None:
        """Ensure logs directory exists."""
        ALLOCATION_FILE.parent.mkdir(parents=True, exist_ok=True)

    def _load_from_disk(self) -> None:
        """Load allocation from disk if exists."""
        self._ensure_dir()
        if ALLOCATION_FILE.exists():
            try:
                with open(ALLOCATION_FILE, "r") as f:
                    data = json.load(f)
                    self.current_allocation = {
                        "momentum": data.get(
                            "momentum", DEFAULT_ALLOCATION["momentum"]
                        ),
                        "reversion": data.get(
                            "reversion", DEFAULT_ALLOCATION["reversion"]
                        ),
                        "grid": data.get("grid", DEFAULT_ALLOCATION["grid"]),
                    }
                    self.preset = data.get("preset", "custom")
                    logger.info(
                        f"Loaded allocation from disk: {self.current_allocation}"
                    )
            except Exception as e:
                logger.error(f"Error loading allocation: {e}")
                self.current_allocation = DEFAULT_ALLOCATION.copy()

    def _save_to_disk(self) -> None:
        """Save allocation to disk."""
        self._ensure_dir()
        try:
            data = {
                **self.current_allocation,
                "preset": self.preset,
            }
            with open(ALLOCATION_FILE, "w") as f:
                json.dump(data, f, indent=2)
            logger.info(f"Saved allocation to disk: {data}")
        except Exception as e:
            logger.error(f"Error saving allocation: {e}")

    def set_allocation(
        self, momentum: float, reversion: float, grid: float, preset: str = "custom"
    ) -> Dict:
        """Set allocation and persist to disk.

        Args:
            momentum: Momentum strategy weight (0-100)
            reversion: Reversion strategy weight (0-100)
            grid: Grid trading weight (0-100)
            preset: Preset name (morning, afternoon, evening, custom)

        Returns:
            Updated allocation dict
        """
        # Validate percentages sum to 100
        total = momentum + reversion + grid
        if total != 100:
            raise ValueError(f"Allocation must sum to 100, got {total}")

        self.current_allocation = {
            "momentum": momentum,
            "reversion": reversion,
            "grid": grid,
        }
        self.preset = preset
        self._save_to_disk()
        return self.current_allocation

    def set_preset(self, preset: str) -> Dict:
        """Apply a time-based preset.

        Args:
            preset: Preset name (morning, afternoon, evening)

        Returns:
            Updated allocation dict

        Raises:
            ValueError: If preset not found
        """
        if preset not in TIME_PRESETS:
            raise ValueError(f"Unknown preset: {preset}")

        allocation = TIME_PRESETS[preset]
        return self.set_allocation(
            momentum=allocation["momentum"],
            reversion=allocation["reversion"],
            grid=allocation["grid"],
            preset=preset,
        )

    def get_allocation(self) -> AllocationState:
        """Get current allocation state.

        Returns:
            AllocationState with current weights
        """
        return AllocationState(
            momentum=self.current_allocation["momentum"],
            reversion=self.current_allocation["reversion"],
            grid=self.current_allocation["grid"],
            preset=self.preset,
        )

    def get_allocation_dict(self) -> Dict:
        """Get allocation as dictionary.

        Returns:
            Dict with momentum, reversion, grid weights
        """
        return self.current_allocation.copy()

    def reset_to_default(self) -> Dict:
        """Reset allocation to defaults.

        Returns:
            Default allocation dict
        """
        return self.set_allocation(
            momentum=DEFAULT_ALLOCATION["momentum"],
            reversion=DEFAULT_ALLOCATION["reversion"],
            grid=DEFAULT_ALLOCATION["grid"],
            preset="evening",
        )

    def get_presets(self) -> Dict[str, Dict]:
        """Get all available presets.

        Returns:
            Dict of preset name -> allocation weights
        """
        return TIME_PRESETS.copy()

    def apply_to_signal(
        self, rsi_score: float, macd_score: float, bb_score: float
    ) -> float:
        """Apply allocation weights to component scores.

        Args:
            rsi_score: RSI indicator score (-100 to +100)
            macd_score: MACD indicator score (-100 to +100)
            bb_score: Bollinger Bands indicator score (-100 to +100)

        Returns:
            Weighted composite score (-100 to +100)

        Note:
            - RSI (momentum indicator) uses momentum weight
            - MACD (momentum indicator) uses momentum weight
            - BB (reversion indicator) uses reversion weight
            - Grid component uses grid weight
        """
        alloc = self.current_allocation

        # RSI and MACD are momentum-based
        momentum_score = (rsi_score + macd_score) / 2

        # Bollinger Bands is reversion-based
        reversion_score = bb_score

        # Grid component (simplified: neutral for now)
        grid_score = 0

        # Convert allocations from percentages to decimals
        momentum_weight = alloc["momentum"] / 100
        reversion_weight = alloc["reversion"] / 100
        grid_weight = alloc["grid"] / 100

        # Weighted composite
        composite = (
            (momentum_score * momentum_weight)
            + (reversion_score * reversion_weight)
            + (grid_score * grid_weight)
        )

        return composite


# Global allocation manager instance
_allocation_manager: Optional[AllocationManager] = None


def init_allocation() -> AllocationManager:
    """Initialize global allocation manager."""
    global _allocation_manager
    _allocation_manager = AllocationManager()
    return _allocation_manager


def get_allocation() -> Optional[AllocationManager]:
    """Get global allocation manager."""
    return _allocation_manager
