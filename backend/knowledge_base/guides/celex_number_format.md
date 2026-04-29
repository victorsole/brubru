# CELEX Number Format — the EU Legal-Document Identifier System

## QUICK FACTS
- **Purpose**: A CELEX number is a **unique, language-independent identifier** assigned to EU legal documents on EUR-Lex. Every Regulation, Directive, Decision, Court judgment, Treaty, COM proposal, Council common position, and consolidated text has one.
- **Source spec**: https://eur-lex.europa.eu/content/help/eurlex-content/celex-number.html (Publications Office of the EU)
- **Why Brubru relies on it**: every chat answer that cites EU law uses CELEX as the canonical reference; the citation verifier validates CELEX refs against the Cellar API; the `eu_laws` table indexes 28,513 OJ publications by CELEX; all 203 knowledge guides cite CELEX numbers in their QUICK FACTS sections.
- **Canonical regex (Brubru `services/citation_verifier.py`)**: `\b[1-9]\d{4}[A-Z]{1,2}\d{4}\b` — sector(1) + year(4) + type(1-2 letters) + sequence(4)
- **Cellar URL pattern**: `https://publications.europa.eu/resource/celex/{CELEX}` (requires headers `Accept: application/xhtml+xml` AND `Accept-Language: en` — both mandatory; without `Accept-Language` Cellar 400s)
- **EUR-Lex URL pattern**: `https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{CELEX}` (use the HEAD method only — body scraping is forbidden per CLAUDE.md learned rule)
- **Brubru never invents identifiers**: if a CELEX number cannot be verified against either Cellar or EUR-Lex HEAD, the chatbot must say so and route the user to authoritative sources, NOT guess. See `feedback_negation_paradox_in_warnings.md` and the `ai_service.py` "NEVER INVENT IDENTIFIERS" rule.

## The 4-part structure

A CELEX number normally has **4 parts** concatenated with no separator:

```
Sector  Year   Type     Number
[1]     [4]    [1-2]    [4]
```

**Worked example — AI Act (Regulation (EU) 2024/1689)**:
```
3       2024   R        1689    →  32024R1689
```

- Sector **3** = Legal acts
- Year **2024** = adoption year
- Type **R** = Regulation
- Document number **1689** (4 digits, zero-padded if shorter)

**Worked example — Water Framework Directive (Directive 2000/60/EC)** (the example in the EUR-Lex spec):
```
3       2000   L        0060    →  32000L0060
```

## The 12 sectors (canonical list)

| Sector | Meaning | Typical content |
|---|---|---|
| **1** | Treaties | TEU, TFEU, Charter of Fundamental Rights, accession treaties |
| **2** | International agreements | EU-Mercosur ITA (`22026A00184`), CETA, EU-Canada SPA, EU-Japan EPA |
| **3** | Legal acts | Regulations, Directives, Decisions, Recommendations, Opinions adopted by EU institutions. **The largest sector and most common in Brubru.** |
| **4** | Complementary legislation | Acts not from Treaties or institutions (Council common positions, EP common positions, Member-State agreements) |
| **5** | Preparatory documents | Commission proposals (COM), Communications, Joint Communications, EESC opinions, CoR opinions, etc. |
| **6** | EU case-law | CJEU, General Court, Civil Service Tribunal judgments, opinions of the Advocate General |
| **7** | National transposition | National measures transposing a Directive — first 10 characters mirror the original Sector 3 CELEX, then 3-letter country code |
| **8** | References to national case-law concerning EU law | National court rulings citing EU law |
| **9** | Parliamentary questions | EP written + oral questions and answers |
| **0** | Consolidated texts | Continuously-updated consolidated versions (often used in conjunction with a date suffix) |
| **C** | Other documents published in OJ C series | OJ C-series-only documents that don't fit the numeric sectors |
| **E** | EFTA documents | EEA Joint Committee acts, EFTA Court rulings |

## Document type descriptors — Sector 3 (most common)

