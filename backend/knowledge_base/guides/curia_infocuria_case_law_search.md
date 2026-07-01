# Searching CJEU Case Law: CURIA, InfoCuria, Reports of Cases, Fact Sheets

## QUICK FACTS
- **Three distinct search surfaces for CJEU case law**: (a) **CURIA** (`curia.europa.eu`): the Court's own portal, best for fact sheets by subject matter, monthly digests, yearly selections of leading judgments, press releases, and context about pending proceedings; (b) **InfoCuria** (`infocuria.curia.europa.eu/tabs/affair`): the granular case-level search engine, best for locating a specific judgment by case number, ECLI, party names, judge-rapporteur, Advocate General, date range, procedure type, or document type; (c) **EUR-Lex JURI sector** (`eur-lex.europa.eu/collection/case-law.html`): best for linking case law to the legislation it interprets (CELEX joins), ELI/ECLI resolution, and full-text CELEX-sector-6 citations.
- **InfoCuria is the primary search tool for practitioners.** The legacy `curia.europa.eu/juris/` URLs now redirect automatically to InfoCuria. Search by: case number (e.g. C-311/18), ECLI (e.g. `ECLI:EU:C:2020:559`), party name (e.g. "Facebook Ireland"), judge-rapporteur, Advocate General, language of the case, type of procedure (preliminary ruling, direct action, appeal), type of document (judgment, order, opinion, AG opinion, press release).
- **ECLI is the cite-safe identifier**: `ECLI:EU:C:{year}:{seq}` for the Court of Justice, `ECLI:EU:T:{year}:{seq}` for the General Court. See `ecli_european_case_law_identifier.md`. CELEX sector-6 (e.g. `62017TJ0160`) is the catalogue identifier. EUR-Lex `legal-content` URLs via ECLI (`?uri=ecli:ECLI:EU:C:2020:559`) are stable and WAF-free. See `celex_number_format.md`.
- **Reports of Cases** (the authoritative published collection): pre-2012 decisions appear in the **European Court Reports (ECR)**; from 2012 onwards the collection is titled **Reports of Cases** and is published digitally. Both are accessible on EUR-Lex. The standard citation is: `Case C-131/12 Google Spain [2014] ECLI:EU:C:2014:317`.
- **JURE database** (`e-justice.europa.eu/content_jure_database`): a European Judicial Network database of **national court decisions that apply EU law**, including preliminary-ruling follow-up by Member-State courts. Distinct from CURIA/InfoCuria which cover only EU courts.
- **Comparison table: which tool for which query**

| Task | Tool |
|---|---|
| Find a specific judgment by case number or ECLI | InfoCuria (`/tabs/affair`) |
| Browse judgments on a subject (e.g. data protection) | CURIA fact sheets + InfoCuria subject filter |
| Cite a judgment in a document (stable URL) | EUR-Lex `?uri=ecli:…` or ELI |
| Link case law to the regulation it interprets | EUR-Lex JURI sector (CELEX join) |
| Find national court rulings on EU law | JURE (e-justice.europa.eu) |
| Get a press-release summary of a landmark ruling | CURIA press room |
| Monthly digest of new case law | CURIA case-law digest |

---

## CURIA: the Court's own portal (curia.europa.eu)

CURIA (`https://curia.europa.eu`) is the official institutional website of the Court of Justice of the European Union. It serves as context and discovery hub rather than a query-by-field search engine.

**What CURIA offers for case-law research:**

**Fact sheets by subject matter.** CURIA publishes thematic fact sheets covering major areas of case law (citizenship, competition, consumer protection, data protection, environmental law, free movement, intellectual property, etc.). Each fact sheet is a curated summary of landmark judgments with links to full texts. Fact sheets are updated periodically and are an efficient entry point when a practitioner needs a subject-matter overview rather than a specific case.

**Monthly digest.** Each month CURIA publishes a digest of newly delivered judgments and Advocate General opinions. The digest is organised by court (Court of Justice and General Court) and by type of procedure. It is useful for systematic monitoring of CJEU output without running a manual InfoCuria query each week.

**Yearly selection of leading judgments.** At the end of each judicial year CURIA publishes an annotated selection of the year's most significant decisions, with brief explanatory notes. This is the fastest way to identify judgments that have attracted institutional attention.

**Press releases.** For Grand Chamber and other high-profile rulings, CURIA publishes same-day press releases that summarise the operative part in plain language. Press releases are issued in the 24 EU official languages (pending translation timelines).

**Pending cases register.** The `Requests for a preliminary ruling` section of CURIA lists pending preliminary references by Member State and subject, which practitioners can use to anticipate forthcoming rulings.

