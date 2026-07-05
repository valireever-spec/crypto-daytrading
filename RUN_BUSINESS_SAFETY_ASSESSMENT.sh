#!/bin/bash
# Business Safety Assessment - Quick Invocation Script

cd "$(dirname "$0")"

echo "Running Business Safety Assessment..."
echo "======================================"
echo ""

python3 << 'EOF'
import sys
sys.path.insert(0, '../skill-library')

from business_safety_assessor_v1 import BusinessSafetyAssessor

# Initialize assessor
assessor = BusinessSafetyAssessor('.')

# Print summary
print("🔍 BUSINESS SAFETY ASSESSMENT\n")
assessor.print_summary()

# Save detailed reports
print("\n📋 Saving detailed reports...\n")
assessor.save_report("BUSINESS_SAFETY_ASSESSMENT.json")
print("✅ JSON report saved: BUSINESS_SAFETY_ASSESSMENT.json")

# Generate markdown
verdicts = assessor.generate_verdict()
lines = [
    "# Business Safety Assessment\n",
    "## Verdicts\n",
]

for v in verdicts:
    verdict_icon = "✅" if v.verdict == "GO" else "⚠️" if v.verdict == "CONDITIONAL" else "❌"
    lines.append(f"**{verdict_icon} {v.capital_level}**: {v.verdict}\n")
    lines.append(f"- Confidence: {v.confidence:.0f}%\n")
    lines.append(f"- Max Loss: ${abs(v.max_expected_loss):.2f}\n")
    lines.append(f"- Timeline: {v.timeline_to_safe_deployment}\n")
    lines.append("\n")

if assessor.blockers:
    lines.append("## Critical Blockers\n\n")
    for i, blocker in enumerate(assessor.blockers, 1):
        lines.append(f"{i}. {blocker}\n")
    lines.append("\n")

with open("BUSINESS_SAFETY_ASSESSMENT.md", "w") as f:
    f.writelines(lines)

print("✅ Markdown report saved: BUSINESS_SAFETY_ASSESSMENT.md\n")

print("📊 Analysis complete!")
print("📋 View reports with:")
print("   cat BUSINESS_SAFETY_ASSESSMENT.md")
print("   cat BUSINESS_SAFETY_ASSESSMENT.json | jq .")
EOF

echo ""
echo "✅ Done!"
echo ""
echo "📋 To view the report:"
echo "   cat BUSINESS_SAFETY_ASSESSMENT.md"
echo ""
echo "🔗 To integrate with your workflow:"
echo "   python3 -c 'from skill-library.business_safety_assessor_v1 import BusinessSafetyAssessor; \\'"
echo "       assessor = BusinessSafetyAssessor(\".\"); assessor.print_summary()'"
