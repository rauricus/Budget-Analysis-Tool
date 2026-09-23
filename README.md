# 📊 Budget Tool

Automatic categorization of bank transactions using configurable JSON rules.

Project documentation:

- [STATUS.md](STATUS.md) — what the tool does today and where it stands (IST)
- [ROADMAP.md](ROADMAP.md) — planned next steps towards an actual budget (SOLL)
- [AGENTS.md](AGENTS.md) — architecture, invariants and conventions for contributors and agents

## Features

- CSV import (PostFinance format)
- Service-specific parser registry (card purchases incl. provider, card and online-shopping refunds, cash withdrawals, credit transfers, account transfers, Twint, Lastschrift variants, foreign payments, bank fees)
- Rule engine with priority-based matching (1-10; 1: lowest, 10: highest)
- Stable transaction IDs via persistent fingerprint registry
- Service/provider-scoped rule selection (`services` + optional `providers` in rules)
- Merchant, location, counterparty, IBAN and include/exclude keyword matching
- Optional validity window per rule (`valid_from` / `valid_to`) for rules that apply only during a defined period
- Transaction-level overrides by transaction ID
- Structured CSV export with parsed service fields
- Aggregated Excel analysis across all categorized months of a dataset
- Budget vs. actual comparison per category (minimal first version, see below)

### CSV locale support (current)

- Import and export are currently aligned to German PostFinance CSV conventions.
- Import reads six German source columns from PostFinance: `Datum`, `Avisierungstext`, `Gutschrift in CHF`, `Lastschrift in CHF`, `Label` and `Kategorie`. Which of the two amount columns is filled decides the transaction direction; `Label` and `Kategorie` are only carried through to the export. Every other column of a PostFinance export, `Bewegungstyp` among them, is ignored. The one exception is a warning: if `Bewegungstyp` ever holds something other than `Buchung`, the row is probably not a booking — a reservation, say — and import says so, because the pipeline would otherwise categorize and count it like any other transaction.
- Columns are read defensively rather than validated: a row without `Datum` is skipped and any other missing field falls back to empty or zero, so a CSV with an unexpected column layout imports quietly instead of failing.
- Export preserves German transaction content (for example Lastschrift/Zahlung/Dauerauftrag details) in parsed fields.

## Setup

Requires Python 3.9 (see `pyproject.toml`).

```bash
# Install uv (one-time, outside project)
brew install uv

# Create/update local virtual environment from pyproject.toml
uv sync

# Optional: activate the local virtual environment in your shell
source .venv/bin/activate
# If `.venv` is active, commands work without the `uv run` prefix,
# e.g. `python categorize_transactions.py example` or `pytest -q`
```

## Datasets

A **run dataset** is any directory that contains a `rules.json` and an `input/` folder.
All CLI tools take such a directory as their first argument, either as a path
(`data/example`) or as a shorthand resolved under `data/` (`example`).

A dataset directory can hold:

```text
<run_dir>/
├── rules.json                       # required; standalone or overlay (see "Rules")
├── transaction_overrides.json       # optional; per-transaction corrections
├── input/                           # required; source CSV files
├── output/                          # generated categorized CSVs + Excel report
└── metadata/                        # generated
    ├── transaction_id_registry.json # transaction fingerprint -> ID mapping
    └── months.json                  # processed month periods
```

Datasets in this repository:

- `data/example` — canonical standalone dataset for tests and documentation. May contain synthetic/fictive merchants and counterparties. Keep it stable and reproducible.
- `data/reference` — global baseline rules for overlay datasets (`data/reference/rules.json`). Not runnable on its own; it has no `input/`.
- `data/private` — gitignored space for personal datasets. Its layout is up to you: put one run dataset directly inside it, or group several (for example per year) as `data/private/<name>/`. Every such directory follows the structure above and is addressed by its own path.

Decision guide for changes:

- New parser behavior examples, test fixtures, and documentation examples → `data/example`.
- Generic rule improvements intended for everyone → `data/reference/rules.json`.
- Personal or sensitive categorization logic → your private dataset's `rules.json`.

Repository policy:

- Tests and docs depend on `data/example`, never on `data/reference` or private data.
- Never commit personal data from `data/private` to the public repository.

