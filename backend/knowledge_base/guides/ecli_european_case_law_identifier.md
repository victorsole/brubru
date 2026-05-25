# ECLI — the European Case-Law Identifier

## QUICK FACTS
- **What it is**: the **European Case-Law Identifier (ECLI)** is a uniform 5-part identifier for **judicial decisions** (EU and national), making case-law easier to find, cite and link. Introduced by Council Conclusions 2011/C 127/01.
- **Shape**: `ECLI:{country}:{court}:{year}:{number}` — five parts, each separated by a colon.
- **It is NOT a CELEX**. Case-law also has a CELEX (sector 6, e.g. `62017TJ0160`), but the ECLI's final part is a **court sequential number**, not the CELEX. Brubru must keep the two distinct.
- **Why Brubru cares**: chat answers about CJEU judgments should cite the ECLI; it is the cleanest case-law link and is searchable via the European e-Justice portal.
- **Source spec**: https://eur-lex.europa.eu/content/help/eurlex-content/ecli.html (Publications Office).

## The 5 parts
| Part | Content | Example |
|---|---|---|
| 1 | Literal `ECLI` | `ECLI` |
| 2 | Country code (2 chars) | `EU` (or a Member-State code) |
| 3 | Court code (1–7 chars) | `C`, `T`, `F` |
| 4 | Year of the decision (4 digits) | `2014` |
| 5 | Sequential number (max 25 chars, dots allowed) | `317` |

### EU court codes (part 3)
- **`C`** — Court of Justice
- **`T`** — General Court (Tribunal)
- **`F`** — Civil Service Tribunal (dissolved 2016; historical decisions retain `F`)

The fifth part is a sequential number **restarted every year and specific to each court** — explicitly **not** the CELEX number.

## Worked examples
| ECLI | Decision |
|---|---|
| `ECLI:EU:C:1998:27` | 27th Court of Justice decision of 1998 |
| `ECLI:EU:F:2010:80` | 80th Civil Service Tribunal decision of 2010 |
| `ECLI:EU:T:2012:426` | 426th General Court decision of 2012 |
| `ECLI:EU:C:2014:317` | Google Spain (right to be forgotten) |

## Linking with an ECLI
ECLI links follow the same EUR-Lex stem as other identifiers (note the lowercase `ecli:` prefix in the `uri` parameter):
- **Text view**: `https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=ecli:ECLI:EU:C:2016:718`
- **XML notice**: `https://eur-lex.europa.eu/legal-content/EN/TXT/XML/?uri=ecli:ECLI:EU:F:2016:177`
- Search by ECLI on the **European e-Justice portal** ECLI search engine.

## Case-law CELEX vs ECLI (do not confuse)
A judgment has both:
- **CELEX (sector 6)**: `62017TJ0160` = General Court (`TJ`) judgment, case T-160/17, entered 2017. Sector-6 numbering uses the **court case number**, not a sequential CELEX.
- **ECLI**: `ECLI:EU:T:2019:...` — court + year + sequential decision number.
Brubru cites the **ECLI** for readability and the CELEX for catalogue lookups. See `celex_number_format.md` (Sector 6).

## How Brubru uses ECLI
- When a chat answer references a CJEU/General Court judgment, cite the ECLI and, where useful, the case name (e.g. "Google Spain, ECLI:EU:C:2014:317").
- Never fabricate an ECLI; if it cannot be verified, route the user to the e-Justice portal or EUR-Lex case-law search. Same anti-hallucination discipline as CELEX.

## Cross-references
- `finding_and_citing_eu_law.md` — the data hub
- `celex_number_format.md` — Sector 6 (case-law) CELEX numbering
- `eli_european_legislation_identifier.md` — the legislation equivalent
- `docs/api/eu_legal_data_access.md` — engineering reference
