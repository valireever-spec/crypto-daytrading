"""Integration tests for execution log loader and paper trading integration."""

import pytest
import json
from pathlib import Path
import tempfile
from datetime import datetime, timezone

from backend.analytics.execution_log_loader import (
    load_executions_from_audit_log,
    _convert_audit_to_daemon_format,
)


class TestExecutionLogLoader:
    """Test execution log loading from audit trail."""

    def test_convert_format_a(self):
        """Test conversion of Format A (preferred)."""
        audit_record = {
            "symbol": "AAPL",
            "side": "BUY",
            "timestamp": "2026-06-24T08:30:00+00:00",
            "price": 150.0,
            "allocation_pct": 5.0,
            "quantity": 10.0,
        }

        result = _convert_audit_to_daemon_format(audit_record)

        assert result is not None
        assert result["symbol"] == "AAPL"
        assert result["side"] == "BUY"
        assert result["price"] == 150.0

    def test_convert_format_b_legacy(self):
        """Test conversion of Format B (legacy)."""
        audit_record = {
            "symbol": "MSFT",
            "side": "SELL",
            "timestamp": "2026-06-24T09:00:00+00:00",
            "filled_price": 320.0,
            "quantity": 5.0,
        }

        result = _convert_audit_to_daemon_format(audit_record)

        assert result is not None
        assert result["symbol"] == "MSFT"
        assert result["side"] == "SELL"
        assert result["price"] == 320.0

    def test_convert_missing_symbol(self):
        """Test invalid record (missing symbol)."""
        audit_record = {
            "side": "BUY",
            "timestamp": "2026-06-24T08:30:00+00:00",
            "price": 100.0,
        }

        result = _convert_audit_to_daemon_format(audit_record)
        assert result is None

    def test_convert_invalid_side(self):
        """Test invalid record (bad side)."""
        audit_record = {
            "symbol": "AAPL",
            "side": "HOLD",
            "timestamp": "2026-06-24T08:30:00+00:00",
            "price": 150.0,
        }

        result = _convert_audit_to_daemon_format(audit_record)
        assert result is None

    def test_convert_with_recommendation_id(self):
        """Test conversion with recommendation_id."""
        audit_record = {
            "symbol": "AAPL",
            "side": "BUY",
            "timestamp": "2026-06-24T08:30:00+00:00",
            "price": 150.0,
            "allocation_pct": 5.0,
            "recommendation_id": "rec-123-abc",
        }

        result = _convert_audit_to_daemon_format(audit_record)

        assert result is not None
        assert result["recommendation_id"] == "rec-123-abc"

    def test_load_executions_file_not_found(self):
        """Test graceful handling of missing audit file."""
        # This should return empty list without crashing
        # (actual file path doesn't exist in test)
        executions = load_executions_from_audit_log()
        assert isinstance(executions, list)

    def test_convert_default_allocation(self):
        """Test allocation defaults to 1% if missing."""
        audit_record = {
            "symbol": "AAPL",
            "side": "BUY",
            "timestamp": "2026-06-24T08:30:00+00:00",
            "price": 150.0,
        }

        result = _convert_audit_to_daemon_format(audit_record)

        assert result is not None
        assert result["allocation_pct"] == 1.0
