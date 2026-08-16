import re

from notification.base import NotificationParseResult, AbstractServiceParser


class CashWithdrawalParser(AbstractServiceParser):
    # Any content between date and KARTEN NR. is skipped (e.g. foreign-currency conversion).
    PATTERN = re.compile(
        r"^BARGELDBEZUG\s+VOM\s+\d{2}\.\d{2}\.\d{4}\s+"
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

        merchant, location = self._extract_merchant_location(match.group("rest").strip())
        return NotificationParseResult(
            service_type="Cash Withdrawal",
            transaction_type_detail="Cash Withdrawal",
            card_number=match.group("card").strip(),
            merchant=merchant,
            location=location,
        )

    @staticmethod
    def _extract_merchant_location(text: str) -> tuple[str, str]:
        if not text:
            return "", ""

        # Drop a trailing country marker like "(CH)" so the last token stays the location.
        text = re.sub(r"\s*\([^)]+\)\s*$", "", text).strip()

        tokens = text.split()
        if len(tokens) < 2:
            return text, ""

        location = tokens[-1]
        merchant = " ".join(tokens[:-1]).strip()
        return merchant, location
