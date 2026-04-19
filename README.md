# 📊 Budget Tool

Automatic categorization of bank transactions using configurable JSON rules.

## Features

- CSV import (PostFinance format)
- Service-specific parser registry (card purchases incl. provider, cash withdrawals, credit transfers, Twint, Lastschrift variants, bank fees)
- Rule engine with priority-based matching
- Stable transaction IDs via persistent fingerprint registry
- Service/provider-scoped rule selection (`services` + optional `providers` in rules)
- Merchant, location, include/exclude keyword matching
- Structured CSV export with parsed service fields

### CSV locale support (current)

- Import and export are currently aligned to German PostFinance CSV conventions.
- Import expects German source columns from PostFinance (for example `Datum`, `Bewegungstyp`, `Avisierungstext`, `Gutschrift in CHF`, `Lastschrift in CHF`, `Kategorie`).
- Export preserves German transaction content (for example Lastschrift/Zahlung/Dauerauftrag details) in parsed fields.

## Setup

```bash
# Install uv (one-time, outside project)
brew install uv

# Create/update local virtual environment from pyproject.toml
uv sync

# Optional: activate the local virtual environment in your shell
source .venv/bin/activate

# If you activate `.venv` via `source .venv/bin/activate`, you can run # the same commands without `uv run`, for example `python categorize_transactions.py reference`
or `pytest -q`.

# Run pipeline for reference dataset
uv run python categorize_transactions.py reference

# Optional: run pipeline for your own local dataset/overlay setup
# I use a dataset in `data/private` only as an example here. If you choose to use that, however, note that it is already gitignored.
uv run python categorize_transactions.py private

# Optional: reuse original input CSV categories for otherwise uncategorized rows
uv run python categorize_transactions.py reference --use-input-category-fallback
```



## Analysis

After categorizing transactions, you can generate an Excel report with category analysis.
The analysis script discovers all `*.categorized.csv` files in the dataset output folder and aggregates them into one report.

```bash
# Generate aggregated analysis for all categorized CSV files in a dataset
uv run python analyze_by_category.py reference

# Specify a custom output file
uv run python analyze_by_category.py private my_analysis.xlsx
```

The generated Excel file includes:
- **Overview sheet**: Summary statistics with pie charts for expenses and income by category
- **Category Analysis sheet**: Detailed breakdown by main category
- **Subcategory Analysis sheet**: Detailed breakdown by category and subcategory

The Excel format allows you to easily modify charts, add custom analysis, and adjust formatting according to your needs.

## Tests

```bash
# Run all tests
uv run pytest -q

# Verbose output
uv run pytest -v

# Run a specific test file
uv run pytest tests/test_rule_matching.py
```

## Structure

```text
data/
├── reference/                     # Base rules + stable sample dataset
│ ├── rules.json                   # Base rule definitions (service-scoped matching)
│ ├── metadata/                    # Persistent metadata (transaction registry + months)
│ │ ├── transaction_id_registry.json # Persistent transaction fingerprint -> ID mapping
│ │ └── months.json                # Processed month periods
│ ├── input/                       # Stable sample input CSV files
│ └── output/                      # Expected/known categorized outputs
└── private/                       # Example for local-only data + optional rule overrides (gitignored)
  ├── rules.json                   # Overlay rules (same id overrides base, new id adds)
  ├── metadata/                    # Persistent metadata (transaction registry + months)
  │ ├── transaction_id_registry.json # Local persistent transaction fingerprint -> ID mapping
  │ └── months.json                # Processed month periods
  ├── input/                       # Your own local input CSV files
  └── output/                      # Generated local categorized CSV outputs

src/
├── import_handler.py              # CSV import utilities
├── export_handler.py              # Structured CSV export builder
├── models/                        # Domain model package
│ ├── transaction.py               # Transaction dataclass
│ └── rule.py                      # Rule dataclass + matching logic
├── rule_engine.py                 # Rule loading + service/provider-filtered categorization
├── transaction_id_registry.py     # Stable transaction ID assignment + registry persistence
├── transaction_parser.py          # Row-to-Transaction conversion
└── notification/
  ├── base.py                    # Parser interface + parse result model
  ├── facade.py                  # Public facade to parser registry
  ├── registry.py                # Parser dispatch (first supporting parser wins)
  └── parsers/
    ├── card_purchase_parser.py  # Card purchase parser (Kauf/Dienstleistung + Online-Shopping, optional provider)
    ├── cash_withdrawal_parser.py# Cash withdrawal parser (Bargeldbezug)
    ├── credit_transfer_parser.py# Credit transfer parser (Gutschrift Auftraggeber/Absender)
    ├── bank_package_fee_parser.py# Bank package fee parser
    ├── twint_send_parser.py     # Twint send-money parser
    ├── debit_direct_parser.py   # CH-DD debit direct parser
    ├── payment_parser.py        # Lastschrift payment parser
    └── standing_order_parser.py # Lastschrift standing-order parser

categorize_transactions.py                # Pipeline entry point
tests/                             # Unit/integration-style tests for pipeline components
```

