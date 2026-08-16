# Roadmap (SOLL or target state)

Plan for turning the existing categorization tool into an actual budgeting tool.
Baseline and gap analysis: [STATUS.md](STATUS.md).

_Last updated: 2026-08-16._

## Goal

Define target values per category, compare them against actual spending per month, and see
deviations early enough to react — while keeping the existing pipeline, dataset conventions
and rule/overlay mechanics unchanged.

## Sequencing

Build the mechanism first (steps 1–3) against whatever categorized history a dataset already
has, then refine the numbers as coverage grows. The plan-vs-actual loop is useful from the
first month it exists, and the proposal generator improves on its own as more history
arrives. Extending a dataset's coverage is dataset work and is tracked in the dataset itself,
not here.

## Step 1 — Budget data model

New file per dataset: `<run_dir>/budget.json`, following the conventions of `rules.json`
and `transaction_overrides.json`.

- Overlay-capable: a shared baseline budget in `data/reference` can be overridden per
  dataset, using the same `base` mechanism as the rules.
- One entry per budget line: `category`, optional `subcategory`, `amount`, `period`
  (`monthly` | `yearly`), `type` (`fixed` | `variable`), optional comment.
- Validation against the categories actually produced by the rule set, so typos surface
  immediately rather than silently creating an unmatched budget line.
- Implementation in `src/budget.py` with tests, mirroring the structure of
  `src/transaction_overrides.py`.

Open decisions to settle here:

- **Refund handling**: net refunds against their expense category, or treat them as income?
  This changes the target values of the affected categories materially.
- **Budget granularity**: which lines are budgeted at category level and which at
  subcategory level. Recommendation: budget at category level by default, and drop to
  subcategory only where it changes behavior.
- **Transfers**: currently excluded from the analysis. Confirm they stay out of the budget.

## Step 2 — Budget proposal generator

New CLI `propose_budget.py <run_dir>`: derives a draft `budget.json` from the categorized
history.

- Median instead of mean for variable categories, so single outliers do not set the target.
- Categories that occur in only a few months of the observed period are proposed as
  `yearly` rather than as an inflated monthly average.
- Fixed costs detected from recurring standing orders and direct debits with a stable
  counterparty. Distinguish two cases: recurring *and* constant in amount (propose directly),
  versus recurring with a varying amount (propose as `fixed` rhythm, amount for review).
- Output is a draft for manual review, never applied automatically.

## Step 3 — Plan vs. actual

New sheet "Budget vs. Actual" in `analyze_by_category.py`, alongside the existing four:

- Per budget line: target, actual, variance in absolute terms and as a percentage,
  year-to-date cumulation, and a colour indicator.
- Yearly items shown pro-rata per month, with the annual total as context.
- Categories with actuals but no budget line flagged explicitly, so gaps stay visible.

The per-month table layout already used in the category sheets carries over directly.

## Step 4 — Monthly routine

- Document the budgeting workflow in `README.md`.
- Optional skill `/monthly-budget-review`: import the new month, categorize, regenerate the
  report, and summarize the variances.
- Revisit the budget at a fixed cadence (for example quarterly) rather than editing it
  ad hoc, so that plan-vs-actual stays meaningful over time.

## Deliberately out of scope for now

- Multi-account support (only a single account per dataset is processed today).
- Forecasting and simulation on top of the budget.
- Non-German CSV locales.
