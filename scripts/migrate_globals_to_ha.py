#!/usr/bin/env python3
"""Migrate unprotected globals to HA-safe pattern

Usage:
    python scripts/migrate_globals_to_ha.py --module backend/analytics/signals.py
    python scripts/migrate_globals_to_ha.py --all
    python scripts/migrate_globals_to_ha.py --dry-run
"""

import argparse
import re
import sys
from pathlib import Path

# Mapping of old global names to new getter function names
GLOBALS_MAP = {
    # Trading & Decision Making
    "_signal_generator": "get_signal_generator",
    "_signal_explainer": "get_signal_explainer",
    "_portfolio_monitor": "get_portfolio_monitor",
    "_allocation_manager": "get_allocation_manager",

    # Optimization & Analysis
    "_portfolio_optimizer": "get_portfolio_optimizer",
    "_risk_engine": "get_risk_engine",
    "_portfolio_analyzer": "get_portfolio_analyzer",
    "_rebalancing_engine": "get_rebalancing_engine",

    # Market Data
    "_historical_service": "get_historical_service",
    "_cost_model": "get_cost_model",
    "_volatility_manager": "get_volatility_manager",

    # Risk & Position Management
    "_position_sizer": "get_position_sizer",
    "_risk_monitor": "get_risk_monitor",
    "_regime_detector": "get_regime_detector",

    # Tax & Accounting
    "_tax_calculator": "get_tax_calculator",
    "_attribution_engine": "get_attribution_engine",

    # Recommendations & Advisory
    "_recommendation_tracker": "get_recommendation_tracker",
    "_sector_advisor": "get_sector_advisor",
    "_allocation_solver": "get_allocation_solver",

    # Cleanup & Maintenance
    "_cleanup_manager": "get_cleanup_manager",
    "_learning_engine": "get_learning_engine",
}

# Reverse mapping for generating imports
GETTER_TO_FUNCTION = {v: k for k, v in GLOBALS_MAP.items()}


def migrate_file(filepath: Path, dry_run: bool = False) -> tuple[bool, list[str]]:
    """Migrate a single file to use HA-safe globals.

    Returns:
        (success, changes_made)
    """
    try:
        content = filepath.read_text()
        original = content
        changes = []

        # Step 1: Add import if needed
        needs_import = False
        imported_functions = set()

        for global_name, getter_func in GLOBALS_MAP.items():
            if global_name in content:
                needs_import = True
                imported_functions.add(getter_func)

        if needs_import and imported_functions:
            # Check if import already exists
            if "from backend.core.ha_globals_manager import" not in content:
                import_statement = f"from backend.core.ha_globals_manager import {', '.join(sorted(imported_functions))}\n"
                # Add after other imports
                if "import" in content:
                    # Find last import line
                    lines = content.split('\n')
                    last_import = 0
                    for i, line in enumerate(lines):
                        if line.startswith('import ') or line.startswith('from '):
                            last_import = i
                    lines.insert(last_import + 1, import_statement)
                    content = '\n'.join(lines)
                    changes.append(f"Added import: {import_statement.strip()}")
                else:
                    content = import_statement + content
                    changes.append(f"Added import at top of file")

        # Step 2: Replace global variable definitions
        for global_name, getter_func in GLOBALS_MAP.items():
            # Pattern: "global _var" or "_var = None" or "if _var is None: _var = ..."

            # Remove "global _var" declarations
            pattern = rf"^\s*global\s+{re.escape(global_name)}\s*$"
            new_content = re.sub(pattern, "", content, flags=re.MULTILINE)
            if new_content != content:
                changes.append(f"Removed 'global {global_name}' declaration")
                content = new_content

            # Replace initialization blocks
            # Pattern: if _var is None: _var = SomeClass()
            pattern = rf"if\s+{re.escape(global_name)}\s+is\s+None:\s*\n\s*{re.escape(global_name)}\s*=\s*\w+\([^)]*\)"
            new_content = re.sub(pattern, f"# Replaced with {getter_func}()", content, flags=re.MULTILINE)
            if new_content != content:
                changes.append(f"Removed initialization block for {global_name}")
                content = new_content

            # Replace direct access with getter calls
            # Pattern: return _var or _var.method() etc
            pattern = rf"\b{re.escape(global_name)}\b"
            # Count occurrences
            count = len(re.findall(pattern, content))
            if count > 0:
                new_content = re.sub(pattern, getter_func + "()", content)
                if new_content != content:
                    changes.append(f"Replaced {count} references to {global_name} with {getter_func}()")
                    content = new_content

        # Step 3: Write back if changed and not dry-run
        if content != original:
            if not dry_run:
                filepath.write_text(content)
            return True, changes
        else:
            return False, []

    except Exception as e:
        print(f"❌ Error processing {filepath}: {e}")
        return False, [str(e)]


def main():
    parser = argparse.ArgumentParser(
        description="Migrate unprotected globals to HA-safe pattern"
    )
    parser.add_argument(
        "--module",
        type=str,
        help="Single module to migrate (e.g., backend/analytics/signals.py)"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Migrate all modules with unprotected globals"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without modifying files"
    )

    args = parser.parse_args()

    if not args.module and not args.all:
        parser.print_help()
        return 1

    # Get list of files to migrate
    root = Path(__file__).parent.parent

    if args.module:
        files = [root / args.module]
    elif args.all:
        # Find all Python files in backend/
        files = list(root.glob("backend/**/*.py"))

    print(f"🔧 HA GLOBALS MIGRATION")
    print(f"{'='*80}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'ACTUAL'}")
    print(f"Files to process: {len(files)}")
    print()

    total_changes = 0
    modified_files = 0

    for filepath in files:
        if not filepath.exists():
            print(f"⚠️  {filepath}: Not found")
            continue

        success, changes = migrate_file(filepath, dry_run=args.dry_run)

        if success and changes:
            modified_files += 1
            total_changes += len(changes)
            status = "✅" if not args.dry_run else "ℹ️"
            print(f"{status} {filepath.relative_to(root)}")
            for change in changes:
                print(f"   • {change}")

    print()
    print(f"{'='*80}")
    print(f"Results:")
    print(f"  Files modified: {modified_files}")
    print(f"  Total changes: {total_changes}")
    if args.dry_run:
        print(f"  (DRY RUN - no files were actually modified)")
    print()

    # Show next steps
    if total_changes > 0:
        print("Next steps:")
        print("  1. Run tests: pytest tests/unit -v")
        print("  2. Verify no regressions: pytest tests/integration -v")
        print("  3. Run HA tests: pytest tests/ha/ -v")

    return 0


if __name__ == "__main__":
    sys.exit(main())
