"""Tests for strategy allocation management (Phase 1 Week 2.5)."""

import pytest
import json
from pathlib import Path
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.analytics.allocation import (
    AllocationManager,
    init_allocation,
    get_allocation,
    DEFAULT_ALLOCATION,
    TIME_PRESETS,
)

# Test file path
TEST_ALLOCATION_FILE = Path("logs/allocation_config_test.json")


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def setup_allocation():
    """Initialize and clean up allocation manager."""
    # Clean up allocation file before test
    import backend.analytics.allocation as alloc_module
    if alloc_module.ALLOCATION_FILE.exists():
        alloc_module.ALLOCATION_FILE.unlink()

    init_allocation()
    yield

    # Cleanup after test
    if alloc_module.ALLOCATION_FILE.exists():
        alloc_module.ALLOCATION_FILE.unlink()
    if TEST_ALLOCATION_FILE.exists():
        TEST_ALLOCATION_FILE.unlink()


class TestAllocationManager:
    """Test AllocationManager class."""

    def test_init_with_defaults(self):
        """Allocation should initialize with defaults."""
        mgr = AllocationManager()
        allocation = mgr.get_allocation_dict()

        assert allocation["momentum"] == 40
        assert allocation["reversion"] == 35
        assert allocation["grid"] == 25

    def test_set_allocation(self):
        """Should set custom allocation."""
        mgr = AllocationManager()
        allocation = mgr.set_allocation(momentum=50, reversion=30, grid=20)

        assert allocation["momentum"] == 50
        assert allocation["reversion"] == 30
        assert allocation["grid"] == 20

    def test_set_allocation_invalid_sum(self):
        """Should reject allocation that doesn't sum to 100."""
        mgr = AllocationManager()

        with pytest.raises(ValueError):
            mgr.set_allocation(momentum=50, reversion=30, grid=15)

    def test_set_allocation_persists_to_disk(self, tmp_path):
        """Allocation should persist to disk."""
        # Create manager with temp file
        import backend.analytics.allocation as alloc_module

        original_file = alloc_module.ALLOCATION_FILE
        alloc_module.ALLOCATION_FILE = tmp_path / "allocation_test.json"

        try:
            mgr = AllocationManager()
            mgr.set_allocation(momentum=60, reversion=20, grid=20)

            # Verify file exists and has correct content
            assert alloc_module.ALLOCATION_FILE.exists()
            with open(alloc_module.ALLOCATION_FILE) as f:
                data = json.load(f)
                assert data["momentum"] == 60
                assert data["reversion"] == 20
                assert data["grid"] == 20
        finally:
            alloc_module.ALLOCATION_FILE = original_file

    def test_set_preset_morning(self):
        """Should apply morning preset."""
        mgr = AllocationManager()
        allocation = mgr.set_preset("morning")

        assert allocation["momentum"] == 50
        assert allocation["reversion"] == 30
        assert allocation["grid"] == 20

    def test_set_preset_afternoon(self):
        """Should apply afternoon preset."""
        mgr = AllocationManager()
        allocation = mgr.set_preset("afternoon")

        assert allocation["momentum"] == 30
        assert allocation["reversion"] == 40
        assert allocation["grid"] == 30

    def test_set_preset_evening(self):
        """Should apply evening preset."""
        mgr = AllocationManager()
        allocation = mgr.set_preset("evening")

        assert allocation["momentum"] == 40
        assert allocation["reversion"] == 35
        assert allocation["grid"] == 25

    def test_set_preset_invalid(self):
        """Should reject invalid preset."""
        mgr = AllocationManager()

        with pytest.raises(ValueError):
            mgr.set_preset("invalid_preset")

    def test_reset_to_default(self):
        """Should reset to default allocation."""
        mgr = AllocationManager()

        # Change allocation
        mgr.set_allocation(momentum=60, reversion=20, grid=20)

        # Reset
        allocation = mgr.reset_to_default()

        assert allocation["momentum"] == 40
        assert allocation["reversion"] == 35
        assert allocation["grid"] == 25

    def test_get_allocation_state(self):
        """Should return allocation state."""
        mgr = AllocationManager()
        mgr.set_allocation(momentum=50, reversion=30, grid=20, preset="custom")

        state = mgr.get_allocation()

        assert state.momentum == 50
        assert state.reversion == 30
        assert state.grid == 20
        assert state.preset == "custom"

    def test_apply_to_signal_default_weights(self):
        """Should apply default weights to signal components."""
        mgr = AllocationManager()

        # All components positive
        result = mgr.apply_to_signal(rsi_score=100, macd_score=100, bb_score=100)
        assert result > 0

        # All components negative
        result = mgr.apply_to_signal(rsi_score=-100, macd_score=-100, bb_score=-100)
        assert result < 0

        # Neutral
        result = mgr.apply_to_signal(rsi_score=0, macd_score=0, bb_score=0)
        assert result == 0

    def test_apply_to_signal_momentum_favored(self):
        """Should weight momentum heavily when allocated."""
        mgr = AllocationManager()
        mgr.set_allocation(momentum=80, reversion=10, grid=10)

        # Momentum strong, reversion weak
        result_momentum_strong = mgr.apply_to_signal(
            rsi_score=100, macd_score=100, bb_score=-100
        )

        # With default allocation
        mgr.reset_to_default()
        result_default = mgr.apply_to_signal(
            rsi_score=100, macd_score=100, bb_score=-100
        )

        # Momentum-favored should be higher
        assert result_momentum_strong > result_default

    def test_apply_to_signal_reversion_favored(self):
        """Should weight reversion heavily when allocated."""
        mgr = AllocationManager()
        mgr.set_allocation(momentum=10, reversion=80, grid=10)

        # Reversion strong, momentum weak
        result_reversion_strong = mgr.apply_to_signal(
            rsi_score=-100, macd_score=-100, bb_score=100
        )

        # With default allocation
        mgr.reset_to_default()
        result_default = mgr.apply_to_signal(
            rsi_score=-100, macd_score=-100, bb_score=100
        )

        # Reversion-favored should be higher
        assert result_reversion_strong > result_default

    def test_get_presets(self):
        """Should return all available presets."""
        mgr = AllocationManager()
        presets = mgr.get_presets()

        assert "morning" in presets
        assert "afternoon" in presets
        assert "evening" in presets
        assert presets["morning"]["momentum"] == 50


