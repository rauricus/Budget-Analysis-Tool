import re

from notification.base import NotificationParseResult, ServiceParser


class LastschriftParser(ServiceParser):
    # Debit Direct: AUFTRAG CH-DD-BASISLASTSCHRIFT ...
    DEBIT_DIRECT_PATTERN = re.compile(
        r"^AUFTRAG\s+CH-DD-BASISLASTSCHRIFT",
        re.IGNORECASE,
    )

    # Dauerauftrag: LASTSCHRIFT DAUERAUFTRAG: <ref> CH<iban> ...
    DAUERAUFTRAG_PATTERN = re.compile(
        r"^LASTSCHRIFT\s+DAUERAUFTRAG:\s+(\S+)\s+(CH\S+)(.*)$",
        re.IGNORECASE,
    )

    # Zahlung: LASTSCHRIFT CH<iban> <merchant>
    ZAHLUNG_PATTERN = re.compile(
        r"^LASTSCHRIFT\s+(CH\S+)\s+(.*)$",
        re.IGNORECASE,
    )

    def supports(self, text: str) -> bool:
        text_stripped = (text or "").strip()
        return bool(
            self.DEBIT_DIRECT_PATTERN.match(text_stripped)
            or self.DAUERAUFTRAG_PATTERN.match(text_stripped)
            or self.ZAHLUNG_PATTERN.match(text_stripped)
        )

    def parse(self, text: str) -> NotificationParseResult:
        text = (text or "").strip()

        if self.DEBIT_DIRECT_PATTERN.match(text):
            return self._parse_debit_direct(text)

        dauerauftrag_match = self.DAUERAUFTRAG_PATTERN.match(text)
        if dauerauftrag_match:
            return self._parse_dauerauftrag(text, dauerauftrag_match)

        zahlung_match = self.ZAHLUNG_PATTERN.match(text)
        if zahlung_match:
            return self._parse_zahlung(text, zahlung_match)

        return NotificationParseResult()

    def _parse_debit_direct(self, text: str) -> NotificationParseResult:
        recipient = ""
        recipient_iban = ""
        reference = ""

        id_nr_match = re.search(
            r"ID-NR\.\s+DES\s+ZAHLUNGSEMPFÄNGERS:\s+(\S+)",
            text,
            re.IGNORECASE,
        )
        if id_nr_match:
            recipient_iban = id_nr_match.group(1).strip()

        zahlungsempfaenger_match = re.search(
            r"ZAHLUNGSEMPFÄNGER:\s+([^M]+?)(?:MITTEILUNGEN:|$)",
            text,
            re.IGNORECASE,
        )
        if zahlungsempfaenger_match:
            recipient = zahlungsempfaenger_match.group(1).strip()

        mitteilungen_match = re.search(
            r"MITTEILUNGEN:\s+(.+?)(?:TRANSAKTIONS-ID:|$)",
            text,
            re.IGNORECASE,
        )
        if mitteilungen_match:
            reference = mitteilungen_match.group(1).strip()

        return NotificationParseResult(
            service_type="Lastschrift",
            transaction_type_detail="Lastschrift Debit Direct",
            recipient=recipient,
            recipient_iban=recipient_iban,
            reference=reference,
        )

    def _parse_dauerauftrag(
        self, text: str, match
    ) -> NotificationParseResult:
        reference = match.group(1).strip()
        recipient_iban = match.group(2).strip()
        rest = match.group(3).strip()

        recipient = rest if rest else ""

        return NotificationParseResult(
            service_type="Lastschrift",
            transaction_type_detail="Dauerauftrag",
            recipient=recipient,
            recipient_iban=recipient_iban,
            reference=reference,
        )

    def _parse_zahlung(self, text: str, match) -> NotificationParseResult:
        recipient_iban = match.group(1).strip()
        rest = match.group(2).strip()

        recipient = rest if rest else ""

        return NotificationParseResult(
            service_type="Lastschrift",
            transaction_type_detail="Zahlung",
            recipient=recipient,
            recipient_iban=recipient_iban,
        )
