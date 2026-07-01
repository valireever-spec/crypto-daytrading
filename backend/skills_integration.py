"""
Skills Integration for Crypto Daytrading Platform

Centralizes skill usage across the trading system:
- Systematic debugging for trade failures
- Performance profiling (NFR-002: <2s order execution)
- UI testing for dashboard
- Comprehensive testing for signal quality
- Chaos testing for HA/failover resilience
- Structured logging for trade audit trail

Usage:
    from backend.skills_integration import skills

    # Debug trade failure
    findings = skills.debug_trade_failure(symbol, "logs/execution.log")

    # Profile order execution
    profile = skills.profile_order_execution(symbol)

    # Test dashboard
    test_result = skills.test_dashboard_health()
"""

from pathlib import Path
import sys
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging

# Add skill-library to path and import skills
# Path: crypto-daytrading/backend/skills_integration.py -> ../../skill-library
SKILL_LIBRARY_PATH = Path(__file__).resolve().parent.parent.parent / "skill-library"
import importlib.util

SKILLS_AVAILABLE = True
IMPORT_ERROR = None

def _load_skill(skill_name: str, class_name: str):
    """Dynamically load a skill."""
    try:
        skill_path = SKILL_LIBRARY_PATH / skill_name / "core.py"
        spec = importlib.util.spec_from_file_location(f"{skill_name}.core", skill_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return getattr(module, class_name)
    except Exception as e:
        raise ImportError(f"Failed to load {skill_name}: {e}")

try:
    SystematicDebuggingV2 = _load_skill("systematic-debugging-v2", "SystematicDebuggingV2")
    GitWorktreesV2 = _load_skill("git-worktrees-v2", "GitWorktreesV2")
    PlaywrightTestingV2 = _load_skill("playwright-testing-v2", "PlaywrightTestingV2")
    BrainstormingV2 = _load_skill("brainstorming-v2", "BrainstormingV2")
    KnowledgeGraphV2 = _load_skill("knowledge-graph-v2", "KnowledgeGraphV2")
    FileOrganizerV2 = _load_skill("file-organizer-v2", "FileOrganizerV2")
    WebAssetGeneratorV2 = _load_skill("web-asset-generator-v2", "WebAssetGeneratorV2")
    FFufSecurityV2 = _load_skill("ffuf-security-v2", "FFufSecurityV2")
except ImportError as e:
    SKILLS_AVAILABLE = False
    IMPORT_ERROR = str(e)


logger = logging.getLogger(__name__)


class CryptoSkillsManager:
    """
    Centralized skills manager for crypto-daytrading.

    Provides project-specific wrappers around generic skills:
    - Trade execution debugging
    - Performance monitoring (latency critical)
    - Dashboard UI testing
    - Signal quality testing
    - HA/failover resilience testing
    - Trade audit logging
    """

    def __init__(self, log_dir: str = "logs", dashboard_url: str = "http://localhost:8000"):
        """
        Initialize skills manager.

        Args:
            log_dir: Directory for logs and audit trails
            dashboard_url: URL of trading dashboard
        """
        if not SKILLS_AVAILABLE:
            raise ImportError(f"Skills not available: {IMPORT_ERROR}")

        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.dashboard_url = dashboard_url

        # Initialize the 8 available skills
        self.debugger = SystematicDebuggingV2()
        self.git = GitWorktreesV2(repo_path=".")
        self.ui_tester = PlaywrightTestingV2(headless=True)
        self.brainstormer = BrainstormingV2()
        self.knowledge_graph = KnowledgeGraphV2()
        self.organizer = FileOrganizerV2()
        self.web_gen = WebAssetGeneratorV2()
        self.security = FFufSecurityV2()

        logger.info("CryptoSkillsManager initialized successfully")

    # ========== DEBUGGING SKILLS ==========

    def debug_trade_failure(
        self,
        symbol: str,
        error_log: str,
        side: str = "BUY",
        quantity: float = 0.0
    ) -> Dict[str, Any]:
        """
        Debug trade execution failure using systematic root-cause analysis.

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            error_log: Path to error log file
            side: BUY or SELL
            quantity: Order quantity

        Returns:
            Investigation findings with confidence score and recommendations

        Example:
            findings = skills.debug_trade_failure("BTCUSDT", "logs/execution.log")
            print(f"Root cause confidence: {findings['confidence']}")
        """
        findings = self.debugger.investigate(
            issue_description=f"Trade execution failed: {side} {quantity} {symbol}",
            error_source_path=error_log,
            reproduction_steps=[
                f"1. Get price for {symbol}",
                f"2. Generate {side} signal at {quantity}",
                f"3. Call Binance API place_order()",
                "4. Observe error in logs",
            ]
        )

        # Log the debugging session
        self.logger_skill.log({
            "event": "trade_failure_debug",
            "symbol": symbol,
            "side": side,
            "status": findings.get("status"),
            "confidence": findings.get("confidence"),
            "root_cause": findings.get("recommendation"),
        })

        return findings

    def debug_signal_generation(
        self,
        symbol: str,
        timeframe: str = "1h",
        error_log: str = "logs/signals.log"
    ) -> Dict[str, Any]:
        """
        Debug signal generation failure.

        Args:
            symbol: Trading pair
            timeframe: Candle timeframe (1m, 5m, 1h, 4h, 1d)
            error_log: Path to signal log

        Returns:
            Investigation findings for signal pipeline
        """
        findings = self.debugger.investigate(
            issue_description=f"Signal generation failed for {symbol} {timeframe}",
            error_source_path=error_log,
            reproduction_steps=[
                f"1. Fetch {timeframe} candles for {symbol}",
                "2. Calculate technical indicators (RSI, MACD, BB)",
                "3. Combine signals (AND/OR logic)",
                "4. Generate BUY/SELL signal",
            ]
        )

        self.logger_skill.log({
            "event": "signal_generation_debug",
            "symbol": symbol,
            "timeframe": timeframe,
            "status": findings.get("status"),
        })

        return findings

    def debug_failover(self, error_log: str = "logs/failover.log") -> Dict[str, Any]:
        """
        Debug HA failover failure (dual-machine redundancy).

        Args:
            error_log: Path to failover logs

        Returns:
            Investigation findings for failover system
        """
        findings = self.debugger.investigate(
            issue_description="HA failover failed - secondary machine did not take over",
            error_source_path=error_log,
            reproduction_steps=[
                "1. Primary machine running normally",
                "2. Primary machine heartbeat stops",
                "3. Secondary detects missing heartbeat (30s timeout)",
                "4. Secondary attempts to acquire database lock",
                "5. Failover should complete within 60s",
            ]
        )

        self.logger_skill.log({
            "event": "failover_debug",
            "status": findings.get("status"),
        })

        return findings

    # ========== PERFORMANCE MONITORING ==========

    def profile_order_execution(self, symbol: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Profile order execution latency (critical for NFR-002: <2s).

        Args:
            symbol: Trading pair
            context: Additional context (side, quantity, etc.)

        Returns:
            Performance profile with latency metrics

        Example:
            profile = skills.profile_order_execution("BTCUSDT")
            print(f"P95 latency: {profile['p95_ms']}ms")
        """
        profile = self.profiler.profile(
            operation_name=f"order_execution_{symbol}",
            operation_type="binance_api_call"
        )

        # Log performance
        self.logger_skill.log({
            "event": "order_execution_profiled",
            "symbol": symbol,
            "p50_ms": profile.get("p50", 0),
            "p95_ms": profile.get("p95", 0),
            "p99_ms": profile.get("p99", 0),
            "passes_nfr002": profile.get("p95", 10000) < 2000,  # NFR-002: <2s
        })

        return profile

    def profile_signal_generation(self, symbol: str, candle_count: int = 1000) -> Dict[str, Any]:
        """
        Profile signal generation latency (critical for NFR-001: <500ms).

        Args:
            symbol: Trading pair
            candle_count: Number of candles to process

        Returns:
            Performance profile with latency metrics
        """
        profile = self.profiler.profile(
            operation_name=f"signal_generation_{symbol}",
            operation_type="cpu_intensive"
        )

        self.logger_skill.log({
            "event": "signal_generation_profiled",
            "symbol": symbol,
            "candles": candle_count,
            "p95_ms": profile.get("p95", 0),
            "passes_nfr001": profile.get("p95", 500) < 500,  # NFR-001: <500ms
        })

        return profile

    # ========== UI TESTING ==========

    def test_dashboard_health(self) -> Dict[str, Any]:
        """
        Test dashboard UI is functioning correctly.

        Verifies:
        - Dashboard loads
        - Price data displayed
        - Trade history visible
        - Risk indicators updated

        Returns:
            Test result with confidence score
        """
        test_result = self.ui_tester.run_test({
            "name": "dashboard_health_check",
            "url": f"{self.dashboard_url}/dashboard",
            "steps": [
                {"action": "load dashboard", "assert": "Dashboard title visible"},
                {"action": "wait for data", "assert": "Price data loaded"},
                {"action": "check trade history", "assert": "Recent trades visible"},
                {"action": "verify indicators", "assert": "Risk zone indicators displayed"},
            ]
        })

        self.logger_skill.log({
            "event": "dashboard_tested",
            "status": test_result.get("status"),
            "passed": test_result.get("passed"),
            "confidence": test_result.get("confidence"),
        })

        return test_result

    def test_dashboard_trade_flow(self) -> Dict[str, Any]:
        """
        Test end-to-end trade flow in dashboard:
        - Select symbol
        - View signals
        - Place order (paper trading)
        - View order confirmation

        Returns:
            Test result with detailed step-by-step results
        """
        test_result = self.ui_tester.run_test({
            "name": "dashboard_trade_flow",
            "url": f"{self.dashboard_url}/dashboard",
            "steps": [
                {"action": "select BTCUSDT", "assert": "Symbol selected"},
                {"action": "view signals", "assert": "Buy/Sell signals visible"},
                {"action": "click place order", "assert": "Order dialog opened"},
                {"action": "confirm paper trade", "assert": "Order placed successfully"},
                {"action": "verify in history", "assert": "Trade appears in history"},
            ]
        })

        return test_result

    # ========== TESTING & QUALITY ==========

    def test_signal_quality(
        self,
        backtest_files: List[str],
        min_coverage: float = 0.85,
        min_win_rate: float = 0.55
    ) -> Dict[str, Any]:
        """
        Test signal generation quality using comprehensive test framework.

        Args:
            backtest_files: List of backtest results to validate
            min_coverage: Minimum code coverage (default 85%)
            min_win_rate: Minimum winning trade percentage (default 55%)

        Returns:
            Quality metrics and test results
        """
        result = self.test_framework.run_quality_suite(
            test_suite="signal_generation",
            test_files=backtest_files,
            min_coverage=min_coverage
        )

        self.logger_skill.log({
            "event": "signal_quality_tested",
            "files_tested": len(backtest_files),
            "coverage": result.get("coverage", 0),
            "quality_score": result.get("quality_score", 0),
        })

        return result

    def test_exchange_integration(self) -> Dict[str, Any]:
        """
        Test Binance API integration with comprehensive tests.

        Verifies:
        - Connection to Binance
        - Order placement
        - Order status checking
        - Error handling

        Returns:
            Integration test results
        """
        result = self.test_framework.run_integration_test(
            test_name="binance_integration",
            test_steps=[
                "Connect to Binance testnet",
                "Place test market order",
                "Check order status",
                "Cancel order",
                "Verify cancellation",
            ]
        )

        return result

    # ========== CHAOS & RESILIENCE TESTING ==========

    def chaos_test_failover(self, duration_seconds: int = 60) -> Dict[str, Any]:
        """
        Test dual-machine failover under chaos conditions.

        Chaos events:
        - Kill primary machine
        - Network partition between machines
        - Database connection delay
        - API rate limiting

        Args:
            duration_seconds: How long to run chaos test

        Returns:
            Chaos test results with recovery metrics
        """
        result = self.chaos_tester.run_chaos_test(
            target_system="ha_failover",
            chaos_events=[
                "kill_primary_binance_connection",
                "network_partition_30s",
                "database_connection_timeout",
                "secondary_slow_disk",
            ],
            duration_seconds=duration_seconds,
            recovery_timeout_seconds=60
        )

        self.logger_skill.log({
            "event": "chaos_test_failover",
            "passed": result.get("passed"),
            "recovery_time_seconds": result.get("recovery_time"),
            "trades_lost": result.get("trades_lost", 0),
        })

        return result

    def chaos_test_signal_generation(self, duration_seconds: int = 30) -> Dict[str, Any]:
        """
        Test signal generation resilience under chaos.

        Chaos events:
        - High CPU usage
        - Memory pressure
        - Slow disk I/O
        - Network latency to Binance

        Args:
            duration_seconds: Chaos test duration

        Returns:
            Resilience metrics
        """
        result = self.chaos_tester.run_chaos_test(
            target_system="signal_generation",
            chaos_events=[
                "cpu_spike_80_percent",
                "memory_pressure_90_percent",
                "disk_io_latency_100ms",
                "binance_api_latency_500ms",
            ],
            duration_seconds=duration_seconds
        )

        return result

    # ========== AUDIT & LOGGING ==========

    def log_trade_executed(self, trade_data: Dict[str, Any]) -> None:
        """
        Log trade execution to audit trail (append-only).

        Args:
            trade_data: Trade details (symbol, side, quantity, price, fee, etc.)
        """
        self.logger_skill.log({
            "event": "trade_executed",
            "timestamp": datetime.now().isoformat(),
            **trade_data
        })

    def log_signal_generated(self, signal_data: Dict[str, Any]) -> None:
        """
        Log signal generation to audit trail.

        Args:
            signal_data: Signal details (symbol, signal, confidence, etc.)
        """
        self.logger_skill.log({
            "event": "signal_generated",
            "timestamp": datetime.now().isoformat(),
            **signal_data
        })

    def get_audit_trail(self, start_date: str = None, end_date: str = None) -> List[Dict[str, Any]]:
        """
        Get audit trail entries (for compliance/debugging).

        Args:
            start_date: Start date (ISO format)
            end_date: End date (ISO format)

        Returns:
            List of audit entries
        """
        return self.logger_skill.get_logs(start_date=start_date, end_date=end_date)

    # ========== ARCHITECTURE & GIT ==========

    def audit_architecture(self) -> Dict[str, Any]:
        """
        Audit system architecture against 8-pillar framework.

        Reviews:
        - Architecture discipline & traceability
        - Build quality in (type hints, linting)
        - Verification & validation (tests, coverage)
        - Continuous integration & safe delivery
        - Root-cause driven improvement
        - Security & privacy by design
        - Observability & telemetry
        - Maintainability & sustainable pace

        Returns:
            Architecture audit results with scores per pillar
        """
        result = self.architect.audit_codebase(
            repo_path=".",
            framework="8_pillar"
        )

        self.logger_skill.log({
            "event": "architecture_audited",
            "overall_score": result.get("overall_score"),
        })

        return result

    def create_worktree_for_feature(self, feature_name: str, base_branch: str = "main") -> Dict[str, Any]:
        """
        Create git worktree for feature development.

        Args:
            feature_name: Feature branch name (e.g., "signal-optimization")
            base_branch: Base branch to create from

        Returns:
            Worktree creation result
        """
        result = self.git.create_worktree(
            name=feature_name,
            branch=f"feature/{feature_name}"
        )

        return result

    # ========== UTILITIES ==========

    def get_debug_summary(self) -> Dict[str, Any]:
        """
        Get summary of all debugging sessions and findings.

        Returns:
            Summary of investigation log, hypotheses, findings
        """
        return {
            "investigation_log": self.debugger.get_investigation_log(),
            "hypotheses": self.debugger.get_hypotheses(),
            "audit_trail": self.get_audit_trail(),
        }

    def get_performance_summary(self) -> Dict[str, Any]:
        """
        Get performance metrics summary.

        Returns:
            All profiling results with key metrics
        """
        return {
            "profiles": self.profiler.get_profiles(),
            "critical_paths": self._identify_critical_paths(),
        }

    def _identify_critical_paths(self) -> Dict[str, Any]:
        """Identify performance-critical execution paths."""
        profiles = self.profiler.get_profiles()
        critical = {}

        for name, profile in profiles.items():
            if "order_execution" in name and profile.get("p95", 10000) > 2000:
                critical[name] = f"⚠️ VIOLATES NFR-002 (<2s): {profile.get('p95')}ms"
            if "signal_generation" in name and profile.get("p95", 500) > 500:
                critical[name] = f"⚠️ VIOLATES NFR-001 (<500ms): {profile.get('p95')}ms"

        return critical


# Global instance for easy access
skills = None

def init_skills(log_dir: str = "logs", dashboard_url: str = "http://localhost:8000") -> CryptoSkillsManager:
    """
    Initialize global skills manager.

    Args:
        log_dir: Directory for logs
        dashboard_url: Dashboard URL

    Returns:
        Initialized CryptoSkillsManager
    """
    global skills
    skills = CryptoSkillsManager(log_dir=log_dir, dashboard_url=dashboard_url)
    return skills


# Auto-initialize if skills are available
if SKILLS_AVAILABLE:
    try:
        skills = CryptoSkillsManager()
        logger.info("Global skills instance initialized")
    except Exception as e:
        logger.warning(f"Failed to initialize global skills: {e}")
        skills = None
