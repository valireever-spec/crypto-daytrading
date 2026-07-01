# Skills Integration Guide — Crypto Daytrading

Complete guide for integrating the skills manager into your crypto-daytrading codebase.

---

## 1. Basic Setup

### Step 1: Initialize skills in your app startup

**File: `backend/api.py` or main entry point**

```python
import logging
from backend.skills_integration import init_skills, SKILLS_AVAILABLE

logger = logging.getLogger(__name__)

# Initialize skills manager at startup
try:
    if SKILLS_AVAILABLE:
        skills = init_skills(
            log_dir="logs",
            dashboard_url="http://localhost:8000"
        )
        logger.info("✅ Skills manager initialized")
    else:
        skills = None
        logger.warning("⚠️  Skills not available")
except Exception as e:
    skills = None
    logger.error(f"Failed to initialize skills: {e}")
```

### Step 2: Create global skills context

**File: `backend/core/skills_context.py`** (new file)

```python
"""Global skills context for accessing skills from anywhere."""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Global skills instance
_skills = None

def set_skills(skills):
    """Set global skills instance."""
    global _skills
    _skills = skills
    logger.info("Global skills context initialized")

def get_skills():
    """Get global skills instance."""
    global _skills
    return _skills
```

Update your startup to use it:

```python
from backend.core.skills_context import set_skills

skills = init_skills(...)
set_skills(skills)  # Make globally accessible
```

---

## 2. Integration by Module

### Example 1: Trade Execution — Debug & Profile

**File: `backend/execution/trade_executor.py`**

```python
import logging
import time
from backend.core.skills_context import get_skills

logger = logging.getLogger(__name__)

class TradeExecutor:
    """Execute trades with debugging and performance monitoring."""
    
    def execute_order(self, symbol: str, side: str, quantity: float) -> dict:
        """
        Execute order with NFR-002 compliance (<2s execution).
        
        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            side: "BUY" or "SELL"
            quantity: Order quantity
            
        Returns:
            Order result with execution details
        """
        
        skills = get_skills()
        start_time = time.time()
        
        try:
            # Profile execution latency (NFR-002: <2s)
            if skills:
                profile = skills.profile_order_execution(symbol)
            
            # Execute order to Binance
            logger.info(f"Executing {side} {quantity} {symbol}")
            order = self.binance_client.place_market_order(symbol, side, quantity)
            
            execution_time = (time.time() - start_time) * 1000
            
            # Check NFR-002 compliance
            if execution_time > 2000:
                logger.warning(f"⚠️  VIOLATES NFR-002: {execution_time}ms > 2000ms")
            
            # Log successful trade
            if skills:
                skills.log_trade_executed({
                    "symbol": symbol,
                    "side": side,
                    "quantity": quantity,
                    "order_id": order["orderId"],
                    "status": "FILLED",
                    "execution_time_ms": execution_time,
                    "passes_nfr002": execution_time < 2000,
                })
            
            logger.info(f"✅ Order filled: {order['orderId']} in {execution_time:.0f}ms")
            return order
            
        except Exception as e:
            # DEBUG: Use skills to understand failure
            if skills:
                findings = skills.debug_trade_failure(
                    symbol=symbol,
                    error_log="logs/execution.log",
                    side=side,
                    quantity=quantity
                )
                logger.error(f"Trade failure: {findings['recommendation']}")
                logger.error(f"Confidence: {findings['confidence']:.0%}")
                
                # Log failed trade
                skills.log_trade_executed({
                    "symbol": symbol,
                    "side": side,
                    "quantity": quantity,
                    "status": "FAILED",
                    "error": findings["recommendation"],
                    "root_cause": findings.get("status"),
                })
            
            raise
```

### Example 2: Signal Generation — Profile & Debug

**File: `backend/strategies/signal_generator.py`**

