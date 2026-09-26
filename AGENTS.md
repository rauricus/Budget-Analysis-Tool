# AGENTS

Working notes for agents in this repository. [README.md](README.md) is the user-facing
manual and stays the source of truth for CLI flags, the rule schema and the export format;
this file covers what an agent needs on top of that: how the code is put together, which
invariants must survive a change, and where the traps are.

- [STATUS.md](STATUS.md) — what the tool does today (IST), including known gaps.
- [ROADMAP.md](ROADMAP.md) — where it is going (SOLL).

## What this is

A local, offline Python tool that reads PostFinance CSV exports, parses each notification
text into structured fields, categorizes the transactions with JSON rules, writes a
categorized CSV per input file, aggregates everything into an Excel report, and compares the
actuals against a `budget.json` on the console. There is no server, no database and no
network access anywhere.

## Virtual environment for Python

- Use `uv` with a local `.venv` in this repository.
- Never create additional Python environments besides `.venv` for this project.
- Use `uv sync` to install/update dependencies from `pyproject.toml`.
- Prefer `uv run <command>` for scripts and tests.
- If activation is required in an interactive shell, use `source .venv/bin/activate`.

Python is pinned to `>=3.9,<3.10`; runtime dependencies are `pandas`, `openpyxl` and
`pytest`, all version-pinned in `pyproject.toml`.

## Commands

Always run from the repository root: dataset shorthands (`example`), a rules file's
`"base"` field and the tests' fixture paths all resolve relative to the current working
directory.

```bash
uv run pytest -q                                              # full suite, ~2s
uv run pytest tests/test_rule_matching.py                     # one module
uv run python categorize_transactions.py example --debug      # the main loop
uv run python categorize_transactions.py example --input-file export.202503.csv
uv run python explain_rule_match.py example --line-number 42  # why did/didn't a rule match
uv run python doctor.py example                               # what needs attention, read-only
uv run python suggest_override_ids.py example                 # after an ID registry reset
uv run python analyze_by_category.py example                  # Excel report
uv run python budget_report.py example --month 2025-03        # budget vs. actual
```

`--debug` on the pipeline is the primary diagnostic: it prints one line per source row with
the matched rule, its key and source file, and any override that was applied on top.
`explain_rule_match.py` is the second one — it breaks a single transaction down into the
individual checks a rule performs and shows which one failed. `doctor.py` looks at the whole
dataset instead: overlapping or missing input, output that no longer matches the rules,
open review questions, uncategorized rows, rules that never match, never win or tie, and
overrides whose `_row` no longer fits their ID. It writes nothing, so it is safe to
run against `data/example` and the private datasets.

Never point the pipeline at `data/example` while investigating something unrelated: it
rewrites that dataset's `output/` and `metadata/`, which are committed. Copy the dataset to
a scratch directory and pass that path instead — the run directory argument accepts any
path, not just a name under `data/`.

## Architecture

The pipeline is a straight line, with no shared state beyond the dataset directory:

```text
<run_dir>/input/*.csv
  → ImportHandler.load_csv            find header line, keep delimited rows, track line numbers
  → TransactionParser.parse_row       German columns → Transaction, amounts, date
  → NotificationTextParser.parse      registry of service parsers → structured fields
  → TransactionIdRegistry.assign_batch fingerprint → stable TX-NNNNNN
  → (strict validation of override IDs, fail-fast)
  → RuleEngine.categorize_batch       service/provider candidates → highest-priority match
  → TransactionOverrides.apply        per-ID corrections, drops hidden rows
  → ExportHandler.export_csv          20-column CSV
<run_dir>/output/*.categorized.csv → analyze_by_category.py → dataset.analysis.xlsx
<run_dir>/output/*.categorized.csv + budget.json → budget_report.py → console
```

Entry points live at the repository root, the library under `src/`:

| Path | Role |
|---|---|
| `categorize_transactions.py` | pipeline driver, dataset/rule resolution, debug report |
| `explain_rule_match.py` | per-transaction match diagnostics, text or `--json` |
| `doctor.py` | dataset-wide findings (reviews, dead rules, suspicious overrides), text or `--json`, read-only |
| `suggest_override_ids.py` | old→new ID suggestions after a registry reset |
| `analyze_by_category.py` | Excel report (summary, overviews, category, subcategory, transactions, top payees); owns `spending_rows` |
| `budget_report.py` | `budget.json` loading and validation, reserves, availability and budget vs. actual on the console |
| `src/import_handler.py` | CSV reading, header detection, per-row error reporting |
| `src/transaction_parser.py` | row → `Transaction`, PostFinance amount/date formats |
| `src/notification/` | parser interface, registry facade, one parser per service |
| `src/models/` | `Transaction` and `Rule` dataclasses; `Rule` owns the matching logic |
| `src/rule_engine.py` | rule file discovery (`resolve_rule_files`), loading, schema validation, overlay merge, candidate filtering |
| `src/transaction_id_registry.py` | fingerprint → ID mapping, persisted per dataset |
| `src/transaction_overrides.py` | override file loading, validation, application |
| `src/override_id_remap.py` | `_row`-hint-based remap suggestions |

