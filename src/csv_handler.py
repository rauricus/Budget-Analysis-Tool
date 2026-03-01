import pandas as pd
from pathlib import Path
from models import Transaction
from transaction_parser import TransactionParser


class CSVHandler:
    """CSV-Import/Export für Transaktionen"""
    
    @staticmethod
    def load_csv(csv_path: str) -> list[Transaction]:
        """
        Lädt CSV (PostFinance Format).
        Skipped erste 5 Zeilen (Header/Meta).
        """
        csv_path = Path(csv_path)
        if not csv_path.exists():
            raise FileNotFoundError(f"CSV nicht gefunden: {csv_path}")
        
        # PostFinance CSV: Skip first 5 rows
        df = pd.read_csv(csv_path, sep=";", skiprows=5, encoding="utf-8")
        
        transactions = []
        for _, row in df.iterrows():
            txn = TransactionParser.parse_row(row)
            if txn is not None:
                transactions.append(txn)
        
        print(f"✅ {len(transactions)} Transaktionen geladen")
        return transactions
    
    @staticmethod
    def save_csv(transactions: list[Transaction], output_path: str):
        """
        Speichert Transaktionen als CSV (mit kategorie_auto Spalte).
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        rows = []
        for txn in transactions:
            rows.append({
                "Datum": txn.datum.strftime("%d.%m.%Y"),
                "Bewegungstyp": txn.bewegungstyp,
                "Avisierungstext": txn.avisierungstext,
                "Gutschrift in CHF": txn.gutschrift if txn.gutschrift > 0 else "",
                "Lastschrift in CHF": txn.lastschrift if txn.lastschrift < 0 else "",
                "Label": txn.label,
                "Kategorie (Bank)": txn.kategorie,
                "Kategorie (Auto)": txn.kategorie_auto or "?",
            })
        
        df = pd.DataFrame(rows)
        df.to_csv(output_path, sep=";", index=False, encoding="utf-8")
        print(f"✅ {len(transactions)} Transaktionen gespeichert: {output_path}")
