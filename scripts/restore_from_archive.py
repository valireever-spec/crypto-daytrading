#!/usr/bin/env python3
"""Restore trades from archive to active JSONL log.

Usage:
    python scripts/restore_from_archive.py --from 2024-01-01 --to 2024-03-31
    python scripts/restore_from_archive.py --year 2024
    python scripts/restore_from_archive.py --test --date 2025-01-01  # Dry-run

Implements: RETENTION_POLICY.md disaster recovery procedure
"""

import argparse
import gzip
import json
import logging
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def restore_trades(archive_dir, active_log, start_date=None, end_date=None, year=None, dry_run=False):
    """Restore trades from archive to active log."""
    if not archive_dir.exists():
        logger.error(f"❌ Archive directory not found: {archive_dir}")
        return 0

    # Determine which archive files to restore
    archive_files = sorted(archive_dir.glob('trades_*.jsonl.gz'))
    if not archive_files:
        logger.warning(f"⚠️  No archive files found in {archive_dir}")
        return 0

    restored_count = 0

    # Read existing active log to avoid duplicates
    existing_trades = set()
    if active_log.exists():
        logger.info(f"Reading existing active log to prevent duplicates...")
        with open(active_log) as f:
            for line in f:
                try:
                    data = json.loads(line)
                    if data.get('event_type') == 'TRADE':
                        # Use order_id as unique identifier
                        trade_id = data.get('order_id')
                        if trade_id:
                            existing_trades.add(trade_id)
                except json.JSONDecodeError:
                    continue

    logger.info(f"Found {len(existing_trades)} existing trades to avoid duplicating")

    # Restore from selected archive files
    temp_trades = []

    for archive_file in archive_files:
        logger.info(f"Reading {archive_file.name}...")

        try:
            with gzip.open(archive_file, 'rt') as f:
                for line in f:
                    try:
                        data = json.loads(line)

                        # Check date filters
                        if start_date or end_date:
                            trade_date = datetime.fromisoformat(
                                data['timestamp']
                            ).date()

                            if start_date and trade_date < start_date:
                                continue
                            if end_date and trade_date > end_date:
                                continue

                        # Check year filter
                        if year:
                            trade_year = int(data['timestamp'][:4])
                            if trade_year != year:
                                continue

                        # Avoid duplicates
                        trade_id = data.get('order_id')
                        if trade_id in existing_trades:
                            logger.debug(f"Skipping duplicate trade: {trade_id}")
                            continue

                        temp_trades.append(data)
                        existing_trades.add(trade_id)

                    except json.JSONDecodeError as e:
                        logger.warning(f"⚠️  Skipped invalid JSON: {line[:50]}")
                        continue

        except Exception as e:
            logger.error(f"❌ Failed to read archive: {archive_file}: {e}")
            continue

    if not temp_trades:
        logger.info("✅ No trades to restore (already in active log or outside date range)")
        return 0

    logger.info(f"Found {len(temp_trades)} trades to restore")

    if dry_run:
        logger.info(f"(DRY RUN) Would restore {len(temp_trades)} trades")
        return len(temp_trades)

    # Append to active log
    try:
        with open(active_log, 'a') as f:
            for trade in temp_trades:
                f.write(json.dumps(trade) + '\n')

        logger.info(f"✅ Restored {len(temp_trades)} trades to {active_log}")
        return len(temp_trades)

    except Exception as e:
        logger.error(f"❌ Failed to write to active log: {e}")
        return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--from', dest='start_date', help='Restore trades from YYYY-MM-DD')
    parser.add_argument('--to', dest='end_date', help='Restore trades until YYYY-MM-DD')
    parser.add_argument('--year', type=int, help='Restore all trades from specific year')
    parser.add_argument('--date', help='Restore trades on specific date (alias for --from + --to)')
    parser.add_argument('--test', action='store_true', help='Dry-run test restore')
    args = parser.parse_args()

    # Parse dates
    start_date = None
    end_date = None

    if args.date:
        start_date = datetime.fromisoformat(args.date).date()
        end_date = start_date
    else:
        if args.start_date:
            start_date = datetime.fromisoformat(args.start_date).date()
        if args.end_date:
            end_date = datetime.fromisoformat(args.end_date).date()

    archive_dir = Path('logs/archive')
    active_log = Path('logs/immutable/trades_active.jsonl')

    if args.test:
        logger.info("(TEST MODE - dry run)")
        restored = restore_trades(
            archive_dir, active_log,
            start_date=start_date, end_date=end_date, year=args.year,
            dry_run=True
        )
    else:
        logger.info("Restoring trades from archive...")
        restored = restore_trades(
            archive_dir, active_log,
            start_date=start_date, end_date=end_date, year=args.year,
            dry_run=False
        )

    if restored:
        logger.info(f"✅ Restore complete: {restored} trades")
    else:
        logger.info("✅ No trades to restore")


if __name__ == '__main__':
    main()
