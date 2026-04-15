---
name: handle-no-notification-parser-warnings
argument-hint: "[dataset] Dataset name (e.g. 'reference' or 'private') to work on."
description: Extend an existing or add a new parser for notification texts of a transaction, when the "Categorize" script outputs warnings that no such parser could be matched for a given row in the input CSV.
user-invocable: true
disable-model-invocation: false
---

## Skill: Add missing or extend existing parser

In this skill, you will address warnings from the "Categorize" script that indicate no parser could be matched for certain notification texts in the input CSV. This involves identifying the problematic notification, anonymizing the data, extending the reference dataset, implementing a new parser, and verifying its functionality through tests.

Prerequisites:
- Follow AGENTS.md.
- Read README.md to familiarize yourself with the project structure and how the categorization process works.

1. **Identify**: Run `python categorize_transactions.py [dataset]` and look for the first `Row N: Notification text could not be parsed. No parser found for:` warnings in the console output. Only work on a single warning at once. Each warning includes the row number in the original input CSV. Open the corresponding input CSV and navigate to that row number to retrieve the raw data for anonymization.
2. **Anonymize**: Create an anonymized version of the original CSV row:
   - Replace names, IBANs, reference numbers, and other personal data with placeholders (e.g. `MAX MUSTER`, `CH56 0000 0000 0000 0000 0`, `REF-0000`).
   - Keep the `Bewegungstyp` and `Avisierungstext` structure exactly as-is, since these are critical for parser matching.
   - Keep amounts (credit/debit) and date roughly the same (slight modification is allowed).
3. **Extend the reference dataset**: Add the anonymized row to `data/reference/input/export.YYYYMM.csv` (matching month file) or a new reference CSV. This allows the new parser to be part of the shared reference dataset and benefit everyone.
4. **Implement the parser**: Create a new parser in `src/notification/parsers/` (naming scheme: `<service>_parser.py`) and register it in the `_NotificationParserRegistry` inside `src/notification/facade.py`.
5. **Update tests**: Add a test case to `tests/test_notification_service_parsers.py` for the new parser, using the anonymized notification text as input and asserting the expected fields.
6. **Verify**: Run `micromamba run -n bat pytest -q` and ensure all tests pass.
7. **Iterate**: If the new parser does not match the original notification text, refine the regex pattern and test case until it matches successfully.