"""
Phase 330+: Execution Log Loader

Load executions from paper trading audit trail and convert to daemon format.
"""

import logging
from typing import List, Dict, Optional
from pathlib import Path
import json
from datetime import datetime

logger = logging.getLogger(__name__)

AUDIT_LOG_PATH = Path("logs/trade_audit.jsonl")


def load_executions_from_audit_log(
    since_timestamp: Optional[str] = None,
) -> List[Dict]:
    """
    Load execution records from paper trading audit trail.

    Parameters:
    -----------
    since_timestamp : str
        ISO timestamp; only load executions after this time (optional)

    Returns:
    --------
    List of execution records in daemon format:
    [{
        'symbol': 'AAPL',
        'side': 'BUY',
        'timestamp': '2026-06-24T08:30:00+00:00',
        'price': 150.0,
        'allocation_pct': 5.0,
        'quantity': 10.0,
        'recommendation_id': 'rec-123' (if available)
    }, ...]
    """
    if not AUDIT_LOG_PATH.exists():
        logger.warning(f"Audit log not found: {AUDIT_LOG_PATH}")
        return []

    executions = []
    cutoff_dt = None

    if since_timestamp:
        try:
            cutoff_dt = datetime.fromisoformat(since_timestamp)
        except (ValueError, TypeError):
            logger.warning(f"Invalid timestamp filter: {since_timestamp}")

    try:
        with open(AUDIT_LOG_PATH) as f:
            for line in f:
                if not line.strip():
                    continue

                try:
                    record = json.loads(line)

                    # Filter by timestamp if provided
                    if cutoff_dt:
                        try:
                            record_dt = datetime.fromisoformat(
                                record.get("timestamp", "")
                            )
                            if record_dt < cutoff_dt:
                                continue
                        except (ValueError, TypeError):
                            pass

                    # Convert paper trading format to daemon format
                    execution = _convert_audit_to_daemon_format(record)
                    if execution:
                        executions.append(execution)

                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse audit line: {e}")
                    continue

    except Exception as e:
        logger.error(f"Failed to load audit log: {e}")
        return []

    logger.info(f"Loaded {len(executions)} executions from audit log")
    return executions


def _convert_audit_to_daemon_format(audit_record: Dict) -> Optional[Dict]:
    """
    Convert paper trading audit record to daemon execution format.

    Handles multiple source formats:
    - Format A (preferred): {symbol, side, timestamp, price, allocation_pct}
    - Format B (legacy): {symbol, side, quantity, filled_price}

    Parameters:
    -----------
    audit_record : dict
        Record from trade_audit.jsonl

    Returns:
    --------
    Execution record or None if conversion fails
    """
    try:
        # Extract symbol and validate
        symbol = (audit_record.get("symbol") or "").strip().upper()
        if not symbol:
            logger.debug(f"Missing symbol in record: {audit_record}")
            return None

        # Extract and validate side
        side = (audit_record.get("side") or "").strip().upper()
        if side not in ["BUY", "SELL"]:
            logger.debug(f"Invalid side '{side}' in record: {audit_record}")
            return None

        # Extract timestamp (required)
        timestamp = (audit_record.get("timestamp") or "").strip()
        if not timestamp:
            logger.debug(f"Missing timestamp in record: {audit_record}")
            return None

        # Try preferred format first (price, allocation_pct)
        price = _safe_float(audit_record.get("price"))
        allocation_pct = _safe_float(audit_record.get("allocation_pct"))

        # Fallback to legacy format (filled_price)
        if price is None:
            price = _safe_float(audit_record.get("filled_price"))

        if price is None or price <= 0:
            logger.debug(f"Invalid price in record: {audit_record}")
            return None

        # Extract quantity
        quantity = _safe_float(audit_record.get("quantity", 0))

        # If allocation_pct not provided, estimate from quantity
        if allocation_pct is None or allocation_pct <= 0:
            allocation_pct = 1.0  # Default 1% if not available

        execution = {
            "symbol": symbol,
            "side": side,
            "timestamp": timestamp,
            "price": price,
            "allocation_pct": allocation_pct,
            "quantity": quantity if quantity is not None else 0.0,
        }

        # Optional: recommendation_id if tracked
        if "recommendation_id" in audit_record and audit_record["recommendation_id"]:
            execution["recommendation_id"] = audit_record["recommendation_id"]

        return execution

    except Exception as e:
        logger.debug(f"Failed to convert audit record: {e}")
        return None


def _safe_float(value) -> Optional[float]:
    """Safely convert value to float, return None if invalid."""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def get_last_sync_timestamp(
    sync_state_file: Path = Path("logs/.daemon_last_sync"),
) -> Optional[str]:
    """
    Get timestamp of last successful daemon sync.

    Parameters:
    -----------
    sync_state_file : Path
        File storing last sync timestamp

    Returns:
    --------
    ISO timestamp string or None if no prior sync
    """
    if sync_state_file.exists():
        try:
            return sync_state_file.read_text().strip()
        except Exception as e:
            logger.warning(f"Failed to read sync state: {e}")

    return None


def save_sync_timestamp(
    timestamp: str,
    sync_state_file: Path = Path("logs/.daemon_last_sync"),
) -> bool:
    """
    Save timestamp of last successful daemon sync.

    Parameters:
    -----------
    timestamp : str
        ISO timestamp
    sync_state_file : Path
        File to write

    Returns:
    --------
    True if successful, False otherwise
    """
    try:
        sync_state_file.parent.mkdir(parents=True, exist_ok=True)
        sync_state_file.write_text(timestamp)
        logger.debug(f"Saved sync timestamp: {timestamp}")
        return True
    except Exception as e:
        logger.error(f"Failed to save sync timestamp: {e}")
        return False
