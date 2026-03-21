import re

from notification.base import NotificationParseResult, AbstractServiceParser


class DauerauftragParser(AbstractServiceParser):
    """Parser for standing-order direct debit format (LASTSCHRIFT DAUERAUFTRAG)."""

    PATTERN = re.compile(
        r"^LASTSCHRIFT\s+DAUERAUFTRAG:\s+(\S+)\s+(CH\S+)\s*(.*)$",
        re.IGNORECASE,
    )

    def supports(self, text: str) -> bool:
        text_stripped = (text or "").strip()
        return bool(self.PATTERN.match(text_stripped))

    def parse(self, text: str) -> NotificationParseResult:
        text = (text or "").strip()
        if not self.supports(text):
            return NotificationParseResult()

        match = self.PATTERN.match(text)
        if not match:
            return NotificationParseResult()

        reference = match.group(1).strip()
        recipient_iban = match.group(2).strip()
        rest = match.group(3).strip()

        recipient = rest if rest else ""

        return NotificationParseResult(
            service_type="Lastschrift",
            transaction_type_detail="Dauerauftrag",
            recipient=recipient,
            recipient_iban=recipient_iban,
            reference=reference,
        )
