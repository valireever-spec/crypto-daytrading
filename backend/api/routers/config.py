"""Configuration management API endpoints."""

import logging
from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel, Field
from typing import Optional

from backend.core.runtime_config import get_config_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/config", tags=["configuration"])


class ConfigUpdateRequest(BaseModel):
    """Request to update configuration."""

    entry_threshold: Optional[int] = Field(None, ge=0, le=100)
    exit_profit_target: Optional[float] = Field(None, gt=0, lt=1)
    exit_stop_loss: Optional[float] = Field(None, gt=0, lt=1)
    max_positions: Optional[int] = Field(None, ge=1)
    position_size_pct: Optional[float] = Field(None, gt=0, le=1)
    max_daily_loss_pct: Optional[float] = Field(None, gt=0)
    max_position_loss_pct: Optional[float] = Field(None, gt=0)
    enabled: Optional[bool] = None
    symbols: Optional[list] = None


class ConfigResponse(BaseModel):
    """Configuration response."""

    entry_threshold: int
    exit_profit_target: float
    exit_stop_loss: float
    max_positions: int
    position_size_pct: float
    max_daily_loss_pct: float
    max_position_loss_pct: float
    websocket_reconnect_max_attempts: int
    websocket_max_backoff: int
    enabled: bool
    symbols: list


@router.get("", response_model=ConfigResponse)
async def get_config():
    """Get current trading configuration.

    Returns:
        Current configuration with all parameters
    """
    manager = get_config_manager()
    config = manager.get_config()
    config_dict = config.to_dict()

    # Safety check: ensure no None values (defensive programming)
    for key, value in config_dict.items():
        if value is None:
            logger.warning(f"⚠️ Config field {key} is None, using default")
            # Set sensible defaults
            defaults = {
                'symbols': ['BTCUSDT', 'ETHUSDT', 'BNBUSDT'],
                'enabled': True,
            }
            config_dict[key] = defaults.get(key, value)

    return ConfigResponse(**config_dict)


@router.post("", response_model=ConfigResponse)
async def update_config(
    updates: ConfigUpdateRequest = Body(...)
):
    """Update trading configuration.

    Parameters can be updated individually or in batches.
    All values are validated before applying.

    Args:
        updates: Configuration updates (optional fields)

    Returns:
        Updated configuration

    Raises:
        HTTPException: If update validation fails
    """
    manager = get_config_manager()

    # Filter out None values
    update_dict = {k: v for k, v in updates.dict().items() if v is not None}

    if not update_dict:
        raise HTTPException(
            status_code=400,
            detail="No configuration updates provided"
        )

    # Try to update
    if manager.update_config(update_dict):
        # Save to file
        if manager.save_config():
            config = manager.get_config()
            logger.info(f"✅ Configuration updated and saved: {update_dict}")
            return ConfigResponse(**config.to_dict())
        else:
            raise HTTPException(
                status_code=500,
                detail="Config updated in memory but failed to save to file"
            )
    else:
        raise HTTPException(
            status_code=400,
            detail="Invalid configuration values"
        )


@router.post("/reload")
async def reload_config():
    """Reload configuration from file.

    Useful for syncing configuration from backup or external updates.

    Returns:
        Current configuration after reload
    """
    manager = get_config_manager()

    if manager.reload_config():
        config = manager.get_config()
        logger.info("✅ Configuration reloaded from file")
        return {
            "status": "success",
            "message": "Configuration reloaded",
            "config": ConfigResponse(**config.to_dict())
        }
    else:
        raise HTTPException(
            status_code=500,
            detail="Failed to reload configuration from file"
        )


@router.post("/trading/enable")
async def enable_trading():
    """Enable automated trading."""
    manager = get_config_manager()
    manager.enable_trading()
    manager.save_config()

    config = manager.get_config()
    logger.info("✅ Trading enabled via API")
    return {
        "status": "success",
        "message": "Trading enabled",
        "trading_enabled": config.enabled
    }


@router.post("/trading/disable")
async def disable_trading():
    """Disable automated trading (emergency stop)."""
    manager = get_config_manager()
    manager.disable_trading()
    manager.save_config()

    config = manager.get_config()
    logger.warning("🛑 Trading disabled via API")
    return {
        "status": "success",
        "message": "Trading disabled",
        "trading_enabled": config.enabled
    }


@router.get("/trading/status")
async def get_trading_status():
    """Get trading enabled/disabled status."""
    manager = get_config_manager()
    config = manager.get_config()

    return {
        "trading_enabled": config.enabled,
        "symbols": config.symbols,
        "max_positions": config.max_positions
    }


@router.get("/parameters")
async def get_parameters():
    """Get all trading parameters in compact format."""
    manager = get_config_manager()
    config = manager.get_config()

    return {
        "entry": {
            "threshold": config.entry_threshold,
            "description": "Signal strength threshold for entry (0-100)"
        },
        "exit": {
            "profit_target": config.exit_profit_target,
            "stop_loss": config.exit_stop_loss,
            "description": "Exit targets as % of position value"
        },
        "risk": {
            "max_daily_loss_pct": config.max_daily_loss_pct,
            "max_position_loss_pct": config.max_position_loss_pct,
            "description": "Maximum losses as % of portfolio"
        },
        "positions": {
            "max_concurrent": config.max_positions,
            "size_pct": config.position_size_pct,
            "description": "Position limits"
        }
    }
