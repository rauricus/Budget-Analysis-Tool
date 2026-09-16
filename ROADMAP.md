# Roadmap (SOLL or target state)

Plan for turning the existing categorization tool into an actual budgeting tool.
Baseline and gap analysis: [STATUS.md](STATUS.md).

_Last updated: 2026-09-16._

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
- **Travel**: trips are now modelled per trip in the datasets, so holiday and business travel arrive as complete, dated units rather than scattered across categories. That makes them the clearest case for a `yearly` line with the individual trips as its detail — a monthly target for travel is meaningless.
- **One-off spending needs a third class.** `monthly` vs `yearly` separates regular from
  rare, and `fixed` vs `variable` separates predictable from not. Neither separates regular
  from *never again*. A single large purchase in a category that otherwise runs small is
  indistinguishable from an annual item by shape alone — both occur once and both are big —
  yet only one of them says anything about next year. Where that marking lives is the open
  question: the override file already carries a `_note` per transaction and could carry a
  flag, or the budget could name the categories it treats as one-off. Without it, step 2
  systematically proposes targets that are too high.

## Step 2 — Budget proposal generator

New CLI `propose_budget.py <run_dir>`: derives a draft `budget.json` from the categorized
history.

- Median instead of mean for variable categories, so single outliers do not set the target.
- Categories that occur in only a few months of the observed period are proposed as
  `yearly` rather than as an inflated monthly average.
- Fixed costs detected from recurring standing orders and direct debits with a stable
  counterparty. Distinguish two cases: recurring *and* constant in amount (propose directly),
  versus recurring with a varying amount (propose as `fixed` rhythm, amount for review).
- One-off spending excluded from the derivation rather than averaged into it, using whatever
  marking step 1 settles on. It still belongs in the report as actuals — it happened — but it
  is not evidence about next year.
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

## Side goal — make the data browsable

The Excel report is a good export, but it is a snapshot: it carries the aggregates, not the
transactions behind them, and nothing in it recalculates. Checking why a category looks the
way it does still means going back to the CSV or to `explain_rule_match.py`.

The goal is to browse the categorized data — drill from a category into the transactions that
make it up, and from a transaction into the rule that claimed it. That serves understanding
and verification of the categorization and the rules, not budgeting. A small local web app is
the obvious shape, but the shape is not the point and this is explicitly secondary to
steps 1–4.

## Deliberately out of scope for now

- Multi-account support (only a single account per dataset is processed today).
- Forecasting and simulation on top of the budget.
- Non-German CSV locales.
