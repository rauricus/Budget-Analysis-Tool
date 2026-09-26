"""
Transaction Split
Splits one transaction into parts with their own categories. Shared by split overrides in
transaction_overrides.json and by the `split` field on rules.

A split turns TX-000042 into TX-000042.1, TX-000042.2, ... in list order. Exactly one part
omits `amount` and receives the remainder.
"""

from dataclasses import replace
from typing import Optional

from models import Transaction

VALID_TRANSACTION_CATEGORIES = {"Income", "Expense", "Refund", "Transfer"}
ALLOWED_SPLIT_PART_FIELDS = {"amount", "transaction_category", "category", "subcategory", "_note"}


def validate_split_parts(parts, where: str, category_optional: bool = False) -> None:
    """Check the structure of a split; amounts against the total are checked when splitting.

    *where* completes the error messages ("in override entry for 'TX-…' in …").
    With *category_optional*, a part may omit `category` and inherit it (rules do this).
    """
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
        if not (category_optional and "category" not in part) and (
            not isinstance(category, str) or not category
        ):
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


def split_transaction(
    txn: Transaction,
    parts: list[dict],
    source: str,
    default_category: Optional[str] = None,
    default_subcategory: Optional[str] = None,
) -> list[Transaction]:
    """Return one copy of *txn* per part, each carrying its share of the amount.

    Parts inherit the transaction's transaction category unless they set their own. A part
    without `category` takes *default_category* and *default_subcategory*. *source* names
    where the split is defined, for the error when the amounts leave no remainder.
    """
    total = txn.credit if txn.transaction_type == "Credit" else txn.debit
    given = sum(part["amount"] for part in parts if "amount" in part)
    remainder = round(total - given, 2)
    if remainder <= 0:
        raise ValueError(
            f"Split amounts for '{txn.transaction_id}' add up to {given:.2f}, which leaves "
            f"no remainder of the transaction total {total:.2f} ({source})."
        )

    result: list[Transaction] = []
    for idx, part in enumerate(parts, start=1):
        amount = round(part["amount"], 2) if "amount" in part else remainder
        inherits = "category" not in part
        result.append(replace(
            txn,
            transaction_id=f"{txn.transaction_id}.{idx}",
            credit=amount if txn.transaction_type == "Credit" else 0.0,
            debit=amount if txn.transaction_type == "Debit" else 0.0,
            auto_transaction_category=part.get(
                "transaction_category", txn.auto_transaction_category
            ),
            auto_category=default_category if inherits else part["category"],
            auto_subcategory=default_subcategory if inherits else part.get("subcategory"),
        ))
    return result
