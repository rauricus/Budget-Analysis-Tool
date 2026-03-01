import pandas as pd
from pathlib import Path
from typing import Optional
import math
from models import Transaction, Rule


class ExportHandler:
    """
    Export-Handler für kategorisierte Transaktionen.
    Speichert in strukturiertes Format mit separaten Spalten für Händler und Ort.
    """
    
    # Standard-Spalten im Export
    EXPORT_COLUMNS = [
        "Datum",
        "Transaktionstyp",
        "Transaktionstyp Detail",
        "Service",
        "Kartennummer",
        "Händler",
        "Ort",
        "Empfänger",
        "Empfänger IBAN",
        "Referenz",
        "Gutschrift in CHF",
        "Lastschrift in CHF",
        "Label",
        "Kategorie",
    ]
    
    @staticmethod
    def extract_merchant_location(
        transaction: Transaction, 
        matching_rules: Optional[list] = None
    ) -> tuple[str, str]:
        """
        Extrahiert Händler und Ort aus Transaktion und zugehörigen Regeln.
        
        Strategie:
        1. Falls Regeln gematched haben: verwende Merchants/Locations aus Regeln
        2. Ansonsten: versuche aus avisierungstext zu extrahieren
        
        Returns:
            (merchant, location) tuple
        """
        merchant = ""
        location = ""

        if transaction.parsed_merchant:
            merchant = transaction.parsed_merchant
        if transaction.parsed_location:
            location = transaction.parsed_location
        
        # Wenn Regeln vorhanden, extrahiere Merchant/Location
        if matching_rules:
            # Merchants aus höchster Priority Rule
            if not merchant and matching_rules[0].merchants:
                merchant = " / ".join(matching_rules[0].merchants)
            
            # Locations aus höchster Priority Rule
            if not location and matching_rules[0].locations:
                location = " / ".join(matching_rules[0].locations)
        
        # Fallback: versuche aus Avisierungstext zu extrahieren
        # Format: "... MERCHANT LOCATION SCHWEIZ" oder "MERCHANT (PLZ) LOCATION SCHWEIZ"
        if not merchant or not location:
            text_parts = transaction.avisierungstext.split()
            
            # Einfache Heuristic: letzte Teile sind meist Ort + Land
            # z.B. "MIGROS IGELWEID (4213) AARAU SCHWEIZ"
            if "SCHWEIZ" in transaction.text_upper:
                # Location ist das, was vor "SCHWEIZ" kommt
                switzerland_idx = transaction.text_upper.rfind("SCHWEIZ")
                before_country = transaction.avisierungstext[:switzerland_idx].strip()
                
                # Letztes Wort vor SCHWEIZ ist üblicherweise die Stadt
                last_word = before_country.split()[-1] if before_country else ""
                if last_word and last_word not in ("VOM", "NR.", "KARTEN"):
                    location = last_word
        
        return merchant, location
    
    @staticmethod
    def export_csv(
        transactions: list,
        output_path: str,
        matching_rules_map: Optional[dict] = None,
    ):
        """
        Speichert Transaktionen im strukturierten Export-Format.
        
        Args:
            transactions: Liste von Transaktionen
            output_path: Ziel-Pfad für CSV
            matching_rules_map: Mapping von Transaction-Index zu matching Rules (optional)
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        rows = []
        for idx, txn in enumerate(transactions):
            # Get matching rules if provided
            rules = matching_rules_map.get(idx) if matching_rules_map else None
            merchant, location = ExportHandler.extract_merchant_location(txn, rules)
            
            # Gutschrift/Lastschrift formatting (use NaN for empty values)
            gutschrift = txn.gutschrift if txn.gutschrift > 0 else math.nan
            lastschrift = abs(txn.lastschrift) if txn.lastschrift < 0 else math.nan
            
            rows.append({
                "Datum": txn.datum.strftime("%d.%m.%Y"),
                "Transaktionstyp": txn.bewegungstyp,
                "Transaktionstyp Detail": txn.transaction_type_detail,
                "Service": txn.service_type,
                "Kartennummer": txn.card_number,
                "Händler": merchant,
                "Ort": location,
                "Empfänger": txn.recipient,
                "Empfänger IBAN": txn.recipient_iban,
                "Referenz": txn.reference,
                "Gutschrift in CHF": gutschrift,
                "Lastschrift in CHF": lastschrift,
                "Label": txn.label,
                "Kategorie": txn.kategorie_auto or txn.kategorie or "?",
            })
        
        df = pd.DataFrame(rows, columns=ExportHandler.EXPORT_COLUMNS)
        # Replace NaN with empty string for cleaner CSV
        df = df.fillna("")
        df.to_csv(output_path, sep=";", index=False, encoding="utf-8")
        print(f"✅ {len(transactions)} Transaktionen exportiert: {output_path}")
        return df
