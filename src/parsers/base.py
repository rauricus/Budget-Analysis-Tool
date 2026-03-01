from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class NotificationParseResult:
    service_type: str = ""
    card_number: str = ""
    merchant: str = ""
    location: str = ""
    recipient: str = ""  # Für LASTSCHRIFT: Zahlungsempfänger
    recipient_iban: str = ""  # Für LASTSCHRIFT: IBAN des Empfängers
    reference: str = ""  # Für LASTSCHRIFT: Referenz-Information
    transaction_type_detail: str = ""  # Für LASTSCHRIFT: Debit Direct / Zahlung / Dauerauftrag

    def to_dict(self) -> dict[str, str]:
        return {
            "service_type": self.service_type,
            "card_number": self.card_number,
            "merchant": self.merchant,
            "location": self.location,
            "recipient": self.recipient,
            "recipient_iban": self.recipient_iban,
            "reference": self.reference,
            "transaction_type_detail": self.transaction_type_detail,
        }


class ServiceParser(ABC):
    @abstractmethod
    def supports(self, text: str) -> bool:
        """Gibt True zurück, wenn dieser Parser das Format unterstützt."""

    @abstractmethod
    def parse(self, text: str) -> NotificationParseResult:
        """Parsed Service-spezifische Daten aus dem Avisierungstext."""
