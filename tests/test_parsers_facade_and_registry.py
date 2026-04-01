#!/usr/bin/env python3
"""Test parser facade, registry, and service strategies."""
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from notification.facade import NotificationTextParser
from notification.parsers.card_purchase_parser import CardPurchaseParser
from notification.registry import NotificationParserRegistry


def test_card_purchase_parser_supports_apple_pay_and_generic_card_purchase():
    """CardPurchaseParser should detect Apple Pay and generic card purchases."""
    parser = CardPurchaseParser()
    text = "APPLE PAY KAUF/DIENSTLEISTUNG VOM 30.03.2025 KARTEN NR. XXXX4821 BYRO BASEL SCHWEIZ"
    generic_text = "KAUF/DIENSTLEISTUNG VOM 27.03.2025 KARTEN NR. XXXX4821 YOOJI'S ROSENGARTEN BIEL SCHWEIZ"
    online_text = "KAUF/ONLINE-SHOPPING VOM 27.03.2025 KARTEN NR. XXXX4821 APPLE.COM/BILL CORK"

    assert parser.supports(text), "Card purchase parser should support valid Apple Pay text"
    assert parser.supports(generic_text), "Card purchase parser should support valid generic card purchase text"
    assert parser.supports(online_text), "Card purchase parser should support online shopping format"


def test_registry_delegates_to_card_purchase_parser_for_apple_pay():
    """Registry should delegate to CardPurchaseParser and return Apple Pay fields."""
    registry = NotificationParserRegistry()
    text = "APPLE PAY KAUF/DIENSTLEISTUNG VOM 31.03.2025 KARTEN NR. XXXX4821 CITY TANKSTELLE OLTEN WAREN 10.34"

    result = registry.parse(text)
    assert result.service_type == "Karteneinkauf"
    assert result.provider == "Apple Pay"
    assert result.card_number == "XXXX4821"
    assert result.merchant == "CITY TANKSTELLE"
    assert result.location == "OLTEN"


def test_registry_delegates_to_card_purchase_parser_for_generic_card_purchase():
    """Registry should parse generic card purchases without provider."""
    registry = NotificationParserRegistry()
    text = "KAUF/DIENSTLEISTUNG VOM 27.03.2025 KARTEN NR. XXXX4821 YOOJI'S ROSENGARTEN BIEL SCHWEIZ"

    result = registry.parse(text)
    assert result.service_type == "Karteneinkauf"
    assert result.provider == ""
    assert result.card_number == "XXXX4821"
    assert result.merchant == "YOOJI'S ROSENGARTEN"
    assert result.location == "BIEL"


def test_registry_delegates_to_card_purchase_parser_for_online_shopping():
    """Registry should parse online shopping card purchases."""
    registry = NotificationParserRegistry()
    text = "KAUF/ONLINE-SHOPPING VOM 27.03.2025 KARTEN NR. XXXX4821 APPLE.COM/BILL CORK"

    result = registry.parse(text)
    assert result.service_type == "Karteneinkauf"
    assert result.provider == ""
    assert result.transaction_type_detail == "Kauf/Online-Shopping"
    assert result.card_number == "XXXX4821"
    assert result.merchant == "APPLE.COM/BILL"
    assert result.location == "CORK"


def test_registry_delegates_to_cash_withdrawal_parser():
    """Registry should parse cash withdrawal card transactions."""
    registry = NotificationParserRegistry()
    text = "BARGELDBEZUG VOM 27.03.2025 KARTEN NR. XXXX4821 EINKAUFSZENTRUM METROPOLE BIEL"

    result = registry.parse(text)
    assert result.service_type == "Bargeldbezug"
    assert result.transaction_type_detail == "Bargeldbezug"
    assert result.card_number == "XXXX4821"
    assert result.merchant == "EINKAUFSZENTRUM METROPOLE"
    assert result.location == "BIEL"


def test_registry_delegates_to_credit_transfer_parser():
    """Registry should parse salary-like credit transfers (Auftraggeber format)."""
    registry = NotificationParserRegistry()
    text = "GUTSCHRIFT AUFTRAGGEBER: ALPENWERK AG INDUSTRIESTRASSE 12 CH-5430 WETTINGEN AG MITTEILUNGEN: SALAER MAERZ 2025 REFERENZEN: SALA80E5ED528784F48B451A4175649C112 9988776655/1XXXX 250325CH7LMNQRTS"

    result = registry.parse(text)
    assert result.service_type == "Gutschrift"
    assert result.transaction_type_detail == "Gutschrift"
    assert result.counterparty == "ALPENWERK AG INDUSTRIESTRASSE 12 CH-5430 WETTINGEN AG"
    assert "SALAER MAERZ 2025" in result.reference


def test_registry_delegates_to_credit_transfer_parser_sender_with_iban():
    """Registry should parse ABSENDER credit transfers with IBAN."""
    registry = NotificationParserRegistry()
    text = "GUTSCHRIFT CH6709000000400025000 ABSENDER: VIVAO SYMPANY AG PETER MERIAN-WEG 4 4052 BASEL MITTEILUNGEN: RECHNUNG NR.: 201941771110536469 WE DER ANDREAS110536469 WEDER ANDREASB ETRIFFT DIV. ABRECHNUNGEN REFERENZEN: SYM95CB11F8253446278F81749F26F10588"

    result = registry.parse(text)
    assert result.service_type == "Gutschrift"
    assert result.transaction_type_detail == "Gutschrift"
    assert result.counterparty_iban == "CH6709000000400025000"
    assert result.counterparty == "VIVAO SYMPANY AG PETER MERIAN-WEG 4 4052 BASEL"
    assert "RECHNUNG NR." in result.reference


def test_registry_delegates_to_bank_package_fee_parser():
    """Registry should parse bank package fee notifications."""
    registry = NotificationParserRegistry()
    text = "PREIS FÜR BANKPAKET SMART 02.2025"

    result = registry.parse(text)
    assert result.service_type == "Gebühren"
    assert result.transaction_type_detail == "Bankpaketpreis"
    assert result.reference == "PREIS FÜR BANKPAKET SMART 02.2025"


def test_notification_text_parser_facade_api_contract():
    """Facade API should return dict and delegate through the registry."""
    text = "APPLE PAY KAUF/DIENSTLEISTUNG VOM 31.03.2025 KARTEN NR. XXXX4821 KKIOSK 45810 BERN SCHWEIZ"
    parsed = NotificationTextParser.parse(text)

    assert isinstance(parsed, dict), "Facade should return dict"
    assert parsed["service_type"] == "Karteneinkauf"
    assert parsed["provider"] == "Apple Pay"
    assert parsed["card_number"] == "XXXX4821"
    assert parsed["merchant"] == "KKIOSK 45810"
    assert parsed["location"] == "BERN"


if __name__ == '__main__':
    test_card_purchase_parser_supports_apple_pay_and_generic_card_purchase()
    test_registry_delegates_to_card_purchase_parser_for_apple_pay()
    test_registry_delegates_to_card_purchase_parser_for_generic_card_purchase()
    test_registry_delegates_to_card_purchase_parser_for_online_shopping()
    test_registry_delegates_to_cash_withdrawal_parser()
    test_registry_delegates_to_credit_transfer_parser()
    test_registry_delegates_to_credit_transfer_parser_sender_with_iban()
    test_registry_delegates_to_bank_package_fee_parser()
    test_notification_text_parser_facade_api_contract()
    print("✓ All parser facade and registry tests passed")
