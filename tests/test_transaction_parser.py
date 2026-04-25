#!/usr/bin/env python3
"""Test transaction row parser"""
import sys
import os

import pandas as pd

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from transaction_parser import TransactionParser


def test_parse_row_apple_pay():
    """Test parsing of an Apple Pay CSV row"""
    df = pd.read_csv('data/example/input/export.202503.csv', sep=';', skiprows=5, encoding='utf-8')
    row = df.iloc[0]

    txn = TransactionParser.parse_row(row)

    assert txn is not None, "Parser should return a transaction"
    assert txn.service_type == 'Card Purchase', "Service type should be Card Purchase"
    assert txn.provider == 'Apple Pay', "Provider should be Apple Pay"
    assert txn.card_number == 'XXXX4821', "Card number should be parsed"
    assert txn.parsed_merchant == 'CITY TANKSTELLE', "Merchant should be parsed"
    assert txn.parsed_location == 'OLTEN', "Location should be parsed"
    assert txn.debit > 0, "Lastschrift should be stored as positive"
    assert txn.transaction_type == 'Debit', "Transaction type should be normalized to Debit"


def test_parse_row_skips_empty_date():
    """Test parser skips rows without date"""
    row = pd.Series({
        'Datum': pd.NA,
        'Bewegungstyp': 'Buchung',
        'Avisierungstext': 'TEST',
        'Gutschrift in CHF': 0,
        'Lastschrift in CHF': 1,
        'Label': '',
        'Kategorie': '',
    })

    txn = TransactionParser.parse_row(row)
    assert txn is None, "Rows without date should be skipped"


def test_parse_row_credit_transaction_type():
    """Credit rows should be normalized to transaction_type='credit'."""
    df = pd.read_csv('data/example/input/export.202503.csv', sep=';', skiprows=5, encoding='utf-8')
    credit_rows = df[pd.to_numeric(df['Gutschrift in CHF'], errors='coerce').fillna(0) > 0]
    assert not credit_rows.empty, "Example dataset should contain at least one credit transaction"
    row = credit_rows.iloc[0]

    txn = TransactionParser.parse_row(row)
    assert txn is not None
    assert txn.transaction_type == 'Credit'


if __name__ == '__main__':
    test_parse_row_apple_pay()
    test_parse_row_skips_empty_date()
    print("✓ All transaction parser tests passed")
