"""Persistent configuration manager for autonomous trading.

Stores trading config to disk so it persists across restarts and syncs between
primary and backup machines.
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

CONFIG_DIR = Path("logs")
CONFIG_FILE = CONFIG_DIR / "trading_config.json"

# Critical environment variables that should be explicitly set
CRITICAL_ENV_VARS = [
    "MACHINE_ID",
    "BACKUP_MACHINE_URL",
    "PRIMARY_API_URL",
]


class ConfigManager:
    """Manages persistent trading configuration."""

    @staticmethod
    def validate_env_config() -> None:
        """Validate that critical environment variables are set.

        Logs warnings if critical env vars are using hardcoded defaults.
        Should be called during startup to catch misconfiguration early.
        """
        missing = []
        for var in CRITICAL_ENV_VARS:
            if var not in os.environ:
                missing.append(var)
                logger.warning(f"Critical env var not set: {var} (using hardcoded default)")

        if missing:
            logger.warning(
                f"Missing {len(missing)} critical env vars: {', '.join(missing)}. "
                f"Set these in .env file for production."
            )

    @staticmethod
    def get_config_path() -> Path:
        """Get path to config file."""
        CONFIG_DIR.mkdir(exist_ok=True)
        return CONFIG_FILE

    @staticmethod
    def load_config() -> Dict[str, Any]:
        """Load config from disk. Falls back to .env if not found."""
        config_file = ConfigManager.get_config_path()

        # Try to load from persistent storage
        if config_file.exists():
            try:
                with open(config_file, "r") as f:
                    data = json.load(f)
                    logger.info(f"Loaded config from {config_file}")
                    return data
            except Exception as e:
                logger.warning(f"Failed to load config from {config_file}: {e}")

        # Fall back to .env values
        logger.info("Loading config from .env (no persistent config found)")
        return ConfigManager.env_to_config()

    @staticmethod
    def env_to_config() -> Dict[str, Any]:
        """Convert .env variables to config dict."""
        import os
        # Parse symbols from comma-separated env var
        symbols_str = os.getenv("TRADING_SYMBOLS", "BTCUSDT,ETHUSDT,BNBUSDT")
        symbols = [s.strip() for s in symbols_str.split(",") if s.strip()]

        return {
            "position_size_pct": float(os.getenv("POSITION_SIZE_PCT", "0.05")),
            "max_positions": int(os.getenv("MAX_POSITIONS", "5")),
            "max_daily_loss_pct": float(os.getenv("MAX_DAILY_LOSS_PCT", "5.0")),
            "entry_threshold": float(os.getenv("ENTRY_THRESHOLD", "60.0")),
            "exit_profit_target": float(os.getenv("EXIT_PROFIT_TARGET", "0.03")),
            "exit_stop_loss": float(os.getenv("EXIT_STOP_LOSS", "0.02")),
            "enabled": True,
            "symbols": symbols,
        }

    @staticmethod
    def save_config(config: Dict[str, Any]) -> bool:
        """Save config to disk (persistent storage)."""
        try:
            config_file = ConfigManager.get_config_path()
            config_with_meta = {
                **config,
                "_last_updated": datetime.utcnow().isoformat() + "Z",
                "_source": "api_update",
            }

            with open(config_file, "w") as f:
                json.dump(config_with_meta, f, indent=2)

            logger.info(f"Saved config to {config_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            return False

    @staticmethod
    def sync_to_backup(backup_url: str, config: Dict[str, Any]) -> bool:
        """Sync config to backup machine via API with retry logic."""
        import httpx
        import asyncio

        max_retries = 3
        retry_delays = [1, 2, 4]  # exponential backoff: 1s, 2s, 4s

        for attempt in range(max_retries):
            try:
                endpoint = f"{backup_url}/api/autonomous/config/sync"
                response = httpx.post(endpoint, json=config, timeout=5)

                if response.status_code == 200:
                    logger.info(f"Synced config to backup: {backup_url}")
                    return True
                else:
                    logger.warning(f"Backup sync attempt {attempt + 1}/{max_retries} failed: HTTP {response.status_code}")
            except Exception as e:
                logger.warning(f"Backup sync attempt {attempt + 1}/{max_retries} failed: {e}")

            # Retry with exponential backoff (except on last attempt)
            if attempt < max_retries - 1:
                delay = retry_delays[attempt]
                logger.info(f"Retrying backup sync in {delay}s...")
                import time
                time.sleep(delay)
            else:
                logger.error(f"Backup sync failed after {max_retries} attempts")
                return False

        return False

    @staticmethod
    def load_from_backup(backup_url: str) -> Optional[Dict[str, Any]]:
        """Load config from backup machine."""
        try:
            import httpx

            endpoint = f"{backup_url}/api/autonomous/config"
            response = httpx.get(endpoint, timeout=5)

            if response.status_code == 200:
                logger.info(f"Loaded config from backup: {backup_url}")
                return response.json()
            else:
                logger.warning(f"Could not get config from backup: HTTP {response.status_code}")
                return None
        except Exception as e:
            logger.warning(f"Could not reach backup: {e}")
            return None
