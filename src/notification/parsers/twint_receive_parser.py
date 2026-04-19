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

    def parse(self, text: str) -> NotificationParseResult:
        t = (text or "").strip()
        match = self.TWINT_RECEIVE_PATTERN.match(t)
        if not match:
            return NotificationParseResult()

        sender_phone = match.group(1)
        rest = match.group(2).strip()
        merchant = " ".join(p for p in [sender_phone, rest] if p)

        return NotificationParseResult(
            service_type="Twint",
            provider="Twint",
            transaction_type_detail="Receive Money",
            merchant=merchant,
        )
