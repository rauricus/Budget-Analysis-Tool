---
name: update-rules-to-categorise-additional-entry
argument-hint: "[dataset] Dataset name (e.g. 'reference' or 'private') to work on."
description: Extend an existing rule set to handle an uncategorized transaction.
user-invocable: true
disable-model-invocation: false
---

## Skill: Add missing or extend existing rule

In this skill, you will address warnings by the "Categorize" script that indicate that a certain transaction could not be categorised. This involves identifying such a transaction using debug output, finding a possible rule to extend or deciding to add a new rule. If the ruleset of the dataset extends a base ruleset, you'll also have to analyse if the transaction seems to be a personal nature - if it is, work should go into the extending rule set, else into the base ruleset.

Prerequisites:
- Follow AGENTS.md.
- Read README.md to familiarize yourself with the project structure and how the categorization process works.

1. **Pre-flight**: Run `uv run python categorize_transactions.py [dataset]`. If you find a `Row N: Notification text could not be parsed. No parser found for:` warning, abort and inform the user - we then first have to add or change parser to tackle a new or unrecognized notification text of a transaction
2. **Identify**: Run `uv run python categorize_transactions.py [dataset] --debug` and look for the first `Row N: No matching rule` warning.
	- Use the warning text exactly as printed (`No matching rule`, not `No rule matching`).
	- Always bind `Row N` to the currently processed file (`-> filename.csv`) shown in the debug output.
	- If output across multiple files is ambiguous, rerun scoped to one file with `uv run python categorize_transactions.py [dataset] --debug --input-file <filename.csv>` and take the first `No matching rule` in that run.
	- Only work on a single warning at once.
3. **Retrieve raw data**: For row N mentioned in the warning, open the matching file from the dataset `input` directory and read exactly that CSV line number.
	- Treat `Row N` as CSV line number from the source file in that run context.
	- Verify by checking that the raw row text matches the warning payload after `No matching rule | ...`.
	- Use this raw data to create a new rule or extend an existing one.
4. **Find a matching rule and decide target ruleset**: Check existing rules in the _base ruleset_ first (if referenced), then the extending ruleset.
	- A candidate for extension should have similar intent, category/subcategory, and matching patterns.
	- Choose **base ruleset** only when the transaction pattern is generic, likely reusable across Switzerland, and does **not** allow clear conclusions about the contributor or a very specific local context.
	- Choose **extending/private ruleset** when the transaction appears personal, local, or contributor-specific. This includes family members, personal account transfers, apartment-specific rent/utility counterparties, explicit place-specific merchants/providers, and companies that are strongly tied to one place or contributor context.
	- If classification is still ambiguous after applying this policy, **ask the user explicitly** before editing rules.
5. **Extend or add a rule**: If you've found a rule to extend, present the user with the option to extend the rule. If they choose to extend, update the rule's matching patterns to also match the new transaction. If they choose not to extend or if no matching rule is found, create a new rule in the selected ruleset (base or extending) with matching patterns that match the new transaction's `Bewegungstyp` and `Avisierungstext`.
	- Before writing changes, confirm with the user in one short decision line: `Target ruleset: base|private` and `Action: extend|new`.
6. **Verify**: Run the "Categorize" script again with the debug flag to verify that the new or extended rule correctly categorizes the transaction without any warnings.
7. **Iterate**: If the introduced changes do not match, refine the rule matching until it matches successfully. Give up after 3 tries and inform the user that the transaction could not be categorized with the current ruleset, suggesting to analyze if the transaction has unique characteristics that require a different approach.