"""HA Failover endpoints for state synchronization.

Critical functions:
- /api/failover/prepare: PRIMARY collects and sends state to BACKUP
- /api/failover/receive-state: BACKUP receives full state snapshot
- /api/failover/sync-position: NEW - Real-time position sync after each trade
- /api/failover/receive-position: NEW - BACKUP receives position snapshot
"""

import json
import os
import asyncio
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from datetime import datetime
import aiohttp
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


def get_paper_trading():
    """Get global paper trading engine instance."""
    from backend.api.main import get_paper_trading as get_engine
    return get_engine()


@router.post("/api/failover/sync-position")
async def sync_position_to_backup():
    """CRITICAL: Sync complete position state + trade history to BACKUP after each trade.

    Called from autonomous trader after every BUY/SELL execution.
    Ensures BACKUP always has PRIMARY's exact account state AND complete trade history.

    This is more reliable than individual trade replication because:
    - Atomic: sends complete snapshot with all trades
    - Idempotent: if called twice with same state, result is the same
    - Audit-friendly: BACKUP has full transaction history
    - Failover-safe: BACKUP can take over with 100% accurate state AND trade log
    """
    try:
        engine = get_paper_trading()
        if not engine:
            raise HTTPException(status_code=500, detail="Paper trading engine not initialized")

        # Collect current account state
        account_state = engine.get_account_state()
        positions_data = []

        # Serialize positions with all required fields
        for symbol, position in engine.positions.items():
            positions_data.append({
                "symbol": position.symbol,
                "side": position.side,
                "quantity": position.quantity,
                "entry_price": position.entry_price,
                "entry_time": position.entry_time.isoformat() if hasattr(position.entry_time, 'isoformat') else str(position.entry_time),
                "current_price": position.current_price,
                "unrealized_pnl": position.unrealized_pnl,
                "db_id": position.db_id
            })

        # Get full trade history from engine
        trades_data = engine.get_trades(limit=10000)

        sync_payload = {
            "timestamp": datetime.utcnow().isoformat(),
            "state": {
                "cash": account_state['cash'],
                "total_equity": account_state['total_equity'],
                "positions_value": account_state['positions_value'],
                "total_pnl": account_state['total_pnl'],
                "daily_pnl": account_state['daily_pnl'],
            },
            "positions": positions_data,
            "trades": trades_data,
        }

        # Send to BACKUP
        backup_url = os.getenv("BACKUP_MACHINE_URL", "http://192.168.3.25:8002")

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{backup_url}/api/failover/receive-position",
                json=sync_payload,
                timeout=aiohttp.ClientTimeout(total=30)  # Increased from 5s for network reliability
            ) as resp:
                if resp.status == 200:
                    logger.info(
                        f"✅ FULL SYNC to backup: {len(positions_data)} positions, "
                        f"{len(trades_data)} trades, €{account_state['cash']:.2f} cash, "
                        f"€{account_state['total_pnl']:.2f} P&L"
                    )
                    return JSONResponse({
                        "status": "synced",
                        "positions_synced": len(positions_data),
                        "trades_synced": len(trades_data),
                        "cash": account_state['cash'],
                        "total_pnl": account_state['total_pnl']
                    })
                else:
                    error_text = await resp.text()
                    logger.error(f"🔴 Position sync failed (HTTP {resp.status}): {error_text}")
                    raise HTTPException(status_code=500, detail=f"Backup position sync failed: {error_text}")

    except asyncio.TimeoutError:
        logger.error("🔴 Position sync timeout - BACKUP may be unreachable")
        raise HTTPException(status_code=500, detail="Position sync timeout")
    except Exception as e:
        logger.error(f"🔴 Position sync error: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Position sync failed: {str(e)}")


