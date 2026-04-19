import json
import logging
from pathlib import Path
from typing import Optional
from models import Rule, Transaction


logger = logging.getLogger(__name__)


class RuleEngine:
    """Loads rules from JSON and matches them against transactions."""
    
    def __init__(
        self,
        rules_path: str = "data/reference/rules.json",
        overlay_path: Optional[str] = None,
        debug: bool = False,
    ):
        self.rules_path = Path(rules_path)
        self.overlay_path = Path(overlay_path) if overlay_path else None
        self.debug = debug
        self.rules: list[Rule] = []
        self.load_rules()
    
    @staticmethod
    def _parse_rules(data: dict, source: str = "") -> dict[int, Rule]:
        """Parse a rules JSON dict into a {id: Rule} mapping."""
        result = {}
        for rule_data in data.get("rules", []):
            rule = Rule(
                id=rule_data["id"],
                name=rule_data["name"],
                category=rule_data["category"],
                subcategory=rule_data.get("subcategory", ""),
                priority=rule_data["priority"],
                transaction_type=rule_data.get("transaction_type", ""),
                services=rule_data.get("services", []),
                providers=rule_data.get("providers", []),
                merchants=rule_data["triggers"].get("merchants", []),
                locations=rule_data["triggers"].get("locations", []),
                include_keywords=rule_data["triggers"].get("include_keywords", []),
                exclude_keywords=rule_data["triggers"].get("exclude_keywords", []),
                source=source,
            )
            result[rule.id] = rule
        return result

    @staticmethod
    def _transaction_debug_label(transaction: Transaction) -> str:
        """Build a short, readable transaction label for debug output."""
        counterparty = (
            transaction.parsed_merchant
            or transaction.counterparty
            or transaction.notification_text[:60]
        )
        return (
            f"{transaction.date.strftime('%Y-%m-%d')} | "
            f"{transaction.service_type or transaction.transaction_type} | "
            f"{counterparty}"
        )

    def load_rules(self):
        """Load base rules, then apply overlay rules (same ID overrides, new ID appends)."""
        if not self.rules_path.exists():
            raise FileNotFoundError(f"Rules file not found: {self.rules_path}")
        
        with open(self.rules_path, "r", encoding="utf-8") as f:
            base_rules = self._parse_rules(json.load(f), source=self.rules_path.as_posix())
        print(f"   Loaded {len(base_rules)} base rules from {self.rules_path}")

        if self.overlay_path and self.overlay_path.exists():
            with open(self.overlay_path, "r", encoding="utf-8") as f:
                overlay_rules = self._parse_rules(json.load(f), source=self.overlay_path.as_posix())
            overridden_rules = [
                (base_rules[rule_id], overlay_rules[rule_id])
                for rule_id in overlay_rules
                if rule_id in base_rules
            ]
            overridden = len(overridden_rules)
            added = len(overlay_rules) - overridden
            base_rules.update(overlay_rules)
            print(f"   Applied overlay {self.overlay_path}: {overridden} overridden, {added} added")
            if self.debug:
                for previous_rule, new_rule in overridden_rules:
                    print(
                        "      Override "
                        f"#{new_rule.id}: '{previous_rule.name}' from {previous_rule.source} "
                        f"-> '{new_rule.name}' from {new_rule.source}"
                    )

        self.rules = sorted(base_rules.values(), key=lambda r: r.priority, reverse=True)
        print(f"   {len(self.rules)} rules active (sorted by priority)")

    @staticmethod
    def _service_provider_candidates(rules: list[Rule], transaction: Transaction) -> list[Rule]:
        """Filter rules by service and optional provider against the parsed transaction."""
        service_upper = (transaction.service_type or "").upper()
        provider_upper = (transaction.provider or "").upper()
        if not service_upper:
            return []

        candidates: list[Rule] = []
        for rule in rules:
            if rule.services and service_upper not in [service.upper() for service in rule.services]:
                continue
            if rule.providers and provider_upper not in [provider.upper() for provider in rule.providers]:
                continue
            candidates.append(rule)

        return candidates

    def categorize(self, transaction: Transaction) -> Optional[str]:
        """
        Find the best rule for a transaction.
        Return the category (or None if no match exists).
        """
        candidate_rules = self._service_provider_candidates(self.rules, transaction)
        if not candidate_rules:
            if not transaction.service_type:
                logger.info("No categorization without service match: %s", transaction.notification_text)
            return None

        for rule in candidate_rules:
            if rule.matches(transaction):
                return rule.category

        return None
    
    def categorize_batch(self, transactions: list[Transaction]) -> tuple[list[Transaction], dict]:
        """
        Categorize a list of transactions.
        Modifies each transaction in place (`auto_category`).

        Returns:
            (categorized_transactions, matching_rules_map)
            matching_rules_map: {transaction_index: [matching_rules]}
        """
        matching_rules_map = {}
        for idx, txn in enumerate(transactions):
            candidate_rules = self._service_provider_candidates(self.rules, txn)

            # Find all matching rules (already in priority order)
            matching = [r for r in candidate_rules if r.matches(txn)]
            matching_rules_map[idx] = matching

            # Categorize
            best_match = matching[0] if matching else None
            txn.auto_category = best_match.category if best_match else None
            txn.auto_subcategory = best_match.subcategory if best_match else None

            if best_match and self.debug:
                category_label = (
                    f"{best_match.category} / {best_match.subcategory}"
                    if best_match.subcategory
                    else best_match.category
                )
                print(
                    "      Rule matched: "
                    f"#{best_match.id} '{best_match.name}' from {best_match.source} "
                    f"-> {category_label} | "
                    f"{self._transaction_debug_label(txn)}"
                )

        return transactions, matching_rules_map
