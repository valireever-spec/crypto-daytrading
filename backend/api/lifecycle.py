"""FastAPI startup and shutdown lifecycle management."""

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

logger = logging.getLogger(__name__)

# Global tasks to manage
websocket_task = None
stream_task = None
simulator_task = None
autonomous_trader_task = None
sync_task = None
failover_task = None
ws = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown."""
    global websocket_task, stream_task, simulator_task, autonomous_trader_task, sync_task, ws

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
        """BACKUP: Monitor PRIMARY health, enable trading on failure."""
        import httpx
        from backend.trading.autonomous_trader import init_autonomous_trader, get_autonomous_trader

        primary_url = os.getenv("PRIMARY_API_URL", "http://127.0.0.1:8001")
        primary_failed = False
        trader = None

        while True:
            try:
                await asyncio.sleep(10)  # Check every 10 seconds

                # Check if PRIMARY is healthy
                try:
                    async with httpx.AsyncClient(timeout=2) as client:
                        resp = await client.get(f"{primary_url}/api/health")
                        primary_healthy = resp.status_code == 200
                except:
                    primary_healthy = False

                if not primary_healthy and not primary_failed:
                    # PRIMARY just failed, enable trading on BACKUP
                    logger.critical("🚨 PRIMARY FAILURE DETECTED - Enabling BACKUP trading")
                    try:
                        trader = init_autonomous_trader()
                        global autonomous_trader_task
                        autonomous_trader_task = asyncio.create_task(trader.start())
                        logger.info("✅ BACKUP autonomous trader ACTIVATED")
                        primary_failed = True
                    except Exception as e:
                        logger.error(f"Failed to activate BACKUP trader: {e}")

                elif primary_healthy and primary_failed:
                    # PRIMARY recovered, disable trading on BACKUP
                    logger.info("✅ PRIMARY RECOVERED - Disabling BACKUP trading")
                    try:
                        if trader:
                            await trader.stop()
                        if autonomous_trader_task:
                            autonomous_trader_task.cancel()
                        logger.info("BACKUP autonomous trader DEACTIVATED")
                        primary_failed = False
                    except Exception as e:
                        logger.error(f"Failed to deactivate BACKUP trader: {e}")

            except Exception as e:
                logger.error(f"Failover monitor error: {e}")

    if machine_id == "main":
        global sync_task
        sync_task = asyncio.create_task(sync_to_backup())
        logger.info("📤 PRIMARY sync task started (→ BACKUP every 5s)")
    else:
        global failover_task
        failover_task = asyncio.create_task(failover_monitor())
        logger.info("📡 BACKUP failover monitor started (check every 10s)")

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

    logger.info("✅ Crypto daytrading platform shut down complete")


def get_paper_trader():
    """Get paper trading engine instance."""
    from backend.exchange.paper_trading import get_paper_trading
    return get_paper_trading()
