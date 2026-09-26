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
    "subcategory": "Diverses",            // override auto_subcategory
    "split": [                             // replace the row by one row per part
      {"amount": 12.50, "category": "Wohnen", "subcategory": "Haushalt"},
      {"category": "Einkaufen"}            // no amount: receives the remainder
    ]
  }

A split turns TX-000042 into TX-000042.1, TX-000042.2, ... in list order. The
parts inherit the transaction's (possibly overridden) transaction category
unless they set their own.
"""

import json
import logging
from dataclasses import replace
from pathlib import Path
from typing import Optional

from models import Transaction

logger = logging.getLogger(__name__)

VALID_TRANSACTION_CATEGORIES = {"Income", "Expense", "Refund", "Transfer"}
ALLOWED_OVERRIDE_FIELDS = {
    "hidden", "transaction_category", "category", "subcategory", "split", "_row", "_note",
}
ALLOWED_SPLIT_PART_FIELDS = {"amount", "transaction_category", "category", "subcategory", "_note"}


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
            for comment_field in ("_row", "_note"):
                comment_value = entry.get(comment_field)
                if comment_value is not None and not isinstance(comment_value, str):
                    raise ValueError(
                        f"'{comment_field}' in override entry for '{tx_id}' must be a string "
                        f"in {self.overrides_path}."
                    )
            if "split" in entry:
                self._validate_split(tx_id, entry)

        self.overrides = raw

    def _validate_split(self, tx_id: str, entry: dict) -> None:
        """Check the structure of a split; amounts against the total are checked in apply."""
        where = f"in override entry for '{tx_id}' in {self.overrides_path}"
        if entry.get("hidden"):
            raise ValueError(f"'split' cannot be combined with 'hidden' {where}.")
        parts = entry["split"]
        if not isinstance(parts, list) or len(parts) < 2:
            raise ValueError(f"'split' must be a list of at least 2 parts {where}.")

        for idx, part in enumerate(parts, start=1):
            if not isinstance(part, dict):
                raise ValueError(f"Split part {idx} must be an object {where}.")
            unknown_fields = set(part.keys()) - ALLOWED_SPLIT_PART_FIELDS
            if unknown_fields:
                raise ValueError(
                    f"Unknown field(s) {sorted(unknown_fields)} in split part {idx} {where}. "
                    f"Allowed: {sorted(ALLOWED_SPLIT_PART_FIELDS)}"
                )
            category = part.get("category")
            if not isinstance(category, str) or not category:
                raise ValueError(f"Split part {idx} needs a 'category' {where}.")
            tc = part.get("transaction_category")
            if tc is not None and tc not in VALID_TRANSACTION_CATEGORIES:
                raise ValueError(
                    f"Invalid 'transaction_category' '{tc}' in split part {idx} {where}. "
                    f"Allowed: {sorted(VALID_TRANSACTION_CATEGORIES)}"
                )
            if "amount" in part:
                amount = part["amount"]
                # bool is an int subclass; reject it explicitly.
                if isinstance(amount, bool) or not isinstance(amount, (int, float)) or amount <= 0:
                    raise ValueError(
                        f"'amount' in split part {idx} must be a positive number {where}."
                    )

        without_amount = sum(1 for part in parts if "amount" not in part)
        if without_amount != 1:
            raise ValueError(
                f"Exactly one split part must omit 'amount' and receive the remainder, "
                f"found {without_amount} {where}."
            )

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

            if "split" in entry:
                result.extend(self._split(txn, entry["split"]))
            else:
                result.append(txn)

        return result

    def _split(self, txn: Transaction, parts: list[dict]) -> list[Transaction]:
        """Return one copy of *txn* per part, each carrying its share of the amount."""
        total = txn.credit if txn.transaction_type == "Credit" else txn.debit
        given = sum(part["amount"] for part in parts if "amount" in part)
        remainder = round(total - given, 2)
        if remainder <= 0:
            raise ValueError(
                f"Split amounts for '{txn.transaction_id}' add up to {given:.2f}, which leaves "
                f"no remainder of the transaction total {total:.2f} "
                f"({self.overrides_path})."
            )

        result: list[Transaction] = []
        for idx, part in enumerate(parts, start=1):
            amount = round(part["amount"], 2) if "amount" in part else remainder
            result.append(replace(
                txn,
                transaction_id=f"{txn.transaction_id}.{idx}",
                credit=amount if txn.transaction_type == "Credit" else 0.0,
                debit=amount if txn.transaction_type == "Debit" else 0.0,
                auto_transaction_category=part.get(
                    "transaction_category", txn.auto_transaction_category
                ),
                auto_category=part["category"],
                auto_subcategory=part.get("subcategory"),
            ))
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
