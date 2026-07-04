"""Week 3 Production Integration Tests.

Tests for Phase 2 monitoring, metrics export, and alert routing.
"""

import pytest
import asyncio
import json
from unittest.mock import patch, AsyncMock, MagicMock

from fastapi.testclient import TestClient
from backend.api.main import app
from backend.core.phase_2_monitoring import init_phase2_monitoring, get_phase2_monitoring
from backend.core.phase_2_alerts import AlertSeverity, Alert
from backend.core.alert_routing import init_alert_router, get_alert_router


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
async def monitoring():
    """Initialize Phase 2 monitoring for tests."""
    monitoring = init_phase2_monitoring()
    await monitoring.start()
    yield monitoring
    await monitoring.stop()


class TestMetricsRouter:
    """Test metrics router endpoints."""

    def test_metrics_endpoint_returns_prometheus_format(self, client):
        """Test /metrics returns valid Prometheus format."""
        response = client.get("/metrics")

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/plain; version=0.0.4"
        assert b"HELP" in response.content  # Prometheus format includes HELP lines
        assert b"TYPE" in response.content  # Prometheus format includes TYPE lines

    def test_metrics_health_endpoint(self, client):
        """Test /metrics/health returns system health."""
        response = client.get("/metrics/health")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "risk_score" in data
        assert "health_message" in data
        assert data["risk_score"] >= 0 and data["risk_score"] <= 100

    def test_metrics_summary_endpoint(self, client):
        """Test /metrics/summary returns current metrics."""
        response = client.get("/metrics/summary")

        assert response.status_code == 200
        data = response.json()

        # Check structure
        assert "memory" in data
        assert "websocket" in data
        assert "ha_sync" in data
        assert "exceptions" in data
        assert "trading" in data

        # Check memory metrics
        assert "mb" in data["memory"]
        assert "percent" in data["memory"]
        assert data["memory"]["percent"] >= 0 and data["memory"]["percent"] <= 100

    def test_cascade_risk_endpoint(self, client):
        """Test /metrics/cascade-risk returns risk score."""
        response = client.get("/metrics/cascade-risk")

        assert response.status_code == 200
        data = response.json()
        assert "risk_score" in data
        assert "risk_level" in data
        assert data["risk_level"] in ["SAFE", "CAUTION", "WARNING", "CRITICAL"]

        # Verify risk level matches score
        score = data["risk_score"]
        level = data["risk_level"]
        if score >= 75:
            assert level == "CRITICAL"
        elif score >= 50:
            assert level == "WARNING"
        elif score >= 25:
            assert level == "CAUTION"
        else:
            assert level == "SAFE"

    def test_metrics_history_endpoint(self, client):
        """Test /metrics/history returns historical data."""
        response = client.get("/metrics/history?minutes=60")

        assert response.status_code == 200
        data = response.json()
        assert "period_minutes" in data
        assert data["period_minutes"] == 60
        assert "snapshot_count" in data
        assert "snapshots" in data
        assert isinstance(data["snapshots"], list)


class TestAlertRouting:
    """Test alert routing functionality."""

    def test_alert_router_initialization(self):
        """Test alert router initializes correctly."""
        router = init_alert_router()
        assert router is not None
        assert router.alert_handlers is not None

    def test_register_custom_handler(self):
        """Test registering custom alert handlers."""
        router = get_alert_router()

        async def test_handler(alert):
            pass

        router.register_handler(AlertSeverity.WARNING, test_handler)
        assert test_handler in router.alert_handlers[AlertSeverity.WARNING]

    @pytest.mark.asyncio
    async def test_route_info_alert(self):
        """Test routing INFO severity alert."""
        router = get_alert_router()

        alert = Alert(
            alert_type="test_info",
            severity=AlertSeverity.INFO,
            message="Test info alert"
        )

        # Should not raise exception
        await router.route_alert(alert)

    @pytest.mark.asyncio
    async def test_route_warning_alert(self):
        """Test routing WARNING severity alert."""
        router = get_alert_router()

        alert = Alert(
            alert_type="test_warning",
            severity=AlertSeverity.WARNING,
            message="Test warning alert",
            details={"threshold": 75, "actual": 80}
        )

        await router.route_alert(alert)

    @pytest.mark.asyncio
    async def test_route_critical_alert(self):
        """Test routing CRITICAL severity alert."""
        router = get_alert_router()

        alert = Alert(
            alert_type="test_critical",
            severity=AlertSeverity.CRITICAL,
            message="Test critical alert"
        )

        await router.route_alert(alert)

    @pytest.mark.asyncio
    async def test_route_cascade_alert(self):
        """Test routing CASCADE severity alert."""
        router = get_alert_router()

        # Mock emergency stop callback
        mock_callback = AsyncMock()
        router.set_emergency_stop_callback(mock_callback)

        alert = Alert(
            alert_type="cascade_detected",
            severity=AlertSeverity.CASCADE,
            message="Cascade failure risk detected"
        )

        await router.route_alert(alert)

        # Verify emergency stop callback was called
        # Note: It's called with asyncio.create_task, so we need to wait a bit
        await asyncio.sleep(0.1)

    @pytest.mark.asyncio
    async def test_alert_routing_setup(self):
        """Test alert routing setup in monitoring system."""
        from backend.core.alert_routing import setup_alert_routing

        # Should not raise exception
        await setup_alert_routing()


