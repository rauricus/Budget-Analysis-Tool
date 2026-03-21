import logging
from typing import Optional

from notification.base import NotificationParseResult, AbstractServiceParser
from notification.parsers.apple_pay_parser import ApplePayParser
from notification.parsers.dauerauftrag_parser import DauerauftragParser
from notification.parsers.debit_direct_parser import DebitDirectParser
from notification.parsers.twint_senden_parser import TwintSendenParser
from notification.parsers.zahlung_parser import ZahlungParser


logger = logging.getLogger(__name__)


class NotificationParserRegistry:
    """Registry for service-specific notification text parsers."""

    def __init__(self, parsers: Optional[list[AbstractServiceParser]] = None):
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
