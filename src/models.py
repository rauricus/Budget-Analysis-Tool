from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Transaction:
    """Einzelne Banktransaktion aus CSV"""
    datum: datetime
    bewegungstyp: str
    avisierungstext: str
    gutschrift: float
    lastschrift: float
    label: str
    kategorie: str  # Original-Kategorie aus CSV
    kategorie_auto: Optional[str] = None  # Automatisch zugewiesene Kategorie
    service_type: str = ""  # z.B. APPLE PAY, TWINT, LASTSCHRIFT
    card_number: str = ""  # z.B. XXXX1384 (Karte)
    parsed_merchant: str = ""
    parsed_location: str = ""
    recipient: str = ""  # Für LASTSCHRIFT: Zahlungsempfänger
    recipient_iban: str = ""  # Für LASTSCHRIFT: IBAN
    reference: str = ""  # Für LASTSCHRIFT: Referenz
    transaction_type_detail: str = ""  # Für LASTSCHRIFT: Detail-Typ
    
    @property
    def betrag(self) -> float:
        """Betrag (positiv für Einnahmen, negativ für Ausgaben)"""
        return self.gutschrift - self.lastschrift
    
    @property
    def is_income(self) -> bool:
        """Einnahme?"""
        return self.betrag > 0
    
    @property
    def text_upper(self) -> str:
        """Avisierungstext in UPPERCASE für Case-insensitive Matching"""
        return self.avisierungstext.upper()


@dataclass
class Rule:
    """Kategorisierungs-Regel"""
    id: int
    name: str
    category: str
    priority: int
    transaction_types: list[str]  # z.B. ["APPLE PAY KAUF/DIENSTLEISTUNG"]
    services: list[str]  # z.B. ["APPLE PAY"]
    merchants: list[str]  # z.B. ["MIGROS", "COOP"]
    locations: list[str]  # z.B. ["AARAU", "ZÜRICH"]
    include_keywords: list[str]  # z.B. ["TAKE AWAY"] – muss enthalten sein
    exclude_keywords: list[str]  # z.B. ["TAKE AWAY"] – darf NICHT enthalten sein
    
    def matches(self, transaction: Transaction) -> bool:
        """
        Prüft, ob diese Regel auf die Transaktion passt.
        ALLE Bedingungen müssen erfüllt sein (UND-Logik).
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
        
        # 1. Bewegungstyp matchen
        if transaction.bewegungstyp not in self.transaction_types:
            return False

        # 1b. Service-Typ matchen (optional)
        if self.services and service not in [s.upper() for s in self.services]:
            return False

        # 2. Mindestens ein Merchant muss im geparsten Merchant/Empfänger vorkommen
        merchant_haystacks = [merchant_text, recipient_text]
        if self.merchants and not any(
            any(m.upper() in haystack for haystack in merchant_haystacks if haystack)
            for m in self.merchants
        ):
            return False

        # 3. Alle Locations müssen im geparsten Ort vorkommen (wenn definiert)
        if self.locations and not all(loc.upper() in location_text for loc in self.locations):
            return False

        # 4. Alle include_keywords müssen in geparsten Feldern vorkommen
        if self.include_keywords and not all(kw.upper() in combined_text for kw in self.include_keywords):
            return False

        # 5. KEINE exclude_keywords dürfen in geparsten Feldern vorkommen
        if self.exclude_keywords and any(kw.upper() in combined_text for kw in self.exclude_keywords):
            return False

        return True
