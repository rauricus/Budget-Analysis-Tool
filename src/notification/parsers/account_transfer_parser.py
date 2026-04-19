import re

from notification.base import NotificationParseResult, AbstractServiceParser


class AccountTransferParser(AbstractServiceParser):
    """Parser for account-transfer notifications (KONTOÜBERTRAG AUF/VON CH...)."""

    PATTERN = re.compile(
        r"^KONTOÜBERTRAG\s+(?P<direction>AUF|VON)\s+(?P<iban>CH\S+)\s*(?P<reference>.*)$",
        re.IGNORECASE,
    )

    def supports(self, text: str) -> bool:
        return bool(self.PATTERN.match((text or "").strip()))

    def parse(self, text: str) -> NotificationParseResult:
        match = self.PATTERN.match((text or "").strip())
        if not match:
            return NotificationParseResult()

        direction = (match.group("direction") or "").upper()
        iban = (match.group("iban") or "").strip()
        reference = (match.group("reference") or "").strip()

        return NotificationParseResult(
            service_type="Account Transfer",
            transaction_type_detail=f"Account Transfer {direction.title()}",
            merchant=reference,
            counterparty_iban=iban,
            reference=reference,
        )
