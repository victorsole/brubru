# EU Who-is-Who: the Official Directory of EU Staff

## QUICK FACTS
- **What it is:** The **EU Who-is-Who** is the Publications Office of the European Union's official, authoritative directory of all EU institutions, bodies and their staff. It maps every institution to its internal organisation, and every unit to the person who heads it.
- **Published by:** Publications Office of the European Union (OP), an interinstitutional body that serves all EU institutions. See `eu_publications_office_and_open_data.md`.
- **Web portal:** `op.europa.eu/en/web/who-is-who` (interactive searchable interface covering all institutions).
- **Coverage:** European Parliament (EP), European Council (EURCOU), Council of the EU (CONSIL), European Commission with all 35 DGs and services (COM), Court of Justice / CURIA, European Central Bank (ECB), European Court of Auditors (ECA), European External Action Service (EEAS), European Economic and Social Committee (EESC), Committee of the Regions (CoR), European Investment Bank (EIB), European Investment Fund (EIF), European Ombudsman (OMB), European Data Protection Supervisor (EDPS), and EU Agencies and Other Bodies (AGEN_OTH).
- **PDF dumps:** 15 institution-specific PDFs, one per institution code: `op.europa.eu/webpub/wiw/pdf/EUWhoiswho_{INST}_EN.pdf` where `{INST}` is one of `EP`, `EURCOU`, `CONSIL`, `COM`, `CURIA`, `ECB`, `ECA`, `EEAS`, `EESC`, `COR`, `EIB`, `EIF`, `OMB`, `EDPS`, `AGEN_OTH`. These PDFs are the canonical data source (the scraped JSON-LD web interface captures address lines and filter labels rather than people). The OP publishes updated PDFs approximately quarterly.
- **Update lag:** The directory reflects appointments as of the PDF publication date, typically a few weeks behind the most recent cabinet reshuffle or Director-General appointment. Senior posts (Commissioner cabinets, Secretary-General, Directors-General) tend to be updated within one publication cycle; unit heads at lower levels may lag by one to two quarters.
- **Hierarchy:** organisation (institution) → Directorate-General or service → directorate → unit → head of unit / official → function and, where available, e-mail address.
- **Brubru ingestion:** Brubru parses the PDF dumps and stores them in two JSON files in the knowledge base: `whoiswho_org.json` (the full DG → directorate → unit → head tree used for org-chart lookups and card displays; Commission: 35 DGs, 240 directorates, 1,055 units, 931 with e-mail) and `whoiswho_officials.json` (top-5 named officials per DG for quick chat retrieval; 171 senior officials across Commission DGs). The cron re-ingests monthly on the 1st of each month at 02:00 UTC.
- **Cross-links:** `eu_publications_office_and_open_data.md`, `commission_guide.md`, `european_commission_who_does_what.md`, `european_council_and_council_personnel.md`, `european_parliament_personnel.md`.

---

## What EU Who-is-Who Is

EU Who-is-Who is the central reference for EU staff. It is not an employee registry or a pay-roll system; it is an organisational directory that shows, for each institution:

1. The **internal structure**: directorates-general, services, directorates, units and equivalent sub-divisions.
2. The **name, title and function** of each identified post-holder.
3. The **official e-mail address** of heads of unit and above (where the institution publishes one).

The directory is produced and maintained by the Publications Office, which has an obligation under the Interinstitutional Agreement on Better Law-Making and successive Staff Regulations to maintain this transparency resource on behalf of all EU institutions. It is freely accessible to the public without registration.

---

## Coverage by Institution

### European Parliament (EP)
Covers the Secretariat-General, all parliamentary committees, political group secretariats and administrative services. MEPs themselves are listed under the EP's own Members database (see `european_parliament_personnel.md`) rather than through Who-is-Who, which focuses on administrative staff.

### European Council and Council of the EU
The European Council Secretariat (EURCOU) and the General Secretariat of the Council (CONSIL) each have separate PDF dumps. For Council Presidency staff and Working Party chairs, see `european_council_and_council_personnel.md`.