```python
import logging
import time
from backend.core.skills_context import get_skills

logger = logging.getLogger(__name__)

class SignalGenerator:
    """Generate trading signals with NFR-001 compliance (<500ms)."""
    
    def generate_signal(self, symbol: str, timeframe: str = "1h") -> dict:
        """
        Generate trading signal.
        
        NFR-001: Signal generation must complete in <500ms per symbol
        
        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            timeframe: Candle timeframe (1m, 5m, 1h, 4h, 1d)
            
        Returns:
            Signal dict with direction, confidence, indicators
        """
        
        skills = get_skills()
        start_time = time.time()
        
        try:
            # Profile signal generation (NFR-001: <500ms)
            if skills:
                profile = skills.profile_signal_generation(
                    symbol=symbol,
                    candle_count=1000
                )
            
            # Generate signal
            logger.debug(f"Generating signal for {symbol} {timeframe}")
            
            # Fetch candles
            candles = self.binance_api.get_klines(symbol, timeframe, limit=1000)
            
            # Calculate indicators
            rsi = self._calculate_rsi(candles)
            macd = self._calculate_macd(candles)
            bb = self._calculate_bollinger_bands(candles)
            
            # Combine signals
            signal = self._combine_signals({
                "rsi": rsi,
                "macd": macd,
                "bb": bb,
            })
            
            generation_time = (time.time() - start_time) * 1000
            
            # Check NFR-001 compliance
            if generation_time > 500:
                logger.warning(f"⚠️  VIOLATES NFR-001: {generation_time}ms > 500ms")
            
            # Log signal
            if skills:
                skills.log_signal_generated({
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "signal": signal["direction"],
                    "confidence": signal["confidence"],
                    "indicators": {
                        "rsi": rsi,
                        "macd": macd,
                        "bb": bb,
                    },
                    "generation_time_ms": generation_time,
                    "passes_nfr001": generation_time < 500,
                })
            
            logger.info(f"Signal {signal['direction']} for {symbol} (conf: {signal['confidence']:.0%})")
            return signal
            
        except Exception as e:
            # DEBUG: Use skills to understand failure
            if skills:
                findings = skills.debug_signal_generation(
                    symbol=symbol,
                    timeframe=timeframe,
                    error_log="logs/signals.log"
                )
                logger.error(f"Signal failure: {findings['recommendation']}")
                
                skills.log_signal_generated({
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "signal": "UNKNOWN",
                    "status": "FAILED",
                    "error": findings["recommendation"],
                })
            
            raise
    
    def _calculate_rsi(self, candles):
        """Calculate RSI indicator."""
        # Your RSI implementation
        pass
    
    def _calculate_macd(self, candles):
        """Calculate MACD indicator."""
        # Your MACD implementation
        pass
    
    def _calculate_bollinger_bands(self, candles):
        """Calculate Bollinger Bands."""
        # Your BB implementation
        pass
    
    def _combine_signals(self, indicators):
        """Combine multiple indicators into final signal."""
        # Your signal combination logic
        pass
```

### Example 3: HA Failover — Test Resilience

**File: `backend/failover/failover_manager.py`**

```python
import logging
from backend.core.skills_context import get_skills

logger = logging.getLogger(__name__)

class FailoverManager:
    """Manage dual-machine HA failover."""
    
    def test_failover_resilience(self, duration_seconds: int = 60):
        """
        Test HA failover under chaos conditions.
        
        Tests:
        - Primary machine heartbeat failure
        - Network partition between machines
        - Database connection loss
        - Secondary machine takeover
        
        Args:
            duration_seconds: How long to run test
            
        Returns:
            Test results with recovery metrics
        """
        
        skills = get_skills()
        if not skills:
            logger.warning("Skills not initialized - skipping failover test")
            return None
        
        logger.info(f"🔥 Starting chaos failover test ({duration_seconds}s)...")
        
        result = skills.chaos_test_failover(duration_seconds=duration_seconds)
        
        logger.info(f"Chaos test results:")
        logger.info(f"  Passed: {result['passed']}")
        logger.info(f"  Recovery time: {result['recovery_time_seconds']}s")
        logger.info(f"  Trades lost: {result.get('trades_lost', 0)}")
        
        # Assertions for production
        assert result["passed"], "Failover test failed"
        assert result["recovery_time_seconds"] <= 60, f"Recovery too slow: {result['recovery_time_seconds']}s"
        assert result.get("trades_lost", 0) <= 1, f"Too many trades lost: {result.get('trades_lost', 0)}"
        
        return result
```

### Example 4: Dashboard Testing

**File: `backend/api/dashboard.py`** (or Flask/FastAPI route)