## Data flow

```text
data/{reference|private}/input/*.csv
   -> ImportHandler.load_csv
   -> TransactionParser.parse_row
   -> NotificationTextParser.parse (via parser registry)
  -> TransactionIdRegistry.assign_batch
   -> RuleEngine.categorize_batch
   -> ExportHandler.export_csv
  -> data/{reference|private}/output/*.categorized.csv

During the categorize run, transaction IDs are assigned and persisted in
`data/{reference|private}/metadata/transaction_id_registry.json`.
Months metadata is written to `data/{reference|private}/metadata/months.json`.
IDs remain stable across reruns as long as the normalized transaction content (date, type, notification text, credit/debit) and duplicate occurrence order remain unchanged.
```

## Rules

`data/reference/rules.json` is the shared base configuration.
`data/private/rules.json` is an optional local overlay example for personal rules and is typically not committed.

Example:

```json
{
  "rules": [
    {
      "id": 1,
      "name": "Migros Take-Away",
      "transaction_category": "expense",
      "category": "Freizeit",
      "subcategory": "Gastronomie",
      "priority": 100,
      "transaction_type": "debit",
      "transaction_type_detail": "Kauf/Dienstleistung",
      "services": ["Karteneinkauf"],
      "providers": ["Apple Pay"],
      "triggers": {
        "merchants": ["MIGROS"],
        "locations": [],
        "include_keywords": ["TAKE AWAY"],
        "exclude_keywords": []
      }
    }
  ]
}
```

### Matching behavior

- Rules are sorted by descending `priority`.
- `transaction_category` is required and must be one of: `income`, `expense`, `refund`, `transfer`.
- Category assignment uses two levels: `category` and `subcategory`.
- `category`/`subcategory` mapping is optional per rule (empty values are allowed).
- `transaction_type` filters on money direction: `credit` or `debit`.
- `transaction_type_detail` can optionally filter on parsed detail (for example `Geld senden`, `Kauf/Dienstleistung`, `Dauerauftrag`). Use `null` (or empty) to disable this filter.
- Rules can filter by parsed `service_type` (`services`) and optional `provider` (`providers`).
- A rule matches only if all configured conditions match.
- `merchants`: OR logic (at least one must match).
- `locations`: AND logic (all must match).
- `include_keywords`: AND logic (all must match).
- `exclude_keywords`: none may match.

### No fallback category

There is no fallback category in the engine.
If no parser matches a service or no rule matches that service, the transaction stays uncategorized.

For export compatibility only, `categorize_transactions.py` can optionally reuse the original input CSV category via `--use-input-category-fallback`.

## Export format

The structured export currently uses these columns:

- Transaction ID
- Date
- Transaction Type
- Transaction Type Detail
- Service
- Provider
- Card Number
- Merchant
- Location
- Counterparty
- Counterparty IBAN
- Reference
- Credit in CHF
- Debit in CHF
- Label
- Transaction Category
- Category
- Subcategory

## Iterative workflow

1. Put a new CSV into `data/reference/input/` (shared) or into your local `data/private/input/` setup.
2. Run `uv run python categorize_transactions.py reference` or, for your local setup, `uv run python categorize_transactions.py private`.
3. Inspect `data/reference/output/*.categorized.csv` or your local `data/private/output/*.categorized.csv`.
4. Add/refine parser(s) in `src/notification/parsers/` if needed.
5. Add/refine matching rules in `data/reference/rules.json` (base) and/or optional personal overrides in `data/private/rules.json`.
6. Repeat until categorization quality is acceptable.

### Private override rules with version control

If you keep personal data and overrides in `data/private`, there are two practical ways to version them without storing them in the public repository.

Approach A (recommended): nested private Git repository in `data/private`

- Initialize a second, private Git repository in `data/private` for personal files (`rules.json`, `metadata/`, optional private input snapshots).
- Commit and push private changes from `data/private` separately.

Example:

```bash
cd data/private
git init
git remote add origin <private-remote-url>
git add rules.json metadata input output
git commit -m "Initial private dataset"
git push -u origin main
```

Approach B (alternative): separate private repository outside this project

- Keep the private repository elsewhere on disk.
- Link `data/private/rules.json` (or the whole `data/private` directory) to that private location.
- Use this when you prefer strict repository separation instead of a nested repository.

Both approaches work with the current overlay mechanism:

- Base rules are always loaded from `data/reference/rules.json`.
- Optional overlay rules are loaded from `{run_dir}/rules.json` (for example `data/private/rules.json`).
- Same rule ID overrides base; new rule ID adds a new rule.
