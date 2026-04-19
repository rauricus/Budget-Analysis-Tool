#!/usr/bin/env python3
"""Test notification service parsers for Twint and Lastschrift variants."""
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from notification.parsers.twint_send_parser import TwintSendParser
from notification.parsers.bank_package_fee_parser import BankPackageFeeParser
from notification.parsers.cash_withdrawal_parser import CashWithdrawalParser
from notification.parsers.card_purchase_parser import CardPurchaseParser
from notification.parsers.efinance_purchase_parser import EFinancePurchaseParser
from notification.parsers.credit_transfer_parser import CreditTransferParser
from notification.parsers.konto_transfer_parser import KontoTransferParser
from notification.parsers.debit_direct_parser import DebitDirectParser
from notification.parsers.payment_parser import PaymentParser
from notification.parsers.standing_order_parser import StandingOrderParser
from notification.parsers.twint_receive_parser import TwintReceiveParser
from notification.parsers.twint_purchase_parser import TwintPurchaseParser


def test_card_purchase_parser_for_generic_card_purchase():
    """CardPurchaseParser should parse generic card purchases without provider."""
    parser = CardPurchaseParser()
    text = "KAUF/DIENSTLEISTUNG VOM 27.03.2025 KARTEN NR. XXXX4821 YOOJI'S ROSENGARTEN BIEL SCHWEIZ"

    assert parser.supports(text), "Card purchase parser should support generic card purchase format"

    result = parser.parse(text)
    assert result.service_type == "Card Purchase"
    assert result.provider == ""
    assert result.transaction_type_detail == "Purchase/Service"
    assert result.card_number == "XXXX4821"
    assert result.merchant == "YOOJI'S ROSENGARTEN"
    assert result.location == "BIEL"


def test_card_purchase_parser_for_online_shopping():
    """CardPurchaseParser should parse online shopping card purchases."""
    parser = CardPurchaseParser()
    text = "KAUF/ONLINE-SHOPPING VOM 27.03.2025 KARTEN NR. XXXX4821 APPLE.COM/BILL CORK"

    assert parser.supports(text), "Card purchase parser should support online shopping format"

    result = parser.parse(text)
    assert result.service_type == "Card Purchase"
    assert result.provider == ""
    assert result.transaction_type_detail == "Purchase/Online Shopping"
    assert result.card_number == "XXXX4821"
    assert result.merchant == "APPLE.COM/BILL"
    assert result.location == "CORK"


def test_card_purchase_parser_for_foreign_currency():
    """CardPurchaseParser should parse card purchases with foreign currency conversion block."""
    parser = CardPurchaseParser()
    text = "APPLE PAY KAUF/ONLINE-SHOPPING VOM 25.03.2025 USD 19.99 ZUM KURS VON 0.9200 BETRAG IN KONTOWÄHRUNG 18.39 1.5% BEARBEITUNGSZUSCHLAG 0.28 KARTEN NR. XXXX4821 CLOUDSERVICE INC SAN JOSE"

    assert parser.supports(text), "Card purchase parser should support foreign currency format"

    result = parser.parse(text)
    assert result.service_type == "Card Purchase"
    assert result.provider == "Apple Pay"
    assert result.transaction_type_detail == "Purchase/Online Shopping"
    assert result.card_number == "XXXX4821"
    assert result.merchant == "CLOUDSERVICE INC SAN"
    assert result.location == "JOSE"


def test_efinance_purchase_parser_without_card_number():
    """EFinancePurchaseParser should parse online shopping notifications with payment ID/order reference."""
    parser = EFinancePurchaseParser()
    text = "KAUF/ONLINE-SHOPPING VOM 19.01.2025 ONLINE HAUSHALT AG N/A PAYMENT ID 250119000000000000 BESTELLNUMMER DP-P-00000000"

    assert parser.supports(text), "Online shopping parser should support payment ID format"

    result = parser.parse(text)
    assert result.service_type == "Card Purchase"
    assert result.provider == ""
    assert result.transaction_type_detail == "Purchase/Online Shopping"
    assert result.card_number == ""
    assert result.merchant == "ONLINE HAUSHALT AG"
    assert result.location == ""
    assert result.reference == "PAYMENT ID 250119000000000000 BESTELLNUMMER DP-P-00000000"