The case-law **search function** on `curia.europa.eu` now redirects to InfoCuria. Direct database queries must go via `infocuria.curia.europa.eu`.

---

## InfoCuria: granular case-level search (infocuria.curia.europa.eu)

**Main search entry point:** `https://infocuria.curia.europa.eu/tabs/affair`

InfoCuria is the primary database interface for case-level searching. It exposes fields not available through EUR-Lex or the Cellar SPARQL endpoint.

**Advanced search fields available in InfoCuria:**

| Field | Examples | Notes |
|---|---|---|
| Case number | C-311/18, T-160/17 | Use the register number, not the ECLI sequence number |
| ECLI | ECLI:EU:C:2020:559 | Full match |
| Party name | "Facebook Ireland", "Schrems" | Searches both applicant and defendant |
| Type of court | Court of Justice, General Court | Filter by institution |
| Type of procedure | Preliminary ruling, Direct action, Appeal, Staff case | 10+ procedure types |
| Type of document | Judgment, Order, Opinion, AG Opinion, Press release | Filter document type |
| Date of delivery | Date range (from / to) | Useful for monitoring |
| Judge-rapporteur | Surname search | Identifies rulings assigned to a specific judge |
| Advocate General | Surname search | Identifies AG opinions by author |
| Language of the case | Any EU official language | The procedural language in which the case was conducted |
| Subject matter | Free text + controlled terms | Broad subject filter; combine with party names for precision |

**InfoCuria URL anatomy for a specific case.** When you open a case on InfoCuria the URL takes the form:
```
https://infocuria.curia.europa.eu/juris/liste.jsf?language=en&jur=C,T,F&num=C-311/18
```
- `jur`: C (Court of Justice), T (General Court), F (Civil Service Tribunal, historical)
- `num`: the register number

A direct link to a specific document within the case uses a longer URL including a `docid` parameter. For persistent linking, prefer the EUR-Lex ECLI URL (see below), which is more stable than InfoCuria's internal `docid` parameters.

