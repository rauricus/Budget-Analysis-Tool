import io
import pandas as pd
from pathlib import Path
from typing import Optional
from models import Transaction
from transaction_parser import TransactionParser, TransactionParserError

_MIN_DELIMITER_COUNT = 3
_HEADER_SCAN_LIMIT = 10
_BOOKED_MOVEMENT_TYPE = "BUCHUNG"


def _movement_type_warning(value) -> Optional[str]:
    """Return a warning when a row is not a booked movement, else None.

    PostFinance writes "Buchung" in the `Bewegungstyp` column of every row seen so
    far, and the pipeline does not read the column at all.  A different value would
    most likely mean the row is not a booking but something like a reservation,
    which the pipeline would nonetheless import, categorize and count as one.  It is
    not treated as an error, because the correct handling is unknown until such a
    row actually turns up.
    """
    text = "" if value is None else str(value).strip()
    if not text or text.lower() in ("nan", "<na>"):
        return None
    if text.upper() == _BOOKED_MOVEMENT_TYPE:
        return None
    return (
        f"Unexpected 'Bewegungstyp': '{text}'. Only 'Buchung' is known to mean a booked "
        "transaction; this row is imported and counted like one."
    )


def _find_header_line(lines: list[str]) -> tuple[int, str]:
    """Scan the first _HEADER_SCAN_LIMIT lines and return (line_index, delimiter).

    The first line that contains at least _MIN_DELIMITER_COUNT occurrences of either
    ";" or "," is treated as the header row.  ";" wins on a tie.

    Raises ValueError if no such line is found within the scan window.
    """
    for idx, line in enumerate(lines[:_HEADER_SCAN_LIMIT]):
        semi = line.count(";")
        comma = line.count(",")
        if semi >= _MIN_DELIMITER_COUNT:
            return idx, ";"
        if comma >= _MIN_DELIMITER_COUNT:
            return idx, ","
    raise ValueError(
        f"No header line with >={_MIN_DELIMITER_COUNT} delimiters found. First {_HEADER_SCAN_LIMIT} lines scanned."
    )


class ImportHandler:
    """CSV import for transactions."""

    @staticmethod
    def load_csv(csv_path: str, debug: bool = False) -> list[Transaction]:
        """
        Load a delimited CSV file.

        Args:
            csv_path: Path to the CSV file.
            debug: When True, print the full row content on warnings and errors.
        """
        csv_path = Path(csv_path)
        if not csv_path.exists():
            raise FileNotFoundError(f"CSV not found: {csv_path}")

        raw_lines = csv_path.read_text(encoding="utf-8").splitlines()

        header_idx, delimiter = _find_header_line(raw_lines)

        kept_lines = [raw_lines[header_idx]]
        # Track the 1-based file line number for each data row so that
        # warnings point to the correct line in the original CSV, even when
        # empty or sparse lines are skipped.
        data_row_file_lines = []
        data_row_texts = []
        for file_idx, line in enumerate(raw_lines[header_idx + 1:], start=header_idx + 1):
            if line.count(delimiter) >= _MIN_DELIMITER_COUNT:
                kept_lines.append(line)
                data_row_file_lines.append(file_idx + 1)  # 1-based
                data_row_texts.append(line)

        df = pd.read_csv(io.StringIO("\n".join(kept_lines)), sep=delimiter)

        firstError = True
        transactions = []
        for pandas_index, row in df.iterrows():
            csv_row = data_row_file_lines[pandas_index]

            movement_warning = _movement_type_warning(row.get("Bewegungstyp"))
            if movement_warning:
                if firstError:
                    print(); firstError = False
                print(f"   ⚠️  Row {csv_row}: {movement_warning}")

            try:
                txn = TransactionParser.parse_row(row)
            except TransactionParserError as e:
                if firstError:
                    print(); firstError = False
                print(f"   ⚠️  Row {csv_row}: {e}")
                txn = e.transaction
            except Exception as e:
                if firstError:
                    print(); firstError = False
                print(f"   ❌  Row {csv_row}: {e}")
                if debug:
                    print(f"      Row data: {row.to_dict()}")
                raise

            if txn is not None:
                txn.source_line_number = csv_row
                txn.source_row_text = data_row_texts[pandas_index]
                transactions.append(txn)

        print()
        print(f"   Loaded {len(transactions)} transactions")
        return transactions
