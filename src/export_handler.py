import pandas as pd
from pathlib import Path
from typing import Optional
import math
from models import Transaction, Rule


class ExportHandler:
    """
    Export handler for categorized transactions.
    Saves data in a structured format with separate merchant and location columns.
    """

    # Standard export columns
    EXPORT_COLUMNS = [
        "Date",
        "Transaction Type",
        "Transaction Type Detail",
        "Service",
        "Card Number",
        "Merchant",
        "Location",
        "Recipient",
        "Recipient IBAN",
        "Reference",
        "Credit in CHF",
        "Debit in CHF",
        "Label",
        "Category",
    ]
    
    @staticmethod
    def extract_merchant_location(
        transaction: Transaction, 
        matching_rules: Optional[list] = None
    ) -> tuple[str, str]:
        """
        Extract merchant and location from the transaction and matching rules.

        Strategy:
        1. If rules matched: use merchants/locations from rules
        2. Otherwise: try to extract from notification text
        
        Returns:
            (merchant, location) tuple
        """
        merchant = ""
        location = ""

        if transaction.parsed_merchant:
            merchant = transaction.parsed_merchant
        if transaction.parsed_location:
            location = transaction.parsed_location
        
        # If rules are present, extract merchant/location
        if matching_rules:
            # Merchants from highest-priority rule
            if not merchant and matching_rules[0].merchants:
                merchant = " / ".join(matching_rules[0].merchants)

            # Locations from highest-priority rule
            if not location and matching_rules[0].locations:
                location = " / ".join(matching_rules[0].locations)

        # Fallback: try to extract from notification text
        # Format: "... MERCHANT LOCATION SCHWEIZ" or "MERCHANT (ZIP) LOCATION SCHWEIZ"
        if not merchant or not location:
            text_parts = transaction.avisierungstext.split()

            # Simple heuristic: trailing tokens are often location + country
            # e.g. "MIGROS IGELWEID (4213) AARAU SCHWEIZ"
            if "SCHWEIZ" in transaction.text_upper:
                # Location is what appears before "SCHWEIZ"
                switzerland_idx = transaction.text_upper.rfind("SCHWEIZ")
                before_country = transaction.avisierungstext[:switzerland_idx].strip()

                # Last token before SCHWEIZ is typically the city
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
        Save transactions in a structured export format.

        Args:
            transactions: List of transactions
            output_path: Target CSV path
            matching_rules_map: Mapping of transaction index to matching rules (optional)
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        rows = []
        for idx, txn in enumerate(transactions):
            # Get matching rules if provided
            rules = matching_rules_map.get(idx) if matching_rules_map else None
            merchant, location = ExportHandler.extract_merchant_location(txn, rules)
            
            # Credit/debit formatting (use NaN for empty values)
            gutschrift = txn.gutschrift if txn.gutschrift > 0 else math.nan
            lastschrift = abs(txn.lastschrift) if txn.lastschrift < 0 else math.nan
            
            rows.append({
                "Date": txn.datum.strftime("%d.%m.%Y"),
                "Transaction Type": txn.bewegungstyp,
                "Transaction Type Detail": txn.transaction_type_detail,
                "Service": txn.service_type,
                "Card Number": txn.card_number,
                "Merchant": merchant,
                "Location": location,
                "Recipient": txn.recipient,
                "Recipient IBAN": txn.recipient_iban,
                "Reference": txn.reference,
                "Credit in CHF": gutschrift,
                "Debit in CHF": lastschrift,
                "Label": txn.label,
                "Category": txn.kategorie_auto or txn.kategorie or "?",
            })
        
        df = pd.DataFrame(rows, columns=ExportHandler.EXPORT_COLUMNS)
        # Replace NaN with empty string for cleaner CSV
        df = df.fillna("")
        df.to_csv(output_path, sep=";", index=False, encoding="utf-8")
        print(f"✅ Exported {len(transactions)} transactions: {output_path}")
        return df
