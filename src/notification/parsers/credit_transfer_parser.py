import re

from notification.base import NotificationParseResult, AbstractServiceParser


class CreditTransferParser(AbstractServiceParser):
    """Parser for credit transfers (GUTSCHRIFT AUFTRAGGEBER/ABSENDER ...)."""

    PATTERN = re.compile(
        r"^GUTSCHRIFT(?:\s+(?P<iban>CH\S+))?\s+(?:AUFTRAGGEBER|ABSENDER):\s+(?P<sender>.+?)(?:\s+MITTEILUNGEN:\s+(?P<message>.+?))?(?:\s+REFERENZEN:\s+(?P<references>.+))?$",
        re.IGNORECASE,
    )

    def supports(self, text: str) -> bool:
        return bool(self.PATTERN.match((text or "").strip()))

    def parse(self, text: str) -> NotificationParseResult:
        match = self.PATTERN.match((text or "").strip())
        if not match:
            return NotificationParseResult()

        iban = (match.group("iban") or "").strip()
        sender = (match.group("sender") or "").strip()
        message = (match.group("message") or "").strip()
        references = (match.group("references") or "").strip()

        reference_parts = [part for part in [message, references] if part]
        reference = " | ".join(reference_parts)

        return NotificationParseResult(
            service_type="Credit",
            transaction_type_detail="Credit",
            counterparty=sender,
            counterparty_iban=iban,
            reference=reference,
        )
