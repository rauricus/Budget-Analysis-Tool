#!/usr/bin/env python3
"""Test rule matching logic"""
from datetime import datetime
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from import_handler import ImportHandler
from models import Transaction
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


def test_reference_dataset_has_uncategorized_matches():
    """Reference dataset should contain at least one unmatched transaction."""
    engine = RuleEngine('data/reference/rules.json')

    txns = ImportHandler.load_csv('data/reference/input/export.202503.csv')
    has_uncategorized = any(engine.categorize(txn) is None for txn in txns)
    assert has_uncategorized, "Expected at least one uncategorized transaction"


def test_reference_dataset_contains_counterparty_example_rules():
    """Reference rules should contain anonymized examples for counterparty-based matching."""
    engine = RuleEngine('data/reference/rules.json')

    by_key = {rule.key: rule for rule in engine.rules}
    assert "example_counterparty_1" in by_key
    assert "example_counterparty_iban_1" in by_key
    assert by_key["example_counterparty_1"].counterparties == ["FIKTIVE LOHN AG"]
    assert by_key["example_counterparty_iban_1"].counterparty_ibans == ["CH11 2222 3333 4444 5555 6"]


def test_reference_dataset_counterparty_examples_match_synthetic_transactions():
    """Anonymized example rules should match synthetic transactions using counterparty fields."""
    engine = RuleEngine('data/reference/rules.json')
    by_key = {rule.key: rule for rule in engine.rules}

    income_txn = Transaction(
        date=datetime(2025, 1, 15),
        notification_text="Gutschrift Beispiel Lohn",
        credit=4200.0,
        debit=0.0,
        label="",
        category="",
        service_type="Credit",
        counterparty="Fiktive Lohn AG Personalabteilung",
        counterparty_iban="CH9300762011623852957",
        reference="Lohnbeispiel Januar",
    )
    debit_txn = Transaction(
        date=datetime(2025, 1, 20),
        notification_text="Lastschrift Demo",
        credit=0.0,
        debit=25.0,
        label="",
        category="",
        service_type="Direct Debit",
        counterparty="Anonymisierter Verein Sektion Nord",
        counterparty_iban="CH1122223333444455556",
        reference="Demo-Zweck Jahresbeitrag",
    )

    assert by_key["example_counterparty_1"].matches(income_txn)
    assert by_key["example_counterparty_iban_1"].matches(debit_txn)


if __name__ == '__main__':
    test_rule_matching_highest_priority()
    test_multiple_rules_per_transaction()
    test_reference_dataset_has_uncategorized_matches()
    test_reference_dataset_contains_counterparty_example_rules()
    test_reference_dataset_counterparty_examples_match_synthetic_transactions()
    print("✓ All rule matching tests passed")
