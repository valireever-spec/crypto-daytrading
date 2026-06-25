"""SQLite database for position persistence (Pillar #5 Hardening - CRITICAL)."""

import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import asdict

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent.parent / "data" / "trading.db"


class TradingDatabase:
    """SQLite database for position and trade persistence."""

    def __init__(self, db_path: str = str(DB_PATH)):
        """Initialize database connection."""
        self.db_path = db_path
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _init_schema(self) -> None:
        """Create tables if they don't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Positions table: track open trades
        cursor.execute("""
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
        """)

        # Trades table: audit trail of all fills
        cursor.execute("""
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
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Configuration snapshots for rollback
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS config_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                config_json TEXT NOT NULL,
                snapshot_time TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        conn.close()
        logger.info(f"Database initialized: {self.db_path}")

    def insert_position(
        self,
        symbol: str,
        quantity: float,
        entry_price: float,
        entry_time: datetime,
    ) -> int:
        """Insert new open position into database.

        Args:
            symbol: Trading symbol (e.g., 'BTCUSDT')
            quantity: Position size
            entry_price: Entry price
            entry_time: Entry timestamp

        Returns:
            Position ID (rowid)
        """
        conn = sqlite3.connect(self.db_path)
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
        conn.close()

        logger.info(f"Position saved to DB: {symbol} {quantity} @ {entry_price} (id={position_id})")
        return position_id

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
                logger.info(f"  - {pos['symbol']}: {pos['quantity']} @ {pos['entry_price']}")

        return positions

    def insert_trade(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        trade_time: datetime,
        order_id: Optional[str] = None,
        slippage_pct: Optional[float] = None,
    ) -> int:
        """Log executed trade to audit trail.

        Args:
            symbol: Trading symbol
            side: 'BUY' or 'SELL'
            quantity: Trade size
            price: Fill price
            trade_time: Fill timestamp
            order_id: Optional order ID for deduplication
            slippage_pct: Slippage percentage

        Returns:
            Trade ID (rowid)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO trades (symbol, side, quantity, price, trade_time, order_id, slippage_pct, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'FILLED')
            """,
            (symbol, side, quantity, price, trade_time.isoformat(), order_id, slippage_pct),
        )

        conn.commit()
        trade_id = cursor.lastrowid
        conn.close()

        logger.info(f"Trade logged to DB: {side} {symbol} {quantity} @ {price}")
        return trade_id

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
            SELECT id, symbol, side, quantity, price, trade_time, slippage_pct
            FROM trades
            WHERE DATE(trade_time) = DATE('now')
            ORDER BY trade_time ASC
            """
        )

        trades = [dict(row) for row in cursor.fetchall()]
        conn.close()

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
