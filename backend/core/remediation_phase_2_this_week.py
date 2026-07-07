"""
REMEDIATION PHASE 2 (THIS WEEK)

Instrumentation for detection + alert rules:
1. Prometheus metrics collection (memory, WebSocket staleness, HA sync failures)
2. Alert rules for cascading failure precursors
3. Chaos test framework (kill WebSocket, block SSH, trigger memory pressure)
4. Integration with Phase 1 fixes

Objective: Make runtime failures observable and testable
"""

import asyncio
import logging
import time
import psutil
import os
from typing import Optional, Dict, Any
from collections import defaultdict
from datetime import datetime

logger = logging.getLogger(__name__)

# ============================================================================
# METRICS COLLECTION
# ============================================================================

class PrometheusMetricsCollector:
    """Collect Prometheus-compatible metrics for monitoring."""

    def __init__(self, namespace: str = "crypto_daytrading"):
        self.namespace = namespace
        self.metrics = defaultdict(lambda: {"value": 0, "timestamp": time.time()})
        self.history = defaultdict(list)  # Keep 1-hour history
        self.HISTORY_WINDOW = 3600  # 1 hour in seconds

    def record_metric(self, metric_name: str, value: float, labels: Dict[str, str] = None):
        """Record a metric value."""
        timestamp = time.time()
        key = f"{self.namespace}_{metric_name}"

        self.metrics[key] = {
            "value": value,
            "timestamp": timestamp,
            "labels": labels or {}
        }

        # Keep rolling history
        self.history[key].append((timestamp, value))
        # Prune old entries
        cutoff = timestamp - self.HISTORY_WINDOW
        self.history[key] = [(t, v) for t, v in self.history[key] if t > cutoff]

        logger.info(f"📊 [{metric_name}] = {value:.2f} {labels or ''}")

    def record_counter(self, metric_name: str, increment: int = 1, labels: Dict[str, str] = None):
        """Increment a counter metric."""
        key = f"{self.namespace}_{metric_name}"
        current = self.metrics[key].get("value", 0)
        self.record_metric(metric_name, current + increment, labels)

    def get_metric(self, metric_name: str) -> Optional[float]:
        """Get current metric value."""
        key = f"{self.namespace}_{metric_name}"
        return self.metrics.get(key, {}).get("value")

    def get_history(self, metric_name: str, lookback_seconds: int = 300) -> list:
        """Get metric history for lookback period."""
        key = f"{self.namespace}_{metric_name}"
        cutoff = time.time() - lookback_seconds
        return [(t, v) for t, v in self.history[key] if t > cutoff]

    def export_prometheus(self) -> str:
        """Export metrics in Prometheus text format."""
        lines = []
        for key, data in self.metrics.items():
            value = data["value"]
            timestamp = int(data["timestamp"] * 1000)
            lines.append(f"{key} {value} {timestamp}")
        return "\n".join(lines)


class CryptoMetricsTracker:
    """Track crypto-specific metrics for anomaly detection."""

    def __init__(self):
        self.collector = PrometheusMetricsCollector()
        self.memory_alerts = []
        self.websocket_alerts = []
        self.ha_sync_alerts = []

    def track_memory_usage(self) -> Dict[str, Any]:
        """Track process memory usage."""
        process = psutil.Process(os.getpid())
        mem_info = process.memory_info()
        mem_percent = process.memory_percent()

        self.collector.record_metric("memory_usage_bytes", mem_info.rss)
        self.collector.record_metric("memory_usage_percent", mem_percent)

        result = {
            "memory_percent": mem_percent,
            "memory_bytes": mem_info.rss,
            "timestamp": datetime.now().isoformat()
        }

        logger.info(f"💾 Memory: {mem_percent:.1f}% ({mem_info.rss / (1024**3):.2f} GB)")
        return result

    def track_websocket_staleness(self, symbol: str, staleness_seconds: float):
        """Track WebSocket staleness for a symbol."""
        self.collector.record_metric(
            "websocket_staleness_seconds",
            staleness_seconds,
            {"symbol": symbol}
        )

        if staleness_seconds > 10:  # Alert if > 10 seconds
            alert = {
                "symbol": symbol,
                "staleness": staleness_seconds,
                "timestamp": datetime.now().isoformat(),
                "severity": "CRITICAL" if staleness_seconds > 30 else "WARNING"
            }
            self.websocket_alerts.append(alert)
            logger.warning(f"🚨 [{symbol}] WebSocket stale {staleness_seconds}s")

    def track_ha_sync_failure(self, sync_method: str, error: str):
        """Track HA sync failures (HTTP or SSH)."""
        self.collector.record_counter(
            "ha_sync_failures_total",
            labels={"method": sync_method}
        )

        alert = {
            "method": sync_method,
            "error": error,
            "timestamp": datetime.now().isoformat()
        }
        self.ha_sync_alerts.append(alert)
        logger.error(f"🔀 HA sync failed ({sync_method}): {error}")

    def track_state_divergence(self, cash_primary: float, cash_backup: float):
        """Detect state divergence between PRIMARY and BACKUP."""
        divergence_percent = abs(cash_primary - cash_backup) / max(abs(cash_primary), 1.0) * 100

        self.collector.record_metric("state_divergence_percent", divergence_percent)

        if divergence_percent > 0.1:  # Alert if > 0.1%
            logger.critical(
                f"🚨 State divergence detected! PRIMARY cash: {cash_primary}, "
                f"BACKUP cash: {cash_backup} ({divergence_percent:.2f}% difference)"
            )

    def get_current_status(self) -> Dict[str, Any]:
        """Get current metrics status."""
        return {
            "memory_percent": self.collector.get_metric("memory_usage_percent"),
            "websocket_staleness_max": max(
                [v for _, v in self.collector.get_history("websocket_staleness_seconds", 60)],
                default=0
            ),
            "ha_sync_failures": self.collector.get_metric("ha_sync_failures_total"),
            "state_divergence_percent": self.collector.get_metric("state_divergence_percent"),
            "websocket_alerts": len(self.websocket_alerts),
            "ha_sync_alerts": len(self.ha_sync_alerts),
        }


