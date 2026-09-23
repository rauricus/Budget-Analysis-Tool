#!/usr/bin/env python3
"""
Budget Analysis by Category

Analyzes categorized CSV files and generates an Excel report with:
- Summary tables by category and subcategory
- Charts for visual analysis
- Every transaction in one filterable table, to trace a figure back to its bookings
- The largest payees per subcategory, to see what drives a line
- Flexibility for users to modify and customize

Usage:
    python analyze_by_category.py <run_dir> [output_excel_file]

Example:
    python analyze_by_category.py example
    python analyze_by_category.py data/example
    python analyze_by_category.py private my_analysis.xlsx
"""

import calendar
import json
import re
import sys
from pathlib import Path
import numbers
from typing import Optional, Sequence, Tuple
import pandas as pd
from openpyxl import Workbook
from openpyxl.chart import PieChart, BarChart, Reference
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
from openpyxl.utils.dataframe import dataframe_to_rows


REQUIRED_COLUMNS = {
    'Category',
    'Subcategory',
    'Credit in CHF',
    'Debit in CHF',
}

OVERVIEW_TABLE_HEADER_GAP = 22
SHEET_TITLE_FONT_SIZE = 16
SUBTITLE_FONT_SIZE = 14
TOP_NOTE_CONTENT_START_ROW = 5
HEADER_FILL = PatternFill(start_color='366092', end_color='366092', fill_type='solid')
TRANSACTIONS_SHEET = 'Transactions'
CHECK_LABEL = 'Check (Transactions)'
DIFFERENCE_LABEL = 'Difference'
AMOUNT_FORMAT = '#,##0.00'
TOP_PAYEES_PER_SUBCATEGORY = 10
OTHER_PAYEES_LABEL = '(übrige)'

# Only spending is budgeted. Income has no target, and transfers move money
# between own accounts without being an expense. Shared with budget_report.py,
# so that the Excel report and the budget agree on what a line contains.
NON_SPENDING_TRANSACTION_CATEGORIES = {"income", "transfer"}

# Branch numbers in parentheses split one merchant into many payees,
# e.g. 'MIGROS MARKTHALLE (8812)'.
_BRANCH_NUMBER = re.compile(r"\s*\(\d+\)")
# Some payment orders carry the sender's reference inside the counterparty
# (a parser leak), which would make every instalment its own payee.
_SENDER_REFERENCE = re.compile(r"\s+SENDER REFERENZ:.*$", re.IGNORECASE)

def _month_label(month_str: str) -> str:
    """Convert 'YYYY-MM' string to English month name, e.g. '2024-01' -> 'January 2024'."""
    year, month = map(int, month_str.split("-"))
    return f"{calendar.month_name[month]} {year}"


def _resolve_run_directory(arg: str) -> Path:
    """Resolve run directory from CLI argument.

    Supports either a direct path (for example data/example) or shorthand
    folder names under data/ (for example example -> data/example).
    """
    direct = Path(arg)
    if direct.exists() and direct.is_dir():
        return direct

    under_data = Path('data') / arg
    if under_data.exists() and under_data.is_dir():
        return under_data

    raise FileNotFoundError(
        f"Run directory not found: '{arg}' (also checked '{under_data}')"
    )


def load_categorized_csv(csv_path: str) -> pd.DataFrame:
    """Load a categorized CSV file.

    Args:
        csv_path: Path to the categorized CSV file

    Returns:
        DataFrame with transaction data
    """
    df = pd.read_csv(csv_path, sep=';', decimal=',', encoding='utf-8')

    # Parse date column
    df['Date'] = pd.to_datetime(df['Date'], format='%d.%m.%Y', errors='coerce')

    # Convert amount columns to numeric
    df['Credit in CHF'] = pd.to_numeric(df['Credit in CHF'], errors='coerce').fillna(0)
    df['Debit in CHF'] = pd.to_numeric(df['Debit in CHF'], errors='coerce').fillna(0)

    # Fill empty categories with "Uncategorized"
    df['Category'] = df['Category'].fillna('?').replace('?', 'Uncategorized')
    df['Subcategory'] = df['Subcategory'].fillna('')

    return df


def load_dataset_categorized_csvs(run_dir: Path) -> Tuple[pd.DataFrame, int]:
    """Load and merge all categorized CSV files from a run directory.

    Args:
        run_dir: Dataset run directory (for example data/example)

    Returns:
        A tuple of merged DataFrame and number of loaded files

    Raises:
        FileNotFoundError: If output directory or categorized files are missing
        ValueError: If a file is missing required columns
        RuntimeError: If a categorized CSV cannot be loaded
    """
    output_dir = run_dir / 'output'
    if not output_dir.exists() or not output_dir.is_dir():
        raise FileNotFoundError(f"Output directory not found: {output_dir}")

    categorized_files = sorted(output_dir.glob('*.categorized.csv'))
    if not categorized_files:
        raise FileNotFoundError(f"No categorized CSV files found in: {output_dir}")

    dataframes = []
    for csv_file in categorized_files:
        try:
            df = load_categorized_csv(str(csv_file))
        except Exception as e:
            raise RuntimeError(f"Failed to load '{csv_file.name}': {e}") from e

        missing_columns = REQUIRED_COLUMNS.difference(df.columns)
        if missing_columns:
            missing_list = ', '.join(sorted(missing_columns))
            raise ValueError(
                f"File '{csv_file.name}' is missing required columns: {missing_list}"
            )

        df['Source File'] = csv_file.name
        dataframes.append(df)

    merged = pd.concat(dataframes, ignore_index=True)
    return merged, len(categorized_files)


