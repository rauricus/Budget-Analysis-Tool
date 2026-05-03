from dataclasses import dataclass, field
from typing import Optional

from models.transaction import Transaction


@dataclass
class Rule:
    """Categorization rule."""

    key: str
    declared_key: str
    name: str
    transaction_category: str  # One of: Income, Expense, Refund, Transfer
    category: str
    subcategory: str
    priority: int
    overlay_of: Optional[str] = None  # Key of the base rule this overlay rule replaces
    
    transaction_type: str = ""  # Optional filter: "Credit" or "Debit"
    transaction_type_detail: Optional[str] = None  # Optional filter: e.g. "Send Money" or "Purchase/Service"
    services: list[str] = field(default_factory=list)  # Optional filter, e.g. ["Card Purchase", "Twint"]
    providers: list[str] = field(default_factory=list)  # Optional filter, e.g. ["Apple Pay"]
    merchants: list[str] = field(default_factory=list)  # Optional filter, e.g. ["MIGROS", "COOP"]
    locations: list[str] = field(default_factory=list)  # Optional filter, e.g. ["AARAU", "ZURICH"]
    counterparties: list[str] = field(default_factory=list)  # Optional filter, e.g. ["DOCUTEAM"]
    counterparty_ibans: list[str] = field(default_factory=list)  # Optional filter, e.g. ["CH5600000000000000000"]
    include_keywords: list[str] = field(default_factory=list)  # Optional filter; all must be present
    exclude_keywords: list[str] = field(default_factory=list)  # Optional filter; none may be present
    
    source: str = ""  # originating rules file (set by RuleEngine)

    @staticmethod
    def _contains_any(needles: list[str], haystacks: list[str]) -> bool:
        """Case-insensitive substring match: at least one needle in one haystack."""
        return any(
            any(needle.upper() in haystack for haystack in haystacks if haystack)
            for needle in needles
        )

    def explain_match(self, transaction: Transaction) -> dict:
        """Return structured diagnostics for why this rule matches (or not)."""
        service = (transaction.service_type or "").upper()
        provider = (transaction.provider or "").upper()
        merchant_text = (transaction.parsed_merchant or "").upper()
        location_text = (transaction.parsed_location or "").upper()
        counterparty_text = (transaction.counterparty or "").upper()
        counterparty_iban_text = (transaction.counterparty_iban or "").replace(" ", "").upper()
        reference_text = (transaction.reference or "").upper()
        detail_text = (transaction.transaction_type_detail or "").upper()

        combined_text = " ".join(
            part
            for part in [
                merchant_text,
                location_text,
                counterparty_text,
                reference_text,
                detail_text,
                service,
                provider,
            ]
            if part
        )

        checks: list[dict] = []

        def add_check(check_id: str, passed: bool, detail: str) -> None:
            checks.append({"id": check_id, "passed": passed, "detail": detail})

        # 1. Match credit/debit direction (optional)
        tx_type_expected = (self.transaction_type or "").strip()
        tx_type_actual = (transaction.transaction_type or "").strip()
        tx_type_passed = (
            True
            if not tx_type_expected
            else tx_type_actual.lower() == tx_type_expected.lower()
        )
        add_check(
            "transaction_type",
            tx_type_passed,
            f"expected='{tx_type_expected or '*'}', actual='{tx_type_actual}'",
        )

        # 1a. Match transaction detail (optional)
        detail_filter = (self.transaction_type_detail or "").upper()
        detail_passed = True if not detail_filter else detail_text == detail_filter
        add_check(
            "transaction_type_detail",
            detail_passed,
            f"expected='{detail_filter or '*'}', actual='{detail_text}'",
        )

        # 1b. Match service type (optional)
        expected_services = [s.upper() for s in self.services]
        service_passed = True if not expected_services else service in expected_services
        add_check(
            "services",
            service_passed,
            f"expected={expected_services or ['*']}, actual='{service}'",
        )

        # 1c. Match provider (optional)
        expected_providers = [p.upper() for p in self.providers]
        provider_passed = True if not expected_providers else provider in expected_providers
        add_check(
            "providers",
            provider_passed,
            f"expected={expected_providers or ['*']}, actual='{provider}'",
        )

        # 2. At least one merchant must appear in parsed merchant/counterparty
        merchant_haystacks = [merchant_text, counterparty_text]
        merchant_passed = (
            True
            if not self.merchants
            else self._contains_any(self.merchants, merchant_haystacks)
        )
        add_check(
            "merchants",
            merchant_passed,
            f"expected_any={self.merchants or ['*']}, in_merchant='{merchant_text}', in_counterparty='{counterparty_text}'",
        )

        # 3. All locations must appear in parsed location (if defined)
        location_passed = (
            True
            if not self.locations
            else all(loc.upper() in location_text for loc in self.locations)
        )
        add_check(
            "locations",
            location_passed,
            f"expected_all={self.locations or ['*']}, actual='{location_text}'",
        )

        # 3a. At least one counterparty must appear in parsed counterparty
        counterparty_passed = (
            True
            if not self.counterparties
            else any(cp.upper() in counterparty_text for cp in self.counterparties)
        )
        add_check(
            "counterparties",
            counterparty_passed,
            f"expected_any={self.counterparties or ['*']}, actual='{counterparty_text}'",
        )

        # 3b. At least one counterparty IBAN must match exactly (ignoring spaces)
        expected_ibans = [iban.replace(" ", "").upper() for iban in self.counterparty_ibans]
        iban_passed = True if not expected_ibans else counterparty_iban_text in set(expected_ibans)
        add_check(
            "counterparty_ibans",
            iban_passed,
            f"expected_any={expected_ibans or ['*']}, actual='{counterparty_iban_text}'",
        )

        # 4. All include keywords must appear in parsed fields
        include_keywords_passed = (
            True
            if not self.include_keywords
            else all(kw.upper() in combined_text for kw in self.include_keywords)
        )
        add_check(
            "include_keywords",
            include_keywords_passed,
            f"expected_all={self.include_keywords or ['*']}, combined_text='{combined_text}'",
        )

        # 5. No exclude keyword may appear in parsed fields
        exclude_keywords_passed = (
            True
            if not self.exclude_keywords
            else not any(kw.upper() in combined_text for kw in self.exclude_keywords)
        )
        add_check(
            "exclude_keywords",
            exclude_keywords_passed,
            f"expected_none={self.exclude_keywords or ['*']}, combined_text='{combined_text}'",
        )

        failed_checks = [check for check in checks if not check["passed"]]
        return {
            "matched": len(failed_checks) == 0,
            "checks": checks,
            "failed_checks": failed_checks,
        }

    def matches(self, transaction: Transaction) -> bool:
        """
        Check whether this rule matches the transaction.
        ALL conditions must be satisfied (AND logic).
        """
        return bool(self.explain_match(transaction)["matched"])