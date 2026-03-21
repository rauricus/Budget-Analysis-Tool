#!/usr/bin/env python3
"""Test export handler"""
import sys
import os
import tempfile
from pathlib import Path

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from import_handler import ImportHandler
from export_handler import ExportHandler
from rule_engine import RuleEngine
import pandas as pd


def test_export_format():
    """Test that export creates correct format with all columns"""
    txns = ImportHandler.load_csv('data/reference/input/export.202503.csv')
    engine = RuleEngine('data/reference/rules.json')
    
    # Categorize
    txns, matching_rules = engine.categorize_batch(txns)
    
    # Export to temp file
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = os.path.join(tmpdir, "test_export.csv")
        ExportHandler.export_csv(txns, output_path, matching_rules)
        
        # Read export back
        df = pd.read_csv(output_path, sep=";", encoding="utf-8")
        
        # Verifice columns
        expected_columns = ExportHandler.EXPORT_COLUMNS
        assert list(df.columns) == expected_columns, \
            f"Export columns mismatch: {list(df.columns)} vs {expected_columns}"
        
        # Verifice data
        assert len(df) == len(txns), "Row count should match transaction count"
        assert all(df["Date"].notna()), "Date should not be empty"
        assert all(df["Transaction Type"].notna()), "Transaction Type should not be empty"
        assert all(df["Category"].notna()), "Category should not be empty"


def test_merchant_location_extraction():
    """Test that merchant and location are extracted correctly"""
    txns = ImportHandler.load_csv('data/reference/input/export.202503.csv')
    engine = RuleEngine('data/reference/rules.json')
    
    # Categorize
    txns, matching_rules = engine.categorize_batch(txns)
    
    # Test extraction for one transaction
    for idx, txn in enumerate(txns[:5]):
        rules = matching_rules.get(idx, [])
        merchant, location = ExportHandler.extract_merchant_location(txn, rules)
        
        # Merchant/location should be strings
        assert isinstance(merchant, str), "Merchant should be string"
        assert isinstance(location, str), "Location should be string"


def test_export_includes_service_fields():
    """Test that service and card number are exported"""
    txns = ImportHandler.load_csv('data/reference/input/export.202503.csv')
    engine = RuleEngine('data/reference/rules.json')

    txns, matching_rules = engine.categorize_batch(txns)

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = os.path.join(tmpdir, "test_service_fields.csv")
        ExportHandler.export_csv(txns, output_path, matching_rules)

        df = pd.read_csv(output_path, sep=";", encoding="utf-8")

        assert "Service" in df.columns, "Service column should exist"
        assert "Card Number" in df.columns, "Card Number column should exist"

        first_row = df.iloc[0]
        assert first_row["Service"] == "Apple Pay", "First row service should be Apple Pay"
        assert first_row["Card Number"] == "XXXX4821", "First row card number should be parsed"


def test_export_preserves_amounts():
    """Test that credit/debit amounts are correctly formatted"""
    txns = ImportHandler.load_csv('data/reference/input/export.202503.csv')
    engine = RuleEngine('data/reference/rules.json')
    
    txns, matching_rules = engine.categorize_batch(txns)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = os.path.join(tmpdir, "test_amounts.csv")
        ExportHandler.export_csv(txns, output_path, matching_rules)
        
        df = pd.read_csv(output_path, sep=";", encoding="utf-8")
        
        # Verify that amounts are handled correctly
        for idx, (_, row) in enumerate(df.iterrows()):
            if idx < len(txns):
                txn = txns[idx]
                
                # Credit
                if txn.credit > 0:
                    assert str(row["Credit in CHF"]) != "nan", \
                        f"Credit should be populated for txn {idx}"

                # Debit
                if txn.debit > 0:
                    assert str(row["Debit in CHF"]) != "nan", \
                        f"Debit should be populated for txn {idx}"


if __name__ == '__main__':
    test_export_format()
    test_merchant_location_extraction()
    test_export_preserves_amounts()
    test_export_includes_service_fields()
    print("✓ All export tests passed")
