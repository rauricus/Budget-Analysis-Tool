import json
import logging
from pathlib import Path
from typing import Optional
from models import Rule, Transaction


logger = logging.getLogger(__name__)

VALID_TRANSACTION_CATEGORIES = {"Income", "Expense", "Refund", "Transfer"}
MIN_RULE_PRIORITY = 1
MAX_RULE_PRIORITY = 10


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
    def _parse_rules(data: dict, source: str = "") -> dict[str, Rule]:
        """Parse a rules JSON dict into a {key: Rule} mapping."""
        result = {}
        for rule_data in data.get("rules", []):
            scope = rule_data.get("scope") or {}
            filters = (
                scope.get("notification_filters")
                or rule_data.get("notification_filters")
                or rule_data.get("triggers")
                or {}
            )
            transaction_category = str(
                scope.get("transaction_category", rule_data.get("transaction_category", ""))
            ).strip()
            # Normalize to Title case for comparison
            transaction_category_normalized = transaction_category[0].upper() + transaction_category[1:].lower() if transaction_category else ""
            if transaction_category_normalized not in VALID_TRANSACTION_CATEGORIES:
                raise ValueError(
                    "Invalid or missing 'transaction_category' for rule "
                    f"'{rule_data.get('key', '?')}' ('{rule_data.get('name', '')}') in {source}: "
                    f"'{transaction_category_normalized}'. Allowed: {sorted(VALID_TRANSACTION_CATEGORIES)}"
                )

            priority = rule_data.get("priority")
            if not isinstance(priority, int) or not (MIN_RULE_PRIORITY <= priority <= MAX_RULE_PRIORITY):
                raise ValueError(
                    "Invalid or missing 'priority' for rule "
                    f"'{rule_data.get('key', '?')}' ('{rule_data.get('name', '')}') in {source}: "
                    f"'{priority}'. Allowed: integer {MIN_RULE_PRIORITY}-{MAX_RULE_PRIORITY}"
                )

            key = rule_data["key"]
            if key in result:
                raise ValueError(
                    f"Duplicate key '{key}' in {source}. Each rule key must be unique within a file."
                )

            rule = Rule(
                key=key,
                name=rule_data["name"],
                override=rule_data.get("override") or None,
                
                transaction_category=transaction_category_normalized,
                category=rule_data.get("category", ""),
                subcategory=rule_data.get("subcategory", ""),
                priority=priority,
                
                transaction_type=scope.get("transaction_type", rule_data.get("transaction_type", "")),
                transaction_type_detail=(
                    scope.get("transaction_type_detail", rule_data.get("transaction_type_detail"))
                    or None
                ),
                services=scope.get("services", rule_data.get("services", [])),
                providers=scope.get("providers", rule_data.get("providers", [])),
                merchants=filters.get("merchants", []),
                locations=filters.get("locations", []),
                counterparties=filters.get("counterparties", []),
                counterparty_ibans=filters.get("counterparty_ibans", []),
                include_keywords=filters.get("include_keywords", []),
                exclude_keywords=filters.get("exclude_keywords", []),
                
                source=source,
            )
            result[rule.key] = rule
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
        """Load base rules, then apply overlay rules (same key overrides, new key appends)."""
        if not self.rules_path.exists():
            raise FileNotFoundError(f"Rules file not found: {self.rules_path}")
        
        with open(self.rules_path, "r", encoding="utf-8") as f:
            base_rules = self._parse_rules(json.load(f), source=self.rules_path.as_posix())
        print(f"   Loaded {len(base_rules)} base rules from {self.rules_path}")

        if self.overlay_path and self.overlay_path.exists():
            with open(self.overlay_path, "r", encoding="utf-8") as f:
                overlay_rules = self._parse_rules(json.load(f), source=self.overlay_path.as_posix())

            overridden_rules: list[tuple[Rule, Rule]] = []
            for overlay_rule in overlay_rules.values():
                if overlay_rule.override is not None:
                    # Explicit override: must target an existing base key
                    target_key = overlay_rule.override
                    if target_key not in base_rules:
                        raise ValueError(
                            f"Rule '{overlay_rule.key}' in {self.overlay_path} declares "
                            f"override: '{target_key}', but no such key exists in base rules."
                        )
                    overridden_rules.append((base_rules[target_key], overlay_rule))
                else:
                    # New rule: must not collide with an existing base key
                    if overlay_rule.key in base_rules:
                        raise ValueError(
                            f"Rule '{overlay_rule.key}' in {self.overlay_path} uses a key that already "
                            f"exists in base rules. Use 'override: \"{overlay_rule.key}\"' to replace it explicitly."
                        )

            # Apply overrides: store the overlay rule under the target (base) key
            for base_rule, overlay_rule in overridden_rules:
                overlay_rule.key = overlay_rule.override  # adopt base key as effective identity
                base_rules[overlay_rule.override] = overlay_rule
            # Add new rules
            new_rules = {r.key: r for r in overlay_rules.values() if r.override is None}
            base_rules.update(new_rules)

            overridden = len(overridden_rules)
            added = len(new_rules)
            print(f"   Applied overlay {self.overlay_path}: {overridden} overridden, {added} added")
            if self.debug:
                for previous_rule, new_rule in overridden_rules:
                    print(
                        "      Override "
                        f"'{new_rule.override}': '{previous_rule.name}' from {previous_rule.source} "
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
                return rule.category or None

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
            txn.auto_transaction_category = best_match.transaction_category if best_match else None
            txn.auto_category = (best_match.category or None) if best_match else None
            txn.auto_subcategory = (best_match.subcategory or None) if best_match else None

            if best_match and self.debug:
                category_label = (
                    f"{best_match.category} / {best_match.subcategory}"
                    if best_match.subcategory
                    else best_match.category
                )
                row_label = (
                    f"Row {txn.source_line_number}: "
                    if txn.source_line_number is not None
                    else ""
                )
                print(
                    f"      {row_label}Rule matched: "
                    f"'{best_match.key}' '{best_match.name}' from {best_match.source} "
                    f"-> {category_label} | "
                    f"{self._transaction_debug_label(txn)}"
                )
            elif self.debug:
                row_label = (
                    f"Row {txn.source_line_number}"
                    if txn.source_line_number is not None
                    else "Row ?"
                )
                row_text = txn.source_row_text or self._transaction_debug_label(txn)
                print(f"      {row_label}: No matching rule | {row_text}")

        return transactions, matching_rules_map
