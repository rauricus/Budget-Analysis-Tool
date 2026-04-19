import re

from notification.base import NotificationParseResult, AbstractServiceParser


class BankPackageFeeParser(AbstractServiceParser):
    """Parser for bank package fee notifications (PREIS FUER BANKPAKET ...)."""

    PATTERN = re.compile(
        r"^PREIS\s+FUER\s+BANKPAKET\s+.+$|^PREIS\s+FÜR\s+BANKPAKET\s+.+$",
        re.IGNORECASE,
    )

    def supports(self, text: str) -> bool:
        return bool(self.PATTERN.match((text or "").strip()))

    def parse(self, text: str) -> NotificationParseResult:
        text_stripped = (text or "").strip()
        if not self.supports(text_stripped):
            return NotificationParseResult()

        return NotificationParseResult(
            service_type="Fees",
            transaction_type_detail="Bank Package Fee",
            reference=text_stripped,
        )
