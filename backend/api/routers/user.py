"""User profile and settings endpoints."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from datetime import datetime

router = APIRouter(prefix="/api/user", tags=["User"])

# In-memory settings storage (in production, use database)
user_settings = {
    "theme": "dark",
    "notifications_enabled": True,
    "auto_refresh_interval": 5000,
    "risk_level": "medium",
    "preferred_currencies": ["USD"],
    "language": "en"
}


@router.get("/profile")
async def get_user_profile() -> JSONResponse:
    """Get user profile information."""
    return JSONResponse({
        "user_id": "user_001",
        "username": "trader",
        "email": "trader@example.com",
        "created_at": "2024-01-01T00:00:00Z",
        "account_type": "paper",
        "verification_status": "verified",
        "avatar": None,
        "bio": "Crypto day trader using AI-powered strategies",
        "preferred_currency": "USD",
        "timezone": "UTC"
    })


@router.get("/settings")
async def get_user_settings() -> JSONResponse:
    """Get user settings."""
    return JSONResponse(user_settings)


@router.put("/settings")
async def update_user_settings(settings: dict) -> JSONResponse:
    """Update user settings."""
    global user_settings

    # Validate and update settings
    if "theme" in settings and settings["theme"] in ["light", "dark"]:
        user_settings["theme"] = settings["theme"]

    if "notifications_enabled" in settings:
        user_settings["notifications_enabled"] = bool(settings["notifications_enabled"])

    if "auto_refresh_interval" in settings and isinstance(settings["auto_refresh_interval"], int):
        user_settings["auto_refresh_interval"] = settings["auto_refresh_interval"]

    if "risk_level" in settings and settings["risk_level"] in ["low", "medium", "high"]:
        user_settings["risk_level"] = settings["risk_level"]

    if "preferred_currencies" in settings and isinstance(settings["preferred_currencies"], list):
        user_settings["preferred_currencies"] = settings["preferred_currencies"]

    if "language" in settings:
        user_settings["language"] = settings["language"]

    return JSONResponse({
        "status": "success",
        "message": "Settings updated successfully",
        "settings": user_settings
    })


@router.get("/preferences")
async def get_user_preferences() -> JSONResponse:
    """Get detailed user preferences."""
    return JSONResponse({
        "trading": {
            "strategy": "hybrid",
            "position_size_pct": 2.0,
            "max_positions": 5,
            "stop_loss_pct": 2.0,
            "take_profit_pct": 5.0
        },
        "risk": {
            "daily_loss_limit": 500.0,
            "max_position_size": 10000.0,
            "correlation_threshold": 0.8
        },
        "notifications": {
            "entry_signals": True,
            "exit_signals": True,
            "portfolio_alerts": True,
            "daily_digest": True
        },
        "display": {
            "theme": user_settings.get("theme", "dark"),
            "language": user_settings.get("language", "en"),
            "timezone": "UTC"
        }
    })
