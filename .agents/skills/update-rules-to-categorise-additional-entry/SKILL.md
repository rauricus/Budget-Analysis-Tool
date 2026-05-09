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
4. **Find a matching rule**: Check the existing rules in _base ruleset_, if one is referenced. Is there an existing rule that could be extended to match the row? A matching rule would have similar matching patterns as well as a description and name that could match its purpose. If no rule matches in the base ruleset, check the extending ruleset of the dataset.
5. **Extend or add a rule**: If you've found a rule to extend, present the user with the option to extend the rule. If they choose to extend, update the rule's matching patterns to also match the new transaction. If they choose not to extend or if no matching rule is found, create a new rule in the appropriate ruleset (base or extending) with matching patterns that match the new transaction's `Bewegungstyp` and `Avisierungstext`.
6. **Verify**: Run the "Categorize" script again with the debug flag to verify that the new or extended rule correctly categorizes the transaction without any warnings.
7. **Iterate**: If the introduced changes do not match, refine the rule matching until it matches successfully. Give up after 3 tries and inform the user that the transaction could not be categorized with the current ruleset, suggesting to analyze if the transaction has unique characteristics that require a different approach.