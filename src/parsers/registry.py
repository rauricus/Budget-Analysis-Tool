import logging
from typing import Optional

from parsers.apple_pay_parser import ApplePayParser
from parsers.base import NotificationParseResult, ServiceParser
from parsers.dauerauftrag_parser import DauerauftragParser
from parsers.debit_direct_parser import DebitDirectParser
from parsers.twint_senden_parser import TwintSendenParser
from parsers.zahlung_parser import ZahlungParser


logger = logging.getLogger(__name__)


class NotificationParserRegistry:
    """Registry for service-specific notification text parsers."""

    def __init__(self, parsers: Optional[list[ServiceParser]] = None):
        self.parsers = parsers or [
            ApplePayParser(),
            TwintSendenParser(),
            DebitDirectParser(),
            DauerauftragParser(),
            ZahlungParser(),
        ]

    def parse(self, avisierungstext: str) -> NotificationParseResult:
        text = (avisierungstext or "").strip()
        if not text:
            return NotificationParseResult()

        for parser in self.parsers:
            if parser.supports(text):
                return parser.parse(text)

        logger.warning("No ServiceParser match for notification text: %s", text)

        return NotificationParseResult()
