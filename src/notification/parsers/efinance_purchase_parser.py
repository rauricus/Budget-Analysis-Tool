import re

from notification.base import NotificationParseResult, AbstractServiceParser


class EFinancePurchaseParser(AbstractServiceParser):
    """Parse PostFinance eFinance purchase notifications."""

    PATTERN = re.compile(
        r"^(?:(?P<provider>.+?)\s+)?KAUF/ONLINE-SHOPPING\s+VOM\s+\d{2}\.\d{2}\.\d{4}\s+"
        r"(?P<merchant>.+?)\s+N/A\s+PAYMENT ID\s+(?P<payment_id>[A-Z0-9-]+)\s+BESTELLNUMMER\s+(?P<order_ref>[A-Z0-9-]+)$",
        re.IGNORECASE,
    )

    def supports(self, text: str) -> bool:
        return bool(self.PATTERN.match((text or "").strip()))

    def parse(self, text: str) -> NotificationParseResult:
        match = self.PATTERN.match((text or "").strip())
        if not match:
            return NotificationParseResult()

        provider = (match.group("provider") or "").strip().title()
        merchant = (match.group("merchant") or "").strip()
        payment_id = (match.group("payment_id") or "").strip()
        order_ref = (match.group("order_ref") or "").strip()

        return NotificationParseResult(
            service_type="Karteneinkauf",
            provider=provider,
            transaction_type_detail="Kauf/Online-Shopping",
            merchant=merchant,
            reference=f"PAYMENT ID {payment_id} BESTELLNUMMER {order_ref}",
        )
