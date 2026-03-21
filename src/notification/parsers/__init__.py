"""Service-specific notification parser strategies."""

from notification.parsers.apple_pay_parser import ApplePayParser
from notification.parsers.dauerauftrag_parser import DauerauftragParser
from notification.parsers.debit_direct_parser import DebitDirectParser
from notification.parsers.lastschrift_parser import LastschriftParser
from notification.parsers.twint_senden_parser import TwintSendenParser
from notification.parsers.zahlung_parser import ZahlungParser

__all__ = [
    "ApplePayParser",
    "TwintSendenParser",
    "DebitDirectParser",
    "DauerauftragParser",
    "ZahlungParser",
    "LastschriftParser",
]