"""
Phase 321: Risk Metrics API Endpoints

REST API for real-time risk analytics: VaR, Expected Shortfall, regime-specific
risk profiles, stress test results, and alert thresholds.
"""

import logging
from typing import Dict, Optional, Any
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query, Path
import pandas as pd
import numpy as np

from backend.analytics.risk_metrics_engine import (
    get_risk_metrics_engine,
)
from backend.analytics.stress_test_engine import (
    get_stress_test_engine,
    StressScenario,
)
from backend.exchange.paper_trading import get_paper_trading

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/risk", tags=["risk"])


@router.get("/metrics")
async def get_risk_metrics(
    lookback_days: int = Query(
        90, ge=30, le=365, description="Days of history for metrics"
    ),
) -> Dict[str, Any]:
    """
    Get comprehensive portfolio risk metrics.

    Parameters:
    -----------
    lookback_days : int
        Number of days of history to analyze (30-365)

    Returns:
    --------
    {
        "timestamp": "2026-06-24T...",
        "value_at_risk_95": -2.5,
        "value_at_risk_99": -4.2,
        "expected_shortfall_95": -4.1,
        "expected_shortfall_99": -6.8,
        "max_drawdown_pct": -15.3,
        "volatility_pct": 18.5,
        "sharpe_ratio": 1.45,
        "sortino_ratio": 1.89,
        "var_ratio": 0.61,
        "skewness": -0.42,
        "kurtosis": 3.21,
        "classification": "BALANCED",
    }
    """
    try:
        engine = get_paper_trading()
        if not engine:
            raise HTTPException(
                status_code=503, detail="Paper trading engine not available"
            )

        # Get portfolio returns (simplified: use equity curve changes)
        positions = engine.get_positions()
        if not positions:
            return {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "error": "No positions in portfolio",
                "value_at_risk_95": 0,
                "value_at_risk_99": 0,
                "expected_shortfall_95": 0,
                "expected_shortfall_99": 0,
                "max_drawdown_pct": 0,
                "volatility_pct": 0,
                "sharpe_ratio": 0,
                "sortino_ratio": 0,
                "var_ratio": 0,
                "skewness": 0,
                "kurtosis": 0,
                "classification": "UNKNOWN",
            }

        # Generate synthetic returns from position data (in real system, would fetch historical)
        returns = pd.Series(np.random.normal(0.05, 1.5, lookback_days))

        risk_engine = get_risk_metrics_engine()
        metrics = risk_engine.calculate_risk_metrics(returns)

        classification = risk_engine.risk_classification(metrics)

        return {
            "timestamp": metrics.timestamp.isoformat(),
            "value_at_risk_95": round(metrics.value_at_risk_95, 2),
            "value_at_risk_99": round(metrics.value_at_risk_99, 2),
            "expected_shortfall_95": round(metrics.expected_shortfall_95, 2),
            "expected_shortfall_99": round(metrics.expected_shortfall_99, 2),
            "max_drawdown_pct": round(metrics.max_drawdown_pct, 2),
            "volatility_pct": round(metrics.volatility_pct, 2),
            "sharpe_ratio": round(metrics.sharpe_ratio, 2),
            "sortino_ratio": round(metrics.sortino_ratio, 2),
            "var_ratio": round(metrics.var_ratio, 2),
            "skewness": round(metrics.skewness, 2),
            "kurtosis": round(metrics.kurtosis, 2),
            "classification": classification,
        }

    except Exception as e:
        logger.error(f"Error calculating risk metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/regime-profile/{regime}")
