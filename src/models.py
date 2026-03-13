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


@dataclass
class Rule:
    """Categorization rule."""
    id: int
    name: str
    category: str
    priority: int
    transaction_types: list[str]  # e.g. ["APPLE PAY KAUF/DIENSTLEISTUNG"]
    services: list[str]  # e.g. ["Apple Pay"]
    merchants: list[str]  # e.g. ["MIGROS", "COOP"]
    locations: list[str]  # e.g. ["AARAU", "ZÜRICH"]
    include_keywords: list[str]  # e.g. ["TAKE AWAY"] - must be present
    exclude_keywords: list[str]  # e.g. ["TAKE AWAY"] - must NOT be present
    
    def matches(self, transaction: Transaction) -> bool:
        """
        Check whether this rule matches the transaction.
        ALL conditions must be satisfied (AND logic).
        """
        service = (transaction.service_type or "").upper()
        merchant_text = (transaction.parsed_merchant or "").upper()
        location_text = (transaction.parsed_location or "").upper()
        recipient_text = (transaction.recipient or "").upper()
        reference_text = (transaction.reference or "").upper()
        detail_text = (transaction.transaction_type_detail or "").upper()

        combined_text = " ".join(
            part
            for part in [merchant_text, location_text, recipient_text, reference_text, detail_text, service]
            if part
        )
        
        # 1. Match transaction type
        if transaction.bewegungstyp not in self.transaction_types:
            return False

        # 1b. Match service type (optional)
        if self.services and service not in [s.upper() for s in self.services]:
            return False

        # 2. At least one merchant must appear in parsed merchant/recipient
        merchant_haystacks = [merchant_text, recipient_text]
        if self.merchants and not any(
            any(m.upper() in haystack for haystack in merchant_haystacks if haystack)
            for m in self.merchants
        ):
            return False

        # 3. All locations must appear in parsed location (if defined)
        if self.locations and not all(loc.upper() in location_text for loc in self.locations):
            return False

        # 4. All include keywords must appear in parsed fields
        if self.include_keywords and not all(kw.upper() in combined_text for kw in self.include_keywords):
            return False

        # 5. No exclude keyword may appear in parsed fields
        if self.exclude_keywords and any(kw.upper() in combined_text for kw in self.exclude_keywords):
            return False

        return True
