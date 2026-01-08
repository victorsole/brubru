# Tenderator Knowledge Base

This directory contains reference data for the Tenderator feature, which monitors EU public procurement tenders and helps SMEs prepare bids.

## Data Sources

### 1. eForms SDK Data
**Source**: [OP-TED eForms SDK](https://github.com/OP-TED/eForms-SDK)
**Extraction Date**: November 2025
**SDK Version**: 1.13.x

#### `eforms/` Directory
- **fields.json** - ~1000 BT-* field definitions with XPath mappings for parsing eForms XML notices
- **notice-types.json** - 54 notice subtypes (PIN, CN, CAN, BRIN) with document types and legal basis
- **notice-subtypes/** - Individual JSON schemas for each notice type (1-40, E1-E6, T01-T02, etc.)

#### `codelists/` Directory
Converted from Genericode XML (.gc) files:

| File | Items | Description |
|------|-------|-------------|
| `cpv_codes.json` | 9,454 | Common Procurement Vocabulary - sector classification codes |
| `nuts_regions.json` | 1,903 | NUTS geographic regions (EU) |
| `countries.json` | 246 | ISO country codes with 24 EU language labels |
| `currencies.json` | 156 | Currency codes |
| `exclusion_grounds.json` | 31 | ESPD Part III - Exclusion criteria |
| `selection_criteria.json` | 32 | ESPD Part IV - Selection criteria |
| `notice_types.json` | 21 | Types of procurement notices |
| `procedure_types.json` | 10 | Procurement procedure types (Open, Restricted, etc.) |
| `buyer_legal_types.json` | 19 | Contracting authority legal types |
| `main_activities.json` | 20 | Buyer main activity sectors |
| `legal_basis.json` | 10 | EU procurement directives |
| `form_types.json` | 8 | Form type categories |
| `award_criteria.json` | 3 | Award criterion types (quality, price, cost) |
| `contract_nature.json` | 3 | Contract nature (works, supplies, services) |

### 2. eCertis Evidence Data
**Source**: [eCertis REST API](https://ec.europa.eu/tools/ecertis/)
**Extraction Date**: November 2025

#### `ecertis/` Directory
Country-specific ESPD criteria and required evidence documents:

- `criteria_{country_code}.json` - One file per EU member state (27 countries)
- Contains:
  - Exclusion grounds and selection criteria
  - Required certificates and attestations
  - Issuing authorities with contact URLs
  - National legislation references

### 3. Historical Data
- **awarded_contracts_2025_EC.csv** - European Commission awarded contracts data

## Usage

### Loading Codelists in Python
```python
import json
from pathlib import Path

CODELISTS_DIR = Path("backend/knowledge_base/tenders/codelists")

def load_codelist(name: str) -> dict:
    with open(CODELISTS_DIR / name, 'r', encoding='utf-8') as f:
        return json.load(f)

# Examples
cpv_codes = load_codelist("cpv_codes.json")
countries = load_codelist("countries.json")
procedure_types = load_codelist("procedure_types.json")

# Access items
for item in cpv_codes["items"][:5]:
    print(f"{item['code']}: {item.get('Name', 'N/A')}")
```

### Loading eForms Field Definitions
```python
import json

with open("backend/knowledge_base/tenders/eforms/fields.json", 'r') as f:
    fields_data = json.load(f)

# Access BT field definitions
for field in fields_data.get("fields", [])[:5]:
    print(f"{field['id']}: {field.get('name', 'N/A')}")
```

### Loading eCertis Evidence Data
```python
import json

def load_ecertis_country(country_code: str) -> dict:
    path = f"backend/knowledge_base/tenders/ecertis/criteria_{country_code}.json"
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

# Example: Belgium
be_criteria = load_ecertis_country("be")
for criterion in be_criteria["criteria"][:3]:
    print(f"{criterion['Name']['value']}")
```

## Updating Data

### Re-extract eForms SDK
```bash
# Clone latest SDK
git clone https://github.com/OP-TED/eForms-SDK.git /tmp/eForms-SDK

# Run extraction
python -m backend.scripts.extract_eforms_sdk /tmp/eForms-SDK
```

### Re-extract eCertis Data
```bash
python -m backend.scripts.extract_ecertis
```

## File Structure
```
backend/knowledge_base/tenders/
├── README.md                        # This file
├── awarded_contracts_2025_EC.csv    # Historical contract data
├── eforms/
│   ├── fields.json                  # BT-* field definitions
│   ├── notice-types.json            # Notice type metadata
│   └── notice-subtypes/             # Individual notice schemas
│       ├── 1.json
│       ├── 2.json
│       └── ...
├── codelists/
│   ├── codelists_summary.json       # Extraction metadata
│   ├── cpv_codes.json               # ~9,500 sector codes
│   ├── countries.json               # ISO countries
│   ├── procedure_types.json         # Procurement procedures
│   ├── exclusion_grounds.json       # ESPD Part III
│   ├── selection_criteria.json      # ESPD Part IV
│   └── ...
└── ecertis/
    ├── criteria_be.json             # Belgium
    ├── criteria_fr.json             # France
    ├── criteria_de.json             # Germany
    └── ...                          # 27 EU member states
```

## Related Documentation
- [TED Developer Docs](https://docs.ted.europa.eu/home/index.html)
- [eForms SDK Documentation](https://docs.ted.europa.eu/eforms/latest/index.html)
- [ESPD-EDM Documentation](https://docs.ted.europa.eu/ESPD-EDM/latest/business/index.html)
- [eCertis](https://ec.europa.eu/tools/ecertis/)
