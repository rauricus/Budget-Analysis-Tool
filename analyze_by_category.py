#!/usr/bin/env python3
"""
Budget Analysis by Category

Analyzes categorized CSV files and generates an Excel report with:
- Summary tables by category and subcategory
- Pie charts for visual analysis
- Flexibility for users to modify and customize

Usage:
    python analyze_by_category.py <run_dir> [output_excel_file]

Example:
    python analyze_by_category.py reference
    python analyze_by_category.py data/reference
    python analyze_by_category.py private my_analysis.xlsx
"""

import sys
from pathlib import Path
import numbers
from typing import Optional, Sequence, Tuple
import pandas as pd
from openpyxl import Workbook
from openpyxl.chart import PieChart, Reference
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils.dataframe import dataframe_to_rows


REQUIRED_COLUMNS = {
    'Category',
    'Subcategory',
    'Credit in CHF',
    'Debit in CHF',
}


def _resolve_run_directory(arg: str) -> Path:
    """Resolve run directory from CLI argument.

    Supports either a direct path (for example data/reference) or shorthand
    folder names under data/ (for example reference -> data/reference).
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
        run_dir: Dataset run directory (for example data/reference)

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


def create_excel_report(category_stats: pd.DataFrame, subcategory_stats: pd.DataFrame,
                        output_path: str, source_label: str):
    """Create an Excel report with tables and charts.

    Args:
        category_stats: DataFrame with category aggregations
        subcategory_stats: DataFrame with subcategory aggregations
        output_path: Path to save the Excel file
        source_label: Human-readable source label for report header
    """
    wb = Workbook()

    # Remove default sheet
    wb.remove(wb.active)

    # Create Overview sheet
    ws_overview = wb.create_sheet("Overview", 0)
    _create_overview_sheet(ws_overview, category_stats, source_label)

    # Create Category Analysis sheet
    ws_category = wb.create_sheet("Category Analysis", 1)
    _create_category_sheet(ws_category, category_stats)

    # Always create Subcategory Analysis sheet for a consistent workbook layout
    ws_subcategory = wb.create_sheet("Subcategory Analysis", 2)
    if not subcategory_stats.empty:
        _create_subcategory_sheet(ws_subcategory, subcategory_stats)
    else:
        ws_subcategory['A1'] = "Subcategory Analysis"
        ws_subcategory['A1'].font = Font(bold=True, size=14)
        ws_subcategory['A3'] = "No subcategory data available."
        ws_subcategory['A3'].font = Font(italic=True)

    # Ensure output directory exists before saving
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Save workbook
    wb.save(output_file)
    print(f"✓ Excel report saved to: {output_file}")


def _create_overview_sheet(ws, category_stats: pd.DataFrame, source_label: str):
    """Create the overview sheet with summary and pie charts."""
    # Title
    ws['A1'] = 'Budget Analysis by Category'
    ws['A1'].font = Font(size=16, bold=True)

    ws['A2'] = f'Source: {source_label}'
    ws['A2'].font = Font(size=10, italic=True)

    # Overall summary
    ws['A4'] = 'Overall Summary'
    ws['A4'].font = Font(size=14, bold=True)

    total_income = category_stats['Credit in CHF'].sum()
    total_expenses = category_stats['Debit in CHF'].sum()
    total_net = total_income - total_expenses

    ws['A6'] = 'Total Income:'
    ws['B6'] = total_income
    ws['B6'].number_format = '#,##0.00'

    ws['A7'] = 'Total Expenses:'
    ws['B7'] = total_expenses
    ws['B7'].number_format = '#,##0.00'

    ws['A8'] = 'Net (Income - Expenses):'
    ws['B8'] = total_net
    ws['B8'].number_format = '#,##0.00'
    ws['B8'].font = Font(bold=True)

    # Filter income and expense categories
    income_data = category_stats[category_stats['Credit in CHF'] > 0].copy()
    expense_data = category_stats[category_stats['Debit in CHF'] > 0].copy()

    # Income section
    current_row = 11
    ws[f'A{current_row}'] = 'Income by Category'
    ws[f'A{current_row}'].font = Font(size=12, bold=True)

    current_row += 2
    income_table_start = current_row
    _add_income_table_and_chart(ws, income_data, start_row=current_row)

    # Expense section (positioned below income section)
    current_row = income_table_start + len(income_data) + 5  # Add spacing
    ws[f'A{current_row}'] = 'Expenses by Category'
    ws[f'A{current_row}'].font = Font(size=12, bold=True)

    current_row += 2
    _add_expense_table_and_chart(ws, expense_data, start_row=current_row)

    # Adjust column widths
    ws.column_dimensions['A'].width = 20
    ws.column_dimensions['B'].width = 15


def _add_income_table_and_chart(ws, income_data: pd.DataFrame, start_row: int):
    """Add income table with blue header and pie chart next to it."""
    if income_data.empty:
        ws.cell(row=start_row, column=1, value="No income data available.")
        return

    # Add table headers (blue background, white text)
    headers = ['Category', 'Amount (CHF)']
    for col, header in enumerate(headers, start=1):
        cell = ws.cell(row=start_row, column=col)
        cell.value = header
        cell.font = Font(color='FFFFFF', bold=True)
        cell.fill = PatternFill(start_color='366092', end_color='366092', fill_type='solid')

    # Add data rows
    for idx, (_, row) in enumerate(income_data.iterrows(), start=1):
        ws.cell(row=start_row + idx, column=1, value=row['Category'])
        ws.cell(row=start_row + idx, column=2, value=row['Credit in CHF']).number_format = '#,##0.00'

    # Create pie chart
    chart = PieChart()
    chart.title = "Income by Category"
    chart.style = 10
    chart.height = 10  # Reduced height to prevent overlap
    chart.width = 14   # Reduced width to prevent overlap

    # Reference the table data for the chart
    data_rows = len(income_data)
    labels = Reference(ws, min_col=1, min_row=start_row + 1, max_row=start_row + data_rows)
    data = Reference(ws, min_col=2, min_row=start_row, max_row=start_row + data_rows)

    chart.add_data(data, titles_from_data=True)
    chart.set_categories(labels)

    # Position chart to the right of the table (column D)
    chart_cell = f"D{start_row}"
    ws.add_chart(chart, chart_cell)


def _add_expense_table_and_chart(ws, expense_data: pd.DataFrame, start_row: int):
    """Add expense table with blue header and pie chart next to it."""
    if expense_data.empty:
        ws.cell(row=start_row, column=1, value="No expense data available.")
        return

    # Add table headers (blue background, white text)
    headers = ['Category', 'Amount (CHF)']
    for col, header in enumerate(headers, start=1):
        cell = ws.cell(row=start_row, column=col)
        cell.value = header
        cell.font = Font(color='FFFFFF', bold=True)
        cell.fill = PatternFill(start_color='366092', end_color='366092', fill_type='solid')

    # Add data rows
    for idx, (_, row) in enumerate(expense_data.iterrows(), start=1):
        ws.cell(row=start_row + idx, column=1, value=row['Category'])
        ws.cell(row=start_row + idx, column=2, value=row['Debit in CHF']).number_format = '#,##0.00'

    # Create pie chart
    chart = PieChart()
    chart.title = "Expenses by Category"
    chart.style = 10
    chart.height = 10  # Reduced height to prevent overlap
    chart.width = 14   # Reduced width to prevent overlap

    # Reference the table data for the chart
    data_rows = len(expense_data)
    labels = Reference(ws, min_col=1, min_row=start_row + 1, max_row=start_row + data_rows)
    data = Reference(ws, min_col=2, min_row=start_row, max_row=start_row + data_rows)

    chart.add_data(data, titles_from_data=True)
    chart.set_categories(labels)

    # Position chart to the right of the table (column D)
    chart_cell = f"D{start_row}"
    ws.add_chart(chart, chart_cell)


def _create_category_sheet(ws, category_stats: pd.DataFrame):
    """Create detailed category analysis sheet."""
    ws['A1'] = 'Category Analysis'
    ws['A1'].font = Font(size=14, bold=True)

    # Add table with data
    for row_idx, row in enumerate(dataframe_to_rows(category_stats, index=False, header=True), start=3):
        for col_idx, value in enumerate(row, start=1):
            cell = ws.cell(row=row_idx, column=col_idx, value=value)

            # Format header
            if row_idx == 3:
                cell.font = Font(color='FFFFFF', bold=True)
                cell.fill = PatternFill(start_color='366092', end_color='366092', fill_type='solid')
                cell.alignment = Alignment(horizontal='center')

            # Format numbers
            elif col_idx > 1 and isinstance(value, numbers.Number):
                cell.number_format = '#,##0.00'

    # Adjust column widths
    ws.column_dimensions['A'].width = 20
    ws.column_dimensions['B'].width = 15
    ws.column_dimensions['C'].width = 15
    ws.column_dimensions['D'].width = 15


def _create_subcategory_sheet(ws, subcategory_stats: pd.DataFrame):
    """Create detailed subcategory analysis sheet."""
    ws['A1'] = 'Subcategory Analysis'
    ws['A1'].font = Font(size=14, bold=True)

    # Add table with data
    for row_idx, row in enumerate(dataframe_to_rows(subcategory_stats, index=False, header=True), start=3):
        for col_idx, value in enumerate(row, start=1):
            cell = ws.cell(row=row_idx, column=col_idx, value=value)

            # Format header
            if row_idx == 3:
                cell.font = Font(color='FFFFFF', bold=True)
                cell.fill = PatternFill(start_color='366092', end_color='366092', fill_type='solid')
                cell.alignment = Alignment(horizontal='center')

            # Format numbers
            elif col_idx > 2 and isinstance(value, numbers.Number):
                cell.number_format = '#,##0.00'

    # Adjust column widths
    ws.column_dimensions['A'].width = 20
    ws.column_dimensions['B'].width = 25
    ws.column_dimensions['C'].width = 15
    ws.column_dimensions['D'].width = 15
    ws.column_dimensions['E'].width = 15


def main(argv: Optional[Sequence[str]] = None):
    """Main entry point."""
    argv = argv if argv is not None else sys.argv[1:]

    if len(argv) < 1 or len(argv) > 2:
        print("Usage: python analyze_by_category.py <run_dir> [output_excel_file]")
        print("\nExample:")
        print("  python analyze_by_category.py reference")
        print("  python analyze_by_category.py data/reference")
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

    print("\n3. Analyzing by subcategory...")
    subcategory_stats = analyze_by_subcategory(df)
    print(f"   Found {len(subcategory_stats)} subcategories")

    print("\n4. Generating Excel report...")
    try:
        source_label = f"{run_dir} ({file_count} categorized file(s))"
        create_excel_report(
            category_stats,
            subcategory_stats,
            output_path,
            source_label
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
