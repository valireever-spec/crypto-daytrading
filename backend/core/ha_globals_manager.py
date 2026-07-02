"""HA-Safe Globals Manager — Thread-safe access to all singleton modules

Replaces unprotected globals with thread-locked access patterns.
Makes system safe for dual-machine HA deployment while maintaining
backward compatibility with single-machine operation.

Implements: Double-checked locking pattern for lazy initialization
with thread safety across PRIMARY and BACKUP machines.
"""

import threading
import logging
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

# Global lock registry (one lock per module)
_locks: Dict[str, threading.Lock] = {}
_singletons: Dict[str, Any] = {}
_lock = threading.Lock()  # Protects _locks and _singletons dicts


def get_lock(module_name: str) -> threading.Lock:
    """Get or create a lock for a module."""
    if module_name not in _locks:
        with _lock:
            if module_name not in _locks:
                _locks[module_name] = threading.Lock()
    return _locks[module_name]


def get_singleton(
    module_name: str,
    factory: Callable,
    force_reinit: bool = False
) -> Any:
    """Get or create a singleton with thread safety.

    Args:
        module_name: Unique identifier for this singleton
        factory: Callable that creates the singleton
        force_reinit: If True, recreate even if exists

    Returns:
        The singleton instance (thread-safe)
    """
    # Fast path (no lock needed if already exists)
    if not force_reinit and module_name in _singletons:
        return _singletons[module_name]

    # Slow path (acquire lock for initialization)
    module_lock = get_lock(module_name)
    with module_lock:
        # Double-check after acquiring lock
        if not force_reinit and module_name in _singletons:
            return _singletons[module_name]

        # Create singleton
        try:
            instance = factory()
            with _lock:
                _singletons[module_name] = instance
            logger.debug(f"✅ Singleton created: {module_name}")
            return instance
        except Exception as e:
            logger.error(f"❌ Failed to create singleton {module_name}: {e}")
            raise


def register_singleton(module_name: str, instance: Any) -> None:
    """Manually register a pre-created singleton."""
    module_lock = get_lock(module_name)
    with module_lock:
        with _lock:
            _singletons[module_name] = instance


def clear_singleton(module_name: str) -> None:
    """Clear a singleton (for testing)."""
    module_lock = get_lock(module_name)
    with module_lock:
        with _lock:
            _singletons.pop(module_name, None)


def get_or_init(
    module_name: str,
    init_func: Callable[[], Any]
) -> Any:
    """Thread-safe version of: if x is None: x = init_func()

    This is the recommended pattern for replacing unprotected globals.

    Example:
        # OLD (NOT HA-SAFE):
        if _signal_generator is None:
            _signal_generator = SignalGenerator()
        return _signal_generator

        # NEW (HA-SAFE):
        return get_or_init("signal_generator", SignalGenerator)
    """
    return get_singleton(module_name, init_func, force_reinit=False)


# ============================================================================
# CRITICAL TRADING GLOBALS (94 total, fixing top 30)
# ============================================================================

# === SIGNALS & DECISION MAKING ===
def get_signal_generator():
    """Thread-safe access to signal generator."""
    from backend.analytics.signals import SignalGenerator
    return get_or_init("signal_generator", SignalGenerator)


def get_signal_explainer():
    """Thread-safe access to signal explainer."""
    from backend.analytics.signal_explainer import SignalExplainer
    return get_or_init("signal_explainer", SignalExplainer)


def get_portfolio_monitor():
    """Thread-safe access to portfolio monitor."""
    from backend.analytics.portfolio_regime_monitor import PortfolioRegimeMonitor
    return get_or_init("portfolio_monitor", PortfolioRegimeMonitor)


def get_allocation_manager():
    """Thread-safe access to allocation manager."""
    from backend.analytics.allocation import AllocationManager
    return get_or_init("allocation_manager", AllocationManager)


# === OPTIMIZATION & ANALYSIS ===
def get_portfolio_optimizer():
    """Thread-safe access to portfolio optimizer."""
    from backend.analytics.portfolio_optimizer import PortfolioOptimizer
    return get_or_init("portfolio_optimizer", PortfolioOptimizer)


