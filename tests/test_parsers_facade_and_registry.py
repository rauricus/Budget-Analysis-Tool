#!/usr/bin/env python3
"""Test parser facade, registry, and service strategies."""
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from notification.facade import NotificationTextParser, NoNotificationParserFoundError
from notification.parsers.card_purchase_parser import CardPurchaseParser


def test_card_purchase_parser_supports_apple_pay_and_generic_card_purchase():
    """CardPurchaseParser should detect Apple Pay and generic card purchases."""
    parser = CardPurchaseParser()
    text = "APPLE PAY KAUF/DIENSTLEISTUNG VOM 30.03.2025 KARTEN NR. XXXX4821 BYRO BASEL SCHWEIZ"
    generic_text = "KAUF/DIENSTLEISTUNG VOM 27.03.2025 KARTEN NR. XXXX4821 YOOJI'S ROSENGARTEN BIEL SCHWEIZ"
    online_text = "KAUF/ONLINE-SHOPPING VOM 27.03.2025 KARTEN NR. XXXX4821 APPLE.COM/BILL CORK"

    assert parser.supports(text), "Card purchase parser should support valid Apple Pay text"
    assert parser.supports(generic_text), "Card purchase parser should support valid generic card purchase text"
    assert parser.supports(online_text), "Card purchase parser should support online shopping format"


def test_facade_parses_apple_pay():
    """Facade should parse Apple Pay card purchases."""
    text = "APPLE PAY KAUF/DIENSTLEISTUNG VOM 31.03.2025 KARTEN NR. XXXX4821 CITY TANKSTELLE OLTEN WAREN 10.34"

    result = NotificationTextParser.parse(text)
    assert result["service_type"] == "Card Purchase"
    assert result["provider"] == "Apple Pay"
    assert result["card_number"] == "XXXX4821"
    assert result["merchant"] == "CITY TANKSTELLE"
    assert result["location"] == "OLTEN"


def test_facade_parses_generic_card_purchase():
    """Facade should parse generic card purchases without provider."""
    text = "KAUF/DIENSTLEISTUNG VOM 27.03.2025 KARTEN NR. XXXX4821 YOOJI'S ROSENGARTEN BIEL SCHWEIZ"

    result = NotificationTextParser.parse(text)
    assert result["service_type"] == "Card Purchase"
    assert result["provider"] == ""
    assert result["card_number"] == "XXXX4821"
    assert result["merchant"] == "YOOJI'S ROSENGARTEN"
    assert result["location"] == "BIEL"


def test_facade_parses_online_shopping():
    """Facade should parse online shopping card purchases."""
    text = "KAUF/ONLINE-SHOPPING VOM 27.03.2025 KARTEN NR. XXXX4821 APPLE.COM/BILL CORK"

    result = NotificationTextParser.parse(text)
    assert result["service_type"] == "Card Purchase"
    assert result["provider"] == ""
    assert result["transaction_type_detail"] == "Purchase/Online Shopping"
    assert result["card_number"] == "XXXX4821"
    assert result["merchant"] == "APPLE.COM/BILL"
    assert result["location"] == "CORK"


def test_facade_parses_cash_withdrawal():
    """Facade should parse cash withdrawal card transactions."""
    text = "BARGELDBEZUG VOM 27.03.2025 KARTEN NR. XXXX4821 EINKAUFSZENTRUM METROPOLE BIEL"

    result = NotificationTextParser.parse(text)
    assert result["service_type"] == "Cash Withdrawal"
    assert result["transaction_type_detail"] == "Cash Withdrawal"
    assert result["card_number"] == "XXXX4821"
    assert result["merchant"] == "EINKAUFSZENTRUM METROPOLE"
    assert result["location"] == "BIEL"


def test_facade_parses_credit_transfer():
    """Facade should parse salary-like credit transfers (Auftraggeber format)."""
    text = "GUTSCHRIFT AUFTRAGGEBER: ALPENWERK AG INDUSTRIESTRASSE 12 CH-5430 WETTINGEN AG MITTEILUNGEN: SALAER MAERZ 2025 REFERENZEN: SALA80E5ED528784F48B451A4175649C112 9988776655/1XXXX 250325CH7LMNQRTS"

    result = NotificationTextParser.parse(text)
    assert result["service_type"] == "Credit"
    assert result["transaction_type_detail"] == "Credit"
    assert result["counterparty"] == "ALPENWERK AG INDUSTRIESTRASSE 12 CH-5430 WETTINGEN AG"
    assert "SALAER MAERZ 2025" in result["reference"]


