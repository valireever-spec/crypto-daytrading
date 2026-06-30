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
ws = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown."""
    global websocket_task, stream_task, simulator_task, autonomous_trader_task, sync_task, heartbeat_task, ws

    logger.info("Starting crypto daytrading platform...")

    # Validate environment configuration first
    validate_environment_configuration()

    # Import essential initialization functions
    from backend.exchange.paper_trading import init_paper_trading
    from backend.exchange.binance_stream import init_stream_client
    from backend.trading.autonomous_trader import init_autonomous_trader, get_autonomous_trader
    from backend.trading.autonomous_trader import TradingConfig
    from backend.execution.smart_executor import init_smart_executor

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

    # Initialize Binance stream
    try:
        stream_client = await init_stream_client()
        logger.info("Binance stream client initialized")

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
                    open_positions = [
                        p for p in positions
                        if isinstance(p, dict) and p.get("status") == "open"
                    ]
                except Exception as pos_err:
                    logger.debug(f"Failed to filter positions: {pos_err}")
                    open_positions = []

                state = {
                    "cash": engine.cash,
                    "total_pnl": engine.total_pnl,
                    "positions": open_positions
                }

                async with httpx.AsyncClient(timeout=constants.HEALTH_CHECK_TIMEOUT) as client:
                    resp = await client.post(f"{constants.BACKUP_API_URL}/api/ha/sync-from-primary", json=state)
                    if resp.status_code == 200:
                        logger.debug(f"✅ Synced to BACKUP: {len(state['positions'])} positions, €{state['cash']:.2f} cash")
                        consecutive_failures = 0
                    else:
                        consecutive_failures += 1
                        logger.warning(f"⚠️  BACKUP sync POST failed: {resp.status_code}")

            except Exception as e:
                consecutive_failures += 1
                if consecutive_failures == 1:
                    logger.warning(f"⚠️  BACKUP sync error: {e}")
                elif consecutive_failures % 10 == 0:
                    logger.warning(f"🔴 BACKUP sync error recurring ({consecutive_failures} failures): {e}")

    async def failover_monitor():
        """BACKUP: Monitor PRIMARY health via heartbeat + HTTP, enable trading on failure."""
        import httpx
        from backend.trading.autonomous_trader import init_autonomous_trader, get_autonomous_trader
        from backend.core.heartbeat import init_heartbeat_monitor, get_heartbeat_monitor

        trader = None

        # Initialize heartbeat monitor using config constants
        monitor = init_heartbeat_monitor(
            check_interval=constants.HEARTBEAT_CHECK_INTERVAL,
            failure_threshold=constants.HEARTBEAT_FAILURE_THRESHOLD
        )
        logger.info(
            f"💓 BACKUP heartbeat monitor initialized "
            f"({constants.HEARTBEAT_FAILURE_THRESHOLD} misses = {constants.HEARTBEAT_TIMEOUT_SECONDS}s timeout)"
        )

        while True:
            try:
                await asyncio.sleep(constants.HEARTBEAT_CHECK_INTERVAL)

                # Check heartbeat timeout
                primary_failed = monitor.check_timeout()

                # Fallback: Check HTTP health via PRIMARY_API_URL
                try:
                    async with httpx.AsyncClient(timeout=constants.HEALTH_CHECK_TIMEOUT) as client:
                        resp = await client.get(f"{constants.PRIMARY_API_URL}/api/health")
                        primary_healthy = resp.status_code == 200
                except Exception as e:
                    logger.debug(f"PRIMARY health check failed: {e}")
                    primary_healthy = False

                # Trigger failover if PRIMARY failed (either heartbeat or HTTP check)
                if (primary_failed or not primary_healthy) and not (trader and trader.running):
                    logger.critical(
                        "🚨 PRIMARY FAILURE DETECTED - "
                        f"Heartbeat: {primary_failed}, HTTP: {not primary_healthy} - "
                        "Enabling BACKUP trading"
                    )
                    try:
                        trader = init_autonomous_trader()
                        global autonomous_trader_task
                        autonomous_trader_task = asyncio.create_task(trader.start())
                        logger.info("✅ BACKUP autonomous trader ACTIVATED")
                    except Exception as e:
                        logger.error(f"Failed to activate BACKUP trader: {e}")

                # Disable trading if PRIMARY recovered (both heartbeat and HTTP healthy)
                elif primary_healthy and (trader and trader.running):
                    logger.info("✅ PRIMARY RECOVERED - Disabling BACKUP trading")
                    try:
                        if trader:
                            await trader.stop()
                        if autonomous_trader_task:
                            autonomous_trader_task.cancel()
                        logger.info("BACKUP autonomous trader DEACTIVATED")
                    except Exception as e:
                        logger.error(f"Failed to deactivate BACKUP trader: {e}")

            except Exception as e:
                logger.error(f"Failover monitor error: {e}")

    # Heartbeat sender (PRIMARY) and heartbeat monitor (BACKUP)
    async def heartbeat_sender():
        """PRIMARY: Send heartbeat to BACKUP at configured interval."""
        from backend.core.heartbeat import init_heartbeat_sender

        sender = init_heartbeat_sender(constants.BACKUP_API_URL, interval=constants.HEARTBEAT_CHECK_INTERVAL)
        await sender.start()

    if constants.IS_PRIMARY:
        global sync_task, heartbeat_task
        sync_task = asyncio.create_task(sync_to_backup())
        logger.info(f"📤 PRIMARY sync task started (→ {constants.BACKUP_API_URL} every {constants.STATE_SYNC_INTERVAL}s)")

        heartbeat_task = asyncio.create_task(heartbeat_sender())
        logger.info(
            f"💓 PRIMARY heartbeat sender started "
            f"(→ {constants.BACKUP_API_URL} every {constants.HEARTBEAT_CHECK_INTERVAL}s)"
        )
    else:
        global failover_task
        failover_task = asyncio.create_task(failover_monitor())
        logger.info(
            f"📡 BACKUP failover monitor started "
            f"(check every {constants.HEARTBEAT_CHECK_INTERVAL}s with heartbeat detection)"
        )

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

    if simulator_task:
        simulator_task.cancel()

    if sync_task:
        sync_task.cancel()

    if failover_task:
        failover_task.cancel()

    if heartbeat_task:
        heartbeat_task.cancel()

    logger.info("✅ Crypto daytrading platform shut down complete")


def get_paper_trader():
    """Get paper trading engine instance."""
    from backend.exchange.paper_trading import get_paper_trading
    return get_paper_trading()