**Language of the case** is a field that EUR-Lex does not expose. In preliminary references, the language of the case is always the language of the referring court (not French, which is the Court's internal deliberation language). For advocates advising on references from non-French courts, the language of the case determines the language of the registry correspondence.

---

## Reports of Cases and European Court Reports: the authoritative text

**Pre-2012: European Court Reports (ECR).** Judgments from 1954 to 2011 were published in the **European Court Reports**, a bound paper collection. Citations from this period typically appear as: `Case C-131/12 Google Spain (2014) I-xxxx` with a Roman-numeral volume reference. The ECR is digitised and searchable on EUR-Lex.

**From 2012: Reports of Cases.** Since 2012 the authoritative collection is titled **Reports of Cases** and is published exclusively in digital format on EUR-Lex. The Reports of Cases text is identified by CELEX (sector 6) and is the formally authoritative version of a judgment for citation in proceedings and academic work.

**Citation format** (Brubru standard):
- Modern: `Case C-131/12 Google Spain SL v AEPD, ECLI:EU:C:2014:317`
- With Reports reference (where available): `Case C-131/12 Google Spain [2014] ECR I-0000`

Brubru prefers the ECLI citation because it is self-contained (year and sequential number), machine-readable, and links directly to the EUR-Lex text.

**EUR-Lex URL for a judgment via ECLI:**
```
https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=ecli:ECLI:EU:C:2014:317
```
This URL is stable, WAF-free, and returns the full text of the judgment. It is the recommended linking form for Brubru chat answers.

**EUR-Lex URL for a judgment via CELEX (sector 6):**
```
https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:62012CJ0131
```
Sector-6 CELEX anatomy: `6` + year + court type (`CJ` = Court of Justice, `TJ` = General Court) + case number (4 digits, zero-padded). See `celex_number_format.md`.

---

## JURE: national case law applying EU law

JURE (`https://e-justice.europa.eu/content_jure_database`) is a database maintained by the European Judicial Network in civil and commercial matters. It indexes **national court decisions that apply, interpret, or reference EU law**, including:

- Follow-up judgments by national courts after CJEU preliminary rulings
- National application of EU directives (transposition disputes, proportionality assessments)
- National courts' own interpretation of EU law in the absence of a CJEU ruling
- Cases where national courts decided NOT to make a preliminary reference

JURE is distinct from InfoCuria and EUR-Lex: it indexes cases decided by courts in the 27 Member States, not by the EU courts. It is the starting point for questions such as "how have Spanish courts applied the Consumer Rights Directive?" or "which national courts have followed Schrems II on data transfers?"

For infringement proceedings and the Article 258 TFEU pipeline (Commission v Member States for non-transposition), see `eu_law_application_monitoring.md`.

---

## Decision tree: which tool for which query

Use this tree when a Brubru user asks a CJEU case-law question:

1. **Known case name or number** (e.g. "Schrems II", "C-311/18"): go to InfoCuria `tabs/affair`, search by case number or party name. Extract the ECLI. Link via EUR-Lex `?uri=ecli:…`.

2. **Subject-matter survey** (e.g. "leading cases on State aid and sport"): start with the CURIA fact sheet for the relevant subject. If no fact sheet exists, search InfoCuria with subject-matter filter + date range. Cross-check with EUR-Lex JURI sector collection view.

3. **Monitoring new judgments**: subscribe to CURIA monthly digest or run a periodic InfoCuria query filtered by delivery date (current month) and court type.

4. **Linking a judgment to legislation** (e.g. "which CJEU cases interpret Article 17 of the Copyright Directive"): use EUR-Lex JURI sector with the directive's CELEX as the cited-work filter. The Cellar SPARQL endpoint also supports this join (see `cellar_semantic_repository.md` when available; interim reference in `finding_and_citing_eu_law.md`).

5. **National court application of EU law**: use JURE, not InfoCuria.

6. **AG opinion before the judgment**: InfoCuria, document type = "Opinion of the Advocate General". The AG opinion is delivered before the judgment and is not binding but is frequently cited in briefings.

7. **Press-release summary of a Grand Chamber ruling**: CURIA press room (`curia.europa.eu/jcms/jcms/j_6/en/`). Same-day, plain-language.

---

## Brubru chat usage patterns

When a user asks about a CJEU judgment, Brubru must:

1. **Cite the ECLI**, not a paraphrase or a case name alone. Format: `Case C-XXX/YY [short name], ECLI:EU:C:{year}:{seq}`.
2. **Provide the EUR-Lex ECLI link**: `https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=ecli:ECLI:EU:{court}:{year}:{seq}`. Do not generate raw `legal-content` URLs without an ECLI anchor (they vary by jurisdiction parameter and can 404).
3. **Never invent an ECLI or CELEX.** If the identifier cannot be confirmed, direct the user to InfoCuria (`https://infocuria.curia.europa.eu/tabs/affair`) or the EUR-Lex case-law search (`https://eur-lex.europa.eu/search.html?scope=EURLEX&type=quick&lang=en&andText0=&orText0=&notText0=&SUBDOM_INIT=CASE_LAW`). The same anti-hallucination rule that applies to CELEX numbers for legislation applies to ECLI numbers for case law. See `finding_and_citing_eu_law.md` and the `ai_service.py` "NEVER INVENT IDENTIFIERS" rule.
4. **Distinguish Court of Justice from General Court.** "CJEU" generically covers both; for a specific ruling, state the court clearly. General Court handles: competition (cartels, mergers, State aid appeals from Commission decisions), intellectual property (EUIPO appeals), staff cases. Court of Justice handles: preliminary references from national courts, direct actions against Member States (Article 258 TFEU), appeals from General Court.
5. **For subject-matter overviews** (e.g. "what does CJEU case law say on algorithmic profiling"): cite 2-3 landmark cases with ECLIs, link to the relevant CURIA fact sheet if one exists, and note the date of the most recent ruling to signal currency.
6. For the landmark Commission v Hungary (LGBTIQ) Article 2 TEU judgment see `cjeu_hungary_lgbti_article2_judgment.md`.

---

## Cross-references

- `ecli_european_case_law_identifier.md`: the ECLI identifier in full (5-part structure, EU court codes, linking)
- `celex_number_format.md`: sector-6 CELEX for case law; how the CELEX is derived from the case register number
- `finding_and_citing_eu_law.md`: where EU law lives (Cellar), all identifier systems, citation standards
- `eu_law_application_monitoring.md`: Article 258 TFEU infringement proceedings; Commission monitoring reports; Article 260 pecuniary penalties after non-compliance with a CJEU judgment
- `cjeu_hungary_lgbti_article2_judgment.md`: landmark 2026 Grand Chamber ruling on Article 2 TEU as a directly justiciable infringement anchor
- `cjeu_structure_and_procedures.md` (planned): composition of the Court, General Court, chambers, Grand Chamber; preliminary references; direct actions; appeals; interim measures
- `cellar_semantic_repository.md` (planned): Cellar SPARQL queries for joining case law to legislation (cited-work relationships in the CDM ontology)
