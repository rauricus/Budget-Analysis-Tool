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
    id: str
    name: str
    category: str
    priority: int
    transaction_types: list[str]  # z.B. ["APPLE PAY KAUF/DIENSTLEISTUNG"]
    merchants: list[str]  # z.B. ["MIGROS", "COOP"]
    locations: list[str]  # z.B. ["AARAU", "ZÜRICH"]
    include_keywords: list[str]  # z.B. ["TAKE AWAY"] – muss enthalten sein
    exclude_keywords: list[str]  # z.B. ["TAKE AWAY"] – darf NICHT enthalten sein
    
    def matches(self, transaction: Transaction) -> bool:
        """
        Prüft, ob diese Regel auf die Transaktion passt.
        ALLE Bedingungen müssen erfüllt sein (UND-Logik).
        """
        text = transaction.text_upper
        
        # 1. Bewegungstyp matchen
        if transaction.bewegungstyp not in self.transaction_types:
            return False
        
        # 2. Mindestens ein Merchant muss vorhanden sein
        if self.merchants and not any(m.upper() in text for m in self.merchants):
            return False
        
        # 3. Alle Locations müssen vorhanden sein (wenn definiert)
        if self.locations and not all(loc.upper() in text for loc in self.locations):
            return False
        
        # 4. Alle include_keywords müssen vorhanden sein
        if self.include_keywords and not all(kw.upper() in text for kw in self.include_keywords):
            return False
        
        # 5. KEINE exclude_keywords dürfen vorhanden sein
        if self.exclude_keywords and any(kw.upper() in text for kw in self.exclude_keywords):
            return False
        
        return True
