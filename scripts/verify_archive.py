#!/usr/bin/env python3
"""Verify integrity of archived trades.

Usage:
    python scripts/verify_archive.py --active       # Verify active log
    python scripts/verify_archive.py --archives     # Verify all archives
    python scripts/verify_archive.py --all          # Verify everything
"""

import argparse
import gzip
import hashlib
import json
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def verify_jsonl_integrity(filepath):
    """Verify JSONL file has valid JSON on every line."""
    invalid_lines = []
    line_count = 0

    try:
        if filepath.suffix == '.gz':
            open_fn = gzip.open
            mode = 'rt'
        else:
            open_fn = open
            mode = 'r'

        with open_fn(filepath, mode) as f:
            for line_no, line in enumerate(f, 1):
                if not line.strip():
                    continue

                line_count += 1
                try:
                    json.loads(line)
                except json.JSONDecodeError as e:
                    invalid_lines.append((line_no, str(e)[:50]))

        if invalid_lines:
            logger.error(f"❌ {filepath}: {len(invalid_lines)} invalid lines")
            for line_no, error in invalid_lines[:5]:
                logger.error(f"   Line {line_no}: {error}")
            return False

        logger.info(f"✅ {filepath}: {line_count} valid trades")
        return True

    except Exception as e:
        logger.error(f"❌ {filepath}: {e}")
        return False


def verify_checksums(archive_dir):
    """Verify checksums of archived files."""
    checksums_file = archive_dir / '.checksums'

    if not checksums_file.exists():
        logger.warning(f"⚠️  No checksums file: {checksums_file}")
        return True

    valid_count = 0
    invalid_count = 0

    with open(checksums_file) as f:
        for line in f:
            if not line.strip():
                continue

            # Parse "HASH  FILENAME" format (two spaces separate)
            # Handle filenames with spaces by splitting on first occurrence of 2+ spaces
            parts = line.split(None, 1)  # Split on first whitespace
            if len(parts) < 2:
                logger.warning(f"⚠️  Invalid checksum line format: {line[:60]}")
                continue

            expected_hash = parts[0]
            filename = parts[1].strip()

            # Validate hash format (should be 64 hex chars for SHA256)
            if len(expected_hash) != 64 or not all(c in '0123456789abcdef' for c in expected_hash):
                logger.warning(f"⚠️  Invalid hash format: {expected_hash}")
                continue

            filepath = archive_dir / filename

            if not filepath.exists():
                logger.warning(f"⚠️  File not found: {filepath}")
                invalid_count += 1
                continue

            # Calculate hash
            try:
                with open(filepath, 'rb') as f:
                    actual_hash = hashlib.sha256(f.read()).hexdigest()

                if actual_hash == expected_hash:
                    logger.info(f"✅ {filename}: hash verified")
                    valid_count += 1
                else:
                    logger.error(f"❌ {filename}: hash mismatch!")
                    logger.error(f"   Expected: {expected_hash}")
                    logger.error(f"   Actual:   {actual_hash}")
                    invalid_count += 1
            except Exception as e:
                logger.error(f"❌ {filename}: failed to read for verification: {e}")
                invalid_count += 1

    return invalid_count == 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--active', action='store_true', help='Verify active log only')
    parser.add_argument('--archives', action='store_true', help='Verify archives only')
    parser.add_argument('--all', action='store_true', help='Verify everything')
    args = parser.parse_args()

    if not any([args.active, args.archives, args.all]):
        args.all = True

    active_log = Path('logs/immutable/trades_active.jsonl')
    archive_dir = Path('logs/archive')

    results = []

    # Verify active log
    if args.active or args.all:
        logger.info("Verifying active log...")
        results.append(verify_jsonl_integrity(active_log))

    # Verify archives
    if args.archives or args.all:
        logger.info("Verifying archives...")
        if archive_dir.exists():
            for archive_file in sorted(archive_dir.glob('trades_*.jsonl.gz')):
                results.append(verify_jsonl_integrity(archive_file))

            if results:
                logger.info("Verifying checksums...")
                results.append(verify_checksums(archive_dir))
        else:
            logger.warning(f"Archive directory not found: {archive_dir}")

    # Summary
    logger.info("")
    if all(results):
        logger.info("✅ All verifications passed")
        return 0
    else:
        logger.error("❌ Some verifications failed")
        return 1


if __name__ == '__main__':
    exit(main())
