"""FastAPI startup and shutdown lifecycle management."""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from backend.core import constants

# Load .env file if it exists (python-dotenv alternative)
env_file = Path.cwd() / ".env"
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                key, _, value = line.partition("=")
                if key and key not in os.environ:
                    os.environ[key] = value.strip('"').strip("'")

logger = logging.getLogger(__name__)


def validate_environment_configuration() -> None:
    """Validate all environment variables and configuration at startup.

    Raises ValueError if any critical configuration is invalid.
    """
    errors = []

    # Validate URLs
    try:
        constants.validate_urls()
    except ValueError as e:
        errors.append(str(e))

    # Validate machine ID
    if constants.MACHINE_ID not in ["main", "backup"]:
        errors.append(f"MACHINE_ID must be 'main' or 'backup', got '{constants.MACHINE_ID}'")

    # Validate timeouts
    if constants.HEALTH_CHECK_TIMEOUT <= 0:
        errors.append(f"HEALTH_CHECK_TIMEOUT must be positive, got {constants.HEALTH_CHECK_TIMEOUT}")
    if constants.HEARTBEAT_CHECK_INTERVAL <= 0:
        errors.append(f"HEARTBEAT_CHECK_INTERVAL must be positive, got {constants.HEARTBEAT_CHECK_INTERVAL}")
    if constants.HEARTBEAT_FAILURE_THRESHOLD <= 0:
        errors.append(f"HEARTBEAT_FAILURE_THRESHOLD must be positive, got {constants.HEARTBEAT_FAILURE_THRESHOLD}")

    # Validate replication thresholds
    if constants.REPLICATION_LAG_WARNING_THRESHOLD <= 0:
        errors.append(f"REPLICATION_LAG_WARNING_THRESHOLD must be positive, got {constants.REPLICATION_LAG_WARNING_THRESHOLD}")
    if constants.REPLICATION_LAG_CRITICAL_THRESHOLD <= 0:
        errors.append(f"REPLICATION_LAG_CRITICAL_THRESHOLD must be positive, got {constants.REPLICATION_LAG_CRITICAL_THRESHOLD}")
    if constants.REPLICATION_LAG_CRITICAL_THRESHOLD < constants.REPLICATION_LAG_WARNING_THRESHOLD:
        errors.append(f"REPLICATION_LAG_CRITICAL_THRESHOLD ({constants.REPLICATION_LAG_CRITICAL_THRESHOLD}) must be >= WARNING threshold ({constants.REPLICATION_LAG_WARNING_THRESHOLD})")

    if errors:
        error_msg = "Environment configuration errors:\n  " + "\n  ".join(errors)
        logger.error(error_msg)
        raise ValueError(error_msg)

    logger.info(f"✅ Environment configuration validated ({len(vars(constants))} settings loaded)")


# Global tasks to manage
websocket_task = None
stream_task = None
simulator_task = None
autonomous_trader_task = None
sync_task = None
failover_task = None
heartbeat_task = None
systemd_watchdog_task = None
staleness_monitor_task = None
staleness_monitor = None
ws = None


