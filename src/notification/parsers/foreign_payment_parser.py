import re

from notification.base import NotificationParseResult, AbstractServiceParser


class ForeignPaymentParser(AbstractServiceParser):
    """Parser for outgoing foreign payments (AUSLANDZAHLUNG (SEPA) ...)."""

    # AUSLANDZAHLUNG (<scheme>) <currency> <amount> ZUM KURS VON <rate>
    #   <correspondent bank and address> <counterparty IBAN> <counterparty and address>
    #   [SENDER REFERENZ: <reference>]
    # The IBAN anchors the split between bank and counterparty: both are free text
    # with addresses in them, so there is no other reliable boundary.
    PATTERN = re.compile(
        r"^AUSLANDZAHLUNG\s+\((?P<scheme>[^)]+)\)\s+"
        r"(?P<currency>[A-Z]{3})\s+(?P<amount>[\d',.]+)\s+"
        r"ZUM KURS VON\s+(?P<rate>[\d.,]+)\s+"
        r"(?P<bank>.+?)\s+(?P<iban>[A-Z]{2}\d{2}[0-9A-Z]{11,30})\s+"
        r"(?P<counterparty>.+?)"
        r"(?:\s+SENDER REFERENZ:\s+(?P<reference>.+))?$",
        re.IGNORECASE,
    )

    def supports(self, text: str) -> bool:
        return bool(self.PATTERN.match((text or "").strip()))

    def parse(self, text: str) -> NotificationParseResult:
        match = self.PATTERN.match((text or "").strip())
        if not match:
            return NotificationParseResult()

        scheme = (match.group("scheme") or "").strip().upper()
        currency = (match.group("currency") or "").strip().upper()
        amount = (match.group("amount") or "").strip()
        rate = (match.group("rate") or "").strip()
        bank = (match.group("bank") or "").strip()
        sender_reference = (match.group("reference") or "").strip()

        reference_parts = [f"{scheme} {currency} {amount} ZUM KURS VON {rate}", bank]
        if sender_reference:
            reference_parts.append(sender_reference)

        return NotificationParseResult(
            service_type="Direct Debit",
            transaction_type_detail="Foreign Payment",
            counterparty=(match.group("counterparty") or "").strip(),
            counterparty_iban=(match.group("iban") or "").strip(),
            reference=" | ".join(reference_parts),
        )
