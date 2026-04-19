import re

from notification.base import NotificationParseResult, AbstractServiceParser


class TwintPurchaseParser(AbstractServiceParser):
    """Parser for TWINT merchant purchases."""

    PATTERN = re.compile(
        r"^TWINT\s+KAUF/(?P<detail>DIENSTLEISTUNG|ONLINE-SHOPPING)\s+VOM\s+\d{2}\.\d{2}\.\d{4}\s+(?P<rest>.+)$",
        re.IGNORECASE,
    )

    def supports(self, text: str) -> bool:
        return bool(self.PATTERN.match((text or "").strip()))

    def parse(self, text: str) -> NotificationParseResult:
        match = self.PATTERN.match((text or "").strip())
        if not match:
            return NotificationParseResult()

        detail = (match.group("detail") or "").strip().upper()
        detail_map = {
            "DIENSTLEISTUNG": "Kauf/Dienstleistung",
            "ONLINE-SHOPPING": "Kauf/Online-Shopping",
        }
        merchant, location = self._extract_merchant_location(match.group("rest").strip())

        return NotificationParseResult(
            service_type="Twint",
            provider="Twint",
            transaction_type_detail=detail_map.get(detail, ""),
            merchant=merchant,
            location=location,
        )

    @staticmethod
    def _extract_merchant_location(text: str) -> tuple[str, str]:
        working = (text or "").strip()
        if not working:
            return "", ""

        if working.upper().endswith(" (CH)"):
            working = working[: -len(" (CH)")].strip()

        tokens = working.split()
        if len(tokens) < 2:
            return working, ""

        location = tokens[-1]
        merchant = " ".join(tokens[:-1]).strip()
        return merchant, location