```python
import logging
from backend.core.skills_context import get_skills

logger = logging.getLogger(__name__)

def test_dashboard():
    """Test dashboard UI is functioning."""
    
    skills = get_skills()
    if not skills:
        logger.warning("Skills not available")
        return {"status": "SKIPPED", "reason": "Skills not initialized"}
    
    logger.info("Testing dashboard health...")
    result = skills.test_dashboard_health()
    
    if result["passed"]:
        logger.info(f"✅ Dashboard healthy (confidence: {result['confidence']:.0%})")
    else:
        logger.error(f"❌ Dashboard test failed")
        for assertion in result.get("assertions", []):
            logger.error(f"  - {assertion['type']}: {assertion['expected']}")
    
    return result

def test_dashboard_trade_flow():
    """Test end-to-end trade flow in dashboard."""
    
    skills = get_skills()
    if not skills:
        return {"status": "SKIPPED"}
    
    logger.info("Testing dashboard trade flow...")
    result = skills.test_dashboard_trade_flow()
    
    if result["passed"]:
        logger.info(f"✅ Trade flow works")
    else:
        logger.error(f"❌ Trade flow test failed")
    
    return result
```

### Example 5: Tests with Skills

**File: `tests/test_trade_execution.py`**

```python
import pytest
import logging
from backend.core.skills_context import get_skills, set_skills
from backend.skills_integration import init_skills
from backend.execution.trade_executor import TradeExecutor

logger = logging.getLogger(__name__)

class TestTradeExecution:
    """Test trade execution with skills integration."""
    
    @pytest.fixture(scope="session", autouse=True)
    def setup_skills(self):
        """Initialize skills once for all tests."""
        skills = init_skills()
        set_skills(skills)
        yield
        # Cleanup if needed
    
    def test_order_execution_latency_nfr002(self):
        """Test order execution latency (NFR-002: <2s)."""
        skills = get_skills()
        if not skills:
            pytest.skip("Skills not initialized")
        
        executor = TradeExecutor()
        profile = skills.profile_order_execution("BTCUSDT")
        
        # NFR-002: Order execution < 2 seconds
        assert profile["p95"] < 2000, \
            f"Order execution too slow: {profile['p95']}ms > 2000ms (violates NFR-002)"
    
    def test_signal_generation_latency_nfr001(self):
        """Test signal generation latency (NFR-001: <500ms)."""
        skills = get_skills()
        if not skills:
            pytest.skip("Skills not initialized")
        
        profile = skills.profile_signal_generation("BTCUSDT", candle_count=1000)
        
        # NFR-001: Signal generation < 500ms
        assert profile["p95"] < 500, \
            f"Signal generation too slow: {profile['p95']}ms > 500ms (violates NFR-001)"
    
    def test_dashboard_health(self):
        """Test dashboard is healthy."""
        skills = get_skills()
        if not skills:
            pytest.skip("Skills not initialized")
        
        result = skills.test_dashboard_health()
        assert result["passed"], f"Dashboard test failed: {result.get('error')}"
    
    def test_signal_quality(self):
        """Test signal generation quality."""
        skills = get_skills()
        if not skills:
            pytest.skip("Skills not initialized")
        
        result = skills.test_signal_quality(
            backtest_files=["backtests/signals_latest.log"],
            min_coverage=0.85,
            min_win_rate=0.55
        )
        
        assert result["quality_score"] >= 0.75, \
            f"Signal quality too low: {result['quality_score']:.0%}"
    
    def test_ha_failover_resilience(self):
        """Test HA failover resilience."""
        skills = get_skills()
        if not skills:
            pytest.skip("Skills not initialized")
        
        result = skills.chaos_test_failover(duration_seconds=60)
        
        assert result["passed"], "Failover test failed"
        assert result["recovery_time_seconds"] <= 60, \
            f"Recovery too slow: {result['recovery_time_seconds']}s"
```

### Example 6: Architecture Auditing

**File: `scripts/audit_architecture.py`** (new file)

