from parsers.apple_pay_parser import ApplePayParser
from parsers.base import NotificationParseResult, ServiceParser
from typing import Optional


class NotificationParserRegistry:
    """Registry für service-spezifische Avisierungstext-Parser."""

    def __init__(self, parsers: Optional[list[ServiceParser]] = None):
        self.parsers = parsers or [ApplePayParser()]

    def parse(self, avisierungstext: str) -> NotificationParseResult:
        text = (avisierungstext or "").strip()
        if not text:
            return NotificationParseResult()

        for parser in self.parsers:
            if parser.supports(text):
                return parser.parse(text)

        return NotificationParseResult()
