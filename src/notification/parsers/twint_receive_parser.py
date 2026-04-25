import re

from notification.base import NotificationParseResult, AbstractServiceParser


class TwintReceiveParser(AbstractServiceParser):
    # Format: "TWINT GELD EMPFANGEN VOM <date> VON TELEFON-NR. <phone> <name> [MITTEILUNGEN: <message>]"
    TWINT_RECEIVE_PATTERN = re.compile(
        r"^TWINT\s+GELD\s+EMPFANGEN\s+VOM\s+\d{2}\.\d{2}\.\d{4}\s+VON\s+TELEFON-NR\.\s+(\S+)\s*(.*)$",
        re.IGNORECASE,
    )

    def supports(self, text: str) -> bool:
        return bool(self.TWINT_RECEIVE_PATTERN.match((text or "").strip()))

    @staticmethod
    def _build_counterparty_and_reference(sender_phone: str, rest: str) -> tuple[str, str]:
        """Return parsed counterparty and optional reference from trailing text."""
        normalized_rest = (rest or "").strip()
        mitteilungen_idx = normalized_rest.upper().find("MITTEILUNGEN:")
        if mitteilungen_idx >= 0:
            name = normalized_rest[:mitteilungen_idx].strip()
            message = normalized_rest[mitteilungen_idx + len("MITTEILUNGEN:"):].strip()
            counterparty = " ".join(p for p in [sender_phone, name] if p)
            reference = f"MITTEILUNGEN: {message}" if message else ""
            return counterparty, reference

        counterparty = " ".join(p for p in [sender_phone, normalized_rest] if p)
        return counterparty, ""

    def parse(self, text: str) -> NotificationParseResult:
        t = (text or "").strip()
        match = self.TWINT_RECEIVE_PATTERN.match(t)
        if not match:
            return NotificationParseResult()

        sender_phone = match.group(1)
        rest = match.group(2).strip()
        counterparty, reference = self._build_counterparty_and_reference(sender_phone, rest)

        return NotificationParseResult(
            service_type="Twint",
            provider="Twint",
            transaction_type_detail="Receive Money",
            counterparty=counterparty,
            reference=reference,
        )
