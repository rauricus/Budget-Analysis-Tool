#!/usr/bin/env python3
"""Test notification service parsers for Twint and Lastschrift variants."""
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from notification.parsers.twint_senden_parser import TwintSendenParser
from notification.parsers.debit_direct_parser import DebitDirectParser
from notification.parsers.zahlung_parser import ZahlungParser
from notification.parsers.dauerauftrag_parser import DauerauftragParser


def test_twint_senden_parser_supports():
    """TwintSendenParser should detect TWINT transaction texts"""
    parser = TwintSendenParser()
    text = "TWINT GELD SENDEN VOM 26.03.2025 VON TELEFON-NR. +41795555111 AN TELEFON-NR. +41796666222 KEBAB, IMBISS MITTEILUNGEN: KEBAB"

    assert parser.supports(text), "TWINT parser should support valid TWINT text"


def test_twint_senden_parser_parse():
    """TwintSendenParser should extract merchant and transaction type"""
    parser = TwintSendenParser()
    text = "TWINT GELD SENDEN VOM 26.03.2025 VON TELEFON-NR. +41795555111 AN TELEFON-NR. +41796666222 KEBAB, IMBISS MITTEILUNGEN: KEBAB"

    result = parser.parse(text)
    assert result.service_type == "Twint"
    assert result.transaction_type_detail == "Geld senden"
    assert "+41796666222 KEBAB, IMBISS" in result.merchant


def test_debit_direct_parser():
    """DebitDirectParser should parse Debit Direct format"""
    parser = DebitDirectParser()
    text = "AUFTRAG CH-DD-BASISLASTSCHRIFT ID-NR. DES ZAHLUNGSEMPFÄNGERS: 41101000000123456 REFERENZ-NR: TAXA2589-695B-4A7B-B290-C9A7BEF7001 ZAHLUNGSEMPFÄNGER: STEUERDIENSTE REGION WEST MITTEILUNGEN: 2025/04/01 / 7045128 TRANSAKTIONS-ID: 305-77445512"

    assert parser.supports(text), "Should support Debit Direct format"

    result = parser.parse(text)
    assert result.service_type == "Lastschrift"
    assert result.transaction_type_detail == "Lastschrift Debit Direct"
    assert result.recipient == "STEUERDIENSTE REGION WEST"
    assert result.recipient_iban == "41101000000123456"
    assert "2025/04/01 / 7045128" in result.reference


def test_zahlung_parser():
    """ZahlungParser should parse Zahlung (payment) format"""
    parser = ZahlungParser()
    text = "LASTSCHRIFT CH6330000011998877665 SUNRISE GMBH POSTFACH 8050 ZURICH"

    assert parser.supports(text), "Should support Zahlung format"

    result = parser.parse(text)
    assert result.service_type == "Lastschrift"
    assert result.transaction_type_detail == "Zahlung"
    assert result.recipient_iban == "CH6330000011998877665"
    assert "SUNRISE GMBH POSTFACH 8050 ZURICH" in result.recipient


def test_dauerauftrag_parser():
    """DauerauftragParser should parse Dauerauftrag (standing order) format"""
    parser = DauerauftragParser()
    text = "LASTSCHRIFT DAUERAUFTRAG: 90-33445566 CH3409000000802999554 FAMILIENKASSE MUSTERHAUSEN SENDER REFERENZ: FAMILIENZULAGE"

    assert parser.supports(text), "Should support Dauerauftrag format"

    result = parser.parse(text)
    assert result.service_type == "Lastschrift"
    assert result.transaction_type_detail == "Dauerauftrag"
    assert result.recipient_iban == "CH3409000000802999554"
    assert result.reference == "90-33445566"


if __name__ == '__main__':
    test_twint_senden_parser_supports()
    test_twint_senden_parser_parse()
    test_debit_direct_parser()
    test_zahlung_parser()
    test_dauerauftrag_parser()
    print("✓ All notification service parser tests passed")