### European Commission (COM)
The Commission entry is the most detailed section of Who-is-Who. It covers all 35 Directorate-Generals and standalone services, including the Secretariat-General (REFOR in the Brubru data), DG AGRI, DG CLIMA, DG COMP, DG CONNECT, DG ECFIN, DG EMPL, DG ENER, DG ENV, DG FISMA, DG GROW, DG HOME, DG JUST, DG MARE, DG MOVE, DG REFORM, DG RTD, DG SANTE, DG TAXUD, DG TRADE and the executive agencies. Each Commissioner's cabinet is listed separately under the relevant Commissioner's name.

For policy-area mapping (which DG handles which regulation), see `european_commission_who_does_what.md` and `commission_guide.md`.

### Court of Justice (CURIA)
Covers the Court of Justice, the General Court and the Civil Service Tribunal. Judges, Advocates-General and registry officials are all included.

### European Central Bank (ECB)
Covers the Executive Board, the Governing Council secretariat and ECB departmental heads. Does not include national central bank staff.

### European Court of Auditors (ECA)
Members of the Court, chambers, audit directorates and supporting services.

### European External Action Service (EEAS)
Central services in Brussels plus EU Delegations worldwide, including Heads of Delegation.

### Advisory and Consultative Bodies (EESC and CoR)
The Economic and Social Committee (EESC) and the Committee of the Regions (CoR) each have a separate PDF covering their secretariat-general, directorates and units.

### Financial Institutions (EIB and EIF)
The European Investment Bank and the European Investment Fund are covered separately. Board members, directors and senior management are listed.

### Independent Bodies (OMB and EDPS)
The European Ombudsman's office and the European Data Protection Supervisor each have a dedicated PDF, given their institutional independence from the Commission.

### Agencies and Other Bodies (AGEN_OTH)
A single PDF covering all decentralised agencies (EMA, EFSA, EEA, ECHA, EUDA, EIGE, Cedefop, EUAA, FRA and others) and joint undertakings. This is a consolidated dump; each agency's own website carries a more detailed organogram.

---

## URL Patterns

### Interactive Web Interface
`https://op.europa.eu/en/web/who-is-who`

The web interface allows free-text search by name or function, and browsing by institution. It is the most up-to-date view but is rendered via a JavaScript-heavy SPA that blocks automated curl/fetch requests (the Publications Office WAF returns HTTP 403 to non-browser clients). Use a real browser to access it.

Browse to a specific institution:
`https://op.europa.eu/web/who-is-who/organization/{slug}`

Where `{slug}` is the institution's path token, for example:
- `european-commission`
- `european-parliament`
- `council-of-the-eu`
- `court-of-justice`
- `eeas`
- `agencies-and-other-bodies`

### Machine-Readable PDF Dumps
`https://op.europa.eu/webpub/wiw/pdf/EUWhoiswho_{INST}_EN.pdf`

Substituting `{INST}` with one of the 15 institution codes listed in the QUICK FACTS block above, for example:

| Code | Institution |
|------|-------------|
| `COM` | European Commission |
| `EP` | European Parliament |
| `CONSIL` | Council of the EU |
| `EURCOU` | European Council |
| `CURIA` | Court of Justice of the EU |
| `ECB` | European Central Bank |
| `ECA` | European Court of Auditors |
| `EEAS` | European External Action Service |
| `EESC` | Economic and Social Committee |
| `COR` | Committee of the Regions |
| `EIB` | European Investment Bank |
| `EIF` | European Investment Fund |
| `OMB` | European Ombudsman |
| `EDPS` | European Data Protection Supervisor |
| `AGEN_OTH` | Agencies and Other Bodies |

The PDFs are the canonical data source used by Brubru's ingest pipeline. Brubru fetches them with the `ingest_whoiswho_pdfs.py` script (using `pypdf` for text extraction) rather than scraping the web interface, precisely because the PDF data is clean and structured while the web interface's JSON-LD output mixes address fields and navigation labels with personnel records.

---

## How Freshness Works

The Publications Office updates the PDF dumps approximately quarterly, in practice around every three to four months. The timeline from appointment to directory listing is typically:

1. **Appointment decision taken** (by College, Parliament Bureau, Council, etc.)
2. **Published in the Official Journal or press release** (days to weeks later)
3. **OP staff update the directory** (weeks to one quarter later)
4. **New PDF generated and published** (batch update, not real-time)

As a result:

