#!/usr/bin/env python3
"""Archive trades older than retention period from JSONL log.

Usage:
    python scripts/archive_old_trades.py --days 1095  # 3 years
    python scripts/archive_old_trades.py --days 90    # 90 days
    python scripts/archive_old_trades.py --date 2023-07-02

Implements: RETENTION_POLICY.md
"""

import argparse
import gzip
import hashlib
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_cutoff_date(days=None, date=None):
    """Calculate cutoff date for archival."""
    if date:
        return datetime.fromisoformat(date).date()
    elif days:
        return (datetime.utcnow() - timedelta(days=days)).date()
    else:
        raise ValueError("Must specify --days or --date")


def archive_trades(active_log, archive_dir, cutoff_date, dry_run=False):
    """Move trades older than cutoff_date to archive."""
    archive_dir.mkdir(exist_ok=True)

    trades_to_archive = []
    trades_to_keep = []

    # Read active log
    if not active_log.exists():
        logger.warning(f"Active log not found: {active_log}")
        return 0

    with open(active_log) as f:
        for line in f:
            if not line.strip():
                continue

            try:
                data = json.loads(line)
                if data.get('event_type') != 'TRADE':
                    trades_to_keep.append(line)
                    continue

                trade_date = datetime.fromisoformat(
                    data['timestamp']
                ).date()

                if trade_date < cutoff_date:
                    trades_to_archive.append(data)
                else:
                    trades_to_keep.append(line)

            except json.JSONDecodeError:
                logger.warning(f"Skipped invalid JSON: {line[:50]}")
                trades_to_keep.append(line)

    # Write archive
    if trades_to_archive:
        year = trades_to_archive[0]['timestamp'][:4]
        archive_file = archive_dir / f"trades_{year}.jsonl.gz"

        logger.info(f"Archiving {len(trades_to_archive)} trades to {archive_file}")

        if not dry_run:
            with gzip.open(archive_file, 'wt') as f:
                for trade in trades_to_archive:
                    f.write(json.dumps(trade) + '\n')

            # Verify archive
            with gzip.open(archive_file, 'rt') as f:
                archived_count = sum(1 for _ in f)

            if archived_count != len(trades_to_archive):
                logger.error(f"Archive mismatch: wrote {len(trades_to_archive)}, verified {archived_count}")
                return 0

            # Calculate checksum
            with open(archive_file, 'rb') as f:
                checksum = hashlib.sha256(f.read()).hexdigest()

            # Save checksum
            checksums_file = archive_dir / '.checksums'
            with open(checksums_file, 'a') as f:
                f.write(f"{checksum}  {archive_file.name}\n")

            logger.info(f"✅ Archived {len(trades_to_archive)} trades")
            logger.info(f"   Checksum: {checksum}")

    # Update active log (keep non-archived trades)
    if not dry_run and trades_to_archive:
        with open(active_log, 'w') as f:
            f.writelines(trades_to_keep)

        logger.info(f"✅ Updated active log: {len(trades_to_keep)} trades remaining")

    return len(trades_to_archive)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--days', type=int, help='Archive trades older than N days')
    parser.add_argument('--date', help='Archive trades older than YYYY-MM-DD')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be archived')
    args = parser.parse_args()

    if not args.days and not args.date:
        parser.error("Must specify --days or --date")

    cutoff_date = get_cutoff_date(args.days, args.date)
    active_log = Path('logs/immutable/trades_active.jsonl')
    archive_dir = Path('logs/archive')

    logger.info(f"Archiving trades older than {cutoff_date}")
    if args.dry_run:
        logger.info("(DRY RUN - no changes will be made)")

    archived = archive_trades(active_log, archive_dir, cutoff_date, args.dry_run)

    if archived:
        logger.info(f"✅ Archived {archived} trades")
    else:
        logger.info("✅ No trades to archive")


if __name__ == '__main__':
    main()