```python
"""Audit system architecture before Phase 2 (live trading)."""

import logging
from backend.core.skills_context import set_skills
from backend.skills_integration import init_skills

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_pre_launch_audit():
    """Run comprehensive pre-launch audit."""
    
    logger.info("=" * 60)
    logger.info("🔍 PRE-LAUNCH ARCHITECTURE AUDIT")
    logger.info("=" * 60)
    
    # Initialize skills
    skills = init_skills()
    set_skills(skills)
    
    checks = {
        "Dashboard Health": skills.test_dashboard_health(),
        "Signal Quality": skills.test_signal_quality(["backtests/latest.log"]),
        "Order Execution (NFR-002)": skills.profile_order_execution("BTCUSDT"),
        "Signal Generation (NFR-001)": skills.profile_signal_generation("BTCUSDT"),
        "Exchange Integration": skills.test_exchange_integration(),
        "HA Failover": skills.chaos_test_failover(duration_seconds=60),
        "Architecture": skills.audit_architecture(),
    }
    
    passed = 0
    failed = 0
    
    for check_name, result in checks.items():
        if isinstance(result, dict):
            if result.get("passed") or result.get("verified"):
                logger.info(f"✅ {check_name}: PASSED")
                passed += 1
            else:
                logger.error(f"❌ {check_name}: FAILED")
                logger.error(f"   {result.get('error', result.get('recommendation'))}")
                failed += 1
        else:
            logger.info(f"ℹ️  {check_name}: {result}")
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("📊 AUDIT SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Passed: {passed}")
    logger.info(f"Failed: {failed}")
    
    if failed == 0:
        logger.info("✅ ALL CHECKS PASSED - READY FOR PHASE 2 (LIVE TRADING)")
        return 0
    else:
        logger.error("❌ SOME CHECKS FAILED - FIX BEFORE GOING LIVE")
        return 1

if __name__ == "__main__":
    exit_code = run_pre_launch_audit()
    exit(exit_code)
```

Run before Phase 2:

```bash
python scripts/audit_architecture.py
```

---

## 3. Integration Checklist

- [ ] ✅ Initialize skills in startup code
- [ ] ✅ Create `backend/core/skills_context.py`
- [ ] ✅ Add debugging to trade executor
- [ ] ✅ Add profiling to signal generator
- [ ] ✅ Add resilience testing to failover manager
- [ ] ✅ Create dashboard test endpoints
- [ ] ✅ Create comprehensive tests
- [ ] ✅ Create pre-launch audit script
- [ ] ✅ Run audit before Phase 2

---

## 4. Common Usage Patterns

### Pattern 1: Debug on Failure

```python
try:
    order = execute_order(symbol, side, quantity)
except Exception:
    skills = get_skills()
    if skills:
        findings = skills.debug_trade_failure(symbol, "logs/exec.log", side, quantity)
        print(f"Root cause: {findings['recommendation']}")
    raise
```

### Pattern 2: Monitor Latency

```python
profile = get_skills().profile_order_execution(symbol)
if profile["p95"] > 2000:
    logger.warning(f"⚠️  Latency: {profile['p95']}ms (exceeds NFR-002)")
```

### Pattern 3: Log Events

```python
skills = get_skills()
if skills:
    skills.log_trade_executed({
        "symbol": "BTCUSDT",
        "side": "BUY",
        "quantity": 0.1,
        "status": "FILLED",
    })
```

### Pattern 4: Test Before Going Live

```python
result = get_skills().chaos_test_failover(duration_seconds=120)
assert result["passed"], "Failover test failed"
assert result["recovery_time_seconds"] <= 60, "Recovery too slow"
logger.info("✅ System ready for Phase 2")
```

---

## 5. Troubleshooting

### Skills not initialized?

```python
from backend.core.skills_context import get_skills

skills = get_skills()
if skills is None:
    logger.warning("Skills not initialized")
```

### NFR-002 violation?

```bash
# Check order execution latency
python scripts/check_latency.py BTCUSDT

# Profile multiple executions
# If p95 > 2000ms, need to optimize:
# - Reduce Binance API calls
# - Use batch orders
# - Check network latency
```

### NFR-001 violation?

```bash
# Check signal generation latency
# If p95 > 500ms, need to optimize:
# - Reduce candle count
# - Pre-compute indicators
# - Use faster libraries (talib vs pandas)
```

---

## 6. Next Steps

1. ✅ Implement initialization
2. ✅ Add debugging to core modules
3. ✅ Run pre-launch audit
4. ✅ Fix any violations
5. ✅ Go live with Phase 1 (paper trading)
6. ✅ Monitor with daily checks

**See SKILLS_QUICKSTART.md for high-level overview.**