def test_cash_withdrawal_parser():
    """CashWithdrawalParser should parse cash withdrawal transactions."""
    parser = CashWithdrawalParser()
    text = "BARGELDBEZUG VOM 27.03.2025 KARTEN NR. XXXX4821 EINKAUFSZENTRUM METROPOLE BIEL"

    assert parser.supports(text), "Cash withdrawal parser should support valid cash withdrawal format"

    result = parser.parse(text)
    assert result.service_type == "Cash Withdrawal"
    assert result.transaction_type_detail == "Cash Withdrawal"
    assert result.card_number == "XXXX4821"
    assert result.merchant == "EINKAUFSZENTRUM METROPOLE"
    assert result.location == "BIEL"


def test_credit_transfer_parser_salary_credit():
    """CreditTransferParser should parse salary-like credit transfer format."""
    parser = CreditTransferParser()
    text = "GUTSCHRIFT AUFTRAGGEBER: ALPENWERK AG INDUSTRIESTRASSE 12 CH-5430 WETTINGEN AG MITTEILUNGEN: SALAER MAERZ 2025 REFERENZEN: SALA80E5ED528784F48B451A4175649C112 9988776655/1XXXX 250325CH7LMNQRTS"

    assert parser.supports(text), "Credit transfer parser should support salary credit format"

    result = parser.parse(text)
    assert result.service_type == "Credit"
    assert result.transaction_type_detail == "Credit"
    assert result.counterparty == "ALPENWERK AG INDUSTRIESTRASSE 12 CH-5430 WETTINGEN AG"
    assert "SALAER MAERZ 2025" in result.reference


def test_credit_transfer_parser_sender_credit_with_iban():
    """CreditTransferParser should parse ABSENDER credit format with IBAN."""
    parser = CreditTransferParser()
    text = "GUTSCHRIFT CH6709000000400025000 ABSENDER: VIVAO SYMPANY AG PETER MERIAN-WEG 4 4052 BASEL MITTEILUNGEN: RECHNUNG NR.: 201941771110536469 WE DER ANDREAS110536469 WEDER ANDREASB ETRIFFT DIV. ABRECHNUNGEN REFERENZEN: SYM95CB11F8253446278F81749F26F10588"

    assert parser.supports(text), "Credit transfer parser should support ABSENDER format"

    result = parser.parse(text)
    assert result.service_type == "Credit"
    assert result.transaction_type_detail == "Credit"
    assert result.counterparty_iban == "CH6709000000400025000"
    assert result.counterparty == "VIVAO SYMPANY AG PETER MERIAN-WEG 4 4052 BASEL"
    assert "RECHNUNG NR." in result.reference


def test_konto_transfer_parser_for_debit_transfer_to_iban():
    """KontoTransferParser should parse KONTOUEBERTRAG AUF format with IBAN and message."""
    parser = KontoTransferParser()
    text = "KONTOÜBERTRAG AUF CH5600000000000000000 ZMITTAG 13.1."

    assert parser.supports(text), "Konto transfer parser should support AUF format"

    result = parser.parse(text)
    assert result.service_type == "Account Transfer"
    assert result.transaction_type_detail == "Account Transfer Auf"
    assert result.merchant == "ZMITTAG 13.1."
    assert result.counterparty_iban == "CH5600000000000000000"
    assert result.reference == "ZMITTAG 13.1."


