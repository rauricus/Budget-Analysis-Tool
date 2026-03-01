"""Service-Parser Paket.

Enthält service-spezifische Parser-Strategien und die Registry.
Domänen-/Ingestion-Parser (z.B. TransactionParser) bleiben außerhalb dieses Pakets.
"""

from parsers.apple_pay_parser import ApplePayParser
from parsers.base import NotificationParseResult, ServiceParser
from parsers.registry import NotificationParserRegistry

__all__ = [
    "ServiceParser",
    "NotificationParseResult",
    "ApplePayParser",
    "NotificationParserRegistry",
]
