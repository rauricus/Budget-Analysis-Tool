#!/usr/bin/env python3
"""Test category analysis script."""
import sys
import os
from pathlib import Path

# Add root directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pandas as pd
from analyze_by_category import (
    load_categorized_csv,
    analyze_by_category,
    analyze_by_subcategory
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
