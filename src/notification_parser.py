import re


class NotificationTextParser:
    """Parser für Avisierungstext (servicebasiert)."""

    APPLE_PAY_PATTERN = re.compile(
        r"^(?P<prefix>APPLE PAY KAUF/DIENSTLEISTUNG)\s+VOM\s+\d{2}\.\d{2}\.\d{4}\s+KARTEN NR\.\s+(?P<card>XXXX\d{4})\s+(?P<rest>.+)$",
        re.IGNORECASE,
    )

    @staticmethod
    def parse(avisierungstext: str) -> dict[str, str]:
        """
        Parsed Felder aus Avisierungstext.

        Returns:
            {
                "service_type": str,
                "card_number": str,
                "merchant": str,
                "location": str,
            }
        """
        parsed = {
            "service_type": "",
            "card_number": "",
            "merchant": "",
            "location": "",
        }

        text = (avisierungstext or "").strip()
        if not text:
            return parsed

        match = NotificationTextParser.APPLE_PAY_PATTERN.match(text)
        if match:
            parsed["service_type"] = "APPLE PAY"
            parsed["card_number"] = match.group("card").strip()

            rest = match.group("rest").strip()
            merchant, location = NotificationTextParser._extract_merchant_location(rest)
            parsed["merchant"] = merchant
            parsed["location"] = location

        return parsed

    @staticmethod
    def _extract_merchant_location(text: str) -> tuple[str, str]:
        """
        Extrahiert Merchant und Ort aus dem service-spezifischen Resttext.

        Beispiele:
        - "RUEDI RÜSSEL TANKSTELLE AARAU WAREN 10.34"
        - "MIGROS IGELWEID (4213) AARAU SCHWEIZ"
        """
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
