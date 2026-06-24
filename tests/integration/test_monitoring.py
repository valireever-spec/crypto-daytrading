"""Integration tests for Phase 334: Production Monitoring."""

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.core.health_checker import init_health_checker
from backend.core.alerting import init_alert_manager, AlertSeverity


class TestMonitoringHealthChecks:
    """Test health check endpoints."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup monitoring services."""
        init_health_checker()
        init_alert_manager()
        yield

    def test_health_endpoint(self, client):
        """Test comprehensive health check endpoint."""
        response = client.get("/api/monitoring/health")
        assert response.status_code == 200
        data = response.json()

        assert 'timestamp' in data
        assert 'overall_healthy' in data
        assert 'checks' in data
        assert 'summary' in data

        # Check specific services
        assert 'api' in data['checks']
        assert 'memory' in data['checks']
        assert 'cpu' in data['checks']
        assert 'disk' in data['checks']

    def test_health_check_structure(self, client):
        """Test health check response structure."""
        response = client.get("/api/monitoring/health")
        assert response.status_code == 200
        data = response.json()

        for service_name, check in data['checks'].items():
            assert 'name' in check
            assert 'healthy' in check
            assert 'message' in check
            assert 'timestamp' in check

    def test_service_health_endpoint(self, client):
        """Test individual service health check."""
        response = client.get("/api/monitoring/health/service/cpu")
        assert response.status_code == 200
        data = response.json()

        assert data['name'] == 'cpu'
        assert 'healthy' in data
        assert 'details' in data

    def test_service_health_not_found(self, client):
        """Test service health with invalid service."""
        response = client.get("/api/monitoring/health/service/invalid_service")
        assert response.status_code == 404

    def test_health_history_endpoint(self, client):
        """Test health check history."""
        # First health check
        client.get("/api/monitoring/health")

        # Get history
        response = client.get("/api/monitoring/health/history/cpu")
        assert response.status_code == 200
        data = response.json()

        assert 'service' in data
        assert 'history' in data
        assert 'total' in data
        assert data['service'] == 'cpu'
        assert len(data['history']) > 0

    def test_system_status_endpoint(self, client):
        """Test overall system status endpoint."""
        response = client.get("/api/monitoring/status")
        assert response.status_code == 200
        data = response.json()

        assert 'timestamp' in data
        assert 'health' in data
        assert 'alerts' in data

    def test_metrics_endpoint(self, client):
        """Test system metrics endpoint."""
        response = client.get("/api/monitoring/metrics")
        assert response.status_code == 200
        data = response.json()

        # Check CPU metrics
        assert 'cpu' in data
        assert 'percent' in data['cpu']
        assert 'count' in data['cpu']

        # Check memory metrics
        assert 'memory' in data
        assert 'used_mb' in data['memory']
        assert 'available_mb' in data['memory']
        assert 'percent' in data['memory']

        # Check disk metrics
        assert 'disk' in data
        assert 'used_gb' in data['disk']
        assert 'free_gb' in data['disk']
        assert 'percent' in data['disk']


