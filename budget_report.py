#!/usr/bin/env python3
"""
Budget vs. Actual Report

Compares the target values in a dataset's budget.json against the actual
spending in its categorized CSV files, for one month plus the cumulated
period up to that month.

Usage:
    python budget_report.py <run_dir> [--month YYYY-MM]

Example:
    python budget_report.py example
    python budget_report.py example --month 2025-03
"""

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

import pandas as pd

from analyze_by_category import (
    _month_label,
    _resolve_run_directory,
    load_dataset_categorized_csvs,
    load_months_metadata,
)

VALID_PERIODS = {"monthly", "yearly"}
ALLOWED_BUDGET_FIELDS = {"amount", "period", "_note"}

# Only spending is budgeted. Income has no target here, and transfers move
# money between own accounts without being an expense.
NON_BUDGET_TRANSACTION_CATEGORIES = {"income", "transfer"}


@dataclass
class BudgetLine:
    """One budgeted category, compared for a single month and cumulated."""

    category: str
    target: float
    actual: float
    ytd_target: float
    ytd_actual: float

    @property
    def variance(self) -> float:
        """Actual minus target; positive means over budget."""
        return self.actual - self.target

    @property
    def variance_pct(self) -> Optional[float]:
        if self.target == 0:
            return None
        return self.variance / self.target * 100

    @property
    def ytd_variance(self) -> float:
        return self.ytd_actual - self.ytd_target


@dataclass
class BudgetComparison:
    """Result of comparing a budget against one month of actuals."""

    month: str
    lines: list
    unbudgeted: list  # (category, actual, ytd_actual) without a budget line
    without_actuals: list  # budgeted categories that never occur in the data


def load_budget(budget_path) -> dict:
    """Load and validate a budget.json.

    Keys are categories as the rule set produces them, values are objects with
    'amount', 'period' and an optional '_note'.
    """
    path = Path(budget_path)
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    if not isinstance(raw, dict):
        raise ValueError(
            f"budget.json must be a JSON object, got {type(raw).__name__}: {path}"
        )

    for category, entry in raw.items():
        if not isinstance(entry, dict):
            raise ValueError(
                f"Budget entry for '{category}' must be an object, got "
                f"{type(entry).__name__}: {path}"
            )

        unknown_fields = set(entry.keys()) - ALLOWED_BUDGET_FIELDS
        if unknown_fields:
            raise ValueError(
                f"Unknown field(s) {sorted(unknown_fields)} in budget entry for "
                f"'{category}' in {path}. Allowed: {sorted(ALLOWED_BUDGET_FIELDS)}"
            )

        amount = entry.get("amount")
        if not isinstance(amount, (int, float)) or isinstance(amount, bool):
            raise ValueError(
                f"'amount' in budget entry for '{category}' must be a number "
                f"in {path}, got {amount!r}."
            )

        period = entry.get("period")
        if period not in VALID_PERIODS:
            raise ValueError(
                f"Invalid 'period' {period!r} in budget entry for '{category}' "
                f"in {path}. Allowed: {sorted(VALID_PERIODS)}"
            )

        note = entry.get("_note")
        if note is not None and not isinstance(note, str):
            raise ValueError(
                f"'_note' in budget entry for '{category}' must be a string in {path}."
            )

    return raw


def monthly_target(entry: dict) -> float:
    """Target for a single month; a yearly amount is spread evenly."""
    if entry["period"] == "yearly":
        return entry["amount"] / 12
    return entry["amount"]


def spending_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Return only the rows a budget is about: neither income nor transfers.

    Rows without a transaction category are kept: they are uncategorized
    spending and should stay visible.
    """
    if "Transaction Category" not in df.columns:
        return df.copy()
    tc = df["Transaction Category"].fillna("").astype(str).str.lower()
    return df[~tc.isin(NON_BUDGET_TRANSACTION_CATEGORIES)].copy()


def net_by_category(df: pd.DataFrame) -> dict:
    """Net spending per category: debits minus credits.

    Subtracting credits is what nets refunds against the category they belong
    to. A refund that carries no expense category (the catch-all rules) forms
    its own category instead, and shows up as unbudgeted.
    """
    if df.empty:
        return {}
    grouped = df.groupby("Category")[["Debit in CHF", "Credit in CHF"]].sum()
    return {
        category: round(row["Debit in CHF"] - row["Credit in CHF"], 2)
        for category, row in grouped.iterrows()
    }


def _rows_for_months(df: pd.DataFrame, months: Sequence[str]) -> pd.DataFrame:
    return df[df["Date"].dt.strftime("%Y-%m").isin(list(months))]


def compare_budget_to_actuals(
    df: pd.DataFrame,
    budget: dict,
    months: Sequence[str],
    month: str,
) -> BudgetComparison:
    """Compare *budget* against the actuals in *df* for *month*.

    Cumulated values run over the months in *months* up to and including
    *month*, so they follow the dataset's own period rather than the calendar.
    """
    months = list(months)
    if month not in months:
        raise ValueError(
            f"Month '{month}' is not part of this dataset. "
            f"Available: {', '.join(months)}"
        )

    cumulated_months = months[: months.index(month) + 1]

    spending = spending_rows(df)
    actuals = net_by_category(_rows_for_months(spending, [month]))
    ytd_actuals = net_by_category(_rows_for_months(spending, cumulated_months))

    lines = []
    for category in sorted(budget):
        target = monthly_target(budget[category])
        lines.append(
            BudgetLine(
                category=category,
                target=target,
                actual=actuals.get(category, 0.0),
                ytd_target=target * len(cumulated_months),
                ytd_actual=ytd_actuals.get(category, 0.0),
            )
        )

    # Cumulated, so that a category which only occurred in an earlier month
    # does not silently drop out of the report.
    unbudgeted = sorted(
        (category, actuals.get(category, 0.0), ytd_amount)
        for category, ytd_amount in ytd_actuals.items()
        if category not in budget
    )
    without_actuals = sorted(
        category for category in budget if category not in ytd_actuals
    )

    return BudgetComparison(
        month=month,
        lines=lines,
        unbudgeted=unbudgeted,
        without_actuals=without_actuals,
    )


def _fmt(value: Optional[float]) -> str:
    """Format an amount in Swiss notation, e.g. -1'369.40."""
    if value is None:
        return "—"
    return f"{value:,.2f}".replace(",", "'")


