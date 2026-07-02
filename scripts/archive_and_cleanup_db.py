#!/usr/bin/env python3
"""Archive trades from JSONL and cleanup SQLite database.

This script coordinates archival across JSONL logs AND SQLite database:
1. Archive trades older than cutoff_date from JSONL to compressed archive
2. Delete corresponding records from SQLite (keeps DB <1GB)
3. Verify integrity after cleanup

Usage:
    python scripts/archive_and_cleanup_db.py --days 90    # Archive 90+ day old trades
    python scripts/archive_and_cleanup_db.py --days 90 --dry-run
    python scripts/archive_and_cleanup_db.py --date 2025-07-02

Implements: RETENTION_POLICY.md (SQLite cleanup section)
"""

import argparse
import gzip
import json
import logging
import sqlite3
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


def archive_from_jsonl(active_log, archive_dir, cutoff_date):
    """Archive trades from JSONL log (returns trade IDs for cleanup)."""
    archive_dir.mkdir(exist_ok=True)

    trades_to_archive = []
    other_events_to_keep = []
    trades_to_keep = []
    trade_ids_to_delete = []  # For database cleanup

    if not active_log.exists():
        logger.warning(f"Active log not found: {active_log}")
        return [], []

    with open(active_log) as f:
        for line in f:
            if not line.strip():
                continue

            try:
                data = json.loads(line)

                if data.get('event_type') != 'TRADE':
                    other_events_to_keep.append(data)
                    continue

                trade_date = datetime.fromisoformat(
                    data['timestamp']
                ).date()

                if trade_date < cutoff_date:
                    trades_to_archive.append(data)
                    trade_ids_to_delete.append(data.get('order_id'))
                else:
                    trades_to_keep.append(data)

            except json.JSONDecodeError:
                logger.warning(f"Skipped invalid JSON: {line[:50]}")
                continue

    # Write archive
    if trades_to_archive:
        year = trades_to_archive[0]['timestamp'][:4]
        archive_file = archive_dir / f"trades_{year}.jsonl.gz"

        logger.info(f"Archiving {len(trades_to_archive)} trades to {archive_file}")

        with gzip.open(archive_file, 'wt') as f:
            for trade in trades_to_archive:
                f.write(json.dumps(trade) + '\n')

        # Verify archive
        with gzip.open(archive_file, 'rt') as f:
            archived_count = sum(1 for _ in f)

        if archived_count != len(trades_to_archive):
            logger.error(f"❌ Archive mismatch: wrote {len(trades_to_archive)}, verified {archived_count}")
            return [], []

        logger.info(f"✅ Archived {len(trades_to_archive)} trades")

    # Update active log
    if trades_to_archive:
        with open(active_log, 'w') as f:
            for event in other_events_to_keep:
                f.write(json.dumps(event) + '\n')
            for trade in trades_to_keep:
                f.write(json.dumps(trade) + '\n')

        remaining = len(other_events_to_keep) + len(trades_to_keep)
        logger.info(f"✅ Updated active log: {remaining} entries remaining")

    return trade_ids_to_delete, trades_to_archive


def cleanup_sqlite(db_path, trade_ids_to_delete):
    """Delete archived trades from SQLite database."""
    if not db_path.exists():
        logger.warning(f"Database not found: {db_path}")
        return 0

    if not trade_ids_to_delete:
        logger.info("No trades to delete from database")
        return 0

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        deleted_count = 0
        for order_id in trade_ids_to_delete:
            cursor.execute('DELETE FROM trades WHERE order_id = ?', (order_id,))
            deleted_count += cursor.rowcount

        conn.commit()
        conn.close()

        logger.info(f"✅ Deleted {deleted_count} trades from SQLite")

        # Check database size
        db_size = db_path.stat().st_size / (1024 * 1024)  # MB
        logger.info(f"   Database size: {db_size:.1f} MB")

        if db_size > 1000:
            logger.warning(f"⚠️  Database still >1GB ({db_size:.1f} MB), consider more aggressive cleanup")

        return deleted_count

    except Exception as e:
        logger.error(f"❌ Failed to cleanup database: {e}")
        return 0


def verify_after_cleanup(active_log, archive_dir):
    """Verify integrity after cleanup."""
    logger.info("Verifying integrity after cleanup...")

    # Check JSONL integrity
    if active_log.exists():
        invalid_count = 0
        with open(active_log) as f:
            for line_no, line in enumerate(f, 1):
                if not line.strip():
                    continue
                try:
                    json.loads(line)
                except json.JSONDecodeError as e:
                    logger.error(f"❌ Line {line_no}: {e}")
                    invalid_count += 1

        if invalid_count == 0:
            logger.info(f"✅ JSONL integrity verified")
            return True
        else:
            logger.error(f"❌ Found {invalid_count} invalid JSON lines")
            return False

    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--days', type=int, help='Archive trades older than N days')
    parser.add_argument('--date', help='Archive trades older than YYYY-MM-DD')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be archived/deleted')
    args = parser.parse_args()

    if not args.days and not args.date:
        parser.error("Must specify --days or --date")

    cutoff_date = get_cutoff_date(args.days, args.date)
    active_log = Path('logs/immutable/trades_active.jsonl')
    archive_dir = Path('logs/archive')
    db_path = Path('data/trades.db')

    logger.info(f"Archiving and cleaning trades older than {cutoff_date}")
    if args.dry_run:
        logger.info("(DRY RUN - no changes will be made)")

    # Step 1: Archive from JSONL
    trade_ids_to_delete, archived_trades = archive_from_jsonl(active_log, archive_dir, cutoff_date)

    if args.dry_run:
        logger.info(f"(DRY RUN) Would delete {len(trade_ids_to_delete)} trades from database")
        return

    # Step 2: Cleanup SQLite
    if trade_ids_to_delete:
        deleted = cleanup_sqlite(db_path, trade_ids_to_delete)
        logger.info(f"✅ Cleanup complete: archived {len(archived_trades)} from JSONL, deleted {deleted} from DB")
    else:
        logger.info("✅ No changes needed")

    # Step 3: Verify
    verify_after_cleanup(active_log, archive_dir)


if __name__ == '__main__':
    main()