## Usage

### Categorize transactions

```bash
# Run the pipeline for a dataset (all input/*.csv files)
uv run python categorize_transactions.py example

# Detailed matching diagnostics (recommended while refining rules)
uv run python categorize_transactions.py example --debug

# Process only one CSV file from the dataset input/ folder
uv run python categorize_transactions.py example --input-file export.202503.csv

# Reuse original input CSV categories for otherwise uncategorized rows
uv run python categorize_transactions.py example --use-input-category-fallback

# Continue even if transaction_overrides.json contains unknown IDs
uv run python categorize_transactions.py example --ignore-unknown-overrides
```

### Explain a rule match

```bash
# Explain rule matching for one transaction (select by source CSV line).
# Use --input-file to scope the line lookup when several input files exist.
uv run python explain_rule_match.py example --input-file export.202503.csv --line-number 42

# Explain one specific rule in detail for the same transaction
uv run python explain_rule_match.py example --input-file export.202503.csv --line-number 42 --rule-id groceries_1

# Select by transaction ID and get JSON output
uv run python explain_rule_match.py example --transaction-id TX-000123 --json

# Ignore overlay rules and evaluate only base rules
uv run python explain_rule_match.py example --line-number 9 --no-overlays
```

Further options: `--no-overrides` (ignore `transaction_overrides.json` for the final decision)
and `--max-non-matching N` (how many non-matching candidate rules to include; default 5).

### Migrate override IDs

```bash
# Suggest old->new transaction ID remapping for transaction_overrides.json
# (useful after resetting/regenerating transaction IDs)
uv run python suggest_override_ids.py example
```

Options: `--limit N` (max candidate rows per entry; default 3) and `--debug`.

### Analysis

After categorizing, generate an Excel report. The script discovers all
`*.categorized.csv` files in the dataset's `output/` folder and aggregates them into one
report. It requires `metadata/months.json`, which `categorize_transactions.py` writes.

```bash
# Write to <run_dir>/output/dataset.analysis.xlsx
uv run python analyze_by_category.py example

# Specify a custom output file
uv run python analyze_by_category.py example my_analysis.xlsx
```

The generated Excel file contains four sheets:

- **Summary** — income vs. expenses vs. refunds across the whole dataset, with a stacked bar chart. Transfers are reported separately.
- **Overviews by category** — income, expense and refund totals per category, each with a pie chart.
- **Category Analysis** — one table per processed month, broken down by category.
- **Subcategory Analysis** — one table per processed month, broken down by category and subcategory.

The Excel format lets you modify charts, add custom analysis, and adjust formatting.

### Budget vs. actual

If a dataset has a `budget.json`, `budget_report.py` compares its target values against
the categorized actuals and prints the result as a table.

```bash
# Report the dataset's last month
uv run python budget_report.py example

# Report a specific month
uv run python budget_report.py example --month 2025-03
```

The table shows target, actual, variance in CHF and in percent per category, plus the
same three figures cumulated over the dataset's months up to and including the reported
one. Two lists follow it: categories with actuals but no budget line, and budget lines
with no actuals at all — the latter is also where a mistyped category surfaces.

This is a deliberately minimal first version. See [ROADMAP.md](ROADMAP.md) for what it
does not do yet.

### Tests

```bash
uv run pytest -q                        # all tests
uv run pytest -v                        # verbose
uv run pytest tests/test_rule_matching.py
```

## Data flow

```text
<run_dir>/input/*.csv
   -> ImportHandler.load_csv
   -> TransactionParser.parse_row
   -> NotificationTextParser.parse (via parser registry)
   -> TransactionIdRegistry.assign_batch
   -> optional strict validation of transaction_overrides.json IDs
   -> RuleEngine.categorize_batch
   -> optional TransactionOverrides.apply (hidden/category transaction overrides)
   -> ExportHandler.export_csv
   -> <run_dir>/output/*.categorized.csv
```

During the run, transaction IDs are assigned and persisted in
`<run_dir>/metadata/transaction_id_registry.json`, and the processed month periods are
written to `<run_dir>/metadata/months.json`.

