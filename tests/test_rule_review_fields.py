#!/usr/bin/env python3
"""Test the documentation and review fields on rules (_note, review, reviewed_until)."""
from datetime import date, datetime
import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from models import Transaction
from rule_engine import RuleEngine


def _payload(**extra) -> dict:
    return {"rules": [{
        "key": "health_default",
        "name": "Krankenkasse",
        "transaction_category": "Expense",
        "category": "Leben",
        "subcategory": "Krankenkasse",
        "priority": 5,
        "scope": {
            "transaction_type": "Debit",
            "notification_filters": {"merchants": ["MUSTER KRANKENKASSE"]},
        },
        **extra,
    }]}


def _rule(**extra):
    return RuleEngine._parse_rules(_payload(**extra), "test")["health_default"]


def test_fields_default_to_empty():
    rule = _rule()
    assert rule.note == ""
    assert rule.review == ""
    assert rule.reviewed_until is None


def test_fields_are_parsed():
    rule = _rule(_note="Warum es sie gibt.", review="Wem gehört das?", reviewed_until="2026-08-31")
    assert rule.note == "Warum es sie gibt."
    assert rule.review == "Wem gehört das?"
    assert rule.reviewed_until == date(2026, 8, 31)


def test_fields_do_not_affect_matching():
    txn = Transaction(
        date=datetime(2026, 9, 9),
        notification_text="LASTSCHRIFT MUSTER KRANKENKASSE",
        credit=0.0,
        debit=8.05,
        label="",
        category="",
        service_type="Direct Debit",
        counterparty="MUSTER KRANKENKASSE",
    )
    plain = _rule()
    marked = _rule(_note="n", review="q", reviewed_until="2026-12-31")
    assert plain.matches(txn) and marked.matches(txn)


@pytest.mark.parametrize("field", ["_note", "review"])
def test_non_string_text_field_is_rejected(field):
    with pytest.raises(ValueError, match=field):
        _rule(**{field: ["kein", "Text"]})


def test_invalid_reviewed_until_is_rejected():
    with pytest.raises(ValueError, match="reviewed_until"):
        _rule(review="q", reviewed_until="31.08.2026")


def test_reviewed_until_without_review_is_rejected():
    with pytest.raises(ValueError, match="without 'review'"):
        _rule(reviewed_until="2026-08-31")
