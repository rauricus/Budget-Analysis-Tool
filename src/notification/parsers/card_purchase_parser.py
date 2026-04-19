import re

from notification.base import NotificationParseResult, AbstractServiceParser


class CardPurchaseParser(AbstractServiceParser):
    # Optional provider prefix (e.g. "APPLE PAY") before KAUF/<detail>.
    # Any content between date and KARTEN NR. is skipped (e.g. foreign-currency conversion).
    PATTERN = re.compile(
        r"^(?:(?P<provider>.+?)\s+)?KAUF/(?P<detail>DIENSTLEISTUNG|ONLINE-SHOPPING)\s+VOM\s+\d{2}\.\d{2}\.\d{4}\s+"
        r"(?:[\w.,/%\s]+?\s+)?"
        r"KARTEN NR\.\s+(?P<card>XXXX\d{4})\s+(?P<rest>.+)$",
        re.IGNORECASE,
    )

    def supports(self, text: str) -> bool:
        return bool(self.PATTERN.match((text or "").strip()))

    def parse(self, text: str) -> NotificationParseResult:
        match = self.PATTERN.match((text or "").strip())
        if not match:
            return NotificationParseResult()

        provider = (match.group("provider") or "").strip().title()
        detail = (match.group("detail") or "").strip().upper()
        detail_map = {
            "DIENSTLEISTUNG": "Purchase/Service",
            "ONLINE-SHOPPING": "Purchase/Online Shopping",
        }
        merchant, location = self._extract_merchant_location(match.group("rest").strip())
        return NotificationParseResult(
            service_type="Card Purchase",
            provider=provider,
            transaction_type_detail=detail_map.get(detail, ""),
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
