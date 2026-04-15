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
        "Transaction ID",
        "Date",
        "Transaction Type",
        "Transaction Type Detail",
        "Service",
        "Provider",
        "Card Number",
        "Merchant",
        "Location",
        "Counterparty",
        "Counterparty IBAN",
        "Reference",
        "Credit in CHF",
        "Debit in CHF",
        "Label",
        "Category",
        "Subcategory",
    ]

    @staticmethod
    def split_category_fields(
        transaction: Transaction,
        use_input_category_fallback: bool = False,
    ) -> tuple[str, str]:
        """Return category/subcategory for export.

        Prefer rule-based automatic categorization. Optionally, a transaction
        can fall back to the original CSV category for export compatibility.
        """
        if transaction.auto_category:
            return transaction.auto_category, transaction.auto_subcategory or ""

        if not use_input_category_fallback:
            return "?", ""

        raw_category = (transaction.category or "").strip()
        if " // " in raw_category:
            category, subcategory = raw_category.split(" // ", 1)
            return category, subcategory

        return raw_category or "?", ""
    
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
            text_parts = transaction.notification_text.split()

            # Simple heuristic: trailing tokens are often location + country
            # e.g. "MIGROS IGELWEID (4213) AARAU SCHWEIZ"
            if "SCHWEIZ" in transaction.notification_text_upper:
                # Location is what appears before "SCHWEIZ"
                switzerland_idx = transaction.notification_text_upper.rfind("SCHWEIZ")
                before_country = transaction.notification_text[:switzerland_idx].strip()

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
        use_input_category_fallback: bool = False,
    ):
        """
        Save transactions in a structured export format.

        Args:
            transactions: List of transactions
            output_path: Target CSV path
            matching_rules_map: Mapping of transaction index to matching rules (optional)
            use_input_category_fallback: If True, reuse the original CSV category
                when no automatic categorization is available.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        rows = []
        for idx, txn in enumerate(transactions):
            # Get matching rules if provided
            rules = matching_rules_map.get(idx) if matching_rules_map else None
            merchant, location = ExportHandler.extract_merchant_location(txn, rules)
            category, subcategory = ExportHandler.split_category_fields(
                txn,
                use_input_category_fallback=use_input_category_fallback,
            )
            
            # Credit/debit formatting (use NaN for empty values)
            credit = txn.credit if txn.credit > 0 else math.nan
            debit = txn.debit if txn.debit > 0 else math.nan
            
            rows.append({
                "Transaction ID": txn.transaction_id,
                "Date": txn.date.strftime("%d.%m.%Y"),
                "Transaction Type": txn.transaction_type,
                "Transaction Type Detail": txn.transaction_type_detail,
                "Service": txn.service_type,
                "Provider": txn.provider,
                "Card Number": txn.card_number,
                "Merchant": merchant,
                "Location": location,
                "Counterparty": txn.counterparty,
                "Counterparty IBAN": txn.counterparty_iban,
                "Reference": txn.reference,
                "Credit in CHF": credit,
                "Debit in CHF": debit,
                "Label": txn.label,
                "Category": category,
                "Subcategory": subcategory,
            })
        
        df = pd.DataFrame(rows, columns=ExportHandler.EXPORT_COLUMNS)
        # Replace NaN with empty string for cleaner CSV
        df = df.fillna("")
        df.to_csv(output_path, sep=";", index=False, encoding="utf-8")
        
        print()
        print(f"   Exported {len(transactions)} transactions: {output_path}")
        return df
