import pandas as pd
from pathlib import Path
from models import Transaction
from transaction_parser import TransactionParser


class ImportHandler:
    """CSV import for transactions."""

    @staticmethod
    def load_csv(csv_path: str) -> list[Transaction]:
        """
        Load CSV (PostFinance format).
        Skips the first 5 rows (header/meta).
        """
        csv_path = Path(csv_path)
        if not csv_path.exists():
            raise FileNotFoundError(f"CSV not found: {csv_path}")

        # PostFinance CSV: Skip first 5 rows
        df = pd.read_csv(csv_path, sep=";", skiprows=5, encoding="utf-8")

        transactions = []
        for _, row in df.iterrows():
            txn = TransactionParser.parse_row(row)
            if txn is not None:
                transactions.append(txn)

        print(f"   Loaded {len(transactions)} transactions")
        return transactions
