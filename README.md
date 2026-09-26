# 📊 Budget Tool

Categorizes bank transactions with configurable JSON rules, reports them in Excel, and
compares them against a budget. Local and offline.

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
- Optional exact-amount filter per rule (`amounts`) for transactions that differ in nothing but their amount
- Transaction-level overrides by transaction ID, including splitting one booking across categories
- Rule notes and review questions, and a read-only `doctor.py` listing what in a dataset needs attention
- Structured CSV export with parsed service fields
- Excel report across all categorized months, with every transaction and the top payees
- Budget vs. actual per category or subcategory, with reserves set aside from planned income

### CSV locale support (current)

- Import and export follow the German PostFinance CSV layout.
- Import reads `Datum`, `Avisierungstext`, `Gutschrift in CHF`, `Lastschrift in CHF`, `Label`
  and `Kategorie`. The filled amount column decides the direction; `Label` and `Kategorie`
  are only carried through. Other columns are ignored, except that a `Bewegungstyp` other
  than `Buchung` triggers a warning: such a row is probably not a booking.
- Columns are read defensively: a row without `Datum` is skipped, other missing fields fall
  back to empty or zero.

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
├── rules.<topic>.json               # optional; more rules of the same set (see "Splitting rules across files")
├── transaction_overrides.json       # optional; per-transaction corrections
├── input/                           # required; source CSV files
├── output/                          # generated categorized CSVs + Excel report
└── metadata/                        # generated
    ├── transaction_id_registry.json # transaction fingerprint -> ID mapping
    └── months.json                  # processed month periods
```

Datasets in this repository:

- `data/example` — canonical standalone dataset for tests and documentation. May contain synthetic/fictive merchants and counterparties. Keep it stable and reproducible.
- `data/reference` — global baseline rules for overlay datasets (`data/reference/rules.json` plus `rules.<topic>.json`). Not runnable on its own; it has no `input/`.
- `data/private` — gitignored space for personal datasets. Its layout is up to you: put one run dataset directly inside it, or group several (for example per year) as `data/private/<name>/`. Every such directory follows the structure above and is addressed by its own path.

Decision guide for changes:

- New parser behavior examples, test fixtures, and documentation examples → `data/example`.
- Generic rule improvements intended for everyone → the fitting rule file in `data/reference`.
- Personal or sensitive categorization logic → the fitting rule file of your private dataset.

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

### Check a dataset (doctor)

```bash
# List what needs attention; writes nothing to output/ or metadata/
uv run python doctor.py example

