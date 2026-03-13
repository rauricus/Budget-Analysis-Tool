import json
import logging
from pathlib import Path
from typing import Optional
from models import Rule, Transaction


logger = logging.getLogger(__name__)


class RuleEngine:
    """Loads rules from JSON and matches them against transactions."""
    
    def __init__(self, rules_path: str = "data/rules.json"):
        self.rules_path = Path(rules_path)
        self.rules: list[Rule] = []
        self.load_rules()
    
    def load_rules(self):
        """Load rules from JSON."""
        if not self.rules_path.exists():
            raise FileNotFoundError(f"Rules file not found: {self.rules_path}")
        
        with open(self.rules_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Parse rules
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
            )
            self.rules.append(rule)
        
        # Sort by priority (descending)
        self.rules.sort(key=lambda r: r.priority, reverse=True)
        print(f"   Loaded {len(self.rules)} rules (sorted by priority)")

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
                logger.info("No categorization without service match: %s", transaction.avisierungstext)
            return None

        for rule in candidate_rules:
            if rule.matches(transaction):
                return rule.category

        return None
    
    def categorize_batch(self, transactions: list[Transaction]) -> tuple[list[Transaction], dict]:
        """
        Categorize a list of transactions.
        Modifies each transaction in place (`kategorie_auto`).

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
            txn.kategorie_auto = self.categorize(txn)

        return transactions, matching_rules_map
