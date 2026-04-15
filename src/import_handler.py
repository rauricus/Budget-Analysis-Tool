import io
import pandas as pd
from pathlib import Path
from models import Transaction
from transaction_parser import TransactionParser, TransactionParserError

_MIN_DELIMITER_COUNT = 3
_HEADER_SCAN_LIMIT = 10


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

        # header_idx is 0-based; CSV row numbers are 1-based.
        # First data row in the original file = header_idx + 2.
        data_row_offset = header_idx + 2

        kept_lines = [raw_lines[header_idx]]
        for line in raw_lines[header_idx + 1:]:
            if line.count(delimiter) >= _MIN_DELIMITER_COUNT:
                kept_lines.append(line)

        df = pd.read_csv(io.StringIO("\n".join(kept_lines)), sep=delimiter)

        firstError = True
        transactions = []
        for pandas_index, row in df.iterrows():
            csv_row = pandas_index + data_row_offset
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
                transactions.append(txn)

        print()
        print(f"   Loaded {len(transactions)} transactions")
        return transactions
