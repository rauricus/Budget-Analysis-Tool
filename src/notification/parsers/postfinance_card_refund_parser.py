import re

from notification.base import NotificationParseResult, AbstractServiceParser


class PostFinanceCardRefundParser(AbstractServiceParser):
    """Parser for PostFinance Card refunds."""

    PATTERN = re.compile(
        r"^GUTSCHRIFT\s+POSTFINANCE\s+CARD\s+VOM\s+\d{2}\.\d{2}\.\d{4}\s+"
        r"KARTEN NR\.\s+(?P<card>XXXX\d{4})\s+(?P<rest>.+)$",
        re.IGNORECASE,
    )

    def supports(self, text: str) -> bool:
        return bool(self.PATTERN.match((text or "").strip()))

    def parse(self, text: str) -> NotificationParseResult:
        match = self.PATTERN.match((text or "").strip())
        if not match:
            return NotificationParseResult()

        merchant, location = self._extract_merchant_location(match.group("rest").strip())
        return NotificationParseResult(
            service_type="PostFinance Card Refund",
            transaction_type_detail="Refund",
            card_number=match.group("card").strip(),
            merchant=merchant,
            location=location,
        )

    @staticmethod
    def _extract_merchant_location(text: str) -> tuple[str, str]:
        """Extract merchant and location from the remaining text."""
        if not text:
            return "", ""

        # Look for location in parentheses at the end
        location_match = re.search(r'\(([^)]+)\)\s*$', text)
        if location_match:
            location = location_match.group(1).strip()
            merchant = text[:location_match.start()].strip()
            return merchant, location

        return text, ""
