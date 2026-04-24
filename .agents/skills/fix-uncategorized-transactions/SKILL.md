---
name: fix-uncategorized-transactions
argument-hint: "[dataset] Dataset name (e.g. 'private') to work on."
description: Fix uncategorized transactions in a dataset by identifying missing or incomplete rules and either adapting the reference rules or adding dataset-specific overrides.
user-invocable: true
disable-model-invocation: false
---

## Skill: Identify missing rule, fix by adapting a reference rule

In this skill, you will attempt to categorize transactions of a dataset using the existing reference rules. If the categorization fails for a transaction, you will identify a closely matching rule in the reference dataset, create an overriding variant of it that matches the uncategorized transaction and add it to the dataset-specific rules.

Prerequisites:
- Follow AGENTS.md.
- Read README.md to familiarize yourself with the project structure and how the categorization process works.

1. **Pre-flight check**: Run `uv run python categorize_transactions.py [dataset]` with the "--debug" flag and look for `Row N: Notification text could not be parsed. No parser found for:` warnings in the console output. In such a case, stop execution as this indicates that the notification text of a transaction could not be parsed at all, which is addressed with the "handle-no-notification-parser-warnings" skill. 
2. **Identify**: Run `uv run python categorize_transactions.py [dataset]` with the "--debug" flag and look for `No matching rule` warnings in the console output. Only work on a single such warning at once. Each warning includes the row number in the original input CSV and the data of that row itself. 
3. **Find reference rule**: For each warning, identify a matching rule in the reference dataset. There must be a row in the reference dataset with a similar `Bewegungstyp` and `Avisierungstext` structure that is categorized successfully. This indicates that there is a reference rule that can be adapted to match the uncategorized transaction. Find that rule.
4. **Decide**: Decide which path to take next:
   - If the reference rule can be extended to also cover the uncategorized transaction (e.g. by adding a merchant or keyword), and the transaction is not privacy-sensitive: continue with step 5 (Adapt the rule).
   - If no suitable reference rule exists, the reference rule cannot be extended without breaking other matches, or the transaction is privacy-sensitive (e.g. health, insurance): continue with step 6 (Override the rule).

5. **Adapt the rule**: Extend the matching reference rule directly in `data/reference/rules.json` so it also covers the uncategorized transaction (e.g. add the merchant name to the `merchants` list).
   Continue with step 7.

6. **Override the rule**: Add a new rule to `data/[dataset]/rules.json` that matches the uncategorized transaction. Use the same `id` as the reference rule you identified in step 3 if you want to replace its behaviour for this dataset, or use a new unique `id` if you want to add to it.
   Continue with step 7.

7. **Verify**: Run the categorization process again with the "--debug" flag and check if the rule now matches the previously unmatched row and thus the transaction is categorized successfully. If not, there may be an issue with the matching criteria (e.g. merchant name, keywords) — refine and retry.