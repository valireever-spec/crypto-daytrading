"""Configuration management for crypto daytrading platform."""

from pydantic_settings import BaseSettings
from typing import Literal


class Settings(BaseSettings):
    """Application configuration from environment variables."""

    # Trading Configuration
    trading_mode: Literal["paper", "live"] = "paper"
    initial_capital: float = 10000.0  # €10,000 for paper trading
    max_daily_loss_pct: float = 5.0  # Stop trading if loss > 5%
    max_positions: int = 5
    position_size_pct: float = 1.5  # Base position size

    # Binance Configuration
    binance_api_key: str = ""
    binance_api_secret: str = ""
    binance_testnet: bool = True  # Use testnet initially, switch to False for live

    # Machine HA Configuration
    machine_id: Literal["main", "backup"] = "main"
    backup_machine_url: str = "http://backup-machine:8000"
    heartbeat_interval: int = 10  # seconds

    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Logging
    log_level: str = "INFO"
    debug: bool = False

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"


# Global settings instance
settings = Settings()