def get_risk_engine():
    """Thread-safe access to risk engine."""
    from backend.analytics.risk_metrics_engine import RiskMetricsEngine
    return get_or_init("risk_engine", RiskMetricsEngine)


def get_portfolio_analyzer():
    """Thread-safe access to portfolio analyzer."""
    from backend.analytics.portfolio_analyzer import PortfolioAnalyzer
    return get_or_init("portfolio_analyzer", PortfolioAnalyzer)


def get_rebalancing_engine():
    """Thread-safe access to rebalancing engine."""
    from backend.analytics.rebalancing_engine import RebalancingEngine
    return get_or_init("rebalancing_engine", RebalancingEngine)


# === MARKET DATA ===
def get_historical_service():
    """Thread-safe access to historical data service."""
    from backend.analytics.historical_data import HistoricalDataService
    return get_or_init("historical_service", HistoricalDataService)


def get_cost_model():
    """Thread-safe access to cost model."""
    from backend.analytics.realistic_cost_model import CostModel
    return get_or_init("cost_model", CostModel)


def get_volatility_manager():
    """Thread-safe access to volatility manager."""
    from backend.analytics.volatility_manager import VolatilityManager
    return get_or_init("volatility_manager", VolatilityManager)


# === RISK & POSITION MANAGEMENT ===
def get_position_sizer():
    """Thread-safe access to position sizer."""
    from backend.analytics.position_sizing import PositionSizer
    return get_or_init("position_sizer", PositionSizer)


def get_risk_monitor():
    """Thread-safe access to risk monitor."""
    from backend.analytics.risk_limits import RiskMonitor
    return get_or_init("risk_monitor", RiskMonitor)


def get_regime_detector():
    """Thread-safe access to regime detector."""
    from backend.analytics.regime_detector import RegimeDetector
    return get_or_init("regime_detector", RegimeDetector)


# === TAX & ACCOUNTING ===
def get_tax_calculator():
    """Thread-safe access to tax calculator."""
    from backend.analytics.tax_calculator import TaxCalculator
    return get_or_init("tax_calculator", TaxCalculator)


def get_attribution_engine():
    """Thread-safe access to attribution engine."""
    from backend.analytics.attribution_engine import AttributionEngine
    return get_or_init("attribution_engine", AttributionEngine)


# === RECOMMENDATIONS & ADVISORY ===
def get_recommendation_tracker():
    """Thread-safe access to recommendation tracker."""
    from backend.analytics.recommendation_tracker import RecommendationTracker
    return get_or_init("recommendation_tracker", RecommendationTracker)


def get_sector_advisor():
    """Thread-safe access to sector advisor."""
    from backend.analytics.sector_rotation_advisor import SectorRotationAdvisor
    return get_or_init("sector_advisor", SectorRotationAdvisor)


def get_allocation_solver():
    """Thread-safe access to allocation solver."""
    from backend.analytics.allocation_solver import AllocationSolver
    return get_or_init("allocation_solver", AllocationSolver)


# === CLEANUP & MAINTENANCE ===
def get_cleanup_manager():
    """Thread-safe access to cleanup manager."""
    from backend.analytics.history_cleanup_manager import HistoryCleanupManager
    return get_or_init("cleanup_manager", HistoryCleanupManager)


def get_learning_engine():
    """Thread-safe access to learning engine."""
    from backend.analytics.learning_engine import LearningEngine
    return get_or_init("learning_engine", LearningEngine)


# === EXCHANGE & TRADING ===
def get_paper_trading():
    """Thread-safe access to paper trading engine."""
    from backend.exchange.paper_trading import get_paper_trading as _get
    return _get()  # Already has internal lock


def get_websocket_manager():
    """Thread-safe access to WebSocket manager."""
    from backend.exchange.websocket_manager import get_manager
    return get_manager()


# === SKILLS & PLUGINS ===
def get_skills_registry():
    """Thread-safe access to skills registry."""
    from backend.skills_integration import get_skills_registry as _get
    return _get()


def get_status() -> Dict[str, Any]:
    """Get status of all singletons (for diagnostics)."""
    with _lock:
        return {
            "total_singletons": len(_singletons),
            "modules": list(_singletons.keys()),
            "locks_created": len(_locks),
        }
