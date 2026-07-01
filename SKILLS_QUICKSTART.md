# Skills Integration Quick Start — Crypto Daytrading

## Overview

The `backend/skills_integration.py` module provides easy access to 8 specialized skills for debugging, testing, and monitoring your crypto trading system.

**Available Skills:**
- ✅ Systematic Debugging (root-cause analysis)
- ✅ Playwright Testing (dashboard UI testing)
- ✅ Performance Profiler (latency monitoring)
- ✅ Comprehensive Testing Framework
- ✅ Chaos Testing Framework (HA/failover)
- ✅ Structured Logger (audit trails)
- ✅ Architecture Auditor
- ✅ Git Worktrees (feature branches)

---

## Quick Start

### 1. Import the Skills Manager

```python
from backend.skills_integration import skills

# Or initialize manually
from backend.skills_integration import init_skills
skills = init_skills(log_dir="logs", dashboard_url="http://localhost:8000")
```

### 2. Debug Trade Failures

When a trade fails, use systematic debugging:

```python
# In your trade execution code
try:
    order = binance_client.place_order(symbol="BTCUSDT", side="BUY", quantity=0.1)
except Exception as e:
    # Debug the failure
    findings = skills.debug_trade_failure(
        symbol="BTCUSDT",
        error_log="logs/execution.log",
        side="BUY",
        quantity=0.1
    )
    print(f"Status: {findings['status']}")
    print(f"Root cause: {findings['recommendation']}")
    print(f"Confidence: {findings['confidence']:.0%}")
```

**Output Example:**
```
Status: ROOT_CAUSE_FOUND
Root cause: Binance API returned 429 (rate limited). Wait 60s before retry.
Confidence: 95%
```

### 3. Monitor Order Execution Latency (NFR-002: <2s)

```python
# Profile order execution to ensure it's <2 seconds
profile = skills.profile_order_execution(symbol="BTCUSDT")

if profile["p95"] > 2000:
    print(f"⚠️  VIOLATES NFR-002: {profile['p95']}ms > 2000ms")
else:
    print(f"✅ Passes NFR-002: {profile['p95']}ms < 2000ms")
```

### 4. Test Dashboard

Before going live, ensure dashboard works:

```python
# Test dashboard health
test_result = skills.test_dashboard_health()

if test_result["passed"]:
    print(f"✅ Dashboard healthy (confidence: {test_result['confidence']:.0%})")
else:
    print(f"❌ Dashboard test failed")
    for step in test_result["assertions"]:
        print(f"  - {step['type']}: {step['expected']}")
```

### 5. Chaos Test HA Failover

Before Phase 2 (live trading), test dual-machine failover:

```python
# Test failover resilience
result = skills.chaos_test_failover(duration_seconds=60)

print(f"Failover test: {'PASSED' if result['passed'] else 'FAILED'}")
print(f"Recovery time: {result['recovery_time_seconds']}s")
print(f"Trades lost during failover: {result.get('trades_lost', 0)}")
```

### 6. Test Signal Quality

Validate signal generation quality:

```python
# Test signal quality on backtest files
result = skills.test_signal_quality(
    backtest_files=["backtests/signals_2024_06.log"],
    min_coverage=0.85,
    min_win_rate=0.55
)

print(f"Signal quality: {result['quality_score']:.1%}")
print(f"Code coverage: {result['coverage']:.1%}")
```

### 7. Profile Signal Generation (NFR-001: <500ms)

```python
# Ensure signal generation completes in <500ms
profile = skills.profile_signal_generation(symbol="BTCUSDT", candle_count=1000)

if profile["p95"] > 500:
    print(f"⚠️  VIOLATES NFR-001: {profile['p95']}ms > 500ms")
else:
    print(f"✅ Passes NFR-001: {profile['p95']}ms < 500ms")
```

### 8. Audit Architecture

Validate architecture against 8-pillar framework:

```python
# Audit system design
audit = skills.audit_architecture()

print(f"Architecture score: {audit['overall_score']:.0%}")
for pillar, score in audit.get("pillar_scores", {}).items():
    print(f"  {pillar}: {score:.0%}")
```

### 9. Log Events to Audit Trail

Trade execution is logged for compliance:

```python
# Log trade execution
skills.log_trade_executed({
    "symbol": "BTCUSDT",
    "side": "BUY",
    "quantity": 0.1,
    "entry_price": 65000.00,
    "fee": 6.50,
    "status": "FILLED"
})

# Log signal generation
skills.log_signal_generated({
    "symbol": "BTCUSDT",
    "timeframe": "1h",
    "signal": "BUY",
    "confidence": 0.82,
    "indicators": ["RSI > 70", "MACD positive"]
})

# Retrieve audit trail
trail = skills.get_audit_trail()
for entry in trail[-10:]:
    print(f"{entry['timestamp']}: {entry['event']}")
```

---

## Integration in Code

### In Trade Executor