| Letter | Document type |
|---|---|
| **R** | Regulation (binding, directly applicable) |
| **L** | Directive (binding as to result, transposed by Member States — "L" for *Loi/Law*) |
| **D** | Decision (binding on those to whom addressed) |
| **H** | Recommendation (non-binding) |
| **A** | Opinion (non-binding) |
| **E** | Common position (CFSP) |
| **F** | Joint action (CFSP) |
| **G** | Common strategy (CFSP) |
| **M** | Merger / concentration decision |
| **O** | Other (typically internal guidelines, no addressee) |
| **Q** | Inter-institutional agreement |
| **X** | Resolution / position taken jointly |
| **B** | Budget |

## Document type descriptors — Sector 5 (preparatory)

| Letter pair | Meaning |
|---|---|
| **PC** | Proposal from the Commission (legislative proposal) |
| **DC** | Communication from the Commission |
| **JC** | Joint communication (Commission + HR/VP) |
| **IP** | Information / press release |
| **IR** | Information report |
| **AE** | Opinion of the European Economic and Social Committee |
| **AR** | Opinion of the Committee of the Regions |
| **AB** | Opinion of the European Central Bank |
| **AA** | Opinion of the Court of Auditors |
| **IG** | Inter-institutional agreement (preparatory) |
| **AS** | Recommendation (preparatory) |
| **XC** | Resolution (preparatory) |

**COM-to-CELEX conversion (the most common operation Brubru performs)**:

```
COM(2024) 206 final  →  52024PC0206  (Proposal)  OR  52024DC0206  (Communication)
```

The Brubru citation verifier tries **PC first, then DC** because most COM references in EU policy debate refer to legislative proposals.

## Document type descriptors — Sector 6 (case-law)

| Letter pair | Meaning |
|---|---|
| **CJ** | Court of Justice judgment |
| **TJ** | General Court judgment (Tribunal) |
| **CO** | Court of Justice order |
| **TO** | General Court order |
| **CC** | Court of Justice opinion (Advocate General) |
| **CN** | Notice of new case |

**Sector-6 numbering** uses the case number from the Court register, not a sequential CELEX number. Example: `62004TJ0201` = General Court judgment in case T-201/04 (the 201st case entered in 2004 in the General Court register).

## National transposition measures (Sector 7)

The first 10 characters match the original Sector 3 CELEX, with the leading `3` replaced by `7`. The following 3 characters are an ISO country code identifying which Member State enacted the transposition.

**Example**: a Spanish national measure transposing Directive 2000/60/EC (CELEX `32000L0060`) would have a Sector 7 CELEX starting `72000L0060ESP...`.

## Consolidated texts (Sector 0)

Consolidated texts have CELEX numbers starting with `0` and often include a date stamp, allowing point-in-time citation of a regulation or directive AS AMENDED.

**Example**: `02016R0679-20240101` = the GDPR consolidated as of 1 January 2024.

## Special-case quirks Brubru users hit

1. **REACH (Regulation (EC) No 1907/2006)**: CELEX `32006R1907`. Cellar 404s on this CELEX (legacy data quality), so the citation verifier falls back to EUR-Lex HEAD which returns 200. Both Brubru's verifier and CLAUDE.md's "EUR-Lex HEAD allowed" rule were designed around exactly this kind of edge case.
2. **GDPR consolidated**: `02016R0679-20240101` (with hyphen-date suffix) — the verifier treats this as a CELEX-shape ref and routes to Cellar with the suffix preserved.
3. **EU-Mercosur Council Decision**: `22026A00184` (Sector 2, year 2026, type A = agreement-related, number 00184) — different shape from the typical Sector 3 pattern; Brubru handles this in `eu_mercosur_trade_agreement.md`.
4. **EU Inc / 28th Regime**: COM(2026) 321 → `52026PC0321`. The deep-dive at `https://brubru.beresol.eu/eu-inc/` cites both the COM number and the CELEX form.

## How Brubru uses CELEX (operational)

