"""Allocation management endpoints for saving and loading presets."""

import logging
import json
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/allocation", tags=["Allocation"])

# Allocation presets
ALLOCATION_PRESETS = {
    "balanced": {"momentum": 33.33, "reversion": 33.33, "grid": 33.34},
    "aggressive": {"momentum": 50, "reversion": 30, "grid": 20},
    "conservative": {"momentum": 20, "reversion": 50, "grid": 30},
    "momentum-heavy": {"momentum": 60, "reversion": 20, "grid": 20},
    "reversion-heavy": {"momentum": 25, "reversion": 60, "grid": 15},
}

ALLOCATION_FILE = Path("logs") / "allocation_config.json"


@router.post("/save")
async def save_allocation(momentum: float, reversion: float, grid: float) -> JSONResponse:
    """Save allocation configuration."""
    try:
        # Validate percentages
        total = momentum + reversion + grid
        if abs(total - 100) > 0.01:
            raise HTTPException(
                status_code=400,
                detail=f"Allocation must sum to 100%, got {total:.2f}%"
            )

        allocation = {
            "momentum": momentum,
            "reversion": reversion,
            "grid": grid,
            "total": total
        }

        # Save to file
        Path("logs").mkdir(exist_ok=True)
        with open(ALLOCATION_FILE, "w") as f:
            json.dump(allocation, f, indent=2)

        logger.info(f"✅ Allocation saved: momentum={momentum:.1f}%, reversion={reversion:.1f}%, grid={grid:.1f}%")

        return {
            "status": "saved",
            "momentum": momentum,
            "reversion": reversion,
            "grid": grid
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving allocation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/preset")
async def load_preset(preset: str) -> JSONResponse:
    """Load a preset allocation configuration."""
    try:
        if preset not in ALLOCATION_PRESETS:
            raise HTTPException(
                status_code=404,
                detail=f"Preset '{preset}' not found. Available: {', '.join(ALLOCATION_PRESETS.keys())}"
            )

        allocation = ALLOCATION_PRESETS[preset]
        logger.info(f"✅ Loaded preset: {preset}")

        return {
            "status": "loaded",
            "preset": preset,
            "momentum": allocation["momentum"],
            "reversion": allocation["reversion"],
            "grid": allocation["grid"]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error loading preset: {e}")
        raise HTTPException(status_code=500, detail=str(e))
