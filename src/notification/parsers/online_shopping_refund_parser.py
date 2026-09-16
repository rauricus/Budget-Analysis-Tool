import re

from notification.base import NotificationParseResult, AbstractServiceParser


class OnlineShoppingRefundParser(AbstractServiceParser):
    """Parse refunds for online shopping purchases (the credit counterpart of
    :class:`EFinancePurchaseParser`)."""

    # Same shape as the purchase notification, with "GUTSCHRIFT ONLINE SHOPPING"
    # instead of "KAUF/ONLINE-SHOPPING" and an optional provider prefix (e.g. "PF PAY").
    PATTERN = re.compile(
        r"^(?:(?P<provider>.+?)\s+)?GUTSCHRIFT\s+ONLINE\s+SHOPPING\s+VOM\s+\d{2}\.\d{2}\.\d{4}\s+"
        r"(?P<merchant>.+?)\s+(?P<descriptor>N/A|\S+\.\S+)\s+"
        r"PAYMENT ID\s+(?P<payment_id>[A-Z0-9_-]+)\s+BESTELLNUMMER\s+(?P<order_ref>[A-Z0-9_-]+)$",
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
            service_type="Card Purchase",
            provider=provider,
            transaction_type_detail="Refund/Online Shopping",
            merchant=merchant,
            reference=f"PAYMENT ID {payment_id} BESTELLNUMMER {order_ref}",
        )