class TestMonitoringAlerts:
    """Test alert management endpoints."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup monitoring services."""
        init_health_checker()
        init_alert_manager()
        yield

    def test_create_alert(self, client):
        """Test creating an alert."""
        response = client.post(
            "/api/monitoring/alerts/create",
            params={
                "severity": "warning",
                "title": "Test Alert",
                "message": "This is a test alert",
                "service": "test"
            }
        )
        assert response.status_code == 200
        data = response.json()

        assert data['status'] == 'created'
        assert 'alert' in data
        assert data['alert']['severity'] == 'warning'
        assert data['alert']['title'] == 'Test Alert'

    def test_get_alerts(self, client):
        """Test getting alerts."""
        # Create alert first
        client.post(
            "/api/monitoring/alerts/create",
            params={
                "severity": "info",
                "title": "Test",
                "message": "Test message",
                "service": "test"
            }
        )

        response = client.get("/api/monitoring/alerts")
        assert response.status_code == 200
        data = response.json()

        assert 'count' in data
        assert 'alerts' in data

    def test_get_active_alerts(self, client):
        """Test getting active alerts."""
        response = client.get("/api/monitoring/alerts/active")
        assert response.status_code == 200
        data = response.json()

        assert 'count' in data
        assert 'alerts' in data
        assert isinstance(data['alerts'], list)

    def test_get_alerts_by_service(self, client):
        """Test getting alerts by service."""
        # Create alert
        client.post(
            "/api/monitoring/alerts/create",
            params={
                "severity": "warning",
                "title": "Service Alert",
                "message": "Test message",
                "service": "database"
            }
        )

        response = client.get("/api/monitoring/alerts/service/database")
        assert response.status_code == 200
        data = response.json()

        assert data['service'] == 'database'
        assert 'count' in data
        assert 'alerts' in data

    def test_get_alerts_by_severity(self, client):
        """Test getting alerts by severity."""
        # Create alert
        client.post(
            "/api/monitoring/alerts/create",
            params={
                "severity": "critical",
                "title": "Critical Alert",
                "message": "Test message",
                "service": "api"
            }
        )

        response = client.get("/api/monitoring/alerts/severity/critical")
        assert response.status_code == 200
        data = response.json()

        assert data['severity'] == 'critical'
        assert 'count' in data
        assert 'alerts' in data

    def test_resolve_alert(self, client):
        """Test resolving an alert."""
        # Create alert
        create_resp = client.post(
            "/api/monitoring/alerts/create",
            params={
                "severity": "warning",
                "title": "Test Alert",
                "message": "Test message",
                "service": "test"
            }
        )
        alert_id = create_resp.json()['alert']['id']

        # Resolve alert
        resolve_resp = client.post(f"/api/monitoring/alerts/{alert_id}/resolve")
        assert resolve_resp.status_code == 200
        assert resolve_resp.json()['status'] == 'resolved'

    def test_invalid_severity(self, client):
        """Test creating alert with invalid severity."""
        response = client.post(
            "/api/monitoring/alerts/create",
            params={
                "severity": "invalid",
                "title": "Test",
                "message": "Test",
                "service": "test"
            }
        )
        assert response.status_code == 400

    def test_alert_alert_history(self, client):
        """Test alert history with multiple alerts."""
        # Create multiple alerts
        for i in range(5):
            client.post(
                "/api/monitoring/alerts/create",
                params={
                    "severity": "info",
                    "title": f"Alert {i}",
                    "message": f"Message {i}",
                    "service": f"service_{i}"
                }
            )

        response = client.get("/api/monitoring/alerts?limit=10")
        assert response.status_code == 200
        data = response.json()

        assert data['count'] >= 5


class TestMonitoringDashboardUI:
    """Test monitoring dashboard UI access."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_monitoring_dashboard_accessible(self, client):
        """Test that monitoring dashboard is accessible."""
        response = client.get("/static/monitoring-dashboard.html")
        assert response.status_code == 200
        assert b'Production Monitoring' in response.content

    def test_dashboard_contains_required_sections(self, client):
        """Test that dashboard contains all required sections."""
        response = client.get("/static/monitoring-dashboard.html")
        assert response.status_code == 200
        content = response.text

        # Check for required sections
        assert 'System Health' in content
        assert 'Resource Usage' in content
        assert 'Active Alerts' in content
        assert 'Service Status' in content


class TestMonitoringIntegration:
    """Integration tests for monitoring system."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup monitoring services."""
        init_health_checker()
        init_alert_manager()
        yield

    def test_monitoring_workflow(self, client):
        """Test complete monitoring workflow."""
        # 1. Get initial health
        health_resp = client.get("/api/monitoring/health")
        assert health_resp.status_code == 200

        # 2. Get metrics
        metrics_resp = client.get("/api/monitoring/metrics")
        assert metrics_resp.status_code == 200

        # 3. Create an alert
        alert_resp = client.post(
            "/api/monitoring/alerts/create",
            params={
                "severity": "warning",
                "title": "Test Alert",
                "message": "Testing workflow",
                "service": "test"
            }
        )
        assert alert_resp.status_code == 200
        alert_id = alert_resp.json()['alert']['id']

        # 4. Get active alerts
        active_resp = client.get("/api/monitoring/alerts/active")
        assert active_resp.status_code == 200

        # 5. Resolve alert
        resolve_resp = client.post(f"/api/monitoring/alerts/{alert_id}/resolve")
        assert resolve_resp.status_code == 200

        # 6. Get system status
        status_resp = client.get("/api/monitoring/status")
        assert status_resp.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