IDs remain stable across reruns as long as the normalized transaction content (date,
type, notification text, credit/debit) and duplicate occurrence order remain unchanged.

## Structure

```text
data/
├── example/                          # Stable example dataset for tests/docs
│ ├── rules.json
│ ├── transaction_overrides.json
│ ├── budget.json                     # Optional: target values per category
│ ├── input/
│ ├── output/
│ └── metadata/
├── reference/                        # Global base rules for overlays (no input/)
│ └── rules.json
└── private/                          # Personal datasets (gitignored)

src/
├── import_handler.py                 # CSV import utilities
├── export_handler.py                 # Structured CSV export builder
├── models/                           # Domain model package
│ ├── transaction.py                  # Transaction dataclass
│ └── rule.py                         # Rule dataclass + matching logic
├── rule_engine.py                    # Rule loading + service/provider-filtered categorization
├── transaction_id_registry.py        # Stable transaction ID assignment + registry persistence
├── transaction_overrides.py          # transaction_overrides.json loading + validation + apply
├── override_id_remap.py              # old->new ID suggestion logic for override migration
├── transaction_parser.py             # Row-to-Transaction conversion
└── notification/
  ├── base.py                         # Parser interface + parse result model
  ├── facade.py                       # Public facade to parser registry
  └── parsers/
    ├── card_purchase_parser.py           # Card purchases (Purchase/Service, Purchase/Online Shopping, optional provider)
    ├── postfinance_card_refund_parser.py # Card refunds
    ├── online_shopping_refund_parser.py  # Online shopping refunds (credit counterpart of e-finance purchases)
    ├── efinance_purchase_parser.py       # E-Finance purchases
    ├── cash_withdrawal_parser.py         # Cash withdrawals (Bargeldbezug)
    ├── credit_transfer_parser.py         # Credit transfers (Gutschrift Auftraggeber/Absender)
    ├── account_transfer_parser.py        # Transfers between own accounts
    ├── bank_package_fee_parser.py        # Bank package fees
    ├── twint_send_parser.py              # Twint send money
    ├── twint_receive_parser.py           # Twint receive money
    ├── twint_purchase_parser.py          # Twint purchases
    ├── debit_direct_parser.py            # CH-DD debit direct
    ├── payment_parser.py                 # Lastschrift payments
    ├── standing_order_parser.py          # Lastschrift standing orders
    └── foreign_payment_parser.py         # Foreign payments (Auslandzahlung, for example SEPA)

categorize_transactions.py            # Pipeline entry point
explain_rule_match.py                 # CLI helper to explain rule matching per transaction
suggest_override_ids.py               # CLI helper for override ID remapping
analyze_by_category.py                # Excel report generator
budget_report.py                      # Budget vs. actual comparison (console)
tests/                                # Unit/integration-style tests for pipeline components
```

## Parsed services

Parsers normalize the notification text into a `Service` value and an optional
`Transaction Type Detail`. Rules match on these fields.

The registry tries its parsers in a fixed order and the first parser that claims a
notification text wins, so a narrow format has to be registered before a broader one.

| Service | Transaction Type Detail (examples) |
|---|---|
| `Card Purchase` | `Purchase/Service`, `Purchase/Online Shopping`, `Refund/Online Shopping` |
| `PostFinance Card Refund` | `Refund` |
| `Cash Withdrawal` | `Cash Withdrawal` |
| `Credit` | `Credit` |
| `Account Transfer` | `Account Transfer Auf` (outgoing), `Account Transfer Von` (incoming) |
| `Direct Debit` | `Payment`, `Standing Order`, `Direct Debit (CH-DD)`, `Foreign Payment` |
| `Twint` | `Send Money`, `Receive Money`, `Purchase/Service`, `Purchase/Online Shopping` |
| `Fees` | `Bank Package Fee` |

`scope.transaction_type_detail` is compared exactly, so these values have to be spelled as
listed. `Account Transfer Auf` / `Account Transfer Von` carry the German direction word
through from the source text, unlike the other details.

## Rules

`data/example/rules.json` is the standalone example rule set used for tests and documentation.
`data/reference/rules.json` is the shared baseline for overlay-based datasets.
A private dataset's `rules.json` is typically an overlay on `reference` and is not committed.

