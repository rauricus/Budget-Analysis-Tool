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

Nothing scheduled; the first item under Next is the one to pick up.

## Next

### 1. Tags on rules

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

## Later

### 2. Mark special spending

Spending that is **one-off individually but recurring as a class** (furniture, appliances)
needs a marking per transaction when no rule can tell it apart: not a target but a
provision — a monthly rate into a pot, sized from history. Tags (item 1) cover the cases a
rule can recognize; the marking covers the rest. (Spending offset by a matching inflow, such
as reimbursed expenses, is handled by a rule split with a review question and an override
where the default does not fit.)

The marking lives in its own `{TX-id: {...}}` file next to `transaction_overrides.json`,
using the same ID-remap helper.

### 3. Due dates for reserves

A tax bill due in a given month should not read as an overdrawn pot until the year catches
up. A reserve may name its due months; the pot is compared against what is due by then.

### 4. Budget proposal

`propose_budget.py <run_dir>` writes a draft `budget.json` from the categorized history, for
manual review, never applied automatically:

- median rather than mean, so single outliers do not set a target;
- categories present in only a few months proposed as `yearly`;
- fixed costs detected from recurring standing orders and direct debits;
- groups carried over from the current budget;
- marked one-off spending (item 2) left out of the derivation;
- more than one year of history, by reading several year datasets.

### 5. Trips from a trip file

A trip needs two to four rules today (country marker, prepayment window, places), and cash
withdrawn during the trip still lands in finance. A `trips.json` with name, period and
country generates those rules and assigns cash withdrawals within the period to the trip.

### 6. Monthly routine

- The budgeting workflow documented in `README.md`: import, categorize, doctor, report,
  review.
- Optional skill `/monthly-budget-review` running those steps and summarizing the variances
  per group; once item 8 exists, it ends with the review report and its analysis.
- Budget targets revisited at a fixed cadence (quarterly, say) rather than edited ad hoc.

### 7. Budget in the Excel report

A sheet "Budget vs. Actual" with the same figures as `budget_report.py`, including groups
and the consumption figure. Computed in Python and written as values, like the other sheets.
Lower priority as long as the console report covers the monthly review.

### 8. Review report with an AI analysis

A budget review happens offline and on paper: a plan for next year checked against this
year and the last, with the doctor's findings and a list of decisions to make. Today that
document is assembled by hand from the console output of five tools.

**Report.** `review_report.py <run_dir> [--budget FILE] [--compare <run_dir>]` writes a
self-contained HTML page, printable to PDF from any browser, into
`<run_dir>/review/<date>/`, next to a copy of the Excel report:

- Every figure comes from the existing code paths — `budget_report.py` and `doctor.py` return
  structured results that the console output and the report both render; nothing parses
  console text, and the report computes nothing of its own.
- Visualized: each budget line and reserve as plan, pro-rata target and actual, with the
  share of the yearly plan already used; group totals; income against consumption per month
  and cumulated; reserve pots. `--compare` adds a previous year's actuals against the same
  plan.
- Appendix: the doctor findings and the console output of the tools, unchanged.
- A `report.json` beside the page holds every figure the page shows. It is the only input
  the analysis step may cite numbers from.

**Analysis.** A skill (`/budget-review-analysis`) reads `report.json` together with the
dataset's own notes (budget `_note` fields, a dataset's markdown) and writes an analysis
file the report embeds as its own section: findings, deadlines and open questions, and
next steps as a checklist. It interprets, it does not calculate: any figure it cites must
be in `report.json`, and its section is marked as generated. The tool itself stays
offline; the skill runs in the agent session.

The report without the analysis is the MVP; the skill follows once the `report.json`
format has settled.

### 9. Override only the remainder of a rule split

An override `split` replaces a rule's whole split, so a payday that departs from the
default repeats the wage and the Familienzulage. If that proves annoying, an override field
`split_remainder` on the transaction's own ID splits only the rule's remainder part and
takes the fixed parts from the rule. Addressing the part by its suffixed ID (`TX-….3`) is
the weaker alternative: the suffix is a position that shifts when the rule's parts change.

## Zukünftige Entwicklungen

### 10. Declarative year planning and generated rules/budget

A yearly plan can be modeled in a declarative source directory, separate from the generated
`rules.json` and `budget.json` the tools actually execute. A dataset may hold a
`.sources/` folder with JSON files such as `income.json`, `reserves.json`, `trips.json`,
`subscriptions.json` and `budget_adjustments.json`. These files describe the year-specific
changes in a more readable form: salary, bonus, insurance premiums, trip periods, recurring
subscription rules and budget adjustments.

A helper script such as `generate_year.py <run_dir>` reads those sources and writes or updates
`rules.json` and `budget.json` for that year. The workflow stays iterative and reviewable:

- edit or copy the declaration files for the new year;
- generate or refresh the rules and budget from them;
- validate the result with `doctor.py` against the real transactions;
- adjust the declarative source or the generated rules where the doctor points to a problem;
- regenerate and validate again until the findings are resolved.

This keeps the generated files as the technical artifact the engine consumes while the source
files remain the human-readable planning layer. Manual edits in the generated files can still
be preserved or merged intentionally, and the doctor validates the result before it becomes a
finalized yearly setup.

## Out of scope

- More than one account per dataset.
- Forecasting and simulation, including retirement planning: a retirement budget is a
  document in the dataset, revised once a year against pension statements.
- Ad-hoc drill-downs (by amount band, weekday, …): one-off questions are answered with a
  script, not a report.
- Non-German CSV layouts.
