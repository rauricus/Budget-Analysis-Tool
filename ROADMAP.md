# Roadmap (SOLL or target state)

Plan for turning the existing categorization tool into an actual budgeting tool.
Baseline and gap analysis: [STATUS.md](STATUS.md).

_Last updated: 2026-09-23._

## Where this stands

A minimal version of steps 1 and 3 exists since 2026-09-20: `budget.json` with one
`monthly`/`yearly` target per category, and `budget_report.py` comparing it against the
actuals for one month plus the cumulated period, on the console. Three of the open decisions
below are settled by it — refunds are netted, transfers stay out, and budgeting happens at
category level.

Since 2026-09-23 `budget.json` has three sections: a planned `income`, `reserves` that set
money aside for known yearly costs (health insurance, taxes, pension) and are tracked as pots
against the transactions of their category or subcategory, and the `budget` lines that
distribute the rest. The report shows how much of the income is left after both.

It was built deliberately small, to get the plan-vs-actual loop running and let real
variances decide what the schema actually needs. The steps below are therefore written as
they were, with the parts already covered marked as such.

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

**Partly done.** `<run_dir>/budget.json` exists with `income`, `reserves` and `budget`
sections, loaded and validated in `budget_report.py`. Still open:

- Overlay-capable: a shared baseline budget in `data/reference` can be overridden per
  dataset, using the same `base` mechanism as the rules.
- Optional `subcategory` per line, and a `type` (`fixed` | `variable`) distinction.
- Validation against the categories actually produced by the rule set. Deliberately skipped
  for now: an unknown category shows up under "Ohne Ist-Werte" with an actual of zero, which
  surfaces a typo without loading and merging the rule files.
- Moving the model out of `budget_report.py` into `src/budget.py`, once a second caller
  (the Excel sheet) needs it.
- Reserves: assigning a rule (the premium rule, say) to a reserve directly instead of
  matching by category/subcategory; matching several categories per reserve; due dates
  instead of linear twelfths, so a tax bill paid in March does not read as an overdrawn pot.

Decisions settled by the first version:

- **Refund handling**: netted. A category's actual is its debits minus its credits, so a
  refund carrying its expense category reduces that category, and an unattributable one
  keeps `Rückerstattungen` and shows up as a line without a budget.
- **Budget granularity**: category level. Subcategory lines are the first candidate for the
  next increment if the grid turns out too coarse in practice.
- **Transfers**: out, together with income. Only spending is budgeted.

Still open:

- **Travel**: trips are now modelled per trip in the datasets, so holiday and business travel arrive as complete, dated units rather than scattered across categories. That makes them the clearest case for a `yearly` line with the individual trips as its detail — a monthly target for travel is meaningless.
- **Three kinds of spending, not one.** `monthly`/`yearly` and `fixed`/`variable` both
  describe recurring spending. Two other kinds need different treatment:

  1. *Recurring* — becomes a category target, as today.
  2. *One-off individually, recurring as a class* — furniture, appliances, equipment. Not a
     target but a **provision**: a monthly rate paid into a pot, sized from history. The
     pot mechanics exist since reserves did (target accrues, actuals draw, balance shown);
     what is missing is selecting the transactions, which no category captures.
  3. *Offset by a matching inflow* — reimbursed by someone else, or drawn from a pot that is
     already being funded elsewhere in the budget. Belongs in neither: both sides must leave
     the derivation, or the same money gets budgeted twice.

  Classes 2 and 3 have to be marked per transaction, since nothing in the transaction itself
  distinguishes them. The mechanism mirrors `transaction_overrides.json` — same
  `{TX-id: {...}}` shape, same ID-remap helper — but in its own file, so that the
  categorization pipeline stays free of budgeting concepts. The marking classifies rather
  than excludes: class 2 leaves the category target *and* feeds the provision rate, both from
  the same entry.

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

**Partly done.** `budget_report.py <run_dir> [--month YYYY-MM]` prints target, actual and
variance per category for one month, plus the same three cumulated over the dataset's months
up to that one, and lists categories with actuals but no budget line. A `yearly` target is
compared at a twelfth per month.

What is still missing is the same comparison inside the report you actually keep — a new
sheet "Budget vs. Actual" in `analyze_by_category.py`, alongside the existing four:

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

The Excel report is a good export, but it is a snapshot, and nothing in it recalculates.
Since 2026-09-23 it carries the transactions behind the aggregates (sheet "Transactions",
filterable) and the largest payees per subcategory (sheet "Top Payees"), which covers the
first half of the drill-down: category to transactions. Going from a transaction to the rule
that claimed it still means `explain_rule_match.py`.

The goal is to browse the categorized data — drill from a category into the transactions that
make it up, and from a transaction into the rule that claimed it. That serves understanding
and verification of the categorization and the rules, not budgeting. A small local web app is
the obvious shape, but the shape is not the point and this is explicitly secondary to
steps 1–4.

## Deliberately out of scope for now

- Multi-account support (only a single account per dataset is processed today). Provision
  balances live on the accounts they are saved into, so "is the pot big enough" stays out of
  reach until this exists.
- Forecasting and simulation on top of the budget.
- Non-German CSV locales.
