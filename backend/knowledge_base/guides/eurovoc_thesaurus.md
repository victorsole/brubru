# EuroVoc — the EU's Multilingual Subject Thesaurus

## QUICK FACTS
- **What it is**: **EuroVoc** is the EU's official **multilingual, multidisciplinary thesaurus** — the controlled vocabulary used to classify EU documents by subject. It covers the fields of EU activity (politics, law, economics, trade, environment, etc.) and is maintained by the Publications Office.
- **Why it matters for Brubru**: EuroVoc concepts are the **subject tags** attached to every law in Cellar (`work_is_about_concept_eurovoc`) and to EP Open Data datasets. They let Brubru group laws by topic, power "related laws" suggestions, and tag knowledge guides for retrieval (`dcat:theme`).
- **Concept URIs**: each concept is a stable URI, e.g. `http://eurovoc.europa.eu/2517` (data protection), `http://eurovoc.europa.eu/4651` (personal data). Concepts have **broader / narrower / related** relationships (SKOS).
- **Where it lives**: the **EU Vocabularies** site (`op.europa.eu/en/web/eu-vocabularies`), alongside the authority tables (country, language, corporate-body, treaty, resource-type) and the Common Data Model. Queryable via the Cellar/Publications-Office SPARQL endpoint.
- **Source**: https://op.europa.eu/en/web/eu-vocabularies/dataset/-/resource?uri=http://publications.europa.eu/resource/dataset/eurovoc

## How EuroVoc is structured
- **Domains and microthesauri**: 21 domains (e.g. *04 politics*, *12 law*, *10 European Union*, *52 environment*) subdivided into microthesauri.
- **Concepts**: each has a **preferred label** per language (24 languages), **alternative labels** (synonyms/entry terms), and **SKOS relations**: `skos:broader`, `skos:narrower`, `skos:related`.
- **Stable URIs**: `http://eurovoc.europa.eu/{id}` — language-independent; the label is resolved per language.

## How it connects to the legal corpus
A single Cellar SPARQL query on a CELEX returns its EuroVoc concepts via `cdm:work_is_about_concept_eurovoc`. Example — GDPR (`32016R0679`) carries 9 EuroVoc concepts. This is how "what is this law about?" and "what else covers this topic?" are answerable without reading the text.

Related classification systems on the same corpus (distinct from EuroVoc):
- **Subject-matter** authority codes (`…/authority/subject-matter/INFO`, `PROT`, `ELSJ`).
- **Directory codes** (the 20-chapter directory of legal acts in force).

## How Brubru uses (and should use) EuroVoc
- **Guide tagging**: new/updated guides carry 2–3 EuroVoc concept URIs (in QUICK FACTS or frontmatter) so `services/vocabularies/glossary_injector.py` can surface label glossaries in chat context and supply `dcat:theme` values for the DCAT-AP self-catalogue. Look up similar guides' IDs with `mcp__brubru__search_knowledge_guides`; **never invent a EuroVoc ID** — leave the field empty if unsure.
- **Related-laws / topic grouping**: query `get_acts_by_eurovoc` on the Cellar client to pull all acts under a concept.
- **Search enrichment**: EuroVoc keywords filter the EP Open Data dataset catalogue and the `data.europa.eu` portal.

## Example concept tags (verified URIs — copy, don't invent)
| Concept | URI |
|---|---|
| data protection | `http://eurovoc.europa.eu/2517` |
| personal data | `http://eurovoc.europa.eu/4651` |
| (look up others via the EU Vocabularies SPARQL endpoint) | |

## Cross-references
- `finding_and_citing_eu_law.md` — the data hub (Cellar, CDM, authority tables)
- `celex_number_format.md` — the identifier EuroVoc concepts attach to
- `docs/api/eu_legal_data_access.md` — engineering reference (CDM `work_is_about_concept_eurovoc`, authority tables)
- `services/vocabularies/glossary_injector.py` — how labels reach chat context
- `memory/reference_eu_vocabularies.md` — Brubru's EU Vocabularies integration notes
