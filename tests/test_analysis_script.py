#!/usr/bin/env python3
"""Test category analysis script."""
import sys
import os
import tempfile
from pathlib import Path

# Add root directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pandas as pd
from openpyxl import load_workbook
from analyze_by_category import (
    load_categorized_csv,
    analyze_by_category,
    analyze_by_subcategory,
    create_excel_report
)


def test_load_categorized_csv():
    """Test that categorized CSV is loaded correctly."""
    csv_path = 'data/reference/output/export.202503.categorized.csv'

    df = load_categorized_csv(csv_path)

    assert df is not None, "CSV should be loaded"
    assert len(df) > 0, "CSV should contain transactions"
    assert 'Category' in df.columns, "Should have Category column"
    assert 'Subcategory' in df.columns, "Should have Subcategory column"
    assert 'Credit in CHF' in df.columns, "Should have Credit in CHF column"
    assert 'Debit in CHF' in df.columns, "Should have Debit in CHF column"


def test_analyze_by_category():
    """Test category analysis."""
    csv_path = 'data/reference/output/export.202503.categorized.csv'
    df = load_categorized_csv(csv_path)

    category_stats = analyze_by_category(df)

    assert category_stats is not None, "Should return category statistics"
    assert len(category_stats) > 0, "Should have at least one category"
    assert 'Category' in category_stats.columns, "Should have Category column"
    assert 'Credit in CHF' in category_stats.columns, "Should have Credit in CHF column"
    assert 'Debit in CHF' in category_stats.columns, "Should have Debit in CHF column"
    assert 'Net in CHF' in category_stats.columns, "Should have Net in CHF column"

    # Verify totals match original data
    total_credit = df['Credit in CHF'].sum()
    total_debit = df['Debit in CHF'].sum()

    assert abs(category_stats['Credit in CHF'].sum() - total_credit) < 0.01, "Credit totals should match"
    assert abs(category_stats['Debit in CHF'].sum() - total_debit) < 0.01, "Debit totals should match"


def test_analyze_by_subcategory():
    """Test subcategory analysis."""
    csv_path = 'data/reference/output/export.202503.categorized.csv'
    df = load_categorized_csv(csv_path)

    subcategory_stats = analyze_by_subcategory(df)

    assert subcategory_stats is not None, "Should return subcategory statistics"
    assert 'Category' in subcategory_stats.columns, "Should have Category column"
    assert 'Subcategory' in subcategory_stats.columns, "Should have Subcategory column"
    assert 'Credit in CHF' in subcategory_stats.columns, "Should have Credit in CHF column"
    assert 'Debit in CHF' in subcategory_stats.columns, "Should have Debit in CHF column"
    assert 'Net in CHF' in subcategory_stats.columns, "Should have Net in CHF column"

    # Verify no empty subcategories
    assert all(subcategory_stats['Subcategory'] != ''), "Should not have empty subcategories"


def test_category_uncategorized_handling():
    """Test that uncategorized transactions are properly handled."""
    csv_path = 'data/reference/output/export.202503.categorized.csv'
    df = load_categorized_csv(csv_path)

    # Check if there are any uncategorized transactions
    uncategorized = df[df['Category'] == 'Uncategorized']

    if len(uncategorized) > 0:
        category_stats = analyze_by_category(df)

        # Should have an 'Uncategorized' category in stats
        assert 'Uncategorized' in category_stats['Category'].values, \
            "Should include Uncategorized category if present"


def test_numerical_calculations():
    """Test that numerical calculations are correct."""
    csv_path = 'data/reference/output/export.202503.categorized.csv'
    df = load_categorized_csv(csv_path)

    category_stats = analyze_by_category(df)

    # Verify Net = Credit - Debit for each category
    for _, row in category_stats.iterrows():
        expected_net = row['Credit in CHF'] - row['Debit in CHF']
        assert abs(row['Net in CHF'] - expected_net) < 0.01, \
            f"Net should equal Credit - Debit for {row['Category']}"


def test_excel_report_creation():
    """Integration test for Excel report generation."""
    csv_path = 'data/reference/output/export.202503.categorized.csv'
    df = load_categorized_csv(csv_path)

    category_stats = analyze_by_category(df)
    subcategory_stats = analyze_by_subcategory(df)

    # Create temporary directory and file
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / 'subdir' / 'test_analysis.xlsx'

        # Test that directory creation works
        create_excel_report(
            category_stats,
            subcategory_stats,
            str(output_path),
            'test.csv'
        )

        # Verify file was created
        assert output_path.exists(), "Excel file should be created"

        # Load and verify workbook structure
        wb = load_workbook(output_path)

        # Check expected sheets exist
        assert 'Overview' in wb.sheetnames, "Should have Overview sheet"
        assert 'Category Analysis' in wb.sheetnames, "Should have Category Analysis sheet"
        assert 'Subcategory Analysis' in wb.sheetnames, "Should have Subcategory Analysis sheet"

        # Verify Overview sheet has expected headers
        ws_overview = wb['Overview']
        assert ws_overview['A1'].value == 'Budget Analysis by Category', "Should have title"
        assert ws_overview['A11'].value == 'Income by Category', "Should have income section"

        # Verify income table has proper headers
        # Income table starts at row 13 (A11 is section title, A12 is blank, A13 is header row)
        assert ws_overview['A13'].value == 'Category', "Should have Category header for income table"
        assert ws_overview['B13'].value == 'Amount (CHF)', "Should have Amount header for income table"

        # Find and verify expense section exists
        # The expense section should be below income section
        expense_section_found = False
        for row in range(15, 30):  # Search in reasonable range
            if ws_overview[f'A{row}'].value == 'Expenses by Category':
                expense_section_found = True
                # Verify expense table headers are 2 rows below
                expense_header_row = row + 2
                assert ws_overview[f'A{expense_header_row}'].value == 'Category', \
                    "Should have Category header for expense table"
                assert ws_overview[f'B{expense_header_row}'].value == 'Amount (CHF)', \
                    "Should have Amount header for expense table"
                break

        assert expense_section_found, "Should have Expenses by Category section"

        # Verify Category Analysis sheet has data
        ws_category = wb['Category Analysis']
        assert ws_category['A1'].value == 'Category Analysis', "Should have title"
        assert ws_category['A3'].value == 'Category', "Should have Category header"

        wb.close()
