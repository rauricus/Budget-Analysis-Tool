#!/usr/bin/env python3
"""
Budget-Tool Pipeline
Load CSV → categorize → save output
"""

import json
import sys
from pathlib import Path
from typing import Optional, Sequence

sys.path.insert(0, str(Path(__file__).parent / "src"))

from import_handler import ImportHandler
from rule_engine import RuleEngine
from export_handler import ExportHandler
from transaction_id_registry import TransactionIdRegistry


def _resolve_run_directory(arg: str) -> Path:
    """Resolve run directory from CLI argument.

    Supports either a direct path (e.g. "data/reference") or shorthand
    folder names under data/ (e.g. "reference" -> "data/reference").
    """
    direct = Path(arg)
    if direct.exists() and direct.is_dir():
        return direct

    under_data = Path("data") / arg
    if under_data.exists() and under_data.is_dir():
        return under_data

    raise FileNotFoundError(
        f"Run directory not found: '{arg}' (also checked '{under_data}')"
    )


def main(argv: Optional[Sequence[str]] = None):
    """Main pipeline.

    Usage:
        python categorize_transactions.py <run_dir> [--debug] [--use-input-category-fallback]

    Example:
        python categorize_transactions.py reference --debug
    """
    argv = argv if argv is not None else sys.argv[1:]
    debug = False
    use_input_category_fallback = False
    if "--debug" in argv:
        debug = True
        argv = [arg for arg in argv if arg != "--debug"]
    if "--use-input-category-fallback" in argv:
        use_input_category_fallback = True
        argv = [arg for arg in argv if arg != "--use-input-category-fallback"]

    if len(argv) != 1:
        print("Usage: python categorize_transactions.py <run_dir> [--debug] [--use-input-category-fallback]")
        print("Example: python categorize_transactions.py reference --debug")
        return 2

    try:
        run_dir = _resolve_run_directory(argv[0])
    except FileNotFoundError as e:
        print(f"❌ {e}")
        return 1

    input_dir = run_dir / "input"
    output_dir = run_dir / "output"
    metadata_dir = run_dir / "metadata"
    registry_path = metadata_dir / "transaction_id_registry.json"

    # Base rules are always data/reference/rules.json
    base_rules = Path("data/reference/rules.json")

    # Optional overlay: {run_dir}/rules.json, but only when run_dir is not data/reference itself
    overlay_file = run_dir / "rules.json"
    overlay_path = (
        str(overlay_file)
        if overlay_file.exists() and overlay_file.resolve() != base_rules.resolve()
        else None
    )
    
    print("=" * 60)
    print("  Budget Tool - Categorization Pipeline")
    print("=" * 60)
    
    # 1. Validate input directory and files
    print("\n1. Discovering Input Files...")
    if not input_dir.exists() or not input_dir.is_dir():
        print(f"❌ Input directory not found: {input_dir}")
        return 1

    input_files = sorted(input_dir.glob("*.csv"))
    if not input_files:
        print(f"❌ No CSV files found in: {input_dir}")
        return 1
    print(f"   Found {len(input_files)} input file(s) in {input_dir}")

    # 2. Load rules
    print("\n2. Loading Rules...")
    try:
        engine = RuleEngine(str(base_rules), overlay_path=overlay_path, debug=debug)
    except FileNotFoundError as e:
        print(f"❌ {e}")
        return 1

    total_txns = 0
    total_categorized = 0
    all_months: set[str] = set()
    id_registry = TransactionIdRegistry(registry_path)

    # 3/4. Process each input file
    print("\n3. Processing Files...")
    if use_input_category_fallback:
        print("   Input category fallback is enabled for uncategorized transactions.")
    for input_csv in input_files:
        print(f"\n   -> {input_csv.name}")

        try:
            transactions = ImportHandler.load_csv(str(input_csv), debug=debug)
        except FileNotFoundError as e:
            print(f"❌ {e}")
            return 1

        id_registry.assign_batch(transactions)

        transactions, matching_rules_map = engine.categorize_batch(transactions)

        for t in transactions:
            all_months.add(t.date.strftime("%Y-%m"))

        categorized_count = sum(1 for t in transactions if t.auto_transaction_category)
        uncategorized_count = sum(1 for t in transactions if not t.auto_transaction_category)

        print(f"      Categorized: {categorized_count}/{len(transactions)}")
        print(f"      Uncategorized: {uncategorized_count}/{len(transactions)}")

        output_csv = output_dir / f"{input_csv.stem}.categorized.csv"
        ExportHandler.export_csv(
            transactions,
            str(output_csv),
            matching_rules_map,
            use_input_category_fallback=use_input_category_fallback,
        )

        total_txns += len(transactions)
        total_categorized += categorized_count

    id_registry.save()

    # Write months metadata
    output_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)
    months_path = metadata_dir / "months.json"
    sorted_months = sorted(all_months)
    with open(months_path, "w", encoding="utf-8") as f:
        json.dump(sorted_months, f, indent=2)
    print(f"\n4. Months metadata saved: {months_path.name} ({len(sorted_months)} month(s))")

    # Summary
    print("\n" + "=" * 60)
    print("Pipeline completed successfully!")
    print(f"Processed files: {len(input_files)}")
    print(f"Total categorized: {total_categorized}/{total_txns}")
    print("=" * 60)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
