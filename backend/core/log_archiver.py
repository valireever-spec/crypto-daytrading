"""Rotating file handler with automatic gzip compression for rotated logs."""

import gzip
import logging
import os
import shutil
from logging.handlers import RotatingFileHandler
from pathlib import Path


class CompressedRotatingFileHandler(RotatingFileHandler):
    """RotatingFileHandler that automatically compresses rotated files with gzip.

    When a log file is rotated (due to size), the old file is automatically
    compressed to .gz format, saving ~90% disk space for text/JSON logs.

    This is especially important for trading systems where:
    - Logs grow quickly (every trade is logged)
    - Disk space is limited
    - Old logs need retention for compliance/debugging
    """

    def doRollover(self):
        """Roll over log file and compress the rotated file.

        Override parent's doRollover to add compression after rotation.
        """
        # Call parent's rollover (creates backup file)
        super().doRollover()

        # Compress the backup file that was just created
        # Parent creates: "api.log.1", "api.log.2", etc.
        # We'll compress it to: "api.log.1.gz", "api.log.2.gz"
        if self.backupCount > 0:
            for i in range(self.backupCount - 1, 0, -1):
                sfn = f"{self.baseFilename}.{i}"
                dfn = f"{self.baseFilename}.{i + 1}"

                # Remove old compressed file if exists
                if os.path.exists(f"{dfn}.gz"):
                    try:
                        os.remove(f"{dfn}.gz")
                    except OSError:
                        pass

            # Compress the most recent backup
            sfn = f"{self.baseFilename}.1"
            if os.path.exists(sfn):
                try:
                    with open(sfn, "rb") as f_in:
                        with gzip.open(f"{sfn}.gz", "wb") as f_out:
                            shutil.copyfileobj(f_in, f_out)
                    os.remove(sfn)  # Remove uncompressed file after successful compression
                    logger = logging.getLogger(__name__)
                    original_size = os.path.getsize(f"{sfn}.gz")
                    logger.info(
                        f"✅ Rotated log archived: {sfn}.gz "
                        f"({original_size / 1024 / 1024:.1f}MB compressed)"
                    )
                except (OSError, IOError) as e:
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Failed to compress log file {sfn}: {e}")


def get_compressed_handler(
    filename: str,
    max_bytes: int = 100 * 1024 * 1024,  # 100 MB default
    backup_count: int = 10,
) -> CompressedRotatingFileHandler:
    """Create a compressed rotating file handler.

    Args:
        filename: Path to log file
        max_bytes: Maximum bytes before rotation (default 100 MB)
        backup_count: Number of backup files to keep (default 10)

    Returns:
        CompressedRotatingFileHandler instance
    """
    # Ensure parent directory exists
    Path(filename).parent.mkdir(parents=True, exist_ok=True)

    handler = CompressedRotatingFileHandler(
        filename,
        maxBytes=max_bytes,
        backupCount=backup_count,
    )
    return handler