def test_bank_package_fee_parser():
    """BankPackageFeeParser should parse bank package fee notifications."""
    parser = BankPackageFeeParser()
    text = "PREIS FÜR BANKPAKET SMART 02.2025"

    assert parser.supports(text), "Bank package fee parser should support fee format"

    result = parser.parse(text)
    assert result.service_type == "Fees"
    assert result.transaction_type_detail == "Bank Package Fee"
    assert result.reference == "PREIS FÜR BANKPAKET SMART 02.2025"


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
    assert result.provider == "Twint"
    assert result.transaction_type_detail == "Send Money"
    assert "+41796666222 KEBAB, IMBISS" in result.merchant


def test_twint_send_parser_direct_supports():
    """TwintSendParser should detect direct TWINT send texts (without sender phone)"""
    parser = TwintSendParser()
    text = "TWINT GELD SENDEN VOM 22.03.2025 AN TELEFON-NR. +41790000000 , MAX MUSTER MITTEILUNGEN: ESSEN GESTERN ABEND"

    assert parser.supports(text), "TWINT parser should support direct send format"


def test_twint_send_parser_direct_parse():
    """TwintSendParser should parse direct send format (without sender phone)"""
    parser = TwintSendParser()
    text = "TWINT GELD SENDEN VOM 22.03.2025 AN TELEFON-NR. +41790000000 , MAX MUSTER MITTEILUNGEN: ESSEN GESTERN ABEND"

    result = parser.parse(text)
    assert result.service_type == "Twint"
    assert result.provider == "Twint"
    assert result.transaction_type_detail == "Send Money"
    assert "+41790000000" in result.merchant
    assert "MAX MUSTER" in result.merchant
    assert "ESSEN GESTERN ABEND" in result.merchant


def test_twint_send_parser_direct_parse_without_mitteilungen():
    """TwintSendParser should parse direct send format with only name, no message"""
    parser = TwintSendParser()
    text = "TWINT GELD SENDEN VOM 22.03.2025 AN TELEFON-NR. +41790000000 , MAX MUSTER"

    result = parser.parse(text)
    assert result.service_type == "Twint"
    assert result.provider == "Twint"
    assert result.transaction_type_detail == "Send Money"
    assert "+41790000000" in result.merchant
    assert "MAX MUSTER" in result.merchant


def test_twint_receive_parser_supports():
    """TwintReceiveParser should detect TWINT receive transaction texts."""
    parser = TwintReceiveParser()
    text = "TWINT GELD EMPFANGEN VOM 25.01.2025 VON TELEFON-NR. +41790000000 MAX MUSTER MITTEILUNGEN: TEST"

    assert parser.supports(text), "TWINT receive parser should support valid receive format"


def test_twint_receive_parser_parse():
    """TwintReceiveParser should extract sender phone and remaining info."""
    parser = TwintReceiveParser()
    text = "TWINT GELD EMPFANGEN VOM 25.01.2025 VON TELEFON-NR. +41790000000 MAX MUSTER MITTEILUNGEN: TEST"

    result = parser.parse(text)
    assert result.service_type == "Twint"
    assert result.provider == "Twint"
    assert result.transaction_type_detail == "Receive Money"
    assert "+41790000000" in result.merchant
    assert "MAX MUSTER" in result.merchant
    assert "MITTEILUNGEN: TEST" in result.merchant


def test_twint_purchase_parser_parse():
    """TwintPurchaseParser should parse TWINT merchant purchase notifications."""
    parser = TwintPurchaseParser()
    text = "TWINT KAUF/DIENSTLEISTUNG VOM 27.02.2025 MUSTER CAFE YVERDON-LES-BAINS (CH)"

    assert parser.supports(text), "TWINT purchase parser should support merchant purchase format"

    result = parser.parse(text)
    assert result.service_type == "Twint"
    assert result.provider == "Twint"
    assert result.transaction_type_detail == "Purchase/Service"
    assert result.merchant == "MUSTER CAFE"
    assert result.location == "YVERDON-LES-BAINS"


