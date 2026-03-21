# 📊 Budget Tool

Automatic categorization of bank transactions using configurable JSON rules.

## 🎯 Features

- ✅ CSV import (PostFinance format)
- ✅ Service-specific parser registry (Apple Pay, Twint, Lastschrift variants)
- ✅ Rule engine with priority-based matching
- ✅ Service-scoped rule selection (`services` in rules)
- ✅ Merchant, location, include/exclude keyword matching
- ✅ Structured CSV export with parsed service fields

### CSV locale support (current)

- Import and export are currently aligned to German PostFinance CSV conventions.
- Import expects German source columns from PostFinance (for example `Datum`, `Bewegungstyp`, `Avisierungstext`, `Gutschrift in CHF`, `Lastschrift in CHF`, `Kategorie`).
- Export preserves German transaction content (for example Lastschrift/Zahlung/Dauerauftrag details) in parsed fields.

## 🚀 Setup

```bash
# Create environment
micromamba env create -f environment.yml

# Activate environment
micromamba activate bat

# Run pipeline
python main.py
```

## ✅ Tests

```bash
# Run all tests
micromamba run -n bat pytest -q

# Verbose output
micromamba run -n bat pytest -v

# Run a specific test file
micromamba run -n bat pytest tests/test_rule_matching.py
```

## 📂 Structure

```text
data/
├── rules.json                     # Rule definitions (service-scoped matching)
├── input/                         # New raw input CSV files
├── output/                        # Generated categorized CSV outputs
└── reference/                     # Versioned reference datasets
  ├── input/                     # Stable sample input CSV files
  └── output/                    # Expected/known categorized outputs

src/
├── import_handler.py              # CSV import utilities
├── export_handler.py              # Structured CSV export builder
├── models/                        # Domain model package
│ ├── transaction.py               # Transaction dataclass
│ └── rule.py                      # Rule dataclass + matching logic
├── rule_engine.py                 # Rule loading + service-filtered categorization
├── transaction_parser.py          # Row-to-Transaction conversion
└── notification/
  ├── base.py                    # Parser interface + parse result model
  ├── facade.py                  # Public facade to parser registry
  ├── registry.py                # Parser dispatch (first supporting parser wins)
  └── parsers/
    ├── apple_pay_parser.py      # Apple Pay notification parser
    ├── twint_senden_parser.py   # Twint send-money parser
    ├── debit_direct_parser.py   # CH-DD debit direct parser
    ├── zahlung_parser.py        # Lastschrift payment parser
    └── dauerauftrag_parser.py   # Lastschrift standing-order parser

main.py                            # Pipeline entry point
tests/                             # Unit/integration-style tests for pipeline components
```

## 🔄 Data Flow

```text
data/input/*.csv
   -> ImportHandler.load_csv
   -> TransactionParser.parse_row
   -> NotificationTextParser.parse (via parser registry)
   -> RuleEngine.categorize_batch
   -> ExportHandler.export_csv
   -> data/output/*.categorized.csv
```

## 🎨 Rules (`data/rules.json`)

Example:

```json
{
  "rules": [
    {
      "id": 1,
      "name": "Migros Take-Away",
      "category": "Freizeit // Gastronomie",
      "priority": 100,
      "transaction_types": ["Buchung"],
      "services": ["Apple Pay"],
      "triggers": {
        "merchants": ["MIGROS"],
        "locations": [],
        "include_keywords": ["TAKE AWAY"],
        "exclude_keywords": []
      }
    }
  ]
}
```

### Matching behavior

- Rules are sorted by descending `priority`.
- Only rules that include the transaction's parsed `service_type` in `services` are considered.
- A rule matches only if all configured conditions match.
- `merchants`: OR logic (at least one must match).
- `locations`: AND logic (all must match).
- `include_keywords`: AND logic (all must match).
- `exclude_keywords`: none may match.

### No fallback category

There is no fallback category in the engine.
If no parser matches a service or no rule matches that service, the transaction stays uncategorized.

## 📤 Export Format

The structured export currently uses these columns:

- Date
- Transaction Type
- Transaction Type Detail
- Service
- Card Number
- Merchant
- Location
- Recipient
- Recipient IBAN
- Reference
- Credit in CHF
- Debit in CHF
- Label
- Category

## 🧪 Iterative workflow

1. Put a new CSV into `data/input/`.
2. Run `python main.py`.
3. Inspect `data/output/*.categorized.csv`.
4. Add/refine parser(s) in `src/notification/parsers/` if needed.
5. Add/refine matching rules in `data/rules.json`.
6. Repeat until categorization quality is acceptable.

## 🎯 Next steps

- [ ] Add parser(s) for currently uncategorized service formats
- [ ] Add category-level reporting summaries
- [ ] Add optional chart/export modules
