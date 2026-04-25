import re

from notification.base import NotificationParseResult, AbstractServiceParser


class TwintSendParser(AbstractServiceParser):
    # Format with sender phone: "VON TELEFON-NR. <sender> AN TELEFON-NR. <recipient> <rest>"
    TWINT_PATTERN = re.compile(
        r"^TWINT\s+GELD\s+SENDEN\s+VOM\s+\d{2}\.\d{2}\.\d{4}\s+VON\s+TELEFON-NR\.\s+(\S+)\s+AN\s+TELEFON-NR\.\s+(\S+)\s+(.*)$",
        re.IGNORECASE,
    )
    # Direct format without sender phone: "AN TELEFON-NR. <recipient> [, <name>] [MITTEILUNGEN: <msg>]"
    TWINT_DIRECT_PATTERN = re.compile(
        r"^TWINT\s+GELD\s+SENDEN\s+VOM\s+\d{2}\.\d{2}\.\d{4}\s+AN\s+TELEFON-NR\.\s+(\S+)\s*(.*)$",
        re.IGNORECASE,
    )

    def supports(self, text: str) -> bool:
        t = (text or "").strip()
        return bool(self.TWINT_PATTERN.match(t) or self.TWINT_DIRECT_PATTERN.match(t))

    @staticmethod
    def _build_counterparty_and_reference(recipient_phone: str, rest: str) -> tuple[str, str]:
        """Return parsed counterparty and optional reference from trailing text."""
        normalized_rest = (rest or "").strip()
        if normalized_rest.startswith(","):
            normalized_rest = normalized_rest[1:].strip()

        mitteilungen_idx = normalized_rest.upper().find("MITTEILUNGEN:")
        if mitteilungen_idx >= 0:
            name = normalized_rest[:mitteilungen_idx].strip()
            message = normalized_rest[mitteilungen_idx + len("MITTEILUNGEN:"):].strip()
            counterparty = " ".join(p for p in [recipient_phone, name] if p)
            reference = f"MITTEILUNGEN: {message}" if message else ""
            return counterparty, reference

        counterparty = " ".join(p for p in [recipient_phone, normalized_rest] if p)
        return counterparty, ""

    def parse(self, text: str) -> NotificationParseResult:
        t = (text or "").strip()

        match = self.TWINT_PATTERN.match(t)
        if match:
            recipient_phone = match.group(2)
            rest = match.group(3).strip()
            counterparty, reference = self._build_counterparty_and_reference(recipient_phone, rest)
            return NotificationParseResult(
                service_type="Twint",
                provider="Twint",
                transaction_type_detail="Send Money",
                counterparty=counterparty,
                reference=reference,
            )

        match = self.TWINT_DIRECT_PATTERN.match(t)
        if match:
            recipient_phone = match.group(1)
            rest = match.group(2).strip()
            counterparty, reference = self._build_counterparty_and_reference(recipient_phone, rest)
            return NotificationParseResult(
                service_type="Twint",
                provider="Twint",
                transaction_type_detail="Send Money",
                counterparty=counterparty,
                reference=reference,
            )

        return NotificationParseResult()