# ============================================================================
# ALERT RULES
# ============================================================================

class AlertRuleEngine:
    """Evaluates alert conditions and raises alerts."""

    def __init__(self, metrics_tracker: CryptoMetricsTracker):
        self.tracker = metrics_tracker
        self.active_alerts = []
        self.RULES = {
            "websocket_stale_critical": {
                "condition": lambda: self.tracker.collector.get_metric("websocket_staleness_seconds") > 30,
                "message": "WebSocket stale >30s - recovery may be stuck",
                "severity": "CRITICAL"
            },
            "websocket_stale_warning": {
                "condition": lambda: self.tracker.collector.get_metric("websocket_staleness_seconds") > 10,
                "message": "WebSocket stale >10s - connection degraded",
                "severity": "WARNING"
            },
            "memory_critical": {
                "condition": lambda: self.tracker.collector.get_metric("memory_usage_percent") > 95,
                "message": "Memory usage >95% - risk of OOM",
                "severity": "CRITICAL"
            },
            "memory_high_with_issues": {
                "condition": self._memory_high_with_correlated_issues,
                "message": "Memory high + other symptoms - investigate",
                "severity": "ERROR"
            },
            "ha_sync_both_failed": {
                "condition": lambda: len(self.tracker.ha_sync_alerts) > 0,
                "message": "HA sync failed - state divergence risk",
                "severity": "CRITICAL"
            },
            "state_divergence": {
                "condition": lambda: self.tracker.collector.get_metric("state_divergence_percent") > 0.1,
                "message": "State divergence >0.1% - PRIMARY/BACKUP out of sync",
                "severity": "CRITICAL"
            },
        }

    def _memory_high_with_correlated_issues(self) -> bool:
        """Check if memory is high AND has other correlated issues."""
        memory_high = self.tracker.collector.get_metric("memory_usage_percent") > 80
        ha_sync_issues = len(self.tracker.ha_sync_alerts) > 0
        websocket_issues = len(self.tracker.websocket_alerts) > 0
        return memory_high and (ha_sync_issues or websocket_issues)

    def evaluate_all_rules(self) -> list:
        """Evaluate all alert rules, return list of triggered alerts."""
        triggered = []

        for rule_name, rule in self.RULES.items():
            try:
                if rule["condition"]():
                    alert = {
                        "rule": rule_name,
                        "message": rule["message"],
                        "severity": rule["severity"],
                        "timestamp": datetime.now().isoformat()
                    }
                    triggered.append(alert)
                    logger.error(
                        f"🚨 ALERT [{rule['severity']}]: {rule['message']}"
                    )
            except Exception as e:
                logger.error(f"Error evaluating rule {rule_name}: {e}")

        return triggered

    def send_alert(self, alert: Dict[str, Any]):
        """Send alert to monitoring system."""
        self.active_alerts.append(alert)
        # TODO: Integrate with Slack/PagerDuty/etc
        logger.critical(f"📢 ALERT SENT: {alert['message']}")


# ============================================================================
# CHAOS TEST FRAMEWORK
# ============================================================================