### Import convention

`src/` is not a package. Each entry point does `sys.path.insert(0, .../src)` and every
module then imports flat — `from models import Transaction`, `from rule_engine import
RuleEngine`. Tests do the same in their own header. Keep new modules consistent with this;
do not introduce `from src.x import y`.

### Where the logic actually sits

- **Matching** is entirely in `Rule.explain_match` (`src/models/rule.py`). It returns the
  full list of checks with pass/fail and a human-readable detail; `Rule.matches` is just
  `explain_match(...)["matched"]`, and `explain_rule_match.py` renders the same structure.
  A new filter field therefore needs to be added *once*, as a check in `explain_match` —
  matching, debugging and the explain CLI all follow from it.
- **Validation** of the rule schema is in `RuleEngine._parse_rules` and is strict: unknown
  or missing `transaction_category`, a `priority` outside 1–10, a malformed or inverted
  validity window, a duplicate key, an `overlay_of` pointing at a non-existent base key, or
  an overlay key colliding with a base key all raise at load time. Unknown rule fields are
  not rejected.
- **Rule notes and review questions** (`_note`, `review`, `reviewed_until`) are parsed onto
  `Rule` but never enter `explain_match`; only `doctor.py` reads them. Keep it that way —
  a review marker that changed a result would make the doctor's list lie.
- **Parsers** are regex strategies implementing `supports(text)` / `parse(text)` from
  `src/notification/base.py`. The registry in `src/notification/facade.py` tries them in
  list order and takes the first parser that claims the text, so order is significant —
  put a narrow parser before a broader one. A text no parser claims raises
  `NoNotificationParserFoundError`, which the import handler turns into a per-row warning.
  A new parser must be registered in the registry list *and* exported from
  `src/notification/parsers/__init__.py`.

## Datasets

A run dataset is any directory with `rules.json` and `input/`; `output/` and `metadata/`
are generated, and `budget.json` is optional. Any `rules.<topic>.json` next to `rules.json`
is discovered and loaded as part of the same rule set; only `rules.json` may carry `"base"`,
and keys must be unique across the files. `resolve_rule_files` in `src/rule_engine.py` is
the one place that resolves a dataset into base and overlay files — use it rather than
reading `rules.json` directly. Three datasets live here:

- `data/example` — standalone, committed, used by tests and documentation. Keep it stable
  and reproducible: changing it moves test expectations. Merchants may be synthetic.
- `data/reference` — shared baseline rules only, no `input/`, not runnable on its own.
- `data/private` — gitignored, personal, and its own nested Git repository with several
  datasets inside. Each declares `"base": "reference"` and overlays it.

Rules for changes: parser examples and test fixtures go to `data/example`; generic,
nationally reusable rules go to the fitting file in `data/reference`; anything personal,
local or contributor-specific goes to the fitting file of the private dataset.
`data/reference` and the private datasets are split by topic (`rules.ferien.json`,
`rules.gastro.json`, `rules.wohnen.json`, …); `data/example` stays a single file.

## Invariants

These are the things a change must not quietly break.

1. **Transaction IDs are stable across reruns.** The fingerprint is date, direction,
   notification text, credit and debit, plus the occurrence index among identical rows.
   Touching normalization in `TransactionIdRegistry._base_fingerprint`, or anything
   upstream that changes those five values, renumbers every ID and invalidates every
   `transaction_overrides.json` in every dataset — including the private ones, which are
   not visible from here. Treat it as a breaking change and mention the remap helper.
2. **No fallback category.** If no parser claims the text or no rule matches, the
   transaction stays uncategorized and shows up as `?` in the export. Do not add a
   catch-all anywhere in the engine; `--use-input-category-fallback` exists purely for
   export compatibility.
3. **Overrides belong to the top-level dataset.** A `transaction_overrides.json` in a base
   dataset is rejected outright. Unknown override IDs abort the run unless
   `--ignore-unknown-overrides` is passed.
4. **Tests never depend on `data/reference` or on private data.** Anything a test needs
   goes into `data/example` or into the test itself.
5. **Python is the only calculation engine; the Excel report only displays.** Every figure is
   written as a fixed value, and `reconcile` in `analyze_by_category.py` checks the summary
   tables against the transaction rows before anything is written. The only formulas are
   the `Check (Transactions)` rows. Do not move report logic into Excel formulas: it would
   duplicate what `budget_report.py` computes, and without an installed spreadsheet
   application no test could verify it (openpyxl stores no calculated values).
6. **The export column list is a contract.** `analyze_by_category.py` reads the categorized
   CSVs back and requires `Category`, `Subcategory`, `Credit in CHF`, `Debit in CHF`;
   the export is `;`-separated with `dd.mm.yyyy` dates.

## Traps