Each rule has a required string `key`. Keys must be unique within a file.
Recommended format: `group_number` (for example `gastronomy_1`, `transport_2`).

### Standalone vs. overlay datasets

A `rules.json` file can declare a dependency on another dataset's rules via a top-level `"base"` field:

```json
{ "base": "reference", "rules": [] }
```

When `"base"` is set, the named dataset's `rules.json` (resolved as `data/<base>/rules.json`)
is loaded first, and the current file is applied as an overlay on top. Without `"base"`, the
file is treated as a complete standalone rule set.

### Replacing a base rule via overlay

An overlay rule that replaces a base rule must declare `"overlay_of": "<base_key>"` and carry
its own unique `key`. At runtime, the engine matches by the base key internally while retaining
the overlay rule's declared key and source for explain/debug output.

```json
{
  "key": "income_1_dev",
  "overlay_of": "income_1",
  "name": "Lohn: Meine Firma"
}
```

Rules that do not set `"overlay_of"` are treated as new overlay additions. A key collision with
a base rule without `"overlay_of"` is an error, as is referencing an unknown base key.

### Rule example

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
        "valid_from": null,
        "valid_to": null,
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
- Category assignment uses two levels: `category` and `subcategory`. Both are optional per rule (empty values are allowed).
- `priority` is a required integer from 1 to 10. Use `5` as the default "medium" value.
- `scope.transaction_type` filters on money direction: `Credit` or `Debit`.
- `scope.transaction_type_detail` optionally filters on the parsed detail (for example `Send Money`, `Purchase/Service`, `Standing Order`). Use `null` (or empty) to disable this filter.
- `scope.valid_from` and `scope.valid_to` optionally restrict a rule to a date range (ISO `YYYY-MM-DD`, both bounds inclusive). Either bound may be omitted for an open-ended window. Omit both (or use `null`) to make the rule apply to every date.
- `scope.services` filters by parsed service and `scope.providers` optionally by payment provider.
- `scope.notification_filters` contains parsed-field matching criteria (`merchants`, `locations`, `counterparties`, `counterparty_ibans`, `include_keywords`, `exclude_keywords`).
- A rule matches only if all configured conditions match.
- Empty filters behave like wildcards: if a field is unset, `null`, `""`, or `[]` (depending on the field), that field does not restrict matching. A rule whose filters are all empty therefore matches every transaction of its service and is decided by priority alone — deliberate catch-alls should sit at priority 1.

Per-field logic:

| Field | Logic |
|---|---|
| `transaction_type`, `transaction_type_detail` | exact match |
| `valid_from`, `valid_to` | inclusive date range; transaction date must fall inside |
| `services`, `providers` | OR within the list, exact match per entry |
| `merchants`, `counterparties` | OR (at least one must match) |
| `counterparty_ibans` | OR, exact IBAN match (spaces ignored) |
| `locations`, `include_keywords` | AND (all must match) |
| `exclude_keywords` | negative filter (none may match) |

Across different fields, checks are cumulative: every configured field must pass for the rule to match.

Note the asymmetry within the fields: one entry from `merchants` or `counterparties` is
enough, while *all* entries of `locations` and `include_keywords` must be present. A rule
with two include keywords therefore stops matching as soon as a creditor rewords half of
its reference. `explain_rule_match.py` reports which logic applies per field, as
`expected_any` versus `expected_all`.

### No fallback category

There is no fallback category in the engine. If no parser matches a service or no rule matches
that service, the transaction stays uncategorized.

For export compatibility only, `categorize_transactions.py` can optionally reuse the original
input CSV category via `--use-input-category-fallback`.

## Transaction overrides

Transaction-level overrides live in `transaction_overrides.json` in the run dataset directory.

This mechanism is separate from rule overlays in `rules.json`:

- Transaction overrides post-process one specific transaction by transaction ID.
- Rule overlays extend or replace rules from a base dataset.

Supported fields per transaction ID entry:

```json
{
  "TX-000042": {
    "hidden": true,
    "transaction_category": "Expense",
    "category": "Freizeit",
    "subcategory": "Kultur",
    "_note": "optional comment explaining why this override exists",
    "_row": "optional raw row hint for future ID remapping"
  }
}
```

