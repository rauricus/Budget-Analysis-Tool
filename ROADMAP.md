# Roadmap (SOLL)

Where the tool is going: from a categorization tool with a plan-vs-actual report to a budget
that answers two questions every month — is consumption covered by income, and where can
discretionary spending shrink. Current state: [STATUS.md](STATUS.md).

Ground rules for every item below:

- The pipeline, the dataset conventions and the rule mechanics stay as they are.
- Python is the only calculation engine; the Excel report displays.
- The categorization pipeline stays free of budget concepts. Rules describe transactions
  (category, subcategory, tags); only the budget files and `budget_report.py` know about
  targets, groups and reserves.

## Now

### 1. Budget checks in `doctor.py`

The doctor already reads the whole dataset; with a `budget.json` present it also reports:

- a reserve or budget line whose category/subcategory no rule produces — today it silently
  shows an actual of zero, which looks the same as a month without spending;
- a budget key that matches no category in the export (typo);
- a month whose actual income is well above the planned income, as a question: bonus,
  expense refunds, or something else.

## Next

### 2. Tags on rules

Discretionary spending often cuts across the category tree: digital subscriptions sit next to
the phone bill in one subcategory, devices sit in household goods, a subscription exists in
several categories. New subcategories fix this one case at a time and change existing lines
each time.

- Rules get an optional `tags` list (`["abo"]`); overlays may set their own.
- The export gets a `Tags` column, appended at the end so existing readers keep working;
  `README.md` documents it as part of the export contract.
- A budget line keyed `#abo` covers all tagged rows. Tag lines are for watching and do not
  count towards the budget total, since their rows are already in a category line.
- A reserve may name a tag instead of a category, which covers "assign a rule to a reserve"
  without a subcategory of its own.

This replaces a budget line per payee or per rule: several rules can share a tag, and a tag
survives a rule being split or renamed.

### 3. Income by source, and offsets

Income is a single figure today, so a bonus and reimbursed expenses look alike.

- `income` may be split by subcategory (`Lohn`, `Bonus`, `Familienzulage`), each with its own
  amount and period.
- **Offset by a matching inflow** — expenses reimbursed by an employer or someone else, or
  paid from a pot funded elsewhere — must leave the budget on both sides, or the same money
  counts twice. Where a rule can recognize the inflow, the refund mirrors the expense
  category (as today). Where it cannot, the transaction is marked (see item 5).

### 4. Shared rule files across years (decide before the next year starts)

Each year's dataset starts as a copy of the previous rule set. Most rules apply to every
year; only a few are tied to a period (trips, amounts that change yearly). The copies drift
apart, and a correction has to be made in every year that is still re-run.

- A dataset's `rules.json` may name directories whose rule files are loaded as part of its
  own layer, e.g. `"include": ["private/common"]`, resolved like `base`. The files join the
  dataset's own files: keys must be unique across all of them, and load order (own
  `rules.json`, then included files, then own `rules.<topic>.json`, each alphabetically)
  decides ties as today.
- Year-specific rules stay in the year's own files; rules shared by all years move to the
  included directory.
- Datasets stay split by year: transaction IDs, overrides, budget files and reports are
  unchanged.
- Not pursued: one dataset for all years (renumbers IDs, and reports would need to separate
  years), and a recursive `base` (a third overlay layer through engine, doctor and explain
  output).

## Later

### 5. Mark special spending

Two kinds of spending need a marking per transaction when no rule can tell them apart:

- **One-off individually, recurring as a class** (furniture, appliances): not a target but a
  provision — a monthly rate into a pot, sized from history. Tags (item 2) cover the cases a
  rule can recognize; the marking covers the rest.
- **Offset by a matching inflow** that no rule can pair (item 3).

The marking lives in its own `{TX-id: {...}}` file next to `transaction_overrides.json`,
using the same ID-remap helper.

### 6. Due dates for reserves

A tax bill due in a given month should not read as an overdrawn pot until the year catches
up. A reserve may name its due months; the pot is compared against what is due by then.

### 7. Budget proposal

`propose_budget.py <run_dir>` writes a draft `budget.json` from the categorized history, for
manual review, never applied automatically:

- median rather than mean, so single outliers do not set a target;
- categories present in only a few months proposed as `yearly`;
- fixed costs detected from recurring standing orders and direct debits;
- groups carried over from the current budget;
- marked one-off and offset spending (item 5) left out of the derivation;
- more than one year of history, by reading several year datasets.

### 8. Trips from a trip file

A trip needs two to four rules today (country marker, prepayment window, places), and cash
withdrawn during the trip still lands in finance. A `trips.json` with name, period and
country generates those rules and assigns cash withdrawals within the period to the trip.

### 9. Monthly routine

- The budgeting workflow documented in `README.md`: import, categorize, doctor, report,
  review.
- Optional skill `/monthly-budget-review` running those steps and summarizing the variances
  per group.
- Budget targets revisited at a fixed cadence (quarterly, say) rather than edited ad hoc.

### 10. Budget in the Excel report

A sheet "Budget vs. Actual" with the same figures as `budget_report.py`, including groups
and the consumption figure. Computed in Python and written as values, like the other sheets.
Lower priority as long as the console report covers the monthly review.

## Out of scope

- More than one account per dataset.
- Forecasting and simulation, including retirement planning: a retirement budget is a
  document in the dataset, revised once a year against pension statements.
- Ad-hoc drill-downs (by amount band, weekday, …): one-off questions are answered with a
  script, not a report.
- Non-German CSV layouts.
