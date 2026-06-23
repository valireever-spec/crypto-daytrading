# Crypto Daytrading Platform — HA System

Automated daytrading platform for crypto (24/7, Binance API) with dual-machine redundancy.

## Quick Start

```bash
# Setup
git clone <repo> crypto-daytrading
cd crypto-daytrading
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your Binance API keys (testnet for paper trading)

# Run tests
pytest tests/unit -v                    # Fast
pytest tests/unit tests/integration -v  # Medium (~5s)

# Paper trade (manual)
python -m backend.strategies.paper_trading

# View dashboard
open http://localhost:8000/dashboard
```

## Project Structure

- **backend/** — Python services (API, strategies, exchange, execution)
- **frontend/** — HTML/CSS/JS dashboard
- **tests/** — Unit, integration, acceptance tests
- **docs/** — Architecture, strategies, runbooks
- **logs/** — Trade audit trail (append-only)

## Key Concepts

### Phases

1. **Phase 0: Design** (CURRENT) — Requirements, architecture, V-Model board
2. **Phase 1: MVP Paper Trading** — Binance API, strategies, execution, 10-day paper test
3. **Phase 2: HA & Live** — Dual-machine failover, monitoring, 2-week live with €1,000

### V-Model Traceability

- **Functional Requirements (FR-001 to FR-009)** — User-facing features
- **Non-Functional Requirements (NFR-001 to NFR-026)** — System properties
- **Use Cases (UC-1 to UC-3)** — Real scenarios
- **Tests (UT-*, IT-*)** — Validation of requirements

See `FUNCTIONAL_REQUIREMENTS.md`, `NONFUNCTIONAL_REQUIREMENTS.md`, `V_MODEL_BOARD.md`.

### 8-Pillar Framework

This project follows NASA/Tesla/Apple/Toyota standards:
1. Architecture Discipline & Traceability
2. Build Quality In / Error-Proofing
3. Verification & Validation
4. Continuous Integration & Safe Delivery
5. Root-Cause Driven Improvement
6. Security & Privacy by Design
7. Observability & Telemetry
8. Maintainability & Sustainable Pace

See `CLAUDE.md` for how each pillar is applied.

## Development Workflow

```bash
# Format and lint
black . && ruff check . --fix
mypy .

# Run full test suite
pytest tests/ -v --cov=backend --cov-report=term-missing

# Deploy to paper trading
bash scripts/deploy-paper.sh

# Deploy to live (requires manual confirmation)
bash scripts/deploy-live.sh

# View trade logs
tail -f logs/trades.jsonl | jq .

# View system health
curl http://localhost:8000/api/health | jq .
```

## Success Criteria

### Phase 0 (Design) ✅
- [x] Functional requirements (9)
- [x] Non-functional requirements (26)
- [ ] Architecture diagram
- [ ] API design
- [ ] Tracker setup

### Phase 1 (MVP)
- [ ] Paper trading acceptance: >55% win rate, positive P&L (10 days)

### Phase 2 (HA + Live)
- [ ] Live trading acceptance: >55% win rate, no loss >5% (2 weeks with €1,000)

## Strategies

### Momentum Scalper
- Entry: RSI > 70 or MACD crossover
- Exit: +1-2% profit target or -2% stop loss
- Hold: <1 hour (quick scalps)
- Use case: High volatility, intraday trades

### Mean Reversion
- Entry: Bollinger Band lower band bounce
- Exit: +1% profit or -2% stop loss
- Hold: 15min - 2h
- Use case: Bounce trading on support/resistance

### Grid Trading
- Entry: Buy at fixed intervals (grid)
- Exit: Sell at fixed intervals above cost
- Hold: Until all levels sold
- Use case: Consistent, mechanical trading

## Monitoring & Alerts

### Real-Time Dashboard
- Live P&L (today, weekly, monthly)
- Active positions (entry, current price, P&L)
- Trade history (entry, exit, duration, profit)
- Strategy performance (win rate, Sharpe, profit factor)
- System health (API status, failover status, last execution)

### Critical Alerts
- Daily loss >5% → Stop new positions
- Binance API offline → Manual intervention
- Backup failover triggered → Investigate main machine
- Strategy error rate >10% → Pause trading

## HA Architecture

### Active-Passive Redundancy
- **Main machine:** Executes all trades, publishes heartbeat
- **Backup machine:** Monitors main, takes over on failure
- **Failover trigger:** 3 missed heartbeats (30 seconds)
- **Trade deduplication:** UUID per order, inherited by backup

### No Duplicate Trades
Each trade gets unique UUID at main machine. Backup checks UUID before executing, preventing duplicates even during concurrent execution.

## Environment Variables

```bash
# Binance API
BINANCE_API_KEY=your_api_key_here
BINANCE_API_SECRET=your_secret_here
BINANCE_TESTNET=true  # For paper trading

# Trading
TRADING_MODE=paper          # paper | live
INITIAL_CAPITAL=10000       # Paper: virtual €10k; Live: real money
STRATEGY=momentum           # momentum | meanreversion | grid
MAX_DAILY_LOSS_PCT=5.0     # Stop trading if daily loss exceeds

# System
API_HOST=0.0.0.0
API_PORT=8000
LOG_LEVEL=INFO             # DEBUG | INFO | WARNING | ERROR

# HA
MACHINE_ID=main             # main | backup
BACKUP_MACHINE_URL=http://backup-machine:8000
HEARTBEAT_INTERVAL=10       # Seconds
FAILOVER_THRESHOLD=3        # Missed heartbeats before failover
```

## File Structure

```
logs/
├── trades.jsonl        # Append-only trade audit trail
├── incidents.jsonl     # Losses >€10 with analysis
├── system.log          # Application logs
└── alerts.jsonl        # Alert history

docs/
├── ARCHITECTURE.md     # High-level design
├── runbooks.md         # Alert runbooks
└── strategies/
    ├── momentum.md
    ├── mean_reversion.md
    └── grid.md
```

## Testing

```bash
# Unit tests (fast, <1s)
pytest tests/unit -v

# Integration tests (real Binance testnet, <30s)
pytest tests/integration -v

# Acceptance tests (paper trading, 10+ days)
pytest tests/acceptance -v

# Coverage analysis
coverage run -m pytest && coverage report --skip-covered
```

## Security

- API keys never in code, only `.env` (git-ignored)
- Pre-commit hooks check for secrets
- All trades logged to immutable audit trail
- Input validation on all parameters
- Rate limiting respects Binance limits (1200 req/min)

## Roadmap

**Phase 1** → Paper trading with 3-4 strategies  
**Phase 2** → HA redundancy + live trading  
**Phase 3** → Strategy optimization + capital scaling

## References

- [FUNCTIONAL_REQUIREMENTS.md](FUNCTIONAL_REQUIREMENTS.md) — User-facing features
- [NONFUNCTIONAL_REQUIREMENTS.md](NONFUNCTIONAL_REQUIREMENTS.md) — System properties
- [CLAUDE.md](CLAUDE.md) — Development guidance
- [V_MODEL_BOARD.md](V_MODEL_BOARD.md) — Progress tracking
- [Binance API Docs](https://binance-docs.github.io/apidocs/)

---

**Status:** Phase 0 Design (COMPLETE) → Phase 1 Development (NEXT)
