import pandas as pd
from pathlib import Path
from models import Transaction
from transaction_parser import TransactionParser


class CSVHandler:
    """CSV import/export for transactions."""
    
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
        
        print(f"✅ Loaded {len(transactions)} transactions")
        return transactions
    
    @staticmethod
    def save_csv(transactions: list[Transaction], output_path: str):
        """
        Save transactions as CSV (with `kategorie_auto` column).
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        rows = []
        for txn in transactions:
            rows.append({
                "Date": txn.datum.strftime("%d.%m.%Y"),
                "Bewegungstyp": txn.bewegungstyp,
                "Avisierungstext": txn.avisierungstext,
                "Credit in CHF": txn.gutschrift if txn.gutschrift > 0 else "",
                "Debit in CHF": txn.lastschrift if txn.lastschrift < 0 else "",
                "Label": txn.label,
                "Category (Bank)": txn.kategorie,
                "Category (Auto)": txn.kategorie_auto or "?",
            })
        
        df = pd.DataFrame(rows)
        df.to_csv(output_path, sep=";", index=False, encoding="utf-8")
        print(f"✅ Saved {len(transactions)} transactions: {output_path}")
