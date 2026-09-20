---
name: handle-no-notification-parser-warnings
argument-hint: "[dataset] Dataset name (e.g. 'example' or a private dataset) to work on."
description: Extend an existing or add a new parser for notification texts of a transaction, when the "Categorize" script outputs warnings that no such parser could be matched for a given row in the input CSV.
user-invocable: true
disable-model-invocation: false
---

## Skill: Add missing or extend existing parser

In this skill, you will address warnings from the "Categorize" script that indicate no parser could be matched for certain notification texts in the input CSV. This involves identifying the problematic notification, anonymizing the data, implementing a new parser, and verifying its functionality through tests.

Prerequisites:
- Follow AGENTS.md.
- Read README.md to familiarize yourself with the project structure and how the categorization process works.

1. **Identify**: Run `uv run python categorize_transactions.py [dataset]` and look for the first `Row N: Notification text could not be parsed. No parser found for:` warnings in the console output. Only work on a single warning at once. Each warning includes the row number in the original input CSV. Open the corresponding input CSV and navigate to that row number to retrieve the raw data for anonymization.
2. **Anonymize**: Create an anonymized version of the original CSV row:
   - Replace names, IBANs, reference numbers, and other personal data with placeholders (e.g. `MAX MUSTER`, `CH56 0000 0000 0000 0000 0`, `REF-0000`).
   - Keep the `Avisierungstext` structure exactly as-is, since the parser matches on it. `Bewegungstyp` is not read by the pipeline; leave it as it is.
   - Keep amounts and date roughly the same (slight modification is allowed), but keep the amount in the same column: `Gutschrift in CHF` versus `Lastschrift in CHF` decides the transaction direction.
3. **Extend the example dataset (optional)**: To demonstrate the new format end to end, add the anonymized row to `data/example/input/export.YYYYMM.csv` (matching month file). `data/reference` holds rules only and has no `input/`. After adding a row, rerun `uv run python categorize_transactions.py example` and commit the regenerated `data/example/output/` and `data/example/metadata/` along with it. The parser test in step 5 is the required fixture; this step is the optional addition.
4. **Implement the parser**: Create a new parser in `src/notification/parsers/` (naming scheme: `<service>_parser.py`) implementing `supports()` and `parse()` from `notification/base.py`. Register it in **both** places: the `_NotificationParserRegistry` list inside `src/notification/facade.py` and the exports in `src/notification/parsers/__init__.py`. The registry takes the first parser whose `supports()` returns True, so place a narrow format before a broader one that would also claim the text.
5. **Update tests**: Add a test case to `tests/test_notification_service_parsers.py` for the new parser, using the anonymized notification text as input and asserting the expected fields, including `service_type` and `transaction_type_detail`. This test is required — it is what keeps the format covered.
6. **Verify**: Run `uv run pytest -q` and ensure all tests pass.
7. **Iterate**: If the new parser does not match the original notification text, refine the regex pattern and test case until it matches successfully.