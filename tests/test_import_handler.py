#!/usr/bin/env python3
"""Test CSV import via ImportHandler."""
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from import_handler import ImportHandler
from models import Transaction


def test_csv_loading():
    """Test that CSV file is loaded correctly"""
    txns = ImportHandler.load_csv('data/reference/input/export.202503.csv')
    
    assert txns is not None, "CSV should be loaded"
    assert len(txns) > 0, "CSV should contain transactions"
    assert all(isinstance(t, Transaction) for t in txns), "All items should be Transaction objects"
    
    # Verify transaction attributes
    txn = txns[0]
    assert hasattr(txn, 'date'), "Transaction should have date"
    assert hasattr(txn, 'transaction_type'), "Transaction should have transaction_type"
    assert hasattr(txn, 'notification_text'), "Transaction should have notification_text"
    assert hasattr(txn, 'notification_text_upper'), "Transaction should have notification_text_upper"


def test_transaction_text_upper():
    """Test that notification_text_upper is properly calculated"""
    txns = ImportHandler.load_csv('data/reference/input/export.202503.csv')
    
    for txn in txns:
        # notification_text_upper should be the uppercase version of notification_text
        assert txn.notification_text_upper == txn.notification_text.upper(), \
            f"notification_text_upper should be uppercase of notification_text"


def test_apple_pay_notification_parsing():
    """Test that Apple Pay fields are parsed from notification text"""
    txns = ImportHandler.load_csv('data/reference/input/export.202503.csv')

    apple_pay_txn = txns[0]
    assert apple_pay_txn.service_type == 'Karteneinkauf', "Service type should be Karteneinkauf"
    assert apple_pay_txn.provider == 'Apple Pay', "Provider should be Apple Pay"
    assert apple_pay_txn.card_number == 'XXXX4821', "Card number should be parsed"
    assert apple_pay_txn.parsed_merchant == 'CITY TANKSTELLE', "Merchant should be parsed"
    assert apple_pay_txn.parsed_location == 'OLTEN', "Location should be parsed"


if __name__ == '__main__':
    test_csv_loading()
    test_transaction_text_upper()
    test_apple_pay_notification_parsing()
    print("✓ All import handler tests passed")
