"""SQLite database for position persistence (Pillar #5 + #10 Hardening - CRITICAL)."""

import sqlite3
import logging
import math
import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Allow database path to be overridden via environment variable (for BACKUP failover on different machines)
DB_PATH = Path(
    os.getenv(
        "TRADING_DB_PATH",
        str(Path(__file__).parent.parent.parent / "data" / "trading.db"),
    )
)
VALID_SYMBOLS = {"BTCUSDT", "ETHUSDT", "BNBUSDT", "ADAUSDT", "DOGEUSDT"}
VALID_SIDES = {"BUY", "SELL"}
VALID_STATUSES = {"OPEN", "CLOSED", "FILLED", "CANCELLED"}


class TradingDatabase:
    """SQLite database for position and trade persistence (Anti-poisoning hardened)."""

    def __init__(self, db_path: str = str(DB_PATH)):
        """Initialize database connection."""
        self.db_path = db_path
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()
        self._verify_schema_integrity()  # Detect tampering on startup

    def _init_schema(self) -> None:
        """Create tables if they don't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Positions table: track open trades
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS open_positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                quantity REAL NOT NULL,
                entry_price REAL NOT NULL,
                entry_time TEXT NOT NULL,
                status TEXT DEFAULT 'OPEN',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # Trades table: audit trail of all fills (PILLAR #10: Hash-verified, append-only)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                quantity REAL NOT NULL,
                price REAL NOT NULL,
                trade_time TEXT NOT NULL,
                order_id TEXT UNIQUE,
                status TEXT DEFAULT 'FILLED',
                slippage_pct REAL,
                fee REAL DEFAULT 0.0,
                realized_pnl REAL DEFAULT 0.0,
                hash TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # Migration: Add realized_pnl column if it doesn't exist (for existing databases)
        try:
            cursor.execute(
                "ALTER TABLE trades ADD COLUMN realized_pnl REAL DEFAULT 0.0"
            )
        except sqlite3.OperationalError:
            pass  # Column already exists

        # HARDENING (Pillar #10): Prevent DELETE on trades table (append-only audit trail)
        # NOTE: UPDATE is NOT prevented - we need to allow updates to realized_pnl
        # for correcting trade P&L values. Hash verification prevents tampering.
        cursor.execute(
            """
            CREATE TRIGGER IF NOT EXISTS prevent_trade_delete
            BEFORE DELETE ON trades
            BEGIN
              SELECT RAISE(ABORT, 'Trades table is append-only: DELETE not allowed');
            END
        """
        )

        # Drop old prevent_trade_update trigger if it exists (we need to allow UPDATE)
        try:
            cursor.execute("DROP TRIGGER IF EXISTS prevent_trade_update")
        except Exception as e:
            logger.debug(f"Could not drop trigger (may not exist): {e}")

        # Configuration snapshots for rollback
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS config_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                config_json TEXT NOT NULL,
                snapshot_time TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # Account state: persists cash and P&L across restarts (CRITICAL for BACKUP failover)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS account_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                cash REAL DEFAULT 1000.0,
                total_pnl REAL DEFAULT 0.0,
                daily_pnl REAL DEFAULT 0.0,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """
        )
        # Ensure single row exists
        cursor.execute(
            "INSERT OR IGNORE INTO account_state (id, cash, total_pnl, daily_pnl) VALUES (1, 1000.0, 0.0, 0.0)"
        )

        conn.commit()
        conn.close()
        logger.info(f"Database initialized: {self.db_path}")

    def _verify_schema_integrity(self) -> None:
        """Verify database schema hasn't been tampered with (Anti-poisoning)."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Verify trades table structure
            cursor.execute("PRAGMA table_info(trades)")
            columns = {row[1]: row[2] for row in cursor.fetchall()}

            required_cols = {
                "id": "INTEGER",
                "symbol": "TEXT",
                "side": "TEXT",
                "quantity": "REAL",
                "price": "REAL",
                "trade_time": "TEXT",
            }

            for col_name, col_type in required_cols.items():
                if col_name not in columns:
                    logger.critical(f"🚨 SCHEMA POISONED: trades.{col_name} missing!")
                    raise RuntimeError(f"Database schema corrupted: missing {col_name}")

            # Verify open_positions table structure
            cursor.execute("PRAGMA table_info(open_positions)")
            pos_columns = {row[1]: row[2] for row in cursor.fetchall()}

            pos_required = {
                "id": "INTEGER",
                "symbol": "TEXT",
                "quantity": "REAL",
                "entry_price": "REAL",
                "entry_time": "TEXT",
            }

            for col_name, col_type in pos_required.items():
                if col_name not in pos_columns:
                    logger.critical(
                        f"🚨 SCHEMA POISONED: open_positions.{col_name} missing!"
                    )
                    raise RuntimeError(f"Database schema corrupted: missing {col_name}")

            conn.close()
            logger.info("✅ Database schema integrity verified")

        except Exception as e:
            logger.critical(f"🚨 DATABASE SCHEMA VERIFICATION FAILED: {e}")
            raise

    @staticmethod
    def _validate_input(symbol: str, quantity: float, price: float, side: str) -> None:
        """Validate trade input before DB write (Anti-poisoning gatekeeper).

        Raises:
            ValueError: If input is invalid
        """
        # Validate symbol
        if not isinstance(symbol, str) or symbol not in VALID_SYMBOLS:
            raise ValueError(f"Invalid symbol: {symbol} (must be in {VALID_SYMBOLS})")

        # Validate quantity
        if not isinstance(quantity, (int, float)):
            raise ValueError(f"Quantity must be numeric, got {type(quantity)}")
        if quantity <= 0:
            raise ValueError(f"Quantity must be positive, got {quantity}")
        if math.isnan(quantity) or math.isinf(quantity):
            raise ValueError(f"Quantity is NaN/Inf: {quantity}")
        if quantity > 1_000_000:  # Sanity check
            raise ValueError(f"Quantity too large: {quantity}")

        # Validate price
        if not isinstance(price, (int, float)):
            raise ValueError(f"Price must be numeric, got {type(price)}")
        if price <= 0:
            raise ValueError(f"Price must be positive, got {price}")
        if math.isnan(price) or math.isinf(price):
            raise ValueError(f"Price is NaN/Inf: {price}")
        if price > 1_000_000:  # Sanity check
            raise ValueError(f"Price too large: {price}")

        # Validate side
        if not isinstance(side, str) or side not in VALID_SIDES:
            raise ValueError(f"Invalid side: {side} (must be 'BUY' or 'SELL')")

    @staticmethod
    def _calculate_trade_hash(trade_data: Dict) -> str:
        """Calculate SHA256 hash of trade data for integrity verification (Pillar #10).

        Args:
            trade_data: Trade record dict (symbol, side, quantity, price, trade_time, order_id)

        Returns:
            SHA256 hash hex string
        """
        # Create deterministic representation (sorted keys for consistency)
        data_to_hash = {
            "symbol": trade_data.get("symbol"),
            "side": trade_data.get("side"),
            "quantity": trade_data.get("quantity"),
            "price": trade_data.get("price"),
            "trade_time": trade_data.get("trade_time"),
            "order_id": trade_data.get("order_id"),
        }
        json_str = json.dumps(data_to_hash, sort_keys=True)
        return hashlib.sha256(json_str.encode()).hexdigest()

    def verify_trade_integrity(self, trade_id: int) -> bool:
        """Verify a trade hasn't been tampered with by recalculating hash (Pillar #10).

        Args:
            trade_id: Trade ID to verify

        Returns:
            True if hash matches (trade is intact), False if corrupted
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM trades WHERE id = ?", (trade_id,))
            row = cursor.fetchone()
            conn.close()

            if not row:
                logger.warning(f"Trade {trade_id} not found")
                return False

            # Pillar #10: Only verify if hash column exists (backward compatible)
            try:
                stored_hash = row["hash"]
                # Recalculate hash from current data
                current_hash = self._calculate_trade_hash(dict(row))

                if stored_hash != current_hash:
                    logger.error(
                        f"🚨 HASH MISMATCH: Trade {trade_id} has been tampered with!"
                    )
                    logger.error(f"   Stored:   {stored_hash}")
                    logger.error(f"   Current:  {current_hash}")
                    return False
            except (KeyError, TypeError):
                # No hash field in old trades - skip verification for backward compatibility
                logger.debug(
                    f"Trade {trade_id}: No hash field (legacy data), skipping verification"
                )

            return True

        except Exception as e:
            logger.error(f"Error verifying trade integrity: {e}")
            return False

    def verify_all_trades_integrity(self) -> bool:
        """Verify integrity of recent trades in database (Pillar #10).

        Checks only last 20 trades to avoid blocking on old test data.
        Returns:
            True if all recent trades are intact, False if any corrupted
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM trades")
            count = cursor.fetchone()[0]

            if count == 0:
                logger.info("No trades to verify")
                conn.close()
                return True

            # Verify only recent trades (last 20) to detect current corruption, not old test data
            cursor.execute("SELECT id FROM trades ORDER BY id DESC LIMIT 20")
            trade_ids = [row[0] for row in cursor.fetchall()]
            conn.close()

            corrupted = []
            for trade_id in trade_ids:
                if not self.verify_trade_integrity(trade_id):
                    corrupted.append(trade_id)

            if corrupted:
                logger.error(
                    f"🚨 DATABASE INTEGRITY FAILED: {len(corrupted)}/{len(trade_ids)} recent trades corrupted!"
                )
                logger.error(f"   Corrupted trades: {corrupted}")
                return False

            logger.info(f"✅ Database integrity verified: {count} trades, all intact")
            return True

        except Exception as e:
            logger.error(f"Error verifying database integrity: {e}")
            return False

    def insert_position(
        self,
        symbol: str,
        quantity: float,
        entry_price: float,
        entry_time: datetime,
    ) -> int:
        """Insert new open position into database (anti-poisoning validated).

        Args:
            symbol: Trading symbol (e.g., 'BTCUSDT')
            quantity: Position size
            entry_price: Entry price
            entry_time: Entry timestamp

        Returns:
            Position ID (rowid)

        Raises:
            ValueError: If input validation fails
        """
        # HARDENING: Validate input before DB write (anti-poisoning)
        self._validate_input(symbol, quantity, entry_price, "BUY")

        conn = sqlite3.connect(self.db_path)
        conn.isolation_level = "DEFERRED"  # Atomic transaction
        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO open_positions (symbol, quantity, entry_price, entry_time, status)
                VALUES (?, ?, ?, ?, 'OPEN')
                """,
                (symbol, quantity, entry_price, entry_time.isoformat()),
            )

            conn.commit()
            position_id = cursor.lastrowid

            logger.info(
                f"Position saved to DB: {symbol} {quantity} @ {entry_price} (id={position_id})"
            )
            return position_id

        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to insert position: {e}")
            raise
        finally:
            conn.close()

    def close_position(self, position_id: int) -> None:
        """Mark position as closed.

        Args:
            position_id: Position ID to close
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE open_positions
            SET status = 'CLOSED', updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (position_id,),
        )

        conn.commit()
        conn.close()

        logger.info(f"Position closed in DB: id={position_id}")

    def get_open_positions(self) -> List[Dict]:
        """Get all open positions from database.

        Returns:
            List of position dicts: {id, symbol, quantity, entry_price, entry_time}
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id, symbol, quantity, entry_price, entry_time
            FROM open_positions
            WHERE status = 'OPEN'
            ORDER BY entry_time ASC
            """
        )

        positions = [dict(row) for row in cursor.fetchall()]
        conn.close()

        if positions:
            logger.info(f"Restored {len(positions)} open positions from DB")
            for pos in positions:
                logger.info(
                    f"  - {pos['symbol']}: {pos['quantity']} @ {pos['entry_price']}"
                )

        return positions

    def clear_all_positions(self) -> None:
        """Clear all corrupted/stale positions (Pillar #10: Database Integrity).

        Used when too many orphaned positions are detected (likely test data).
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("DELETE FROM open_positions WHERE status = 'OPEN'")
            conn.commit()
            deleted = cursor.rowcount
            logger.critical(
                f"🚨 CLEARED {deleted} STALE POSITIONS - DATABASE INTEGRITY CHECK"
            )
        except Exception as e:
            logger.error(f"Failed to clear positions: {e}")
            conn.rollback()
        finally:
            conn.close()

    def insert_trade(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        trade_time: datetime,
        order_id: Optional[str] = None,
        slippage_pct: Optional[float] = None,
        realized_pnl: float = 0.0,
        fee: float = 0.0,
    ) -> int:
        """Log executed trade to audit trail (anti-poisoning validated).

        Args:
            symbol: Trading symbol
            side: 'BUY' or 'SELL'
            quantity: Trade size
            price: Fill price
            trade_time: Fill timestamp
            order_id: Optional order ID for deduplication
            slippage_pct: Slippage percentage
            realized_pnl: Realized P&L from this trade (for SELL orders)

        Returns:
            Trade ID (rowid)

        Raises:
            ValueError: If input validation fails
            sqlite3.IntegrityError: If order_id duplicate
        """
        # HARDENING: Validate input before DB write (anti-poisoning)
        self._validate_input(symbol, quantity, price, side)

        # Validate order_id if provided
        if order_id and not isinstance(order_id, str):
            raise ValueError(f"order_id must be string, got {type(order_id)}")

        # Validate slippage_pct if provided
        if slippage_pct is not None:
            if not isinstance(slippage_pct, (int, float)):
                raise ValueError(
                    f"slippage_pct must be numeric, got {type(slippage_pct)}"
                )
            if slippage_pct < -100 or slippage_pct > 100:
                raise ValueError(f"slippage_pct out of range: {slippage_pct}")

        conn = sqlite3.connect(self.db_path)
        conn.isolation_level = "DEFERRED"  # Atomic transaction
        try:
            cursor = conn.cursor()

            # HARDENING (Pillar #10): Calculate hash for integrity verification
            trade_data = {
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "price": price,
                "trade_time": trade_time.isoformat(),
                "order_id": order_id,
            }
            trade_hash = self._calculate_trade_hash(trade_data)

            cursor.execute(
                """
                INSERT INTO trades (symbol, side, quantity, price, trade_time, order_id, slippage_pct, realized_pnl, fee, status, hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'FILLED', ?)
                """,
                (
                    symbol,
                    side,
                    quantity,
                    price,
                    trade_time.isoformat(),
                    order_id,
                    slippage_pct,
                    realized_pnl,
                    fee,
                    trade_hash,
                ),
            )

            conn.commit()
            trade_id = cursor.lastrowid

            logger.info(
                f"Trade logged to DB (hash-verified): {side} {symbol} {quantity} @ {price} (id={trade_id})"
            )
            return trade_id

        except sqlite3.IntegrityError as e:
            conn.rollback()
            if "UNIQUE constraint failed" in str(e):
                logger.warning(f"Duplicate trade rejected (deduplication): {order_id}")
                raise ValueError(f"Duplicate order_id: {order_id}")
            raise
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to insert trade: {e}")
            raise
        finally:
            conn.close()

    def get_trades_today(self) -> List[Dict]:
        """Get all trades from today (UTC).

        Returns:
            List of trade dicts
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id, symbol, side, quantity, price, trade_time, slippage_pct, realized_pnl, order_id, status, fee
            FROM trades
            WHERE DATE(trade_time) = DATE('now')
            ORDER BY trade_time ASC
            """
        )

        trades = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return trades

    def get_all_trades(self) -> List[Dict]:
        """Get ALL trades ever (not just today's).

        Used on startup to restore full trade history after API restart.
        Critical for persistence: ensures trades aren't lost on restart.

        Returns:
            List of all trade dicts (entire history)
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id, symbol, side, quantity, price, trade_time, slippage_pct, realized_pnl, order_id, status, fee
            FROM trades
            ORDER BY trade_time ASC
            """
        )

        trades = [dict(row) for row in cursor.fetchall()]
        conn.close()

        if trades:
            logger.info(f"✅ Restored {len(trades)} trades from database (full history)")

        return trades

    def save_config_snapshot(self, config_dict: Dict) -> None:
        """Save configuration snapshot for audit trail.

        Args:
            config_dict: Configuration dictionary to snapshot
        """
        import json

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        config_json = json.dumps(config_dict)
        cursor.execute(
            """
            INSERT INTO config_snapshots (config_json)
            VALUES (?)
            """,
            (config_json,),
        )

        conn.commit()
        conn.close()

        logger.info(f"Config snapshot saved: {config_json[:100]}...")

    def save_account_state(
        self, cash: float, total_pnl: float, daily_pnl: float
    ) -> None:
        """Save account state (cash and P&L) for recovery after restart.

        Critical for BACKUP failover - persists synced state across restarts.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE account_state
                SET cash = ?, total_pnl = ?, daily_pnl = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = 1
                """,
                (cash, total_pnl, daily_pnl),
            )
            conn.commit()
            conn.close()
            logger.info(f"Account state saved: €{cash} cash, €{total_pnl} P&L")
        except Exception as e:
            logger.error(f"Failed to save account state: {e}")

    def load_account_state(self) -> Dict:
        """Load account state from database.

        Called on startup to restore synced state after restart.
        Returns dict with cash, total_pnl, daily_pnl.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT cash, total_pnl, daily_pnl FROM account_state WHERE id = 1"
            )
            row = cursor.fetchone()
            conn.close()

            if row:
                return {"cash": row[0], "total_pnl": row[1], "daily_pnl": row[2]}
            return {"cash": 1000.0, "total_pnl": 0.0, "daily_pnl": 0.0}
        except Exception as e:
            logger.error(f"Failed to load account state: {e}")
            return {"cash": 1000.0, "total_pnl": 0.0, "daily_pnl": 0.0}

    def close(self) -> None:
        """Close database connection."""
        logger.info("Database closed")


# Global database instance
_db_instance: Optional[TradingDatabase] = None


def get_database() -> TradingDatabase:
    """Get or create global database instance."""
    global _db_instance
    if _db_instance is None:
        _db_instance = TradingDatabase()
    return _db_instance
