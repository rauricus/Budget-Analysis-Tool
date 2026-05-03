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
from transaction_overrides import load_overrides_if_present


def _resolve_run_directory(arg: str) -> Path:
    """Resolve run directory from CLI argument.

    Supports either a direct path (e.g. "data/example") or shorthand
    folder names under data/ (e.g. "example" -> "data/example").
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
        python categorize_transactions.py <run_dir> [--debug] [--use-input-category-fallback] [--ignore-unknown-overrides]

    Example:
        python categorize_transactions.py example --debug
    """
    argv = argv if argv is not None else sys.argv[1:]
    debug = False
    use_input_category_fallback = False
    ignore_unknown_overrides = False
    if "--debug" in argv:
        debug = True
        argv = [arg for arg in argv if arg != "--debug"]
    if "--use-input-category-fallback" in argv:
        use_input_category_fallback = True
        argv = [arg for arg in argv if arg != "--use-input-category-fallback"]
    if "--ignore-unknown-overrides" in argv:
        ignore_unknown_overrides = True
        argv = [arg for arg in argv if arg != "--ignore-unknown-overrides"]

    if len(argv) != 1:
        print(
            "Usage: python categorize_transactions.py <run_dir> [--debug] [--use-input-category-fallback] [--ignore-unknown-overrides]"
        )
        print("Example: python categorize_transactions.py example --debug")
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

    # Resolve rules: read "base" field from dataset's rules.json
    rules_file = run_dir / "rules.json"
    if not rules_file.exists():
        print(f"❌ Rules file not found: {rules_file}")
        return 1

    with open(rules_file, "r", encoding="utf-8") as f:
        rules_data = json.load(f)

    base_name = rules_data.get("base")
    transaction_overrides_file = run_dir / "transaction_overrides.json"
    if base_name:
        base_rules_path = str(Path("data") / base_name / "rules.json")
        overlay_path: Optional[str] = str(rules_file)
        base_transaction_overrides_file = Path("data") / base_name / "transaction_overrides.json"
        if base_transaction_overrides_file.exists():
            print(
                f"❌ transaction_overrides.json is not allowed in a base dataset ('{base_name}'). "
                f"Place transaction overrides in the top-level dataset only."
            )
            return 1
    else:
        base_rules_path = str(rules_file)
        overlay_path = None
    
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

    # 2. Load rules (plus optional overlay) and transaction overrides
    print("\n2. Loading Rules...")
    try:
        engine = RuleEngine(base_rules_path, overlay_path=overlay_path, debug=debug)
    except FileNotFoundError as e:
        print(f"❌ {e}")
        return 1

    transaction_overrides_path: Optional[str] = (
        str(transaction_overrides_file) if transaction_overrides_file.exists() else None
    )
    try:
        transaction_overrides = load_overrides_if_present(transaction_overrides_path)
    except (ValueError, json.JSONDecodeError) as e:
        print(f"❌ Failed to load transaction_overrides.json: {e}")
        return 1
    if transaction_overrides:
        print(f"   Loaded transaction overrides: {transaction_overrides.count} entry(ies)")

    total_txns = 0
    total_categorized = 0
    all_months: set[str] = set()
    id_registry = TransactionIdRegistry(registry_path)

    # 3. Load all transactions and assign IDs first (needed for strict transaction override validation)
    print("\n3. Loading Files and Assigning IDs...")
    preloaded_transactions: dict[Path, list] = {}
    known_transaction_ids: set[str] = set()
    for input_csv in input_files:
        print(f"\n   -> {input_csv.name}")
        try:
            transactions = ImportHandler.load_csv(str(input_csv), debug=debug)
        except FileNotFoundError as e:
            print(f"❌ {e}")
            return 1

        id_registry.assign_batch(transactions)
        preloaded_transactions[input_csv] = transactions
        known_transaction_ids.update(t.transaction_id for t in transactions)

    if transaction_overrides:
        unknown_override_ids = transaction_overrides.unknown_ids(known_transaction_ids)
        if unknown_override_ids:
            prefix = "⚠️" if ignore_unknown_overrides else "❌"
            print(f"\n{prefix} transaction_overrides.json contains unknown transaction ID(s):")
            for tx_id in unknown_override_ids[:20]:
                print(f"   - {tx_id}")
            if len(unknown_override_ids) > 20:
                print(f"   ... and {len(unknown_override_ids) - 20} more")
            if ignore_unknown_overrides:
                print("\n   Continuing because --ignore-unknown-overrides is set.")
                print("   Unknown override IDs will be ignored for this run.")
            else:
                print("\n   If transaction IDs were regenerated, use the remap helper to find the new IDs:")
                print(f"   uv run python suggest_override_ids.py {run_dir}")
                print("\n   To continue anyway, rerun with --ignore-unknown-overrides.")
                return 1

    # 4. Categorize and export each preloaded input file
    print("\n4. Categorizing and Exporting...")
    if use_input_category_fallback:
        print("   Input category fallback is enabled for uncategorized transactions.")
    for input_csv in input_files:
        print(f"\n   -> {input_csv.name}")
        transactions = preloaded_transactions[input_csv]

        transactions, matching_rules_map = engine.categorize_batch(transactions)

        if transaction_overrides:
            # Build a lookup from transaction_id → matched rules before applying transaction overrides
            id_to_rules = {
                t.transaction_id: matching_rules_map.get(i)
                for i, t in enumerate(transactions)
            }
            transactions = transaction_overrides.apply(transactions)
            # Rebuild matching_rules_map with new 0-based indices
            matching_rules_map = {
                i: id_to_rules[t.transaction_id]
                for i, t in enumerate(transactions)
                if id_to_rules.get(t.transaction_id) is not None
            }

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
    print(f"\n5. Months metadata saved: {months_path.name} ({len(sorted_months)} month(s))")

    # Summary
    print("\n" + "=" * 60)
    print("Pipeline completed successfully!")
    print(f"Processed files: {len(input_files)}")
    print(f"Total categorized: {total_categorized}/{total_txns}")
    print("=" * 60)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