def _fmt_pct(value: Optional[float]) -> str:
    if value is None:
        return "—"
    return f"{value:+.0f}%"


def format_report(comparison: BudgetComparison, source_label: str) -> str:
    """Render the comparison as a plain-text table."""
    out = []
    out.append(f"Budget vs. Ist — {source_label}, {_month_label(comparison.month)}")
    out.append("")
    out.append(
        f"{'Kategorie':<20}{'Soll':>12}{'Ist':>12}{'Abw.':>12}{'Abw.%':>8}"
        f"{'Kum. Soll':>14}{'Kum. Ist':>12}{'Kum. Abw.':>12}"
    )
    out.append("-" * 102)

    for line in comparison.lines:
        out.append(
            f"{line.category:<20}"
            f"{_fmt(line.target):>12}{_fmt(line.actual):>12}"
            f"{_fmt(line.variance):>12}{_fmt_pct(line.variance_pct):>8}"
            f"{_fmt(line.ytd_target):>14}{_fmt(line.ytd_actual):>12}"
            f"{_fmt(line.ytd_variance):>12}"
        )

    if comparison.lines:
        out.append("-" * 102)
        out.append(
            f"{'Summe':<20}"
            f"{_fmt(sum(l.target for l in comparison.lines)):>12}"
            f"{_fmt(sum(l.actual for l in comparison.lines)):>12}"
            f"{_fmt(sum(l.variance for l in comparison.lines)):>12}"
            f"{'':>8}"
            f"{_fmt(sum(l.ytd_target for l in comparison.lines)):>14}"
            f"{_fmt(sum(l.ytd_actual for l in comparison.lines)):>12}"
            f"{_fmt(sum(l.ytd_variance for l in comparison.lines)):>12}"
        )

    if comparison.unbudgeted:
        out.append("")
        out.append("Ohne Budgetzeile (Ist vorhanden):")
        for category, amount, ytd_amount in comparison.unbudgeted:
            # Widths line the two amounts up under 'Ist' and 'Kum. Ist'.
            out.append(f"   {category:<17}{_fmt(amount):>24}{_fmt(ytd_amount):>46}")

    if comparison.without_actuals:
        out.append("")
        out.append("Ohne Ist-Werte (Budget vorhanden):")
        for category in comparison.without_actuals:
            out.append(f"   {category}")

    return "\n".join(out)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compare a dataset's budget.json against its actual spending."
    )
    parser.add_argument(
        "run_dir",
        help="Dataset directory or shorthand under data/ (for example: example)",
    )
    parser.add_argument(
        "--month",
        help="Month to report, as YYYY-MM (default: the dataset's last month)",
    )
    args = parser.parse_args(argv)

    try:
        run_dir = _resolve_run_directory(args.run_dir)
    except FileNotFoundError as e:
        print(f"❌ {e}")
        return 1

    budget_path = run_dir / "budget.json"
    if not budget_path.exists():
        print(f"❌ Budget file not found: {budget_path}")
        return 1

    try:
        budget = load_budget(budget_path)
    except (ValueError, json.JSONDecodeError) as e:
        print(f"❌ {e}")
        return 1

    try:
        df, file_count = load_dataset_categorized_csvs(run_dir)
        months = load_months_metadata(run_dir)
    except Exception as e:
        print(f"❌ {e}")
        return 1

    if not months:
        print(f"❌ No months recorded in {run_dir / 'metadata' / 'months.json'}")
        return 1

    month = args.month or months[-1]
    try:
        comparison = compare_budget_to_actuals(df, budget, months, month)
    except ValueError as e:
        print(f"❌ {e}")
        return 1

    source_label = f"{run_dir} ({file_count} categorized file(s))"
    print(format_report(comparison, source_label))
    return 0


if __name__ == "__main__":
    sys.exit(main())
