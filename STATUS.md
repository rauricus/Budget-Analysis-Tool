# Status (IST or current state)

Snapshot of what this project actually does today, as a baseline for [ROADMAP.md](ROADMAP.md).

_Last reviewed: 2026-08-16._

## Summary

The categorization pipeline is complete and reliable. What does **not** exist yet is the
budget itself: the tool is purely retrospective. There are no target values anywhere, no
place to store them, and no plan-vs-actual comparison. "Budget" appears only as a report
title.

## What works

| Area | State |
|---|---|
| CSV import (PostFinance) | Complete |
| Notification parsing | 13 parsers, registry-based, 8 normalized service types |
| Transaction IDs | Stable fingerprint registry, persisted per dataset |
| Rule engine | Priority-based matching, service/provider scoping, keyword and counterparty filters |
| Rule overlays | `base` + `overlay_of` mechanism, base rules replaceable per dataset |
| Transaction overrides | Per-ID overrides incl. `hidden`, with fail-fast ID validation and a remap helper |
| Explain tooling | `explain_rule_match.py` with per-rule check breakdown, JSON output |
| Export | 20-column structured CSV incl. matched rule key and source |
| Analysis | Excel report with 4 sheets (summary, category overviews, per-month category and subcategory tables) |
| Tests | 15 test modules covering parsers, rules, overlays, overrides, export, ID registry |
| Agent skills | 3 skills covering the rule/parser iteration loop |

Rule sets: 52 baseline rules in `data/reference`, 36 in the standalone `data/example`.

Per-dataset state — coverage, open transactions, figures — is tracked inside the respective
dataset directory, not here.

## Known gaps

1. **No budget artifacts.** No schema, no storage location, no comparison logic, no report
   section for target values.

2. **No notion of periodicity.** The analysis aggregates strictly per month. An annual
   charge appears in whichever month it was paid, and there is no way to express it as an
   annual target that is spread across the year. Any average computed over such data is
   misleading.

3. **Refunds are never netted.** `Refund` is reported as its own transaction category, so
   expense categories are always gross. Whether a refund should reduce the corresponding
   expense line is neither decided nor implemented — and it materially changes what a
   realistic target for the affected categories looks like.

4. **Category granularity is analysis-driven.** The rule sets produce fine-grained
   subcategories, which is right for analysis but not necessarily the right grid for budget
   lines. There is no concept of a coarser budget-level grouping.

## Smaller findings

- `src/notification/parsers/__init__.py` re-exports 11 parsers, while the registry in
  `facade.py` instantiates 13. `AccountTransferParser` and `PostFinanceCardRefundParser`
  are missing from `__all__`. Harmless today (the facade imports directly from the modules),
  but the two lists should not drift apart.
- `categorize_transactions.py` parses its flags by hand, while the other three CLIs use
  `argparse`. Consistency would make the flags self-documenting.
- `pyproject.toml` pins `requires-python = ">=3.9,<3.10"`, which is a narrow window for a
  tool that is otherwise version-agnostic.
