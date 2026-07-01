"""Emergency control endpoints (FR-016, FR-017, FR-020).

POST /api/emergency/stop       - FR-020: Hard kill switch
POST /api/emergency/close-all  - FR-017: Close all positions (market crash response)
GET  /api/emergency/status     - Get emergency system status
"""

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from datetime import datetime

from backend.core.emergency_stop import (
    trigger_emergency_stop,
    get_emergency_stop_status,
    reset_emergency_stop,
    is_emergency_stop_active
)
from backend.core.crash_detector import (
    detect_crash,
    reset_crash_detection,
    get_crash_detection_status,
    set_crash_threshold,
    CrashDetectionConfig
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/emergency", tags=["Emergency Controls"])


class EmergencyStopRequest(BaseModel):
    reason: str = Field(..., description="Why emergency stop is being triggered")


class EmergencyStopResponse(BaseModel):
    success: bool
    positions_closed: int
    timestamp: datetime
    reason: str
    error: str = None


class CrashDetectionRequest(BaseModel):
    threshold_percent: float = Field(default=5.0, description="% drop to trigger close-all")
    lookback_minutes: int = Field(default=5, description="Time window in minutes")
    min_candles: int = Field(default=3, description="Minimum candles needed")


class CrashDetectionResponse(BaseModel):
    crash_detected: bool
    triggered_at: datetime
    symbols_analyzed: list
    largest_drop_symbol: str = None
    largest_drop_percent: float
    details: dict


class EmergencyStatusResponse(BaseModel):
    emergency_stop_active: bool
    emergency_stop_triggered_at: datetime = None
    emergency_stop_reason: str = None
    crash_detected: bool
    crash_threshold_percent: float
    tracked_symbols: list


@router.post("/stop", response_model=EmergencyStopResponse)
async def emergency_stop(request: EmergencyStopRequest) -> EmergencyStopResponse:
    """
    HARD KILL SWITCH - FR-020.

    Immediately:
    1. Stop all trading
    2. Close all open positions
    3. Halt HA failover
    4. Log to audit trail

    **This is a one-way operation.** System won't resume trading until
    you manually call POST /api/emergency/reset (which requires confirmation).

    Args:
        reason: Why you're triggering emergency stop

    Returns:
        Status of positions closed and any errors
    """
    if is_emergency_stop_active():
        raise HTTPException(
            status_code=400,
            detail="Emergency stop already active"
        )

    logger.critical(f"🚨 EMERGENCY STOP REQUESTED: {request.reason}")

    result = await trigger_emergency_stop(request.reason)

    return EmergencyStopResponse(**result)


@router.post("/close-all", response_model=CrashDetectionResponse)
async def close_all_positions(request: CrashDetectionRequest) -> CrashDetectionResponse:
    """
    CLOSE ALL POSITIONS - FR-017.

    Triggered by market crash or manual request.
    Uses crash detection to identify if market crashed.

    If crash detected:
    - Analyzes price movements
    - Returns detailed breakdown
    - **Does NOT automatically close** (you must call /emergency/stop)

    Args:
        threshold_percent: Market drop % to trigger alert
        lookback_minutes: Time window for price analysis
        min_candles: Minimum candles needed

    Returns:
        Crash analysis details
    """
    config = CrashDetectionConfig(
        threshold_percent=request.threshold_percent,
        lookback_minutes=request.lookback_minutes,
        min_candles=request.min_candles
    )

    result = detect_crash(config)

    if result['crash_detected']:
        logger.critical(
            f"💥 CRASH RESPONSE: {result['largest_drop_symbol']} "
            f"down {result['largest_drop_percent']}%"
        )

    return CrashDetectionResponse(**result)


@router.get("/status", response_model=EmergencyStatusResponse)
async def get_emergency_status() -> EmergencyStatusResponse:
    """
    Get current emergency system status.

    Returns:
        - Is emergency stop active?
        - When was it triggered?
        - Has market crash been detected?
        - Current crash detection configuration
    """
    stop_status = get_emergency_stop_status()
    crash_status = get_crash_detection_status()

    return EmergencyStatusResponse(
        emergency_stop_active=stop_status['active'],
        emergency_stop_triggered_at=stop_status['triggered_at'],
        emergency_stop_reason=stop_status['reason'],
        crash_detected=crash_status['crashed'],
        crash_threshold_percent=crash_status['threshold_percent'],
        tracked_symbols=crash_status['tracked_symbols']
    )


@router.post("/reset")
async def reset_emergency_system(confirm: bool = False) -> dict:
    """
    Reset emergency stop (for testing or after manual recovery).

    **DANGEROUS:** Only call after:
    - Confirming all positions are manually closed
    - Market has stabilized
    - System is in safe state

    Args:
        confirm: Must be True to proceed

    Returns:
        Confirmation message
    """
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Must pass confirm=true to reset emergency stop"
        )

    logger.warning("⚠️  RESETTING EMERGENCY STOP SYSTEM")

    await reset_emergency_stop()
    reset_crash_detection()

    return {
        'message': 'Emergency stop system reset',
        'status': get_emergency_stop_status(),
        'warning': 'System will resume trading on next scheduled run'
    }


@router.post("/set-crash-threshold")
async def configure_crash_threshold(threshold_percent: float = 5.0) -> dict:
    """
    Configure crash detection threshold.

    Args:
        threshold_percent: Market drop % to trigger (e.g., 5.0 for 5%)

    Returns:
        New configuration
    """
    if threshold_percent <= 0 or threshold_percent > 50:
        raise HTTPException(
            status_code=400,
            detail="Threshold must be between 0 and 50%"
        )

    set_crash_threshold(threshold_percent)

    return {
        'threshold_percent': threshold_percent,
        'message': f'Crash detection now triggers at {threshold_percent}% drop'
    }
