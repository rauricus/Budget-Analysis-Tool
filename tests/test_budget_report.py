#!/usr/bin/env python3
"""Tests for budget_report: loading budget.json and comparing it to actuals."""
import json
import os
import sys
from datetime import datetime

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from budget_report import (
    compare_budget_to_actuals,
    format_report,
    load_budget,
    main,
    monthly_target,
    net_by_category,
    spending_rows,
)

MONTHS = ["2025-01", "2025-02", "2025-03"]


def _write(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")


def _rows(*specs) -> pd.DataFrame:
    """Build a categorized dataframe from (month, transaction_category,
    category, debit, credit) tuples."""
    columns = ["Date", "Transaction Category", "Category",
               "Debit in CHF", "Credit in CHF"]
    records = []
    for month, transaction_category, category, debit, credit in specs:
        year, mon = map(int, month.split("-"))
        records.append({
            "Date": datetime(year, mon, 15),
            "Transaction Category": transaction_category,
            "Category": category,
            "Debit in CHF": debit,
            "Credit in CHF": credit,
        })
    df = pd.DataFrame(records, columns=columns)
    df["Date"] = pd.to_datetime(df["Date"])
    return df


# ---------------------------------------------------------------------------
# Loading & Validation
# ---------------------------------------------------------------------------

class TestLoading:
    def test_loads_empty_file(self, tmp_path):
        f = tmp_path / "budget.json"
        _write(f, {})
        assert load_budget(f) == {}

    def test_loads_entries(self, tmp_path):
        f = tmp_path / "budget.json"
        _write(f, {
            "Wohnen": {"amount": 1900.0, "period": "monthly"},
            "Finanzen": {"amount": 2400, "period": "yearly", "_note": "jährlich"},
        })
        budget = load_budget(f)
        assert budget["Wohnen"]["amount"] == 1900.0
        assert budget["Finanzen"]["period"] == "yearly"

    def test_rejects_non_object_document(self, tmp_path):
        f = tmp_path / "budget.json"
        _write(f, [{"Wohnen": 1900}])
        with pytest.raises(ValueError, match="must be a JSON object"):
            load_budget(f)

    def test_rejects_non_object_entry(self, tmp_path):
        f = tmp_path / "budget.json"
        _write(f, {"Wohnen": 1900})
        with pytest.raises(ValueError, match="must be an object"):
            load_budget(f)

    def test_rejects_unknown_field(self, tmp_path):
        f = tmp_path / "budget.json"
        _write(f, {"Wohnen": {"amount": 1, "period": "monthly", "type": "fixed"}})
        with pytest.raises(ValueError, match="Unknown field"):
            load_budget(f)

    def test_rejects_invalid_period(self, tmp_path):
        f = tmp_path / "budget.json"
        _write(f, {"Wohnen": {"amount": 1, "period": "quarterly"}})
        with pytest.raises(ValueError, match="Invalid 'period'"):
            load_budget(f)

    def test_rejects_missing_period(self, tmp_path):
        f = tmp_path / "budget.json"
        _write(f, {"Wohnen": {"amount": 1}})
        with pytest.raises(ValueError, match="Invalid 'period'"):
            load_budget(f)

    def test_rejects_non_numeric_amount(self, tmp_path):
        f = tmp_path / "budget.json"
        _write(f, {"Wohnen": {"amount": "1900", "period": "monthly"}})
        with pytest.raises(ValueError, match="must be a number"):
            load_budget(f)

    def test_rejects_boolean_amount(self, tmp_path):
        f = tmp_path / "budget.json"
        _write(f, {"Wohnen": {"amount": True, "period": "monthly"}})
        with pytest.raises(ValueError, match="must be a number"):
            load_budget(f)

    def test_rejects_non_string_note(self, tmp_path):
        f = tmp_path / "budget.json"
        _write(f, {"Wohnen": {"amount": 1, "period": "monthly", "_note": 5}})
        with pytest.raises(ValueError, match="must be a string"):
            load_budget(f)


# ---------------------------------------------------------------------------
# Targets and actuals
# ---------------------------------------------------------------------------

class TestTargetsAndActuals:
    def test_monthly_target_is_the_amount(self):
        assert monthly_target({"amount": 150.0, "period": "monthly"}) == 150.0

    def test_yearly_target_is_pro_rata(self):
        assert monthly_target({"amount": 2400.0, "period": "yearly"}) == 200.0

    def test_spending_rows_exclude_income_and_transfers(self):
        df = _rows(
            ("2025-01", "Expense", "Wohnen", 100.0, 0.0),
            ("2025-01", "Income", "Einkommen", 0.0, 5000.0),
            ("2025-01", "Transfer", "Überträge", 0.0, 450.0),
        )
        assert list(spending_rows(df)["Category"]) == ["Wohnen"]

    def test_spending_rows_keep_rows_without_transaction_category(self):
        df = _rows(
            ("2025-01", None, "Uncategorized", 12.4, 0.0),
            ("2025-01", "Income", "Einkommen", 0.0, 5000.0),
        )
        assert list(spending_rows(df)["Category"]) == ["Uncategorized"]

    def test_refunds_are_netted_against_their_category(self):
        df = _rows(
            ("2025-01", "Expense", "Leben", 500.0, 0.0),
            ("2025-01", "Refund", "Leben", 0.0, 200.0),
        )
        assert net_by_category(spending_rows(df)) == {"Leben": 300.0}

    def test_unattributable_refund_forms_its_own_category(self):
        df = _rows(
            ("2025-01", "Expense", "Leben", 500.0, 0.0),
            ("2025-01", "Refund", "Rückerstattungen", 0.0, 1.0),
        )
        assert net_by_category(spending_rows(df)) == {
            "Leben": 500.0,
            "Rückerstattungen": -1.0,
        }

    def test_net_by_category_on_empty_frame(self):
        assert net_by_category(_rows()) == {}


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------

class TestComparison:
    def test_target_actual_and_variance(self):
        df = _rows(("2025-01", "Expense", "Wohnen", 1950.0, 0.0))
        budget = {"Wohnen": {"amount": 1900.0, "period": "monthly"}}

        line = compare_budget_to_actuals(df, budget, MONTHS, "2025-01").lines[0]

        assert line.target == 1900.0
        assert line.actual == 1950.0
        assert line.variance == 50.0
        assert round(line.variance_pct, 4) == round(50 / 1900 * 100, 4)

    def test_variance_pct_is_none_for_a_zero_target(self):
        df = _rows(("2025-01", "Expense", "Wohnen", 10.0, 0.0))
        budget = {"Wohnen": {"amount": 0.0, "period": "monthly"}}

        line = compare_budget_to_actuals(df, budget, MONTHS, "2025-01").lines[0]

        assert line.variance_pct is None

    def test_yearly_line_is_compared_pro_rata(self):
        df = _rows(("2025-01", "Expense", "Finanzen", 2400.0, 0.0))
        budget = {"Finanzen": {"amount": 2400.0, "period": "yearly"}}

        line = compare_budget_to_actuals(df, budget, MONTHS, "2025-01").lines[0]

        assert line.target == 200.0
        assert line.variance == 2200.0

    def test_cumulation_runs_up_to_the_selected_month(self):
        df = _rows(
            ("2025-01", "Expense", "Wohnen", 100.0, 0.0),
            ("2025-02", "Expense", "Wohnen", 200.0, 0.0),
            ("2025-03", "Expense", "Wohnen", 400.0, 0.0),
        )
        budget = {"Wohnen": {"amount": 150.0, "period": "monthly"}}

        line = compare_budget_to_actuals(df, budget, MONTHS, "2025-02").lines[0]

        assert line.actual == 200.0
        assert line.ytd_actual == 300.0
        assert line.ytd_target == 300.0
        assert line.ytd_variance == 0.0

    def test_months_after_the_selected_one_are_ignored(self):
        df = _rows(("2025-03", "Expense", "Wohnen", 999.0, 0.0))
        budget = {"Wohnen": {"amount": 150.0, "period": "monthly"}}

        line = compare_budget_to_actuals(df, budget, MONTHS, "2025-01").lines[0]

        assert line.actual == 0.0
        assert line.ytd_actual == 0.0

    def test_lines_are_sorted_by_category(self):
        budget = {
            "Wohnen": {"amount": 1.0, "period": "monthly"},
            "Einkaufen": {"amount": 1.0, "period": "monthly"},
        }
        comparison = compare_budget_to_actuals(_rows(), budget, MONTHS, "2025-01")

        assert [l.category for l in comparison.lines] == ["Einkaufen", "Wohnen"]

    def test_unbudgeted_categories_are_listed(self):
        df = _rows(("2025-01", "Expense", "Mobilität", 96.9, 0.0))
        comparison = compare_budget_to_actuals(df, {}, MONTHS, "2025-01")

        assert comparison.unbudgeted == [("Mobilität", 96.9, 96.9)]

    def test_unbudgeted_category_from_an_earlier_month_stays_visible(self):
        df = _rows(("2025-01", "Expense", "Mobilität", 96.9, 0.0))
        comparison = compare_budget_to_actuals(df, {}, MONTHS, "2025-02")

        assert comparison.unbudgeted == [("Mobilität", 0.0, 96.9)]

    def test_budget_lines_without_any_actuals_are_listed(self):
        budget = {"Mobilität": {"amount": 100.0, "period": "monthly"}}
        comparison = compare_budget_to_actuals(_rows(), budget, MONTHS, "2025-01")

        assert comparison.without_actuals == ["Mobilität"]

    def test_budget_line_with_actuals_is_not_listed_as_missing(self):
        df = _rows(("2025-01", "Expense", "Mobilität", 10.0, 0.0))
        budget = {"Mobilität": {"amount": 100.0, "period": "monthly"}}
        comparison = compare_budget_to_actuals(df, budget, MONTHS, "2025-01")

        assert comparison.without_actuals == []

    def test_unknown_month_is_rejected(self):
        with pytest.raises(ValueError, match="not part of this dataset"):
            compare_budget_to_actuals(_rows(), {}, MONTHS, "2025-12")

    def test_report_renders_categories_and_gaps(self):
        df = _rows(
            ("2025-01", "Expense", "Wohnen", 1950.0, 0.0),
            ("2025-01", "Expense", "Mobilität", 96.9, 0.0),
        )
        budget = {"Wohnen": {"amount": 1900.0, "period": "monthly"}}
        comparison = compare_budget_to_actuals(df, budget, MONTHS, "2025-01")

        text = format_report(comparison, "data/test")

        assert "January 2025" in text
        assert "Wohnen" in text
        assert "1'950.00" in text
        assert "Ohne Budgetzeile" in text
        assert "Mobilität" in text


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

class TestCli:
    def test_runs_on_the_example_dataset(self, capsys):
        assert main(["example"]) == 0
        out = capsys.readouterr().out
        assert "Budget vs. Ist" in out
        assert "Wohnen" in out

    def test_month_flag_selects_the_month(self, capsys):
        assert main(["example", "--month", "2025-03"]) == 0
        assert "March 2025" in capsys.readouterr().out

    def test_unknown_month_exits_with_an_error(self, capsys):
        assert main(["example", "--month", "2025-12"]) == 1
        assert "not part of this dataset" in capsys.readouterr().out

    def test_missing_run_dir_exits_with_an_error(self, capsys):
        assert main(["does-not-exist"]) == 1
        assert "Run directory not found" in capsys.readouterr().out

    def test_missing_budget_file_exits_with_an_error(self, capsys):
        assert main(["reference"]) == 1
        assert "Budget file not found" in capsys.readouterr().out
