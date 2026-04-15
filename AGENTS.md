# AGENTS

## Python Environment

- Never create a new virtual environment in this repository.
- Always use the existing Micromamba environment named `bat`.
- Prefer `micromamba run -n bat <command>` for scripts and tests.
- If `-n bat` does not resolve due prefix differences, use the explicit environment path with `micromamba run -p /Users/andreas/micromamba/envs/bat <command>`.
- If activation is required in an interactive shell, use `micromamba activate bat`.

## Workflow: Adding Missing Parsers

When `categorize_transactions.py` does not recognize a parser for a transaction (transaction remains without Service/Provider information), proceed as follows:

1. **Identify**: Run `python categorize_transactions.py <dataset>` and look for `⚠️  Row N: No parser matched notification text` warnings in the console output. Each warning includes the 1-based row number in the original input CSV. Open the corresponding input CSV and navigate to that row number to retrieve the raw data for anonymization.
2. **Anonymize**: Create an anonymized version of the original CSV row:
   - Replace names, IBANs, reference numbers, and other personal data with placeholders (e.g. `MAX MUSTER`, `CH56 0000 0000 0000 0000 0`, `REF-0000`).
   - Keep the `Bewegungstyp` and `Avisierungstext` structure exactly as-is, since these are critical for parser matching.
   - Keep amounts (credit/debit) and date roughly the same (slight modification is allowed).
3. **Extend the reference dataset**: Add the anonymized row to `data/reference/input/export.YYYYMM.csv` (matching month file) or a new reference CSV.
4. **Implement the parser**: Create a new parser in `src/notification/parsers/` (naming scheme: `<service>_parser.py`) and register it in the `_NotificationParserRegistry` inside `src/notification/facade.py`.
5. **Update tests**: Add a test case to `tests/test_notification_service_parsers.py` for the new parser, using the anonymized notification text as input and asserting the expected fields.
6. **Verify**: Run `micromamba run -n bat pytest -q` and ensure all tests pass.
