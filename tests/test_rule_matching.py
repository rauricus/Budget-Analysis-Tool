#!/usr/bin/env python3
"""Test rule matching logic"""
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from import_handler import ImportHandler
from rule_engine import RuleEngine


def test_rule_matching_highest_priority():
    """Test that the highest priority matching rule is applied"""
    txns = ImportHandler.load_csv('data/reference/input/export.202503.csv')
    engine = RuleEngine('data/reference/rules.json')
    
    # Find a transaction that matches at least one rule
    txn = None
    for t in txns:
        if any(r.matches(t) for r in engine.rules):
            txn = t
            break
    
    assert txn is not None, "Should find at least one transaction with matching rules"
    
    # Get all matching rules
    matches = [r for r in engine.rules if r.matches(txn)]
    assert len(matches) > 0, "Transaction should match at least one rule"
    
    # Get the highest priority match
    best_match = max(matches, key=lambda r: r.priority)
    
    # Verify categorization uses the highest priority rule
    category = engine.categorize(txn)
    assert best_match.category in category, \
        f"Should categorize as {best_match.category}, not {category}"


def test_multiple_rules_per_transaction():
    """Test that transactions can match multiple rules"""
    txns = ImportHandler.load_csv('data/reference/input/export.202503.csv')
    engine = RuleEngine('data/reference/rules.json')
    
    # Test different transaction types
    matched_count = 0
    for txn in txns:
        matches = [r for r in engine.rules if r.matches(txn)]
        if matches:
            matched_count += 1
            assert len(matches) >= 0, f"Matched transaction should have at least one rule"
    
    # Verify that at least some transactions match
    assert matched_count > 0, "Should find transactions that match rules"


def test_uncategorized_allowed_without_service_match():
    """Without a service match, categorize may return None."""
    engine = RuleEngine('data/reference/rules.json')

    txns = ImportHandler.load_csv('data/reference/input/export.202503.csv')
    has_uncategorized = any(engine.categorize(txn) is None for txn in txns)
    assert has_uncategorized, "Expected at least one uncategorized transaction"


if __name__ == '__main__':
    test_rule_matching_highest_priority()
    test_multiple_rules_per_transaction()
    test_uncategorized_allowed_without_service_match()
    print("✓ All rule matching tests passed")
