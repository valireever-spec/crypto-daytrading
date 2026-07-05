"""
HA Configuration: Settings for dual-machine HA setup.

Controls:
- Whether HA is enabled
- Sync frequency
- Heartbeat intervals
- Failover thresholds
- Network endpoints
"""

import os
from typing import Optional
from dataclasses import dataclass


@dataclass
class HAConfig:
    """HA system configuration."""

    # Enable/disable HA
    enabled: bool = os.getenv("HA_ENABLED", "false").lower() == "true"

    # Role assignment (PRIMARY or BACKUP)
    role: str = os.getenv("HA_ROLE", "PRIMARY")

    # State synchronization
    sync_interval: float = float(os.getenv("HA_SYNC_INTERVAL", "5.0"))  # seconds
    sync_timeout: float = float(os.getenv("HA_SYNC_TIMEOUT", "10.0"))  # seconds
    sync_retries: int = int(os.getenv("HA_SYNC_RETRIES", "3"))

    # Heartbeat monitoring
    heartbeat_interval: float = float(os.getenv("HA_HEARTBEAT_INTERVAL", "5.0"))  # seconds
    heartbeat_timeout: float = float(os.getenv("HA_HEARTBEAT_TIMEOUT", "6.0"))  # seconds (5s + 1s grace)
    heartbeat_failure_threshold: int = int(os.getenv("HA_HEARTBEAT_THRESHOLD", "3"))  # 3 missed beats = 15s

    # Network endpoints - MUST be explicitly set in environment!
    # Using localhost defaults causes split-brain (BACKUP checks itself instead of PRIMARY)
    primary_host: str = os.getenv("HA_PRIMARY_HOST", "")  # Required: 192.168.30.137
    primary_port: int = int(os.getenv("HA_PRIMARY_PORT", "8001"))

    backup_host: str = os.getenv("HA_BACKUP_HOST", "")  # Required: 192.168.3.25
    backup_port: int = int(os.getenv("HA_BACKUP_PORT", "8002"))

    # Failover
    failover_validation: bool = os.getenv("HA_FAILOVER_VALIDATION", "true").lower() == "true"
    failover_min_state_coverage: float = float(
        os.getenv("HA_FAILOVER_MIN_STATE_COVERAGE", "0.80")
    )  # 80% of globals
    failover_timeout: float = float(os.getenv("HA_FAILOVER_TIMEOUT", "60.0"))  # seconds

    # Trade execution during/after failover
    resume_trading_immediately: bool = os.getenv(
        "HA_RESUME_IMMEDIATELY", "true"
    ).lower() == "true"
    incomplete_order_timeout: float = float(
        os.getenv("HA_INCOMPLETE_ORDER_TIMEOUT", "30.0")
    )  # seconds

    # Logging
    log_level: str = os.getenv("HA_LOG_LEVEL", "INFO")
    log_file: str = os.getenv("HA_LOG_FILE", "logs/ha.log")

    # Monitoring
    export_metrics: bool = os.getenv("HA_EXPORT_METRICS", "true").lower() == "true"
    metrics_port: int = int(os.getenv("HA_METRICS_PORT", "8888"))

    def validate(self) -> bool:
        """Validate configuration."""
        if not self.enabled:
            return True  # No validation needed if disabled

        # CRITICAL: Validate network endpoints are explicitly configured
        if not self.primary_host:
            raise ValueError(
                "HA_PRIMARY_HOST must be set in environment (e.g., 192.168.30.137). "
                "Using localhost default causes split-brain!"
            )
        if not self.backup_host:
            raise ValueError(
                "HA_BACKUP_HOST must be set in environment (e.g., 192.168.3.25). "
                "Using localhost default causes split-brain!"
            )

        # Validate role
        if self.role not in ("PRIMARY", "BACKUP"):
            raise ValueError(f"Invalid role: {self.role}")

        # Validate intervals
        if self.sync_interval <= 0:
            raise ValueError("sync_interval must be > 0")
        if self.heartbeat_interval <= 0:
            raise ValueError("heartbeat_interval must be > 0")

        # Validate thresholds
        if self.heartbeat_failure_threshold < 1:
            raise ValueError("heartbeat_failure_threshold must be >= 1")
        if not (0 <= self.failover_min_state_coverage <= 1):
            raise ValueError("failover_min_state_coverage must be 0-1")

        # Validate ports
        if self.primary_port < 1 or self.primary_port > 65535:
            raise ValueError("primary_port must be 1-65535")
        if self.backup_port < 1 or self.backup_port > 65535:
            raise ValueError("backup_port must be 1-65535")

        return True

    @classmethod
    def from_env(cls) -> "HAConfig":
        """Load configuration from environment variables."""
        config = cls()
        config.validate()
        return config

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "enabled": self.enabled,
            "role": self.role,
            "sync_interval": self.sync_interval,
            "heartbeat_interval": self.heartbeat_interval,
            "heartbeat_failure_threshold": self.heartbeat_failure_threshold,
            "failover_min_state_coverage": self.failover_min_state_coverage,
        }


# Global configuration instance
_config: Optional[HAConfig] = None


def get_ha_config() -> HAConfig:
    """Get HA configuration instance."""
    global _config
    if _config is None:
        _config = HAConfig.from_env()
    return _config


def set_ha_config(config: HAConfig) -> None:
    """Set HA configuration instance."""
    global _config
    _config = config
