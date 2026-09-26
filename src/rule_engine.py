import json
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Optional, Union
from models import Rule, Transaction


logger = logging.getLogger(__name__)

VALID_TRANSACTION_CATEGORIES = {"Income", "Expense", "Refund", "Transfer"}
MIN_RULE_PRIORITY = 1
MAX_RULE_PRIORITY = 10
MAIN_RULES_FILE = "rules.json"
RULE_PART_PATTERN = "rules.*.json"

PathsArg = Union[str, Path, list]


def discover_rule_files(dataset_dir: Path) -> list[Path]:
    """Return a dataset's rule files: `rules.json` first, then every `rules.*.json`.

    The parts are sorted by name only so that reruns load rules in the same order;
    which part a rule lives in carries no meaning.
    """
    main_file = Path(dataset_dir) / MAIN_RULES_FILE
    if not main_file.exists():
        raise FileNotFoundError(f"Rules file not found: {main_file}")
    return [main_file] + sorted(Path(dataset_dir).glob(RULE_PART_PATTERN))


def resolve_rule_files(run_dir: Path) -> tuple[Optional[str], list[Path], list[Path]]:
    """Resolve a run dataset's rule layers as (base name, base files, overlay files).

    The `"base"` field of the dataset's `rules.json` decides the layering: without it the
    dataset's own files form the only layer; with it, `data/<base>/` becomes the base layer
    (relative to the current working directory) and the dataset's files the overlay.
    """
    run_files = discover_rule_files(run_dir)
    with open(run_files[0], "r", encoding="utf-8") as f:
        base_name = json.load(f).get("base")
    if not base_name:
        return None, run_files, []
    return base_name, discover_rule_files(Path("data") / base_name), run_files


def _as_path_list(paths: Optional[PathsArg]) -> list[Path]:
    """Accept a single path or a list of paths and return a list of Paths."""
    if paths is None:
        return []
    if isinstance(paths, (str, Path)):
        return [Path(paths)]
    return [Path(p) for p in paths]