- **`include_keywords` is AND, `merchants` is OR.** All include keywords must be present in
  the combined parsed text; one merchant is enough. The asymmetry is deliberate but easy to
  misread, and a two-keyword rule stops matching silently as soon as a creditor rewords
  half its reference. `locations` is AND, `counterparties` is OR, `exclude_keywords` is a
  negative filter. `explain_rule_match.py` labels these correctly as `expected_all` vs
  `expected_any`.
- **An empty filter is a wildcard, not a no-match.** A rule that loses its last filter
  keeps matching on priority alone and quietly absorbs transactions. When editing rules,
  check what is left, not only what was removed.
- **Rules are evaluated by descending priority, not by file order.** Sorting a rules file
  by key is a readability choice only.
- **Ties between equal priorities are resolved by load order.** `sorted` is stable, so of
  two matching rules with the same priority the one loaded first wins: base before overlay,
  `rules.json` before the `rules.<topic>.json` files, those alphabetically. Moving a rule to
  another file can therefore change a result. Most reference rules share priority 5, so
  when a rule should win a known conflict, give it a higher priority or add an
  `exclude_keywords` entry to the other; do not rely on file placement.
- **An overlay rule keeps two identities.** `key` becomes the base key it replaces so the
  engine can match it, while `declared_key` stays what the file declared and is what the
  export and debug output show. Read both before changing overlay handling.
- **Split rows carry a suffixed ID.** A `split` override turns `TX-000042` into
  `TX-000042.1`, `.2`, … after ID assignment, so the export's `Transaction ID` is no longer
  always a registry ID. Anything that maps an exported row back to its override, its rule or
  the registry must use the part before the dot, as the `matching_rules_map` rebuild in
  `categorize_transactions.py` does.
- **Argument parsing is inconsistent.** `categorize_transactions.py` and
  `analyze_by_category.py` parse `sys.argv` by hand; adding a flag there means editing the
  hand-rolled block *and* both usage strings. The other tools use `argparse`.
- **`merchants` also searches the counterparty.** `Rule.explain_match` checks merchant
  names against both parsed fields, so a payee written into `counterparty` by a payment
  parser still matches a `merchants` entry.
- **Reserves count transfers, budget lines do not.** In `budget_report.py`, rows are first
  assigned to reserves by category/subcategory over everything except income, so a
  pension payment booked as a transfer still draws on its reserve. Only the rows no reserve
  claims go through `spending_rows` into the budget lines.
- **The budget nets refunds, most of the Excel report does not.** `budget_report.py` computes a
  line's actual as debits minus credits and excludes income and transfers; the category
  sheets of the Excel report show `Refund` as its own transaction category and exclude only
  transfers. "Transactions" (`Amount`) and "Top Payees" follow the budget via the shared
  `spending_rows`. Do not align the rest without deciding which behaviour the analysis
  should have.
- **Everything user-facing is German, everything structural is English.** Input columns,
  notification texts and category names are German; service types, transaction categories,
  export headers, code and documentation are English. Keep that split. The one leak is
  `Account Transfer Auf` / `Account Transfer Von`, where the parser carries the German
  direction word into the detail — since details are matched exactly, the spelling cannot
  be tidied up without invalidating every rule that filters on it.

## Conventions

- Code and comments in English, type hints throughout, dataclasses for models, docstrings
  on public functions explaining intent rather than restating the signature.
- Comments explain *why*, especially for regex anchors and format quirks — see
  `foreign_payment_parser.py`, where the IBAN is the only reliable split point.
- Tests are plain `pytest` functions named `test_*`, one module per component, no
  `conftest.py`, no fixtures framework. Follow the existing header when adding a module.
- New parser → a case in `tests/test_notification_service_parsers.py` with an anonymized
  notification text. New rule behavior → a test against `data/example`.
- Commit subjects are a single third-person sentence ending in a period ("Adds a parser for
  SEPA foreign payments."). The body explains the reasoning and the consequence, wrapped at
  about 80 characters, and ends with the `Co-Authored-By` line when an agent wrote it.

## Privacy

- Never commit anything from `data/private` to this repository, and never copy real
  merchants, counterparties, IBANs or reference numbers out of it into committed files.
  Anonymize before adding a row to `data/example`.
- Keep CHF figures out of committed documentation. Public docs stay qualitative;
  per-dataset numbers live inside the dataset directory.
- Rule sets can leak as much as data: a rule naming a landlord, a family member or a local
  merchant belongs in the private dataset, not in `data/reference`.

## Skills

`.agents/skills/` holds three skills covering the iteration loop, each expecting this file
and `README.md` to be read first, and each deliberately handling exactly one warning per
run:

- `handle-no-notification-parser-warnings` — a notification text no parser claims.
- `fix-uncategorized-transactions` / `update-rules-to-categorise-additional-entry` — a
  parsed transaction no rule claims; the second also decides base vs. private rule set.

Order matters: parser warnings first, rule warnings only once the input parses.

The skills hard-code warning strings, file paths and rule field names. When one of those
changes, update the skills in the same commit.
