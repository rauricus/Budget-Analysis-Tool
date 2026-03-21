#!/usr/bin/env python3
"""
Budget-Tool Pipeline
Load CSV → categorize → save output
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from import_handler import ImportHandler
from rule_engine import RuleEngine
from export_handler import ExportHandler


def main():
    """Main pipeline."""
    
    # Paths
    # Use reference/ for known examples, input/ for new inputs
    input_csv = "data/input/export.202401.csv"
    rules_file = "data/rules.json"
    output_csv = "data/output/export.202401.categorized.csv"
    
    print("=" * 60)
    print("  Budget Tool - Categorization Pipeline")
    print("=" * 60)
    
    # 1. Load CSV
    print("\n1. Loading Transactions...")
    try:
        transactions = ImportHandler.load_csv(input_csv)
    except FileNotFoundError as e:
        print(f"❌ {e}")
        return 1
    
    # 2. Load rules
    print("\n2. Loading Rules...")
    try:
        engine = RuleEngine(rules_file)
    except FileNotFoundError as e:
        print(f"❌ {e}")
        return 1
    
    # 3. Categorize
    print("\n3. Categorizing...")
    transactions, matching_rules_map = engine.categorize_batch(transactions)
    
    # Stats
    categorized_count = sum(1 for t in transactions if t.kategorie_auto)
    uncategorized_count = sum(1 for t in transactions if not t.kategorie_auto)
    
    print(f"   - Categorized: {categorized_count}/{len(transactions)}")
    print(f"   - Uncategorized: {uncategorized_count}/{len(transactions)}")
    
    # 4. Export (new structured format)
    print("\n4. Exporting to structured format...")
    ExportHandler.export_csv(transactions, output_csv, matching_rules_map)
    
    # Summary
    print("\n" + "=" * 60)
    print("Pipeline completed successfully!")
    print("=" * 60)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
