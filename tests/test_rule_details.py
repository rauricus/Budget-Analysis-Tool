#!/usr/bin/env python3
"""Test rule matching against sample transactions"""
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from import_handler import ImportHandler
from rule_engine import RuleEngine


def test_migros_supermarket_rule():
    """Test that migros_supermarket rule matches correctly"""
    txns = ImportHandler.load_csv('data/reference/input/export.202503.csv')
    engine = RuleEngine('data/reference/rules.json')
    
    # Get transaction 4 (MIGROS transaction)
    txn = txns[4]
    
    # Get the migros_supermarket rule
    rule = [r for r in engine.rules if r.id == 1001][0]
    
    # Verify rule properties
    assert rule.merchants == ['MIGROS', 'COOP']
    assert rule.exclude_keywords == ['TAKE AWAY']
    
    # Verify transaction direction matches
    assert rule.transaction_type == txn.transaction_type
    
    # Verify the rule matches this transaction
    assert rule.matches(txn), f"Rule '{rule.id}' should match transaction 4"
    
    # Verify categorization
    category = engine.categorize(txn)
    assert rule.category in category


def test_rule_matching_order():
    """Test that rules are applied in priority order"""
    txns = ImportHandler.load_csv('data/reference/input/export.202503.csv')
    engine = RuleEngine('data/reference/rules.json')
    
    # Find a transaction that matches at least one rule
    txn = None
    for t in txns:
        if any(r.matches(t) for r in engine.rules):
            txn = t
            break
    
    assert txn is not None, "Should find at least one transaction with matching rules"
    
    # Find all matching rules
    matches = [r for r in engine.rules if r.matches(txn)]
    assert len(matches) > 0, "Transaction should match at least one rule"
    
    # Verify rules are sorted by priority
    priorities = [r.priority for r in matches]
    assert priorities == sorted(priorities, reverse=True), "Rules should be in priority order"


def test_rule_service_filtering():
    """Test that optional service/provider filters in rules work"""
    txns = ImportHandler.load_csv('data/reference/input/export.202503.csv')
    engine = RuleEngine('data/reference/rules.json')

    txn = txns[4]
    rule = [r for r in engine.rules if r.id == 1001][0]

    rule.services = ["Karteneinkauf"]
    rule.providers = ["Apple Pay"]
    assert rule.matches(txn), "Rule should match when service/provider filters include Karteneinkauf + Apple Pay"

    rule.services = ["Twint"]
    assert not rule.matches(txn), "Rule should not match when service filter excludes Karteneinkauf"

    rule.services = ["Karteneinkauf"]
    rule.providers = ["Google Pay"]
    assert not rule.matches(txn), "Rule should not match when provider filter excludes Apple Pay"


def test_rule_without_service_filter_can_match():
    """A rule without services filter should rely on other criteria."""
    txns = ImportHandler.load_csv('data/reference/input/export.202503.csv')
    engine = RuleEngine('data/reference/rules.json')

    txn = txns[4]
    rule = [r for r in engine.rules if r.id == 1001][0]

    rule.services = []
    rule.providers = []
    assert rule.matches(txn), "Rule without service/provider filters should still match by merchant criteria"


if __name__ == '__main__':
    test_migros_supermarket_rule()
    test_rule_matching_order()
    test_rule_service_filtering()
    print("✓ All tests passed")