class ChaosTestFramework:
    """Simulates failures to test recovery mechanisms."""

    def __init__(self, metrics_tracker: CryptoMetricsTracker):
        self.tracker = metrics_tracker
        self.failures_active = {}

    async def simulate_websocket_down(self, duration_seconds: int = 30, symbol: str = "BTCUSDT"):
        """Simulate WebSocket connection failure."""
        logger.critical(f"🔥 CHAOS: WebSocket DOWN for {duration_seconds}s ({symbol})")

        self.failures_active["websocket_down"] = True

        for i in range(duration_seconds):
            # Simulate staleness increasing
            staleness = i * 2
            self.tracker.track_websocket_staleness(symbol, staleness)
            await asyncio.sleep(1)

        self.failures_active.pop("websocket_down", None)
        logger.info("✅ CHAOS: WebSocket DOWN test complete")

    async def simulate_ssh_blocked(self, duration_seconds: int = 30):
        """Simulate SSH tunnel being blocked."""
        logger.critical(f"🔥 CHAOS: SSH BLOCKED for {duration_seconds}s")

        self.failures_active["ssh_blocked"] = True

        for _ in range(duration_seconds):
            self.tracker.track_ha_sync_failure("SSH", "Connection timeout (simulated)")
            await asyncio.sleep(1)

        self.failures_active.pop("ssh_blocked", None)
        logger.info("✅ CHAOS: SSH BLOCKED test complete")

    async def simulate_memory_pressure(self, target_percent: float = 85, duration_seconds: int = 30):
        """Simulate high memory pressure."""
        logger.critical(f"🔥 CHAOS: Memory pressure {target_percent}% for {duration_seconds}s")

        self.failures_active["memory_pressure"] = True

        # Allocate memory to simulate pressure
        allocated = []
        try:
            import numpy as np
            # Each array is ~100MB
            num_arrays = int(target_percent / 100 * 10)  # Rough estimate
            for _ in range(num_arrays):
                allocated.append(np.zeros((10_000_000,)))  # 100MB array

            for i in range(duration_seconds):
                self.tracker.track_memory_usage()
                await asyncio.sleep(1)

        finally:
            allocated.clear()
            self.failures_active.pop("memory_pressure", None)
            logger.info("✅ CHAOS: Memory pressure test complete")

    async def simulate_network_latency(self, latency_ms: int = 500, duration_seconds: int = 30):
        """Simulate network latency."""
        logger.critical(f"🔥 CHAOS: Network latency {latency_ms}ms for {duration_seconds}s")

        self.failures_active["network_latency"] = True

        for _ in range(duration_seconds):
            await asyncio.sleep(latency_ms / 1000)  # Simulate latency
            self.failures_active["network_latency"] = True

        self.failures_active.pop("network_latency", None)
        logger.info("✅ CHAOS: Network latency test complete")

    def get_active_failures(self) -> Dict[str, Any]:
        """Get currently active failure simulations."""
        return self.failures_active


# ============================================================================
# INTEGRATION UTILITIES
# ============================================================================

async def demonstrate_remediation_phase_2():
    """Demonstrate all Phase 2 instrumentation."""

    # Initialize
    tracker = CryptoMetricsTracker()
    alert_engine = AlertRuleEngine(tracker)
    chaos = ChaosTestFramework(tracker)

    # Example 1: Monitor normal operation
    logger.info("═" * 60)
    logger.info("PHASE 2 DEMO: Normal Operation Monitoring")
    logger.info("═" * 60)

    tracker.track_memory_usage()
    tracker.track_websocket_staleness("BTCUSDT", 2.5)
    alerts = alert_engine.evaluate_all_rules()
    logger.info(f"Alerts triggered: {len(alerts)}")
    logger.info(f"Status: {tracker.get_current_status()}")

    # Example 2: WebSocket stale alert
    logger.info("\n" + "═" * 60)
    logger.info("PHASE 2 DEMO: WebSocket Staleness Alert")
    logger.info("═" * 60)

    tracker.track_websocket_staleness("BTCUSDT", 25.0)  # >10s warning
    alerts = alert_engine.evaluate_all_rules()
    logger.info(f"Alerts triggered: {len(alerts)}")

    # Example 3: HA sync failure
    logger.info("\n" + "═" * 60)
    logger.info("PHASE 2 DEMO: HA Sync Failure Detection")
    logger.info("═" * 60)

    tracker.track_ha_sync_failure("HTTP", "403 Forbidden from BACKUP")
    alerts = alert_engine.evaluate_all_rules()
    logger.info(f"Alerts triggered: {len(alerts)}")

    # Example 4: Chaos test - WebSocket down
    logger.info("\n" + "═" * 60)
    logger.info("PHASE 2 DEMO: Chaos Test - WebSocket Down")
    logger.info("═" * 60)

    await chaos.simulate_websocket_down(duration_seconds=5, symbol="BTCUSDT")
    tracker.track_websocket_staleness("BTCUSDT", 60.0)  # Critical
    alerts = alert_engine.evaluate_all_rules()
    logger.info(f"Alerts triggered: {len(alerts)}")

    # Example 5: Export metrics
    logger.info("\n" + "═" * 60)
    logger.info("PHASE 2 DEMO: Prometheus Metrics Export")
    logger.info("═" * 60)

    prometheus_output = tracker.collector.export_prometheus()
    logger.info("Prometheus Format Output:")
    logger.info(prometheus_output[:500])  # First 500 chars


if __name__ == "__main__":
    logger.info("✅ Remediation Phase 2 (This Week) module loaded")

    # Uncomment to test
    # asyncio.run(demonstrate_remediation_phase_2())