```python
# backend/execution/trade_executor.py
from backend.skills_integration import skills

class TradeExecutor:
    def execute_order(self, symbol, side, quantity):
        # Profile execution latency (NFR-002)
        profile = skills.profile_order_execution(symbol)
        
        try:
            order = self.binance_api.place_order(symbol, side, quantity)
            
            # Log successful trade
            skills.log_trade_executed({
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "status": "FILLED"
            })
            
            return order
        except Exception as e:
            # Debug failure
            findings = skills.debug_trade_failure(symbol, "logs/exec.log", side, quantity)
            skills.log_trade_executed({
                "symbol": symbol,
                "side": side,
                "status": "FAILED",
                "error": findings["recommendation"]
            })
            raise
```

### In Signal Generator

```python
# backend/strategies/signal_generator.py
from backend.skills_integration import skills

class SignalGenerator:
    def generate_signal(self, symbol, timeframe="1h"):
        # Profile signal latency (NFR-001)
        profile = skills.profile_signal_generation(symbol)
        
        # Check if latency is acceptable
        if profile["p95"] > 500:
            logger.warning(f"Signal generation slow: {profile['p95']}ms > 500ms")
        
        # Generate signal
        signal = self._calculate_signal(symbol, timeframe)
        
        # Log signal
        skills.log_signal_generated({
            "symbol": symbol,
            "timeframe": timeframe,
            "signal": signal["direction"],
            "confidence": signal["confidence"]
        })
        
        return signal
```

### In Tests

```python
# tests/test_dashboard.py
from backend.skills_integration import skills

def test_dashboard_health():
    """Ensure dashboard loads and functions correctly."""
    result = skills.test_dashboard_health()
    assert result["passed"], f"Dashboard test failed: {result['error']}"
    assert result["confidence"] >= 0.8, "Confidence too low"

def test_ha_failover():
    """Test dual-machine failover under chaos."""
    result = skills.chaos_test_failover(duration_seconds=60)
    assert result["passed"], "Failover test failed"
    assert result["recovery_time_seconds"] <= 60, "Recovery took too long"

def test_signal_quality():
    """Test signal generation quality."""
    result = skills.test_signal_quality(
        backtest_files=["backtests/signals_2024_06.log"]
    )
    assert result["quality_score"] >= 0.75, "Quality score too low"
```

---

## Common Workflows

### Pre-Launch Checklist

Before deploying Phase 1 (paper trading):

```python
# 1. Test dashboard
print("1. Testing dashboard...")
assert skills.test_dashboard_health()["passed"]

# 2. Validate NFR-001 (signal latency <500ms)
print("2. Testing signal latency...")
profile = skills.profile_signal_generation("BTCUSDT", 1000)
assert profile["p95"] < 500, f"Signal too slow: {profile['p95']}ms"

# 3. Validate NFR-002 (order execution <2s)
print("3. Testing order execution latency...")
profile = skills.profile_order_execution("BTCUSDT")
assert profile["p95"] < 2000, f"Order execution too slow: {profile['p95']}ms"

# 4. Test exchange integration
print("4. Testing Binance integration...")
result = skills.test_exchange_integration()
assert result["passed"]

# 5. Audit architecture
print("5. Auditing architecture...")
audit = skills.audit_architecture()
assert audit["overall_score"] >= 0.70, "Architecture score too low"

print("✅ All pre-launch checks passed!")
```

### Weekly Resilience Monitoring

```python
# Run weekly (e.g., via cron)
def weekly_resilience_check():
    print("🔄 Weekly resilience check...")
    
    # Test failover
    result = skills.chaos_test_failover(duration_seconds=120)
    assert result["passed"], "Failover test failed"
    
    # Test signal quality
    result = skills.test_signal_quality(
        backtest_files=["backtests/signals_recent.log"]
    )
    assert result["quality_score"] >= 0.70, "Signal quality degraded"
    
    # Check architecture
    audit = skills.audit_architecture()
    if audit["overall_score"] < 0.70:
        print(f"⚠️  Architecture score dropped to {audit['overall_score']:.0%}")
    
    print("✅ Weekly check complete")
```

---

## Environment Setup

Add to your `.env` or configuration:

```bash
# Skills configuration
SKILLS_LOG_DIR=logs
DASHBOARD_URL=http://localhost:8000
SKILL_LIBRARY_PATH=../skill-library
```

## Troubleshooting

### "ImportError: No module named 'systematic_debugging_v2'"

**Solution:** Ensure skill-library path is correct:
```python
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "skill-library"))
```

### Skills not initializing at startup

**Solution:** Check that all skills are available:
```python
from backend.skills_integration import SKILLS_AVAILABLE, IMPORT_ERROR

if not SKILLS_AVAILABLE:
    print(f"⚠️  Skills unavailable: {IMPORT_ERROR}")
else:
    print("✅ Skills initialized")
```

---

## Next Steps

1. ✅ Import `skills` in your code
2. ✅ Add debugging to trade execution
3. ✅ Add performance monitoring (NFR-001, NFR-002)
4. ✅ Run pre-launch checklist
5. ✅ Set up chaos testing for failover
6. ✅ Enable audit trail logging

See `README.md` for full architecture details.
