# 📊 Budget Tool

Automatic categorization of bank transactions using configurable JSON rules.

## Features

- CSV import (PostFinance format)
- Service-specific parser registry (card purchases incl. provider, cash withdrawals, credit transfers, Twint, Lastschrift variants, bank fees)
- Rule engine with priority-based matching (1-10; 1:lowest, 10:highest)
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

# If `.venv` is active, you can run commands without `uv run`
# e.g. `python categorize_transactions.py example` or `pytest -q`

# Run pipeline for the example dataset (used by tests/docs)
uv run python categorize_transactions.py example

# Optional: run pipeline for your own local dataset/overlay setup
# I use a dataset in `data/private` only as an example here. If you choose to use that, however, note that it is already gitignored.
uv run python categorize_transactions.py private

# Optional: reuse original input CSV categories for otherwise uncategorized rows
uv run python categorize_transactions.py example --use-input-category-fallback
```



## Analysis

After categorizing transactions, you can generate an Excel report with category analysis.
The analysis script discovers all `*.categorized.csv` files in the dataset output folder and aggregates them into one report.

```bash
# Generate aggregated analysis for all categorized CSV files in a dataset
uv run python analyze_by_category.py example

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
├── example/                       # Stable example dataset for tests/docs
│ ├── rules.json                   # Example rule set used by tests and docs
│ ├── metadata/                    # Example metadata (transaction registry + months)
│ │ ├── transaction_id_registry.json # Persistent transaction fingerprint -> ID mapping
│ │ └── months.json                # Processed month periods
│ ├── input/                       # Stable example input CSV files
│ └── output/                      # Expected/known categorized outputs for examples
├── reference/                     # Global base rules for overlays (shared baseline)
│ └── rules.json                   # Base rule definitions (service-scoped matching)
└── private/                       # Example for local-only data + optional rule overlay (gitignored)
  ├── rules.json                   # Optional overlay; can declare "base": "reference"
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
    ├── card_purchase_parser.py  # Card purchase parser (Purchase/Service + Purchase/Online Shopping, optional provider)
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
data/{example|private}/input/*.csv
   -> ImportHandler.load_csv
   -> TransactionParser.parse_row
   -> NotificationTextParser.parse (via parser registry)
  -> TransactionIdRegistry.assign_batch
   -> RuleEngine.categorize_batch
   -> ExportHandler.export_csv
  -> data/{example|private}/output/*.categorized.csv

During the categorize run, transaction IDs are assigned and persisted in
`data/{example|private}/metadata/transaction_id_registry.json`.
Months metadata is written to `data/{example|private}/metadata/months.json`.
IDs remain stable across reruns as long as the normalized transaction content (date, type, notification text, credit/debit) and duplicate occurrence order remain unchanged.
```

## Dataset convention

Use the datasets with clearly separated responsibilities:

- `data/example`: canonical examples for tests and documentation. May contain synthetic/fictive merchants and counterparties. Keep this dataset stable and reproducible. Standalone dataset.
- `data/reference`: global baseline rules for overlay-based datasets (`data/reference/rules.json`). Not a runnable dataset on its own (no input files).
- `data/private`: local, personal data and optional rule overlay. Usually gitignored and not committed to the public repository.

Decision guide for changes:

- New parser behavior examples, test fixtures, and documentation examples: change `data/example`.
- Generic rule improvements intended for everyone: change `data/reference/rules.json`.
- Personal or sensitive categorization logic: change `data/private/rules.json`.

Repository policy:

- Tests and docs should depend on `data/example`, not on `data/reference`.
- Never commit personal data from `data/private` to the public repository.

## Rules

`data/example/rules.json` is the standalone example rule set used for tests and documentation.
`data/reference/rules.json` is the shared baseline for overlay-based datasets.
`data/private/rules.json` is an optional local overlay for personal rules and is typically not committed.

Each rule has a required string `key`. Keys must be unique within a file.
Recommended format: `group_number` (for example `gastronomy_1`, `transport_2`).

### Standalone vs. overlay datasets

A `rules.json` file can optionally declare a dependency on another dataset's rules via a top-level `"base"` field:

```json
{ "base": "reference", "rules": [...] }
```

When `"base"` is set, the named dataset's `rules.json` is loaded first as the base, and the current file is applied as an overlay on top. Without `"base"`, the file is treated as a complete standalone rule set.

### Overriding a base rule

An overlay rule that replaces a base rule must declare `"override": "<base_key>"` and carry its own unique `key`. At runtime, the engine stores the overlay rule under the base rule's key, so the original identity is preserved for matching and debug output.

```json
{
  "key": "income_1_dev",
  "override": "income_1",
  "name": "Lohn: Meine Firma",
  ...
}
```

Rules that do not set `"override"` are treated as new additions. A key collision with a base rule without `"override"` is an error.

Referencing an unknown base key in `"override"` is also an error.

Example:

```json
{
  "rules": [
    {
      "key": "gastronomy_1",
      "name": "Migros Take-Away",
      "transaction_category": "Expense",
      "category": "Freizeit",
      "subcategory": "Gastronomie",
      "priority": 5,
      "scope": {
        "transaction_type": "Debit",
        "transaction_type_detail": "Purchase/Service",
        "services": ["Card Purchase"],
        "providers": ["Apple Pay"],
        "notification_filters": {
          "merchants": ["MIGROS"],
          "locations": [],
          "counterparties": [],
          "counterparty_ibans": [],
          "include_keywords": ["TAKE AWAY"],
          "exclude_keywords": []
        }
      }
    }
  ]
}
```

### Matching behavior

- Rules in `rules.json` can be kept sorted by `key` for readability; at runtime the engine evaluates them by descending `priority`.
- `transaction_category` is required and must be one of: `Income`, `Expense`, `Refund`, `Transfer`.
- Category assignment uses two levels: `category` and `subcategory`.
- `category`/`subcategory` mapping is optional per rule (empty values are allowed).
- `priority` is a required integer from 1 to 10. Use `5` as the default "medium" value.
- `scope.transaction_type` filters on money direction: `Credit` or `Debit`.
- `scope.transaction_type_detail` can optionally filter on parsed detail (for example `Send Money`, `Purchase/Service`, `Standing Order`). Use `null` (or empty) to disable this filter.
- `scope.services` filters by parsed `service_type` and `scope.providers` optionally by payment provider.
- `scope.notification_filters` contains parsed-field matching criteria (`merchants`, `locations`, `counterparties`, `counterparty_ibans`, `include_keywords`, `exclude_keywords`).
- A rule matches only if all configured conditions match.
- `merchants`: OR logic (at least one must match).
- `locations`: AND logic (all must match).
- `counterparties`: OR logic (at least one must match the parsed counterparty).
- `counterparty_ibans`: OR logic with exact IBAN match (spaces ignored).
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

1. Put a new CSV into `data/private/input/`.
2. Run `uv run python categorize_transactions.py private --debug` to process the private dataset and see detailed matching diagnostics.
3. Inspect `data/private/output/*.categorized.csv`.
4. Add/refine parser(s) in `src/notification/parsers/` if needed.
5. Add/refine private rules in `data/private/rules.json`.
6. Decide explicitly for each new/changed rule whether it should stay private or be added/updated in `data/reference/rules.json` as a generic baseline improvement.
7. Repeat until categorization quality is acceptable.

### Private override rules with version control

If you keep personal data and local overlays in `data/private`, there are two practical ways to version them without storing them in the public repository.

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

- If `rules.json` has no `base`, it is a standalone ruleset.
- If `rules.json` contains `"base": "reference"`, `data/reference/rules.json` is loaded first.
- Replacements are explicit via `"override": "<base_key>"`; rules without `override` are additions.