class RuleEngine:
    """Loads rules from JSON and matches them against transactions."""
    
    def __init__(
        self,
        rules_path: PathsArg = "data/reference/rules.json",
        overlay_path: Optional[PathsArg] = None,
        debug: bool = False,
    ):
        self.rules_paths = _as_path_list(rules_path)
        self.overlay_paths = _as_path_list(overlay_path)
        self.debug = debug
        self.rules: list[Rule] = []
        self.load_rules()
    
    @staticmethod
    def _parse_validity_date(value, field_name: str, rule_data: dict, source: str) -> Optional[date]:
        """Parse an optional ISO date (YYYY-MM-DD) from a rule's validity window."""
        if value in (None, ""):
            return None
        try:
            return datetime.strptime(str(value), "%Y-%m-%d").date()
        except ValueError:
            raise ValueError(
                f"Invalid '{field_name}' for rule "
                f"'{rule_data.get('key', '?')}' ('{rule_data.get('name', '')}') in {source}: "
                f"'{value}'. Expected ISO date YYYY-MM-DD"
            )

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

            valid_from = RuleEngine._parse_validity_date(
                scope.get("valid_from", rule_data.get("valid_from")), "valid_from", rule_data, source
            )
            valid_to = RuleEngine._parse_validity_date(
                scope.get("valid_to", rule_data.get("valid_to")), "valid_to", rule_data, source
            )
            if valid_from and valid_to and valid_from > valid_to:
                raise ValueError(
                    "Invalid validity window for rule "
                    f"'{rule_data.get('key', '?')}' ('{rule_data.get('name', '')}') in {source}: "
                    f"valid_from '{valid_from}' is after valid_to '{valid_to}'"
                )

            amounts = scope.get("amounts", rule_data.get("amounts")) or []
            if not isinstance(amounts, list) or not all(
                isinstance(a, (int, float)) and not isinstance(a, bool) and a > 0
                for a in amounts
            ):
                raise ValueError(
                    "Invalid 'amounts' for rule "
                    f"'{rule_data.get('key', '?')}' ('{rule_data.get('name', '')}') in {source}: "
                    f"{amounts!r}. Expected a list of positive numbers"
                )

            key = rule_data["key"]
            if key in result:
                raise ValueError(
                    f"Duplicate key '{key}' in {source}. Each rule key must be unique within a file."
                )

            rule = Rule(
                key=key,
                declared_key=key,
                name=rule_data["name"],
                overlay_of=rule_data.get("overlay_of") or None,
                
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
                valid_from=valid_from,
                valid_to=valid_to,
                amounts=[float(a) for a in amounts],
                
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

    def _load_layer(self, paths: list[Path], layer: str) -> dict[str, Rule]:
        """Parse several rule files into one layer; keys must be unique across all of them."""
        merged: dict[str, Rule] = {}
        for path in paths:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if path.name != MAIN_RULES_FILE and data.get("base"):
                raise ValueError(
                    f"'base' is only allowed in {MAIN_RULES_FILE}, not in {path.as_posix()}."
                )
            rules = self._parse_rules(data, source=path.as_posix())
            for key, rule in rules.items():
                if key in merged:
                    raise ValueError(
                        f"Duplicate key '{key}' in {path.as_posix()} and {merged[key].source}. "
                        "Each rule key must be unique across the rule files of a dataset."
                    )
                merged[key] = rule
            print(f"   Loaded {len(rules)} {layer} rules from {path}")
        return merged

    def load_rules(self):
        """Load base rules, then apply overlay rules (replacements plus additions)."""
        for path in self.rules_paths:
            if not path.exists():
                raise FileNotFoundError(f"Rules file not found: {path}")
        base_rules = self._load_layer(self.rules_paths, "base")

        # A missing overlay file is ignored, as a dataset without overlay rules is valid
        overlay_paths = [p for p in self.overlay_paths if p.exists()]
        if overlay_paths:
            overlay_rules = self._load_layer(overlay_paths, "overlay")

            replacing_overlay_rules: list[tuple[Rule, Rule]] = []
            for overlay_rule in overlay_rules.values():
                if overlay_rule.overlay_of is not None:
                    # Explicit overlay replacement: must target an existing base key
                    target_key = overlay_rule.overlay_of
                    if target_key not in base_rules:
                        raise ValueError(
                            f"Rule '{overlay_rule.key}' in {overlay_rule.source} declares "
                            f"overlay_of: '{target_key}', but no such key exists in base rules."
                        )
                    replacing_overlay_rules.append((base_rules[target_key], overlay_rule))
                else:
                    # New rule: must not collide with an existing base key
                    if overlay_rule.key in base_rules:
                        raise ValueError(
                            f"Rule '{overlay_rule.key}' in {overlay_rule.source} uses a key that already "
                            f"exists in base rules. Use 'overlay_of: \"{overlay_rule.key}\"' to replace it explicitly."
                        )

            # Apply overlay replacements: store the overlay rule under the target base key
            for base_rule, overlay_rule in replacing_overlay_rules:
                overlay_rule.key = overlay_rule.overlay_of  # adopt base key as effective identity
                base_rules[overlay_rule.overlay_of] = overlay_rule
            # Add new rules
            new_rules = {r.key: r for r in overlay_rules.values() if r.overlay_of is None}
            base_rules.update(new_rules)

            replaced = len(replacing_overlay_rules)
            added = len(new_rules)
            print(f"   Applied overlay ({len(overlay_paths)} file(s)): {replaced} replaced, {added} added")
            if self.debug:
                for previous_rule, new_rule in replacing_overlay_rules:
                    print(
                        "      Overlay replacement "
                        f"'{new_rule.overlay_of}': '{previous_rule.name}' from {previous_rule.source} "
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

        return transactions, matching_rules_map
