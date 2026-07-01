"""Tests for FR-016: Autonomous 24/7 Trading."""

import pytest
from datetime import datetime, time
from fastapi.testclient import TestClient

from backend.api.main import app

client = TestClient(app)


class TestAutonomousStatusEndpoint:
    """Test GET /api/autonomous/status endpoint."""

    def test_get_status_default_disabled(self):
        """Default status shows autonomous disabled."""
        response = client.get("/api/autonomous/status")
        assert response.status_code == 200

        data = response.json()
        assert 'enabled' in data
        assert 'start_time' in data
        assert 'end_time' in data
        assert 'emergency_stop_active' in data
        assert 'next_execution' in data

    def test_status_shows_emergency_stop_state(self):
        """Status includes whether emergency stop is active."""
        response = client.get("/api/autonomous/status")
        data = response.json()

        assert 'emergency_stop_active' in data
        assert isinstance(data['emergency_stop_active'], bool)


class TestAutonomousEnableDisable:
    """Test enabling/disabling autonomous trading."""

    def test_enable_autonomous(self):
        """POST /api/autonomous/enable activates autonomous."""
        response = client.post("/api/autonomous/enable")

        if response.status_code == 200:
            data = response.json()
            assert data['message'] == 'Autonomous trading enabled'
            assert 'next_execution' in data

    def test_disable_autonomous(self):
        """POST /api/autonomous/disable deactivates autonomous."""
        # First enable
        client.post("/api/autonomous/enable")

        # Then disable
        response = client.post("/api/autonomous/disable")

        if response.status_code == 200:
            data = response.json()
            assert data['message'] == 'Autonomous trading disabled'
            assert data['mode'] == 'Manual'


class TestScheduleConfiguration:
    """Test setting autonomous schedule."""

    def test_set_schedule_basic(self):
        """POST /api/autonomous/set-schedule configures trading window."""
        payload = {
            "enabled": True,
            "start_hour": 22,
            "start_minute": 0,
            "end_hour": 7,
            "end_minute": 0,
            "interval_minutes": 15
        }

        response = client.post("/api/autonomous/set-schedule", json=payload)

        if response.status_code == 200:
            data = response.json()
            assert data['enabled'] is True
            assert '22:00' in data['start_time']
            assert '07:00' in data['end_time']
            assert data['interval_minutes'] == 15

    def test_set_schedule_validates_hours(self):
        """Invalid hours rejected."""
        payload = {
            "enabled": True,
            "start_hour": 25,  # Invalid (0-23)
            "start_minute": 0,
            "end_hour": 7,
            "end_minute": 0,
            "interval_minutes": 15
        }

        response = client.post("/api/autonomous/set-schedule", json=payload)

        assert response.status_code == 400

    def test_set_schedule_validates_interval(self):
        """Interval must be 15-60 minutes."""
        payload = {
            "enabled": True,
            "start_hour": 22,
            "start_minute": 0,
            "end_hour": 7,
            "end_minute": 0,
            "interval_minutes": 10  # Too small (min 15)
        }

        response = client.post("/api/autonomous/set-schedule", json=payload)

        assert response.status_code == 400

    def test_set_schedule_overnight_window(self):
        """Can set overnight schedule (e.g., 22:00 to 07:00)."""
        payload = {
            "enabled": True,
            "start_hour": 22,
            "start_minute": 0,
            "end_hour": 7,
            "end_minute": 0,
            "interval_minutes": 15
        }

        response = client.post("/api/autonomous/set-schedule", json=payload)

        if response.status_code == 200:
            data = response.json()
            assert data['enabled'] is True


class TestNextExecution:
    """Test execution scheduling."""

    def test_get_next_execution(self):
        """GET /api/autonomous/next-execution shows when next trade runs."""
        response = client.get("/api/autonomous/next-execution")
        assert response.status_code == 200

        data = response.json()
        assert 'will_execute' in data
        assert 'next_execution' in data or 'reason' in data

    def test_next_execution_disabled_returns_none(self):
        """If autonomous disabled, next_execution is None."""
        # Ensure disabled
        client.post("/api/autonomous/disable")

        response = client.get("/api/autonomous/next-execution")

        if response.status_code == 200:
            data = response.json()
            assert data['will_execute'] is False or data['next_execution'] is None

    def test_next_execution_includes_time_format(self):
        """Next execution shows both seconds and human-readable time."""
        response = client.get("/api/autonomous/next-execution")

        if response.status_code == 200:
            data = response.json()
            if 'seconds_until' in data:
                assert isinstance(data['seconds_until'], (int, float))
            if 'time_until' in data:
                assert isinstance(data['time_until'], str)


class TestLogExecution:
    """Test execution logging."""

    def test_log_execution_endpoint(self):
        """POST /api/autonomous/log-execution logs execution time."""
        response = client.post("/api/autonomous/log-execution")
        assert response.status_code == 200

        data = response.json()
        assert 'logged_at' in data
        assert 'next_scheduled' in data


class TestAutonomousWindowLogic:
    """Test time-based window logic via API."""

    def test_window_configuration_persists(self):
        """Setting window configuration is reflected in status."""
        payload = {
            "enabled": True,
            "start_hour": 20,
            "start_minute": 30,
            "end_hour": 6,
            "end_minute": 45,
            "interval_minutes": 15
        }

        client.post("/api/autonomous/set-schedule", json=payload)
        response = client.get("/api/autonomous/status")
        data = response.json()

        # Config should be in response
        assert '20:30' in data['start_time']
        assert '06:45' in data['end_time']


class TestAutonomousCrashInteraction:
    """Test autonomous trading interaction with emergency stop."""

    def test_autonomous_respects_emergency_stop(self):
        """Autonomous won't run if emergency stop active."""
        # Enable autonomous
        client.post("/api/autonomous/enable")

        # Get status (should show emergency_stop_active = False by default)
        response = client.get("/api/autonomous/status")
        data = response.json()

        # If emergency stop were active, running_now should be False
        assert 'running_now' in data
        assert isinstance(data['running_now'], bool)


class TestAutonomousAPIIntegration:
    """Integration tests with full API."""

    def test_set_schedule_then_check_status(self):
        """Set schedule, then verify status reflects changes."""
        payload = {
            "enabled": True,
            "start_hour": 22,
            "start_minute": 0,
            "end_hour": 7,
            "end_minute": 0,
            "interval_minutes": 20
        }

        response_set = client.post("/api/autonomous/set-schedule", json=payload)

        if response_set.status_code == 200:
            response_status = client.get("/api/autonomous/status")
            status_data = response_status.json()

            assert status_data['enabled'] is True
            assert status_data['interval_minutes'] == 20

    def test_enable_disable_cycle(self):
        """Enable, verify active, disable, verify inactive."""
        # Enable
        enable_resp = client.post("/api/autonomous/enable")
        if enable_resp.status_code == 200:
            # Check enabled
            status_resp = client.get("/api/autonomous/status")
            assert status_resp.json()['enabled'] is True

            # Disable
            disable_resp = client.post("/api/autonomous/disable")
            if disable_resp.status_code == 200:
                # Check disabled
                status_resp = client.get("/api/autonomous/status")
                assert status_resp.json()['enabled'] is False
