from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class NotificationParseResult:
    service_type: str = ""
    card_number: str = ""
    merchant: str = ""
    location: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "service_type": self.service_type,
            "card_number": self.card_number,
            "merchant": self.merchant,
            "location": self.location,
        }


class ServiceParser(ABC):
    @abstractmethod
    def supports(self, text: str) -> bool:
        """Gibt True zurück, wenn dieser Parser das Format unterstützt."""

    @abstractmethod
    def parse(self, text: str) -> NotificationParseResult:
        """Parsed Service-spezifische Daten aus dem Avisierungstext."""
