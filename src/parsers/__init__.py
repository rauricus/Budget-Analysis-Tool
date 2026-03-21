"""Service parser package.

Contains service-specific parser strategies and the registry.
Domain/ingestion parsers (e.g. TransactionParser) remain outside this package.
"""

from parsers.apple_pay_parser import ApplePayParser
from parsers.base import NotificationParseResult, ServiceParser
from parsers.dauerauftrag_parser import DauerauftragParser
from parsers.debit_direct_parser import DebitDirectParser
from parsers.facade import NotificationTextParser
from parsers.registry import NotificationParserRegistry
from parsers.twint_senden_parser import TwintSendenParser
from parsers.zahlung_parser import ZahlungParser

__all__ = [
    "ServiceParser",
    "NotificationParseResult",
    "ApplePayParser",
    "TwintSendenParser",
    "DebitDirectParser",
    "DauerauftragParser",
    "ZahlungParser",
    "NotificationParserRegistry",
    "NotificationTextParser",
]
