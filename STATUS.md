# Status (IST)

What the tool does today and where its known limits are. Next steps: [ROADMAP.md](ROADMAP.md).

## What works

| Area | State |
|---|---|
| Import | PostFinance CSV, German column layout |
| Parsing | 15 notification parsers, 8 normalized service types |
| Transaction IDs | Stable fingerprint registry per dataset |
| Rules | Priority matching; service, provider, merchant, location, counterparty, IBAN, keyword, validity-window and exact-amount filters; overlays on a base rule set; rules split over any number of `rules.<topic>.json` files |
| Overrides | Per-transaction corrections by ID, with a remap helper after ID changes |
| Diagnostics | `--debug` pipeline output and `explain_rule_match.py` |
| Export | 20-column categorized CSV per input file |
| Analysis | Excel report: summary, overviews, per-month category and subcategory tables, all transactions filterable, top payees per subcategory. Static figures, reconciled against the transactions, with a check row per table |
| Budget | `budget.json` with planned income, reserves (pots) and budget lines per category or subcategory; `budget_report.py` compares one month and the cumulated period on the console |
| Tests | 17 modules, independent of `data/reference` and private data |

Rule sets: 70 baseline rules in `data/reference`, split by topic into `rules.json` and
`rules.<topic>.json` files; 38 in `data/example`, in a single `rules.json`.

## Known gaps

- **Budget lines stop at subcategory level.** No budget per payee or per rule, and reserves
  match by category/subcategory only. Two things that share a subcategory can only be
  separated by the rules.
- **Reserves accrue linearly.** A bill due in one month reads as an overdrawn pot until the
  year catches up.
- **No marking of special spending.** Nothing distinguishes one-off purchases that recur as a
  class (furniture) or spending that is offset by a matching inflow; both distort averages.
- **Targets are written by hand.** Nothing derives them from the history yet.
- **The Excel report is per month and mostly gross.** Refunds appear as their own transaction
  category except in "Transactions" and "Top Payees", and yearly items are not spread. The
  budget report is where netting and yearly lines apply.
- **Payees are grouped only lightly.** The same company with two addresses stays two payees.

## Smaller findings

- **A rule with no active filter is a silent catch-all.** The engine could warn when a rule
  above priority 1 has none; the deliberate catch-alls all sit at priority 1.
- **`merchants` also matches the counterparty field.** Rules that name a payee under
  `merchants` work even though payment parsers write it into `counterparty`. Convenient, but
  the rule files read as if they matched a merchant.
- **Argument parsing is inconsistent.** `categorize_transactions.py` and
  `analyze_by_category.py` parse `sys.argv` by hand, the other tools use `argparse`.
- **Python is pinned to 3.9 only** (`>=3.9,<3.10`), narrower than the code needs.
