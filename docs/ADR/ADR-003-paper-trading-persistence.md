# ADR-003: Paper Trading State Persistence

**Date:** 2026-06-25  
**Status:** ACCEPTED  
**Phase:** 1 (Paper Trading)

## Context

Paper trading engine must maintain state across:
- API restarts
- Power failures
- Position tracking accuracy
- Audit trail immutability

Three approaches:
1. **In-memory only** — Fast, simple, loses data on restart
2. **File-based** — JSON/CSV on disk, slower, loose format
3. **Database (SQLite)** — ACID transactions, reliable, overhead

## Decision

**Use SQLite for positions + append-only JSON log for trades**

Hybrid approach:
- **Positions:** SQLite (atomic, fast lookup, easy reconciliation)
- **Trades:** Append-only JSON log (immutable, human-readable, audit trail)

## Rationale

### Why SQLite for Positions
- ✅ ACID guarantees (either fully saved or not)
- ✅ Atomic updates (no partial writes on crash)
- ✅ Fast queries (reconciliation checks)
- ✅ Built-in, no extra dependencies
- ✅ Embeds in single file (`data/trading.db`)

### Why Append-Only Log for Trades
- ✅ Cannot be modified (immutability)
- ✅ Human-readable (JSON)
- ✅ Grep-able (analysis tools)
- ✅ No risk of corruption from UPDATE/DELETE
- ✅ One trade per line (streaming-friendly)

### Why Not Pure File System
- ❌ Race conditions (concurrent writes)
- ❌ No atomic transactions
- ❌ Slow for queries
- ❌ Hard to validate consistency

### Why Not PostgreSQL
- ❌ Extra dependency (not available on edge devices)
- ❌ Overkill for Phase 1 (single machine, 100 trades/day)
- ❌ Network dependency (unreliable in crypto trading)
- ❌ Higher operational complexity

## Architecture

```
Autonomous Trader
    ↓
Paper Trading Engine
    ├─ SQLite DB: positions table (open/closed)
    └─ JSON log: trades.jsonl (append-only)
    ↓
On Restart: Restore positions from DB
```

### Positions Table (SQLite)
```sql
CREATE TABLE positions (
  id INTEGER PRIMARY KEY,
  symbol TEXT NOT NULL,
  quantity REAL NOT NULL,
  entry_price REAL NOT NULL,
  entry_time DATETIME NOT NULL,
  current_price REAL,
  status TEXT DEFAULT 'open',
  closed_at DATETIME
);

-- Indices
CREATE INDEX idx_symbol ON positions(symbol);
CREATE INDEX idx_status ON positions(status);
```

### Trades Log (Append-Only JSON)
```json
{"timestamp": "2026-06-25T10:30:00Z", "symbol": "BTCUSDT", "side": "BUY", "quantity": 0.5, "price": 60000.0, "fee": 30.0, "realized_pnl": 0.0, "order_id": "uuid-123", "mode": "PAPER", "status": "FILLED"}
{"timestamp": "2026-06-25T11:15:00Z", "symbol": "BTCUSDT", "side": "SELL", "quantity": 0.5, "price": 61000.0, "fee": 30.5, "realized_pnl": 970.0, "order_id": "uuid-124", "mode": "PAPER", "status": "FILLED"}
...
```

## Consequences

### Positive
- ✅ Positions safe across restarts (ACID guarantees)
- ✅ Trades immutable (append-only protects against corruption)
- ✅ No external dependencies (SQLite built-in)
- ✅ Reconciliation fast (indexed queries)
- ✅ Audit trail for compliance (immutable log)
- ✅ Single file deployment (`data/trading.db`)

### Negative
- ❌ Database corruption possible (mitigated by append-only trades)
- ❌ SQLite not ideal for high concurrency (acceptable for Phase 1)
- ❌ Must manage disk space (logs can grow large)

## Safeguards

### Position Corruption Recovery
If positions table corrupted:
1. Restore from append-only trade log
2. Replay all trades to rebuild positions
3. Verify checksums if available

### Trade Log Corruption Prevention
```
- Append-only (no UPDATE/DELETE)
- Trigger prevents modifications
- Human-readable for manual inspection
- Separate from positions (isolation)
```

### Backup Strategy
Daily backup:
```bash
cp data/trading.db data/trading.db.backup.$(date +%Y%m%d)
tar gz logs/trades.jsonl → cloud storage
```

## Migration Path (Future)

**Phase 2:** Add replication
- Sync SQLite to backup machine
- Test failover recovery

**Phase 3:** Add data warehouse
- Archive old trades to data lake
- Analysis and reporting

## Implementation Status

✅ **Implemented:**
- SQLite positions table with integrity checks
- Append-only JSON log for trades
- Position restoration on startup
- Duplicate detection

⏳ **Future:**
- Automated backup (Phase 2)
- Replication to backup machine (Phase 2)
- Data warehouse sync (Phase 3)

## References
- SQLite reliability: https://www.sqlite.org/transactional.html
- Append-only log pattern: https://en.wikipedia.org/wiki/Append-only_file
- ACID properties: https://en.wikipedia.org/wiki/ACID