# Same report as JSON
uv run python doctor.py example --json
```

The doctor categorizes the dataset in memory and reports:

- **Input:** input files that overlap (the same booking in two files gets the same ID and is
  exported and counted twice), and calendar months without any transaction between the
  first and the last one.
- **Stale output:** rows in `output/*.categorized.csv` whose category differs from what the
  current rules and overrides give, transactions missing from `output/`, output rows
  without a transaction, and a `metadata/months.json` that does not list exactly the input
  months (a run with `--input-file` rewrites it with that file's months only). The reports
  read these files, not the rules: rerun the pipeline before them.
- **To review:** transactions won by a rule with a `review` question (see
  [Notes and review questions](#notes-and-review-questions)), dated after its
  `reviewed_until` and without an override. Grouped by rule, with question and note.
- **Uncategorized:** every transaction left without a category after overrides.
- **Rules** of the dataset itself (base rules are left out, a baseline naturally has rules a
  dataset never uses): rules that never match, with a hint when they belong to another
  period (validity window outside the data, or a year in key or name the data does not
  cover); rules that match but always lose to a higher-priority rule, with the winner;
  `amounts` entries that no transaction matches; a `reviewed_until` after the end of the
  last month with data, which would mark later imports as reviewed unseen.
- **Equal-priority ties:** transactions where the two best matching rules, from any layer,
  share a priority but differ in result, so that load order decides.
- **Overrides:** unknown IDs; a `_row` hint that does not fit its transaction (other date,
  or most of its words missing from the row), which means IDs have shifted and the override
  now hits another booking; overrides that change nothing (only what the rule already
  assigns, or only a `_note`); overrides without `_row`, which the remap helper cannot follow.

Exit code 0 means no findings, 1 findings, 2 an error loading the dataset.

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

The generated Excel file contains six sheets:

- **Summary** — income vs. expenses vs. refunds across the whole dataset, with a stacked bar chart. Transfers are reported separately.
- **Overviews by category** — income, expense and refund totals per category, each with a pie chart.
- **Category Analysis** — one table per processed month, broken down by category.
- **Subcategory Analysis** — one table per processed month, broken down by category and subcategory.
- **Transactions** — every transaction as one filterable row: ID, date, month, transaction
  category, category, subcategory, `Category / Subcategory`, payee, reference, credit, debit,
  amount, rule and source file. `Amount` is debit minus credit, as in the budget report, so
  a filtered sum matches the actual there.
- **Top Payees** — the ten largest payees per subcategory, net of refunds, without income
  and transfers; the rest is folded into `(übrige)`. Payees are the merchant, else the
  counterparty, else the reference, grouped without branch numbers and sender references.

All figures are computed by the script and written as values; Excel only displays them.
Before writing, the script reconciles every summary table with the transactions and aborts
on a difference. Each table also ends with `Total`, `Check (Transactions)` — a `SUMIFS` over
the Transactions sheet with the table's criteria — and `Difference`, which should read 0.00.
In the category overviews a difference equals the categories left out of the pie chart
(net zero or negative). Viewers that do not calculate, such as the macOS preview, leave the
check cells empty.

Edits in the workbook are lost when the report is regenerated; lasting corrections belong
in the rules or in `transaction_overrides.json`.

### Budget vs. actual

If a dataset has a `budget.json`, `budget_report.py` compares its target values against
the categorized actuals and prints the result as a table.

```bash
# Report the dataset's last month
uv run python budget_report.py example

# Report a specific month
uv run python budget_report.py example --month 2025-03

# Compare the same actuals against another budget file, e.g. a draft for next year
uv run python budget_report.py example --budget budget-2027.json
```

`--budget` replaces `<run_dir>/budget.json` for this run. A relative path is looked up from
the current directory first, then inside the dataset directory, so a draft kept next to
`budget.json` can be named by file name alone. The report header names the file it used.

The report has up to three parts:

- **Availability** (with an `income`): planned and actual income, minus reserves, minus
  budget lines, and what is left unplanned.
- **Reserves** (with `reserves`): target, actual, cumulated values and the pot balance.
- **Budget lines**: target, actual and variance for the month and cumulated over the
  dataset's months, followed by categories without a line and lines without actuals —
  the latter is where a mistyped category surfaces.

The file format is described under [Budget](#budget).

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
   -> optional TransactionOverrides.apply (hidden/category/split transaction overrides)
   -> ExportHandler.export_csv
   -> <run_dir>/output/*.categorized.csv
```

Transaction IDs are persisted in `metadata/transaction_id_registry.json` and stay stable
across reruns as long as date, direction, notification text and amounts of a transaction do
not change. Processed months are written to `metadata/months.json`.

## Structure

```text
data/
├── example/                          # Stable example dataset for tests/docs
│ ├── rules.json
│ ├── transaction_overrides.json
│ ├── budget.json                     # Optional: income, reserves, budget lines
│ ├── input/
│ ├── output/
│ └── metadata/
├── reference/                        # Global base rules for overlays (no input/)
│ ├── rules.json
│ └── rules.<topic>.json              # ferien, gastro, einkaufen, wohnen, ...
└── private/                          # Personal datasets (gitignored)

src/
├── import_handler.py                 # CSV import
├── transaction_parser.py             # Row -> Transaction
├── notification/                     # Parser interface, registry, one parser per service
├── transaction_id_registry.py        # Stable transaction IDs
├── rule_engine.py                    # Rule loading, overlays, categorization
├── models/                           # Transaction and Rule (incl. matching logic)
├── transaction_overrides.py          # transaction_overrides.json handling
├── override_id_remap.py              # Old -> new ID suggestions
└── export_handler.py                 # Categorized CSV export

categorize_transactions.py            # Pipeline entry point
explain_rule_match.py                 # CLI helper to explain rule matching per transaction
doctor.py                             # CLI helper listing what in a dataset needs attention
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

Each rule has a required string `key`. Keys must be unique within a dataset's rule files.
Recommended format: `group_number` (for example `gastronomy_1`, `transport_2`).

### Standalone vs. overlay datasets

A `rules.json` file can declare a dependency on another dataset's rules via a top-level `"base"` field:

```json
{ "base": "reference", "rules": [] }
```

When `"base"` is set, the named dataset's rules (resolved as `data/<base>/`) are loaded first,
and the current dataset's rules are applied as an overlay on top. Without `"base"`, the
dataset's rules are treated as a complete standalone rule set.

### Splitting rules across files

Besides `rules.json`, a dataset may hold any number of `rules.<topic>.json` files, for example
`rules.ferien.json`, `rules.gastro.json` or `rules.wohnen.json`. They are discovered
automatically and loaded together with `rules.json` as one rule set:

- `rules.json` stays required; it is the only file that may declare `"base"`.
- Each file has the same shape, `{ "rules": [...] }`.
- Keys must be unique across all files of the dataset; a duplicate is an error that names
  both files.
- The split applies to both layers: a base dataset such as `data/reference` is split the same
  way, and `"overlay_of"` in any overlay file may target a rule in any base file.
- Which file a rule lives in is organization only. The engine evaluates by `priority`; files
  are read in a fixed order (`rules.json`, then the others alphabetically) only so that runs
  are reproducible. Do not rely on that order to break ties between two matching rules with
  the same priority — give the intended winner a higher priority or exclude the other.

`--debug` and `explain_rule_match.py` show the file each rule comes from.

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
        "amounts": [],
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

- Rules can be kept sorted by `key` for readability; at runtime the engine evaluates them by descending `priority`, across all rule files.
- `transaction_category` is required and must be one of: `Income`, `Expense`, `Refund`, `Transfer`.
- Category assignment uses two levels: `category` and `subcategory`. Both are optional per rule (empty values are allowed).
- `priority` is a required integer from 1 to 10. Use `5` as the default "medium" value.
- `scope.transaction_type` filters on money direction: `Credit` or `Debit`.
- `scope.transaction_type_detail` optionally filters on the parsed detail (for example `Send Money`, `Purchase/Service`, `Standing Order`). Use `null` (or empty) to disable this filter.
- `scope.valid_from` and `scope.valid_to` optionally restrict a rule to a date range (ISO `YYYY-MM-DD`, both bounds inclusive). Either bound may be omitted for an open-ended window. Omit both (or use `null`) to make the rule apply to every date.
- `scope.amounts` optionally restricts a rule to exact amounts in CHF, compared without sign (direction is `transaction_type`'s job). Meant for the case where nothing but the amount tells two transactions apart, such as two standing orders from the same account. It breaks as soon as the amount changes, so pair it with a validity window where the amount is known to change.
- `scope.services` filters by parsed service and `scope.providers` optionally by payment provider.
- `scope.notification_filters` contains parsed-field matching criteria (`merchants`, `locations`, `counterparties`, `counterparty_ibans`, `include_keywords`, `exclude_keywords`).
- A rule matches only if all configured conditions match.
- Empty filters behave like wildcards: if a field is unset, `null`, `""`, or `[]` (depending on the field), that field does not restrict matching. A rule whose filters are all empty therefore matches every transaction of its service and is decided by priority alone — deliberate catch-alls should sit at priority 1.

Per-field logic:

| Field | Logic |
|---|---|
| `transaction_type`, `transaction_type_detail` | exact match |
| `valid_from`, `valid_to` | inclusive date range; transaction date must fall inside |
| `amounts` | OR, exact amount to the cent, sign ignored |
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

### Notes and review questions

Three optional top-level rule fields document a rule and mark its matches for review. None
of them affects matching; `doctor.py` reads them.

```json
{
  "key": "health_2_private",
  "overlay_of": "health_2",
  "_note": "Direct debits do not name the insured person; the child's amounts have their own rule.",
  "review": "Is this the child's cost share? Then add the amount to kk_child_2026.",
  "reviewed_until": "2026-08-31",
  ...
}
```

- `_note`: free text on why the rule exists and how to maintain it. Shown with review items.
- `review`: a question to ask about every transaction the rule wins. Meant for a default
  rule behind which a case sometimes needs another rule or an override.
- `reviewed_until`: ISO date; wins up to and including it count as reviewed. Move it forward
  after each review. Requires `review`.

A transaction with an override never shows up for review: the override is the decision.

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
- `split` divides the transaction into parts, each with its own category (see below).
- `_row` is optional metadata that helps remap old IDs after registry resets; it does not affect categorization.
- `_note` is optional free text documenting the reason for the override, for example the rule it belongs with; it does not affect categorization.
- A `transaction_overrides.json` file is only valid in the top-level run dataset. One in a referenced base dataset (declared via `"base"`) is rejected.
- If an override references an unknown transaction ID, `categorize_transactions.py` fails fast by default. Opt into warning-only behavior with `--ignore-unknown-overrides`.

When unknown override IDs are detected, use `suggest_override_ids.py` (see above). It suggests
old->new ID mappings based on `_row` hints and current input files.

### Splitting a transaction

A booking that covers several things, such as a supermarket receipt with household goods,
can be split so that each part lands in its own category:

```json
{
  "TX-000048": {
    "split": [
      { "amount": 18.90, "category": "Wohnen", "subcategory": "Haushalt" },
      { "category": "Einkaufen", "subcategory": "Supermärkte" }
    ],
    "_row": "24.03.2025;Buchung;..."
  }
}
```

- Each part takes `category` (required), `subcategory`, `transaction_category`, `amount` and
  `_note`. A part without `transaction_category` keeps the transaction's.
- Amounts are positive CHF on the transaction's side (debit or credit). Exactly one part
  omits `amount` and receives the remainder; the given amounts must leave a remainder above
  zero, otherwise the run aborts.
- The export writes one row per part, with the ID suffixed in list order: `TX-000048.1`,
  `TX-000048.2`. All other columns, including the matched rule, are copied from the
  original row. The override key itself stays the unsuffixed ID.
- `split` cannot be combined with `hidden`. Top-level `transaction_category`, `category` and
  `subcategory` are applied first.
- The Excel report and the budget treat the parts as ordinary rows, so "Top Payees" counts a
  split transaction once per part.

`data/example` splits `TX-000048` into two and `TX-000076` into three parts.

## Budget

A dataset may carry a `budget.json` next to its `rules.json`. It has up to three sections,
each optional:

```json
{
  "income": { "amount": 4200.00, "period": "monthly", "_note": "Nettolohn" },
  "reserves": {
    "Krankenkasse": {
      "amount": 3600.00, "period": "yearly",
      "category": "Leben", "subcategory": "Krankenkasse"
    }
  },
  "budget": {
    "Wohnen": { "amount": 1900.00, "period": "monthly" },
    "Leben": { "amount": 250.00, "period": "monthly" }
  }
}
```

- **`income`** is the planned income the rest is measured against. Without it the report
  skips the availability block.
- **`reserves`** set money aside for known costs before anything else is distributed —
  health insurance premiums and deductible, projected taxes, pension contributions. Keys
  are free names; `category` is required and `subcategory` optional. Each reserve is a
  pot: its target accrues month by month, the transactions it covers draw on it, and the
  report shows the balance.
- **`budget`** distributes what is left, one target per line. A key is a category exactly
  as the rule set produces it (`Freizeit`), or a category and subcategory separated by
  ` / ` (`Freizeit / Gastronomie`) — the same shape as the `Category / Subcategory` column in
  the Excel report. A subcategory line takes its transactions out of the category line, so
  `Freizeit` then stands for Freizeit without Gastronomie. A category with only subcategory
  lines lists its remaining transactions under "Ohne Budgetzeile". The spaces around the
  slash are required: `Einkaufen / Bücher/Filme/Musik` is category `Einkaufen`,
  subcategory `Bücher/Filme/Musik`.

Every entry has an `amount` (a number) and a `period` (`monthly` or `yearly`), and may have
an optional `_note` that does not affect anything. A yearly amount counts one twelfth per
month, with the cumulated columns showing whether the year as a whole is on track. Unknown
fields and unknown sections are rejected at load time.

Reserves and budget lines never share a transaction:

- A transaction matching a reserve counts against that reserve only, and leaves both the
  budget lines and the list of categories without a budget.
- A reserve on a subcategory takes precedence over one on the whole category. A reserve
  on `Leben` / `Krankenkasse` next to a budget line on `Leben` is fine: the line then sees
  `Leben` without its health insurance.
- Two reserves on the same category and subcategory, a reserve and a budget line on the
  same subcategory, or a reserve on a whole category next to any budget line in that
  category, are rejected — the money would be planned twice.
- Two reserves on the same kind of transaction — premiums and deductible, say — need
  distinct subcategories from the rule set; otherwise use one reserve for both.

How actuals are derived:

- **Refunds are netted.** A category's actual is its debits minus its credits, so a refund
  that carries the expense category it belongs to (`Leben` / `Gesundheit`, say) reduces
  that category or reserve. A refund caught by a catch-all rule keeps its own category
  (`Rückerstattungen`) and appears as a line without a budget, which is the right signal:
  it could not be attributed.
- **Income is excluded from both.** It only feeds the actual-income line.
- **Transfers are excluded from budget lines, but count for reserves.** A pension payment
  often leaves the account as a transfer; if the rules give it the reserve's category, it
  draws on the reserve.
- Rows that no rule categorized stay visible under `Uncategorized`.

There is no validation against `rules.json`. A category that does not exist simply shows
up under "Ohne Ist-Werte" with an actual of zero, which surfaces a typo just as clearly.
A reserve on a mistyped category stays at an actual of zero in the reserves table.

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
5. Add/refine rules in the fitting rule file of your dataset (`rules.json` or a `rules.<topic>.json`).
6. Decide explicitly for each new/changed rule whether it stays private or belongs in `data/reference` as a generic baseline improvement.
7. Run `uv run python doctor.py <run_dir>` and work through its list: open review questions, rules that never match or never win, overrides that no longer fit.
8. Repeat until categorization quality is acceptable, then run `analyze_by_category.py`.

Three skills in `.agents/skills/` support this loop: `fix-uncategorized-transactions`,
`update-rules-to-categorise-additional-entry`, and `handle-no-notification-parser-warnings`.

### Versioning private data

`data/private` is gitignored. To version it, make it a Git repository of its own
(`cd data/private && git init`), or link it to a private repository elsewhere on disk. A
private `rules.json` with `"base": "reference"` works either way.
