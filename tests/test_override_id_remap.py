#!/usr/bin/env python3
"""Tests for manual transaction override ID remap suggestions."""

import json
import os
import shutil
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


def test_override_statuses_against_a_real_dataset(tmp_path):
    """Every remap status should be reachable on a dataset loaded from disk.

    The stale entries live here rather than in `data/example`, which doubles as the
    dataset the README tells a newcomer to run: overrides pointing at IDs that no longer
    exist are exactly what this test needs and exactly what makes that run fail.
    """
    run_dir = tmp_path / "remap_dataset"
    (run_dir / "input").mkdir(parents=True)
    (run_dir / "metadata").mkdir()
    for csv_path in sorted(Path("data/example/input").glob("*.csv")):
        shutil.copy(csv_path, run_dir / "input" / csv_path.name)
    shutil.copy(
        Path("data/example/metadata/transaction_id_registry.json"),
        run_dir / "metadata" / "transaction_id_registry.json",
    )

    overrides = json.loads(
        Path("data/example/transaction_overrides.json").read_text(encoding="utf-8")
    )
    overrides.update({
        # No row hint at all, so nothing can be matched against.
        "TX-910003": {"category": "Wohnen"},
        # Row hint quotes a transaction that is present, so the ID can be remapped.
        "TX-910001": {
            "category": "Mobilität",
            "subcategory": "Bahn",
            "_row": "31.03.2025;Buchung;\"APPLE PAY KAUF/DIENSTLEISTUNG VOM 31.03.2025 KARTEN NR. XXXX4821 KKIOSK 45810 BERN SCHWEIZ\";;-7.55;;Einkaufen // Sonstiges Einkaufen",
        },
        # Row hint is close to more than one transaction.
        "TX-910002": {
            "category": "Freizeit",
            "subcategory": "Gastronomie",
            "_row": "30.03.2025;Buchung;\"APPLE PAY KAUF/DIENSTLEISTUNG VOM 30.03.2025 KARTEN NR. XXXX4821 BYRO BASEL SCHWEIZ\"",
        },
        # Row hint resembles nothing in the dataset.
        "TX-999999": {"hidden": True, "_row": "Unknown former transaction"},
    })

    transactions = []
    for csv_path in sorted((run_dir / "input").glob("*.csv")):
        transactions.extend(ImportHandler.load_csv(str(csv_path)))

    id_registry = TransactionIdRegistry(run_dir / "metadata" / "transaction_id_registry.json")
    id_registry.assign_batch(transactions)

    suggestions = build_remap_suggestions(overrides, transactions, candidate_limit=3)
    by_id = {s.old_id: s for s in suggestions}

    assert by_id["TX-000013"].status == "id_exists"
    assert by_id["TX-000031"].status == "id_exists"
    assert by_id["TX-999999"].status == "no_match"
    assert by_id["TX-910003"].status == "missing_row_hint"
    assert by_id["TX-910001"].status == "remap_exact"
    assert by_id["TX-910002"].status in {"ambiguous", "remap_fuzzy"}
