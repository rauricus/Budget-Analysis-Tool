import json
import logging
from pathlib import Path
from typing import Optional
from models import Rule, Transaction


logger = logging.getLogger(__name__)


class RuleEngine:
    """Loads rules from JSON and matches them against transactions."""
    
    def __init__(self, rules_path: str = "data/reference/rules.json", overlay_path: Optional[str] = None):
        self.rules_path = Path(rules_path)
        self.overlay_path = Path(overlay_path) if overlay_path else None
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
                priority=rule_data["priority"],
                transaction_types=rule_data.get("transaction_types", []),
                services=rule_data.get("services", []),
                merchants=rule_data["triggers"].get("merchants", []),
                locations=rule_data["triggers"].get("locations", []),
                include_keywords=rule_data["triggers"].get("include_keywords", []),
                exclude_keywords=rule_data["triggers"].get("exclude_keywords", []),
                source=source,
            )
            result[rule.id] = rule
        return result

    def load_rules(self):
        """Load base rules, then apply overlay rules (same ID overrides, new ID appends)."""
        if not self.rules_path.exists():
            raise FileNotFoundError(f"Rules file not found: {self.rules_path}")
        
        with open(self.rules_path, "r", encoding="utf-8") as f:
            base_rules = self._parse_rules(json.load(f), source=self.rules_path.name)
        print(f"   Loaded {len(base_rules)} base rules from {self.rules_path}")

        if self.overlay_path and self.overlay_path.exists():
            with open(self.overlay_path, "r", encoding="utf-8") as f:
                overlay_rules = self._parse_rules(json.load(f), source=self.overlay_path.name)
            overridden = len([k for k in overlay_rules if k in base_rules])
            added = len(overlay_rules) - overridden
            base_rules.update(overlay_rules)
            print(f"   Applied overlay {self.overlay_path}: {overridden} overridden, {added} added")

        self.rules = sorted(base_rules.values(), key=lambda r: r.priority, reverse=True)
        print(f"   {len(self.rules)} rules active (sorted by priority)")

    @staticmethod
    def _service_candidates(rules: list[Rule], service_type: str) -> list[Rule]:
        service_upper = (service_type or "").upper()
        if not service_upper:
            return []
        return [
            rule
            for rule in rules
            if rule.services and service_upper in [service.upper() for service in rule.services]
        ]

    def categorize(self, transaction: Transaction) -> Optional[str]:
        """
        Find the best rule for a transaction.
        Return the category (or None if no match exists).
        """
        candidate_rules = self._service_candidates(self.rules, transaction.service_type)
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
            candidate_rules = self._service_candidates(self.rules, txn.service_type)

            # Find all matching rules (already in priority order)
            matching = [r for r in candidate_rules if r.matches(txn)]
            matching_rules_map[idx] = matching

            # Categorize
            txn.auto_category = self.categorize(txn)

        return transactions, matching_rules_map
