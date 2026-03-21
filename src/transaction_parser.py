from datetime import datetime
from typing import Optional

import math

def _is_na(x):
    if x is None:
        return True
    try:
        if isinstance(x, float) and math.isnan(x):
            return True
    except Exception:
        pass
    s = str(x).strip()
    return s == "" or s.lower() == "nan" or s == "<NA>"

from models import Transaction
from notification.facade import NotificationTextParser


def _parse_amount(val) -> float:
    """
    Parse a PostFinance amount string into a float.

    Handles the following PostFinance-specific formats:
    - Thousands separator: "1'234.50" → 1234.50
    - Negative debit values: "-1'234.50" → 1234.50 (sign handled by caller)
    - Empty / NaN values: "", NaN, None → 0.0

    Args:
        val: Raw cell value from the CSV row.

    Returns:
        Absolute float value, always >= 0.
    """
    if _is_na(val):
        return 0.0
    normalized = str(val).replace("'", "").replace("-", "").strip()
    return float(normalized or 0)


class TransactionParser:
    """Parser for converting single CSV rows into Transaction objects."""

    @staticmethod
    def parse_row(row) -> Optional[Transaction]:
        """
        Parse a single CSV row.

        Returns:
            Transaction or None (if the row should be skipped).
        """
        if _is_na(row.get("Datum")):
            return None

        gutschrift = _parse_amount(row.get("Gutschrift in CHF", 0))
        lastschrift = _parse_amount(row.get("Lastschrift in CHF", 0))

        datum = datetime.strptime(str(row["Datum"]), "%d.%m.%Y")

        avisierung_raw = row.get("Avisierungstext", "")
        avisierungstext = "" if _is_na(avisierung_raw) else str(avisierung_raw).strip()
        parsed = NotificationTextParser.parse(avisierungstext)

        return Transaction(
            datum=datum,
            bewegungstyp=str(row["Bewegungstyp"]).strip(),
            avisierungstext=avisierungstext,
            gutschrift=gutschrift,
            lastschrift=lastschrift,
            label=TransactionParser._clean_value(row.get("Label", "")),
            kategorie=TransactionParser._clean_value(row.get("Kategorie", "")),
            service_type=parsed["service_type"],
            card_number=parsed["card_number"],
            parsed_merchant=parsed["merchant"],
            parsed_location=parsed["location"],
            recipient=parsed["recipient"],
            recipient_iban=parsed["recipient_iban"],
            reference=parsed["reference"],
            transaction_type_detail=parsed["transaction_type_detail"],
        )

    @staticmethod
    def _clean_value(val) -> str:
        s = str(val).strip() if val is not None else ""
        return "" if s in ("nan", "<NA>", "") else s
