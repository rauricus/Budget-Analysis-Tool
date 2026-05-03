#!/usr/bin/env python3
"""Tests for TransactionOverrides: loading, validation, and applying overrides."""
import json
import csv
import shutil
import sys
import os
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from models import Transaction
from transaction_overrides import TransactionOverrides, load_overrides_if_present


def _make_transaction(tx_id: str, category="Kategorie A", subcategory="Sub A",
                      transaction_category="Expense") -> Transaction:
    t = Transaction(
        date=datetime(2025, 1, 15),
        notification_text="Test Transaktion",
        credit=0.0,
        debit=42.0,
        label="",
        category="",
    )
    t.transaction_id = tx_id
    t.auto_transaction_category = transaction_category
    t.auto_category = category
    t.auto_subcategory = subcategory
    return t


def _write(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")


# ---------------------------------------------------------------------------
# Loading & Validation
# ---------------------------------------------------------------------------

class TestLoading:
    def test_loads_empty_file(self, tmp_path):
        f = tmp_path / "transaction_overrides.json"
        _write(f, {})
        ov = TransactionOverrides(str(f))
        assert ov.count == 0

    def test_loads_hidden_entry(self, tmp_path):
        f = tmp_path / "transaction_overrides.json"
        _write(f, {"TX-000001": {"hidden": True}})
        ov = TransactionOverrides(str(f))
        assert ov.count == 1

    def test_loads_category_override(self, tmp_path):
        f = tmp_path / "transaction_overrides.json"
        _write(f, {"TX-000001": {"category": "Sonstiges", "subcategory": "Diverses"}})
        ov = TransactionOverrides(str(f))
        assert ov.count == 1

    def test_raises_on_non_dict_root(self, tmp_path):
        f = tmp_path / "transaction_overrides.json"
        _write(f, [{"hidden": True}])
        with pytest.raises(ValueError, match="must be a JSON object"):
            TransactionOverrides(str(f))

    def test_raises_on_invalid_tx_id_key(self, tmp_path):
        f = tmp_path / "transaction_overrides.json"
        _write(f, {"000001": {"hidden": True}})
        with pytest.raises(ValueError, match="Invalid transaction ID key"):
            TransactionOverrides(str(f))

    def test_raises_on_non_dict_entry(self, tmp_path):
        f = tmp_path / "transaction_overrides.json"
        _write(f, {"TX-000001": True})
        with pytest.raises(ValueError, match="must be an object"):
            TransactionOverrides(str(f))

    def test_raises_on_unknown_field(self, tmp_path):
        f = tmp_path / "transaction_overrides.json"
        _write(f, {"TX-000001": {"unknown_field": "value"}})
        with pytest.raises(ValueError, match="Unknown field"):
            TransactionOverrides(str(f))

    def test_raises_on_invalid_transaction_category(self, tmp_path):
        f = tmp_path / "transaction_overrides.json"
        _write(f, {"TX-000001": {"transaction_category": "NotACategory"}})
        with pytest.raises(ValueError, match="Invalid 'transaction_category'"):
            TransactionOverrides(str(f))

    def test_valid_transaction_categories_accepted(self, tmp_path):
        f = tmp_path / "transaction_overrides.json"
        for tc in ("Income", "Expense", "Refund", "Transfer"):
            _write(f, {"TX-000001": {"transaction_category": tc}})
            ov = TransactionOverrides(str(f))
            assert ov.count == 1

    def test_row_hint_accepted_as_string(self, tmp_path):
        f = tmp_path / "transaction_overrides.json"
        _write(f, {"TX-000001": {"hidden": True, "_row": "15.01.2025;\"Karteneinkauf\";0.00;42.00;\"\";\"\"}"}})
        ov = TransactionOverrides(str(f))
        assert ov.count == 1

    def test_row_hint_non_string_raises(self, tmp_path):
        f = tmp_path / "transaction_overrides.json"
        _write(f, {"TX-000001": {"_row": 12345}})
        with pytest.raises(ValueError, match="'_row'.*must be a string"):
            TransactionOverrides(str(f))

    def test_row_hint_does_not_affect_apply(self, tmp_path):
        f = tmp_path / "transaction_overrides.json"
        _write(f, {"TX-000001": {"category": "Neu", "_row": "some raw csv row"}})
        ov = TransactionOverrides(str(f))
        txns = [_make_transaction("TX-000001")]
        result = ov.apply(txns)
        assert result[0].auto_category == "Neu"


# ---------------------------------------------------------------------------
# apply()
# ---------------------------------------------------------------------------

class TestApply:
    def test_passthrough_when_no_matching_ids(self, tmp_path):
        f = tmp_path / "transaction_overrides.json"
        _write(f, {"TX-999999": {"hidden": True}})
        ov = TransactionOverrides(str(f))

        txns = [_make_transaction("TX-000001"), _make_transaction("TX-000002")]
        result = ov.apply(txns)

        assert len(result) == 2

    def test_hidden_transaction_is_removed(self, tmp_path):
        f = tmp_path / "transaction_overrides.json"
        _write(f, {"TX-000002": {"hidden": True}})
        ov = TransactionOverrides(str(f))

        txns = [_make_transaction("TX-000001"), _make_transaction("TX-000002")]
        result = ov.apply(txns)

        assert len(result) == 1
        assert result[0].transaction_id == "TX-000001"

    def test_category_override_applied(self, tmp_path):
        f = tmp_path / "transaction_overrides.json"
        _write(f, {"TX-000001": {"category": "Überschrieben", "subcategory": "Neu"}})
        ov = TransactionOverrides(str(f))

        txns = [_make_transaction("TX-000001")]
        result = ov.apply(txns)

        assert len(result) == 1
        assert result[0].auto_category == "Überschrieben"
        assert result[0].auto_subcategory == "Neu"

    def test_transaction_category_override_applied(self, tmp_path):
        f = tmp_path / "transaction_overrides.json"
        _write(f, {"TX-000001": {"transaction_category": "Income"}})
        ov = TransactionOverrides(str(f))

        txns = [_make_transaction("TX-000001", transaction_category="Expense")]
        result = ov.apply(txns)

        assert result[0].auto_transaction_category == "Income"

    def test_partial_override_does_not_clear_other_fields(self, tmp_path):
        f = tmp_path / "transaction_overrides.json"
        _write(f, {"TX-000001": {"category": "NeuKategorie"}})
        ov = TransactionOverrides(str(f))

        txns = [_make_transaction("TX-000001", subcategory="OriginalSub")]
        result = ov.apply(txns)

        assert result[0].auto_category == "NeuKategorie"
        assert result[0].auto_subcategory == "OriginalSub"  # untouched

    def test_multiple_hidden_transactions_removed(self, tmp_path):
        f = tmp_path / "transaction_overrides.json"
        _write(f, {
            "TX-000002": {"hidden": True},
            "TX-000004": {"hidden": True},
        })
        ov = TransactionOverrides(str(f))

        txns = [_make_transaction(f"TX-00000{i}") for i in range(1, 6)]
        result = ov.apply(txns)

        ids = [t.transaction_id for t in result]
        assert ids == ["TX-000001", "TX-000003", "TX-000005"]

    def test_unknown_id_produces_warning(self, tmp_path, caplog):
        f = tmp_path / "transaction_overrides.json"
        _write(f, {"TX-999999": {"hidden": True}})
        ov = TransactionOverrides(str(f))

        txns = [_make_transaction("TX-000001")]
        import logging
        with caplog.at_level(logging.WARNING, logger="transaction_overrides"):
            ov.apply(txns)

        assert "TX-999999" in caplog.text

    def test_empty_overrides_file_is_no_op(self, tmp_path):
        f = tmp_path / "transaction_overrides.json"
        _write(f, {})
        ov = TransactionOverrides(str(f))

        txns = [_make_transaction("TX-000001"), _make_transaction("TX-000002")]
        result = ov.apply(txns)

        assert len(result) == 2


# ---------------------------------------------------------------------------
# load_overrides_if_present()
# ---------------------------------------------------------------------------

class TestLoadOverridesIfPresent:
    def test_returns_none_when_path_is_none(self):
        assert load_overrides_if_present(None) is None

    def test_returns_none_when_file_missing(self, tmp_path):
        assert load_overrides_if_present(str(tmp_path / "nonexistent.json")) is None

    def test_returns_overrides_when_file_exists(self, tmp_path):
        f = tmp_path / "transaction_overrides.json"
        _write(f, {"TX-000001": {"hidden": True}})
        result = load_overrides_if_present(str(f))
        assert result is not None
        assert result.count == 1


# ---------------------------------------------------------------------------
# Integration: main() rejects transaction_overrides.json in base datasets
# ---------------------------------------------------------------------------

def _setup_run_dir(tmp_path: Path, base_rules_dir: Path, has_overrides: bool, base=None) -> Path:
    """Build a minimal run directory structure for integration tests."""
    run_dir = tmp_path / "run"
    (run_dir / "input").mkdir(parents=True)
    (run_dir / "output").mkdir(parents=True)
    (run_dir / "metadata").mkdir(parents=True)

    # Copy a real CSV input file
    src_csv = Path("data/example/input/export.202503.csv")
    shutil.copy(src_csv, run_dir / "input" / src_csv.name)

    # Write rules.json
    if base:
        rules_content = {"base": base, "rules": []}
    else:
        # Copy the reference rules
        src_rules = base_rules_dir / "rules.json"
        rules_content = json.loads(src_rules.read_text(encoding="utf-8"))
    _write(run_dir / "rules.json", rules_content)

    if has_overrides:
        _write(run_dir / "transaction_overrides.json", {})

    return run_dir


class TestMainWithOverrides:
    def test_main_rejects_overrides_in_referenced_base_dataset(self, tmp_path):
        """main() must return 1 when the referenced base dataset contains a transaction_overrides.json."""
        from categorize_transactions import main

        # Set up a fake base dataset under tmp_path/data/mybase/
        base_dir = tmp_path / "data" / "mybase"
        base_dir.mkdir(parents=True)
        shutil.copy(Path("data/reference/rules.json"), base_dir / "rules.json")
        # Place overrides in the BASE – this must be rejected
        _write(base_dir / "transaction_overrides.json", {})

        # Set up the top-level run dir that references the base
        run_dir = tmp_path / "run"
        (run_dir / "input").mkdir(parents=True)
        (run_dir / "output").mkdir(parents=True)
        (run_dir / "metadata").mkdir(parents=True)
        shutil.copy(
            Path("data/example/input/export.202503.csv"),
            run_dir / "input" / "export.202503.csv",
        )
        _write(run_dir / "rules.json", {"base": "mybase", "rules": []})

        # Run from tmp_path so "data/mybase" resolves correctly
        old_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            result = main([str(run_dir)])
        finally:
            os.chdir(old_cwd)

        assert result == 1

    def test_main_accepts_overrides_in_top_level_dataset_with_base(self, tmp_path):
        """main() must succeed when the top-level dataset (with 'base') has overrides."""
        from categorize_transactions import main

        # Set up base dataset (no overrides)
        base_dir = tmp_path / "data" / "mybase"
        base_dir.mkdir(parents=True)
        shutil.copy(Path("data/reference/rules.json"), base_dir / "rules.json")

        # Top-level run dir with overrides file – this must be accepted
        run_dir = tmp_path / "run"
        (run_dir / "input").mkdir(parents=True)
        (run_dir / "output").mkdir(parents=True)
        (run_dir / "metadata").mkdir(parents=True)
        shutil.copy(
            Path("data/example/input/export.202503.csv"),
            run_dir / "input" / "export.202503.csv",
        )
        _write(run_dir / "rules.json", {"base": "mybase", "rules": []})
        _write(run_dir / "transaction_overrides.json", {})

        old_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            result = main([str(run_dir)])
        finally:
            os.chdir(old_cwd)

        assert result == 0

    def test_main_accepts_overrides_in_standalone_dataset(self, tmp_path):
        """main() must succeed when a standalone dataset (no 'base') has overrides."""
        from categorize_transactions import main

        run_dir = tmp_path / "run"
        (run_dir / "input").mkdir(parents=True)
        (run_dir / "output").mkdir(parents=True)
        (run_dir / "metadata").mkdir(parents=True)

        shutil.copy(
            Path("data/example/input/export.202503.csv"),
            run_dir / "input" / "export.202503.csv",
        )
        shutil.copy(Path("data/example/rules.json"), run_dir / "rules.json")
        _write(run_dir / "transaction_overrides.json", {})

        result = main([str(run_dir)])

        assert result == 0

    def test_main_no_overrides_file_is_fine(self, tmp_path):
        """main() must succeed when no transaction_overrides.json exists at all."""
        from categorize_transactions import main

        run_dir = tmp_path / "run"
        (run_dir / "input").mkdir(parents=True)
        (run_dir / "output").mkdir(parents=True)
        (run_dir / "metadata").mkdir(parents=True)

        shutil.copy(
            Path("data/example/input/export.202503.csv"),
            run_dir / "input" / "export.202503.csv",
        )
        shutil.copy(Path("data/example/rules.json"), run_dir / "rules.json")

        result = main([str(run_dir)])

        assert result == 0

    def test_main_processes_only_selected_input_file(self, tmp_path):
        """With --input-file, main() must only process the selected file."""
        from categorize_transactions import main

        run_dir = tmp_path / "run"
        (run_dir / "input").mkdir(parents=True)
        (run_dir / "output").mkdir(parents=True)
        (run_dir / "metadata").mkdir(parents=True)

        shutil.copy(
            Path("data/example/input/export.202503.csv"),
            run_dir / "input" / "export.202503.csv",
        )
        shutil.copy(
            Path("data/example/input/export.202504.csv"),
            run_dir / "input" / "export.202504.csv",
        )
        shutil.copy(Path("data/example/rules.json"), run_dir / "rules.json")

        result = main([str(run_dir), "--input-file", "export.202503.csv"])

        assert result == 0
        assert (run_dir / "output" / "export.202503.categorized.csv").exists()
        assert not (run_dir / "output" / "export.202504.categorized.csv").exists()

    def test_main_accepts_input_file_path_with_input_prefix(self, tmp_path):
        """--input-file should accept paths that already include input/."""
        from categorize_transactions import main

        run_dir = tmp_path / "run"
        (run_dir / "input").mkdir(parents=True)
        (run_dir / "output").mkdir(parents=True)
        (run_dir / "metadata").mkdir(parents=True)

        shutil.copy(
            Path("data/example/input/export.202503.csv"),
            run_dir / "input" / "export.202503.csv",
        )
        shutil.copy(
            Path("data/example/input/export.202504.csv"),
            run_dir / "input" / "export.202504.csv",
        )
        shutil.copy(Path("data/example/rules.json"), run_dir / "rules.json")

        result = main([str(run_dir), "--input-file", "input/export.202504.csv"])

        assert result == 0
        assert (run_dir / "output" / "export.202504.categorized.csv").exists()
        assert not (run_dir / "output" / "export.202503.categorized.csv").exists()


class TestExampleDatasetOverrides:
    def test_example_overrides_fail_on_unknown_ids_with_help_hint(self, tmp_path, capsys):
        """Example overrides must fail when unknown IDs exist and should point to remap helper."""
        from categorize_transactions import main

        run_dir = tmp_path / "example"
        (run_dir / "input").mkdir(parents=True)
        (run_dir / "output").mkdir(parents=True)
        (run_dir / "metadata").mkdir(parents=True)

        # Copy a single month for deterministic assertions
        shutil.copy(
            Path("data/example/input/export.202503.csv"),
            run_dir / "input" / "export.202503.csv",
        )
        shutil.copy(Path("data/example/rules.json"), run_dir / "rules.json")
        shutil.copy(
            Path("data/example/transaction_overrides.json"),
            run_dir / "transaction_overrides.json",
        )

        result = main([str(run_dir)])

        assert result == 1
        captured = capsys.readouterr().out
        assert "unknown transaction ID" in captured
        assert "TX-999999" in captured
        assert "suggest_override_ids.py" in captured

    def test_example_overrides_can_ignore_unknown_ids_with_switch(self, tmp_path, capsys):
        """With --ignore-unknown-overrides, unknown IDs are logged but do not fail the run."""
        from categorize_transactions import main

        run_dir = tmp_path / "example"
        (run_dir / "input").mkdir(parents=True)
        (run_dir / "output").mkdir(parents=True)
        (run_dir / "metadata").mkdir(parents=True)

        shutil.copy(
            Path("data/example/input/export.202503.csv"),
            run_dir / "input" / "export.202503.csv",
        )
        shutil.copy(Path("data/example/rules.json"), run_dir / "rules.json")
        shutil.copy(
            Path("data/example/transaction_overrides.json"),
            run_dir / "transaction_overrides.json",
        )

        result = main([str(run_dir), "--ignore-unknown-overrides"])

        assert result == 0
        captured = capsys.readouterr().out
        assert "unknown transaction ID" in captured
        assert "TX-999999" in captured
        assert "Continuing because --ignore-unknown-overrides is set." in captured

        output_csv = run_dir / "output" / "export.202503.categorized.csv"
        assert output_csv.exists()

        with open(output_csv, "r", encoding="utf-8") as f:
            rows = list(csv.DictReader(f, delimiter=";"))

        by_id = {row["Transaction ID"]: row for row in rows}
        # Known overrides from example fixture should still apply.
        assert "TX-000031" not in by_id
        assert "TX-000013" in by_id
        assert by_id["TX-000013"]["Category"] == "Freizeit"
        assert by_id["TX-000013"]["Subcategory"] == "Kultur"

    def test_known_overrides_are_applied_successfully(self, tmp_path):
        """Overrides should still be applied when all override IDs exist."""
        from categorize_transactions import main

        run_dir = tmp_path / "example"
        (run_dir / "input").mkdir(parents=True)
        (run_dir / "output").mkdir(parents=True)
        (run_dir / "metadata").mkdir(parents=True)

        shutil.copy(
            Path("data/example/input/export.202503.csv"),
            run_dir / "input" / "export.202503.csv",
        )
        shutil.copy(Path("data/example/rules.json"), run_dir / "rules.json")
        _write(
            run_dir / "transaction_overrides.json",
            {
                "TX-000031": {
                    "hidden": True,
                    "_row": "27.03.2025;Bargeldbezug Einkaufszentrum Metropole Biel",
                },
                "TX-000013": {
                    "transaction_category": "Expense",
                    "category": "Freizeit",
                    "subcategory": "Kultur",
                    "_row": "30.03.2025;Karteneinkauf BYRO BASEL",
                },
            },
        )

        result = main([str(run_dir)])

        assert result == 0

        output_csv = run_dir / "output" / "export.202503.categorized.csv"
        assert output_csv.exists()

        with open(output_csv, "r", encoding="utf-8") as f:
            rows = list(csv.DictReader(f, delimiter=";"))

        by_id = {row["Transaction ID"]: row for row in rows}

        # Hidden example: must not be present in export
        assert "TX-000031" not in by_id

        # Category override example: must reflect override values
        assert "TX-000013" in by_id
        assert by_id["TX-000013"]["Category"] == "Freizeit"
        assert by_id["TX-000013"]["Subcategory"] == "Kultur"