- **Directors-General and Secretaries-General:** Updated within one publication cycle after their appointment. A newly-appointed DG head will usually appear in the next quarterly PDF.
- **Deputy Directors-General and Directors:** Similar lag of one quarter or less.
- **Heads of unit:** May lag one to two publication cycles, especially if the unit was recently restructured. Commission internal reorganisations that merge or split units are not always reflected in the directory immediately.
- **Commissioner cabinets:** Cabinet compositions after an investiture vote (as in late 2024 for the von der Leyen II Commission) are typically captured in full within one or two publication cycles.

**Cabinet reshuffles of 2024-2025:** The second von der Leyen Commission took office on 1 December 2024 after prolonged investiture hearings. Several commissioner portfolios were restructured and some cabinet chiefs replaced compared to the 2019-2024 term. Brubru's data reflects the state of the PDF at the time of the most recent ingest. Always verify a senior appointment against the institution's own press release or the Official Journal for the most current information.

---

## How Brubru Uses Who-is-Who

### Chat Lookups
When a user asks "Who is the head of unit for DG GROW's Single Market for Financial Services?" or "Who is the Director-General of DG ENER?", Brubru queries `whoiswho_org.json` (the full structural tree) or `whoiswho_officials.json` (the senior officials index). The Commission data covers:

- 35 Directorate-Generals and standalone services
- 240 directorates with director names
- 1,055 units with head names and e-mail addresses (931 with e-mail populated)
- 171 senior officials at Director-General / Deputy Director-General level indexed for fast retrieval

### Stakeholder Mapping
`backend/services/strategy/stakeholder_map.py` uses the Who-is-Who data as one of its graph sources. When building a stakeholder map for a legislative procedure, the graph engine edges officials to their DG and the DG to the relevant policy area, enabling the chat to surface decision-relevant contact points.

### Permanent Representations
`permanent_representations.py` (EU Calendar institutions module) cross-references Who-is-Who data to enrich calendar event records with institutional context.

### Monthly Refresh Cron
Brubru's cron job (1st of each month, 02:00 UTC) calls `ingest_whoiswho_pdfs.py --apply` to re-download the 15 PDFs and repopulate `whoiswho_org.json` and `whoiswho_officials.json`. This means Brubru's directory data is typically no more than one month older than the most recent OP publication.

---

## Practical Caveats

**Data lag is structural.** The quarterly PDF cadence is inherent to how the Publications Office produces the directory. No automated tool (including Brubru) can provide real-time staff data unless it scrapes individual institution websites, which Brubru does not do for the Who-is-Who pipeline. When pinpoint-current information is required (for instance, confirming whether a specific unit head was replaced last week), verify directly on the institution's own organogram page or via a news search.

**Reorganisations outpace the directory.** The Commission reorganises DGs and units through Commission Decisions, which are published in the Official Journal. Between two quarterly PDFs, a unit may have been renamed, merged or abolished. If a unit cannot be found in the Brubru data but a name is known from other sources, search by person rather than by unit title.

**The `AGEN_OTH` PDF is an aggregate.** It compresses all decentralised agencies into a single document. For detailed organograms of individual agencies (EMA, EFSA, ECHA, etc.), the agency's own website under `.europa.eu` is the primary source.

**E-mail addresses are work addresses, not personal.** EU Who-is-Who publishes official institutional e-mail addresses in the format `Firstname.SURNAME@institution.europa.eu`. These are work addresses published for official business communication. They are not personal contact channels and not intended for unsolicited outreach.

**Commissioner names vs cabinet names.** Who-is-Who lists the Commissioner (as a political figure) and their cabinet separately. The Commissioner's title is listed under the College section; the cabinet chief and advisers appear under a cabinet sub-entry. Brubru's `whoiswho_officials.json` captures senior Commission officials (Secretaries-General, Directors-General and their deputies); cabinet members are stored in the organisation tree rather than the officials index.

---

## Related Guides

- `eu_publications_office_and_open_data.md`: full overview of the Publications Office portfolio including the Official Journal, EUR-Lex, TED, CORDIS and data.europa.eu
- `commission_guide.md`: how to engage with the Commission, its DGs and its stakeholder consultation process
- `european_commission_who_does_what.md`: the master map of which DG/service/executive agency handles which policy area
- `european_council_and_council_personnel.md`: Council Presidency, COREPER, Working Party chairs and senior Council Secretariat staff
- `european_parliament_personnel.md`: MEPs, committee chairs, rapporteurs and political group leadership
