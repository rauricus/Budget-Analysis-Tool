import re

from notification.base import NotificationParseResult, ServiceParser


class ZahlungParser(ServiceParser):
    """Parser for LASTSCHRIFT payments (debit with IBAN)."""

    # LASTSCHRIFT CH<iban> <merchant> (but not DAUERAUFTRAG)
    PATTERN = re.compile(
        r"^LASTSCHRIFT\s+(CH\S+)\s+(.+)$",
        re.IGNORECASE,
    )

    def supports(self, text: str) -> bool:
        text_stripped = (text or "").strip()
        # Must be LASTSCHRIFT, but not DAUERAUFTRAG
        if not self.PATTERN.match(text_stripped):
            return False
        return "DAUERAUFTRAG" not in text_stripped.upper()

    def parse(self, text: str) -> NotificationParseResult:
        text = (text or "").strip()
        if not self.supports(text):
            return NotificationParseResult()

        match = self.PATTERN.match(text)
        if not match:
            return NotificationParseResult()

        recipient_iban = match.group(1).strip()
        recipient = match.group(2).strip()

        return NotificationParseResult(
            service_type="Lastschrift",
            transaction_type_detail="Zahlung",
            recipient=recipient,
            recipient_iban=recipient_iban,
        )
