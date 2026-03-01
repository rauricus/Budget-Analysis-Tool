"""Service-Parser Paket.

Enthält service-spezifische Parser-Strategien und die Registry.
Domänen-/Ingestion-Parser (z.B. TransactionParser) bleiben außerhalb dieses Pakets.
"""

from parsers.apple_pay_parser import ApplePayParser
from parsers.base import NotificationParseResult, ServiceParser
from parsers.dauerauftrag_parser import DauerauftragParser
from parsers.debit_direct_parser import DebitDirectParser
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
]
