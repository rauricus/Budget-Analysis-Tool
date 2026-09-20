---
name: fix-uncategorized-transactions
argument-hint: "[dataset] Dataset name (e.g. 'private') to work on."
description: Fix uncategorized transactions in a dataset by identifying missing or incomplete rules and either adapting the reference rules or adding dataset-specific overrides.
user-invocable: true
disable-model-invocation: false
---

## Skill: Identify missing rule, fix by adapting a reference rule

In this skill, you will attempt to categorize transactions of a dataset using the existing reference rules. If the categorization fails for a transaction, you will identify a closely matching rule in `data/reference/rules.json`, create an overlay variant of it that matches the uncategorized transaction and add it to the dataset-specific rules.

Prerequisites:

- Follow AGENTS.md.
- Read README.md to familiarize yourself with the project structure and how the categorization process works.

1. **Pre-flight check**: Run `uv run python categorize_transactions.py [dataset]` with the "--debug" flag and look for `Row N: Notification text could not be parsed. No parser found for:` warnings in the console output. In such a case, stop execution as this indicates that the notification text of a transaction could not be parsed at all, which is addressed with the "handle-no-notification-parser-warnings" skill. 
2. **Identify**: Run `uv run python categorize_transactions.py [dataset]` with the "--debug" flag and look for `No matching rule` warnings in the console output. **Pick only the first such warning — do not process multiple warnings in one run.** Each warning includes the row number in the original input CSV and the data of that row itself.

3. **Find reference rule**: For this warning, identify a candidate rule in `data/reference/rules.json` that can be adapted. `data/reference` holds rules only and has no transactions to compare against, so judge the candidate by the rule itself: it should target the same parsed `services` and `transaction_type_detail` as the uncategorized transaction, the same `transaction_type` (`Credit` or `Debit`), and the category the transaction belongs in. The debug line of the warning shows the parsed values for the transaction; `uv run python explain_rule_match.py [dataset] --line-number N` shows which check a near-miss rule fails on.

4. **Decide**: Decide which path to take next:
   - If the reference rule can be extended to also cover the uncategorized transaction (e.g. by adding a merchant or keyword), and the transaction is not privacy-sensitive: continue with step 5 (Adapt the rule).
   - If no suitable reference rule exists, the reference rule cannot be extended without breaking other matches, or the transaction is privacy-sensitive (e.g. health, insurance): continue with step 6 (Override the rule).

5. **Adapt the rule**: Extend the matching reference rule directly in `data/reference/rules.json` so it also covers the uncategorized transaction (e.g. add the merchant name to the `merchants` list).

6. **Override the rule**: Add a rule to `data/[dataset]/rules.json` that matches the uncategorized transaction. Rules are identified by `key`, not `id`:
   - To replace the reference rule from step 3 for this dataset, give the new rule its own unique `key` and declare `"overlay_of": "<key of the reference rule>"`.
   - To add a rule alongside the reference rules, give it a unique `key` and no `overlay_of`. Reusing a base key without `overlay_of` is rejected at load time.
   - Either way the rule needs `name`, `transaction_category` (`Income`, `Expense`, `Refund` or `Transfer`) and an integer `priority` from 1 to 10.

7. **Verify**: Run the categorization process again with the "--debug" flag and check if the rule now matches the previously unmatched row and thus the transaction is categorized successfully. If not, there may be an issue with the matching criteria (e.g. merchant name, keywords) — refine and retry. **Once verified, stop. Do not proceed to the next warning.**