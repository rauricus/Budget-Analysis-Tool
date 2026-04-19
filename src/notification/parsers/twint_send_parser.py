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

    def parse(self, text: str) -> NotificationParseResult:
        t = (text or "").strip()

        match = self.TWINT_PATTERN.match(t)
        if match:
            recipient_phone = match.group(2)
            rest = match.group(3).strip()
            merchant = recipient_phone
            if rest:
                merchant = f"{recipient_phone} {rest}".strip()
            return NotificationParseResult(
                service_type="Twint",
                provider="Twint",
                transaction_type_detail="Send Money",
                merchant=merchant,
            )

        match = self.TWINT_DIRECT_PATTERN.match(t)
        if match:
            recipient_phone = match.group(1)
            rest = match.group(2).strip()
            # Strip optional leading comma (format: ", NAME MITTEILUNGEN: ...")
            if rest.startswith(","):
                rest = rest[1:].strip()
            # Split off MITTEILUNGEN section
            mitteilungen_idx = rest.upper().find("MITTEILUNGEN:")
            if mitteilungen_idx >= 0:
                name = rest[:mitteilungen_idx].strip()
                message = rest[mitteilungen_idx + len("MITTEILUNGEN:"):].strip()
                merchant_parts = [p for p in [recipient_phone, name, f"MITTEILUNGEN: {message}"] if p]
            else:
                merchant_parts = [p for p in [recipient_phone, rest] if p]
            return NotificationParseResult(
                service_type="Twint",
                provider="Twint",
                transaction_type_detail="Send Money",
                merchant=" ".join(merchant_parts),
            )

        return NotificationParseResult()
