"""
Transaction Overrides
Loads a transaction_overrides.json file and applies per-ID overrides
(hidden flag or category override) to already-categorized transactions.

Override entries are keyed by transaction_id (e.g. "TX-000042") and may
contain any combination of:
  {
    "hidden": true,                        // exclude from output
    "transaction_category": "Expense",     // override auto_transaction_category
    "category": "Sonstiges",              // override auto_category
    "subcategory": "Diverses"             // override auto_subcategory
  }
"""

import json
import logging
from pathlib import Path
from typing import Optional

from models import Transaction

logger = logging.getLogger(__name__)

VALID_TRANSACTION_CATEGORIES = {"Income", "Expense", "Refund", "Transfer"}
ALLOWED_OVERRIDE_FIELDS = {"hidden", "transaction_category", "category", "subcategory", "_row"}


class TransactionOverrides:
    """Loads and applies transaction-level overrides from a JSON file."""

    def __init__(self, overrides_path: str):
        self.overrides_path = Path(overrides_path)
        self.overrides: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        with open(self.overrides_path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        if not isinstance(raw, dict):
            raise ValueError(
                f"transaction_overrides.json must be a JSON object, got {type(raw).__name__}: "
                f"{self.overrides_path}"
            )

        for tx_id, entry in raw.items():
            if not isinstance(tx_id, str) or not tx_id.startswith("TX-"):
                raise ValueError(
                    f"Invalid transaction ID key '{tx_id}' in {self.overrides_path}. "
                    "Keys must be transaction IDs starting with 'TX-'."
                )
            if not isinstance(entry, dict):
                raise ValueError(
                    f"Override entry for '{tx_id}' must be an object, got "
                    f"{type(entry).__name__}: {self.overrides_path}"
                )
            unknown_fields = set(entry.keys()) - ALLOWED_OVERRIDE_FIELDS
            if unknown_fields:
                raise ValueError(
                    f"Unknown field(s) {sorted(unknown_fields)} in override entry for '{tx_id}' "
                    f"in {self.overrides_path}. "
                    f"Allowed: {sorted(ALLOWED_OVERRIDE_FIELDS)}"
                )
            tc = entry.get("transaction_category")
            if tc is not None and tc not in VALID_TRANSACTION_CATEGORIES:
                raise ValueError(
                    f"Invalid 'transaction_category' '{tc}' in override entry for '{tx_id}' "
                    f"in {self.overrides_path}. "
                    f"Allowed: {sorted(VALID_TRANSACTION_CATEGORIES)}"
                )
            row_hint = entry.get("_row")
            if row_hint is not None and not isinstance(row_hint, str):
                raise ValueError(
                    f"'_row' in override entry for '{tx_id}' must be a string "
                    f"in {self.overrides_path}."
                )

        self.overrides = raw

    def apply(self, transactions: list[Transaction]) -> list[Transaction]:
        """Apply overrides to *transactions* in-place and return the filtered list.

        Hidden transactions are removed from the returned list.
        Unknown transaction IDs in the overrides file produce a warning.
        """
        known_ids = {t.transaction_id for t in transactions}
        for tx_id in self.overrides:
            if tx_id not in known_ids:
                logger.warning(
                    "transaction_overrides.json references unknown transaction ID '%s' "
                    "(not present in current batch) – entry ignored.",
                    tx_id,
                )

        result: list[Transaction] = []
        for txn in transactions:
            entry = self.overrides.get(txn.transaction_id)
            if entry is None:
                result.append(txn)
                continue

            if entry.get("hidden"):
                continue  # exclude from output

            if "transaction_category" in entry:
                txn.auto_transaction_category = entry["transaction_category"]
            if "category" in entry:
                txn.auto_category = entry["category"]
            if "subcategory" in entry:
                txn.auto_subcategory = entry["subcategory"]

            result.append(txn)

        return result

    @property
    def count(self) -> int:
        return len(self.overrides)

    def unknown_ids(self, known_ids: set[str]) -> list[str]:
        """Return sorted override IDs that are not present in *known_ids*."""
        return sorted(tx_id for tx_id in self.overrides if tx_id not in known_ids)


def load_overrides_if_present(overrides_path: Optional[str]) -> Optional["TransactionOverrides"]:
    """Load overrides from *overrides_path* if the file exists; return None otherwise."""
    if overrides_path is None:
        return None
    p = Path(overrides_path)
    if not p.exists():
        return None
    return TransactionOverrides(str(p))
