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
from doctor import _render_text_report, build_doctor_report, count_findings, main


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



def test_review_of_a_split_rule_shows_the_remainder(tmp_path):
    """For fixed parts plus a variable rest, the rest is what the review checks."""
    run_dir = _copy_example(tmp_path)

    def edit(rules, _):
        rules["housing_1"]["review"] = "Rest nur Nebenkosten?"
        rules["housing_1"]["split"] = [
            {"amount": 1500.00, "subcategory": "Miete", "category": "Wohnen"},
            {"transaction_category": "Refund", "category": "Wohnen", "subcategory": "Nebenkosten"},
        ]
    _edit_rules(run_dir, edit)

    report = build_doctor_report(run_dir)
    remainders = {item["transaction_id"]: item["remainder"] for item in report["to_review"]}

    assert remainders["TX-000009"] == {
        "amount": 274.00, "transaction_category": "Refund", "category": "Wohnen", "subcategory": "Nebenkosten",
    }
    assert "remainder 274.00 -> Refund / Wohnen / Nebenkosten" in _render_text_report(report)


def test_review_of_a_split_rule_with_an_inheriting_remainder(tmp_path):
    run_dir = _copy_example(tmp_path)

    def edit(rules, _):
        rules["housing_1"]["review"] = "Rest nur Miete?"
        rules["housing_1"]["split"] = [{"amount": 1700.00, "category": "Wohnen"}, {}]
    _edit_rules(run_dir, edit)

    item = build_doctor_report(run_dir)["to_review"][0]

    assert item["remainder"] == {
        "amount": 74.00, "transaction_category": "Expense", "category": "Wohnen", "subcategory": "Miete und Hypothek",
    }


def test_review_of_a_split_rule_without_remainder_says_so(tmp_path):
    run_dir = _copy_example(tmp_path)

    def edit(rules, _):
        rules["housing_1"]["review"] = "Nur Miete?"
        rules["housing_1"]["split"] = [{"amount": 1774.00, "category": "Wohnen"}, {}]
    _edit_rules(run_dir, edit)

    report = build_doctor_report(run_dir)

    assert report["to_review"][0]["remainder"]["amount"] == 0
    assert "remainder 0.00, no part" in _render_text_report(report)

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
    # The example budget carries deliberate findings of its own.
    (run_dir / "budget.json").unlink()
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
        {"files": ["export.202504-copy.csv", "export.202504.csv"], "transactions": 16},
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


def _edit_budget(run_dir: Path, edit, name: str = "budget.json") -> None:
    path = run_dir / name
    data = json.loads(path.read_text(encoding="utf-8"))
    edit(data)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def test_example_budget_has_one_unproduced_entry_and_one_income_question(tmp_path):
    findings = build_doctor_report(_copy_example(tmp_path))["budget_findings"]

    assert findings["unproduced_entries"] == [{
        "section": "budget",
        "name": "Freizeit / Sport",
        "scope": "Freizeit / Sport",
        "suggestion": None,
    }]
    assert findings["income_above_plan"] == [{"month": "2025-03", "planned": 4200.0, "actual": 5700.0}]


def test_category_only_an_override_produces_counts_as_produced(tmp_path):
    run_dir = _copy_example(tmp_path)
    _edit_budget(run_dir, lambda b: b["budget"].update({
        "Freizeit / Kultur": {"amount": 1, "period": "monthly", "group": "discretionary"},
    }))

    names = [i["name"] for i in build_doctor_report(run_dir)["budget_findings"]["unproduced_entries"]]
    assert "Freizeit / Kultur" not in names


def test_unknown_reserve_and_whole_category_are_reported(tmp_path):
    run_dir = _copy_example(tmp_path)

    def edit(budget):
        budget["reserves"]["Säule 3a"]["subcategory"] = "Saeule 3a"
        budget["budget"]["Freizeitt"] = {"amount": 1, "period": "monthly", "group": "discretionary"}

    _edit_budget(run_dir, edit)

    items = {i["name"]: i for i in build_doctor_report(run_dir)["budget_findings"]["unproduced_entries"]}
    assert items["Säule 3a"]["section"] == "reserves"
    assert items["Säule 3a"]["suggestion"] == "Vorsorge / Säule 3a"
    assert items["Freizeitt"]["suggestion"] == "Freizeit"


def test_income_within_the_margin_is_not_questioned(tmp_path):
    run_dir = _copy_example(tmp_path)
    _edit_budget(run_dir, lambda b: b["income"].update(amount=5000))

    assert build_doctor_report(run_dir)["budget_findings"]["income_above_plan"] == []



def test_income_by_source_is_checked_against_the_rules_and_summed_for_the_plan(tmp_path):
    run_dir = _copy_example(tmp_path)
    _edit_budget(run_dir, lambda b: b.update(income={
        "Einkommen / Lohn": {"amount": 4000, "period": "monthly"},
        "Einkommen / Bonus": {"amount": 1500, "period": "yearly"},
        "Einkommen / Familienzulage": {"amount": 200, "period": "monthly"},
    }))

    findings = build_doctor_report(run_dir)["budget_findings"]

    # No rule produces Bonus or Familienzulage in the example; Lohn exists.
    assert [(i["section"], i["name"]) for i in findings["unproduced_entries"] if i["section"] == "income"] == [
        ("income", "Einkommen / Bonus"), ("income", "Einkommen / Familienzulage"),
    ]
    assert findings["income_above_plan"] == [{"month": "2025-03", "planned": 4325.0, "actual": 5700.0}]


def test_dataset_without_budget_has_no_budget_findings(tmp_path):
    run_dir = _copy_example(tmp_path)
    (run_dir / "budget.json").unlink()

    report = build_doctor_report(run_dir)

    assert report["budget_findings"] == {"unproduced_entries": [], "income_above_plan": []}


def test_budget_flag_checks_another_file(tmp_path, capsys):
    run_dir = _copy_example(tmp_path)
    (run_dir / "budget.json").rename(run_dir / "budget-draft.json")
    _edit_budget(
        run_dir,
        lambda b: b["budget"].update({"Mobilitaet": {"amount": 1, "period": "monthly", "group": "essential"}}),
        "budget-draft.json",
    )

    assert main([str(run_dir), "--budget", "budget-draft.json", "--json"]) == 1

    out = json.loads(capsys.readouterr().out)
    assert "Mobilitaet" in [i["name"] for i in out["budget_findings"]["unproduced_entries"]]


def test_missing_budget_file_is_an_error(tmp_path, capsys):
    assert main([str(_copy_example(tmp_path)), "--budget", "nope.json"]) == 2
    assert "Budget file not found" in capsys.readouterr().out
