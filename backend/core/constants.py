"""Central configuration for all hardcoded values and URLs.

This module consolidates all magic numbers, hardcoded URLs, and configuration
values into a single source of truth to prevent inconsistencies and make it
easier to configure for different environments.
"""

import os
from typing import Optional

# ============================================================================
# MACHINE & HA CONFIGURATION
# ============================================================================

PRIMARY_API_URL = os.getenv(
    "PRIMARY_API_URL", "http://127.0.0.1:8001"
)
BACKUP_API_URL = os.getenv(
    "BACKUP_API_URL", "http://192.168.3.25:8002"
)
PRIMARY_PORT = int(os.getenv("PRIMARY_PORT", "8001"))
BACKUP_PORT = int(os.getenv("BACKUP_PORT", "8002"))

# ============================================================================
# HEARTBEAT & HEALTH CHECK CONFIGURATION
# ============================================================================

# Heartbeat monitor settings
HEARTBEAT_CHECK_INTERVAL = int(os.getenv("HEARTBEAT_CHECK_INTERVAL", "5"))  # seconds
HEARTBEAT_FAILURE_THRESHOLD = int(os.getenv("HEARTBEAT_FAILURE_THRESHOLD", "3"))  # misses before failover
HEARTBEAT_TIMEOUT_SECONDS = HEARTBEAT_CHECK_INTERVAL * HEARTBEAT_FAILURE_THRESHOLD  # 15 seconds

# Health check timeouts
HEALTH_CHECK_TIMEOUT = int(os.getenv("HEALTH_CHECK_TIMEOUT", "2"))  # seconds
HEALTH_CHECK_RETRIES = int(os.getenv("HEALTH_CHECK_RETRIES", "2"))

# Retry configuration
RETRY_DELAYS = [0.1, 0.5, 1.0]  # exponential backoff in seconds
MAX_RETRIES = len(RETRY_DELAYS)

# ============================================================================
# REPLICATION & SYNC CONFIGURATION
# ============================================================================

STATE_SYNC_INTERVAL = int(os.getenv("STATE_SYNC_INTERVAL", "5"))  # seconds
REPLICATION_LAG_WARNING_THRESHOLD = float(os.getenv("REPLICATION_LAG_WARNING", "2.0"))  # seconds
REPLICATION_LAG_CRITICAL_THRESHOLD = float(os.getenv("REPLICATION_LAG_CRITICAL", "5.0"))  # seconds

# ============================================================================
# TRADING CONFIGURATION DEFAULTS
# ============================================================================

DEFAULT_ENTRY_THRESHOLD = float(os.getenv("DEFAULT_ENTRY_THRESHOLD", "60.0"))
DEFAULT_EXIT_PROFIT_TARGET = float(os.getenv("DEFAULT_EXIT_PROFIT_TARGET", "3.0"))  # percent
DEFAULT_EXIT_STOP_LOSS = float(os.getenv("DEFAULT_EXIT_STOP_LOSS", "3.0"))  # percent
DEFAULT_POSITION_SIZE_PCT = float(os.getenv("DEFAULT_POSITION_SIZE_PCT", "2.5"))  # percent
DEFAULT_MAX_POSITIONS = int(os.getenv("DEFAULT_MAX_POSITIONS", "8"))
DEFAULT_MAX_DAILY_LOSS_PCT = float(os.getenv("DEFAULT_MAX_DAILY_LOSS_PCT", "5.0"))  # percent
DEFAULT_QUALITY_GATE_ENTRY = float(os.getenv("DEFAULT_QUALITY_GATE_ENTRY", "90.0"))  # percent
DEFAULT_QUALITY_GATE_EXIT = float(os.getenv("DEFAULT_QUALITY_GATE_EXIT", "60.0"))  # percent

# Trading loop timing
TRADING_LOOP_SLEEP = float(os.getenv("TRADING_LOOP_SLEEP", "10.0"))  # seconds
TRADING_LOOP_RETRY_SLEEP = float(os.getenv("TRADING_LOOP_RETRY_SLEEP", "5.0"))  # seconds

# ============================================================================
# ACCOUNT & CAPITAL CONFIGURATION
# ============================================================================

DEFAULT_INITIAL_CAPITAL = float(os.getenv("INITIAL_CAPITAL", "1000.0"))  # euros

# ============================================================================
# BINANCE CONFIGURATION
# ============================================================================

BINANCE_BASE_URL = "https://api.binance.com"
BINANCE_TESTNET_URL = "https://testnet.binance.vision"
BINANCE_RATE_LIMIT_PER_MINUTE = 1200

# Default trading pairs for crypto trading
DEFAULT_TRADING_PAIRS = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]

# ============================================================================
# LOGGING & MONITORING
# ============================================================================

DEFAULT_LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE_PATH = os.getenv("LOG_FILE_PATH", "logs/trades.jsonl")
METRICS_FLUSH_INTERVAL = int(os.getenv("METRICS_FLUSH_INTERVAL", "60"))  # seconds

# ============================================================================
# ENVIRONMENT DETECTION
# ============================================================================

MACHINE_ID = os.getenv("MACHINE_ID", "main")
IS_PRIMARY = MACHINE_ID == "main"
IS_BACKUP = MACHINE_ID == "backup"

# ============================================================================
# DATABASE CONFIGURATION
# ============================================================================

DATABASE_PATH = os.getenv("DATABASE_PATH", "data/trading.db")
DATABASE_BACKUP_PATH = os.getenv("DATABASE_BACKUP_PATH", "data/trading.backup.db")
DATABASE_WAL_ENABLED = os.getenv("DATABASE_WAL_ENABLED", "true").lower() == "true"

# ============================================================================
# SSH CONFIGURATION (for SSH tunneling)
# ============================================================================

SSH_USER = os.getenv("SSH_USER", "openhabian")
SSH_HOST_PRIMARY = os.getenv("SSH_HOST_PRIMARY", "192.168.30.137")
SSH_HOST_BACKUP = os.getenv("SSH_HOST_BACKUP", "192.168.3.25")
SSH_PORT = int(os.getenv("SSH_PORT", "22"))
SSH_REMOTE_PORT = int(os.getenv("SSH_REMOTE_PORT", "8001"))
SSH_LOCAL_PORT = int(os.getenv("SSH_LOCAL_PORT", "8001"))

# ============================================================================
# ALERTS & NOTIFICATIONS
# ============================================================================

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
ALERT_CRITICAL_THRESHOLD = float(os.getenv("ALERT_CRITICAL_THRESHOLD", "2.0"))  # percent change

# ============================================================================
# VALIDATION HELPERS
# ============================================================================

def get_primary_url() -> str:
    """Get PRIMARY API URL, falling back to fallback if env var not set."""
    return PRIMARY_API_URL or "http://127.0.0.1:8001"


def get_backup_url() -> str:
    """Get BACKUP API URL, falling back to default if env var not set."""
    return BACKUP_API_URL or "http://192.168.3.25:8002"


def validate_urls() -> bool:
    """Validate that PRIMARY and BACKUP URLs are different."""
    if get_primary_url() == get_backup_url():
        raise ValueError(
            f"PRIMARY and BACKUP URLs must be different. "
            f"Got PRIMARY={get_primary_url()}, BACKUP={get_backup_url()}"
        )
    return True
