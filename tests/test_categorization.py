#!/usr/bin/env python3
"""Test transaction categorization"""
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from import_handler import ImportHandler
from rule_engine import RuleEngine


def test_categorization():
    """Test that sample transactions are categorized correctly"""
    txns = ImportHandler.load_csv('data/reference/input/export.202503.csv')
    engine = RuleEngine('data/reference/rules.json')
    
    # Test transactions 3 (KKIOSK), 10 (BYRO), 43 (COOP)
    test_indices = [3, 10, 43]
    
    for idx in test_indices:
        txn = txns[idx]
        
        # Should have a categorization (not just fallback)
        category = engine.categorize(txn)
        assert category is not None, f"Transaction {idx} should be categorized"
        assert len(category) > 0, f"Transaction {idx} should have a non-empty category"
        
        # Find matching rules
        matches = [r for r in engine.rules if r.matches(txn)]
        if matches:
            # If rules match, categorization should include the rule's category
            top_priority_rule = max(matches, key=lambda r: r.priority)
            assert top_priority_rule.category in category, \
                f"Transaction {idx} should be categorized as {top_priority_rule.category}"


def test_reference_dataset_contains_uncategorized_cases():
    """Reference dataset should keep at least one intentionally uncategorized case."""
    txns = ImportHandler.load_csv('data/reference/input/export.202503.csv')
    engine = RuleEngine('data/reference/rules.json')

    categories = [engine.categorize(txn) for txn in txns]
    categorized_count = sum(1 for c in categories if c)
    uncategorized_count = sum(1 for c in categories if not c)

    assert categorized_count > 0, "There should be categorized transactions"
    assert uncategorized_count > 0, "Reference dataset should contain uncategorized transactions"


def test_reference_dataset_contains_transfer_case():
    """Reference dataset should contain at least one transaction categorized as transfer."""
    txns = ImportHandler.load_csv('data/reference/input/export.202503.csv')
    engine = RuleEngine('data/reference/rules.json')

    categorized, _ = engine.categorize_batch(txns)
    transfer_count = sum(1 for txn in categorized if txn.auto_transaction_category == 'Transfer')

    assert transfer_count > 0, "Expected at least one transfer transaction in reference dataset"


if __name__ == '__main__':
    test_categorization()
    test_reference_dataset_contains_uncategorized_cases()
    test_reference_dataset_contains_transfer_case()
    print("✓ All categorization tests passed")

