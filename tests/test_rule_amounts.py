#!/usr/bin/env python3
"""Test the optional exact-amount filter (amounts) on rules."""
from datetime import datetime
import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from models import Transaction
from rule_engine import RuleEngine


def _transaction(credit: float = 0.0, debit: float = 0.0) -> Transaction:
    """Build a minimal credit from a joint account, as a standing order carries it."""
    return Transaction(
        date=datetime(2026, 3, 2),
        notification_text="GUTSCHRIFT ABSENDER: MUSTER GEMEINSAMES KONTO",
        credit=credit,
        debit=debit,
        label="",
        category="",
        service_type="Credit",
        counterparty="MUSTER GEMEINSAMES KONTO",
    )


def _payload(amounts) -> dict:
    return {"rules": [{
        "key": "refund_premium_share",
        "name": "Rückzahlung Prämienanteil",
        "transaction_category": "Refund",
        "category": "Leben",
        "subcategory": "Krankenkasse",
        "priority": 6,
        "scope": {
            "transaction_type": "Credit",
            "services": ["Credit"],
            "amounts": amounts,
            "notification_filters": {"counterparties": ["GEMEINSAMES KONTO"]},
        },
    }]}


def _rule(amounts):
    return RuleEngine._parse_rules(_payload(amounts), "test")["refund_premium_share"]


def test_rule_without_amounts_matches_any_amount():
    rule = _rule([])
    assert rule.matches(_transaction(credit=169.20))
    assert rule.matches(_transaction(credit=13.20))


def test_matching_amount_passes():
    assert _rule([169.20]).matches(_transaction(credit=169.20))


def test_other_amount_fails():
    assert not _rule([169.20]).matches(_transaction(credit=13.20))


def test_any_listed_amount_is_enough():
    rule = _rule([152.80, 169.20])
    assert rule.matches(_transaction(credit=152.80))
    assert rule.matches(_transaction(credit=169.20))


def test_amount_is_compared_without_sign():
    rule = RuleEngine._parse_rules(_payload([848.30]), "test")["refund_premium_share"]
    rule.transaction_type = ""
    assert rule.matches(_transaction(debit=848.30))


def test_float_noise_does_not_break_the_match():
    assert _rule([0.3]).matches(_transaction(credit=0.1 + 0.2))


def test_explain_reports_the_amount_check():
    explanation = _rule([169.20]).explain_match(_transaction(credit=13.20))
    failed = [c["id"] for c in explanation["failed_checks"]]
    assert failed == ["amounts"]
    assert "actual=13.2" in explanation["failed_checks"][0]["detail"]


@pytest.mark.parametrize("amounts", ["169.20", [-5], [0], ["169.20"], [True]])
def test_invalid_amounts_are_rejected(amounts):
    with pytest.raises(ValueError, match="Invalid 'amounts'"):
        _rule(amounts)
