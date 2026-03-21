from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Transaction:
    """Single bank transaction parsed from CSV."""

    datum: datetime
    bewegungstyp: str
    avisierungstext: str
    gutschrift: float
    lastschrift: float
    label: str
    kategorie: str  # Original category from CSV
    kategorie_auto: Optional[str] = None  # Automatically assigned category
    service_type: str = ""  # e.g. Apple Pay, Twint, Lastschrift
    card_number: str = ""  # e.g. XXXX1384 (card)
    parsed_merchant: str = ""
    parsed_location: str = ""
    recipient: str = ""  # For Lastschrift: payment recipient
    recipient_iban: str = ""  # For Lastschrift: IBAN
    reference: str = ""  # For Lastschrift: reference
    transaction_type_detail: str = ""  # For Lastschrift: detail type

    @property
    def betrag(self) -> float:
        """Amount (positive for income, negative for expenses)."""
        return self.gutschrift - self.lastschrift

    @property
    def is_income(self) -> bool:
        """Is income?"""
        return self.betrag > 0

    @property
    def text_upper(self) -> str:
        """Notification text in uppercase for case-insensitive matching."""
        return self.avisierungstext.upper()