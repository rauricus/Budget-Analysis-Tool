#!/usr/bin/env python3
"""Tests for doctor.py: review items, rule and override findings, and that it writes nothing."""
import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from categorize_transactions import main as run_pipeline
from doctor import build_doctor_report, count_findings, main


def _copy_example(tmp_path) -> Path:
    run_dir = tmp_path / "example"
    shutil.copytree("data/example", run_dir)
    return run_dir


def _edit_rules(run_dir: Path, edit) -> None:
    path = run_dir / "rules.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    edit({rule["key"]: rule for rule in data["rules"]}, data["rules"])
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _write_overrides(run_dir: Path, overrides: dict) -> None:
    (run_dir / "transaction_overrides.json").write_text(json.dumps(overrides), encoding="utf-8")


def _snapshot(run_dir: Path) -> dict:
    return {p.relative_to(run_dir).as_posix(): p.read_bytes() for p in run_dir.rglob("*") if p.is_file()}


def test_example_has_only_its_deliberately_uncategorized_rows(tmp_path):
    report = build_doctor_report(_copy_example(tmp_path))

    assert report["to_review"] == []
    for group in ("rules_findings", "override_findings", "input_findings", "output_findings"):
        assert all(not items for items in report[group].values()), group
    assert {item["transaction_id"] for item in report["uncategorized"]} == {
        "TX-000055", "TX-000065", "TX-000066", "TX-000067", "TX-000068",
    }


def test_doctor_writes_nothing(tmp_path):
    run_dir = _copy_example(tmp_path)
    (run_dir / "metadata" / "transaction_id_registry.json").unlink()
    before = _snapshot(run_dir)

    assert main([str(run_dir)]) == 1

    assert _snapshot(run_dir) == before


def test_review_lists_wins_after_reviewed_until_without_override(tmp_path):
    run_dir = _copy_example(tmp_path)

    def edit(rules, _):
        rules["housing_1"]["review"] = "Miete noch aktuell?"
        rules["housing_1"]["reviewed_until"] = "2025-02-28"
        rules["housing_1"]["_note"] = "Dauerauftrag an die Verwaltung."
    _edit_rules(run_dir, edit)
    _write_overrides(run_dir, {"TX-000088": {"category": "Wohnen", "_row": "30.04.2025;Buchung"}})

    items = build_doctor_report(run_dir)["to_review"]

    # TX-000074 and TX-000079 fall on or before reviewed_until, TX-000088 is overridden.
    assert [item["transaction_id"] for item in items] == ["TX-000009"]
    assert items[0]["question"] == "Miete noch aktuell?"
    assert items[0]["note"] == "Dauerauftrag an die Verwaltung."


def test_review_without_reviewed_until_lists_every_win(tmp_path):
    run_dir = _copy_example(tmp_path)
    _edit_rules(run_dir, lambda rules, _: rules["housing_1"].update(review="Miete noch aktuell?"))

    items = build_doctor_report(run_dir)["to_review"]

    assert sorted(item["transaction_id"] for item in items) == [
        "TX-000009", "TX-000074", "TX-000079", "TX-000088",
    ]


def test_rule_findings(tmp_path):
    run_dir = _copy_example(tmp_path)

    def edit(rules, rule_list):
        rules["housing_1"]["scope"]["amounts"] = [1774.0, 1800.0]
        dead = json.loads(json.dumps(rules["housing_1"]))
        dead["key"] = "dead_rule"
        dead["scope"]["notification_filters"]["include_keywords"] = ["GIBT ES NICHT"]
        shadowed = json.loads(json.dumps(rules["housing_1"]))
        shadowed["key"] = "shadowed_rule"
        shadowed["priority"] = 1
        shadowed["scope"]["amounts"] = []
        rule_list.extend([dead, shadowed])
    _edit_rules(run_dir, edit)

    findings = build_doctor_report(run_dir)["rules_findings"]

    assert [item["key"] for item in findings["never_matching"]] == ["dead_rule"]
    assert findings["never_winning"] == [{
        "key": "shadowed_rule",
        "source": (run_dir / "rules.json").as_posix(),
        "beaten_by": {"housing_1": 4},
    }]
    assert [(item["key"], item["amounts"]) for item in findings["unused_amounts"]] == [
        ("housing_1", [1800.0]),
    ]


def test_override_findings(tmp_path):
    run_dir = _copy_example(tmp_path)
    rules = {r["key"]: r for r in json.loads((run_dir / "rules.json").read_text(encoding="utf-8"))["rules"]}
    housing = rules["housing_1"]
    _write_overrides(run_dir, {
        "TX-999999": {"category": "Wohnen", "_row": "01.01.2025;Buchung"},
        "TX-000074": {
            "category": housing["category"],
            "subcategory": housing["subcategory"],
            "_row": "31.01.2025;Buchung",
        },
        "TX-000079": {"category": "Anders", "_row": "28.02.2025;Karteneinkauf MIGROS ZUERICH"},
        "TX-000009": {"category": "Anders", "_row": "01.01.2020;Buchung"},
        "TX-000070": {"category": "Anders"},
        "TX-000088": {"_note": "nur eine Notiz", "_row": "30.04.2025;Buchung"},
    })

    findings = build_doctor_report(run_dir)["override_findings"]

    assert [item["transaction_id"] for item in findings["unknown_ids"]] == ["TX-999999"]
    mismatch = {item["transaction_id"]: item["problem"] for item in findings["row_mismatch"]}
    assert mismatch.keys() == {"TX-000079", "TX-000009"}
    assert "01.01.2020" in mismatch["TX-000009"]
    assert "MIGROS" in mismatch["TX-000079"]
    assert sorted(item["transaction_id"] for item in findings["without_effect"]) == [
        "TX-000074", "TX-000088",
    ]
    assert [item["transaction_id"] for item in findings["without_row"]] == ["TX-000070"]