async def systemd_watchdog_heartbeat():
    """Send WATCHDOG=1 notification to systemd every 20s.

    Systemd will auto-restart the service if this heartbeat stops for >30s.
    This prevents hung API processes from blocking recovery.
    """
    while True:
        try:
            import systemd.daemon
            systemd.daemon.notify("WATCHDOG=1")
            logger.debug("📍 Systemd watchdog heartbeat sent")
        except ImportError:
            # systemd not available, likely running outside systemd (dev/test)
            logger.debug("Systemd watchdog unavailable (running outside systemd)")
        except Exception as e:
            logger.warning(f"Failed to send systemd watchdog: {e}")

        await asyncio.sleep(20)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown."""
    global websocket_task, stream_task, simulator_task, autonomous_trader_task, sync_task, heartbeat_task, systemd_watchdog_task, staleness_monitor_task, staleness_monitor, ws

    logger.info("Starting crypto daytrading platform...")

    # Validate environment configuration first
    validate_environment_configuration()

    # ========== FR-015: Database Authority Recovery ==========
    # Auto-detect and sync stale database before trading starts
    logger.info("🔍 Checking database authority (FR-015)...")
    try:
        from backend.core.database_authority import DatabaseAuthority
        from backend.core.database_sync import DatabaseSyncer
        from backend.core import constants as db_constants

        authority = DatabaseAuthority(divergence_threshold_seconds=60)

        # Get database paths from environment or defaults
        primary_db = os.getenv("PRIMARY_DB_PATH", "/home/vali/projects/crypto-daytrading/data/trading.db")
        backup_db = os.getenv("BACKUP_DB_PATH", "/home/claude/crypto-daytrading/data/trading.db")

        result = authority.detect_authority(primary_db, backup_db)
        logger.info(f"Authority result: {result['authoritative']} - {result['reason']}")

        # If divergence detected, auto-sync
        if result['sync_needed']:
            logger.warning(f"🚨 Database divergence detected: {result['divergence_seconds']:.1f}s")

            syncer = DatabaseSyncer(
                remote_user="claude",
                remote_host="192.168.3.25"  # BACKUP host
            )

            if result['authoritative'] == 'primary':
                # PRIMARY is authoritative, sync to BACKUP
                logger.info("Syncing PRIMARY → BACKUP")
                sync_result = syncer.sync_from_authoritative(primary_db, backup_db)
            elif result['authoritative'] == 'backup':
                # BACKUP is authoritative, sync to PRIMARY
                logger.info("Syncing BACKUP → PRIMARY")
                sync_result = syncer.sync_from_authoritative(backup_db, primary_db)
            else:
                sync_result = {'success': False, 'error': 'Unknown authority'}

            if sync_result['success']:
                logger.info(f"✅ Database recovery complete: {sync_result['time_seconds']:.2f}s, "
                           f"{sync_result['bytes_copied']} bytes")
            else:
                logger.error(f"❌ Database sync failed: {sync_result['error']}")
                # Don't crash, continue with potentially diverged state
                # Manual intervention can fix this later
        else:
            logger.info("✅ Databases in sync (or acceptable clock drift)")

    except Exception as e:
        logger.error(f"Database authority check failed: {e}")
        # Non-critical error, continue anyway
    # ========== End FR-015 ==========

    # Import essential initialization functions
    from backend.exchange.paper_trading import init_paper_trading
    from backend.exchange.binance_stream import init_stream_client
    from backend.exchange.websocket_manager import init_manager
    from backend.exchange.websocket_staleness_monitor import WebSocketStalenessMonitor
    from backend.trading.autonomous_trader import init_autonomous_trader, get_autonomous_trader
    from backend.trading.autonomous_trader import TradingConfig
    from backend.execution.smart_executor import init_smart_executor
    from backend.core.circuit_breaker_v2 import init_circuit_breaker

    # Validate HA configuration
    try:
        constants.validate_urls()
        logger.info(f"HA Configuration validated: PRIMARY={constants.PRIMARY_API_URL}, BACKUP={constants.BACKUP_API_URL}")
    except ValueError as e:
        logger.error(f"HA Configuration error: {e}")
        raise

    # Initialize core components
    initial_capital = float(os.getenv("INITIAL_CAPITAL", "1000"))
    init_paper_trading(starting_capital=initial_capital)
    logger.info(f"Paper trading engine initialized with €{initial_capital:.2f}")

    # Initialize smart executor
    init_smart_executor()
    logger.info("Smart executor initialized")

    # Initialize new circuit breaker v2 (intelligent, not just halt)
    try:
        circuit_breaker = init_circuit_breaker(
            failure_threshold=5,      # More tolerant than before
            recover_timeout=20,       # Faster recovery
        )
        logger.info("✅ Circuit breaker v2 initialized (intelligent degradation mode)")
    except Exception as e:
        logger.error(f"Failed to initialize circuit breaker: {e}")

    # Initialize new WebSocket manager (with automatic recovery + REST fallback)
    ws_manager = None
    try:
        ws_manager = await init_manager(symbols=["BTCUSDT", "ETHUSDT", "BNBUSDT"])
        logger.info("✅ WebSocket manager initialized (automatic recovery + REST fallback)")
    except Exception as e:
        logger.error(f"Failed to initialize WebSocket manager: {e}")

    # SKILL #1: Initialize WebSocket staleness detection + auto-reconnect
    if ws_manager:
        try:
            staleness_monitor = WebSocketStalenessMonitor(ws_manager)
            # Register callback to detect price updates
            ws_manager.register_callback(
                lambda symbol, price: staleness_monitor.on_price_update(symbol)
            )
            # Start monitor in background
            staleness_monitor_task = asyncio.create_task(
                staleness_monitor.start_monitoring(["BTCUSDT", "ETHUSDT", "BNBUSDT"])
            )
            logger.info("✅ WebSocket staleness monitor initialized (SKILL #1: Early detection + auto-reconnect)")
        except Exception as e:
            logger.error(f"Failed to initialize staleness monitor: {e}")
            staleness_monitor = None

    # Initialize Binance stream (legacy, kept for backward compatibility)
    try:
        stream_client = await init_stream_client()
        logger.info("Binance stream client initialized (legacy)")

        async def on_price_update(symbol: str, data: dict) -> None:
            """Handle price updates from Binance stream."""
            try:
                if "k" in data:
                    price = float(data["k"]["c"])
                elif "p" in data:
                    price = float(data["p"])
                else:
                    return
                logger.debug(f"{symbol}: ${price:.2f}")
            except Exception as e:
                logger.error(f"Error processing price update: {e}")

        # Subscribe to streams
        pairs = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
        for pair in pairs:
            stream_name = f"{pair.lower()}@kline_1m"
            stream_client.subscribe(stream_name, on_price_update)

        global stream_task
        stream_task = asyncio.create_task(stream_client.connect())
    except Exception as e:
        logger.error(f"Failed to initialize Binance stream: {e}")

    # Initialize autonomous trader (disabled on BACKUP)
    machine_id = os.getenv("MACHINE_ID", "main")
    if machine_id == "backup":
        logger.info("⏸️  BACKUP mode: Autonomous trading DISABLED (will enable on failover)")
    else:
        try:
            trader = init_autonomous_trader()
            global autonomous_trader_task
            autonomous_trader_task = asyncio.create_task(trader.start())
            logger.info("Autonomous trader initialized")
        except Exception as e:
            logger.error(f"Failed to initialize autonomous trader: {e}")

    # Add sync task for PRIMARY or failover monitor for BACKUP

    async def sync_to_backup():
        """PRIMARY: Periodically sync state to BACKUP with health monitoring."""
        import httpx
        from backend.exchange.paper_trading import get_paper_trading

        consecutive_failures = 0
        backup_last_healthy = False

        while True:
            try:
                await asyncio.sleep(constants.STATE_SYNC_INTERVAL)
                engine = get_paper_trading()
                if not engine:
                    continue

                # Step 1: Check BACKUP health first
                backup_healthy = False
                try:
                    async with httpx.AsyncClient(timeout=constants.HEALTH_CHECK_TIMEOUT) as client:
                        health_resp = await client.get(f"{constants.BACKUP_API_URL}/api/health")
                        backup_healthy = health_resp.status_code == 200
                except Exception as health_err:
                    backup_healthy = False

                # Log health status change at INFO level for visibility
                if backup_healthy != backup_last_healthy:
                    if backup_healthy:
                        logger.info(f"✅ BACKUP health restored - sync resuming")
                        consecutive_failures = 0
                    else:
                        logger.warning(f"⚠️  BACKUP unhealthy (connection failed)")
                    backup_last_healthy = backup_healthy

                if not backup_healthy:
                    consecutive_failures += 1
                    if consecutive_failures % 6 == 0:  # Log every 30 seconds at default 5s interval
                        logger.warning(f"🔴 BACKUP unhealthy for {consecutive_failures * constants.STATE_SYNC_INTERVAL}s - systemd may have crashed")
                    continue

                # Step 2: Sync state only if BACKUP is healthy
                try:
                    positions = engine.get_positions()
                    # get_positions() already returns only open positions, no filtering needed
                    open_positions = [p for p in positions if isinstance(p, dict)]
                except Exception as pos_err:
                    logger.debug(f"Failed to get positions: {pos_err}")
                    open_positions = []

                # Include configuration in state sync (critical blocker #2)
                from backend.core.runtime_config import get_config_manager
                from backend.core.ha_deduplication import get_ha_deduplicator

                config_manager = get_config_manager()
                current_config = config_manager.get_config()
                deduplicator = get_ha_deduplicator()

                state = {
                    "cash": engine.cash,
                    "total_pnl": engine.total_pnl,
                    "positions": open_positions,
                    "config": {
                        "entry_threshold": current_config.entry_threshold,
                        "exit_profit_target": current_config.exit_profit_target,
                        "exit_stop_loss": current_config.exit_stop_loss,
                        "max_positions": current_config.max_positions,
                        "position_size_pct": current_config.position_size_pct,
                        "max_daily_loss_pct": current_config.max_daily_loss_pct,
                        "max_position_loss_pct": current_config.max_position_loss_pct,
                        "enabled": current_config.enabled,
                        "symbols": current_config.symbols
                    },
                    "deduplicator_state": {
                        "seen_orders": {k: v.isoformat() for k, v in deduplicator.seen_orders.items()}
                    }
                }

                # Try HTTP sync first
                sync_succeeded = False
                async with httpx.AsyncClient(timeout=constants.HEALTH_CHECK_TIMEOUT) as client:
                    try:
                        resp = await client.post(f"{constants.BACKUP_API_URL}/api/ha/sync-from-primary", json=state)
                        if resp.status_code == 200:
                            logger.debug(f"✅ Synced to BACKUP (HTTP): {len(state['positions'])} positions, €{state['cash']:.2f} cash")
                            sync_succeeded = True
                            consecutive_failures = 0
                    except Exception as http_err:
                        logger.debug(f"HTTP sync failed: {http_err}")

                # Fallback to SSH tunnel if HTTP failed
                if not sync_succeeded and backup_healthy:
                    logger.info("🌐 Attempting SSH tunnel fallback sync...")
                    from backend.core.ssh_tunnel_sync import SSHTunnelSync
                    ssh_sync = SSHTunnelSync()
                    if await ssh_sync.sync_via_ssh_tunnel(state):
                        logger.info(f"✅ Synced to BACKUP (SSH tunnel): {len(state['positions'])} positions, €{state['cash']:.2f} cash")
                        sync_succeeded = True
                        consecutive_failures = 0
                    else:
                        consecutive_failures += 1
                        logger.warning(f"⚠️ Both HTTP and SSH sync failed")

            except Exception as e:
                consecutive_failures += 1
                if consecutive_failures == 1:
                    logger.warning(f"⚠️  BACKUP sync error: {e}")
                elif consecutive_failures % 10 == 0:
                    logger.warning(f"🔴 BACKUP sync error recurring ({consecutive_failures} failures): {e}")

    async def failover_monitor():
        """BACKUP: Monitor PRIMARY health via explicit heartbeat (Skill #3) + HTTP, enable trading on failure."""
        import httpx
        from backend.trading.autonomous_trader import init_autonomous_trader, get_autonomous_trader
        from backend.core.heartbeat import init_heartbeat_monitor, get_heartbeat_monitor
        from backend.failover.explicit_heartbeat import init_explicit_heartbeat_monitor

        trader = None

        # Initialize old heartbeat monitor (backward compatibility)
        monitor = init_heartbeat_monitor(
            check_interval=constants.HEARTBEAT_CHECK_INTERVAL,
            failure_threshold=constants.HEARTBEAT_FAILURE_THRESHOLD
        )
        logger.info(
            f"💓 BACKUP heartbeat monitor initialized "
            f"({constants.HEARTBEAT_FAILURE_THRESHOLD} misses = {constants.HEARTBEAT_TIMEOUT_SECONDS}s timeout)"
        )

        # NEW: Explicit heartbeat monitor (Skill #3) - primary detection method
        explicit_monitor = init_explicit_heartbeat_monitor()
        await explicit_monitor.start()
        logger.info(
            f"💓 BACKUP explicit heartbeat monitor started (Skill #3) "
            f"(3 misses = 6s failover, interval: 1s)"
        )

        while True:
            try:
                await asyncio.sleep(1)  # Check every second for responsive failover

                # Priority 1: Check explicit heartbeat (Skill #3, most reliable)
                explicit_failed = explicit_monitor.is_primary_failed()

                # Priority 2: Check old heartbeat (backward compatibility)
                primary_failed = monitor.check_timeout()

                # Priority 3: Fallback to HTTP health check
                try:
                    async with httpx.AsyncClient(timeout=constants.HEALTH_CHECK_TIMEOUT) as client:
                        resp = await client.get(f"{constants.PRIMARY_API_URL}/api/health")
                        primary_healthy = resp.status_code == 200
                except Exception as e:
                    logger.debug(f"PRIMARY health check failed: {e}")
                    primary_healthy = False

                # Use explicit heartbeat detection if available, fall back to other methods
                should_failover = explicit_failed or primary_failed or not primary_healthy

                # Trigger failover if PRIMARY failed
                if should_failover and not (trader and trader.running):
                    failover_reason = []
                    if explicit_failed:
                        failover_reason.append("Explicit heartbeat: 3+ misses")
                    if primary_failed:
                        failover_reason.append("Old heartbeat timeout")
                    if not primary_healthy:
                        failover_reason.append("HTTP health check failed")

                    logger.critical(
                        f"🚨 PRIMARY FAILURE DETECTED (Skill #3) - {', '.join(failover_reason)} - "
                        "Enabling BACKUP trading"
                    )
                    try:
                        trader = init_autonomous_trader()
                        global autonomous_trader_task
                        autonomous_trader_task = asyncio.create_task(trader.start())
                        logger.info("✅ BACKUP autonomous trader ACTIVATED (PRIMARY promoted to BACKUP)")
                    except Exception as e:
                        logger.error(f"Failed to activate BACKUP trader: {e}")

                # Disable trading if PRIMARY recovered (all checks healthy)
                elif not should_failover and (trader and trader.running):
                    logger.info("✅ PRIMARY RECOVERED - Disabling BACKUP trading")
                    try:
                        if trader:
                            await trader.stop()
                        if autonomous_trader_task:
                            autonomous_trader_task.cancel()
                        logger.info("BACKUP autonomous trader DEACTIVATED (PRIMARY demoted to PRIMARY)")
                    except Exception as e:
                        logger.error(f"Failed to deactivate BACKUP trader: {e}")

            except Exception as e:
                logger.error(f"Failover monitor error: {e}")

    # Heartbeat sender (PRIMARY) and heartbeat monitor (BACKUP)
    async def heartbeat_sender():
        """PRIMARY: Send heartbeat to BACKUP at configured interval."""
        from backend.core.heartbeat import init_heartbeat_sender
        from backend.failover.explicit_heartbeat import init_explicit_heartbeat_sender

        # Old heartbeat (for backward compatibility)
        sender = init_heartbeat_sender(constants.BACKUP_API_URL, interval=constants.HEARTBEAT_CHECK_INTERVAL)
        await sender.start()

        # NEW: Explicit heartbeat (Skill #3) - more reliable, faster failover
        explicit_sender = init_explicit_heartbeat_sender(constants.BACKUP_API_URL)
        await explicit_sender.start()

    if constants.IS_PRIMARY:
        global sync_task, heartbeat_task
        sync_task = asyncio.create_task(sync_to_backup())
        logger.info(f"📤 PRIMARY sync task started (→ {constants.BACKUP_API_URL} every {constants.STATE_SYNC_INTERVAL}s)")

        heartbeat_task = asyncio.create_task(heartbeat_sender())
        logger.info(
            f"💓 PRIMARY heartbeat sender started "
            f"(→ {constants.BACKUP_API_URL} every {constants.HEARTBEAT_CHECK_INTERVAL}s)"
        )
        logger.info(
            f"💓 PRIMARY explicit heartbeat (Skill #3) started "
            f"(→ {constants.BACKUP_API_URL} every 2.0s, threshold: 3 misses = 6s failover)"
        )
    else:
        global failover_task
        failover_task = asyncio.create_task(failover_monitor())
        logger.info(
            f"📡 BACKUP failover monitor started "
            f"(check every {constants.HEARTBEAT_CHECK_INTERVAL}s with heartbeat detection)"
        )

    # Start systemd watchdog heartbeat (Skill #4 hardening)
    global systemd_watchdog_task
    systemd_watchdog_task = asyncio.create_task(systemd_watchdog_heartbeat())
    logger.info("⏰ Systemd watchdog heartbeat started (every 20s, timeout 30s)")

    # Start process health monitor (Skill #2 hardening)
    try:
        from backend.core.process_health_monitor import init_process_health_monitor
        process_monitor = init_process_health_monitor()
        await process_monitor.start()
        logger.info("📊 Process health monitor started (Skill #2 - detects stuck processes)")
    except Exception as e:
        logger.warning(f"Failed to start process health monitor: {e}")

    # Initialize circuit breaker recovery (Skill #5 hardening)
    try:
        from backend.core.circuit_breaker_recovery import init_circuit_breaker_recovery
        cb_recovery = init_circuit_breaker_recovery()
        logger.info("🔄 Circuit breaker recovery initialized (Skill #5 - manual reset capability)")
    except Exception as e:
        logger.warning(f"Failed to initialize CB recovery: {e}")

    # Signal to systemd that we're ready (for Type=notify)
    try:
        import systemd.daemon
        systemd.daemon.notify("READY=1")
        logger.info("📢 Systemd READY signal sent")
    except (ImportError, Exception):
        pass  # Not running under systemd or signal failed, ignore

    # Startup complete
    logger.info("✅ Crypto daytrading platform started successfully")

    yield

    # Shutdown
    logger.info("Shutting down crypto daytrading platform...")

    # Stop tasks
    if autonomous_trader_task:
        try:
            trader = get_autonomous_trader()
            await trader.stop()
            await autonomous_trader_task
        except:
            pass

    if stream_task:
        stream_task.cancel()

    if websocket_task:
        websocket_task.cancel()

    if staleness_monitor_task:
        staleness_monitor_task.cancel()

    if simulator_task:
        simulator_task.cancel()

    if sync_task:
        sync_task.cancel()

    if failover_task:
        failover_task.cancel()

    if heartbeat_task:
        heartbeat_task.cancel()

    if systemd_watchdog_task:
        systemd_watchdog_task.cancel()

    logger.info("✅ Crypto daytrading platform shut down complete")


def get_paper_trader():
    """Get paper trading engine instance."""
    from backend.exchange.paper_trading import get_paper_trading
    return get_paper_trading()