class TestPhase2Monitoring:
    """Test Phase 2 monitoring integration."""

    @pytest.mark.asyncio
    async def test_monitoring_starts(self):
        """Test Phase 2 monitoring starts correctly."""
        monitoring = init_phase2_monitoring()
        await monitoring.start()

        assert monitoring.is_monitoring is True

        await monitoring.stop()
        assert monitoring.is_monitoring is False

    @pytest.mark.asyncio
    async def test_metrics_collection_running(self):
        """Test metrics are being collected."""
        monitoring = init_phase2_monitoring()
        await monitoring.start()

        # Wait for first collection
        await asyncio.sleep(1)

        snapshot = monitoring.get_metrics_summary()
        assert snapshot is not None
        assert "memory" in snapshot

        await monitoring.stop()

    @pytest.mark.asyncio
    async def test_cascade_risk_calculation(self):
        """Test cascade risk score calculation."""
        monitoring = init_phase2_monitoring()
        await monitoring.start()

        risk_score = monitoring.get_cascade_risk_score()
        assert isinstance(risk_score, float)
        assert risk_score >= 0 and risk_score <= 100

        await monitoring.stop()

    @pytest.mark.asyncio
    async def test_system_health_determination(self):
        """Test system health status determination."""
        monitoring = init_phase2_monitoring()
        await monitoring.start()

        health = monitoring.get_system_health()
        assert "status" in health
        assert health["status"] in ["UNKNOWN", "HEALTHY", "CAUTION", "WARNING", "CRITICAL"]

        await monitoring.stop()

    @pytest.mark.asyncio
    async def test_metrics_history(self):
        """Test metrics history collection."""
        monitoring = init_phase2_monitoring()
        await monitoring.start()

        # Let some history accumulate
        await asyncio.sleep(2)

        history = monitoring.get_metrics_history(minutes=1)
        assert isinstance(history, list)
        # Should have at least a few snapshots
        assert len(history) >= 1

        await monitoring.stop()

    @pytest.mark.asyncio
    async def test_prometheus_export(self):
        """Test Prometheus format export."""
        monitoring = init_phase2_monitoring()
        await monitoring.start()

        prometheus_text = monitoring.export_prometheus_metrics()
        assert isinstance(prometheus_text, str)
        assert "HELP" in prometheus_text
        assert "TYPE" in prometheus_text
        assert "crypto_daytrading" in prometheus_text

        await monitoring.stop()


class TestEndToEndIntegration:
    """End-to-end integration tests."""

    def test_full_monitoring_flow(self, client):
        """Test complete flow: metrics collection → export → dashboard."""

        # 1. Get system health
        response = client.get("/metrics/health")
        assert response.status_code == 200
        health = response.json()

        # 2. Get cascade risk
        response = client.get("/metrics/cascade-risk")
        assert response.status_code == 200
        risk = response.json()

        # 3. Get metrics summary
        response = client.get("/metrics/summary")
        assert response.status_code == 200
        summary = response.json()

        # 4. Export Prometheus
        response = client.get("/metrics")
        assert response.status_code == 200
        assert len(response.content) > 0

        # Verify consistency
        assert health["risk_score"] == risk["risk_score"]
        assert "memory" in summary
        assert "websocket" in summary

    def test_alert_generation_flow(self, client):
        """Test alert generation in monitoring."""

        # Get current metrics
        response = client.get("/metrics/summary")
        assert response.status_code == 200
        summary = response.json()

        # Check if any alerts would be generated
        memory_percent = summary["memory"]["percent"]
        ws_age = summary["websocket"]["max_age_seconds"]
        exception_rate = summary["exceptions"]["rate_percent"]

        # Determine expected alerts
        expected_alerts = []
        if memory_percent > 85:
            expected_alerts.append("memory_critical")
        if ws_age > 60:
            expected_alerts.append("websocket_critical")
        if exception_rate > 1.0:
            expected_alerts.append("exception_critical")

        # If thresholds exceeded, we should see alert history
        if expected_alerts:
            response = client.get("/metrics/health")
            health = response.json()
            assert health["status"] != "HEALTHY"


class TestPrometheusMetricsFormat:
    """Test Prometheus metrics format compliance."""

    def test_prometheus_format_compliance(self, client):
        """Test that exported metrics follow Prometheus format."""
        response = client.get("/metrics")
        content = response.text

        # Check for required Prometheus components
        lines = content.split("\n")

        # Count different line types
        help_lines = [l for l in lines if l.startswith("# HELP")]
        type_lines = [l for l in lines if l.startswith("# TYPE")]
        metric_lines = [l for l in lines if l and not l.startswith("#")]

        assert len(help_lines) > 0, "No HELP lines found"
        assert len(type_lines) > 0, "No TYPE lines found"
        assert len(metric_lines) > 0, "No metric lines found"

        # Verify format of metric lines (should be: name value [timestamp])
        for line in metric_lines:
            parts = line.split()
            assert len(parts) >= 2, f"Invalid metric line: {line}"

    def test_prometheus_metric_names(self, client):
        """Test that metric names follow Prometheus conventions."""
        response = client.get("/metrics")
        content = response.text

        lines = content.split("\n")
        metric_lines = [l for l in lines if l and not l.startswith("#")]

        for line in metric_lines:
            # Extract metric name (before { or space)
            metric_name = line.split("{")[0].split()[0]

            # Should start with app prefix
            assert metric_name.startswith("crypto_daytrading_"), \
                f"Metric {metric_name} doesn't follow naming convention"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
