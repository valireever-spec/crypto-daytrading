#!/bin/bash
# Trading Algorithm Validator - Quick Invocation Script

cd "$(dirname "$0")"

echo "Running Trading Algorithm Validator..."
echo "======================================="

python3 << 'EOF'
import sys
sys.path.insert(0, '../skill-creator/skills')
from trading_algorithm_validator_v2.core import TradingAlgorithmValidator

# Initialize validator
validator = TradingAlgorithmValidator('.')

# Run validation
print("\n🔍 Analyzing trading algorithm...\n")
report = validator.validate(generate_tests=True, verbose=True)

# Print verdict
print("\n" + "="*70)
print(f"VERDICT: {report['go_no_go_verdict']}")
print(f"Confidence: {report.get('confidence', 0)*100:.0f}%")
print("="*70 + "\n")

# Save outputs
validator.save_report("TRADING_VALIDATION_REPORT.md")
validator.save_json("trading_validation_results.json")
validator.save_test_suite("tests/test_trading_validation.py")

print("✅ Reports saved:")
print("   - TRADING_VALIDATION_REPORT.md")
print("   - trading_validation_results.json")
print("   - tests/test_trading_validation.py")
print("\n📋 To view the report, run:")
print("   cat TRADING_VALIDATION_REPORT.md")
print("\n🧪 To run the tests, run:")
print("   pytest tests/test_trading_validation.py -v")
EOF