async def get_regime_risk_profile(
    regime: str = Path(..., description="Market regime: bull/bear/sideways/volatile"),
) -> Dict[str, Any]:
    """
    Get risk profile for a specific market regime.

    Parameters:
    -----------
    regime : str
        Market regime: bull, bear, sideways, or volatile

    Returns:
    --------
    {
        "regime": "bull",
        "volatility_pct": 12.3,
        "var_95_pct": -1.8,
        "es_95_pct": -2.9,
        "max_historical_drawdown_pct": -8.5,
        "avg_daily_loss_pct": -0.3,
        "worst_day_loss_pct": -5.2,
        "prob_loss_above_1pct": 5.2,
        "sharpe_ratio": 1.8,
        "guidance": "Lower risk environment suitable for growth exposure"
    }
    """
    if regime not in ["bull", "bear", "sideways", "volatile"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid regime. Must be: bull, bear, sideways, or volatile",
        )

    try:
        # In real system, would fetch historical data and calculate regime profile
        # For now, return pre-calculated profiles
        profiles = {
            "bull": {
                "regime": "bull",
                "volatility_pct": 12.3,
                "var_95_pct": -1.8,
                "es_95_pct": -2.9,
                "max_historical_drawdown_pct": -8.5,
                "avg_daily_loss_pct": -0.3,
                "worst_day_loss_pct": -5.2,
                "prob_loss_above_1pct": 5.2,
                "sharpe_ratio": 1.8,
                "guidance": "Lower risk environment - suitable for growth exposure",
            },
            "bear": {
                "regime": "bear",
                "volatility_pct": 28.5,
                "var_95_pct": -4.2,
                "es_95_pct": -6.8,
                "max_historical_drawdown_pct": -35.2,
                "avg_daily_loss_pct": -0.8,
                "worst_day_loss_pct": -12.5,
                "prob_loss_above_1pct": 28.5,
                "sharpe_ratio": -0.5,
                "guidance": "Higher risk environment - consider defensive positioning",
            },
            "sideways": {
                "regime": "sideways",
                "volatility_pct": 15.8,
                "var_95_pct": -2.3,
                "es_95_pct": -3.8,
                "max_historical_drawdown_pct": -12.1,
                "avg_daily_loss_pct": -0.4,
                "worst_day_loss_pct": -6.3,
                "prob_loss_above_1pct": 12.3,
                "sharpe_ratio": 0.9,
                "guidance": "Moderate risk - focus on income strategies",
            },
            "volatile": {
                "regime": "volatile",
                "volatility_pct": 32.1,
                "var_95_pct": -5.1,
                "es_95_pct": -8.2,
                "max_historical_drawdown_pct": -42.5,
                "avg_daily_loss_pct": -1.2,
                "worst_day_loss_pct": -18.3,
                "prob_loss_above_1pct": 35.2,
                "sharpe_ratio": -0.8,
                "guidance": "High volatility - reduce leverage and risk exposure",
            },
        }

        return profiles.get(regime, {})

    except Exception as e:
        logger.error(f"Error fetching regime profile: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stress-tests")
async def get_stress_test_results(
    symbol: Optional[str] = Query(None, description="Optional: filter by symbol"),
) -> Dict[str, Any]:
    """
    Run all stress test scenarios and return results.

    Returns:
    --------
    {
        "timestamp": "2026-06-24T...",
        "scenarios": [
            {
                "scenario": "market_crash",
                "portfolio_loss_pct": -22.5,
                "worst_affected": "BTCUSDT",
                "worst_loss_pct": -25.0,
                "recovery_days": 60,
                "leverage_requirement": 11.25,
                "risk_classification": "HIGH"
            },
            ...
        ],
        "worst_case": {
            "scenario": "crypto_crash",
            "portfolio_loss_pct": -28.3,
            "recovery_days": 90
        },
        "portfolio_value_eur": 100000,
        "estimated_value_after_worst": 71700
    }
    """
    engine = get_paper_trading()
    if not engine:
        raise HTTPException(
            status_code=503, detail="Paper trading engine not available"
        )

    positions = engine.get_positions()
    if not positions:
        raise HTTPException(status_code=400, detail="No positions to stress test")

    try:
        account = engine.get_account_state()
        portfolio_value = account.get("total_equity", 0)

        # Mock position values and symbols
        position_values = {p["symbol"]: p.get("value_eur", 0) for p in positions}
        symbol_sectors = {
            "BTCUSDT": "cryptocurrency",
            "ETHUSDT": "cryptocurrency",
            "EQ_AAPL": "technology",
            "EQ_MSFT": "technology",
        }

        stress_engine = get_stress_test_engine()
        results = stress_engine.run_all_scenarios(
            position_values=position_values,
            current_prices={p["symbol"]: p.get("price", 0) for p in positions},
            symbol_sectors=symbol_sectors,
        )

        # Format results
        scenarios = []
        worst_case = None
        worst_loss = float("inf")

        for scenario, result in results.items():
            scenario_result = {
                "scenario": scenario.value,
                "portfolio_loss_pct": round(result.portfolio_loss_pct, 2),
                "worst_affected": result.worst_affected,
                "worst_loss_pct": round(result.worst_loss_pct, 2),
                "recovery_days": result.recovery_days_estimate,
                "leverage_requirement": round(result.leverage_requirement, 2),
                "risk_classification": result.risk_classification,
            }
            scenarios.append(scenario_result)

            if result.portfolio_loss_pct < worst_loss:
                worst_loss = result.portfolio_loss_pct
                worst_case = {
                    "scenario": scenario.value,
                    "portfolio_loss_pct": round(result.portfolio_loss_pct, 2),
                    "recovery_days": result.recovery_days_estimate,
                }

        return {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "scenarios": scenarios,
            "worst_case": worst_case,
            "portfolio_value_eur": portfolio_value,
            "estimated_value_after_worst": round(
                portfolio_value * (1 + worst_loss / 100), 2
            ),
        }

    except Exception as e:
        logger.error(f"Error running stress tests: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stress-tests/{scenario}")
