# Trading Algorithm Validator - Quick Start

**Purpose:** Guarantees trading algorithm is tuned for gain before production deployment

## TL;DR - Run This Now

```bash
cd /home/vali/projects/crypto-daytrading

python3 << 'EOF'
import sys
sys.path.insert(0, '../skill-creator/skills')
from trading_algorithm_validator_v2.core import TradingAlgorithmValidator

validator = TradingAlgorithmValidator('.')
report = validator.validate(generate_tests=True, verbose=True)

print(f"\nVERDICT: {report['go_no_go_verdict']}")
print(f"Confidence: {report.get('confidence', 0)*100:.0f}%\n")

validator.save_report('TRADING_VALIDATION_REPORT.md')
validator.save_json('trading_validation_results.json')
validator.save_test_suite('tests/test_trading_validation.py')

print("✅ Reports saved:")
print("  - TRADING_VALIDATION_REPORT.md")
print("  - trading_validation_results.json")
print("  - tests/test_trading_validation.py")
EOF
```

## What It Validates

✅ **4 Critical Bugs Detected**
- Bug #1: No minimum hold time (99% losses)
- Bug #2: BACKUP response validation (0% win rate)
- Bug #3: Position accumulation unbounded (-$5,419 loss)
- Bug #4: Data quality gates too soft (stale data trading)

✅ **Business Goals**
- Win rate >15% (currently 0.88%)
- Average hold time 300-600 seconds
- Single position loss <10% account
- Data staleness <30 seconds

✅ **Risk Controls**
- Position sizing enforced
- Stop loss working
- Profit targets correct
- Data quality gates active

✅ **Automated Test Suite**
- 8+ pytest tests generated
- All business goals tested
- Final go/no-go decision tests

## Output Files

After running, you get:
- `TRADING_VALIDATION_REPORT.md` - Human-readable report with verdict
- `trading_validation_results.json` - Machine-readable results
- `tests/test_trading_validation.py` - Pytest test suite

## Run Generated Tests

```bash
# All tests
pytest tests/test_trading_validation.py -v

# Specific categories
pytest tests/test_trading_validation.py -k "win_rate" -v
pytest tests/test_trading_validation.py -k "hold_time" -v
pytest tests/test_trading_validation.py -k "position" -v
pytest tests/test_trading_validation.py -k "go_no_go" -v

# With coverage
pytest tests/test_trading_validation.py --cov --cov-report=html
```

## Expected Verdict

### ✅ GO = Deploy to Production
- All 4 bugs fixed (0 remaining)
- Win rate ≥15%
- Hold time 300-600s
- Single position loss ≤10%
- Data quality halts on stale
- All risk controls working

### ❌ NO-GO = Needs Fixes
- Specific bugs listed
- Recommendations provided
- Fix timeline estimated
- Re-validate after fixes

## Next Steps After Validation

1. If ✅ GO: Run 48-hour paper trading test, then deploy
2. If ❌ NO-GO: Fix issues listed, re-validate
3. Run generated pytest suite to verify fixes
4. Compare results between runs to track progress

## For More Details

See: https://github.com/anthropics/validator-skills

## Questions?

Check the validator skill documentation at:
`/home/vali/projects/skill-creator/skills/trading-algorithm-validator-v2/USAGE_GUIDE.md`