class TestAllocationAPI:
    """Test allocation API endpoints."""

    def test_get_allocation(self, client):
        """GET /api/allocation should return current allocation."""
        response = client.get("/api/allocation")
        assert response.status_code == 200

        data = response.json()
        assert "momentum" in data
        assert "reversion" in data
        assert "grid" in data
        assert "preset" in data

    def test_get_allocation_defaults(self, client):
        """GET /api/allocation should return defaults initially."""
        response = client.get("/api/allocation")
        data = response.json()

        assert data["momentum"] == 40
        assert data["reversion"] == 35
        assert data["grid"] == 25

    def test_save_allocation(self, client):
        """POST /api/allocation/save should persist allocation."""
        response = client.post(
            "/api/allocation/save",
            params={"momentum": 50, "reversion": 30, "grid": 20},
        )
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "saved"
        assert data["momentum"] == 50
        assert data["reversion"] == 30
        assert data["grid"] == 20

    def test_save_allocation_invalid_sum(self, client):
        """POST /api/allocation/save should reject invalid allocation."""
        response = client.post(
            "/api/allocation/save",
            params={"momentum": 50, "reversion": 30, "grid": 15},
        )
        assert response.status_code == 400

    def test_save_allocation_persists(self, client):
        """Saved allocation should be returned on next GET."""
        # Save
        client.post(
            "/api/allocation/save",
            params={"momentum": 60, "reversion": 20, "grid": 20},
        )

        # Get
        response = client.get("/api/allocation")
        data = response.json()

        assert data["momentum"] == 60
        assert data["reversion"] == 20
        assert data["grid"] == 20
        assert data["preset"] == "custom"

    def test_set_preset_morning(self, client):
        """POST /api/allocation/preset should apply morning preset."""
        response = client.post(
            "/api/allocation/preset",
            params={"preset": "morning"},
        )
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "preset_applied"
        assert data["preset"] == "morning"
        assert data["momentum"] == 50
        assert data["reversion"] == 30
        assert data["grid"] == 20

    def test_set_preset_afternoon(self, client):
        """POST /api/allocation/preset should apply afternoon preset."""
        response = client.post(
            "/api/allocation/preset",
            params={"preset": "afternoon"},
        )
        assert response.status_code == 200

        data = response.json()
        assert data["momentum"] == 30
        assert data["reversion"] == 40
        assert data["grid"] == 30

    def test_set_preset_invalid(self, client):
        """POST /api/allocation/preset should reject invalid preset."""
        response = client.post(
            "/api/allocation/preset",
            params={"preset": "invalid"},
        )
        assert response.status_code == 400

    def test_reset_allocation(self, client):
        """POST /api/allocation/reset should reset to defaults."""
        # First change allocation
        client.post(
            "/api/allocation/save",
            params={"momentum": 60, "reversion": 20, "grid": 20},
        )

        # Then reset
        response = client.post("/api/allocation/reset")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "reset"
        assert data["momentum"] == 40
        assert data["reversion"] == 35
        assert data["grid"] == 25

    def test_get_presets(self, client):
        """GET /api/allocation/presets should return all presets."""
        response = client.get("/api/allocation/presets")
        assert response.status_code == 200

        data = response.json()
        assert "presets" in data
        presets = data["presets"]

        assert "morning" in presets
        assert "afternoon" in presets
        assert "evening" in presets

        assert presets["morning"]["momentum"] == 50
        assert presets["afternoon"]["reversion"] == 40
        assert presets["evening"]["grid"] == 25


class TestAllocationIntegration:
    """Test allocation integration with signals."""

    def test_allocation_affects_signal(self, client):
        """Allocation should affect composite signal calculation."""
        import pandas as pd
        import numpy as np

        # Initialize signal generator
        from backend.analytics.signals import init_signal_generator, get_signal_generator

        signal_gen = init_signal_generator()
        if not signal_gen:
            pytest.skip("Signal generator not initialized")

        # Create test prices (uptrend)
        rising_prices = pd.Series(np.linspace(100, 150, 50))

        # Get signal with default allocation
        import asyncio

        signal_default = asyncio.run(
            signal_gen.generate_signal("TEST", rising_prices.copy())
        )
        default_score = signal_default["score"]

        # Change allocation to favor reversion (reduce momentum weight)
        client.post(
            "/api/allocation/save",
            params={"momentum": 20, "reversion": 60, "grid": 20},
        )

        # Get signal with new allocation
        signal_modified = asyncio.run(
            signal_gen.generate_signal("TEST", rising_prices.copy())
        )
        modified_score = signal_modified["score"]

        # Scores should be different
        # (momentum favors uptrend, reversion disfavors it)
        assert default_score != modified_score


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
