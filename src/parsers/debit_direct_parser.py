import re

from parsers.base import NotificationParseResult, ServiceParser


class DebitDirectParser(ServiceParser):
    """Parser for CH-DD-BASISLASTSCHRIFT transactions."""

    PATTERN = re.compile(
        r"^AUFTRAG\s+CH-DD-BASISLASTSCHRIFT",
        re.IGNORECASE,
    )

    def supports(self, text: str) -> bool:
        return bool(self.PATTERN.match((text or "").strip()))

    def parse(self, text: str) -> NotificationParseResult:
        text = (text or "").strip()
        if not self.supports(text):
            return NotificationParseResult()

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
