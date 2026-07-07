"""Wrapper endpoints for dashboard compatibility.

Maps legacy dashboard endpoints to the correct underlying API endpoints.
"""

import logging
from fastapi import APIRouter
from backend.exchange.paper_trading import get_paper_trading
from backend.exchange.binance_stream import get_stream_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/prices")
async def get_prices():
    """Get current market prices for all tracked symbols.

    Returns prices from WebSocket (preferred) or REST fallback.
    Includes health status and data freshness.
    """
    try:
        # Try to get engine for symbol list
        engine = get_paper_trading()
        symbols = engine.config.symbols if (engine and hasattr(engine, 'config')) else ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']

        # Try unified stream client
        try:
            client = get_stream_client()
            if client:
                prices = client.get_prices(symbols)
                health = client.check_health()

                return {
                    "prices": prices,
                    "stream_status": {
                        "connected": client.is_connected,
                        "source": "websocket" if prices else "fallback",
                        "health": health,
                    "healthy": len(prices) == len(symbols)
                }
            }
        except Exception as e:
            logger.debug(f"WebSocket manager error: {e}")

        # Fallback: try old stream client
        stream_client = get_stream_client()
        if stream_client and hasattr(stream_client, 'get_prices_fresh'):
            prices = stream_client.get_prices_fresh(symbols, max_age_seconds=5)
            if prices:
                return {
                    "prices": prices,
                    "stream_status": {
                        "connected": True,
                        "source": "stream_client_fallback",
                        "healthy": len(prices) == len(symbols)
                    }
                }

        # Last resort: return empty with error
        return {
            "prices": {},
            "stream_status": {
                "connected": False,
                "source": "none",
                "message": "No price source available (WebSocket down, REST unavailable)",
                "recommendation": "Check WebSocket connection or API health"
            }
        }

    except Exception as e:
        logger.error(f"Error fetching prices: {e}", exc_info=True)
        return {
            "prices": {},
            "stream_status": {
                "connected": False,
                "message": f"Error: {str(e)}",
                "recommendation": "Restart API server"
            }
        }


@router.get("/strategies/all-stats")
async def get_strategies_stats():
    """Get strategy performance statistics."""
    try:
        engine = get_paper_trading()
        if not engine:
            return {
                "strategies": {},
                "summary": {
                    "total_strategies": 0,
                    "total_trades": 0,
                    "avg_win_rate": 0
                }
            }

        # Get trades from the engine
        trades = engine.get_all_trades() if hasattr(engine, 'get_all_trades') else []

        # Group trades by strategy if available
        strategies = {}
        total_trades = len(trades)

        if total_trades == 0:
            return {
                "strategies": {
                    "momentum": {
                        "total_trades": 0,
                        "winning_trades": 0,
                        "losing_trades": 0,
                        "win_rate_pct": 0.0,
                        "total_pnl": 0.0,
                        "expectancy": 0.0,
                        "profit_factor": 1.0
                    },
                    "mean_reversion": {
                        "total_trades": 0,
                        "winning_trades": 0,
                        "losing_trades": 0,
                        "win_rate_pct": 0.0,
                        "total_pnl": 0.0,
                        "expectancy": 0.0,
                        "profit_factor": 1.0
                    },
                    "grid": {
                        "total_trades": 0,
                        "winning_trades": 0,
                        "losing_trades": 0,
                        "win_rate_pct": 0.0,
                        "total_pnl": 0.0,
                        "expectancy": 0.0,
                        "profit_factor": 1.0
                    }
                },
                "summary": {
                    "total_strategies": 3,
                    "total_trades": 0,
                    "avg_win_rate": 0
                }
            }

        # Calculate stats per strategy
        for trade in trades:
            strategy_name = trade.get('strategy', 'unknown')
            if strategy_name not in strategies:
                strategies[strategy_name] = {
                    'trades': [],
                    'winning_pnl': 0.0,
                    'losing_pnl': 0.0,
                    'winning': 0,
                    'losing': 0
                }

            strategies[strategy_name]['trades'].append(trade)
            pnl = trade.get('realized_pnl', 0)
            if pnl > 0:
                strategies[strategy_name]['winning'] += 1
                strategies[strategy_name]['winning_pnl'] += pnl
            elif pnl < 0:
                strategies[strategy_name]['losing'] += 1
                strategies[strategy_name]['losing_pnl'] += abs(pnl)

        # Format response
        formatted = {}
        total_winning = 0
        for strat_name, data in strategies.items():
            total = len(data['trades'])
            total_pnl = sum(t.get('realized_pnl', 0) for t in data['trades'])
            winning = data['winning']
            losing = data['losing']
            win_rate = (winning / total * 100) if total > 0 else 0
            expectancy = total_pnl / total if total > 0 else 0

            # Profit factor = gross profit / gross loss
            gross_profit = data['winning_pnl']
            gross_loss = data['losing_pnl']
            profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (1.0 if gross_profit == 0 else float('inf'))

            formatted[strat_name] = {
                'total_trades': total,
                'winning_trades': winning,
                'losing_trades': losing,
                'win_rate_pct': win_rate,
                'total_pnl': total_pnl,
                'expectancy': expectancy,
                'profit_factor': profit_factor
            }
            total_winning += winning

        avg_win_rate = (total_winning / total_trades * 100) if total_trades > 0 else 0

        return {
            "strategies": formatted,
            "summary": {
                "total_strategies": len(formatted),
                "total_trades": total_trades,
                "avg_win_rate": avg_win_rate
            }
        }

    except Exception as e:
        logger.error(f"Error fetching strategy stats: {e}", exc_info=True)
        return {
            "strategies": {},
            "summary": {
                "total_strategies": 0,
                "total_trades": 0,
                "avg_win_rate": 0
            }
        }


@router.get("/allocation")
async def get_allocation_compat():
    """Compatibility wrapper for /api/portfolio/allocation."""
    try:
        from backend.exchange.paper_trading import get_paper_trading

        engine = get_paper_trading()
        if not engine:
            return {
                "allocation": {
                    "crypto": {"total": 0, "pct": 0},
                    "cash": {"total": 1000, "pct": 100}
                },
                "diversification": {
                    "herfindahl_index": 0,
                    "effective_number_of_positions": 0,
                    "concentration_risk": "none"
                }
            }

        account = engine.get_account_state()
        cash = account.get('cash', 1000)
        positions_value = account.get('positions_value', 0)
        total_equity = account.get('total_equity', 1000)

        crypto_pct = (positions_value / total_equity * 100) if total_equity > 0 else 0
        cash_pct = (cash / total_equity * 100) if total_equity > 0 else 100

        return {
            "allocation": {
                "crypto": {
                    "total": positions_value,
                    "pct": crypto_pct
                },
                "cash": {
                    "total": cash,
                    "pct": cash_pct
                }
            },
            "diversification": {
                "herfindahl_index": 0.5 if positions_value > 0 else 0,
                "effective_number_of_positions": 1 if positions_value > 0 else 0,
                "concentration_risk": "high" if positions_value > (total_equity * 0.5) else "low"
            },
            "rebalancing": {
                "target_allocation": {
                    "crypto": 10,
                    "cash": 90
                },
                "rebalance_needed": abs(crypto_pct - 10) > 5
            }
        }

    except Exception as e:
        logger.error(f"Error in allocation wrapper: {e}", exc_info=True)
        return {
            "allocation": {
                "crypto": {"total": 0, "pct": 0},
                "cash": {"total": 1000, "pct": 100}
            }
        }
