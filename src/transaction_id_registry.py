import hashlib
import json
from pathlib import Path

from models import Transaction


class TransactionIdRegistry:
    """Persistent mapping of transaction fingerprints to stable transaction IDs."""

    def __init__(self, registry_path: Path):
        self.registry_path = registry_path
        self._next_id = 1
        self._mapping: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        if not self.registry_path.exists():
            return

        with open(self.registry_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self._next_id = int(data.get("next_id", 1))
        self._mapping = {
            str(key): str(value)
            for key, value in data.get("mapping", {}).items()
        }

    def save(self) -> None:
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "next_id": self._next_id,
            "mapping": self._mapping,
        }
        with open(self.registry_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=True, indent=2, sort_keys=True)

    def assign_batch(self, transactions: list[Transaction]) -> None:
        duplicate_counter: dict[str, int] = {}
        for transaction in transactions:
            base_key = self._base_fingerprint(transaction)
            duplicate_counter[base_key] = duplicate_counter.get(base_key, 0) + 1
            occurrence = duplicate_counter[base_key]
            unique_key = f"{base_key}#{occurrence}"

            if unique_key not in self._mapping:
                self._mapping[unique_key] = self._generate_id()

            transaction.transaction_id = self._mapping[unique_key]

    def _generate_id(self) -> str:
        transaction_id = f"TX-{self._next_id:06d}"
        self._next_id += 1
        return transaction_id

    @staticmethod
    def _base_fingerprint(transaction: Transaction) -> str:
        canonical = "|".join(
            [
                transaction.date.strftime("%Y-%m-%d"),
                transaction.transaction_type.strip().upper(),
                transaction.notification_text.strip().upper(),
                f"{transaction.credit:.2f}",
                f"{transaction.debit:.2f}",
            ]
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()