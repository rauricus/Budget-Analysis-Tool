# 📊 Budget-Tool

Automatische Kategorisierung von Banktransaktionen mit konfigurierbaren Regeln.

## 🎯 Features

- ✅ CSV-Import (PostFinance Format)
- ✅ Rule-Engine mit Prioritäten
- ✅ Merchant + Location-basiertes Matching
- ✅ Include/Exclude Keywords
- ✅ CSV-Export mit Auto-Kategorien

## 🚀 Setup

```bash
# Environment erstellen
micromamba env create -f environment.yml

# Environment aktivieren
micromamba activate bat

# Pipeline ausführen
python src/main.py
```

## ✅ Tests

```bash
# Alle Tests ausführen
pytest

# Mit Verbose Output
pytest -v

# Spezifischen Test ausführen
pytest tests/test_rule_matching.py
```

## 📂 Struktur

```
data/
├── reference/                     # Referenzdaten für Rule-Entwicklung (versioniert)
│   ├── input/                     # Input CSV (PostFinance Format)
│   │   └── export.202401.csv     # Beispiel-Datensatz für Rules
│   └── output/                    # Kategorisierte Outputs
│       └── export.202401.categorized.csv
├── input/                         # Neue Input CSVs (ignoriert, zum Testen)
├── output/                        # Neue Output CSVs (ignoriert, generiert)
└── rules.json                     # Kategorisierungs-Regeln

src/
├── models.py                      # Transaction, Rule Dataclasses
├── rule_engine.py                 # Matching-Logik
├── csv_handler.py                 # CSV I/O (Input/PostFinance)
├── export_handler.py              # CSV Export (strukturiertes Format)
└── main.py                        # Pipeline

tests/
├── test_csv_handler.py            # CSV Handling Tests
├── test_export_handler.py         # Export Format Tests
├── test_rule_details.py           # Rule Matching Details
├── test_rule_matching.py          # Rule Matching Logic
└── test_categorization.py         # Transaction Categorization
```

### Datenfluss

```
data/reference/input/export.202401.csv
        ↓ (CSVHandler.load_csv)
    [Transactions]
        ↓ (RuleEngine.categorize_batch)
    [Categorized + Matching Rules]
        ↓ (ExportHandler.export_csv)
data/reference/output/export.202401.categorized.csv
```

## 🎨 Rules definieren (rules.json)

```json
{
  "rules": [
    {
      "id": 1,
      "name": "Beschreibung",
      "category": "Kategorie // Unterkategorie",
      "priority": 100,
      "transaction_types": ["APPLE PAY KAUF/DIENSTLEISTUNG"],
      "services": ["APPLE PAY"],
      "triggers": {
        "merchants": ["MIGROS"],
        "locations": ["AARAU"],
        "include_keywords": ["TAKE AWAY"],
        "exclude_keywords": []
      }
    }
  ],
  "fallback_category": "Sonstiges"
}
```

### Matching-Logik

- **Priority**: Höchste gewinnt
- **Merchants**: Min. einer muss vorhanden sein (ODER)
- **Locations**: Alle müssen vorhanden sein (UND)
- **include_keywords**: Alle müssen vorhanden sein (UND)
- **exclude_keywords**: KEINE darf vorhanden sein

Alle Bedingungen sind case-insensitive.

## 📝 Example

Input: `"APPLE PAY KAUF/DIENSTLEISTUNG VOM 27.01.2024 ... MIGROS IGELWEID TAKE AWAY (5413) AARAU SCHWEIZ"`

→ Matche gegen `migros_takeaway` (weil Merchant=MIGROS + Keyword TAKE AWAY)
→ `Freizeit // Gastronomie`

## � Export Format

Das Tool exportiert kategorisierte Transaktionen in einem strukturierten CSV mit folgenden Spalten:

| Spalte | Beschreibung |
|--------|-------------|
| **Datum** | Transaktionsdatum (TT.MM.YYYY) |
| **Bewegungstyp** | Typ der Banktransaktion (z.B. Buchung, Apple Pay) |
| **Service** | Aus Avisierungstext geparster Service (z.B. APPLE PAY) |
| **Kartennummer** | Aus Avisierungstext geparste Kartennummer (z.B. XXXX1384) |
| **Händler** | Extrahierter Merchant-Name (aus Rules oder Avisierungstext) |
| **Ort** | Transaktionsort/Stadt |
| **Gutschrift in CHF** | Positive Beträge (Einnahmen) |
| **Lastschrift in CHF** | Negative Beträge (Ausgaben) |
| **Label** | Original-Label der Bank |
| **Kategorie** | Automatisch zugewiesene oder Original-Kategorie |

## 🔄 Workflow

### Iterative Rule-Entwicklung

1. **Neue Daten testen** - CSV in `data/input/` legen
2. **Pipeline testen** - `python src/main.py` mit default Reference-Daten
3. **Rules verfeinern** - Anpassungen in `data/rules.json`
4. **Iterieren** - Schritte 2-3 wiederholen bis Rules zufriedenstellend

### Reference-Daten aktualisieren

Wenn neue Testdateien optimale Regeln erzeugen:

1. CSV von `data/input/abc.csv` nach `data/reference/input/abc.csv` verschieben
2. Output von `data/output/` nach `data/reference/output/` verschieben
3. `src/main.py` Input-Pfade ggf. aktualisieren
4. Commit für Versionskontrolle

**Vorteil:** `data/reference/` ist versioniert → reproduzierbar, `data/input/` wird ignoriert

## 🎯 Next Steps

- [ ] Analyse/Reports (Summen pro Kategorie)
- [ ] Visualisierung (Diagramme)
- [ ] Excel-Export
- [ ] AI-Modul (optional)
