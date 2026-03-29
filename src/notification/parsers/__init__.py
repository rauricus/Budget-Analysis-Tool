"""Service-specific notification parser strategies."""

from notification.parsers.card_purchase_parser import CardPurchaseParser
from notification.parsers.dauerauftrag_parser import DauerauftragParser
from notification.parsers.debit_direct_parser import DebitDirectParser
from notification.parsers.twint_senden_parser import TwintSendenParser
from notification.parsers.zahlung_parser import ZahlungParser

__all__ = [
    "CardPurchaseParser",
    "TwintSendenParser",
    "DebitDirectParser",
    "DauerauftragParser",
    "ZahlungParser",
]