def test_debit_direct_parser():
    """DebitDirectParser should parse Debit Direct format"""
    parser = DebitDirectParser()
    text = "AUFTRAG CH-DD-BASISLASTSCHRIFT ID-NR. DES ZAHLUNGSEMPFÄNGERS: 41101000000123456 REFERENZ-NR: TAXA2589-695B-4A7B-B290-C9A7BEF7001 ZAHLUNGSEMPFÄNGER: STEUERDIENSTE REGION WEST MITTEILUNGEN: 2025/04/01 / 7045128 TRANSAKTIONS-ID: 305-77445512"

    assert parser.supports(text), "Should support Debit Direct format"

    result = parser.parse(text)
    assert result.service_type == "Direct Debit"
    assert result.transaction_type_detail == "Direct Debit (CH-DD)"
    assert result.counterparty == "STEUERDIENSTE REGION WEST"
    assert result.counterparty_iban == "41101000000123456"
    assert "2025/04/01 / 7045128" in result.reference


def test_payment_parser():
    """PaymentParser should parse standard and bank-route payment formats."""
    parser = PaymentParser()
    text = "LASTSCHRIFT CH6330000011998877665 SUNRISE GMBH POSTFACH 8050 ZURICH"
    bank_route_text = "LASTSCHRIFT MUSTERBANK AG MUSTERSTRASSE 12 6002 LUZERN CH5600000000000000000 MOBILITY MUSTER GENOSSENSCHAFT 6343 ROTKREUZ"

    assert parser.supports(text), "Should support Zahlung format"
    assert parser.supports(bank_route_text), "Should support Zahlung format with bank route details"

    result = parser.parse(text)
    assert result.service_type == "Direct Debit"
    assert result.transaction_type_detail == "Payment"
    assert result.counterparty_iban == "CH6330000011998877665"
    assert "SUNRISE GMBH POSTFACH 8050 ZURICH" in result.counterparty

    bank_route_result = parser.parse(bank_route_text)
    assert bank_route_result.service_type == "Direct Debit"
    assert bank_route_result.transaction_type_detail == "Payment"
    assert bank_route_result.counterparty_iban == "CH5600000000000000000"
    assert bank_route_result.counterparty == "MOBILITY MUSTER GENOSSENSCHAFT 6343 ROTKREUZ"
    assert bank_route_result.reference == "MUSTERBANK AG MUSTERSTRASSE 12 6002 LUZERN"


def test_standing_order_parser():
    """StandingOrderParser should parse Dauerauftrag (standing order) format"""
    parser = StandingOrderParser()
    text = "LASTSCHRIFT DAUERAUFTRAG: 90-33445566 CH3409000000802999554 FAMILIENKASSE MUSTERHAUSEN SENDER REFERENZ: FAMILIENZULAGE"

    assert parser.supports(text), "Should support Dauerauftrag format"

    result = parser.parse(text)
    assert result.service_type == "Direct Debit"
    assert result.transaction_type_detail == "Standing Order"
    assert result.counterparty_iban == "CH3409000000802999554"
    assert result.reference == "90-33445566"


if __name__ == '__main__':
    test_card_purchase_parser_for_generic_card_purchase()
    test_card_purchase_parser_for_online_shopping()
    test_card_purchase_parser_for_foreign_currency()
    test_efinance_purchase_parser_without_card_number()
    test_cash_withdrawal_parser()
    test_credit_transfer_parser_salary_credit()
    test_credit_transfer_parser_sender_credit_with_iban()
    test_konto_transfer_parser_for_debit_transfer_to_iban()
    test_bank_package_fee_parser()
    test_twint_send_parser_supports()
    test_twint_send_parser_parse()
    test_twint_send_parser_direct_supports()
    test_twint_send_parser_direct_parse()
    test_twint_send_parser_direct_parse_without_mitteilungen()
    test_twint_receive_parser_supports()
    test_twint_receive_parser_parse()
    test_twint_purchase_parser_parse()
    test_debit_direct_parser()
    test_payment_parser()
    test_standing_order_parser()
    print("✓ All notification service parser tests passed")
