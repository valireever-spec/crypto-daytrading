"""Phase 2 Integration Test: Metrics + Alerts + Chaos Tests.

This test demonstrates how Phase 2 components work together:
1. Metrics are collected continuously
2. Alerts are generated based on metrics
3. Cascade precursors trigger emergency responses

Tests:
- Integration with monitoring loop
- Alert routing and callbacks
- Cascade detection end-to-end
"""

import asyncio
import logging
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_metrics_collection_integration():
    """Test that metrics collector integrates properly with alert manager."""
    from backend.core.phase_2_metrics import Phase2MetricsCollector
    from backend.core.phase_2_alerts import Phase2AlertManager

    logger.info("\n" + "=" * 80)
    logger.info("TEST: Metrics Collection Integration")
    logger.info("=" * 80)

    collector = Phase2MetricsCollector()
    alert_manager = Phase2AlertManager()

    # Collect a snapshot
    snapshot = await collector.collect_snapshot()
    assert snapshot is not None
    logger.info(f"✓ Collected snapshot: {snapshot.timestamp}")

    # Verify snapshot structure
    snap_dict = snapshot.to_dict()
    assert "memory" in snap_dict
    assert "websocket" in snap_dict
    assert "ha_sync" in snap_dict
    assert "exceptions" in snap_dict
    assert "trading" in snap_dict
    logger.info(f"✓ Snapshot has all required sections")

    # Simulate high memory condition
    snap_dict["memory"]["percent"] = 87
    alerts = alert_manager.analyze_metrics(snap_dict)

    assert len(alerts) > 0
    assert any(a.severity.value == "critical" for a in alerts)
    logger.info(f"✓ Memory alert generated: {alerts[0].message}")

    logger.info("✓ TEST PASSED\n")
    return True


async def test_alert_callback_routing():
    """Test that alerts are properly routed to callbacks."""
    from backend.core.phase_2_alerts import Phase2AlertManager, AlertSeverity

    logger.info("=" * 80)
    logger.info("TEST: Alert Callback Routing")
    logger.info("=" * 80)

    alert_manager = Phase2AlertManager()

    # Track callback invocations
    alerts_received = []

    async def test_callback(alert):
        alerts_received.append(alert)
        logger.info(f"  → Callback received: {alert.alert_type}")

    alert_manager.register_alert_callback(test_callback)

    # Send an alert
    from backend.core.phase_2_alerts import Alert

    test_alert = Alert(
        alert_type="test_alert",
        severity=AlertSeverity.WARNING,
        message="Test warning",
    )

    await alert_manager.send_alert(test_alert)

    # Verify callback was invoked
    assert len(alerts_received) == 1
    assert alerts_received[0].alert_type == "test_alert"
    logger.info(f"✓ Alert callback invoked correctly")

    logger.info("✓ TEST PASSED\n")
    return True


async def test_cascade_precursor_detection():
    """Test cascade precursor detection with multiple conditions."""
    from backend.core.phase_2_alerts import Phase2AlertManager

    logger.info("=" * 80)
    logger.info("TEST: Cascade Precursor Detection")
    logger.info("=" * 80)

    alert_manager = Phase2AlertManager()

    # Normal metrics
    normal_metrics = {
        "memory": {"percent": 50},
        "websocket": {"max_age_seconds": 2, "stale_symbols": []},
        "ha_sync": {"latency_ms": 100},
        "exceptions": {"rate_percent": 0.1},
    }

    alerts = alert_manager.analyze_metrics(normal_metrics)
    assert len(alerts) == 0
    logger.info(f"✓ No alerts for normal metrics")

    # Single precursor (should generate 1 alert)
    single_precursor = {
        "memory": {"percent": 80},
        "websocket": {"max_age_seconds": 2, "stale_symbols": []},
        "ha_sync": {"latency_ms": 100},
        "exceptions": {"rate_percent": 0.1},
    }

    alerts = alert_manager.analyze_metrics(single_precursor)
    assert len(alerts) == 1
    assert "memory" in alerts[0].alert_type
    logger.info(f"✓ Single precursor detected: {alerts[0].alert_type}")

    # Multiple precursors (should trigger CASCADE alert)
    cascade_metrics = {
        "memory": {"percent": 82},
        "websocket": {"max_age_seconds": 35, "stale_symbols": ["BTCUSDT"]},
        "ha_sync": {"latency_ms": 7000},
        "exceptions": {"rate_percent": 0.8},
    }

    alerts = alert_manager.analyze_metrics(cascade_metrics)
    assert len(alerts) >= 4  # Individual + cascade
    cascade_alert = next((a for a in alerts if a.alert_type == "cascade_precursor"), None)
    assert cascade_alert is not None
    logger.info(f"✓ Cascade alert triggered: {cascade_alert.message}")

    logger.info("✓ TEST PASSED\n")
    return True