def load_months_metadata(run_dir: Path) -> list[str]:
    """Load the months metadata written by categorize_transactions.py.

    Args:
        run_dir: Dataset run directory (e.g. data/example)

    Returns:
        Sorted list of month strings in 'YYYY-MM' format

    Raises:
        FileNotFoundError: If months.json does not exist
    """
    months_path = run_dir / 'metadata' / 'months.json'
    if not months_path.exists():
        raise FileNotFoundError(
            f"Months metadata not found: {months_path}. "
            "Run categorize_transactions.py first to generate it."
        )
    with open(months_path, encoding='utf-8') as f:
        return json.load(f)


def spending_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Return only the rows a budget is about: neither income nor transfers.

    Rows without a transaction category are kept: they are uncategorized
    spending and should stay visible.
    """
    if "Transaction Category" not in df.columns:
        return df.copy()
    tc = df["Transaction Category"].fillna("").astype(str).str.lower()
    return df[~tc.isin(NON_SPENDING_TRANSACTION_CATEGORIES)].copy()


def _text_column(df: pd.DataFrame, column: str) -> pd.Series:
    """A column as stripped strings, empty where the column or value is missing."""
    if column not in df.columns:
        return pd.Series("", index=df.index)
    return df[column].fillna("").astype(str).str.strip()


def payees(df: pd.DataFrame) -> pd.Series:
    """Who the money went to or came from: merchant, else counterparty, else reference."""
    merchant = _text_column(df, "Merchant")
    counterparty = _text_column(df, "Counterparty")
    reference = _text_column(df, "Reference")
    return merchant.where(merchant != "", counterparty.where(counterparty != "", reference))


def normalize_payee(payee: str) -> str:
    """Group spellings of one payee: upper case, single spaces, no branch number,
    no sender reference.

    Deliberately minimal. Merging different spellings of the same company
    (addresses, legal forms) is left to the reader of the report.
    """
    text = _SENDER_REFERENCE.sub("", str(payee or ""))
    text = _BRANCH_NUMBER.sub("", text).upper()
    return " ".join(text.split())


def net_amounts(df: pd.DataFrame) -> pd.Series:
    """Debit minus credit: positive for spending, as in the budget report."""
    return (df["Debit in CHF"] - df["Credit in CHF"]).round(2)


def top_payees(df: pd.DataFrame, limit: int = TOP_PAYEES_PER_SUBCATEGORY) -> pd.DataFrame:
    """The largest payees per category and subcategory, net of refunds.

    Income and transfers are excluded, refunds are netted against the payee
    they come from — the same basis as the budget report. Per subcategory the
    top *limit* payees are listed and the rest folded into one row, so every
    subcategory still sums to its total. Subcategories are ordered by total,
    payees by net amount, both descending.
    """
    columns = ["Category", "Subcategory", "Payee", "Net", "Count", "Months", "Share", "Rank"]
    spending = spending_rows(df)
    if spending.empty:
        return pd.DataFrame(columns=columns)

    spending = spending.assign(
        Payee=payees(spending).map(normalize_payee),
        Net=net_amounts(spending),
        Month=spending["Date"].dt.strftime("%Y-%m"),
    )
    per_payee = (
        spending.groupby(["Category", "Subcategory", "Payee"])
        .agg(Net=("Net", "sum"), Count=("Net", "size"), Months=("Month", "nunique"))
        .reset_index()
    )
    totals = per_payee.groupby(["Category", "Subcategory"])["Net"].sum()

    rows = []
    for (category, subcategory), total in totals.sort_values(ascending=False).items():
        group = per_payee[
            (per_payee["Category"] == category) & (per_payee["Subcategory"] == subcategory)
        ].sort_values("Net", ascending=False)
        top, rest = group.head(limit), group.iloc[limit:]
        entries = [
            (row.Payee, row.Net, row.Count, row.Months, rank)
            for rank, row in enumerate(top.itertuples(index=False), start=1)
        ]
        if not rest.empty:
            entries.append(
                (OTHER_PAYEES_LABEL, rest["Net"].sum(), int(rest["Count"].sum()), None, None)
            )
        for payee, net, count, months, rank in entries:
            share = round(net / total, 4) if total else None
            rows.append([category, subcategory, payee, net, count, months, share, rank])

    result = pd.DataFrame(rows, columns=columns)
    result["Net"] = result["Net"].round(2)
    return result


def transaction_table(df: pd.DataFrame) -> pd.DataFrame:
    """Every transaction as one row, for filtering in Excel.

    Amount carries the budget report's sign (debit minus credit), so the sum
    over a filtered category matches its actual there. Columns an older export
    lacks stay empty.
    """
    category = _text_column(df, "Category")
    subcategory = _text_column(df, "Subcategory")
    table = pd.DataFrame({
        "Transaction ID": _text_column(df, "Transaction ID"),
        "Date": df["Date"],
        "Month": df["Date"].dt.strftime("%Y-%m"),
        "Transaction Category": _text_column(df, "Transaction Category"),
        "Category": category,
        "Subcategory": subcategory,
        # One filter field for a line; also the shape a subcategory budget key takes.
        "Category / Subcategory": category.where(subcategory == "", category + " / " + subcategory),
        "Payee": payees(df),
        "Reference": _text_column(df, "Reference"),
        "Credit": df["Credit in CHF"].round(2),
        "Debit": df["Debit in CHF"].round(2),
        "Amount": net_amounts(df),
        "Rule": _text_column(df, "Matched Rule Key"),
        "Source File": _text_column(df, "Source File"),
    })
    return table.sort_values(["Date", "Transaction ID"], kind="stable").reset_index(drop=True)


SUMMARY_TRANSACTION_CATEGORIES = ("Income", "Expense", "Refund", "Transfer")


def _summary_sums(df: pd.DataFrame) -> dict:
    """Credit and debit per transaction category, as the Summary sheet shows them."""
    if 'Transaction Category' in df.columns:
        grouped = (
            df.assign(_tc=df['Transaction Category'].fillna('').astype(str))
            .groupby('_tc')[['Credit in CHF', 'Debit in CHF']].sum()
        )
    else:
        grouped = pd.DataFrame(columns=['Credit in CHF', 'Debit in CHF'])
    return {
        tc: (
            float(grouped.loc[tc, 'Credit in CHF']) if tc in grouped.index else 0.0,
            float(grouped.loc[tc, 'Debit in CHF']) if tc in grouped.index else 0.0,
        )
        for tc in SUMMARY_TRANSACTION_CATEGORIES
    }


def _tx_range(table: pd.DataFrame, column: str) -> str:
    """Absolute range of one column in the Transactions sheet, e.g. for SUMIFS.

    Bounded to the rows actually written rather than a whole column, which
    Numbers does not import reliably.
    """
    letter = get_column_letter(list(table.columns).index(column) + 1)
    last_row = max(len(table) + 1, 2)
    return f"{TRANSACTIONS_SHEET}!${letter}$2:${letter}${last_row}"


def _sumifs(table: pd.DataFrame, value_column: str, *criteria: Tuple[str, str]) -> str:
    """SUMIFS over the Transactions sheet; criteria are (column, Excel criterion)."""
    parts = [_tx_range(table, value_column)]
    for column, criterion in criteria:
        parts += [_tx_range(table, column), f'"{criterion}"']
    return f"SUMIFS({', '.join(parts)})"


def reconcile(df: pd.DataFrame, months: list[str]) -> None:
    """Check the report's aggregations against the plain transaction table.

    The sheets are computed through different paths (groupby per category,
    per subcategory, per transaction category); the Transactions sheet is the
    row-level truth. Any difference is a bug in the report, so it fails loudly
    instead of writing figures nobody can trust.
    """
    table = transaction_table(df)
    problems = []

    def compare(label: str, reported: float, expected: float) -> None:
        if round(reported - expected, 2) != 0:
            problems.append(f"{label}: report {reported:.2f}, transactions {expected:.2f}")

    tc = table["Transaction Category"]
    summary = _summary_sums(df)
    for transaction_category in SUMMARY_TRANSACTION_CATEGORIES:
        credit, debit = summary[transaction_category]
        subset = table[tc == transaction_category]
        compare(f"Summary {transaction_category} credit", credit, subset["Credit"].sum())
        compare(f"Summary {transaction_category} debit", debit, subset["Debit"].sum())

    analysis_df = _exclude_transfer_transactions(df)
    not_transfer = tc.str.lower() != "transfer"
    for month in months:
        year, mon = map(int, month.split("-"))
        month_df = analysis_df[(analysis_df["Date"].dt.year == year) & (analysis_df["Date"].dt.month == mon)]
        month_rows = table[not_transfer & (table["Month"] == month)]
        category_stats = analyze_by_category(month_df)
        compare(f"Category Analysis {month} credit", category_stats["Credit in CHF"].sum(), month_rows["Credit"].sum())
        compare(f"Category Analysis {month} debit", category_stats["Debit in CHF"].sum(), month_rows["Debit"].sum())
        subcategory_stats = analyze_by_subcategory(month_df)
        with_subcategory = month_rows[month_rows["Subcategory"] != ""]
        compare(f"Subcategory Analysis {month} credit", subcategory_stats["Credit in CHF"].sum(), with_subcategory["Credit"].sum())
        compare(f"Subcategory Analysis {month} debit", subcategory_stats["Debit in CHF"].sum(), with_subcategory["Debit"].sum())

    if problems:
        raise ValueError("Report does not reconcile with its transactions:\n  " + "\n  ".join(problems))


def _write_check_rows(ws, row: int, total_cells: dict, formulas: dict, label_column: int = 1) -> int:
    """Write a check row with SUMIFS on Transactions and the difference to the table total.

    The static figures above stay authoritative; this is a visible cross-check
    that only shows a value once a spreadsheet application has calculated it.
    *total_cells* and *formulas* map a column index to the table's total cell and
    to the check formula. Returns the next free row.
    """
    ws.cell(row=row, column=label_column, value=CHECK_LABEL).font = Font(italic=True)
    ws.cell(row=row + 1, column=label_column, value=DIFFERENCE_LABEL).font = Font(italic=True)
    for column, formula in formulas.items():
        check = ws.cell(row=row, column=column, value=f"={formula}")
        check.number_format = AMOUNT_FORMAT
        check.font = Font(italic=True)
        difference = ws.cell(row=row + 1, column=column, value=f"={check.coordinate}-{total_cells[column]}")
        difference.number_format = AMOUNT_FORMAT
        difference.font = Font(italic=True)
    return row + 2


def analyze_by_category(df: pd.DataFrame) -> pd.DataFrame:
    """Analyze transactions by category.

    Args:
        df: DataFrame with transaction data

    Returns:
        DataFrame with category-level aggregations
    """
    category_stats = df.groupby('Category').agg({
        'Credit in CHF': 'sum',
        'Debit in CHF': 'sum'
    }).reset_index()

    # Calculate net (income - expenses)
    category_stats['Net in CHF'] = category_stats['Credit in CHF'] - category_stats['Debit in CHF']

    # Sort by total amount (debit + credit)
    category_stats['Total'] = category_stats['Credit in CHF'] + category_stats['Debit in CHF']
    category_stats = category_stats.sort_values('Total', ascending=False).drop('Total', axis=1)

    # Round to 2 decimals
    category_stats = category_stats.round(2)

    return category_stats


def analyze_by_subcategory(df: pd.DataFrame) -> pd.DataFrame:
    """Analyze transactions by category and subcategory.

    Args:
        df: DataFrame with transaction data

    Returns:
        DataFrame with subcategory-level aggregations
    """
    # Filter out rows without subcategory
    df_with_sub = df[df['Subcategory'] != ''].copy()

    if df_with_sub.empty:
        return pd.DataFrame(columns=['Category', 'Subcategory', 'Credit in CHF', 'Debit in CHF', 'Net in CHF'])

    subcategory_stats = df_with_sub.groupby(['Category', 'Subcategory']).agg({
        'Credit in CHF': 'sum',
        'Debit in CHF': 'sum'
    }).reset_index()

    # Calculate net
    subcategory_stats['Net in CHF'] = subcategory_stats['Credit in CHF'] - subcategory_stats['Debit in CHF']

    # Sort by category and total amount
    subcategory_stats['Total'] = subcategory_stats['Credit in CHF'] + subcategory_stats['Debit in CHF']
    subcategory_stats = subcategory_stats.sort_values(['Category', 'Total'], ascending=[True, False]).drop('Total', axis=1)

    # Round to 2 decimals
    subcategory_stats = subcategory_stats.round(2)

    return subcategory_stats


def create_excel_report(df: pd.DataFrame, category_stats: pd.DataFrame,
                        output_path: str, source_label: str, months: list[str]):
    """Create an Excel report with tables and charts.

    Args:
        df: Full transaction DataFrame with parsed Date column
        category_stats: DataFrame with overall category aggregations (for Overview sheet)
        output_path: Path to save the Excel file
        source_label: Human-readable source label for report header
        months: Sorted list of 'YYYY-MM' strings for per-month breakdown
    """
    # Python is the only calculation engine: every figure below is static.
    # Fail before writing anything that does not add up to its transactions.
    reconcile(df, months)
    table = transaction_table(df)

    wb = Workbook()

    # Remove default sheet
    wb.remove(wb.active)

    # Create summary sheet
    ws_summary = wb.create_sheet("Summary", 0)
    _create_summary_sheet(ws_summary, df, source_label, table)

    # Create first overview sheet
    ws_overview = wb.create_sheet("Overviews by category", 1)
    _create_overview_sheet(ws_overview, df, source_label, table)

    # Create Category Analysis sheet (one table per month)
    ws_category = wb.create_sheet("Category Analysis", 2)
    _create_category_sheet(ws_category, df, months, table)

    # Create Subcategory Analysis sheet (one table per month)
    ws_subcategory = wb.create_sheet("Subcategory Analysis", 3)
    _create_subcategory_sheet(ws_subcategory, df, months, table)

    # Every transaction behind the figures above, filterable
    ws_transactions = wb.create_sheet(TRANSACTIONS_SHEET, 4)
    _create_transactions_sheet(ws_transactions, table)

    # Largest payees per subcategory
    ws_top_payees = wb.create_sheet("Top Payees", 5)
    _create_top_payees_sheet(ws_top_payees, df)

    # Ensure output directory exists before saving
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Save workbook
    wb.save(output_file)
    print(f"✓ Excel report saved to: {output_file}")


def _create_summary_sheet(ws, df: pd.DataFrame, source_label: str, table: pd.DataFrame):
    """Create Summary sheet with transaction-category overview and chart."""
    ws['A1'] = 'Budget Analysis Summary'
    ws['A1'].font = Font(size=SHEET_TITLE_FONT_SIZE, bold=True)

    ws['A2'] = f'Source: {source_label}'
    ws['A2'].font = Font(size=10, italic=True)

    ws[f'A{TOP_NOTE_CONTENT_START_ROW}'] = 'Overall Summary'
    ws[f'A{TOP_NOTE_CONTENT_START_ROW}'].font = Font(size=SUBTITLE_FONT_SIZE, bold=True)

    header_row = TOP_NOTE_CONTENT_START_ROW + 2
    headers = ['Transaction Category', 'Credit (CHF)', 'Debit (CHF)']
    for col, header in enumerate(headers, start=1):
        cell = ws.cell(row=header_row, column=col, value=header)
        cell.font = Font(color='FFFFFF', bold=True)
        cell.fill = PatternFill(start_color='366092', end_color='366092', fill_type='solid')
        cell.alignment = Alignment(horizontal='center')

    sums = _summary_sums(df)
    income_credit, income_debit = sums['Income']
    expense_credit, expense_debit = sums['Expense']
    refund_credit, refund_debit = sums['Refund']
    transfer_credit, transfer_debit = sums['Transfer']

    first_data_row = header_row + 1
    summary_rows = [
        (first_data_row, 'Income', income_credit, income_debit),
        (first_data_row + 1, 'Expense', expense_credit, expense_debit),
        (first_data_row + 2, 'Refund', refund_credit, refund_debit),
    ]

    for row_idx, label, credit, debit in summary_rows:
        ws.cell(row=row_idx, column=1, value=label)
        ws.cell(row=row_idx, column=2, value=credit).number_format = '#,##0.00'
        ws.cell(row=row_idx, column=3, value=debit).number_format = '#,##0.00'

    total_credit = income_credit + expense_credit + refund_credit
    total_debit = income_debit + expense_debit + refund_debit
    total_row = first_data_row + 3
    ws.cell(row=total_row, column=1, value='Total').font = Font(bold=True)
    ws.cell(row=total_row, column=2, value=total_credit).number_format = '#,##0.00'
    ws.cell(row=total_row, column=3, value=total_debit).number_format = '#,##0.00'
    ws.cell(row=total_row, column=2).font = Font(bold=True)
    ws.cell(row=total_row, column=3).font = Font(bold=True)

    transfer_row = total_row + 2
    ws.cell(row=transfer_row, column=1, value='Transfer')
    ws.cell(row=transfer_row, column=2, value=transfer_credit).number_format = '#,##0.00'
    ws.cell(row=transfer_row, column=3, value=transfer_debit).number_format = '#,##0.00'

    grand_total_credit = total_credit + transfer_credit
    grand_total_debit = total_debit + transfer_debit
    grand_total_row = transfer_row + 2
    ws.cell(row=grand_total_row, column=1, value='Grand Total').font = Font(bold=True)
    ws.cell(row=grand_total_row, column=2, value=grand_total_credit).number_format = '#,##0.00'
    ws.cell(row=grand_total_row, column=3, value=grand_total_debit).number_format = '#,##0.00'
    ws.cell(row=grand_total_row, column=2).font = Font(bold=True)
    ws.cell(row=grand_total_row, column=3).font = Font(bold=True)

    # Rows without a transaction category are not part of the Grand Total, so
    # the check adds up exactly the four categories shown above.
    def check(value_column: str) -> str:
        return " + ".join(
            _sumifs(table, value_column, ("Transaction Category", tc))
            for tc in SUMMARY_TRANSACTION_CATEGORIES
        )

    _write_check_rows(
        ws,
        grand_total_row + 2,
        total_cells={2: f"B{grand_total_row}", 3: f"C{grand_total_row}"},
        formulas={2: check("Credit"), 3: check("Debit")},
    )

    # Helper block for contiguous chart data in stacked format.
    # Use four explicit series so chart legend can represent all parts correctly.
    ws.cell(row=6, column=5, value='Flow')
    ws.cell(row=6, column=6, value='income')
    ws.cell(row=6, column=7, value='refund (credit)')
    ws.cell(row=6, column=8, value='expenses')
    ws.cell(row=6, column=9, value='refund (debit)')

    ws.cell(row=7, column=5, value='Income')
    ws.cell(row=7, column=6, value=income_credit).number_format = '#,##0.00'
    ws.cell(row=7, column=7, value=refund_credit).number_format = '#,##0.00'
    ws.cell(row=7, column=8, value=0.0).number_format = '#,##0.00'
    ws.cell(row=7, column=9, value=0.0).number_format = '#,##0.00'

    ws.cell(row=8, column=5, value='Expenses')
    ws.cell(row=8, column=6, value=0.0).number_format = '#,##0.00'
    ws.cell(row=8, column=7, value=0.0).number_format = '#,##0.00'
    ws.cell(row=8, column=8, value=expense_debit).number_format = '#,##0.00'
    ws.cell(row=8, column=9, value=refund_debit).number_format = '#,##0.00'

    chart = BarChart()
    chart.type = 'col'
    chart.grouping = 'stacked'
    chart.overlap = 100
    chart.title = 'Income vs. Expenses'
    chart.y_axis.title = 'Amount (CHF)'
    chart.style = 10
    chart.height = 10
    chart.width = 14
    labels = Reference(ws, min_col=8, min_row=7, max_row=8)
    chart_data = Reference(ws, min_col=6, max_col=9, min_row=6, max_row=8)
    chart.add_data(chart_data, titles_from_data=True)
    chart.set_categories(labels)

    # Color each series so legend and bar colors are consistent.
    if len(chart.series) >= 4:
        chart.series[0].graphicalProperties.solidFill = '2E7D32'
        chart.series[1].graphicalProperties.solidFill = 'A5D6A7'
        chart.series[2].graphicalProperties.solidFill = 'C62828'
        chart.series[3].graphicalProperties.solidFill = 'EF9A9A'

    # Keep chart aligned with table header row.
    ws.add_chart(chart, 'E6')

    ws.column_dimensions['A'].width = 24
    ws.column_dimensions['B'].width = 15
    ws.column_dimensions['C'].width = 15


def _create_overview_sheet(ws, df: pd.DataFrame, source_label: str, table: pd.DataFrame):
    """Create the overview sheet with summary and pie charts."""
    # Title
    ws['A1'] = 'Budget Analysis by Category'
    ws['A1'].font = Font(size=SHEET_TITLE_FONT_SIZE, bold=True)

    ws['A2'] = f'Source: {source_label}'
    ws['A2'].font = Font(size=10, italic=True)

    # Build all three overview blocks with the same aggregation approach.
    income_data = _build_transaction_category_overview(
        df,
        transaction_category='Income',
        amount_column='Income in CHF',
        amount_formula='credit_minus_debit',
    )
    expense_data = _build_transaction_category_overview(
        df,
        transaction_category='Expense',
        amount_column='Expense in CHF',
        amount_formula='debit_minus_credit',
    )
    refund_data = _build_transaction_category_overview(
        df,
        transaction_category='Refund',
        amount_column='Refund in CHF',
        amount_formula='credit_minus_debit',
    )

    # Income section
    current_row = TOP_NOTE_CONTENT_START_ROW
    ws[f'A{current_row}'] = 'Income by Category'
    ws[f'A{current_row}'].font = Font(size=SUBTITLE_FONT_SIZE, bold=True)

    current_row += 2
    _add_table_and_chart(
        ws,
        income_data,
        start_row=current_row,
        amount_column='Income in CHF',
        chart_title='Income by Category',
        empty_message='No income data available.',
        check_formula=_net_check(table, 'Income', credit_first=True),
    )
    income_header_row = current_row

    # Expense section (header is fixed OVERVIEW_TABLE_HEADER_GAP rows below prior table header)
    expense_header_row = income_header_row + OVERVIEW_TABLE_HEADER_GAP
    current_row = expense_header_row - 2
    ws[f'A{current_row}'] = 'Expenses by Category'
    ws[f'A{current_row}'].font = Font(size=SUBTITLE_FONT_SIZE, bold=True)

    current_row += 2
    _add_table_and_chart(
        ws,
        expense_data,
        start_row=current_row,
        amount_column='Expense in CHF',
        chart_title='Expenses by Category',
        empty_message='No expense data available.',
        check_formula=_net_check(table, 'Expense', credit_first=False),
    )
    expense_header_row = current_row

    # Refund section (header is fixed OVERVIEW_TABLE_HEADER_GAP rows below prior table header)
    current_row = (expense_header_row + OVERVIEW_TABLE_HEADER_GAP) - 2
    ws[f'A{current_row}'] = 'Refunds by Category'
    ws[f'A{current_row}'].font = Font(size=SUBTITLE_FONT_SIZE, bold=True)

    current_row += 2
    _add_table_and_chart(
        ws,
        refund_data,
        start_row=current_row,
        amount_column='Refund in CHF',
        chart_title='Refunds by Category',
        empty_message='No refund data available.',
        check_formula=_net_check(table, 'Refund', credit_first=True),
    )

    # Adjust column widths
    ws.column_dimensions['A'].width = 20
    ws.column_dimensions['B'].width = 15


def _add_table_and_chart(
    ws,
    data: pd.DataFrame,
    start_row: int,
    amount_column: str,
    chart_title: str,
    empty_message: str,
    check_formula: Optional[str] = None,
):
    """Add category/amount table with blue header and pie chart next to it.

    Below the table follow a total and, if *check_formula* is given, the
    check rows against the Transactions sheet.
    """
    if data.empty:
        ws.cell(row=start_row, column=1, value=empty_message)
        return

    headers = ['Category', 'Amount (CHF)']
    for col, header in enumerate(headers, start=1):
        cell = ws.cell(row=start_row, column=col)
        cell.value = header
        cell.font = Font(color='FFFFFF', bold=True)
        cell.fill = PatternFill(start_color='366092', end_color='366092', fill_type='solid')

    for idx, (_, row) in enumerate(data.iterrows(), start=1):
        ws.cell(row=start_row + idx, column=1, value=row['Category'])
        ws.cell(row=start_row + idx, column=2, value=row[amount_column]).number_format = '#,##0.00'

    chart = PieChart()
    chart.title = chart_title
    chart.style = 10
    chart.height = 10
    chart.width = 14

    data_rows = len(data)
    labels = Reference(ws, min_col=1, min_row=start_row + 1, max_row=start_row + data_rows)
    chart_data = Reference(ws, min_col=2, min_row=start_row, max_row=start_row + data_rows)

    chart.add_data(chart_data, titles_from_data=True)
    chart.set_categories(labels)

    chart_cell = f"D{start_row}"
    ws.add_chart(chart, chart_cell)

    total_row = start_row + data_rows + 1
    ws.cell(row=total_row, column=1, value='Total').font = Font(bold=True)
    total = ws.cell(row=total_row, column=2, value=round(float(data[amount_column].sum()), 2))
    total.number_format = AMOUNT_FORMAT
    total.font = Font(bold=True)
    if check_formula:
        _write_check_rows(ws, total_row + 1, total_cells={2: f"B{total_row}"}, formulas={2: check_formula})


def _net_check(table: pd.DataFrame, transaction_category: str, credit_first: bool) -> str:
    """Net amount of one transaction category, as a formula on Transactions.

    The overview tables only list categories with a positive net amount (a pie
    chart cannot show the rest), so a difference in the check row is exactly
    what those left-out categories add up to.
    """
    credit = _sumifs(table, "Credit", ("Transaction Category", transaction_category))
    debit = _sumifs(table, "Debit", ("Transaction Category", transaction_category))
    return f"{credit} - {debit}" if credit_first else f"{debit} - {credit}"


def _build_transaction_category_overview(
    df: pd.DataFrame,
    transaction_category: str,
    amount_column: str,
    amount_formula: str,
) -> pd.DataFrame:
    """Aggregate one transaction category per category for the overview sheet."""
    if 'Transaction Category' not in df.columns:
        return pd.DataFrame(columns=['Category', amount_column])

    rows = df[df['Transaction Category'].fillna('').astype(str) == transaction_category].copy()
    if rows.empty:
        return pd.DataFrame(columns=['Category', amount_column])

    grouped = rows.groupby('Category').agg({
        'Credit in CHF': 'sum',
        'Debit in CHF': 'sum',
    }).reset_index()

    if amount_formula == 'debit_minus_credit':
        grouped[amount_column] = grouped['Debit in CHF'] - grouped['Credit in CHF']
    else:
        grouped[amount_column] = grouped['Credit in CHF'] - grouped['Debit in CHF']

    grouped = grouped[grouped[amount_column] > 0].copy()
    grouped = grouped.sort_values(amount_column, ascending=False)
    return grouped[['Category', amount_column]]


def _exclude_transfer_transactions(df: pd.DataFrame) -> pd.DataFrame:
    """Return dataframe without rows classified as transaction category 'transfer'."""
    if 'Transaction Category' not in df.columns:
        return df
    mask = df['Transaction Category'].fillna('').astype(str).str.lower() != 'transfer'
    return df[mask].copy()


def _create_category_sheet(ws, df: pd.DataFrame, months: list[str], table: pd.DataFrame):
    """Create category analysis sheet with one table per month."""
    ws['A1'] = 'Category Analysis'
    ws['A1'].font = Font(size=SHEET_TITLE_FONT_SIZE, bold=True)

    ws['A2'] = "Note: Transactions with Transaction Category 'transfer' are excluded."
    ws['A2'].font = Font(size=10, italic=True)

    analysis_df = _exclude_transfer_transactions(df)

    current_row = TOP_NOTE_CONTENT_START_ROW
    for month_str in months:
        year, month = map(int, month_str.split("-"))
        mask = (analysis_df['Date'].dt.year == year) & (analysis_df['Date'].dt.month == month)
        month_stats = analyze_by_category(analysis_df[mask])

        # Month header
        ws.cell(row=current_row, column=1, value=_month_label(month_str)).font = Font(size=SUBTITLE_FONT_SIZE, bold=True)
        current_row += 2

        # Table header + data rows
        for i, row in enumerate(dataframe_to_rows(month_stats, index=False, header=True)):
            for col_idx, value in enumerate(row, start=1):
                cell = ws.cell(row=current_row, column=col_idx, value=value)
                if i == 0:  # header row
                    cell.font = Font(color='FFFFFF', bold=True)
                    cell.fill = PatternFill(start_color='366092', end_color='366092', fill_type='solid')
                    cell.alignment = Alignment(horizontal='center')
                elif col_idx > 1 and isinstance(value, numbers.Number):
                    cell.number_format = '#,##0.00'
            current_row += 1

        criteria = [("Month", month_str), ("Transaction Category", "<>Transfer")]
        current_row = _write_month_totals(
            ws, current_row, month_stats, table, criteria, first_amount_column=2
        )

        current_row += 2  # spacing between months

    # Adjust column widths
    ws.column_dimensions['A'].width = 20
    ws.column_dimensions['B'].width = 15
    ws.column_dimensions['C'].width = 15
    ws.column_dimensions['D'].width = 15


def _create_subcategory_sheet(ws, df: pd.DataFrame, months: list[str], table: pd.DataFrame):
    """Create subcategory analysis sheet with one table per month."""
    ws['A1'] = 'Subcategory Analysis'
    ws['A1'].font = Font(size=SHEET_TITLE_FONT_SIZE, bold=True)

    ws['A2'] = "Note: Transactions with Transaction Category 'transfer' are excluded."
    ws['A2'].font = Font(size=10, italic=True)

    analysis_df = _exclude_transfer_transactions(df)

    current_row = TOP_NOTE_CONTENT_START_ROW
    for month_str in months:
        year, month = map(int, month_str.split("-"))
        mask = (analysis_df['Date'].dt.year == year) & (analysis_df['Date'].dt.month == month)
        month_stats = analyze_by_subcategory(analysis_df[mask])

        if month_stats.empty:
            continue

        # Month header
        ws.cell(row=current_row, column=1, value=_month_label(month_str)).font = Font(size=SUBTITLE_FONT_SIZE, bold=True)
        current_row += 2

        # Table header + data rows
        for i, row in enumerate(dataframe_to_rows(month_stats, index=False, header=True)):
            for col_idx, value in enumerate(row, start=1):
                cell = ws.cell(row=current_row, column=col_idx, value=value)
                if i == 0:  # header row
                    cell.font = Font(color='FFFFFF', bold=True)
                    cell.fill = PatternFill(start_color='366092', end_color='366092', fill_type='solid')
                    cell.alignment = Alignment(horizontal='center')
                elif col_idx > 2 and isinstance(value, numbers.Number):
                    cell.number_format = '#,##0.00'
            current_row += 1

        # Rows without a subcategory are not part of this table ("<>" = not empty).
        criteria = [
            ("Month", month_str),
            ("Transaction Category", "<>Transfer"),
            ("Subcategory", "<>"),
        ]
        current_row = _write_month_totals(
            ws, current_row, month_stats, table, criteria, first_amount_column=3
        )

        current_row += 2  # spacing between months

    # Adjust column widths
    ws.column_dimensions['A'].width = 20
    ws.column_dimensions['B'].width = 25
    ws.column_dimensions['C'].width = 15
    ws.column_dimensions['D'].width = 15
    ws.column_dimensions['E'].width = 15


def _write_month_totals(
    ws,
    row: int,
    stats: pd.DataFrame,
    table: pd.DataFrame,
    criteria: list,
    first_amount_column: int,
) -> int:
    """Write the total of a month table (credit, debit, net) and its check rows.

    Returns the next free row.
    """
    ws.cell(row=row, column=1, value='Total').font = Font(bold=True)
    credit_col, debit_col, net_col = (first_amount_column + i for i in range(3))
    totals = {
        credit_col: stats['Credit in CHF'].sum(),
        debit_col: stats['Debit in CHF'].sum(),
        net_col: stats['Net in CHF'].sum(),
    }
    for column, value in totals.items():
        cell = ws.cell(row=row, column=column, value=round(float(value), 2))
        cell.number_format = AMOUNT_FORMAT
        cell.font = Font(bold=True)

    credit = _sumifs(table, "Credit", *criteria)
    debit = _sumifs(table, "Debit", *criteria)
    return _write_check_rows(
        ws,
        row + 1,
        total_cells={c: ws.cell(row=row, column=c).coordinate for c in totals},
        formulas={credit_col: credit, debit_col: debit, net_col: f"{credit} - {debit}"},
    )


def _write_filterable_table(ws, table: pd.DataFrame, widths: dict, formats: dict):
    """Write *table* from A1 with a frozen, filterable header row.

    The header sits in row 1 on purpose: Excel's filter and freeze panes work
    best without title rows above the table.
    """
    for col_idx, name in enumerate(table.columns, start=1):
        cell = ws.cell(row=1, column=col_idx, value=name)
        cell.font = Font(color='FFFFFF', bold=True)
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal='center')

    for row_idx, values in enumerate(table.itertuples(index=False), start=2):
        for col_idx, value in enumerate(values, start=1):
            # Empty text is written as a truly empty cell, so that SUMIFS
            # criteria like "<>" (not empty) behave the same in Excel and Numbers.
            if value is None or value == "" or (isinstance(value, float) and pd.isna(value)) or value is pd.NaT:
                value = None
            elif isinstance(value, pd.Timestamp):
                value = value.to_pydatetime()
            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            number_format = formats.get(table.columns[col_idx - 1])
            if number_format and value is not None:
                cell.number_format = number_format

    last_column = ws.cell(row=1, column=len(table.columns)).column_letter
    ws.auto_filter.ref = f"A1:{last_column}{max(len(table) + 1, 1)}"
    ws.freeze_panes = 'A2'
    for letter, width in widths.items():
        ws.column_dimensions[letter].width = width


def _create_transactions_sheet(ws, table: pd.DataFrame):
    """Create a sheet with every transaction, to trace any figure to its bookings."""
    _write_filterable_table(
        ws,
        table,
        widths={'A': 12, 'B': 11, 'C': 9, 'D': 12, 'E': 16, 'F': 22, 'G': 32,
                'H': 40, 'I': 40, 'J': 12, 'K': 12, 'L': 12, 'M': 28, 'N': 32},
        formats={'Date': 'DD.MM.YYYY', 'Credit': AMOUNT_FORMAT, 'Debit': AMOUNT_FORMAT,
                 'Amount': AMOUNT_FORMAT},
    )


def _create_top_payees_sheet(ws, df: pd.DataFrame):
    """Create a sheet with the largest payees per subcategory."""
    _write_filterable_table(
        ws,
        top_payees(df),
        widths={'A': 16, 'B': 22, 'C': 40, 'D': 12, 'E': 8, 'F': 8, 'G': 8, 'H': 6},
        formats={'Net': '#,##0.00', 'Share': '0%'},
    )


def main(argv: Optional[Sequence[str]] = None):
    """Main entry point."""
    argv = argv if argv is not None else sys.argv[1:]

    if len(argv) < 1 or len(argv) > 2:
        print("Usage: python analyze_by_category.py <run_dir> [output_excel_file]")
        print("\nExample:")
        print("  python analyze_by_category.py example")
        print("  python analyze_by_category.py data/example")
        print("  python analyze_by_category.py private my_analysis.xlsx")
        return 2

    try:
        run_dir = _resolve_run_directory(argv[0])
    except FileNotFoundError as e:
        print(f"❌ {e}")
        return 1

    # Determine output path
    if len(argv) == 2:
        output_path = argv[1]
    else:
        # Default: in dataset output directory
        output_path = str(run_dir / 'output' / 'dataset.analysis.xlsx')

    print("=" * 60)
    print("  Budget Analysis - Category Report Generator")
    print("=" * 60)
    print(f"\nInput dataset:  {run_dir}")
    print(f"Output: {output_path}")

    # Discover and load all categorized files in dataset output
    print("\n1. Discovering and loading categorized CSV files...")
    try:
        df, file_count = load_dataset_categorized_csvs(run_dir)
        print(f"   Loaded {len(df)} transactions from {file_count} file(s)")
    except Exception as e:
        print(f"❌ Error loading categorized files: {e}")
        return 1

    print("\n2. Analyzing by category...")
    category_stats = analyze_by_category(df)
    print(f"   Found {len(category_stats)} categories")

    print("\n3. Loading month metadata...")
    try:
        months = load_months_metadata(run_dir)
        print(f"   Found {len(months)} month(s): {', '.join(_month_label(m) for m in months)}")
    except FileNotFoundError as e:
        print(f"\u274c {e}")
        return 1

    print("\n4. Generating Excel report...")
    try:
        source_label = f"{run_dir} ({file_count} categorized file(s))"
        create_excel_report(
            df,
            category_stats,
            output_path,
            source_label,
            months,
        )
    except Exception as e:
        print(f"❌ Error creating Excel report: {e}")
        return 1

    print("\n" + "=" * 60)
    print("Analysis completed successfully!")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
