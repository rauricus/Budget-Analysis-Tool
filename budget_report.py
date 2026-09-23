#!/usr/bin/env python3
"""
Budget vs. Actual Report

Compares the target values in a dataset's budget.json against the actual
spending in its categorized CSV files, for one month plus the cumulated
period up to that month. Reserves set money aside for known yearly costs
before the rest is distributed over the budget lines, and are tracked as
pots against the transactions they cover.

Usage:
    python budget_report.py <run_dir> [--month YYYY-MM]

Example:
    python budget_report.py example
    python budget_report.py example --month 2025-03
"""

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Sequence

import pandas as pd

from analyze_by_category import (
    _month_label,
    _resolve_run_directory,
    load_dataset_categorized_csvs,
    load_months_metadata,
    spending_rows,
)

VALID_PERIODS = {"monthly", "yearly"}
ALLOWED_SECTIONS = {"income", "reserves", "budget"}
ALLOWED_BUDGET_FIELDS = {"amount", "period", "_note"}
ALLOWED_RESERVE_FIELDS = ALLOWED_BUDGET_FIELDS | {"category", "subcategory"}


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
class ReserveLine:
    """One reserve: money set aside for a known cost, compared as a pot."""

    name: str
    category: str
    subcategory: Optional[str]
    target: float
    actual: float
    ytd_target: float
    ytd_actual: float
    yearly_amount: float

    @property
    def scope(self) -> str:
        """The category, and subcategory if any, whose transactions draw on it."""
        if self.subcategory:
            return f"{self.category} / {self.subcategory}"
        return self.category

    @property
    def balance(self) -> float:
        """What is left in the pot: set aside so far minus spent so far."""
        return self.ytd_target - self.ytd_actual


@dataclass
class Availability:
    """Planned income, what the reserves and budget lines take from it, and
    what is left. Only computed when the budget declares an income."""

    income_target: float
    ytd_income_target: float
    income_actual: float
    ytd_income_actual: float
    reserved: float
    ytd_reserved: float
    budgeted: float
    ytd_budgeted: float

    @property
    def free(self) -> float:
        """Income left for the budget lines once the reserves are taken."""
        return self.income_target - self.reserved

    @property
    def ytd_free(self) -> float:
        return self.ytd_income_target - self.ytd_reserved

    @property
    def unplanned(self) -> float:
        """Income no reserve and no budget line claims; negative if over-planned."""
        return self.free - self.budgeted

    @property
    def ytd_unplanned(self) -> float:
        return self.ytd_free - self.ytd_budgeted


@dataclass
class BudgetComparison:
    """Result of comparing a budget against one month of actuals."""

    month: str
    lines: list
    unbudgeted: list  # (category, actual, ytd_actual) without a budget line
    without_actuals: list  # budgeted categories that never occur in the data
    reserves: list = field(default_factory=list)
    availability: Optional[Availability] = None


def _validate_entry(entry, label: str, allowed_fields: set, path: Path) -> None:
    """Check the fields every budget entry shares: 'amount', 'period', '_note'."""
    if not isinstance(entry, dict):
        raise ValueError(
            f"{label} must be an object, got {type(entry).__name__}: {path}"
        )

    unknown_fields = set(entry.keys()) - allowed_fields
    if unknown_fields:
        raise ValueError(
            f"Unknown field(s) {sorted(unknown_fields)} in {label} in {path}. "
            f"Allowed: {sorted(allowed_fields)}"
        )

    amount = entry.get("amount")
    if not isinstance(amount, (int, float)) or isinstance(amount, bool):
        raise ValueError(
            f"'amount' in {label} must be a number in {path}, got {amount!r}."
        )

    period = entry.get("period")
    if period not in VALID_PERIODS:
        raise ValueError(
            f"Invalid 'period' {period!r} in {label} in {path}. "
            f"Allowed: {sorted(VALID_PERIODS)}"
        )

    note = entry.get("_note")
    if note is not None and not isinstance(note, str):
        raise ValueError(f"'_note' in {label} must be a string in {path}.")


def _validate_section(raw: dict, section: str, path: Path) -> dict:
    value = raw.get(section, {})
    if not isinstance(value, dict):
        raise ValueError(
            f"'{section}' must be an object, got {type(value).__name__}: {path}"
        )
    return value