async def test_monitoring_loop_integration():
    """Test integrated monitoring loop."""
    from backend.core.phase_2_monitoring import Phase2MonitoringLoop
    from backend.core.phase_2_metrics import Phase2MetricsCollector
    from backend.core.phase_2_alerts import Phase2AlertManager

    logger.info("=" * 80)
    logger.info("TEST: Monitoring Loop Integration")
    logger.info("=" * 80)

    metrics = Phase2MetricsCollector(max_history_snapshots=50)
    alerts = Phase2AlertManager()
    loop = Phase2MonitoringLoop(metrics, alerts)

    # Track alerts from monitoring loop
    received_alerts = []

    async def alert_handler(alert):
        received_alerts.append(alert)

    loop.register_alert_handler(alert_handler)

    # Start monitoring
    await loop.start()
    logger.info("✓ Monitoring loop started")

    # Collect a few cycles
    await asyncio.sleep(6)  # Wait for first collection

    # Simulate high memory to trigger alerts
    snapshot = metrics.get_current_snapshot()
    if snapshot:
        snapshot.memory_percent = 87
        logger.info(f"✓ Simulated memory at {snapshot.memory_percent}%")

    await asyncio.sleep(1)

    # Check cascade risk score
    risk_score = loop.get_cascade_risk_score()
    logger.info(f"✓ Cascade risk score: {risk_score:.1f}")

    # Get system health
    health = loop.get_system_health()
    logger.info(
        f"✓ System health: {health['status']} (risk: {health['risk_score']:.0f})"
    )

    # Stop monitoring
    await loop.stop()
    logger.info("✓ Monitoring loop stopped")

    logger.info("✓ TEST PASSED\n")
    return True


async def test_prometheus_export():
    """Test Prometheus format export."""
    from backend.core.phase_2_metrics import Phase2MetricsCollector

    logger.info("=" * 80)
    logger.info("TEST: Prometheus Format Export")
    logger.info("=" * 80)

    collector = Phase2MetricsCollector()

    # Collect snapshot
    await collector.collect_snapshot()

    # Export Prometheus format
    prometheus_text = collector.export_prometheus_format()
    assert "phase2_memory_mb" in prometheus_text
    assert "phase2_websocket_max_age_seconds" in prometheus_text
    assert "phase2_ha_sync_latency_ms" in prometheus_text

    logger.info(f"✓ Prometheus export successful ({len(prometheus_text)} bytes)")
    logger.info("\nSample metrics:")
    for line in prometheus_text.split("\n")[:5]:
        logger.info(f"  {line}")

    logger.info("✓ TEST PASSED\n")
    return True


async def test_metrics_recording():
    """Test recording of metrics events."""
    from backend.core.phase_2_metrics import Phase2MetricsCollector

    logger.info("=" * 80)
    logger.info("TEST: Metrics Recording")
    logger.info("=" * 80)

    collector = Phase2MetricsCollector()

    # Record various events
    collector.record_trade(success=True)
    collector.record_trade(success=True)
    collector.record_trade(success=False)
    logger.info("✓ Recorded 3 trades (2 success, 1 error)")

    collector.record_exception("TimeoutError")
    collector.record_exception("ConnectionError")
    collector.record_exception("TimeoutError")
    logger.info("✓ Recorded 3 exceptions")

    collector.record_ha_sync(success=True, latency_ms=100)
    collector.record_ha_sync(success=True, latency_ms=120)
    collector.record_ha_sync(success=False, latency_ms=5000)
    logger.info("✓ Recorded 3 HA sync attempts")

    # Collect snapshot
    await collector.collect_snapshot()

    # Get summary
    summary = collector.get_stats_summary()
    assert summary["trading"]["trades_total"] == 3
    assert summary["exceptions"]["total"] == 3
    logger.info(f"✓ Stats summary: {summary['trading']['trades_total']} trades, "
                f"{summary['exceptions']['total']} exceptions")

    logger.info("✓ TEST PASSED\n")
    return True


async def main():
    """Run all integration tests."""
    logger.info("\n" + "=" * 80)
    logger.info("PHASE 2 INTEGRATION TESTS")
    logger.info("=" * 80)

    results = []

    try:
        results.append(("Metrics Collection", await test_metrics_collection_integration()))
    except Exception as e:
        logger.error(f"✗ FAILED: {e}", exc_info=True)
        results.append(("Metrics Collection", False))

    try:
        results.append(("Alert Routing", await test_alert_callback_routing()))
    except Exception as e:
        logger.error(f"✗ FAILED: {e}", exc_info=True)
        results.append(("Alert Routing", False))

    try:
        results.append(("Cascade Detection", await test_cascade_precursor_detection()))
    except Exception as e:
        logger.error(f"✗ FAILED: {e}", exc_info=True)
        results.append(("Cascade Detection", False))

    try:
        results.append(("Monitoring Loop", await test_monitoring_loop_integration()))
    except Exception as e:
        logger.error(f"✗ FAILED: {e}", exc_info=True)
        results.append(("Monitoring Loop", False))

    try:
        results.append(("Prometheus Export", await test_prometheus_export()))
    except Exception as e:
        logger.error(f"✗ FAILED: {e}", exc_info=True)
        results.append(("Prometheus Export", False))

    try:
        results.append(("Metrics Recording", await test_metrics_recording()))
    except Exception as e:
        logger.error(f"✗ FAILED: {e}", exc_info=True)
        results.append(("Metrics Recording", False))

    # Print summary
    logger.info("=" * 80)
    logger.info("INTEGRATION TEST SUMMARY")
    logger.info("=" * 80)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        logger.info(f"{status}: {name}")

    logger.info(f"\nTotal: {passed}/{total} passed")
    logger.info("=" * 80)

    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
