#!/usr/bin/env python3
"""Test notification service parsers for Twint and Lastschrift variants."""
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from notification.parsers.twint_send_parser import TwintSendParser
from notification.parsers.cash_withdrawal_parser import CashWithdrawalParser
from notification.parsers.card_purchase_parser import CardPurchaseParser
from notification.parsers.credit_transfer_parser import CreditTransferParser
from notification.parsers.debit_direct_parser import DebitDirectParser
from notification.parsers.payment_parser import PaymentParser
from notification.parsers.standing_order_parser import StandingOrderParser


def test_card_purchase_parser_for_generic_card_purchase():
    """CardPurchaseParser should parse generic card purchases without provider."""
    parser = CardPurchaseParser()
    text = "KAUF/DIENSTLEISTUNG VOM 27.03.2025 KARTEN NR. XXXX4821 YOOJI'S ROSENGARTEN BIEL SCHWEIZ"

    assert parser.supports(text), "Card purchase parser should support generic card purchase format"

    result = parser.parse(text)
    assert result.service_type == "Karteneinkauf"
    assert result.provider == ""
    assert result.transaction_type_detail == "Kauf/Dienstleistung"
    assert result.card_number == "XXXX4821"
    assert result.merchant == "YOOJI'S ROSENGARTEN"
    assert result.location == "BIEL"


def test_card_purchase_parser_for_online_shopping():
    """CardPurchaseParser should parse online shopping card purchases."""
    parser = CardPurchaseParser()
    text = "KAUF/ONLINE-SHOPPING VOM 27.03.2025 KARTEN NR. XXXX4821 APPLE.COM/BILL CORK"

    assert parser.supports(text), "Card purchase parser should support online shopping format"

    result = parser.parse(text)
    assert result.service_type == "Karteneinkauf"
    assert result.provider == ""
    assert result.transaction_type_detail == "Kauf/Online-Shopping"
    assert result.card_number == "XXXX4821"
    assert result.merchant == "APPLE.COM/BILL"
    assert result.location == "CORK"


def test_cash_withdrawal_parser():
    """CashWithdrawalParser should parse cash withdrawal transactions."""
    parser = CashWithdrawalParser()
    text = "BARGELDBEZUG VOM 27.03.2025 KARTEN NR. XXXX4821 EINKAUFSZENTRUM METROPOLE BIEL"

    assert parser.supports(text), "Cash withdrawal parser should support valid cash withdrawal format"

    result = parser.parse(text)
    assert result.service_type == "Bargeldbezug"
    assert result.transaction_type_detail == "Bargeldbezug"
    assert result.card_number == "XXXX4821"
    assert result.merchant == "EINKAUFSZENTRUM METROPOLE"
    assert result.location == "BIEL"


def test_credit_transfer_parser_salary_credit():
    """CreditTransferParser should parse salary-like credit transfer format."""
    parser = CreditTransferParser()
    text = "GUTSCHRIFT AUFTRAGGEBER: ALPENWERK AG INDUSTRIESTRASSE 12 CH-5430 WETTINGEN AG MITTEILUNGEN: SALAER MAERZ 2025 REFERENZEN: SALA80E5ED528784F48B451A4175649C112 9988776655/1XXXX 250325CH7LMNQRTS"

    assert parser.supports(text), "Credit transfer parser should support salary credit format"

    result = parser.parse(text)
    assert result.service_type == "Gutschrift"
    assert result.transaction_type_detail == "Gutschrift"
    assert result.counterparty == "ALPENWERK AG INDUSTRIESTRASSE 12 CH-5430 WETTINGEN AG"
    assert "SALAER MAERZ 2025" in result.reference


def test_credit_transfer_parser_sender_credit_with_iban():
    """CreditTransferParser should parse ABSENDER credit format with IBAN."""
    parser = CreditTransferParser()
    text = "GUTSCHRIFT CH6709000000400025000 ABSENDER: VIVAO SYMPANY AG PETER MERIAN-WEG 4 4052 BASEL MITTEILUNGEN: RECHNUNG NR.: 201941771110536469 WE DER ANDREAS110536469 WEDER ANDREASB ETRIFFT DIV. ABRECHNUNGEN REFERENZEN: SYM95CB11F8253446278F81749F26F10588"

    assert parser.supports(text), "Credit transfer parser should support ABSENDER format"

    result = parser.parse(text)
    assert result.service_type == "Gutschrift"
    assert result.transaction_type_detail == "Gutschrift"
    assert result.counterparty_iban == "CH6709000000400025000"
    assert result.counterparty == "VIVAO SYMPANY AG PETER MERIAN-WEG 4 4052 BASEL"
    assert "RECHNUNG NR." in result.reference


def test_twint_send_parser_supports():
    """TwintSendParser should detect TWINT transaction texts"""
    parser = TwintSendParser()
    text = "TWINT GELD SENDEN VOM 26.03.2025 VON TELEFON-NR. +41795555111 AN TELEFON-NR. +41796666222 KEBAB, IMBISS MITTEILUNGEN: KEBAB"

    assert parser.supports(text), "TWINT parser should support valid TWINT text"


def test_twint_send_parser_parse():
    """TwintSendParser should extract merchant and transaction type"""
    parser = TwintSendParser()
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
    assert result.counterparty == "STEUERDIENSTE REGION WEST"
    assert result.counterparty_iban == "41101000000123456"
    assert "2025/04/01 / 7045128" in result.reference


def test_payment_parser():
    """PaymentParser should parse Zahlung (payment) format"""
    parser = PaymentParser()
    text = "LASTSCHRIFT CH6330000011998877665 SUNRISE GMBH POSTFACH 8050 ZURICH"

    assert parser.supports(text), "Should support Zahlung format"

    result = parser.parse(text)
    assert result.service_type == "Lastschrift"
    assert result.transaction_type_detail == "Zahlung"
    assert result.counterparty_iban == "CH6330000011998877665"
    assert "SUNRISE GMBH POSTFACH 8050 ZURICH" in result.counterparty


def test_standing_order_parser():
    """StandingOrderParser should parse Dauerauftrag (standing order) format"""
    parser = StandingOrderParser()
    text = "LASTSCHRIFT DAUERAUFTRAG: 90-33445566 CH3409000000802999554 FAMILIENKASSE MUSTERHAUSEN SENDER REFERENZ: FAMILIENZULAGE"

    assert parser.supports(text), "Should support Dauerauftrag format"

    result = parser.parse(text)
    assert result.service_type == "Lastschrift"
    assert result.transaction_type_detail == "Dauerauftrag"
    assert result.counterparty_iban == "CH3409000000802999554"
    assert result.reference == "90-33445566"


if __name__ == '__main__':
    test_card_purchase_parser_for_generic_card_purchase()
    test_card_purchase_parser_for_online_shopping()
    test_cash_withdrawal_parser()
    test_credit_transfer_parser_salary_credit()
    test_credit_transfer_parser_sender_credit_with_iban()
    test_twint_send_parser_supports()
    test_twint_send_parser_parse()
    test_debit_direct_parser()
    test_payment_parser()
    test_standing_order_parser()
    print("✓ All notification service parser tests passed")
