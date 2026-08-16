import re

from notification.base import NotificationParseResult, AbstractServiceParser


class PaymentParser(AbstractServiceParser):
    """Parser for direct debit payment formats (LASTSCHRIFT ... CH<iban> ...)."""

    # Pattern: LASTSCHRIFT [optional bank route] CH<iban> <counterparty>
    # The IBAN group must be a full 21-character Swiss IBAN. A loose "CH\S+" would
    # also match counterparty words starting with CH (for example "CHRISTIAN"), which
    # cuts the payee name in half.
    PATTERN = re.compile(
        r"^LASTSCHRIFT\s+(?:(.+?)\s+)?(CH\d{2}[0-9A-Z]{17})\s+(.+)$",
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

        bank_route = (match.group(1) or "").strip()
        counterparty_iban = match.group(2).strip()
        counterparty = match.group(3).strip()

        return NotificationParseResult(
            service_type="Direct Debit",
            transaction_type_detail="Payment",
            counterparty=counterparty,
            counterparty_iban=counterparty_iban,
            reference=bank_route,
        )
