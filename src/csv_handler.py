import pandas as pd
from pathlib import Path
from datetime import datetime
from models import Transaction
from notification_parser import NotificationTextParser


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
            # Skip leere Reihen
            if pd.isna(row.get("Datum")):
                continue
            
            # Belege in Floats (NaN → 0.0)
            gutschrift = float(row.get("Gutschrift in CHF", 0) or 0)
            lastschrift = float(str(row.get("Lastschrift in CHF", 0) or 0).replace("-", ""))
            
            datum = datetime.strptime(str(row["Datum"]), "%d.%m.%Y")
            
            # Helper function to clean pandas NaN/nan strings (only for optional fields)
            def clean_value(val):
                s = str(val).strip() if val is not None else ""
                return "" if s in ("nan", "<NA>", "") else s

            avisierungstext = str(row["Avisierungstext"]).strip()
            parsed = NotificationTextParser.parse(avisierungstext)
            
            txn = Transaction(
                datum=datum,
                bewegungstyp=str(row["Bewegungstyp"]).strip(),
                avisierungstext=avisierungstext,
                gutschrift=gutschrift,
                lastschrift=-lastschrift,  # Negative speichern
                label=clean_value(row.get("Label", "")),
                kategorie=clean_value(row.get("Kategorie", "")),
                service_type=parsed["service_type"],
                card_number=parsed["card_number"],
                parsed_merchant=parsed["merchant"],
                parsed_location=parsed["location"],
            )
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