@router.post("/api/failover/receive-position")
async def receive_position_from_primary(request: Request):
    """CRITICAL: BACKUP receives complete state snapshot + trade history from PRIMARY.

    Restores PRIMARY's exact state on BACKUP:
    - Clears BACKUP's stale positions
    - Restores exact cash balance
    - Restores exact position list with current prices
    - Restores P&L counters
    - Restores COMPLETE trade history (audit trail)

    After this, BACKUP is identical to PRIMARY and ready for failover.
    """
    try:
        from backend.exchange.paper_trading import Position, Trade
        from backend.core.database import get_database

        data = await request.json()
        engine = get_paper_trading()
        if not engine:
            raise HTTPException(status_code=500, detail="Paper trading engine not initialized")

        db = get_database()

        # Clear BACKUP's stale positions, state, and trades
        engine.positions.clear()
        engine.trade_history.clear()

        # Restore PRIMARY's exact state
        engine.cash = data['state']['cash']
        engine.total_pnl = data['state']['total_pnl']
        engine.daily_pnl = data['state']['daily_pnl']

        # CRITICAL: Save state to database so it survives BACKUP restart
        db.save_account_state(
            cash=data['state']['cash'],
            total_pnl=data['state']['total_pnl'],
            daily_pnl=data['state']['daily_pnl']
        )

        # Restore positions from PRIMARY
        for pos_data in data.get('positions', []):
            entry_time_str = pos_data.get('entry_time')
            if entry_time_str:
                try:
                    entry_time = datetime.fromisoformat(entry_time_str.replace('Z', '+00:00'))
                except:
                    entry_time = datetime.utcnow()
            else:
                entry_time = datetime.utcnow()

            position = Position(
                symbol=pos_data['symbol'],
                side=pos_data['side'],
                quantity=pos_data['quantity'],
                entry_price=pos_data['entry_price'],
                entry_time=entry_time,
                current_price=pos_data.get('current_price', pos_data['entry_price']),
                unrealized_pnl=pos_data.get('unrealized_pnl', 0.0),
                db_id=pos_data.get('db_id')
            )
            engine.positions[pos_data['symbol']] = position

        # Restore trade history from PRIMARY (both in-memory and to database for persistence)
        from backend.core.database import get_database
        db = get_database()
        trades_synced = 0

        for trade_data in data.get('trades', []):
            timestamp_str = trade_data.get('timestamp')
            if timestamp_str:
                try:
                    timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                except:
                    timestamp = datetime.utcnow()
            else:
                timestamp = datetime.utcnow()

            trade = Trade(
                timestamp=timestamp,
                symbol=trade_data['symbol'],
                side=trade_data['side'],
                quantity=trade_data['quantity'],
                price=trade_data['price'],
                fee=trade_data['fee'],
                realized_pnl=trade_data.get('realized_pnl', 0.0),
                order_id=trade_data['order_id'],
                mode=trade_data.get('mode', 'PAPER'),
                status=trade_data.get('status', 'FILLED')
            )

            # Add to in-memory history
            engine.trade_history.append(trade)

            # CRITICAL: Persist to database so trades survive BACKUP restart
            try:
                db.insert_trade(
                    symbol=trade.symbol,
                    side=trade.side,
                    quantity=trade.quantity,
                    price=trade.price,
                    trade_time=trade.timestamp,
                    order_id=trade.order_id,
                    slippage_pct=0.0  # Already included in price on PRIMARY
                )
                logger.info(f"✅ Trade persisted to BACKUP database: {trade.symbol} {trade.side} {trade.quantity}")
            except Exception as e:
                logger.error(f"❌ Failed to persist trade to BACKUP database: {e}")
                # Don't fail the entire sync, but log the error

            trades_synced += 1

        logger.critical(
            f"✅ BACKUP FULL SYNC COMPLETE: {len(data['positions'])} positions, "
            f"{trades_synced} trades, €{engine.cash:.2f} cash, €{engine.total_pnl:.2f} P&L"
        )

        return JSONResponse({
            "status": "received",
            "positions_restored": len(data.get('positions', [])),
            "trades_restored": trades_synced,
            "cash_restored": data['state']['cash'],
            "pnl_restored": data['state']['total_pnl'],
            "backup_state": "SYNCHRONIZED_WITH_PRIMARY_COMPLETE"
        })

    except Exception as e:
        logger.error(f"🔴 Position reception failed: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Position reception failed: {str(e)}")