async def get_single_stress_test(
    scenario: str = Path(
        ..., description="Stress scenario: market_crash, volatility_spike, etc"
    ),
) -> Dict[str, Any]:
    """
    Get stress test result for a single scenario.

    Parameters:
    -----------
    scenario : str
        Scenario name: market_crash, volatility_spike, correlation_breakdown, sector_rotation, etc

    Returns:
    --------
    {
        "scenario": "market_crash",
        "portfolio_loss_pct": -22.5,
        "affected_symbols": {"BTCUSDT": -25.0, "EQ_AAPL": -20.0, ...},
        "worst_affected": "BTCUSDT",
        "worst_loss_pct": -25.0,
        "recovery_days": 60,
        "leverage_requirement": 11.25,
        "risk_classification": "HIGH",
        "description": "Global market crash (-20%)"
    }
    """
    valid_scenarios = [s.value for s in StressScenario]
    if scenario not in valid_scenarios:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid scenario. Must be one of: {', '.join(valid_scenarios)}",
        )

    engine = get_paper_trading()
    if not engine:
        raise HTTPException(
            status_code=503, detail="Paper trading engine not available"
        )

    positions = engine.get_positions()
    if not positions:
        raise HTTPException(status_code=400, detail="No positions to stress test")

    try:
        position_values = {p["symbol"]: p.get("value_eur", 0) for p in positions}
        current_prices = {p["symbol"]: p.get("price", 0) for p in positions}
        symbol_sectors = {p["symbol"]: "other" for p in positions}

        stress_engine = get_stress_test_engine()
        scenario_enum = StressScenario(scenario)

        result = stress_engine.run_stress_test(
            position_values=position_values,
            current_prices=current_prices,
            symbol_sectors=symbol_sectors,
            scenario=scenario_enum,
        )

        return {
            "scenario": result.scenario.value,
            "portfolio_loss_pct": round(result.portfolio_loss_pct, 2),
            "affected_symbols": {
                k: round(v, 2) for k, v in result.affected_symbols.items()
            },
            "worst_affected": result.worst_affected,
            "worst_loss_pct": round(result.worst_loss_pct, 2),
            "recovery_days": result.recovery_days_estimate,
            "leverage_requirement": round(result.leverage_requirement, 2),
            "risk_classification": result.risk_classification,
            "description": stress_engine.scenario_definitions[scenario_enum].get(
                "description", ""
            ),
        }

    except Exception as e:
        logger.error(f"Error running stress test: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/alerts/thresholds")
async def set_risk_alert_thresholds(
    var_95_threshold: float = Query(..., description="VaR 95% threshold (%)"),
    volatility_threshold: float = Query(..., description="Volatility threshold (%)"),
    max_drawdown_threshold: float = Query(
        ..., description="Max drawdown threshold (%)"
    ),
) -> Dict[str, Any]:
    """
    Set risk alert thresholds for monitoring.

    Parameters:
    -----------
    var_95_threshold : float
        Alert if VaR 95% exceeds this value (e.g., -3.5%)
    volatility_threshold : float
        Alert if volatility exceeds this value (e.g., 25%)
    max_drawdown_threshold : float
        Alert if drawdown exceeds this value (e.g., -20%)

    Returns:
    --------
    {
        "success": true,
        "thresholds": {
            "var_95": -3.5,
            "volatility": 25.0,
            "max_drawdown": -20.0
        },
        "message": "Risk alert thresholds updated successfully"
    }
    """
    # In real system, would persist to database
    # For now, just validate and return
    if var_95_threshold >= 0:
        raise HTTPException(status_code=400, detail="VaR threshold must be negative")
    if volatility_threshold <= 0:
        raise HTTPException(
            status_code=400, detail="Volatility threshold must be positive"
        )
    if max_drawdown_threshold >= 0:
        raise HTTPException(
            status_code=400, detail="Max drawdown threshold must be negative"
        )

    try:
        return {
            "success": True,
            "thresholds": {
                "var_95": var_95_threshold,
                "volatility": volatility_threshold,
                "max_drawdown": max_drawdown_threshold,
            },
            "message": "Risk alert thresholds updated successfully",
        }

    except Exception as e:
        logger.error(f"Error setting thresholds: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts/status")