def test_facade_parses_credit_transfer_sender_with_iban():
    """Facade should parse ABSENDER credit transfers with IBAN."""
    text = "GUTSCHRIFT CH6709000000400025000 ABSENDER: VIVAO SYMPANY AG PETER MERIAN-WEG 4 4052 BASEL MITTEILUNGEN: RECHNUNG NR.: 201941771110536469 WE DER ANDREAS110536469 WEDER ANDREASB ETRIFFT DIV. ABRECHNUNGEN REFERENZEN: SYM95CB11F8253446278F81749F26F10588"

    result = NotificationTextParser.parse(text)
    assert result["service_type"] == "Credit"
    assert result["transaction_type_detail"] == "Credit"
    assert result["counterparty_iban"] == "CH6709000000400025000"
    assert result["counterparty"] == "VIVAO SYMPANY AG PETER MERIAN-WEG 4 4052 BASEL"
    assert "RECHNUNG NR." in result["reference"]


def test_facade_parses_bank_package_fee():
    """Facade should parse bank package fee notifications."""
    text = "PREIS FÜR BANKPAKET SMART 02.2025"

    result = NotificationTextParser.parse(text)
    assert result["service_type"] == "Fees"
    assert result["transaction_type_detail"] == "Bank Package Fee"
    assert result["reference"] == "PREIS FÜR BANKPAKET SMART 02.2025"


def test_facade_parses_lastschrift_with_bank_route_details():
    """Facade should parse LASTSCHRIFT texts containing intermediary bank details."""
    text = "LASTSCHRIFT MUSTERBANK AG MUSTERSTRASSE 12 6002 LUZERN CH5600000000000000000 MOBILITY MUSTER GENOSSENSCHAFT 6343 ROTKREUZ"

    result = NotificationTextParser.parse(text)
    assert result["service_type"] == "Direct Debit"
    assert result["transaction_type_detail"] == "Payment"
    assert result["counterparty_iban"] == "CH5600000000000000000"
    assert result["counterparty"] == "MOBILITY MUSTER GENOSSENSCHAFT 6343 ROTKREUZ"
    assert result["reference"] == "MUSTERBANK AG MUSTERSTRASSE 12 6002 LUZERN"


def test_notification_text_parser_facade_api_contract():
    """Facade API should return dict and delegate through the registry."""
    text = "APPLE PAY KAUF/DIENSTLEISTUNG VOM 31.03.2025 KARTEN NR. XXXX4821 KKIOSK 45810 BERN SCHWEIZ"
    parsed = NotificationTextParser.parse(text)

    assert isinstance(parsed, dict), "Facade should return dict"
    assert parsed["service_type"] == "Card Purchase"
    assert parsed["provider"] == "Apple Pay"
    assert parsed["card_number"] == "XXXX4821"
    assert parsed["merchant"] == "KKIOSK 45810"
    assert parsed["location"] == "BERN"


def test_facade_raises_no_parser_found_error_for_unknown_text():
    """Facade should raise NoNotificationParserFoundError for unrecognised notification text."""
    import pytest
    with pytest.raises(NoNotificationParserFoundError) as exc_info:
        NotificationTextParser.parse("SOME COMPLETELY UNKNOWN FORMAT XYZ 12345")
    assert "SOME COMPLETELY UNKNOWN FORMAT XYZ 12345" in str(exc_info.value)


if __name__ == '__main__':
    test_card_purchase_parser_supports_apple_pay_and_generic_card_purchase()
    test_facade_parses_apple_pay()
    test_facade_parses_generic_card_purchase()
    test_facade_parses_online_shopping()
    test_facade_parses_cash_withdrawal()
    test_facade_parses_credit_transfer()
    test_facade_parses_credit_transfer_sender_with_iban()
    test_facade_parses_bank_package_fee()
    test_facade_parses_lastschrift_with_bank_route_details()
    test_notification_text_parser_facade_api_contract()
    test_facade_raises_no_parser_found_error_for_unknown_text()
    print("✓ All parser facade tests passed")
