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
                logger.warning(
                    f"Critical env var not set: {var} (using hardcoded default)"
                )

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
        """Sync config to backup machine via SSH with automatic failover.

        ARCHITECTURE (HA with Reverse SSH Tunnel):
        ═══════════════════════════════════════════════════════════════════════
        - Primary machine (internal): 192.168.30.137:8001
        - Backup machine (internal): 192.168.3.25:8002 [NOT internet-exposed]
        - Internet access: Primary ↔ r33v3r.ddns.net (reverse SSH tunnel)

        Sync Strategy:
        1. Try direct LAN connection: ssh backup (192.168.3.25)
        2. If fails: Fall back to reverse tunnel: ssh r33v3r.ddns.net
        3. Both use passwordless auth (openhab_claude key via ~/.ssh/config)
        4. Retry with exponential backoff (1s, 2s, 4s)

        Returns:
            bool: True if sync successful, False if all attempts fail
        """
        import subprocess
        import time

        backup_remote_path = "/home/claude/crypto-daytrading/.env"

        # Convert config to .env format
        env_lines = ConfigManager._config_to_env_lines(config)
        env_content = "\n".join(env_lines)

        # Two connection methods: LAN first, then reverse SSH tunnel
        ssh_methods = [
            ("backup", "Direct LAN connection (192.168.3.25)"),
            ("r33v3r.ddns.net", "Reverse SSH tunnel (internet fallback)"),
        ]

        max_retries = 3
        retry_delays = [1, 2, 4]  # exponential backoff: 1s, 2s, 4s

        for method_idx, (ssh_host, method_desc) in enumerate(ssh_methods):
            logger.info(f"Attempting SSH sync via {method_desc}...")

            for attempt in range(max_retries):
                try:
                    # SSH command to update .env on backup - use full path to ssh
                    ssh_cmd = ["/usr/bin/ssh", ssh_host, f"cat > {backup_remote_path}"]

                    result = subprocess.run(
                        ssh_cmd,
                        input=env_content,
                        timeout=10,
                        capture_output=True,
                        text=True
                    )

                    if result.returncode == 0:
                        logger.info(f"✅ Synced config to backup via {method_desc} ({ssh_host})")
                        # Also trigger backup API reload if possible
                        ConfigManager._trigger_backup_reload()
                        return True
                    else:
                        logger.warning(
                            f"SSH sync via {method_desc} attempt {attempt + 1}/{max_retries} failed: {result.stderr}"
                        )

                except subprocess.TimeoutExpired:
                    logger.warning(
                        f"SSH sync via {method_desc} attempt {attempt + 1}/{max_retries} timed out"
                    )
                except Exception as e:
                    logger.warning(
                        f"SSH sync via {method_desc} attempt {attempt + 1}/{max_retries} failed: {e}"
                    )

                # Retry with exponential backoff (except on last attempt of this method)
                if attempt < max_retries - 1:
                    delay = retry_delays[attempt]
                    logger.info(f"Retrying via {method_desc} in {delay}s...")
                    time.sleep(delay)

            # If this method failed, try next method before giving up
            if method_idx < len(ssh_methods) - 1:
                logger.info(f"Direct LAN failed, trying reverse SSH tunnel as fallback...")
                time.sleep(2)  # Brief pause before trying internet route

        logger.error(f"SSH backup sync failed via all methods after {max_retries} attempts each")
        return False

    @staticmethod
    def _config_to_env_lines(config: Dict[str, Any]) -> list:
        """Convert trading config dict to .env format lines.

        STANDARDIZED: All values stored as percentages (e.g., 2.5 = 2.5%), not decimals.
        No conversion needed - values are already in correct format.
        """
        env_lines = [
            "# Trading Configuration - SOURCE OF TRUTH FOR BOTH MACHINES",
            "TRADING_MODE=paper",
            f"INITIAL_CAPITAL={config.get('initial_capital', 10000.0)}",
            "",
            "# 9 Adjustable Parameters (critical for HA sync)",
            "# IMPORTANT: All percentages stored as percentages (e.g., 2.5 = 2.5%), NOT decimals",
            f"ENTRY_THRESHOLD={config.get('entry_threshold', 60.0)}",
            f"POSITION_SIZE_PCT={config.get('position_size_pct', 2.5)}",
            f"MAX_POSITIONS={config.get('max_positions', 8)}",
            f"EXIT_STOP_LOSS={config.get('exit_stop_loss', 3.0)}",
            f"EXIT_PROFIT_TARGET={config.get('exit_profit_target', 4.5)}",
            f"QUALITY_GATE_ENTRY={config.get('quality_gate_entry', 90.0)}",
            f"QUALITY_GATE_EXIT={config.get('quality_gate_exit', 60.0)}",
            f"LOOP_SLEEP_SECONDS={config.get('loop_sleep_seconds', 10.0)}",
            f"MAX_DAILY_LOSS_PCT={config.get('max_daily_loss_pct', 5.0)}",
        ]
        return env_lines

    @staticmethod
    def _trigger_backup_reload() -> None:
        """Attempt to trigger backup API reload via SSH (best-effort).

        Uses SSH alias 'backup' from ~/.ssh/config for passwordless auth.
        """
        try:
            # Use SSH alias for passwordless authentication
            ssh_cmd = "ssh backup 'pkill -f \"uvicorn.*8002\" || true; sleep 2; cd ~/crypto-daytrading && source venv/bin/activate && nohup python -m uvicorn backend.api.main:app --host 0.0.0.0 --port 8002 > logs/api.log 2>&1 &'"
            subprocess.run(
                ssh_cmd,
                shell=True,
                timeout=15,
                capture_output=True,
            )
            logger.info("Triggered backup API reload via SSH (backup alias)")
        except Exception as e:
            logger.debug(f"Could not trigger backup reload (non-critical): {e}")

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
                logger.warning(
                    f"Could not get config from backup: HTTP {response.status_code}"
                )
                return None
        except Exception as e:
            logger.warning(f"Could not reach backup: {e}")
            return None
