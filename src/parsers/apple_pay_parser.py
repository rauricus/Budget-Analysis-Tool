import re

from parsers.base import NotificationParseResult, ServiceParser


class ApplePayParser(ServiceParser):
    APPLE_PAY_PATTERN = re.compile(
        r"^(?P<prefix>APPLE PAY KAUF/DIENSTLEISTUNG)\s+VOM\s+\d{2}\.\d{2}\.\d{4}\s+KARTEN NR\.\s+(?P<card>XXXX\d{4})\s+(?P<rest>.+)$",
        re.IGNORECASE,
    )

    def supports(self, text: str) -> bool:
        return bool(self.APPLE_PAY_PATTERN.match((text or "").strip()))

    def parse(self, text: str) -> NotificationParseResult:
        match = self.APPLE_PAY_PATTERN.match((text or "").strip())
        if not match:
            return NotificationParseResult()

        merchant, location = self._extract_merchant_location(match.group("rest").strip())
        return NotificationParseResult(
            service_type="APPLE PAY",
            card_number=match.group("card").strip(),
            merchant=merchant,
            location=location,
        )

    @staticmethod
    def _extract_merchant_location(text: str) -> tuple[str, str]:
        if not text:
            return "", ""

        working = text.strip()
        upper = working.upper()

        if " WAREN " in upper:
            split_idx = upper.rfind(" WAREN ")
            working = working[:split_idx].strip()
            upper = working.upper()

        if upper.endswith(" SCHWEIZ"):
            working = working[: -len(" SCHWEIZ")].strip()

        tokens = working.split()
        if len(tokens) < 2:
            return working, ""

        location = tokens[-1]
        merchant = " ".join(tokens[:-1]).strip()
        return merchant, location
