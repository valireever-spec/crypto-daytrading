#!/usr/bin/env python3
"""Delete archived trades older than 3+ years (cleanup script).

Archives are compressed and stored long-term, but we can delete after
additional retention period (e.g., keep archives for 3 years + 6 months).

Usage:
    python scripts/cleanup_old_archives.py --max-age 1095  # Delete archives >3 years old
    python scripts/cleanup_old_archives.py --max-age 1095 --dry-run

Implements: RETENTION_POLICY.md (archive cleanup section)
"""

import argparse
import logging
from datetime import datetime, timedelta
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def cleanup_old_archives(archive_dir, max_age_days, dry_run=False):
    """Delete archived files older than max_age_days."""
    if not archive_dir.exists():
        logger.warning(f"Archive directory not found: {archive_dir}")
        return 0

    cutoff_date = datetime.utcnow() - timedelta(days=max_age_days)
    deleted_count = 0
    freed_space = 0

    archive_files = sorted(archive_dir.glob('trades_*.jsonl.gz'))
    if not archive_files:
        logger.info("No archive files found")
        return 0

    logger.info(f"Cleaning archives modified before {cutoff_date.date()}")

    for archive_file in archive_files:
        file_mtime = datetime.fromtimestamp(archive_file.stat().st_mtime)
        file_size = archive_file.stat().st_size

        if file_mtime < cutoff_date:
            size_mb = file_size / (1024 * 1024)
            logger.info(f"Marking for deletion: {archive_file.name} ({size_mb:.1f} MB, modified {file_mtime.date()})")

            if not dry_run:
                try:
                    archive_file.unlink()
                    deleted_count += 1
                    freed_space += file_size
                    logger.info(f"  ✅ Deleted")
                except Exception as e:
                    logger.error(f"  ❌ Failed to delete: {e}")
            else:
                deleted_count += 1
                freed_space += file_size

    if dry_run:
        logger.info(f"(DRY RUN) Would delete {deleted_count} archives, freeing {freed_space / (1024*1024):.1f} MB")
    else:
        logger.info(f"✅ Deleted {deleted_count} archives, freed {freed_space / (1024*1024):.1f} MB")

    # Update checksums file to remove entries for deleted files
    if deleted_count > 0 and not dry_run:
        checksums_file = archive_dir / '.checksums'
        if checksums_file.exists():
            try:
                with open(checksums_file) as f:
                    lines = f.readlines()

                # Keep only checksums for existing files
                remaining_lines = []
                removed_count = 0

                for line in lines:
                    if not line.strip():
                        continue

                    parts = line.split(None, 1)
                    if len(parts) < 2:
                        continue

                    filename = parts[1].strip()
                    filepath = archive_dir / filename

                    if filepath.exists():
                        remaining_lines.append(line)
                    else:
                        removed_count += 1
                        logger.debug(f"Removed checksum entry: {filename}")

                # Write updated checksums
                with open(checksums_file, 'w') as f:
                    f.writelines(remaining_lines)

                logger.info(f"✅ Updated checksums file: removed {removed_count} entries")

            except Exception as e:
                logger.error(f"⚠️  Failed to update checksums file: {e}")

    return deleted_count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--max-age', type=int, default=1095,
                        help='Delete archives older than N days (default: 1095 = 3 years)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be deleted')
    args = parser.parse_args()

    archive_dir = Path('logs/archive')

    if args.dry_run:
        logger.info("(DRY RUN - no deletions will be performed)")

    logger.info(f"Cleaning archives older than {args.max_age} days")
    deleted = cleanup_old_archives(archive_dir, args.max_age, args.dry_run)

    if deleted:
        logger.info(f"✅ Cleanup complete: {deleted} archives removed")
    else:
        logger.info("✅ No archives to clean up")


if __name__ == '__main__':
    main()