def load_budget(budget_path) -> dict:
    """Load and validate a budget.json.

    The document has up to three sections, each optional:
    - 'income': one entry with the planned income.
    - 'reserves': name -> entry with 'category' and optional 'subcategory';
      the money is set aside first, and matching transactions draw on it.
    - 'budget': category -> entry, distributing what is left.

    Returns the three sections normalized, with 'income' None when absent.
    """
    path = Path(budget_path)
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    if not isinstance(raw, dict):
        raise ValueError(
            f"budget.json must be a JSON object, got {type(raw).__name__}: {path}"
        )

    unknown_sections = set(raw.keys()) - ALLOWED_SECTIONS
    if unknown_sections:
        raise ValueError(
            f"Unknown field(s) {sorted(unknown_sections)} in {path}. "
            f"Allowed: {sorted(ALLOWED_SECTIONS)}"
        )

    income = raw.get("income")
    if income is not None:
        _validate_entry(income, "'income'", ALLOWED_BUDGET_FIELDS, path)

    budget = _validate_section(raw, "budget", path)
    for category, entry in budget.items():
        _validate_entry(
            entry, f"budget entry for '{category}'", ALLOWED_BUDGET_FIELDS, path
        )

    reserves = _validate_section(raw, "reserves", path)
    claimed = {}
    for name, entry in reserves.items():
        label = f"reserve '{name}'"
        _validate_entry(entry, label, ALLOWED_RESERVE_FIELDS, path)

        category = entry.get("category")
        if not isinstance(category, str) or not category:
            raise ValueError(
                f"'category' in {label} must be a non-empty string in {path}."
            )
        subcategory = entry.get("subcategory")
        if "subcategory" in entry and (
            not isinstance(subcategory, str) or not subcategory
        ):
            raise ValueError(
                f"'subcategory' in {label} must be a non-empty string in {path}."
            )

        target = (category, subcategory)
        if target in claimed:
            raise ValueError(
                f"Reserves '{claimed[target]}' and '{name}' both cover "
                f"{_reserve_scope(entry)} in {path}."
            )
        claimed[target] = name

        # A whole category cannot be reserved and budgeted at once: every
        # transaction in it would count twice. A reserved subcategory is fine,
        # the budget line then sees the category without it.
        if subcategory is None and category in budget:
            raise ValueError(
                f"Category '{category}' is covered by {label} and by a budget "
                f"line in {path}. Reserve a subcategory, or drop one of the two."
            )

    return {"income": income, "reserves": reserves, "budget": budget}


def _reserve_scope(entry: dict) -> str:
    if entry.get("subcategory"):
        return f"{entry['category']} / {entry['subcategory']}"
    return entry["category"]


def monthly_target(entry: dict) -> float:
    """Target for a single month; a yearly amount is spread evenly."""
    if entry["period"] == "yearly":
        return entry["amount"] / 12
    return entry["amount"]


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


def assign_reserves(df: pd.DataFrame, reserves: dict) -> pd.Series:
    """Name of the reserve each row draws on, or None.

    Everything except income is eligible, transfers included: a pillar 3a
    payment typically leaves as a transfer but is exactly what a reserve is
    for. A reserve on a subcategory takes precedence over one on the whole
    category.
    """
    owner = pd.Series([None] * len(df), index=df.index, dtype=object)
    if df.empty or not reserves:
        return owner

    if "Transaction Category" in df.columns:
        tc = df["Transaction Category"].fillna("").astype(str).str.lower()
        eligible = tc != "income"
    else:
        eligible = pd.Series(True, index=df.index)
    category = df["Category"].fillna("").astype(str)
    if "Subcategory" in df.columns:
        subcategory = df["Subcategory"].fillna("").astype(str)
    else:
        subcategory = pd.Series("", index=df.index)

    # Whole-category reserves first, so that subcategory reserves overwrite them.
    for name, entry in sorted(reserves.items(), key=lambda kv: "subcategory" in kv[1]):
        mask = eligible & (category == entry["category"])
        if "subcategory" in entry:
            mask &= subcategory == entry["subcategory"]
        owner[mask] = name
    return owner


def _net_by_reserve(df: pd.DataFrame, owner: pd.Series) -> dict:
    """Debits minus credits per reserve, over the rows of *df*."""
    rows = df[owner.loc[df.index].notna()]
    if rows.empty:
        return {}
    grouped = rows.groupby(owner.loc[rows.index])[["Debit in CHF", "Credit in CHF"]].sum()
    return {
        name: round(row["Debit in CHF"] - row["Credit in CHF"], 2)
        for name, row in grouped.iterrows()
    }


def _income_actual(df: pd.DataFrame) -> float:
    """Credits minus debits over the rows categorized as income."""
    if df.empty or "Transaction Category" not in df.columns:
        return 0.0
    tc = df["Transaction Category"].fillna("").astype(str).str.lower()
    rows = df[tc == "income"]
    return round(rows["Credit in CHF"].sum() - rows["Debit in CHF"].sum(), 2)


def _rows_for_months(df: pd.DataFrame, months: Sequence[str]) -> pd.DataFrame:
    return df[df["Date"].dt.strftime("%Y-%m").isin(list(months))]


