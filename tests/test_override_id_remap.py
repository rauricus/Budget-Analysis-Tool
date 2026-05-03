#!/usr/bin/env python3
"""Tests for manual transaction override ID remap suggestions."""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from import_handler import ImportHandler
from models import Transaction
from override_id_remap import build_remap_suggestions, normalize_row_text
from transaction_id_registry import TransactionIdRegistry


def _txn(tx_id: str, row_text: str, line_no=1) -> Transaction:
    t = Transaction(
        date=datetime(2025, 1, 1),
        notification_text="x",
        credit=0.0,
        debit=1.0,
        label="",
        category="",
    )
    t.transaction_id = tx_id
    t.source_row_text = row_text
    t.source_line_number = line_no
    return t


def test_normalize_row_text_uppercases_and_collapses_spaces():
    value = '  31.03.2025; "Card"   purchase  '
    assert normalize_row_text(value) == "31.03.2025; CARD PURCHASE"


def test_suggestion_marks_existing_id_as_noop():
    txns = [_txn("TX-000123", "31.03.2025;A")]
    overrides = {"TX-000123": {"hidden": True, "_row": "31.03.2025;A"}}

    result = build_remap_suggestions(overrides, txns)

    assert len(result) == 1
    assert result[0].status == "id_exists"
    assert result[0].new_id == "TX-000123"


def test_suggestion_exact_row_match_proposes_remap_exact():
    txns = [_txn("TX-000500", "31.03.2025;KARTENEINKAUF;12.00")]
    overrides = {"TX-000001": {"category": "X", "_row": "31.03.2025;KARTENEINKAUF;12.00"}}

    result = build_remap_suggestions(overrides, txns)

    assert result[0].status == "remap_exact"
    assert result[0].new_id == "TX-000500"
    assert result[0].score == 1.0


def test_suggestion_missing_row_hint():
    txns = [_txn("TX-000500", "31.03.2025;KARTENEINKAUF;12.00")]
    overrides = {"TX-000001": {"category": "X"}}

    result = build_remap_suggestions(overrides, txns)

    assert result[0].status == "missing_row_hint"
    assert result[0].new_id is None


def test_suggestion_no_match_when_similarity_too_low():
    txns = [_txn("TX-000500", "31.03.2025;KARTENEINKAUF;12.00")]
    overrides = {"TX-000001": {"_row": "completely unrelated text"}}

    result = build_remap_suggestions(overrides, txns)

    assert result[0].status == "no_match"
    assert result[0].new_id is None


def test_suggestion_ambiguous_when_top_two_are_too_close():
    txns = [
        _txn("TX-000111", "31.03.2025;MIGROS MARKTHALLE SOLOTHURN;22.20", line_no=10),
        _txn("TX-000112", "31.03.2025;MIGROS MARKTHALLE SOLOTHURN;22.21", line_no=11),
    ]
    overrides = {"TX-000001": {"_row": "31.03.2025;MIGROS MARKTHALLE SOLOTHURN;22.2"}}

    result = build_remap_suggestions(overrides, txns, candidate_limit=2)

    assert result[0].status == "ambiguous"
    assert len(result[0].candidates) == 2


def test_example_overrides_cover_additional_statuses():
    run_dir = Path("data/example")
    overrides_path = run_dir / "transaction_overrides.json"
    input_dir = run_dir / "input"
    registry_path = run_dir / "metadata" / "transaction_id_registry.json"

    with open(overrides_path, "r", encoding="utf-8") as f:
        overrides = json.load(f)

    transactions = []
    for csv_path in sorted(input_dir.glob("*.csv")):
        transactions.extend(ImportHandler.load_csv(str(csv_path)))

    id_registry = TransactionIdRegistry(registry_path)
    id_registry.assign_batch(transactions)

    suggestions = build_remap_suggestions(overrides, transactions, candidate_limit=3)
    by_id = {s.old_id: s for s in suggestions}

    assert by_id["TX-000013"].status == "id_exists"
    assert by_id["TX-000031"].status == "id_exists"
    assert by_id["TX-999999"].status == "no_match"
    assert by_id["TX-910003"].status == "missing_row_hint"
    assert by_id["TX-910001"].status == "remap_exact"
    assert by_id["TX-910002"].status in {"ambiguous", "remap_fuzzy"}
