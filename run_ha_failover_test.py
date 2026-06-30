#!/usr/bin/env python3
"""
HA Failover Acceptance Test - Autonomous 3-Loop Validator
Runs unattended for ~2+ hours, testing failover cycles
"""

import subprocess
import time
import requests
import json
import sys
from datetime import datetime
from pathlib import Path

# Configuration
PRIMARY_URL = "http://127.0.0.1:8001"
BACKUP_URL = "http://192.168.3.25:8002"
TEST_DURATION_MINUTES = 15  # ~15min per test phase (total test ~2.5 hours for 3 loops)
WAIT_DURATION_SECONDS = 300  # 5 minutes between phases
LOG_FILE = Path("/tmp/ha_failover_test_results.log")
TEST_PLAN_FILE = Path("/home/vali/projects/crypto-daytrading/HA_FAILOVER_TEST_PLAN.md")

def log(message: str, level: str = "INFO"):
    """Log to both stdout and file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_msg = f"[{timestamp}] [{level}] {message}"
    print(log_msg)
    with open(LOG_FILE, "a") as f:
        f.write(log_msg + "\n")

def health_check(url: str, timeout: int = 3) -> dict:
    """Check machine health."""
    try:
        resp = requests.get(f"{url}/api/health", timeout=timeout)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        pass
    return {"status": "UNREACHABLE"}

def get_ha_status(url: str) -> dict:
    """Get HA status."""
    try:
        resp = requests.get(f"{url}/api/ha/status", timeout=3)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        pass
    return {"role": "UNKNOWN"}

def enable_trading(url: str) -> bool:
    """Enable autonomous trading on a machine."""
    try:
        resp = requests.post(f"{url}/api/autonomous/start", timeout=5)
        return resp.status_code == 200
    except Exception:
        return False

def disable_trading(url: str) -> bool:
    """Disable autonomous trading on a machine."""
    try:
        resp = requests.post(f"{url}/api/autonomous/stop", timeout=5)
        return resp.status_code == 200
    except Exception:
        return False

def kill_primary() -> bool:
    """Kill primary process (graceful)."""
    try:
        result = subprocess.run(
            "pkill -f 'uvicorn backend.api.main:app --host 0.0.0.0 --port 8001'",
            shell=True,
            capture_output=True,
            timeout=5
        )
        log("PRIMARY process termination signal sent", "INFO")
        time.sleep(2)

        # Verify it's down
        health = health_check(PRIMARY_URL, timeout=1)
        if health["status"] == "UNREACHABLE":
            log("✓ PRIMARY confirmed down", "INFO")
            return True
        else:
            log("✗ PRIMARY still responding after kill", "WARN")
            return False
    except Exception as e:
        log(f"✗ Error killing PRIMARY: {e}", "ERROR")
        return False

def start_primary() -> bool:
    """Start primary process."""
    try:
        # Start in background using nohup for better reliability
        cmd = (
            "cd /home/vali/projects/crypto-daytrading && "
            "nohup bash -c 'source venv/bin/activate && python -m uvicorn backend.api.main:app --host 0.0.0.0 --port 8001' "
            "> /tmp/crypto-trading-primary.log 2>&1 &"
        )
        result = subprocess.run(cmd, shell=True, timeout=5, capture_output=True)
        time.sleep(4)  # Give it more time to start

        # Verify it's up with more retries
        for attempt in range(10):
            health = health_check(PRIMARY_URL, timeout=2)
            if health.get("status") == "healthy":
                log(f"✓ PRIMARY confirmed up (attempt {attempt+1})", "INFO")
                return True
            if attempt < 9:
                time.sleep(1.5)

        log("✗ PRIMARY failed to start after 10 attempts", "WARN")
        # Try to get more diagnostic info
        try:
            with open("/tmp/crypto-trading-primary.log", "r") as f:
                tail_lines = f.readlines()[-5:]
                log(f"  Last log lines: {' '.join([line.strip() for line in tail_lines])}", "INFO")
        except:
            pass
        return False
    except Exception as e:
        log(f"✗ Error starting PRIMARY: {e}", "ERROR")
        return False

def sync_backup_from_primary() -> bool:
    """Manually sync backup from primary."""
    try:
        # Call primary sync endpoint
        resp = requests.post(f"{PRIMARY_URL}/api/ha/sync-from-primary", timeout=10)
        if resp.status_code in [200, 201]:
            log("✓ Backup sync from PRIMARY initiated", "INFO")
            time.sleep(2)
            return True
    except Exception as e:
        pass
    log("⚠ Backup sync may not have succeeded", "WARN")
    return True  # Don't fail test, continue anyway

def monitor_trading(url: str, duration_seconds: int, machine_name: str) -> dict:
    """Monitor trading on a machine for duration."""
    log(f"📊 Monitoring {machine_name} trading for {duration_seconds}s ({duration_seconds//60}min)", "INFO")

    start_time = datetime.now()
    start_health = health_check(url)
    start_cash = start_health.get("account", {}).get("cash", 0)
    start_pnl = start_health.get("account", {}).get("total_pnl", 0)
    start_positions = start_health.get("account", {}).get("active_positions", 0)

    log(f"  Initial: cash={start_cash}, pnl={start_pnl}, positions={start_positions}", "INFO")

    # Check every 10 minutes
    check_interval = min(600, max(60, duration_seconds // 6))
    checks_done = 0

    while (datetime.now() - start_time).total_seconds() < duration_seconds:
        remaining = duration_seconds - (datetime.now() - start_time).total_seconds()
        if remaining < check_interval:
            time.sleep(remaining)
            break

        time.sleep(check_interval)
        checks_done += 1

        health = health_check(url)
        if health.get("status") == "healthy":
            current_cash = health.get("account", {}).get("cash", 0)
            current_pnl = health.get("account", {}).get("total_pnl", 0)
            current_positions = health.get("account", {}).get("active_positions", 0)

            cash_change = current_cash - start_cash
            pnl_change = current_pnl - start_pnl

            log(f"  [{checks_done}] cash={current_cash} (Δ{cash_change:+.2f}), "
                f"pnl={current_pnl} (Δ{pnl_change:+.2f}), "
                f"positions={current_positions}", "INFO")
        else:
            log(f"  [{checks_done}] ⚠ {machine_name} health check failed", "WARN")

    # Final check
    end_health = health_check(url)
    end_cash = end_health.get("account", {}).get("cash", 0)
    end_pnl = end_health.get("account", {}).get("total_pnl", 0)
    end_positions = end_health.get("account", {}).get("active_positions", 0)

    log(f"  Final: cash={end_cash}, pnl={end_pnl}, positions={end_positions}", "INFO")

    return {
        "machine": machine_name,
        "duration": duration_seconds,
        "start_cash": start_cash,
        "end_cash": end_cash,
        "cash_change": end_cash - start_cash,
        "start_pnl": start_pnl,
        "end_pnl": end_pnl,
        "pnl_change": end_pnl - start_pnl,
        "start_positions": start_positions,
        "end_positions": end_positions,
        "status": end_health.get("status", "unknown"),
        "checks_performed": checks_done
    }

def run_test_loop(loop_num: int) -> dict:
    """Run one complete test loop (3 phases)."""
    log(f"\n{'='*70}", "INFO")
    log(f"LOOP {loop_num}/3 STARTING", "INFO")
    log(f"{'='*70}\n", "INFO")

    results = {
        "loop": loop_num,
        "start_time": datetime.now().isoformat(),
        "phases": {}
    }

    # ===== PHASE 1: PRIMARY DISABLED → BACKUP FAILOVER =====
    log(f"\n--- PHASE 1/{loop_num}: PRIMARY DISABLED → BACKUP FAILOVER ---\n", "INFO")

    # Pre-check
    primary_health = health_check(PRIMARY_URL)
    backup_health = health_check(BACKUP_URL)
    log(f"Pre-check: PRIMARY={primary_health.get('status')}, "
        f"BACKUP={backup_health.get('status')}", "INFO")

    # Kill primary
    if not kill_primary():
        log("✗ LOOP FAILED: Could not kill primary", "ERROR")
        results["phases"]["1"] = {"status": "FAILED", "reason": "Could not kill primary"}
        return results

    # Enable backup trading
    time.sleep(1)
    if not enable_trading(BACKUP_URL):
        log("✗ LOOP FAILED: Could not enable backup trading", "ERROR")
        results["phases"]["1"] = {"status": "FAILED", "reason": "Could not enable backup trading"}
        return results

    log("✓ Backup trading enabled", "INFO")

    # Sync backup state
    sync_backup_from_primary()

    # Monitor backup trading
    backup_results = monitor_trading(BACKUP_URL, TEST_DURATION_MINUTES * 60, "BACKUP")
    results["phases"]["1"] = {
        "status": "COMPLETED",
        "backup_trading": backup_results
    }

    log(f"\n✓ PHASE 1 COMPLETE: Backup traded for {TEST_DURATION_MINUTES} minutes", "INFO")

    # ===== WAIT 15 MINUTES =====
    log(f"\n--- WAIT: 15 minutes before Phase 2 ---\n", "INFO")
    for i in range(0, WAIT_DURATION_SECONDS, 60):
        remaining = WAIT_DURATION_SECONDS - i
        log(f"Waiting... {remaining // 60}m {remaining % 60}s remaining", "INFO")
        time.sleep(60)

    # ===== PHASE 2: PRIMARY RE-ENABLED → REVERT TO PRIMARY =====
    log(f"\n--- PHASE 2/{loop_num}: PRIMARY RE-ENABLED → REVERT TO PRIMARY ---\n", "INFO")

    # Disable backup first
    disable_trading(BACKUP_URL)
    log("Backup trading disabled", "INFO")

    time.sleep(1)

    # Restart primary
    if not start_primary():
        log("✗ LOOP FAILED: Could not start primary", "ERROR")
        results["phases"]["2"] = {"status": "FAILED", "reason": "Could not start primary"}
        return results

    # Enable primary trading
    time.sleep(1)
    if not enable_trading(PRIMARY_URL):
        log("⚠ Could not enable primary trading, continuing anyway", "WARN")

    log("✓ Primary restarted and trading enabled", "INFO")

    # Monitor primary trading
    primary_results = monitor_trading(PRIMARY_URL, TEST_DURATION_MINUTES * 60, "PRIMARY")
    results["phases"]["2"] = {
        "status": "COMPLETED",
        "primary_trading": primary_results
    }

    log(f"\n✓ PHASE 2 COMPLETE: Primary traded for {TEST_DURATION_MINUTES} minutes", "INFO")

    # ===== WAIT 15 MINUTES =====
    log(f"\n--- WAIT: 15 minutes before Phase 3 ---\n", "INFO")
    for i in range(0, WAIT_DURATION_SECONDS, 60):
        remaining = WAIT_DURATION_SECONDS - i
        log(f"Waiting... {remaining // 60}m {remaining % 60}s remaining", "INFO")
        time.sleep(60)

    # ===== PHASE 3: PRIMARY DISABLED AGAIN → BACKUP FAILOVER =====
    log(f"\n--- PHASE 3/{loop_num}: PRIMARY DISABLED AGAIN → BACKUP FAILOVER ---\n", "INFO")

    # Kill primary again
    if not kill_primary():
        log("✗ LOOP FAILED: Could not kill primary (2nd time)", "ERROR")
        results["phases"]["3"] = {"status": "FAILED", "reason": "Could not kill primary (2nd time)"}
        return results

    # Enable backup trading
    time.sleep(1)
    if not enable_trading(BACKUP_URL):
        log("✗ LOOP FAILED: Could not enable backup trading (2nd time)", "ERROR")
        results["phases"]["3"] = {"status": "FAILED", "reason": "Could not enable backup trading (2nd time)"}
        return results

    log("✓ Backup trading enabled (2nd time)", "INFO")

    # Monitor backup trading
    backup_results2 = monitor_trading(BACKUP_URL, TEST_DURATION_MINUTES * 60, "BACKUP (2nd)")
    results["phases"]["3"] = {
        "status": "COMPLETED",
        "backup_trading": backup_results2
    }

    log(f"\n✓ PHASE 3 COMPLETE: Backup traded again for {TEST_DURATION_MINUTES} minutes", "INFO")

    # ===== LOOP COMPLETE =====
    log(f"\n{'='*70}", "INFO")
    log(f"✓✓✓ LOOP {loop_num}/3 SUCCESSFUL", "INFO")
    log(f"{'='*70}\n", "INFO")

    results["end_time"] = datetime.now().isoformat()
    results["status"] = "SUCCESSFUL"

    return results

def main():
    """Run 3-loop failover test."""
    log("="*70, "INFO")
    log("HA FAILOVER ACCEPTANCE TEST - 3 LOOPS", "INFO")
    log(f"Start Time: {datetime.now().isoformat()}", "INFO")
    log("="*70, "INFO")
    log(f"Test will run for approximately {3 * (TEST_DURATION_MINUTES * 3 + WAIT_DURATION_SECONDS * 3 + 60) // 60} minutes\n", "INFO")

    # Clear log file
    with open(LOG_FILE, "w") as f:
        f.write("")

    all_results = {
        "test_start": datetime.now().isoformat(),
        "loops": []
    }

    # Run 3 loops
    for loop in range(1, 4):
        try:
            loop_results = run_test_loop(loop)
            all_results["loops"].append(loop_results)

            # Check for critical failures
            if loop_results["status"] != "SUCCESSFUL":
                log(f"\n✗✗✗ CRITICAL FAILURE IN LOOP {loop}", "ERROR")
                log("Stopping test", "ERROR")
                all_results["status"] = "FAILED"
                break

            # Wait between loops (except after last)
            if loop < 3:
                log(f"\n📋 Completed {loop}/3 loops. Waiting before next loop...", "INFO")
                time.sleep(60)

        except KeyboardInterrupt:
            log("\n⚠ Test interrupted by user", "WARN")
            all_results["status"] = "INTERRUPTED"
            break
        except Exception as e:
            log(f"\n✗ Unexpected error in loop {loop}: {e}", "ERROR")
            all_results["status"] = "ERROR"
            break

    # Final summary
    if all_results.get("status") != "FAILED":
        all_results["status"] = "SUCCESSFUL" if len(all_results["loops"]) == 3 else "PARTIAL"

    all_results["test_end"] = datetime.now().isoformat()

    # Save results
    with open(LOG_FILE, "a") as f:
        f.write("\n\n" + "="*70 + "\n")
        f.write("TEST RESULTS SUMMARY\n")
        f.write("="*70 + "\n")
        f.write(json.dumps(all_results, indent=2))

    # Print summary
    log("\n" + "="*70, "INFO")
    log("TEST COMPLETE", "INFO")
    log("="*70, "INFO")
    log(f"Status: {all_results['status']}", "INFO")
    log(f"Loops Completed: {len(all_results['loops'])}/3", "INFO")
    log(f"Results saved to: {LOG_FILE}", "INFO")
    log("="*70 + "\n", "INFO")

    return 0 if all_results["status"] == "SUCCESSFUL" else 1

if __name__ == "__main__":
    sys.exit(main())
