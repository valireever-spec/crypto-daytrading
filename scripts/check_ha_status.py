#!/usr/bin/env python3
"""
HA Status Checker - Monitor redundancy health and alert on issues.

Usage:
    python3 check_ha_status.py                 # Quick check
    python3 check_ha_status.py --detailed      # Detailed output
    python3 check_ha_status.py --watch 5       # Watch every 5 seconds
"""

import requests
import json
import sys
import time
import argparse
from datetime import datetime
from typing import Dict, Tuple

PRIMARY_API = "http://127.0.0.1:8001"
REDUNDANCY_ENDPOINT = f"{PRIMARY_API}/api/redundancy/status"

# ANSI color codes
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'


def colored(text: str, color: str) -> str:
    """Colorize text."""
    return f"{color}{text}{RESET}"


def format_status(status_str: str) -> str:
    """Format status with color."""
    if "HEALTHY" in status_str or "ACTIVE" in status_str:
        return colored(status_str, GREEN)
    elif "DEGRADED" in status_str or "WARNING" in status_str:
        return colored(status_str, YELLOW)
    elif "DOWN" in status_str or "FAILOVER" in status_str:
        return colored(status_str, RED)
    return status_str


def get_redundancy_status() -> Tuple[bool, Dict]:
    """Fetch redundancy status from API."""
    try:
        response = requests.get(REDUNDANCY_ENDPOINT, timeout=5)
        if response.status_code == 200:
            return True, response.json()
        else:
            return False, {"error": f"HTTP {response.status_code}"}
    except Exception as e:
        return False, {"error": str(e)}


def print_summary(status: Dict) -> None:
    """Print concise status summary."""
    print(f"\n{BOLD}=== REDUNDANCY STATUS ==={RESET}")
    print(f"Timestamp: {status.get('timestamp', 'N/A')}")

    overall = status.get('overall_status', 'UNKNOWN')
    print(f"Overall: {format_status(overall)}")

    redundancy_level = status.get('redundancy_level', 'UNKNOWN')
    print(f"Level: {redundancy_level}")

    # Primary status
    primary_status = status.get('primary', {})
    primary_health = primary_status.get('status', {}).get('healthy', False)
    print(f"Primary: {format_status('HEALTHY' if primary_health else 'DOWN')}")

    # Backup status
    backup_status = status.get('backup', {})
    backup_health = backup_status.get('status', {}).get('healthy', False)
    backup_role = backup_status.get('role', 'UNKNOWN')
    print(f"Backup: {format_status(backup_role)} ({format_status('HEALTHY' if backup_health else 'DOWN')})")

    # Replication
    replication = status.get('replication', {})
    lag = replication.get('lag_seconds')
    lag_status = replication.get('status', 'UNKNOWN')

    if lag is not None:
        lag_str = f"{lag}s"
    else:
        lag_str = "N/A"

    print(f"Replication Lag: {colored(lag_str, YELLOW if lag_status == 'WARNING' else RED if lag_status == 'CRITICAL' else GREEN)} ({lag_status})")

    # Failover readiness
    failover = status.get('failover', {})
    readiness = failover.get('readiness', {}).get('ready', False)
    print(f"Failover Ready: {colored('YES' if readiness else 'NO', GREEN if readiness else RED)}")


def print_detailed(status: Dict) -> None:
    """Print detailed status information."""
    print(f"\n{BOLD}=== DETAILED REDUNDANCY STATUS ==={RESET}\n")

    # Overall
    print(f"{BOLD}OVERALL SYSTEM{RESET}")
    print(f"  Status: {format_status(status.get('overall_status', 'UNKNOWN'))}")
    print(f"  Level: {status.get('redundancy_level', 'UNKNOWN')}")
    print(f"  Timestamp: {status.get('timestamp', 'N/A')}")

    # Primary
    print(f"\n{BOLD}PRIMARY TRADER{RESET}")
    primary = status.get('primary', {})
    primary_status = primary.get('status', {})
    print(f"  Health: {colored('✓ OK' if primary_status.get('healthy') else '✗ DOWN', GREEN if primary_status.get('healthy') else RED)}")
    print(f"  Host: {primary_status.get('host', 'N/A')}")
    print(f"  Role: {primary.get('role', 'UNKNOWN')}")
    print(f"  Status Code: {primary_status.get('status_code', 'N/A')}")
    if 'error' in primary_status:
        print(f"  Error: {primary_status.get('error')}")
    print(f"  Checked: {primary_status.get('timestamp', 'N/A')}")

    # Backup
    print(f"\n{BOLD}BACKUP TRADER{RESET}")
    backup = status.get('backup', {})
    backup_status = backup.get('status', {})
    print(f"  Health: {colored('✓ OK' if backup_status.get('healthy') else '✗ DOWN', GREEN if backup_status.get('healthy') else RED)}")
    print(f"  Host: {backup_status.get('host', 'N/A')}")
    print(f"  Role: {backup.get('role', 'UNKNOWN')}")
    print(f"  Status Code: {backup_status.get('status_code', 'N/A')}")
    if 'error' in backup_status:
        print(f"  Error: {backup_status.get('error')}")
    print(f"  Checked: {backup_status.get('timestamp', 'N/A')}")

    # Failover Readiness
    readiness = backup.get('ready_for_failover', {})
    print(f"  Failover Ready: {colored('YES' if readiness.get('ready') else 'NO', GREEN if readiness.get('ready') else RED)}")
    print(f"  Readiness Reason: {readiness.get('reason', 'N/A')}")
    print(f"  Mode: {readiness.get('mode', 'N/A')}")

    # Replication
    print(f"\n{BOLD}REPLICATION{RESET}")
    replication = status.get('replication', {})
    lag = replication.get('lag_seconds')
    lag_status = replication.get('status', 'UNKNOWN')

    if lag is not None:
        print(f"  Lag: {lag}s")
        print(f"  Status: {format_status(lag_status)}")
    else:
        print(f"  Lag: N/A (unable to calculate)")
        print(f"  Status: {lag_status}")

    print(f"  Warning Threshold: {replication.get('warning_threshold')}s")
    print(f"  Critical Threshold: {replication.get('critical_threshold')}s")

    # Failover
    print(f"\n{BOLD}FAILOVER{RESET}")
    failover = status.get('failover', {})
    print(f"  Active: {colored('YES' if failover.get('active') else 'NO', RED if failover.get('active') else GREEN)}")

    failover_readiness = failover.get('readiness', {})
    print(f"  Ready: {colored('YES' if failover_readiness.get('ready') else 'NO', GREEN if failover_readiness.get('ready') else RED)}")
    print(f"  Reason: {failover_readiness.get('reason', 'N/A')}")


