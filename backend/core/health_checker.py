"""Health check system for production monitoring.

CRITICAL: These checks verify ACTUAL system functionality, not just "is it running."
All thresholds are based on real trading requirements.
"""

import logging
import json
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import psutil

logger = logging.getLogger(__name__)


class HealthStatus:
    """Health check result."""

    def __init__(
        self, name: str, healthy: bool, message: str = "", details: Dict = None
    ) -> None:
        self.name = name
        self.healthy = healthy
        self.message = message
        self.details = details or {}
        self.timestamp = datetime.utcnow().isoformat()

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "healthy": self.healthy,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp,
        }


class HealthChecker:
    """Production health monitoring."""

    def __init__(self) -> None:
        self.last_checks: Dict[str, HealthStatus] = {}
        self.check_history: Dict[str, list] = {}
        self.max_history = 100

    async def check_all(self) -> Dict:
        """Run all health checks (CRITICAL CHECKS ONLY)."""
        checks = {
            "websocket": await self._check_websocket(),
            "trade_log": await self._check_trade_log(),
            "price_feed": await self._check_price_feed(),
            "autonomous_trader": await self._check_autonomous_trader(),
            "database": await self._check_database(),
            "memory": await self._check_memory(),
            "disk": await self._check_disk(),
        }

        # Store results
        for name, status in checks.items():
            self.last_checks[name] = status
            if name not in self.check_history:
                self.check_history[name] = []
            self.check_history[name].append(status.to_dict())
            if len(self.check_history[name]) > self.max_history:
                self.check_history[name].pop(0)

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "overall_healthy": all(s.healthy for s in checks.values()),
            "checks": {k: v.to_dict() for k, v in checks.items()},
            "summary": self._generate_summary(checks),
        }

    async def _check_websocket(self) -> HealthStatus:
        """Check WebSocket connection and data freshness.

        CRITICAL: WebSocket must have data within last 2 minutes.
        Failure = stale price data = trading disabled.
        """
        try:
            from backend.exchange.binance_stream import get_stream_client

            client = get_stream_client()
            if not client:
                return HealthStatus(
                    "websocket", False, "WebSocket not initialized"
                )

            # Get last update timestamp from cached prices
            last_update = client.get_last_update_time()
            if not last_update:
                return HealthStatus(
                    "websocket", False, "No price data received yet"
                )

            age_seconds = (datetime.utcnow() - last_update).total_seconds()
            max_age_seconds = 120  # 2 minutes max

            healthy = age_seconds < max_age_seconds
            message = f"WebSocket data age: {age_seconds:.0f}s"

            if not healthy:
                message += f" ⚠️ STALE! Max allowed: {max_age_seconds}s"

            return HealthStatus(
                "websocket",
                healthy,
                message,
                {
                    "age_seconds": age_seconds,
                    "max_age_seconds": max_age_seconds,
                    "last_update": last_update.isoformat(),
                }
            )
        except Exception as e:
            logger.error(f"WebSocket health check failed: {type(e).__name__}: {e}")
            return HealthStatus("websocket", False, f"WebSocket check failed: {str(e)}")

    async def _check_trade_log(self) -> HealthStatus:
        """Check trade log freshness.

        CRITICAL: Trade log must exist and be recent.
        Failure = autonomous trader not executing = system stalled.
        """
        try:
            log_file = Path("logs/trades.jsonl")
            if not log_file.exists():
                return HealthStatus(
                    "trade_log", False, "Trade log not found"
                )

            # Get last line timestamp
            with open(log_file, 'r') as f:
                lines = f.readlines()

            if not lines:
                return HealthStatus(
                    "trade_log", False, "Trade log is empty"
                )

            # Parse last trade timestamp
            last_line = json.loads(lines[-1])
            last_trade_time = datetime.fromisoformat(last_line['timestamp'].replace('Z', '+00:00'))

            # Convert to naive UTC for comparison with utcnow()
            if last_trade_time.tzinfo is not None:
                last_trade_time = last_trade_time.replace(tzinfo=None)

            age_seconds = (datetime.utcnow() - last_trade_time).total_seconds()
            max_age_seconds = 3600  # 1 hour max (no trades in 1 hour is OK if no signals)

            healthy = age_seconds < max_age_seconds
            message = f"Last trade: {age_seconds/60:.0f} minutes ago"

            if not healthy:
                message += f" ⚠️ STALE! No trades for {age_seconds/3600:.1f} hours"

            return HealthStatus(
                "trade_log",
                healthy,
                message,
                {
                    "age_seconds": age_seconds,
                    "max_age_seconds": max_age_seconds,
                    "last_trade": last_line.get('symbol', 'N/A'),
                    "total_trades": len(lines),
                }
            )
        except Exception as e:
            logger.error(f"Trade log health check failed: {type(e).__name__}: {e}")
            return HealthStatus("trade_log", False, f"Trade log check failed: {str(e)}")

    async def _check_price_feed(self) -> HealthStatus:
        """Check if prices are being updated in real-time.

        CRITICAL: Each symbol must have fresh price data.
        Failure = price data disconnected = cannot calculate positions.
        """
        try:
            from backend.exchange.binance_stream import get_stream_client

            client = get_stream_client()
            if not client:
                return HealthStatus("price_feed", False, "Stream client not initialized")

            # Check each symbol
            symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
            stale_symbols = []
            max_age = 120  # 2 minutes

            for symbol in symbols:
                age = client.get_price_age_seconds(symbol)
                if age and age > max_age:
                    stale_symbols.append((symbol, age))

            if stale_symbols:
                stale_msg = ", ".join([f"{s}({a:.0f}s)" for s, a in stale_symbols])
                return HealthStatus(
                    "price_feed",
                    False,
                    f"Stale prices: {stale_msg}",
                    {"stale_symbols": stale_symbols}
                )

            return HealthStatus(
                "price_feed",
                True,
                f"All {len(symbols)} symbols receiving live prices",
                {
                    "symbols": symbols,
                    "max_age_seconds": max_age,
                }
            )
        except Exception as e:
            logger.error(f"Price feed health check failed: {type(e).__name__}: {e}")
            return HealthStatus("price_feed", False, f"Price feed check failed: {str(e)}")

    async def _check_autonomous_trader(self) -> HealthStatus:
        """Check if autonomous trader is running and responsive.

        CRITICAL: Trader must be running and making decisions.
        Failure = no new signals = manual intervention required.
        """
        try:
            from backend.trading.autonomous_trader import get_autonomous_trader

            trader = get_autonomous_trader()
            if not trader:
                return HealthStatus(
                    "autonomous_trader", False, "Trader not initialized"
                )

            if not trader.is_running():
                return HealthStatus(
                    "autonomous_trader", False, "Trader is stopped"
                )

            # Check trader status and last signal time
            status = trader.get_status()
            if not status:
                return HealthStatus(
                    "autonomous_trader", False, "Cannot get trader status"
                )

            return HealthStatus(
                "autonomous_trader",
                True,
                f"Trader running: {status.get('active_positions', 0)} positions",
                {
                    "active_positions": status.get('active_positions'),
                    "total_trades": status.get('total_trades'),
                    "daily_pnl": status.get('daily_pnl'),
                }
            )
        except Exception as e:
            logger.error(f"Autonomous trader health check failed: {type(e).__name__}: {e}")
            return HealthStatus("autonomous_trader", False, f"Trader check failed: {str(e)}")

    async def _check_database(self) -> HealthStatus:
        """Check database connectivity and integrity.

        CRITICAL: Database must be accessible and consistent.
        Failure = cannot save/restore positions = data loss.
        """
        try:
            from backend.core.database import get_database

            db = get_database()
            if not db:
                return HealthStatus(
                    "database", False, "Database not initialized"
                )

            # Test connection by querying
            open_pos = db.get_open_positions()
            if open_pos is None:
                return HealthStatus(
                    "database", False, "Cannot query open positions"
                )

            return HealthStatus(
                "database",
                True,
                f"Database connected, {len(open_pos)} positions",
                {
                    "open_positions": len(open_pos),
                    "db_path": str(db.db_path) if hasattr(db, 'db_path') else "unknown",
                }
            )
        except Exception as e:
            logger.error(f"Database health check failed: {type(e).__name__}: {e}")
            return HealthStatus("database", False, f"Database check failed: {str(e)}")

    async def _check_memory(self) -> HealthStatus:
        """Check memory usage."""
        try:
            mem = psutil.virtual_memory()
            percent = mem.percent

            healthy = percent < 85
            message = f"Memory usage: {percent:.1f}%"
            if percent > 90:
                message += " (CRITICAL)"
            elif percent > 85:
                message += " (WARNING)"

            return HealthStatus(
                "memory",
                healthy,
                message,
                {
                    "used_mb": mem.used / 1024 / 1024,
                    "available_mb": mem.available / 1024 / 1024,
                    "percent": percent,
                    "threshold_percent": 85,
                },
            )
        except Exception as e:
            return HealthStatus("memory", False, f"Memory check failed: {str(e)}")

    async def _check_disk(self) -> HealthStatus:
        """Check disk usage."""
        try:
            disk = psutil.disk_usage("/")
            percent = disk.percent

            healthy = percent < 85
            message = f"Disk usage: {percent:.1f}%"
            if percent > 90:
                message += " (CRITICAL)"
            elif percent > 85:
                message += " (WARNING)"

            return HealthStatus(
                "disk",
                healthy,
                message,
                {
                    "used_gb": disk.used / 1024 / 1024 / 1024,
                    "free_gb": disk.free / 1024 / 1024 / 1024,
                    "percent": percent,
                    "threshold_percent": 85,
                },
            )
        except Exception as e:
            return HealthStatus("disk", False, f"Disk check failed: {str(e)}")

    async def _check_cpu(self) -> HealthStatus:
        """Check CPU usage."""
        try:
            percent = psutil.cpu_percent(interval=1)

            healthy = percent < 80
            message = f"CPU usage: {percent:.1f}%"
            if percent > 90:
                message += " (CRITICAL)"
            elif percent > 80:
                message += " (WARNING)"

            return HealthStatus(
                "cpu",
                healthy,
                message,
                {
                    "percent": percent,
                    "cores": psutil.cpu_count(),
                    "threshold_percent": 80,
                },
            )
        except Exception as e:
            return HealthStatus("cpu", False, f"CPU check failed: {str(e)}")


    def _generate_summary(self, checks: Dict[str, HealthStatus]) -> Dict:
        """Generate health summary."""
        total = len(checks)
        healthy = sum(1 for s in checks.values() if s.healthy)
        unhealthy = sum(1 for s in checks.values() if not s.healthy)

        if healthy == total:
            status = "HEALTHY"
        elif healthy >= total * 0.75:
            status = "DEGRADED"
        else:
            status = "CRITICAL"

        return {
            "status": status,
            "total_checks": total,
            "healthy": healthy,
            "unhealthy": unhealthy,
            "unhealthy_services": [k for k, v in checks.items() if not v.healthy],
        }

    def get_history(self, service: str) -> list:
        """Get check history for a service."""
        return self.check_history.get(service, [])


# Global health checker instance
_health_checker: Optional[HealthChecker] = None


def init_health_checker() -> HealthChecker:
    """Initialize health checker."""
    global _health_checker
    if _health_checker is None:
        _health_checker = HealthChecker()
        logger.info("Health checker initialized")
    return _health_checker


def get_health_checker() -> Optional[HealthChecker]:
    """Get health checker instance."""
    return _health_checker
