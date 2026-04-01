import re

from notification.base import NotificationParseResult, AbstractServiceParser


class CashWithdrawalParser(AbstractServiceParser):
    PATTERN = re.compile(
        r"^BARGELDBEZUG\s+VOM\s+\d{2}\.\d{2}\.\d{4}\s+KARTEN NR\.\s+(?P<card>XXXX\d{4})\s+(?P<rest>.+)$",
        re.IGNORECASE,
    )

    def supports(self, text: str) -> bool:
        return bool(self.PATTERN.match((text or "").strip()))

    def parse(self, text: str) -> NotificationParseResult:
        match = self.PATTERN.match((text or "").strip())
        if not match:
            return NotificationParseResult()

        merchant, location = self._extract_merchant_location(match.group("rest").strip())
        return NotificationParseResult(
            service_type="Bargeldbezug",
            transaction_type_detail="Bargeldbezug",
            card_number=match.group("card").strip(),
            merchant=merchant,
            location=location,
        )

    @staticmethod
    def _extract_merchant_location(text: str) -> tuple[str, str]:
        if not text:
            return "", ""

        tokens = text.split()
        if len(tokens) < 2:
            return text, ""

        location = tokens[-1]
        merchant = " ".join(tokens[:-1]).strip()
        return merchant, location
