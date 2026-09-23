#!/usr/bin/env python3
"""Tests for budget_report: loading budget.json and comparing it to actuals."""
import json
import os
import shutil
import sys
from datetime import datetime

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from budget_report import (
    assign_reserves,
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
    category, debit, credit) tuples, optionally followed by a subcategory."""
    columns = ["Date", "Transaction Category", "Category", "Subcategory",
               "Debit in CHF", "Credit in CHF"]
    records = []
    for spec in specs:
        month, transaction_category, category, debit, credit = spec[:5]
        subcategory = spec[5] if len(spec) > 5 else ""
        year, mon = map(int, month.split("-"))
        records.append({
            "Date": datetime(year, mon, 15),
            "Transaction Category": transaction_category,
            "Category": category,
            "Subcategory": subcategory,
            "Debit in CHF": debit,
            "Credit in CHF": credit,
        })
    df = pd.DataFrame(records, columns=columns)
    df["Date"] = pd.to_datetime(df["Date"])
    return df


def _budget(lines=None, reserves=None, income=None) -> dict:
    """A budget as load_budget returns it."""
    return {"income": income, "reserves": reserves or {}, "budget": lines or {}}


# ---------------------------------------------------------------------------
# Loading & Validation
# ---------------------------------------------------------------------------

class TestLoading:
    def test_loads_empty_file(self, tmp_path):
        f = tmp_path / "budget.json"
        _write(f, {})
        assert load_budget(f) == _budget()

    def test_loads_entries(self, tmp_path):
        f = tmp_path / "budget.json"
        _write(f, {"budget": {
            "Wohnen": {"amount": 1900.0, "period": "monthly"},
            "Finanzen": {"amount": 2400, "period": "yearly", "_note": "jährlich"},
        }})
        budget = load_budget(f)["budget"]
        assert budget["Wohnen"]["amount"] == 1900.0
        assert budget["Finanzen"]["period"] == "yearly"

    def test_rejects_non_object_document(self, tmp_path):
        f = tmp_path / "budget.json"
        _write(f, [{"Wohnen": 1900}])
        with pytest.raises(ValueError, match="must be a JSON object"):
            load_budget(f)

    def test_rejects_non_object_entry(self, tmp_path):
        f = tmp_path / "budget.json"
        _write(f, {"budget": {"Wohnen": 1900}})
        with pytest.raises(ValueError, match="must be an object"):
            load_budget(f)

    def test_rejects_unknown_field(self, tmp_path):
        f = tmp_path / "budget.json"
        _write(f, {"budget": {"Wohnen": {"amount": 1, "period": "monthly", "type": "fixed"}}})
        with pytest.raises(ValueError, match="Unknown field"):
            load_budget(f)

    def test_rejects_invalid_period(self, tmp_path):
        f = tmp_path / "budget.json"
        _write(f, {"budget": {"Wohnen": {"amount": 1, "period": "quarterly"}}})
        with pytest.raises(ValueError, match="Invalid 'period'"):
            load_budget(f)

    def test_rejects_missing_period(self, tmp_path):
        f = tmp_path / "budget.json"
        _write(f, {"budget": {"Wohnen": {"amount": 1}}})
        with pytest.raises(ValueError, match="Invalid 'period'"):
            load_budget(f)

    def test_rejects_non_numeric_amount(self, tmp_path):
        f = tmp_path / "budget.json"
        _write(f, {"budget": {"Wohnen": {"amount": "1900", "period": "monthly"}}})
        with pytest.raises(ValueError, match="must be a number"):
            load_budget(f)

    def test_rejects_boolean_amount(self, tmp_path):
        f = tmp_path / "budget.json"
        _write(f, {"budget": {"Wohnen": {"amount": True, "period": "monthly"}}})
        with pytest.raises(ValueError, match="must be a number"):
            load_budget(f)

    def test_rejects_non_string_note(self, tmp_path):
        f = tmp_path / "budget.json"
        _write(f, {"budget": {"Wohnen": {"amount": 1, "period": "monthly", "_note": 5}}})
        with pytest.raises(ValueError, match="must be a string"):
            load_budget(f)

    def test_rejects_unknown_top_level_field(self, tmp_path):
        f = tmp_path / "budget.json"
        _write(f, {"Wohnen": {"amount": 1900, "period": "monthly"}})
        with pytest.raises(ValueError, match="Unknown field"):
            load_budget(f)

    def test_rejects_non_object_section(self, tmp_path):
        f = tmp_path / "budget.json"
        _write(f, {"reserves": []})
        with pytest.raises(ValueError, match="'reserves' must be an object"):
            load_budget(f)

    def test_loads_income_and_reserves(self, tmp_path):
        f = tmp_path / "budget.json"
        _write(f, {
            "income": {"amount": 8000, "period": "monthly"},
            "reserves": {"Steuern": {"amount": 9000, "period": "yearly",
                                     "category": "Steuern"}},
        })
        budget = load_budget(f)
        assert budget["income"]["amount"] == 8000
        assert budget["reserves"]["Steuern"]["category"] == "Steuern"
        assert budget["budget"] == {}

    def test_income_is_validated_like_an_entry(self, tmp_path):
        f = tmp_path / "budget.json"
        _write(f, {"income": {"amount": 8000, "period": "weekly"}})
        with pytest.raises(ValueError, match="Invalid 'period'"):
            load_budget(f)

    def test_rejects_reserve_without_category(self, tmp_path):
        f = tmp_path / "budget.json"
        _write(f, {"reserves": {"Steuern": {"amount": 1, "period": "yearly"}}})
        with pytest.raises(ValueError, match="'category'"):
            load_budget(f)

    def test_rejects_empty_subcategory(self, tmp_path):
        f = tmp_path / "budget.json"
        _write(f, {"reserves": {"KK": {"amount": 1, "period": "yearly",
                                       "category": "Leben", "subcategory": ""}}})
        with pytest.raises(ValueError, match="'subcategory'"):
            load_budget(f)

    def test_rejects_two_reserves_on_the_same_scope(self, tmp_path):
        f = tmp_path / "budget.json"
        entry = {"amount": 1, "period": "yearly",
                 "category": "Leben", "subcategory": "Krankenkasse"}
        _write(f, {"reserves": {"Prämien": entry, "Franchise": entry}})
        with pytest.raises(ValueError, match="both cover"):
            load_budget(f)

    def test_rejects_reserve_and_budget_line_on_the_same_category(self, tmp_path):
        f = tmp_path / "budget.json"
        _write(f, {
            "reserves": {"Steuern": {"amount": 1, "period": "yearly",
                                     "category": "Steuern"}},
            "budget": {"Steuern": {"amount": 1, "period": "monthly"}},
        })
        with pytest.raises(ValueError, match="covered by reserve"):
            load_budget(f)

    def test_allows_reserved_subcategory_next_to_a_budget_line(self, tmp_path):
        f = tmp_path / "budget.json"
        _write(f, {
            "reserves": {"KK": {"amount": 1, "period": "yearly",
                                "category": "Leben", "subcategory": "Krankenkasse"}},
            "budget": {"Leben": {"amount": 1, "period": "monthly"}},
        })
        assert "Leben" in load_budget(f)["budget"]


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
        budget = _budget({"Wohnen": {"amount": 1900.0, "period": "monthly"}})

        line = compare_budget_to_actuals(df, budget, MONTHS, "2025-01").lines[0]

        assert line.target == 1900.0
        assert line.actual == 1950.0
        assert line.variance == 50.0
        assert round(line.variance_pct, 4) == round(50 / 1900 * 100, 4)

    def test_variance_pct_is_none_for_a_zero_target(self):
        df = _rows(("2025-01", "Expense", "Wohnen", 10.0, 0.0))
        budget = _budget({"Wohnen": {"amount": 0.0, "period": "monthly"}})

        line = compare_budget_to_actuals(df, budget, MONTHS, "2025-01").lines[0]

        assert line.variance_pct is None

    def test_yearly_line_is_compared_pro_rata(self):
        df = _rows(("2025-01", "Expense", "Finanzen", 2400.0, 0.0))
        budget = _budget({"Finanzen": {"amount": 2400.0, "period": "yearly"}})

        line = compare_budget_to_actuals(df, budget, MONTHS, "2025-01").lines[0]

        assert line.target == 200.0
        assert line.variance == 2200.0

    def test_cumulation_runs_up_to_the_selected_month(self):
        df = _rows(
            ("2025-01", "Expense", "Wohnen", 100.0, 0.0),
            ("2025-02", "Expense", "Wohnen", 200.0, 0.0),
            ("2025-03", "Expense", "Wohnen", 400.0, 0.0),
        )
        budget = _budget({"Wohnen": {"amount": 150.0, "period": "monthly"}})

        line = compare_budget_to_actuals(df, budget, MONTHS, "2025-02").lines[0]

        assert line.actual == 200.0
        assert line.ytd_actual == 300.0
        assert line.ytd_target == 300.0
        assert line.ytd_variance == 0.0

    def test_months_after_the_selected_one_are_ignored(self):
        df = _rows(("2025-03", "Expense", "Wohnen", 999.0, 0.0))
        budget = _budget({"Wohnen": {"amount": 150.0, "period": "monthly"}})

        line = compare_budget_to_actuals(df, budget, MONTHS, "2025-01").lines[0]

        assert line.actual == 0.0
        assert line.ytd_actual == 0.0

    def test_lines_are_sorted_by_category(self):
        budget = _budget({
            "Wohnen": {"amount": 1.0, "period": "monthly"},
            "Einkaufen": {"amount": 1.0, "period": "monthly"},
        })
        comparison = compare_budget_to_actuals(_rows(), budget, MONTHS, "2025-01")

        assert [l.category for l in comparison.lines] == ["Einkaufen", "Wohnen"]

    def test_unbudgeted_categories_are_listed(self):
        df = _rows(("2025-01", "Expense", "Mobilität", 96.9, 0.0))
        comparison = compare_budget_to_actuals(df, _budget(), MONTHS, "2025-01")

        assert comparison.unbudgeted == [("Mobilität", 96.9, 96.9)]

    def test_unbudgeted_category_from_an_earlier_month_stays_visible(self):
        df = _rows(("2025-01", "Expense", "Mobilität", 96.9, 0.0))
        comparison = compare_budget_to_actuals(df, _budget(), MONTHS, "2025-02")

        assert comparison.unbudgeted == [("Mobilität", 0.0, 96.9)]

    def test_budget_lines_without_any_actuals_are_listed(self):
        budget = _budget({"Mobilität": {"amount": 100.0, "period": "monthly"}})
        comparison = compare_budget_to_actuals(_rows(), budget, MONTHS, "2025-01")

        assert comparison.without_actuals == ["Mobilität"]

    def test_budget_line_with_actuals_is_not_listed_as_missing(self):
        df = _rows(("2025-01", "Expense", "Mobilität", 10.0, 0.0))
        budget = _budget({"Mobilität": {"amount": 100.0, "period": "monthly"}})
        comparison = compare_budget_to_actuals(df, budget, MONTHS, "2025-01")

        assert comparison.without_actuals == []

    def test_unknown_month_is_rejected(self):
        with pytest.raises(ValueError, match="not part of this dataset"):
            compare_budget_to_actuals(_rows(), _budget(), MONTHS, "2025-12")

    def test_report_renders_categories_and_gaps(self):
        df = _rows(
            ("2025-01", "Expense", "Wohnen", 1950.0, 0.0),
            ("2025-01", "Expense", "Mobilität", 96.9, 0.0),
        )
        budget = _budget({"Wohnen": {"amount": 1900.0, "period": "monthly"}})
        comparison = compare_budget_to_actuals(df, budget, MONTHS, "2025-01")

        text = format_report(comparison, "data/test")

        assert "January 2025" in text
        assert "Wohnen" in text
        assert "1'950.00" in text
        assert "Ohne Budgetzeile" in text
        assert "Mobilität" in text


# ---------------------------------------------------------------------------
# Subcategory budget lines
# ---------------------------------------------------------------------------

class TestSubcategoryLines:
    def test_subcategory_line_takes_its_rows_out_of_the_category_line(self):
        df = _rows(
            ("2025-01", "Expense", "Freizeit", 80.0, 0.0, "Gastronomie"),
            ("2025-01", "Expense", "Freizeit", 20.0, 0.0, "Kultur"),
        )
        budget = _budget({
            "Freizeit": {"amount": 50.0, "period": "monthly"},
            "Freizeit / Gastronomie": {"amount": 100.0, "period": "monthly"},
        })

        lines = compare_budget_to_actuals(df, budget, MONTHS, "2025-01").lines

        assert [(l.category, l.actual) for l in lines] == [
            ("Freizeit", 20.0),
            ("Freizeit / Gastronomie", 80.0),
        ]

    def test_refunds_are_netted_on_the_subcategory_line(self):
        df = _rows(
            ("2025-01", "Expense", "Freizeit", 80.0, 0.0, "Gastronomie"),
            ("2025-01", "Refund", "Freizeit", 0.0, 30.0, "Gastronomie"),
        )
        budget = _budget({"Freizeit / Gastronomie": {"amount": 100.0, "period": "monthly"}})

        line = compare_budget_to_actuals(df, budget, MONTHS, "2025-01").lines[0]

        assert line.actual == 50.0

    def test_rest_of_a_category_without_its_own_line_is_unbudgeted(self):
        df = _rows(
            ("2025-01", "Expense", "Freizeit", 80.0, 0.0, "Gastronomie"),
            ("2025-01", "Expense", "Freizeit", 20.0, 0.0, "Kultur"),
        )
        budget = _budget({"Freizeit / Gastronomie": {"amount": 100.0, "period": "monthly"}})

        comparison = compare_budget_to_actuals(df, budget, MONTHS, "2025-01")

        assert comparison.unbudgeted == [("Freizeit", 20.0, 20.0)]
        assert comparison.without_actuals == []

    def test_subcategory_line_without_actuals_is_listed(self):
        budget = _budget({"Freizeit / Gastronomie": {"amount": 100.0, "period": "monthly"}})
        comparison = compare_budget_to_actuals(_rows(), budget, MONTHS, "2025-01")
        assert comparison.without_actuals == ["Freizeit / Gastronomie"]

    def test_slash_without_spaces_stays_part_of_the_name(self):
        df = _rows(("2025-01", "Expense", "Einkaufen", 10.0, 0.0, "Bücher/Filme/Musik"))
        budget = _budget({"Einkaufen / Bücher/Filme/Musik": {"amount": 1.0, "period": "monthly"}})

        line = compare_budget_to_actuals(df, budget, MONTHS, "2025-01").lines[0]

        assert line.actual == 10.0

    def test_rejects_an_empty_part_in_the_key(self, tmp_path):
        f = tmp_path / "budget.json"
        _write(f, {"budget": {"Freizeit / ": {"amount": 1, "period": "monthly"}}})
        with pytest.raises(ValueError, match="must be 'Category' or"):
            load_budget(f)

    def test_rejects_a_line_on_a_reserved_subcategory(self, tmp_path):
        f = tmp_path / "budget.json"
        _write(f, {
            "reserves": {"KK": {"amount": 1, "period": "yearly",
                                "category": "Leben", "subcategory": "Krankenkasse"}},
            "budget": {"Leben / Krankenkasse": {"amount": 1, "period": "monthly"}},
        })
        with pytest.raises(ValueError, match="covered by reserve"):
            load_budget(f)

    def test_rejects_a_subcategory_line_in_a_fully_reserved_category(self, tmp_path):
        f = tmp_path / "budget.json"
        _write(f, {
            "reserves": {"Steuern": {"amount": 1, "period": "yearly", "category": "Steuern"}},
            "budget": {"Steuern / Bund": {"amount": 1, "period": "monthly"}},
        })
        with pytest.raises(ValueError, match="covered by reserve"):
            load_budget(f)

    def test_report_renders_a_long_line_key(self):
        df = _rows(("2025-01", "Expense", "Freizeit", 80.0, 0.0, "Reisen und Erleben"))
        budget = _budget({"Freizeit / Reisen und Erleben": {"amount": 100.0, "period": "monthly"}})
        comparison = compare_budget_to_actuals(df, budget, MONTHS, "2025-01")

        text = format_report(comparison, "data/test")

        assert "Freizeit / Reisen und Erleben   " in text


# ---------------------------------------------------------------------------
# Reserves and availability
# ---------------------------------------------------------------------------

HEALTH = {"amount": 1200.0, "period": "yearly",
          "category": "Leben", "subcategory": "Krankenkasse"}


class TestReserves:
    def test_subcategory_reserve_wins_over_category_reserve(self):
        df = _rows(
            ("2025-01", "Expense", "Leben", 80.0, 0.0, "Krankenkasse"),
            ("2025-01", "Expense", "Leben", 20.0, 0.0, "Familie"),
        )
        reserves = {
            "Leben": {"amount": 1, "period": "yearly", "category": "Leben"},
            "KK": HEALTH,
        }
        assert list(assign_reserves(df, reserves)) == ["KK", "Leben"]

    def test_income_is_never_reserved(self):
        df = _rows(("2025-01", "Income", "Leben", 0.0, 100.0, "Krankenkasse"))
        assert list(assign_reserves(df, {"KK": HEALTH})) == [None]

    def test_transfer_with_a_reserved_category_counts(self):
        df = _rows(("2025-01", "Transfer", "Vorsorge", 588.0, 0.0))
        reserves = {"3a": {"amount": 7056, "period": "yearly", "category": "Vorsorge"}}

        comparison = compare_budget_to_actuals(
            df, _budget(reserves=reserves), MONTHS, "2025-01"
        )

        assert comparison.reserves[0].actual == 588.0

    def test_reserved_rows_leave_the_budget_line_and_unbudgeted_list(self):
        df = _rows(
            ("2025-01", "Expense", "Leben", 80.0, 0.0, "Krankenkasse"),
            ("2025-01", "Expense", "Leben", 20.0, 0.0, "Familie"),
            ("2025-01", "Expense", "Steuern", 500.0, 0.0),
        )
        budget = _budget(
            lines={"Leben": {"amount": 50.0, "period": "monthly"}},
            reserves={
                "KK": HEALTH,
                "Steuern": {"amount": 6000, "period": "yearly", "category": "Steuern"},
            },
        )

        comparison = compare_budget_to_actuals(df, budget, MONTHS, "2025-01")

        assert comparison.lines[0].actual == 20.0
        assert comparison.unbudgeted == []

    def test_reserve_is_a_pot_netted_and_cumulated(self):
        df = _rows(
            ("2025-01", "Expense", "Leben", 300.0, 0.0, "Krankenkasse"),
            ("2025-02", "Refund", "Leben", 0.0, 120.0, "Krankenkasse"),
            ("2025-03", "Expense", "Leben", 999.0, 0.0, "Krankenkasse"),
        )

        line = compare_budget_to_actuals(
            df, _budget(reserves={"KK": HEALTH}), MONTHS, "2025-02"
        ).reserves[0]

        assert line.target == 100.0
        assert line.actual == -120.0
        assert line.ytd_target == 200.0
        assert line.ytd_actual == 180.0
        assert line.balance == 20.0
        assert line.scope == "Leben / Krankenkasse"
        assert line.yearly_amount == 1200.0

    def test_availability_subtracts_reserves_and_budget_lines(self):
        df = _rows(
            ("2025-01", "Income", "Einkommen", 0.0, 5000.0),
            ("2025-02", "Income", "Einkommen", 0.0, 5100.0),
        )
        budget = _budget(
            income={"amount": 5000.0, "period": "monthly"},
            reserves={"KK": HEALTH},
            lines={"Wohnen": {"amount": 1900.0, "period": "monthly"}},
        )

        a = compare_budget_to_actuals(df, budget, MONTHS, "2025-02").availability

        assert a.income_actual == 5100.0
        assert a.ytd_income_actual == 10100.0
        assert a.free == 4900.0
        assert a.unplanned == 3000.0
        assert a.ytd_free == 9800.0
        assert a.ytd_unplanned == 6000.0

    def test_overplanning_shows_as_negative(self):
        budget = _budget(
            income={"amount": 1000.0, "period": "monthly"},
            lines={"Wohnen": {"amount": 1900.0, "period": "monthly"}},
        )
        a = compare_budget_to_actuals(_rows(), budget, MONTHS, "2025-01").availability
        assert a.unplanned == -900.0

    def test_no_income_means_no_availability(self):
        comparison = compare_budget_to_actuals(_rows(), _budget(), MONTHS, "2025-01")
        assert comparison.availability is None

    def test_report_renders_availability_and_reserves(self):
        budget = _budget(
            income={"amount": 5000.0, "period": "monthly"},
            reserves={"KK": HEALTH},
        )
        comparison = compare_budget_to_actuals(_rows(), budget, MONTHS, "2025-01")

        text = format_report(comparison, "data/test")

        assert "Verfügbarkeit" in text
        assert "= Nicht verplant" in text
        assert "Reservation" in text
        assert "KK" in text
        assert "Leben / Krankenkasse" in text

    def test_report_without_income_and_reserves_omits_both_blocks(self):
        comparison = compare_budget_to_actuals(_rows(), _budget(), MONTHS, "2025-01")

        text = format_report(comparison, "data/test")

        assert "Verfügbarkeit" not in text
        assert "Reservation" not in text


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

class TestCli:
    def test_runs_on_the_example_dataset(self, capsys):
        assert main(["example"]) == 0
        out = capsys.readouterr().out
        assert "Budget vs. Ist" in out
        assert "Wohnen" in out
        assert "Krankenkasse" in out

    def test_example_income_is_the_planned_salary_plus_a_bonus(self, capsys):
        # Four months at the planned 4'200 plus one bonus of 1'500 in March.
        assert main(["example"]) == 0
        line = next(
            l for l in capsys.readouterr().out.splitlines()
            if l.startswith("Einkommen Ist")
        )
        assert line.split()[-1] == "18'300.00"

    def test_month_flag_selects_the_month(self, capsys):
        assert main(["example", "--month", "2025-03"]) == 0
        assert "March 2025" in capsys.readouterr().out

    def test_unknown_month_exits_with_an_error(self, capsys):
        assert main(["example", "--month", "2025-12"]) == 1
        assert "not part of this dataset" in capsys.readouterr().out

    def test_report_names_the_budget_file(self, capsys):
        assert main(["example"]) == 0
        assert "Budget: budget.json" in capsys.readouterr().out

    def test_alternative_budget_file_by_path(self, tmp_path, capsys):
        draft = tmp_path / "draft.json"
        _write(draft, {"budget": {"Wohnen": {"amount": 1234.0, "period": "monthly"}}})

        assert main(["example", "--budget", str(draft)]) == 0

        out = capsys.readouterr().out
        assert "Budget: draft.json" in out
        assert "1'234.00" in out
        assert "Krankenkasse" not in out, "Reserves come from the chosen file only"

    def test_alternative_budget_file_inside_the_dataset(self, tmp_path, capsys):
        run_dir = tmp_path / "dataset"
        shutil.copytree("data/example", run_dir)
        _write(run_dir / "budget-2027.json",
               {"budget": {"Wohnen": {"amount": 999.0, "period": "monthly"}}})

        assert main([str(run_dir), "--budget", "budget-2027.json"]) == 0

        out = capsys.readouterr().out
        assert "Budget: budget-2027.json" in out
        assert "999.00" in out

    def test_missing_alternative_budget_file_exits_with_an_error(self, capsys):
        assert main(["example", "--budget", "does-not-exist.json"]) == 1
        assert "Budget file not found" in capsys.readouterr().out

    def test_missing_run_dir_exits_with_an_error(self, capsys):
        assert main(["does-not-exist"]) == 1
        assert "Run directory not found" in capsys.readouterr().out

    def test_missing_budget_file_exits_with_an_error(self, capsys):
        assert main(["reference"]) == 1
        assert "Budget file not found" in capsys.readouterr().out
