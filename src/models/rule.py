from dataclasses import dataclass, field
from typing import Optional

from models.transaction import Transaction


@dataclass
class Rule:
    """Categorization rule."""

    key: str
    name: str
    transaction_category: str  # One of: Income, Expense, Refund, Transfer
    category: str
    subcategory: str
    priority: int
    transaction_type: str = ""  # Optional filter: "Credit" or "Debit"
    transaction_type_detail: Optional[str] = None  # Optional filter: e.g. "Send Money" or "Purchase/Service"
    services: list[str] = field(default_factory=list)  # Optional filter, e.g. ["Card Purchase", "Twint"]
    merchants: list[str] = field(default_factory=list)  # Optional filter, e.g. ["MIGROS", "COOP"]
    locations: list[str] = field(default_factory=list)  # Optional filter, e.g. ["AARAU", "ZURICH"]
    include_keywords: list[str] = field(default_factory=list)  # Optional filter; all must be present
    exclude_keywords: list[str] = field(default_factory=list)  # Optional filter; none may be present
    providers: list[str] = field(default_factory=list)  # Optional filter, e.g. ["Apple Pay"]
    source: str = ""  # originating rules file (set by RuleEngine)

    def matches(self, transaction: Transaction) -> bool:
        """
        Check whether this rule matches the transaction.
        ALL conditions must be satisfied (AND logic).
        """
        service = (transaction.service_type or "").upper()
        provider = (transaction.provider or "").upper()
        merchant_text = (transaction.parsed_merchant or "").upper()
        location_text = (transaction.parsed_location or "").upper()
        counterparty_text = (transaction.counterparty or "").upper()
        reference_text = (transaction.reference or "").upper()
        detail_text = (transaction.transaction_type_detail or "").upper()

        combined_text = " ".join(
            part
            for part in [merchant_text, location_text, counterparty_text, reference_text, detail_text, service, provider]
            if part
        )

        # 1. Match credit/debit direction (optional)
        if self.transaction_type and transaction.transaction_type.lower() != self.transaction_type.lower():
            return False

        # 1a. Match transaction detail (optional)
        detail_filter = (self.transaction_type_detail or "").upper()
        if detail_filter and detail_text != detail_filter:
            return False

        # 1b. Match service type (optional)
        if self.services and service not in [s.upper() for s in self.services]:
            return False

        # 1c. Match provider (optional)
        if self.providers and provider not in [p.upper() for p in self.providers]:
            return False

        # 2. At least one merchant must appear in parsed merchant/counterparty
        merchant_haystacks = [merchant_text, counterparty_text]
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