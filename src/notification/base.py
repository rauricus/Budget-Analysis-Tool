from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class NotificationParseResult:
    service_type: str = ""
    provider: str = ""  # Specific payment provider, e.g. "Apple Pay" for card purchases
    card_number: str = ""
    merchant: str = ""
    location: str = ""
    counterparty: str = ""  # Neutral counterparty name across debit/credit transactions
    counterparty_iban: str = ""  # Neutral counterparty IBAN across debit/credit transactions
    reference: str = ""  # For direct debit (Lastschrift): reference information
    transaction_type_detail: str = ""  # For direct debit (Lastschrift): Debit Direct / payment (Zahlung) / standing order (Dauerauftrag)

    def to_dict(self) -> dict[str, str]:
        return {
            "service_type": self.service_type,
            "provider": self.provider,
            "card_number": self.card_number,
            "merchant": self.merchant,
            "location": self.location,
            "counterparty": self.counterparty,
            "counterparty_iban": self.counterparty_iban,
            "reference": self.reference,
            "transaction_type_detail": self.transaction_type_detail,
        }


class AbstractServiceParser(ABC):
    @abstractmethod
    def supports(self, text: str) -> bool:
        """Return True if this parser supports the format."""

    @abstractmethod
    def parse(self, text: str) -> NotificationParseResult:
        """Parse service-specific data from the notification text."""
