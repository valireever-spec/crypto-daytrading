"""FastAPI startup and shutdown lifecycle management."""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

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

    # Import essential initialization functions
    from backend.exchange.paper_trading import init_paper_trading
    from backend.exchange.binance_stream import init_stream_client
    from backend.trading.autonomous_trader import init_autonomous_trader, get_autonomous_trader
    from backend.trading.autonomous_trader import TradingConfig

    # Validate HA configuration
    primary_url = os.getenv("PRIMARY_API_URL", "http://127.0.0.1:8001")
    backup_url = os.getenv("BACKUP_API_URL", "http://192.168.3.25:8002")
    if primary_url == backup_url:
        logger.error(f"ERROR: PRIMARY and BACKUP URLs are identical: {primary_url}")
        raise ValueError("PRIMARY_API_URL and BACKUP_API_URL must be different")
    logger.info(f"HA Configuration validated: PRIMARY={primary_url}, BACKUP={backup_url}")

    # Initialize core components
    initial_capital = float(os.getenv("INITIAL_CAPITAL", "1000"))
    init_paper_trading(starting_capital=initial_capital)
    logger.info(f"Paper trading engine initialized with €{initial_capital:.2f}")

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
    machine_id = os.getenv("MACHINE_ID", "main")
    backup_url = os.getenv("BACKUP_API_URL", "http://192.168.3.25:8002")

    async def sync_to_backup():
        """PRIMARY: Periodically sync state to BACKUP."""
        import httpx
        from backend.exchange.paper_trading import get_paper_trading

        while True:
            try:
                await asyncio.sleep(5)  # Sync every 5 seconds
                engine = get_paper_trading()
                if not engine:
                    continue

                state = {
                    "cash": engine.cash,
                    "total_pnl": engine.total_pnl,
                    "positions": [p for p in engine.get_positions() if p["status"] == "open"]
                }

                async with httpx.AsyncClient(timeout=3) as client:
                    resp = await client.post(f"{backup_url}/api/ha/sync-from-primary", json=state)
                    if resp.status_code == 200:
                        logger.debug(f"✅ Synced to BACKUP: {len(state['positions'])} positions, €{state['cash']:.2f} cash")
                    else:
                        logger.warning(f"⚠️  BACKUP sync failed: {resp.status_code}")
            except Exception as e:
                logger.debug(f"BACKUP sync error (will retry): {e}")

    async def failover_monitor():
        """BACKUP: Monitor PRIMARY health via heartbeat + HTTP, enable trading on failure."""
        import httpx
        from backend.trading.autonomous_trader import init_autonomous_trader, get_autonomous_trader
        from backend.core.heartbeat import init_heartbeat_monitor, get_heartbeat_monitor

        primary_url = os.getenv("PRIMARY_API_URL", "http://127.0.0.1:8001")
        trader = None

        # Initialize heartbeat monitor (5s checks, 3 misses = 15s timeout)
        monitor = init_heartbeat_monitor(check_interval=5, failure_threshold=3)
        logger.info("💓 BACKUP heartbeat monitor initialized (3 misses = 15s timeout)")

        while True:
            try:
                await asyncio.sleep(5)  # Check every 5 seconds (matches heartbeat interval)

                # Check heartbeat timeout (PRIMARY sends heartbeat every 5s)
                primary_failed = monitor.check_timeout()

                # Fallback: Check HTTP health (in case heartbeat isn't implemented yet)
                try:
                    async with httpx.AsyncClient(timeout=2) as client:
                        resp = await client.get(f"{primary_url}/api/health")
                        primary_healthy = resp.status_code == 200
                except:
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
        """PRIMARY: Send heartbeat to BACKUP every 5 seconds."""
        from backend.core.heartbeat import init_heartbeat_sender

        backup_url = os.getenv("BACKUP_API_URL", "http://192.168.3.25:8002")
        sender = init_heartbeat_sender(backup_url, interval=5)
        await sender.start()

    if machine_id == "main":
        global sync_task, heartbeat_task
        sync_task = asyncio.create_task(sync_to_backup())
        logger.info("📤 PRIMARY sync task started (→ BACKUP every 5s)")

        heartbeat_task = asyncio.create_task(heartbeat_sender())
        logger.info(f"💓 PRIMARY heartbeat sender started (→ {os.getenv('BACKUP_API_URL', 'http://192.168.3.25:8002')} every 5s)")
    else:
        global failover_task
        failover_task = asyncio.create_task(failover_monitor())
        logger.info("📡 BACKUP failover monitor started (check every 5s with heartbeat detection)")

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
