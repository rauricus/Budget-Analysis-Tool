import re

from notification.base import NotificationParseResult, ServiceParser


class TwintSendenParser(ServiceParser):
    TWINT_PATTERN = re.compile(
        r"^TWINT\s+GELD\s+SENDEN\s+VOM\s+\d{2}\.\d{2}\.\d{4}\s+VON\s+TELEFON-NR\.\s+(\S+)\s+AN\s+TELEFON-NR\.\s+(\S+)\s+(.*)$",
        re.IGNORECASE,
    )

    def supports(self, text: str) -> bool:
        return bool(self.TWINT_PATTERN.match((text or "").strip()))

    def parse(self, text: str) -> NotificationParseResult:
        match = self.TWINT_PATTERN.match((text or "").strip())
        if not match:
            return NotificationParseResult()

        sender_phone = match.group(1)
        recipient_phone = match.group(2)
        rest = match.group(3).strip()

        merchant = f"{recipient_phone}"
        if rest:
            merchant = f"{recipient_phone} {rest}".strip()

        return NotificationParseResult(
            service_type="Twint",
            transaction_type_detail="Geld senden",
            merchant=merchant,
        )