Behavior and constraints:

- `hidden: true` removes the transaction from export.
- `transaction_category`, `category`, `subcategory` override automatic categorization values for that transaction ID.
- `_row` is optional metadata that helps remap old IDs after registry resets; it does not affect categorization.
- `_note` is optional free text documenting the reason for the override, for example the rule it belongs with; it does not affect categorization.
- A `transaction_overrides.json` file is only valid in the top-level run dataset. One in a referenced base dataset (declared via `"base"`) is rejected.
- If an override references an unknown transaction ID, `categorize_transactions.py` fails fast by default. Opt into warning-only behavior with `--ignore-unknown-overrides`.

When unknown override IDs are detected, use `suggest_override_ids.py` (see above). It suggests
old->new ID mappings based on `_row` hints and current input files.

## Budget

A dataset may carry a `budget.json` next to its `rules.json`. It holds one target value per
category:

```json
{
  "Wohnen": { "amount": 1900.00, "period": "monthly" },
  "Finanzen": { "amount": 2400.00, "period": "yearly", "_note": "Versicherungen und Gebühren" }
}
```

- Keys are categories exactly as the rule set produces them.
- `amount` is a number, `period` is `monthly` or `yearly`. A yearly amount is compared
  pro rata, one twelfth per month, with the cumulated columns showing whether the year as
  a whole is on track.
- `_note` is optional free text and does not affect the comparison.
- Unknown fields are rejected at load time.

How actuals are derived:

- **Refunds are netted.** A category's actual is its debits minus its credits, so a refund
  that carries the expense category it belongs to (`Leben` / `Gesundheit`, say) reduces
  that category. A refund caught by a catch-all rule keeps its own category
  (`Rückerstattungen`) and appears as a line without a budget, which is the right signal:
  it could not be attributed.
- **Income and transfers are excluded.** Only spending is budgeted.
- Rows that no rule categorized stay visible under `Uncategorized`.

There is no validation against `rules.json`. A category that does not exist simply shows
up under "Ohne Ist-Werte" with an actual of zero, which surfaces a typo just as clearly.

Budget files follow the same privacy rule as the rest of a dataset: `data/example/budget.json`
holds fictitious amounts for documentation and tests, real target values belong in
`data/private/`.

## Export format

The structured export uses these columns:

`Transaction ID`, `Date`, `Transaction Type`, `Transaction Type Detail`, `Service`,
`Provider`, `Card Number`, `Merchant`, `Location`, `Counterparty`, `Counterparty IBAN`,
`Reference`, `Credit in CHF`, `Debit in CHF`, `Label`, `Transaction Category`, `Category`,
`Subcategory`, `Matched Rule Key`, `Matched Rule Source`

## Iterative workflow

1. Put a new CSV into your dataset's `input/` folder.
2. Run `uv run python categorize_transactions.py <run_dir> --debug` and watch for warnings about missing parsers and uncategorized transactions.
3. Inspect `<run_dir>/output/*.categorized.csv`.
4. Add/refine parser(s) in `src/notification/parsers/` if a notification text is not parsed.
5. Add/refine rules in your dataset's `rules.json`.
6. Decide explicitly for each new/changed rule whether it stays private or belongs in `data/reference/rules.json` as a generic baseline improvement.
7. Repeat until categorization quality is acceptable, then run `analyze_by_category.py`.

Three skills in `.agents/skills/` support this loop: `fix-uncategorized-transactions`,
`update-rules-to-categorise-additional-entry`, and `handle-no-notification-parser-warnings`.

### Versioning private data

`data/private` is gitignored. Two practical ways to version it anyway:

**Approach A (recommended): nested private Git repository in `data/private`**

```bash
cd data/private
git init
git remote add origin <private-remote-url>
git add .
git commit -m "Initial private dataset"
git push -u origin main
```

**Approach B: separate private repository outside this project**

Keep the private repository elsewhere on disk and link `data/private` (or a single dataset
directory inside it) to that location. Use this when you prefer strict repository separation.

Both approaches work with the overlay mechanism: a private `rules.json` with
`"base": "reference"` loads `data/reference/rules.json` first and applies the private rules
on top.