def health_alerts(status: Dict) -> list:
    """Generate alerts based on status."""
    alerts = []

    overall = status.get('overall_status', '')
    if overall == 'DOWN':
        alerts.append(f"{RED}🔴 CRITICAL: System is DOWN{RESET}")
    elif overall == 'DEGRADED':
        alerts.append(f"{YELLOW}⚠️  WARNING: System is DEGRADED{RESET}")
    elif overall == 'FAILOVER_ACTIVE':
        alerts.append(f"{RED}🔴 ALERT: FAILOVER is ACTIVE - Primary is down, Backup is trading{RESET}")

    # Replication lag
    replication = status.get('replication', {})
    lag_status = replication.get('status', '')
    if lag_status == 'CRITICAL':
        lag = replication.get('lag_seconds', 'N/A')
        alerts.append(f"{RED}🔴 CRITICAL: Replication lag {lag}s exceeds threshold{RESET}")
    elif lag_status == 'WARNING':
        lag = replication.get('lag_seconds', 'N/A')
        alerts.append(f"{YELLOW}⚠️  WARNING: Replication lag {lag}s approaching critical{RESET}")

    # Failover readiness
    backup = status.get('backup', {})
    readiness = backup.get('ready_for_failover', {})
    if backup.get('status', {}).get('healthy') and not readiness.get('ready'):
        alerts.append(f"{YELLOW}⚠️  WARNING: Backup is running but not ready for failover{RESET}")

    return alerts


def main():
    parser = argparse.ArgumentParser(description='Monitor HA redundancy status')
    parser.add_argument('--detailed', '-d', action='store_true', help='Show detailed output')
    parser.add_argument('--watch', '-w', type=int, metavar='SECONDS', help='Watch status every N seconds')
    args = parser.parse_args()

    if args.watch:
        # Watch mode
        try:
            iteration = 0
            while True:
                success, status = get_redundancy_status()

                if not success:
                    print(f"{RED}✗ Failed to fetch redundancy status: {status.get('error')}{RESET}")
                    sys.exit(1)

                # Clear screen (Unix/Linux)
                if iteration > 0:
                    print("\033[2J\033[H", end='')

                iteration += 1

                if args.detailed:
                    print_detailed(status)
                else:
                    print_summary(status)

                # Show alerts
                alerts = health_alerts(status)
                if alerts:
                    print(f"\n{BOLD}ALERTS:{RESET}")
                    for alert in alerts:
                        print(f"  {alert}")

                print(f"\n(Watching every {args.watch}s, press Ctrl+C to stop)")
                time.sleep(args.watch)
        except KeyboardInterrupt:
            print("\n\nStopped.")
            sys.exit(0)
    else:
        # One-time check
        success, status = get_redundancy_status()

        if not success:
            print(f"{RED}✗ Failed to fetch redundancy status: {status.get('error')}{RESET}")
            sys.exit(1)

        if args.detailed:
            print_detailed(status)
        else:
            print_summary(status)

        # Show alerts
        alerts = health_alerts(status)
        if alerts:
            print(f"\n{BOLD}ALERTS:{RESET}")
            for alert in alerts:
                print(f"  {alert}")

        # Exit with appropriate code
        overall = status.get('overall_status', '')
        if overall == 'DOWN':
            sys.exit(2)
        elif overall in ['DEGRADED', 'FAILOVER_ACTIVE']:
            sys.exit(1)
        else:
            sys.exit(0)


if __name__ == '__main__':
    main()
