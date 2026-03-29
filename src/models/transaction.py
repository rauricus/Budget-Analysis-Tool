from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Transaction:
    """Single bank transaction parsed from CSV."""

    date: datetime
    transaction_type: str
    notification_text: str
    credit: float
    debit: float
    label: str
    category: str  # Original category from CSV
    auto_category: Optional[str] = None  # Automatically assigned category
    service_type: str = ""  # e.g. Karteneinkauf, Twint, Lastschrift
    provider: str = ""  # Specific payment provider, e.g. "Apple Pay" for card purchases
    card_number: str = ""  # e.g. XXXX1384 (card)
    parsed_merchant: str = ""
    parsed_location: str = ""
    recipient: str = ""  # For direct debit (Lastschrift): payment recipient
    recipient_iban: str = ""  # For direct debit (Lastschrift): IBAN
    reference: str = ""  # For direct debit (Lastschrift): reference
    transaction_type_detail: str = ""  # For direct debit (Lastschrift): detail type

    @property
    def amount(self) -> float:
        """Amount (positive for income, negative for expenses)."""
        return self.credit - self.debit

    @property
    def is_income(self) -> bool:
        """Is income?"""
        return self.amount > 0

    @property
    def notification_text_upper(self) -> str:
        """Notification text in uppercase for case-insensitive matching."""
        return self.notification_text.upper()