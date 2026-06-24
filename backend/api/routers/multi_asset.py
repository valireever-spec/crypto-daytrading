"""API endpoints for multi-asset support."""

import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from typing import Optional

from backend.analytics.asset_classes import (
    AssetRegistry,
    AssetClass,
    Region,
    AssetClassWeights,
    SignalWeights
)
from backend.analytics.currency_risk import CurrencyRiskCalculator, CurrencyExposure
from backend.analytics.global_optimization import GlobalPortfolioOptimizer

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/multi-asset", tags=["Multi-Asset"])


@router.get("/assets")
async def list_all_assets():
    """List all supported assets."""
    registry = AssetRegistry()
    assets = registry.get_all()
    return JSONResponse({
        "total": len(assets),
        "assets": [a.to_dict() for a in assets]
    })


@router.get("/assets/by-class/{asset_class}")
async def list_assets_by_class(asset_class: str):
    """List assets by class."""
    registry = AssetRegistry()

    try:
        ac = AssetClass(asset_class)
        assets = registry.get_by_class(ac)
        return JSONResponse({
            "asset_class": asset_class,
            "count": len(assets),
            "assets": [a.to_dict() for a in assets]
        })
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid asset class: {asset_class}")


@router.get("/assets/by-region/{region}")
async def list_assets_by_region(region: str):
    """List assets by region."""
    registry = AssetRegistry()

    try:
        reg = Region(region)
        assets = registry.get_by_region(reg)
        return JSONResponse({
            "region": region,
            "count": len(assets),
            "assets": [a.to_dict() for a in assets]
        })
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid region: {region}")


@router.get("/assets/{symbol}")
async def get_asset(symbol: str):
    """Get asset details."""
    registry = AssetRegistry()
    asset = registry.get(symbol.upper())
    if not asset:
        raise HTTPException(status_code=404, detail=f"Asset not found: {symbol}")

    return JSONResponse(asset.to_dict())


@router.get("/allocation/recommended")
async def get_recommended_allocation():
    """Get recommended asset allocation."""
    weights = AssetClassWeights()

    if not weights.validate():
        logger.warning("Asset allocation weights do not sum to 1.0")

    return JSONResponse({
        "allocation": weights.get_all_weights(),
        "valid": weights.validate(),
        "message": "Recommended global asset allocation"
    })


@router.get("/allocation/signal-weights/{asset_class}")
async def get_signal_weights(asset_class: str):
    """Get signal calculation weights for asset class."""
    signal_weights = SignalWeights()

    try:
        ac = AssetClass(asset_class)
        weights = signal_weights.get_weights(ac)
        return JSONResponse({
            "asset_class": asset_class,
            "signal_weights": weights,
            "components": list(weights.keys())
        })
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid asset class: {asset_class}")


@router.get("/currency/exposure")
async def get_currency_exposure(positions: Optional[str] = None):
    """Calculate currency exposure."""
    calc = CurrencyRiskCalculator()

    # Mock positions for demo
    test_positions = {
        "AAPL": {"currency": "USD", "value": 50000},
        "EWG": {"currency": "EUR", "value": 30000},
        "HKSE": {"currency": "HKD", "value": 20000},
    }

    exposures = calc.calculate_currency_exposure(test_positions)

    return JSONResponse({
        "exposures": {
            currency: {
                "amount_usd": exposure.exposure_amount,
                "pct": exposure.exposure_pct,
                "hedged_amount": exposure.hedged_amount,
                "hedge_ratio": exposure.hedge_ratio
            }
            for currency, exposure in exposures.items()
        }
    })


@router.get("/currency/var")
async def get_currency_var(currency: str = "EUR", confidence: float = 0.95):
    """Calculate currency Value at Risk."""
    calc = CurrencyRiskCalculator()

    # Mock total exposure
    total_exposure = 100000.0

    var = calc.calculate_currency_var(total_exposure, currency, confidence)

    return JSONResponse({
        "currency": currency,
        "exposure_usd": total_exposure,
        "var_usd": var,
        "var_pct": (var / total_exposure * 100) if total_exposure > 0 else 0,
        "confidence": confidence
    })


@router.get("/currency/hedge-suggestions")
async def get_hedge_suggestions():
    """Get currency hedge recommendations."""
    calc = CurrencyRiskCalculator()

    # Mock exposures
    exposures = {
        "EUR": CurrencyExposure("EUR", 50000, 25, 0, 0),
        "GBP": CurrencyExposure("GBP", 30000, 15, 0, 0),
        "JPY": CurrencyExposure("JPY", 10000, 5, 0, 0),
    }

    suggestions = calc.suggest_hedges(exposures)

    return JSONResponse({
        "count": len(suggestions),
        "suggestions": suggestions
    })


@router.get("/optimization/efficient-frontier")
async def get_efficient_frontier(num_points: int = 30):
    """Calculate efficient frontier."""
    optimizer = GlobalPortfolioOptimizer()

    # Set up mock returns and risks for asset classes
    optimizer.set_expected_returns({
        "crypto": 0.25,
        "us_equity": 0.10,
        "eu_equity": 0.08,
        "bond_gov": 0.03,
        "commodity": 0.05,
    })

    optimizer.set_volatilities({
        "crypto": 0.70,
        "us_equity": 0.15,
        "eu_equity": 0.18,
        "bond_gov": 0.05,
        "commodity": 0.20,
    })

    frontier = optimizer.calculate_efficient_frontier(num_points)

    return JSONResponse({
        "points": len(frontier),
        "frontier": frontier
    })


@router.get("/optimization/optimal-portfolio")
async def get_optimal_portfolio(target_return: Optional[float] = None, risk_aversion: float = 1.0):
    """Get optimal portfolio allocation."""
    optimizer = GlobalPortfolioOptimizer()

    # Set up mock data
    optimizer.set_expected_returns({
        "crypto": 0.25,
        "us_equity": 0.10,
        "eu_equity": 0.08,
        "bond_gov": 0.03,
        "commodity": 0.05,
    })

    optimizer.set_volatilities({
        "crypto": 0.70,
        "us_equity": 0.15,
        "eu_equity": 0.18,
        "bond_gov": 0.05,
        "commodity": 0.20,
    })

    result = optimizer.find_optimal_portfolio(target_return, risk_aversion)

    return JSONResponse({
        "weights": result["weights"],
        "expected_return": result["expected_return"],
        "risk": result["risk"],
        "sharpe_ratio": result["sharpe_ratio"]
    })


@router.post("/optimization/rebalancing-plan")
async def calculate_rebalancing_plan(
    current_weights: dict,
    target_weights: dict,
    portfolio_value: float
):
    """Calculate rebalancing plan."""
    optimizer = GlobalPortfolioOptimizer()

    plan = optimizer.calculate_rebalancing_plan(
        current_weights,
        target_weights,
        portfolio_value
    )

    return JSONResponse(plan)


@router.get("/portfolio-summary")
async def get_portfolio_summary():
    """Get multi-asset portfolio summary."""
    registry = AssetRegistry()
    all_assets = registry.get_all()

    summary_by_class = {}
    for asset_class in AssetClass:
        assets = registry.get_by_class(asset_class)
        summary_by_class[asset_class.value] = len(assets)

    summary_by_region = {}
    for region in Region:
        assets = registry.get_by_region(region)
        summary_by_region[region.value] = len(assets)

    return JSONResponse({
        "total_assets": len(all_assets),
        "by_class": summary_by_class,
        "by_region": summary_by_region,
        "asset_classes": [ac.value for ac in AssetClass],
        "regions": [r.value for r in Region]
    })
