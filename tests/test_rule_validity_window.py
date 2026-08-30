#!/usr/bin/env python3
"""Test the optional validity window (valid_from / valid_to) on rules."""
from datetime import date, datetime
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from models import Transaction
from rule_engine import RuleEngine


def _transaction(day: str) -> Transaction:
    """Build a minimal card purchase in Vienna on the given ISO date."""
    return Transaction(
        date=datetime.strptime(day, "%Y-%m-%d"),
        notification_text="KAUF/DIENSTLEISTUNG KLEINOD WIEN",
        credit=0.0,
        debit=49.30,
        label="",
        category="",
        service_type="Card Purchase",
        parsed_merchant="KLEINOD WIEN",
        parsed_location="ÖSTERREICH",
    )


def _rules_payload(scope_extra: dict) -> dict:
    scope = {
        "transaction_type": "Debit",
        "services": ["Card Purchase"],
        "notification_filters": {"merchants": ["WIEN"]},
    }
    scope.update(scope_extra)
    return {"rules": [{
        "key": "trip_vienna",
        "name": "Geschäftsreise Wien",
        "transaction_category": "Expense",
        "category": "Leben",
        "subcategory": "Geschäftsreisen",
        "priority": 8,
        "scope": scope,
    }]}


def _rule(scope_extra: dict):
    return RuleEngine._parse_rules(_rules_payload(scope_extra), "test")["trip_vienna"]


def test_rule_without_window_matches_any_date():
    rule = _rule({})
    assert rule.valid_from is None and rule.valid_to is None
    assert rule.matches(_transaction("2024-01-01"))
    assert rule.matches(_transaction("2025-10-22"))


def test_rule_matches_inside_window_and_on_its_boundaries():
    rule = _rule({"valid_from": "2025-10-21", "valid_to": "2025-10-23"})
    assert rule.valid_from == date(2025, 10, 21)
    assert rule.valid_to == date(2025, 10, 23)
    assert rule.matches(_transaction("2025-10-21"))
    assert rule.matches(_transaction("2025-10-22"))
    assert rule.matches(_transaction("2025-10-23"))


def test_rule_does_not_match_outside_window():
    rule = _rule({"valid_from": "2025-10-21", "valid_to": "2025-10-23"})
    assert not rule.matches(_transaction("2025-10-20"))
    assert not rule.matches(_transaction("2025-10-24"))
    assert not rule.matches(_transaction("2026-10-22"))


def test_open_ended_windows():
    from_only = _rule({"valid_from": "2025-10-21"})
    assert not from_only.matches(_transaction("2025-10-20"))
    assert from_only.matches(_transaction("2030-01-01"))

    to_only = _rule({"valid_to": "2025-10-23"})
    assert to_only.matches(_transaction("2020-01-01"))
    assert not to_only.matches(_transaction("2025-10-24"))


def test_validity_failure_is_reported_in_explain_output():
    rule = _rule({"valid_from": "2025-10-21", "valid_to": "2025-10-23"})
    report = rule.explain_match(_transaction("2025-10-24"))
    assert report["matched"] is False
    failed = [c["id"] for c in report["failed_checks"]]
    assert failed == ["validity"]
    assert "2025-10-21..2025-10-23" in report["checks"][0]["detail"]


def test_invalid_date_format_is_rejected():
    try:
        _rule({"valid_from": "21.10.2025"})
        assert False, "Expected ValueError"
    except ValueError as e:
        assert "valid_from" in str(e) and "YYYY-MM-DD" in str(e)


def test_reversed_window_is_rejected():
    try:
        _rule({"valid_from": "2025-10-23", "valid_to": "2025-10-21"})
        assert False, "Expected ValueError"
    except ValueError as e:
        assert "is after valid_to" in str(e)