| Layer | Use of CELEX |
|---|---|
| Knowledge guides (203 files) | Every QUICK FACTS section cites the CELEX of the anchor regulation. Required for every new guide. |
| `eu_laws` DB (28,513 OJ publications) | Primary key is CELEX. Search via TSVECTOR; lookup by CELEX is O(log n). |
| Citation verifier (`services/citation_verifier.py`) | Regex `\b[1-9]\d{4}[A-Z]{1,2}\d{4}\b` extracts CELEX from any free text; per-ref Cellar + EUR-Lex HEAD verification with DB cache (TTLs 30d ok / 24h broken / 1h unknown). |
| Catalan corpus (28,513 Formex V4 XML) | Each Formex file is named by its CELEX; output HTML at `frontend/public/legislacio-ue-catala/{celex}/index.html`. |
| MCP `search_eu_legislation` | Returns CELEX + title + document_type, exposed to external LLM agents (GovClipping et al). |
| Daily brief headlines | Headlines naming a CELEX are auto-linkified by `_linkify_legislation()` in `ai_service.py`. |
| System prompt rule | "NEVER INVENT IDENTIFIERS" — describes the FORMAT (`PE-numbers: PE followed by digits and a sub-version`) without naming specific values, after the negation-paradox lesson of 27-28 April 2026. |

## Adjacent identifier systems (related but NOT CELEX)

These appear alongside CELEX in policy work and Brubru must NOT confuse them:

- **OJ reference**: `OJ L 169, 25.6.2024, p. 1` — the publication in the Official Journal. Different from CELEX. The Brubru `eu_laws` table stores both.
- **OEIL procedure number**: e.g. `2021/0106(COD)` — the EP/Council legislative-procedure tracker reference. Different from CELEX (a procedure has many CELEX numbers across stages: COM proposal, Council common position, final Regulation).
- **COM number**: `COM(2024) 206 final` — a Commission document number. Convertible to a Sector 5 CELEX (PC or DC).
- **PE number**: `PE 760.987` — an internal EP parliamentary-document number (committee reports, opinions, amendments tabled). Not a CELEX.
- **A-/T-/B-numbers**: EP plenary documents — A = report, T = adopted text, B = motion for resolution. Not a CELEX.
- **SEC / SWD / C / IP / SPEECH / FS / QANDA / MEX**: Commission internal document numbers. SEC = Secretariat-General, SWD = Staff Working Document, C = Commission decisions, IP = Press release, etc. Not CELEX directly but some convertible.

## Validation rules Brubru enforces

1. **Shape check**: must match the regex `\b[1-9]\d{4}[A-Z]{1,2}\d{4}\b` (or the consolidated `0YYYY...` shape, or the international-agreements `2YYYY...` shape).
2. **Cellar verification**: send a HEAD-equivalent GET with `Accept: application/xhtml+xml` AND `Accept-Language: en`. 200 = ok. 4xx = unknown.
3. **EUR-Lex HEAD fallback**: only for CELEX-shape refs; if Cellar returns unknown, try EUR-Lex HEAD. 200 = ok.
4. **DB cache**: results stored in `citation_verifications` table with PK=ref. TTL: 30 days for OK, 24h for broken, 1h for unknown.
5. **Year sanity check**: extract YYYY; if year is in the future (>current year + 1), flag as suspicious. (E.g. a 2027 CELEX in April 2026 is impossible unless it's a forecast.)
6. **Brubru chatbot answer rule**: when citing CELEX in a chat response, prefer the format `Regulation (EU) 2024/1689 (CELEX 32024R1689)` — both human-readable form and the canonical identifier in one citation.

## Cross-references

- `services/citation_verifier.py` + `models/citation_verification.py` + `migrations/040_citation_verifications.sql` — the verifier infrastructure
- `quality_framework.md` — citation verifier is part of Sprint 1a (26 April 2026)
- `feedback_cellar_needs_accept_language.md` — the Cellar Accept-Language gotcha
- `feedback_negation_paradox_in_warnings.md` + `feedback_seed_fixtures_contaminate_prod.md` — why Brubru describes the FORMAT and never names specific values in warnings
- `eu_regulation_linguistic_patterns.md` — drafting conventions of EU regulations (modal verbs, recital structure)
- `data/LEG_2025-11/` — 28,513 Formex V4 XML files, each named by CELEX
- CLAUDE.md "Canonical Numbers of the EU Legal Corpus" section — LEG_2025-11 reference numbers (8,710 distinct laws / 28,513 OJ publications / 61,219 translatable XML files)
