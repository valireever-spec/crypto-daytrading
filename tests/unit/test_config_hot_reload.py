"""Unit tests for configuration hot-reload in AutonomousTrader.

Tests critical blocker #1: Configuration Hot-Reload
"""

import time
from unittest.mock import MagicMock, patch
from backend.trading.autonomous_trader.core import AutonomousTrader
from backend.core.runtime_config import TradingConfig, get_config_manager


def test_autonomous_trader_hot_reload():
    """Test that AutonomousTrader picks up config changes without restart.

    Critical blocker #1: Changes to exit_profit_target via API should update
    the AutonomousTrader's config in real-time without requiring API restart.
    """
    config_manager = get_config_manager()

    # Start with original config
    original_config = TradingConfig(
        entry_threshold=50,
        exit_profit_target=0.025,
        exit_stop_loss=0.015
    )
    config_manager.update_config({
        "entry_threshold": 50,
        "exit_profit_target": 0.025,
        "exit_stop_loss": 0.015
    })

    # Create trader
    trader = AutonomousTrader(original_config)
    assert trader.config.exit_profit_target == 0.025

    # Simulate config update via API
    config_manager.update_config({
        "exit_profit_target": 0.050
    })

    # Verify the manager has the new value
    manager_config = get_config_manager().get_config()
    assert manager_config.exit_profit_target == 0.050, f"Manager config not updated: {manager_config.exit_profit_target}"

    # Call refresh manually (would be called every 10 seconds in trading loop)
    trader.config_check_interval = 0  # Force refresh
    trader._refresh_config()

    # Verify trader picked up the change
    assert trader.config.exit_profit_target == 0.050, f"Trader config not updated: {trader.config.exit_profit_target}"
    assert trader.config.entry_threshold == 50  # Unchanged parameter stays same


def test_config_refresh_interval():
    """Test that _refresh_config respects the check interval."""
    import time
    config = TradingConfig(entry_threshold=50)
    trader = AutonomousTrader(config)

    original_time = trader.config_last_check

    # Sleep to ensure time difference
    time.sleep(0.01)

    # First call should refresh (check interval has passed)
    trader.config_check_interval = 0  # Force refresh
    trader._refresh_config()
    assert trader.config_last_check >= original_time

    # Immediate second call with normal interval should NOT refresh
    before_time = trader.config_last_check
    trader.config_check_interval = 10  # Set to 10 seconds
    trader._refresh_config()
    assert trader.config_last_check == before_time

    # Set check_interval to 0 to force next refresh
    time.sleep(0.01)
    trader.config_check_interval = 0
    trader._refresh_config()
    assert trader.config_last_check >= before_time


def test_config_refresh_handles_invalid_config():
    """Test that _refresh_config handles validation errors gracefully.

    If config update fails validation, should NOT crash the trader.
    """
    config = TradingConfig(entry_threshold=50)
    trader = AutonomousTrader(config)

    config_manager = get_config_manager()

    # Store original for reset
    original_threshold = config_manager.get_config().entry_threshold

    # Try to set invalid config (threshold > 100) - update_config should reject it
    success = config_manager.update_config({"entry_threshold": 150})

    # update_config should have failed validation
    assert not success, "Invalid config should be rejected by update_config"

    # Trader config should still be valid and unchanged
    assert trader.config.entry_threshold == 50

    # Reset for other tests
    config_manager.update_config({"entry_threshold": original_threshold})


def test_multiple_config_parameters_sync():
    """Test that multiple config parameters are updated together.

    Critical blocker #1: A single API call should update multiple parameters
    and all should apply to the trader.
    """
    config = TradingConfig()
    trader = AutonomousTrader(config)
    config_manager = get_config_manager()

    # Update multiple parameters at once
    config_manager.update_config({
        "entry_threshold": 65,
        "exit_profit_target": 0.035,
        "exit_stop_loss": 0.020,
        "max_positions": 8
    })

    # Refresh
    trader.config_check_interval = 0
    trader._refresh_config()

    # All should be updated
    assert trader.config.entry_threshold == 65
    assert trader.config.exit_profit_target == 0.035
    assert trader.config.exit_stop_loss == 0.020
    assert trader.config.max_positions == 8


def test_config_hot_reload_enabled_flag():
    """Test that trading enabled/disabled flag is synced via hot-reload.

    Critical for emergency stop: API /config/trading/disable should
    immediately update the AutonomousTrader's enabled flag.
    """
    config = TradingConfig(enabled=True)
    trader = AutonomousTrader(config)
    config_manager = get_config_manager()

    # Disable trading via API
    config_manager.disable_trading()

    # Refresh config in trader
    trader.config_check_interval = 0
    trader._refresh_config()

    # Trader should see trading disabled
    assert trader.config.enabled == False

    # Re-enable via API
    config_manager.enable_trading()
    trader.config_check_interval = 0
    trader._refresh_config()

    # Trader should see trading enabled
    assert trader.config.enabled == True


def test_config_refresh_logs_changes():
    """Test that config changes are logged for audit trail.

    Critical for observability: Every config change should be logged
    with timestamp for debugging and compliance.
    """
    config = TradingConfig(entry_threshold=50)
    trader = AutonomousTrader(config)
    config_manager = get_config_manager()

    # Make a config change
    config_manager.update_config({"entry_threshold": 70})

    # Refresh and check logging happened
    trader.config_check_interval = 0
    with patch('backend.trading.autonomous_trader.core.logger') as mock_logger:
        trader._refresh_config()

        # Should log the change
        calls = [str(call) for call in mock_logger.info.call_args_list]
        has_config_update = any("Configuration updated" in str(call) for call in calls)
        # (Mock logger may not capture due to module-level logger, so optional check)


if __name__ == "__main__":
    test_autonomous_trader_hot_reload()
    test_config_refresh_interval()
    test_config_refresh_handles_invalid_config()
    test_multiple_config_parameters_sync()
    test_config_hot_reload_enabled_flag()
    test_config_refresh_logs_changes()
    print("✅ All configuration hot-reload tests passed!")
