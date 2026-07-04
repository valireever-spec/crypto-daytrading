"""Runtime configuration management for trading parameters.

Allows loading and updating trading parameters without code changes or restarts.
Supports JSON file-based config and environment variable overrides.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

logger = logging.getLogger(__name__)

CONFIG_FILE = Path("system_config.json")


@dataclass
class TradingConfig:
    """Runtime trading configuration."""

    # Entry/Exit parameters
    entry_threshold: int = 65  # Entry signal threshold (0-100) - CRITICAL FIX
    exit_profit_target: float = 2.0  # Exit profit target (2.0%) - CRITICAL FIX (risk ratio 2:1)
    exit_stop_loss: float = 1.0  # Exit stop loss (1.0%) - CRITICAL FIX (risk ratio 2:1)

    # Position sizing
    max_positions: int = 10  # Maximum concurrent positions
    position_size_pct: float = 1.0  # Position size as % of portfolio

    # Risk management
    max_daily_loss_pct: float = 5.0  # Max daily loss before stop
    max_position_loss_pct: float = 2.0  # Max loss per position

    # WebSocket
    websocket_reconnect_max_attempts: int = 5
    websocket_max_backoff: int = 60  # Max 60 seconds

    # Trading behavior
    enabled: bool = True  # Whether trading is enabled
    symbols: list = None  # List of trading symbols

    # Data quality gates
    quality_gate_entry: int = 80  # Minimum data quality % to enter positions
    quality_gate_exit: int = 60  # Minimum data quality % to exit positions

    # Recovery parameters
    retry_sleep_seconds: int = 5  # Seconds to sleep between recovery attempts
    loop_sleep_seconds: int = 1  # Seconds to sleep between trading loop iterations

    def __post_init__(self):
        """Validate configuration after initialization."""
        if self.symbols is None:
            self.symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]

        # Validate ranges
        if not 0 <= self.entry_threshold <= 100:
            raise ValueError(f"entry_threshold must be 0-100, got {self.entry_threshold}")
        if not 0 < self.exit_profit_target < 1:
            raise ValueError(f"exit_profit_target must be 0-1, got {self.exit_profit_target}")
        if not 0 < self.exit_stop_loss < 1:
            raise ValueError(f"exit_stop_loss must be 0-1, got {self.exit_stop_loss}")
        if self.max_positions < 1:
            raise ValueError(f"max_positions must be >= 1, got {self.max_positions}")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TradingConfig":
        """Create from dictionary."""
        return cls(**data)


class RuntimeConfigManager:
    """Manage runtime trading configuration."""

    def __init__(self, config_file: Path = CONFIG_FILE):
        """Initialize config manager.

        Args:
            config_file: Path to JSON config file
        """
        self.config_file = config_file
        self.config = self._load_config()
        self.last_modified = datetime.utcnow()
        logger.info(f"✅ Runtime config loaded from {config_file}")

    def _load_config(self) -> TradingConfig:
        """Load configuration from file or use defaults."""
        if self.config_file.exists():
            try:
                with open(self.config_file, "r") as f:
                    data = json.load(f)
                    config = TradingConfig.from_dict(data)
                    logger.info(f"✅ Loaded config from {self.config_file}")
                    return config
            except Exception as e:
                logger.warning(f"⚠️  Failed to load config from file: {e}, using defaults")
                return TradingConfig()
        else:
            logger.info("📝 No config file found, using defaults")
            return TradingConfig()

    def save_config(self) -> bool:
        """Save current configuration to file."""
        try:
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, "w") as f:
                json.dump(self.config.to_dict(), f, indent=2)
            self.last_modified = datetime.utcnow()
            logger.info(f"✅ Saved config to {self.config_file}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to save config: {e}")
            return False

    def get_config(self) -> TradingConfig:
        """Get current configuration."""
        return self.config

    def update_config(self, updates: Dict[str, Any]) -> bool:
        """Update configuration with new values.

        Args:
            updates: Dictionary of fields to update

        Returns:
            True if update successful
        """
        try:
            # Validate all updates first
            test_config = TradingConfig.from_dict({
                **self.config.to_dict(),
                **updates
            })

            # Apply updates
            for key, value in updates.items():
                if hasattr(self.config, key):
                    setattr(self.config, key, value)
                    logger.info(f"✅ Updated {key} = {value}")
                else:
                    logger.warning(f"⚠️  Unknown config field: {key}")

            self.last_modified = datetime.utcnow()
            logger.info("✅ Config updated")
            return True

        except ValueError as e:
            logger.error(f"❌ Invalid config update: {e}")
            return False

    def get_entry_threshold(self) -> int:
        """Get entry signal threshold (0-100)."""
        return self.config.entry_threshold

    def get_exit_profit_target(self) -> float:
        """Get exit profit target (e.g., 0.025 = 2.5%)."""
        return self.config.exit_profit_target

    def get_exit_stop_loss(self) -> float:
        """Get exit stop loss (e.g., 0.015 = 1.5%)."""
        return self.config.exit_stop_loss

    def get_max_positions(self) -> int:
        """Get maximum number of concurrent positions."""
        return self.config.max_positions

    def get_symbols(self) -> list:
        """Get list of trading symbols."""
        return self.config.symbols

    def is_trading_enabled(self) -> bool:
        """Check if trading is enabled."""
        return self.config.enabled

    def enable_trading(self) -> None:
        """Enable trading."""
        self.config.enabled = True
        self.last_modified = datetime.utcnow()
        logger.info("✅ Trading enabled")

    def disable_trading(self) -> None:
        """Disable trading."""
        self.config.enabled = False
        self.last_modified = datetime.utcnow()
        logger.info("🛑 Trading disabled")

    def reload_config(self) -> bool:
        """Reload configuration from file."""
        try:
            self.config = self._load_config()
            logger.info("✅ Config reloaded")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to reload config: {e}")
            return False


# Global instance
_config_manager: Optional[RuntimeConfigManager] = None


def get_config_manager() -> RuntimeConfigManager:
    """Get global config manager instance (lazy initialization)."""
    global _config_manager
    if _config_manager is None:
        _config_manager = RuntimeConfigManager()
    return _config_manager


def get_trading_config() -> TradingConfig:
    """Get current trading configuration."""
    return get_config_manager().get_config()
