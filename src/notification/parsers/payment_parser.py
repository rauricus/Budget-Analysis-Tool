import re

from notification.base import NotificationParseResult, AbstractServiceParser


class PaymentParser(AbstractServiceParser):
    """Parser for direct debit payment format (LASTSCHRIFT ... CH<iban> ...)."""

    # Pattern: LASTSCHRIFT CH<iban> <merchant> (but not DAUERAUFTRAG)
    PATTERN = re.compile(
        r"^LASTSCHRIFT\s+(CH\S+)\s+(.+)$",
        re.IGNORECASE,
    )

    def supports(self, text: str) -> bool:
        text_stripped = (text or "").strip()
        # Must be LASTSCHRIFT, but not a DAUERAUFTRAG variant.
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

        counterparty_iban = match.group(1).strip()
        counterparty = match.group(2).strip()

        return NotificationParseResult(
            service_type="Lastschrift",
            transaction_type_detail="Zahlung",
            counterparty=counterparty,
            counterparty_iban=counterparty_iban,
        )