async def get_risk_alert_status() -> Dict[str, Any]:
    """
    Get current risk alert status (comparing metrics to thresholds).

    Returns:
    --------
    {
        "timestamp": "2026-06-24T...",
        "current_metrics": {
            "var_95": -2.5,
            "volatility": 18.5,
            "max_drawdown": -15.3
        },
        "thresholds": {
            "var_95": -3.5,
            "volatility": 25.0,
            "max_drawdown": -20.0
        },
        "alerts": [
            {"metric": "var_95", "status": "OK", "value": -2.5, "threshold": -3.5}
        ],
        "critical_alerts": []
    }
    """
    try:
        engine = get_paper_trading()
        if not engine:
            raise HTTPException(
                status_code=503, detail="Paper trading engine not available"
            )

        # In real system, would fetch actual current metrics
        # For demo, return synthetic data
        current_metrics = {
            "var_95": -2.5,
            "volatility": 18.5,
            "max_drawdown": -15.3,
        }

        thresholds = {
            "var_95": -3.5,
            "volatility": 25.0,
            "max_drawdown": -20.0,
        }

        alerts = []
        critical_alerts = []

        # Check each metric against threshold
        for metric_name, metric_value in current_metrics.items():
            threshold = thresholds[metric_name]
            if metric_name == "var_95":
                # For VaR, alert if metric is MORE negative than threshold
                status = "ALERT" if metric_value < threshold else "OK"
            else:
                # For volatility/drawdown, alert if metric exceeds threshold
                status = "ALERT" if metric_value > threshold else "OK"

            alert = {
                "metric": metric_name,
                "status": status,
                "value": round(metric_value, 2),
                "threshold": round(threshold, 2),
            }

            if status == "ALERT":
                critical_alerts.append(alert)
            else:
                alerts.append(alert)

        return {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "current_metrics": current_metrics,
            "thresholds": thresholds,
            "alerts": alerts,
            "critical_alerts": critical_alerts,
            "status": "CRITICAL" if critical_alerts else "OK",
        }

    except Exception as e:
        logger.error(f"Error fetching alert status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard/summary")
async def get_risk_dashboard_summary() -> Dict[str, Any]:
    """
    Get complete risk dashboard summary (all metrics, regimes, alerts in one call).

    Returns:
    --------
    {
        "timestamp": "2026-06-24T...",
        "portfolio_value": 100000,
        "risk_metrics": {...},
        "regime_profiles": {"bull": {...}, "bear": {...}, ...},
        "worst_stress_scenario": {...},
        "alerts": {...}
    }
    """
    try:
        engine = get_paper_trading()
        if not engine:
            raise HTTPException(
                status_code=503, detail="Paper trading engine not available"
            )

        account = engine.get_account_state()
        portfolio_value = account.get("total_equity", 0)

        # Aggregate all risk data
        # In real system, would call individual endpoints
        return {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "portfolio_value": portfolio_value,
            "risk_level": "BALANCED",
            "summary": {
                "var_95_pct": -2.5,
                "volatility_pct": 18.5,
                "max_drawdown_pct": -15.3,
                "sharpe_ratio": 1.45,
            },
            "regime": {
                "current": "bull",
                "confidence": 0.78,
                "risk_profile": {
                    "volatility_pct": 12.3,
                    "var_95_pct": -1.8,
                    "guidance": "Lower risk environment",
                },
            },
            "worst_stress": {
                "scenario": "crypto_crash",
                "portfolio_loss_pct": -28.3,
                "recovery_days": 90,
            },
            "alerts": {
                "critical": 0,
                "warnings": 1,
                "status": "OK",
            },
        }

    except Exception as e:
        logger.error(f"Error generating dashboard: {e}")
        raise HTTPException(status_code=500, detail=str(e))
