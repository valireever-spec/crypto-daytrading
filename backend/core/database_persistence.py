"""Database Persistence: ACID transactions + crash recovery"""

import logging
import sqlite3
from typing import Dict, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)


class DatabasePersistence:
    """ACID-compliant trade persistence with crash recovery."""

    def __init__(self, db_path: str = "/tmp/crypto_trades.db"):
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self.init_db()

    def init_db(self) -> None:
        """Initialize database with proper schema."""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.isolation_level = None  # Autocommit mode
        cursor = self.conn.cursor()

        # Enable WAL mode for crash safety
        cursor.execute("PRAGMA journal_mode=WAL")

        # Create trades table with ACID guarantees
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                trade_id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                quantity REAL NOT NULL,
                price REAL NOT NULL,
                filled_qty REAL,
                filled_price REAL,
                status TEXT DEFAULT 'PENDING',
                created_at TEXT NOT NULL,
                executed_at TEXT,
                confirmed_at TEXT
            )
        """)

        # Create trades_tx for transaction logging
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades_tx (
                tx_id TEXT PRIMARY KEY,
                trade_id TEXT NOT NULL,
                operation TEXT NOT NULL,
                status TEXT DEFAULT 'PENDING',
                timestamp TEXT NOT NULL,
                FOREIGN KEY(trade_id) REFERENCES trades(trade_id)
            )
        """)

        self.conn.commit()
        logger.info("✅ Database initialized with WAL mode")

    async def write_trade_atomic(
        self,
        trade_id: str,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
    ) -> bool:
        """Write trade atomically (all-or-nothing).

        Args:
            trade_id: Unique trade identifier
            symbol: Trading pair
            side: BUY or SELL
            quantity: Order size
            price: Price

        Returns:
            True if written, False if failed
        """
        try:
            cursor = self.conn.cursor()

            # Begin explicit transaction
            cursor.execute("BEGIN EXCLUSIVE")

            # Write trade
            cursor.execute("""
                INSERT INTO trades (trade_id, symbol, side, quantity, price, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (trade_id, symbol, side, quantity, price, datetime.utcnow().isoformat()))

            # Commit atomically
            self.conn.commit()

            logger.info(f"✅ Trade persisted atomically: {trade_id}")
            return True

        except Exception as e:
            self.conn.rollback()
            logger.error(f"❌ Trade persistence failed: {e}")
            return False

    async def mark_trade_executed(
        self,
        trade_id: str,
        filled_qty: float,
        filled_price: float,
    ) -> bool:
        """Mark trade as executed (atomic update).

        Args:
            trade_id: Trade identifier
            filled_qty: Quantity filled
            filled_price: Price filled

        Returns:
            True if successful
        """
        try:
            cursor = self.conn.cursor()

            cursor.execute("BEGIN EXCLUSIVE")

            cursor.execute("""
                UPDATE trades
                SET status = 'FILLED', filled_qty = ?, filled_price = ?, executed_at = ?
                WHERE trade_id = ?
            """, (filled_qty, filled_price, datetime.utcnow().isoformat(), trade_id))

            self.conn.commit()

            logger.info(f"✅ Trade marked executed: {trade_id}")
            return True

        except Exception as e:
            self.conn.rollback()
            logger.error(f"❌ Trade update failed: {e}")
            return False

    async def recover_pending_trades(self) -> List[Dict]:
        """Recover pending trades on startup (crash recovery).

        Returns:
            List of trades that need reconciliation
        """
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT trade_id, symbol, side, quantity, price, created_at
            FROM trades
            WHERE status IN ('PENDING', 'EXECUTING')
            ORDER BY created_at
        """)

        pending = []
        for row in cursor.fetchall():
            pending.append({
                "trade_id": row[0],
                "symbol": row[1],
                "side": row[2],
                "quantity": row[3],
                "price": row[4],
                "created_at": row[5],
            })

        if pending:
            logger.warning(f"⚠️  Found {len(pending)} pending trades, reconciling...")

        return pending

    def get_trade_status(self, trade_id: str) -> Optional[Dict]:
        """Get trade status (check if executed)."""
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT trade_id, symbol, side, quantity, price, status, filled_qty, filled_price
            FROM trades
            WHERE trade_id = ?
        """, (trade_id,))

        row = cursor.fetchone()
        if row:
            return {
                "trade_id": row[0],
                "symbol": row[1],
                "side": row[2],
                "quantity": row[3],
                "price": row[4],
                "status": row[5],
                "filled_qty": row[6],
                "filled_price": row[7],
            }

        return None

    def get_status(self) -> Dict:
        """Get database status."""
        cursor = self.conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM trades")
        total = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM trades WHERE status = 'FILLED'")
        filled = cursor.fetchone()[0]

        return {
            "total_trades": total,
            "filled": filled,
            "pending": total - filled,
            "db_path": self.db_path,
        }


# Global instance
_database_persistence: Optional[DatabasePersistence] = None


def get_database_persistence(db_path: str = "/tmp/crypto_trades.db") -> DatabasePersistence:
    global _database_persistence
    if _database_persistence is None:
        _database_persistence = DatabasePersistence(db_path)
    return _database_persistence
