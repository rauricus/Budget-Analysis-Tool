# Roadmap (SOLL)

Where the tool is going: from a categorization tool with a plan-vs-actual report to a
budget that can be derived, kept and reviewed month by month. Current state:
[STATUS.md](STATUS.md).

The pipeline, the dataset conventions and the rule mechanics stay as they are. Python stays
the only calculation engine; the Excel report displays.

## 1. Finer budget lines

- **Budget per payee or rule.** A line such as a single café or a single rule, below the
  subcategory. Candidate key: the normalized payee from "Top Payees", or a rule key.
- **Reserves by rule.** Assign a rule (the premium rule, say) to a reserve directly, instead
  of relying on a subcategory of its own.
- **Due dates for reserves.** A tax bill due in March should not read as an overdrawn pot
  until the year catches up.

## 2. Mark special spending

Recurring spending is covered by budget lines and reserves. Two other kinds need a marking
per transaction, because nothing in the transaction itself tells them apart:

- **One-off individually, recurring as a class** (furniture, appliances): not a target but a
  provision — a monthly rate into a pot, sized from history. The pot mechanics exist in the
  reserves; what is missing is selecting the transactions.
- **Offset by a matching inflow** (reimbursed by someone else, or paid from a pot funded
  elsewhere in the budget): both sides must leave the budget, or the same money counts twice.

The marking lives in its own `{TX-id: {...}}` file next to `transaction_overrides.json`,
using the same ID-remap helper, so that the categorization pipeline stays free of budget
concepts.

## 3. Budget proposal

`propose_budget.py <run_dir>` writes a draft `budget.json` from the categorized history, for
manual review, never applied automatically:

- median rather than mean, so single outliers do not set a target;
- categories present in only a few months proposed as `yearly`;
- fixed costs detected from recurring standing orders and direct debits;
- marked one-off and offset spending left out of the derivation.

## 4. Budget in the Excel report

A sheet "Budget vs. Actual" with the same figures as `budget_report.py`: target, actual,
variance and cumulated values per line, reserves with their pots, and lines without a budget.
Computed in Python and written as values, like the other sheets.

## 5. Monthly routine

- The budgeting workflow documented in `README.md`: import, categorize, report, review.
- Optional skill `/monthly-budget-review` running those steps and summarizing the variances.
- Budget targets revisited at a fixed cadence (quarterly, say) rather than edited ad hoc.

## Out of scope

- More than one account per dataset.
- Forecasting and simulation.
- Non-German CSV layouts.