def compare_budget_to_actuals(
    df: pd.DataFrame,
    budget: dict,
    months: Sequence[str],
    month: str,
) -> BudgetComparison:
    """Compare *budget*, as returned by load_budget, against the actuals in *df*
    for *month*.

    Cumulated values run over the months in *months* up to and including
    *month*, so they follow the dataset's own period rather than the calendar.
    Rows a reserve claims count against that reserve only, never against a
    budget line or the unbudgeted list.
    """
    months = list(months)
    if month not in months:
        raise ValueError(
            f"Month '{month}' is not part of this dataset. "
            f"Available: {', '.join(months)}"
        )

    cumulated_months = months[: months.index(month) + 1]
    n_months = len(cumulated_months)
    lines_budget = budget.get("budget", {})
    reserves = budget.get("reserves", {})
    income = budget.get("income")

    month_rows = _rows_for_months(df, [month])
    cumulated_rows = _rows_for_months(df, cumulated_months)

    owner = assign_reserves(df, reserves)
    reserve_actuals = _net_by_reserve(month_rows, owner)
    ytd_reserve_actuals = _net_by_reserve(cumulated_rows, owner)

    unreserved = df[owner.isna()]
    spending = spending_rows(unreserved)
    actuals = net_by_category(_rows_for_months(spending, [month]))
    ytd_actuals = net_by_category(_rows_for_months(spending, cumulated_months))

    lines = []
    for category in sorted(lines_budget):
        target = monthly_target(lines_budget[category])
        lines.append(
            BudgetLine(
                category=category,
                target=target,
                actual=actuals.get(category, 0.0),
                ytd_target=target * n_months,
                ytd_actual=ytd_actuals.get(category, 0.0),
            )
        )

    reserve_lines = []
    for name in sorted(reserves):
        entry = reserves[name]
        target = monthly_target(entry)
        reserve_lines.append(
            ReserveLine(
                name=name,
                category=entry["category"],
                subcategory=entry.get("subcategory"),
                target=target,
                actual=reserve_actuals.get(name, 0.0),
                ytd_target=target * n_months,
                ytd_actual=ytd_reserve_actuals.get(name, 0.0),
                yearly_amount=target * 12,
            )
        )

    availability = None
    if income is not None:
        income_target = monthly_target(income)
        reserved = sum(line.target for line in reserve_lines)
        budgeted = sum(line.target for line in lines)
        availability = Availability(
            income_target=income_target,
            ytd_income_target=income_target * n_months,
            income_actual=_income_actual(month_rows),
            ytd_income_actual=_income_actual(cumulated_rows),
            reserved=reserved,
            ytd_reserved=reserved * n_months,
            budgeted=budgeted,
            ytd_budgeted=budgeted * n_months,
        )

    # Cumulated, so that a category which only occurred in an earlier month
    # does not silently drop out of the report.
    unbudgeted = sorted(
        (category, actuals.get(category, 0.0), ytd_amount)
        for category, ytd_amount in ytd_actuals.items()
        if category not in lines_budget
    )
    without_actuals = sorted(
        category for category in lines_budget if category not in ytd_actuals
    )

    return BudgetComparison(
        month=month,
        lines=lines,
        unbudgeted=unbudgeted,
        without_actuals=without_actuals,
        reserves=reserve_lines,
        availability=availability,
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

    a = comparison.availability
    if a is not None:
        out.append("")
        out.append(f"{'Verfügbarkeit':<20}{'Monat':>12}{'Kum.':>14}")
        out.append("-" * 46)
        for label, value, ytd_value in (
            ("Einkommen Soll", a.income_target, a.ytd_income_target),
            ("Einkommen Ist", a.income_actual, a.ytd_income_actual),
            ("− Reservationen", a.reserved, a.ytd_reserved),
            ("= Frei verteilbar", a.free, a.ytd_free),
            ("− Budgetiert", a.budgeted, a.ytd_budgeted),
            ("= Nicht verplant", a.unplanned, a.ytd_unplanned),
        ):
            out.append(f"{label:<20}{_fmt(value):>12}{_fmt(ytd_value):>14}")

    if comparison.reserves:
        out.append("")
        out.append(
            f"{'Reservation':<20}{'Kategorie':<28}{'Soll':>12}{'Ist':>12}"
            f"{'Kum. Soll':>14}{'Kum. Ist':>12}{'Topf':>12}{'Jahr':>12}"
        )
        out.append("-" * 122)
        for r in comparison.reserves:
            out.append(
                f"{r.name:<20}{r.scope:<28}{_fmt(r.target):>12}{_fmt(r.actual):>12}"
                f"{_fmt(r.ytd_target):>14}{_fmt(r.ytd_actual):>12}"
                f"{_fmt(r.balance):>12}{_fmt(r.yearly_amount):>12}"
            )
        out.append("-" * 122)
        out.append(
            f"{'Summe':<48}"
            f"{_fmt(sum(r.target for r in comparison.reserves)):>12}"
            f"{_fmt(sum(r.actual for r in comparison.reserves)):>12}"
            f"{_fmt(sum(r.ytd_target for r in comparison.reserves)):>14}"
            f"{_fmt(sum(r.ytd_actual for r in comparison.reserves)):>12}"
            f"{_fmt(sum(r.balance for r in comparison.reserves)):>12}"
            f"{_fmt(sum(r.yearly_amount for r in comparison.reserves)):>12}"
        )

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
