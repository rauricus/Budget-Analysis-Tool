# Status (IST or current state)

Snapshot of what this project actually does today, as a baseline for [ROADMAP.md](ROADMAP.md).

_Last reviewed: 2026-09-23._

## Summary

The categorization pipeline is complete and reliable. Budgeting exists as of 2026-09-20,
but only as a minimal first version: a `budget.json` with a planned income, reserves set
aside for known yearly costs, and target values per category, and a console report
comparing them against the actuals for one month plus the cumulated period. Everything the
roadmap describes around that — overlays, subcategory lines, provisions, a proposal
generator, an Excel sheet — is still open.

## What works

| Area | State |
|---|---|
| CSV import (PostFinance) | Complete |
| Notification parsing | 15 parsers, registry-based, 8 normalized service types |
| Transaction IDs | Stable fingerprint registry, persisted per dataset |
| Rule engine | Priority-based matching, service/provider scoping, keyword and counterparty filters, optional per-rule validity window (`valid_from`/`valid_to`) |
| Rule overlays | `base` + `overlay_of` mechanism, base rules replaceable per dataset |
| Transaction overrides | Per-ID overrides incl. `hidden`, with fail-fast ID validation, a remap helper and an optional `_note` for documenting why an override exists |
| Explain tooling | `explain_rule_match.py` with per-rule check breakdown, JSON output |
| Export | 20-column structured CSV incl. matched rule key and source |
| Analysis | Excel report with 4 sheets (summary, category overviews, per-month category and subcategory tables) |
| Budget | Minimal: `budget.json` with a planned `income`, `reserves` (pots per category or subcategory, e.g. health insurance, taxes, pension) and one `monthly`/`yearly` target per category in `budget`, compared per month and cumulated by `budget_report.py` on the console. Shows what is left of the income after reserves and budget lines. Refunds netted; income excluded; transfers excluded from budget lines but counted for reserves |
| Tests | 16 test modules covering parsers, rules, overlays, validity windows, overrides, export, ID registry, budget comparison; no test depends on a private dataset |
| Agent skills | 3 skills covering the rule/parser iteration loop |

Rule sets: 70 baseline rules in `data/reference`, 36 in the standalone `data/example`.

Per-dataset state — coverage, open transactions, figures — is tracked inside the respective
dataset directory, not here.

## Known gaps

1. **The budget is category-level only, and standalone.** No subcategory lines, so rent and
   furniture share one `Wohnen` target — only a reserve can take a subcategory out. A
   reserve matches by category/subcategory, not by rule, so premiums and deductible can
   only be separated if the rules give them distinct subcategories. Reserves accrue
   linearly; a tax bill due in March shows as an overdrawn pot until the year catches up. No `base`/overlay mechanism, so a budget shared
   across datasets means copying the file. No `fixed`/`variable` distinction, no provisions
   for spending that is one-off individually but recurring as a class, and no way to mark a
   transaction as offset by a matching inflow. Targets are written by hand; nothing derives
   them from the history.

2. **Periodicity is handled in the budget, not in the analysis.** `budget_report.py` spreads
   a `yearly` target evenly across the months and cumulates actuals, so an annual charge
   resolves over the year. The Excel report still aggregates strictly per month, and any
   average computed over it remains misleading.

3. **Refunds are netted in the budget, gross in the analysis.** `budget_report.py` subtracts
   a category's credits from its debits, so a refund carrying an expense category reduces
   it. The Excel report still reports `Refund` as its own transaction category. Whether the
   analysis should follow is open.

4. **Category granularity is analysis-driven.** The rule sets produce fine-grained
   subcategories, which is right for analysis. The budget sidesteps this by living one level
   up, at category level — which is coarse enough that "why is `Wohnen` over?" still has to
   be answered from the Subcategory sheet.

## Smaller findings

- **`include_keywords` is an AND across the list, `merchants` is an OR.** The asymmetry is
  deliberate but easy to misread, and a two-keyword rule silently stops matching as soon as a
  creditor rewords half of its reference. Worth stating in the rule documentation next to the
  filter list; `explain_rule_match.py` already shows it correctly as `expected_all` vs
  `expected_any`.
- `categorize_transactions.py` and `analyze_by_category.py` parse their flags by hand, while `explain_rule_match.py`, `suggest_override_ids.py` and `budget_report.py` use `argparse`. Consistency would make the flags self-documenting.
- `pyproject.toml` pins `requires-python = ">=3.9,<3.10"`, which is a narrow window for a
  tool that is otherwise version-agnostic.
- **A rule with no filter at all is a silent catch-all.** Empty filter lists mean "do not filter by this field", so a rule that loses its last filter keeps matching on priority alone and quietly absorbs transactions. This bit once, in a private rule set. The engine could warn at load time when a rule above priority 1 has no active filter; the deliberate catch-alls (`shopping_other_1`, `finance_1`, `refund_1`, `refund_3`) all sit at priority 1 or are scoped by service, so the check would be quiet in practice.