def test_abbreviated_row_hint_is_accepted(tmp_path):
    """The committed example abbreviates `_row` by hand; that must not read as a shift."""
    report = build_doctor_report(_copy_example(tmp_path))
    assert report["override_findings"]["row_mismatch"] == []


def test_exit_code_is_zero_without_findings(tmp_path):
    run_dir = _copy_example(tmp_path)
    overrides = json.loads((run_dir / "transaction_overrides.json").read_text(encoding="utf-8"))
    for item in build_doctor_report(run_dir)["uncategorized"]:
        year, month, day = item["date"].split("-")
        overrides[item["transaction_id"]] = {"hidden": True, "_row": f"{day}.{month}.{year}"}
    _write_overrides(run_dir, overrides)
    run_pipeline([str(run_dir)])

    assert count_findings(build_doctor_report(run_dir)) == 0
    assert main([str(run_dir)]) == 0


def _add_housing_copy(run_dir: Path, key: str, **changes) -> None:
    def edit(rules, rule_list):
        copy = json.loads(json.dumps(rules["housing_1"]))
        copy["key"] = key
        for field, value in changes.items():
            if field in ("valid_from", "valid_to"):
                copy["scope"][field] = value
            elif field == "include_keywords":
                copy["scope"]["notification_filters"]["include_keywords"] = value
            else:
                copy[field] = value
        rule_list.append(copy)
    _edit_rules(run_dir, edit)


def test_rule_change_without_rerun_marks_output_stale(tmp_path):
    run_dir = _copy_example(tmp_path)
    _edit_rules(run_dir, lambda rules, _: rules["housing_1"].update(subcategory="Anders"))

    differs = build_doctor_report(run_dir)["output_findings"]["differs"]
    assert sorted(item["transaction_id"] for item in differs) == [
        "TX-000009", "TX-000074", "TX-000079", "TX-000088",
    ]
    assert differs[0]["current"].endswith("/ Anders")

    run_pipeline([str(run_dir)])
    assert build_doctor_report(run_dir)["output_findings"]["differs"] == []


def test_partial_pipeline_run_leaves_months_json_incomplete(tmp_path):
    run_dir = _copy_example(tmp_path)
    run_pipeline([str(run_dir), "--input-file", "export.202503.csv", "--ignore-unknown-overrides"])

    outputs = build_doctor_report(run_dir)["output_findings"]
    assert outputs["months_not_recorded"] == ["2025-01", "2025-02", "2025-04"]
    assert outputs["recorded_months_without_input"] == []


def test_overlapping_input_files_are_reported(tmp_path):
    run_dir = _copy_example(tmp_path)
    shutil.copy(run_dir / "input" / "export.202504.csv", run_dir / "input" / "export.202504-copy.csv")

    assert build_doctor_report(run_dir)["input_findings"]["overlapping_files"] == [
        {"files": ["export.202504-copy.csv", "export.202504.csv"], "transactions": 15},
    ]


def test_missing_input_month_is_reported(tmp_path):
    run_dir = _copy_example(tmp_path)
    (run_dir / "input" / "export.202502.csv").unlink()

    report = build_doctor_report(run_dir)
    assert report["input_findings"]["missing_months"] == ["2025-02"]
    assert report["output_findings"]["recorded_months_without_input"] == ["2025-02"]


def test_never_matching_rules_name_another_period(tmp_path):
    run_dir = _copy_example(tmp_path)
    _add_housing_copy(run_dir, "miete_alt", valid_from="2024-01-01", valid_to="2024-12-31")
    _add_housing_copy(run_dir, "miete_neu", valid_from="2025-06-01")
    _add_housing_copy(run_dir, "ferien_2023", include_keywords=["GIBT ES NICHT"])

    reasons = {i["key"]: i["reason"] for i in build_doctor_report(run_dir)["rules_findings"]["never_matching"]}
    assert "valid_to 2024-12-31 is before" in reasons["miete_alt"]
    assert "valid_from 2025-06-01 is after" in reasons["miete_neu"]
    assert reasons["ferien_2023"] == "names 2023, the data covers 2025"


def test_reviewed_until_after_the_last_month_is_reported(tmp_path):
    run_dir = _copy_example(tmp_path)
    _edit_rules(run_dir, lambda rules, _: rules["housing_1"].update(review="q", reviewed_until="2025-04-30"))
    assert build_doctor_report(run_dir)["rules_findings"]["review_after_data"] == []

    _edit_rules(run_dir, lambda rules, _: rules["housing_1"].update(reviewed_until="2025-05-15"))
    items = build_doctor_report(run_dir)["rules_findings"]["review_after_data"]
    assert [(i["key"], i["month_end"]) for i in items] == [("housing_1", "2025-04-30")]


def test_equal_priority_rules_with_different_results_are_reported(tmp_path):
    run_dir = _copy_example(tmp_path)
    _add_housing_copy(run_dir, "housing_tie", subcategory="Anders")

    assert build_doctor_report(run_dir)["rules_findings"]["priority_ties"] == [{
        "winner": "housing_1",
        "loser": "housing_tie",
        "priority": json.loads((run_dir / "rules.json").read_text(encoding="utf-8"))["rules"][-1]["priority"],
        "transactions": 4,
    }]
