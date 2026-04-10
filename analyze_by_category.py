#!/usr/bin/env python3
"""
Budget Analysis by Category

Analyzes categorized CSV files and generates an Excel report with:
- Summary tables by category and subcategory
- Pie charts for visual analysis
- Flexibility for users to modify and customize

Usage:
    python analyze_by_category.py <categorized_csv_file> [output_excel_file]

Example:
    python analyze_by_category.py data/reference/output/export.202503.categorized.csv
    python analyze_by_category.py data/reference/output/export.202503.categorized.csv analysis.xlsx
"""

import sys
from pathlib import Path
import numbers
import pandas as pd
from openpyxl import Workbook
from openpyxl.chart import PieChart, Reference
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils.dataframe import dataframe_to_rows


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
                        output_path: str, original_filename: str):
    """Create an Excel report with tables and charts.

    Args:
        category_stats: DataFrame with category aggregations
        subcategory_stats: DataFrame with subcategory aggregations
        output_path: Path to save the Excel file
        original_filename: Name of the original CSV file for reference
    """
    wb = Workbook()

    # Remove default sheet
    wb.remove(wb.active)

    # Create Overview sheet
    ws_overview = wb.create_sheet("Overview", 0)
    _create_overview_sheet(ws_overview, category_stats, original_filename)

    # Create Category Analysis sheet
    ws_category = wb.create_sheet("Category Analysis", 1)
    _create_category_sheet(ws_category, category_stats)

    # Create Subcategory Analysis sheet if there's data
    if not subcategory_stats.empty:
        ws_subcategory = wb.create_sheet("Subcategory Analysis", 2)
        _create_subcategory_sheet(ws_subcategory, subcategory_stats)

    # Ensure output directory exists before saving
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Save workbook
    wb.save(output_file)
    print(f"✓ Excel report saved to: {output_file}")


def _create_overview_sheet(ws, category_stats: pd.DataFrame, original_filename: str):
    """Create the overview sheet with summary and pie charts."""
    # Title
    ws['A1'] = 'Budget Analysis by Category'
    ws['A1'].font = Font(size=16, bold=True)

    ws['A2'] = f'Source: {original_filename}'
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

    # Category breakdown table
    ws['A11'] = 'Category Breakdown'
    ws['A11'].font = Font(size=12, bold=True)

    # Add headers
    headers = ['Category', 'Income (CHF)', 'Expenses (CHF)', 'Net (CHF)']
    for col, header in enumerate(headers, start=1):
        cell = ws.cell(row=13, column=col)
        cell.value = header
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color='366092', end_color='366092', fill_type='solid')
        cell.font = Font(color='FFFFFF', bold=True)

    # Add data rows
    for idx, (_, row) in enumerate(category_stats.iterrows(), start=14):
        ws.cell(row=idx, column=1, value=row['Category'])
        ws.cell(row=idx, column=2, value=row['Credit in CHF']).number_format = '#,##0.00'
        ws.cell(row=idx, column=3, value=row['Debit in CHF']).number_format = '#,##0.00'
        ws.cell(row=idx, column=4, value=row['Net in CHF']).number_format = '#,##0.00'

    # Add pie chart for expenses
    _add_expense_pie_chart(ws, category_stats, start_row=13)

    # Adjust column widths
    ws.column_dimensions['A'].width = 20
    ws.column_dimensions['B'].width = 15
    ws.column_dimensions['C'].width = 15
    ws.column_dimensions['D'].width = 15


def _add_expense_pie_chart(ws, category_stats: pd.DataFrame, start_row: int):
    """Add a pie chart for expenses by category."""
    # Filter out categories with zero expenses
    expense_data = category_stats[category_stats['Debit in CHF'] > 0].copy()

    if expense_data.empty:
        return

    # Create pie chart
    chart = PieChart()
    chart.title = "Expenses by Category"
    chart.style = 10
    chart.height = 12
    chart.width = 16

    # Calculate chart data range
    data_rows = len(expense_data)

    # Categories (labels)
    labels = Reference(ws, min_col=1, min_row=start_row + 1, max_row=start_row + data_rows)

    # Data (expenses - column 3)
    data = Reference(ws, min_col=3, min_row=start_row, max_row=start_row + data_rows)

    chart.add_data(data, titles_from_data=True)
    chart.set_categories(labels)

    # Position chart
    ws.add_chart(chart, "F11")


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
                cell.font = Font(bold=True)
                cell.fill = PatternFill(start_color='366092', end_color='366092', fill_type='solid')
                cell.font = Font(color='FFFFFF', bold=True)
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
                cell.font = Font(bold=True)
                cell.fill = PatternFill(start_color='366092', end_color='366092', fill_type='solid')
                cell.font = Font(color='FFFFFF', bold=True)
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


def main(argv=None):
    """Main entry point."""
    argv = argv if argv is not None else sys.argv[1:]

    if len(argv) < 1 or len(argv) > 2:
        print("Usage: python analyze_by_category.py <categorized_csv_file> [output_excel_file]")
        print("\nExample:")
        print("  python analyze_by_category.py data/reference/output/export.202503.categorized.csv")
        print("  python analyze_by_category.py data/reference/output/export.202503.categorized.csv analysis.xlsx")
        return 2

    csv_path = argv[0]

    # Validate input file
    if not Path(csv_path).exists():
        print(f"❌ File not found: {csv_path}")
        return 1

    # Determine output path
    if len(argv) == 2:
        output_path = argv[1]
    else:
        # Default: same directory as input, with .xlsx extension
        csv_file = Path(csv_path)
        output_path = str(csv_file.parent / f"{csv_file.stem}.analysis.xlsx")

    print("=" * 60)
    print("  Budget Analysis - Category Report Generator")
    print("=" * 60)
    print(f"\nInput:  {csv_path}")
    print(f"Output: {output_path}")

    # Load and analyze
    print("\n1. Loading categorized CSV...")
    try:
        df = load_categorized_csv(csv_path)
        print(f"   Loaded {len(df)} transactions")
    except Exception as e:
        print(f"❌ Error loading CSV: {e}")
        return 1

    print("\n2. Analyzing by category...")
    category_stats = analyze_by_category(df)
    print(f"   Found {len(category_stats)} categories")

    print("\n3. Analyzing by subcategory...")
    subcategory_stats = analyze_by_subcategory(df)
    print(f"   Found {len(subcategory_stats)} subcategories")

    print("\n4. Generating Excel report...")
    try:
        create_excel_report(
            category_stats,
            subcategory_stats,
            output_path,
            Path(csv_path).name
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
