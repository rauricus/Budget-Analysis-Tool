#!/usr/bin/env python3
"""Test the split field on rules: validation, application after overrides, and the pipeline."""
import csv
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from categorize_transactions import main as run_pipeline
from doctor import build_doctor_report
from models import Transaction
from rule_engine import RuleEngine, apply_rule_splits

PREMIUM_SPLIT = [
    {"amount": 169.20, "category": "Leben", "subcategory": "Familie", "_note": "Prämie Tochter"},
    {"_note": "Meine Prämie"},
]


def _payload(split) -> dict:
    return {"rules": [{
        "key": "kk_praemie",
        "name": "Krankenkasse: Prämie",
        "transaction_category": "Expense",
        "category": "Leben",
        "subcategory": "Krankenkasse",
        "priority": 6,
        "split": split,
        "scope": {
            "transaction_type": "Debit",
            "notification_filters": {"merchants": ["MUSTER KRANKENKASSE"]},
        },
    }]}


def _rule(split=PREMIUM_SPLIT):
    return RuleEngine._parse_rules(_payload(split), "test")["kk_praemie"]


def _premium(tx_id="TX-000001", debit=848.30) -> Transaction:
    txn = Transaction(
        date=datetime(2026, 3, 2),
        notification_text="LASTSCHRIFT MUSTER KRANKENKASSE",
        credit=0.0,
        debit=debit,
        label="",
        category="",
        service_type="Direct Debit",
        counterparty="MUSTER KRANKENKASSE",
    )
    txn.transaction_id = tx_id
    txn.auto_transaction_category = "Expense"
    txn.auto_category = "Leben"
    txn.auto_subcategory = "Krankenkasse"
    return txn


def test_split_is_parsed_and_does_not_affect_matching():
    rule = _rule()
    assert rule.split == PREMIUM_SPLIT
    assert rule.matches(_premium())


def test_rule_without_split_has_an_empty_list():
    assert _rule(None).split == []


@pytest.mark.parametrize("split, message", [
    ([{"amount": 10.0, "category": "Leben"}], "at least 2 parts"),
    ([{"category": "Leben"}, {"category": "Leben"}], "Exactly one split part"),
    ([{"amount": 10.0}, {"amount": 20.0}], "Exactly one split part"),
    ([{"amount": 0, "category": "Leben"}, {}], "non-zero number"),
    ([{"amount": 10.0, "category": "Leben", "percent": 5}, {}], "Unknown field"),
    ([{"amount": 10.0, "category": "Leben", "transaction_category": "Gift"}, {}], "transaction_category"),
])
def test_invalid_split_is_rejected(split, message):
    with pytest.raises(ValueError, match=message):
        _rule(split)


def test_parts_get_suffixed_ids_amounts_and_categories():
    parts = apply_rule_splits([_premium()], {"TX-000001": _rule()})

    assert [(p.transaction_id, p.debit, p.auto_category, p.auto_subcategory) for p in parts] == [
        ("TX-000001.1", 169.20, "Leben", "Familie"),
        ("TX-000001.2", 679.10, "Leben", "Krankenkasse"),
    ]
    assert all(p.auto_transaction_category == "Expense" for p in parts)


def test_transaction_won_by_another_rule_is_not_split():
    assert [t.transaction_id for t in apply_rule_splits([_premium()], {"TX-000001": None})] == ["TX-000001"]


def test_override_that_sets_categories_wins_over_the_rule_split():
    overrides = {"TX-000001": {"category": "Leben", "subcategory": "Gesundheit"}}
    result = apply_rule_splits([_premium()], {"TX-000001": _rule()}, overrides)
    assert [t.transaction_id for t in result] == ["TX-000001"]


def test_note_only_override_does_not_stop_the_rule_split():
    overrides = {"TX-000001": {"_note": "nur eine Notiz", "_row": "02.03.2026;Buchung"}}
    result = apply_rule_splits([_premium()], {"TX-000001": _rule()}, overrides)
    assert [t.transaction_id for t in result] == ["TX-000001.1", "TX-000001.2"]


def test_negative_remainder_becomes_a_part_on_the_other_side():
    """A collective refund that also nets out a charge: 125.00 back, 5.00 owed, 120.00 paid."""
    rule = _rule([
        {"amount": 125.00, "category": "Leben", "subcategory": "Familie"},
        {"transaction_category": "Expense", "_note": "Kostenbeteiligung, verrechnet"},
    ])
    refund = _premium(debit=0.0)
    refund.credit = 120.00
    refund.auto_transaction_category = "Refund"

    parts = apply_rule_splits([refund], {"TX-000001": rule})

    assert [(p.credit, p.debit, p.transaction_type, p.auto_transaction_category) for p in parts] == [
        (125.00, 0.0, "Credit", "Refund"),
        (0.0, 5.00, "Debit", "Expense"),
    ]
    assert round(sum(p.amount for p in parts), 2) == 120.00


def test_amounts_without_remainder_abort():
    with pytest.raises(ValueError, match="no remainder"):
        apply_rule_splits([_premium(debit=169.20)], {"TX-000001": _rule()})


def _exported(run_dir: Path) -> dict:
    rows = {}
    for path in sorted((run_dir / "output").glob("*.categorized.csv")):
        with open(path, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f, delimiter=";"):
                rows[row["Transaction ID"]] = row
    return rows


def test_pipeline_splits_rule_matches_and_respects_overrides(tmp_path):
    run_dir = tmp_path / "example"
    shutil.copytree("data/example", run_dir)
    rules_path = run_dir / "rules.json"
    data = json.loads(rules_path.read_text(encoding="utf-8"))
    housing = next(r for r in data["rules"] if r["key"] == "housing_1")
    housing["split"] = [{"amount": 300.0, "category": "Wohnen", "subcategory": "Nebenkosten"}, {}]
    rules_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    overrides_path = run_dir / "transaction_overrides.json"
    overrides = json.loads(overrides_path.read_text(encoding="utf-8"))
    overrides["TX-000079"] = {"category": "Anders", "_row": "28.02.2025;Buchung"}
    overrides["TX-000088"] = {"_note": "nur eine Notiz", "_row": "30.04.2025;Buchung"}
    overrides_path.write_text(json.dumps(overrides), encoding="utf-8")

    run_pipeline([str(run_dir)])
    rows = _exported(run_dir)

    assert "TX-000074" not in rows
    assert (rows["TX-000074.1"]["Debit in CHF"], rows["TX-000074.1"]["Subcategory"]) == ("300.0", "Nebenkosten")
    assert rows["TX-000074.2"]["Debit in CHF"] == "1474.0"
    assert (rows["TX-000074.2"]["Category"], rows["TX-000074.2"]["Subcategory"]) == (
        housing["category"], housing["subcategory"],
    )
    assert rows["TX-000074.2"]["Matched Rule Key"] == "housing_1"
    assert rows["TX-000079"]["Category"] == "Anders"
    assert {"TX-000088.1", "TX-000088.2"} <= rows.keys()
    # The doctor applies rule splits the same way, so the fresh output is not stale.
    assert all(not items for items in build_doctor_report(run_dir)["output_findings"].values())
