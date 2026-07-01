# EP Public Register of Documents (RegistreWeb)

## QUICK FACTS
- **URL:** `https://www.europarl.europa.eu/RegistreWeb/en/home/welcome.htm`
- **What it is:** The European Parliament's official register of documents under Regulation (EC) No 1049/2001 and Article 15(3) TFEU, giving every EU citizen and legal person the right of access to EP documents.
- **Coverage:** All EP documents since 3 December 2001 (the date Regulation 1049/2001 entered into force). Documents predating that cut-off fall under the EP's historical archives.
- **Legal basis:** Article 15(3) TFEU (formerly Article 255 TEC); Regulation (EC) No 1049/2001 (CELEX 32001R1049; OJ L 145, 31.5.2001); Article 42 of the Charter of Fundamental Rights of the EU.
- **Who can request:** Any EU citizen; any natural or legal person residing or having a registered office in a Member State. The EP may also grant access to third-country nationals (discretionary).
- **Response deadline:** 15 working days; extendable by a further 15 working days; failure to reply within the combined deadline constitutes a tacit refusal.
- **Classifications:** Documents carrying an EU classification level (RESTREINT UE/EU RESTRICTED, CONFIDENTIEL UE/EU CONFIDENTIAL, SECRET UE/EU SECRET, TRES SECRET UE/EU TOP SECRET) are not listed in the public register; access is subject to additional internal procedures.
- **Annual report URL:** `https://www.europarl.europa.eu/RegistreWeb/en/home/annualReport.htm`
- **Legal background URL:** `https://www.europarl.europa.eu/RegistreWeb/en/home/legalBg.htm`
- **NOT doceo:** doceo (`europarl.europa.eu/doceo/document/...`) is the document store with constructible references (reports A10-NNN/YYYY, adopted texts P10_TA(YYYY)NNNN, committee docs PE-NNN). RegistreWeb is the legal-access transparency surface; doceo is the content repository.
- **NOT the developer API:** `data.europarl.europa.eu/api/v2` (339 datasets, CC BY 4.0) is the machine-readable API for bulk data. RegistreWeb is for document-by-document access requests and keyword-based document discovery.
- **Appeal route:** Confirmatory application to the EP Secretary-General if access is denied; then complaint to the European Ombudsman (`ombudsman.europa.eu`) or action before the General Court (CJEU).

## Legal Basis

### Article 15(3) TFEU

Article 15(3) TFEU guarantees the right of access to documents of the European Parliament, the Council and the Commission. Any EU citizen, and any natural or legal person residing or having a registered office in a Member State, holds this right. The article instructs the three institutions to lay down their own procedures in their Rules of Procedure and provides for a recast of Regulation 1049/2001 by the ordinary legislative procedure.

### Regulation (EC) No 1049/2001

Regulation 1049/2001 (CELEX 32001R1049; OJ L 145, 31.5.2001, p. 43) is the horizontal access-to-documents framework. It defines:
- the beneficiaries (Article 2): citizens and EU residents/registered-office holders;
- the definition of "document" (Article 3): any content in any form, produced or received by the institution;
- the exceptions to access (Article 4): interpreted narrowly by the CJEU (see Turco C-39/05 P, Council v Access Info Europe C-280/11 P);
- the 15-working-day procedure (Articles 7 and 8);
- the obligation on each institution to maintain a public register (Article 10).

The regulation remains in force in its original form. A 2008 Commission proposal (COM(2008) 229, procedure 2011/0073(COD)) to recast it has been dormant in Council since 2011, though the PETI committee opened a revival of the file in April 2026. For the full legal framework, exceptions and CJEU case law, see `public_access_to_documents_1049_2001.md`.

### EP Rules of Procedure

Rules of Procedure Rules 115 and 116 transpose the right into EP practice, setting out the EP's internal transparency obligations and the precise procedures for public-access requests.

## What the Register Holds

RegistreWeb covers every EP document from 3 December 2001 onwards that has been produced, received or transmitted by the Parliament in the exercise of its powers. This includes, non-exhaustively:
- Plenary documents: draft legislative resolutions, motions, agendas, verbatim reports, minutes.
- Committee documents: reports (A-series), opinions, amendments (PE-numbers), committee minutes and working documents.
- Adopted texts (P-series).
- Correspondence between the EP and other institutions, including trilogue-related letters.
- Parliamentary questions (written and oral) and their answers.
- Delegation-related documents and interparliamentary cooperation records.
- Budgetary documents.

Documents predating 3 December 2001 are held in the EP historical archives and are accessible via a separate route.

**Not included in the public register:** Documents classified at any security level; documents whose disclosure would undermine an ongoing judicial procedure or investigation; third-party documents for which the originator's consent is required under Article 4 of Regulation 1049/2001.

## Search Interfaces

RegistreWeb provides several search modes:

1. **Keyword search:** Free-text search across titles, document references and metadata. Useful when you know a policy term but not the document reference.
2. **Register reference search:** Direct lookup by the EP's internal document reference (e.g., A10-0XXX/2026, P10_TA(2026)0XXX, PE-NNN.NNN/AMxx).
3. **Date-range filter:** Narrow results to a specific period, useful for tracking what was produced in a given week or plenary session.
4. **Document type filter:** Filter by plenary documents, committee documents, adopted texts, correspondence and more.
5. **Procedure reference filter:** Link a document to its legislative procedure reference (e.g., 2021/0106(COD)), mirroring the OEIL procedure number.

**Practical note for Brubru users:** If you already have a document reference from doceo or the EP Open Data API, do not use RegistreWeb to retrieve the text. Go to doceo directly or query the API. RegistreWeb is the transparency-audit and document-discovery surface, not the fastest content-retrieval path.

## The Request-Document Procedure

If a document listed in the register is marked as not directly accessible, or if a document you believe exists is not listed, you may submit a formal access-to-documents request:

1. **Locate the request form** on the RegistreWeb welcome page or via the EP's "Ask EP" contact portal.
2. **Describe the document precisely:** title, reference number, date, author or originating committee, legislative procedure reference.
3. **Submit.** The EP has 15 working days to respond, extendable by a further 15 working days where the volume or complexity justifies it. If you are not notified of an extension and receive no reply within 15 days, this constitutes a tacit refusal.
4. **Partial access:** The EP may grant partial access, redacting the classified or exempt portions while releasing the rest.
5. **Confirmatory application:** If access is wholly or partially refused, you may file a confirmatory application with the EP Secretary-General within 15 working days of the refusal. The Secretary-General has the same 15-plus-15 day deadline.
6. **Further remedies:** After a confirmatory refusal, you may bring an action before the CJEU General Court or lodge a complaint with the European Ombudsman (see the appeal section below).

## What Gets Classified

The EP applies the EU interinstitutional classification framework, aligned with Council Decision 2013/488/EU on the security rules for protecting EU classified information. The four levels are:

- **RESTREINT UE/EU RESTRICTED:** Disclosure could be disadvantageous to EU interests.
- **CONFIDENTIEL UE/EU CONFIDENTIAL:** Disclosure could seriously harm EU interests.
- **SECRET UE/EU SECRET:** Disclosure could gravely harm EU interests.
- **TRES SECRET UE/EU TOP SECRET / EU TOP SECRET:** Disclosure could cause exceptionally grave harm.

Classified documents do not appear in the RegistreWeb public listing. Members of the European Parliament may access classified documents via the EP Reading Room, subject to a security clearance procedure for CONFIDENTIEL and above.

For advocacy professionals, this means: if a document you expect to exist does not appear in RegistreWeb, it may be classified, it may predate 2001, or it may simply not have been registered yet (documents are typically registered within a few days of creation or receipt).

Separately from formal classification, Article 4 of Regulation 1049/2001 lists exceptions that do not require a classified marking: public interest (security, defence, international relations, financial/monetary policy), privacy, commercial interests, court proceedings, and the "space to think" exception for ongoing internal decision-making (Article 4(3), the most litigated).

## Appeal to the European Ombudsman

If access is refused or the EP fails to respond, the two-stage remedy is:

**Stage 1: Confirmatory application.** File with the EP Secretary-General within 15 working days of the first refusal (or of the expiry of the initial response deadline).

**Stage 2: External remedies.** After a confirmatory refusal (or no confirmatory reply), you have two options:
- **Complaint to the European Ombudsman** (`ombudsman.europa.eu`): The Ombudsman investigates maladministration, including unreasonable refusals of access to documents. Transparency is consistently the largest single subject of Ombudsman complaints (see the Ombudsman Annual Report 2024). The Ombudsman cannot compel disclosure but can issue recommendations and own-initiative inquiries. There is no formal filing deadline, but the complaint should be lodged within two years of becoming aware of the issue.
- **Action before the CJEU General Court:** A direct action under Article 263 TFEU must be lodged within two months of the confirmatory refusal.

For the broader Ombudsman framework, see `european_ombudsman.md` (planned guide).

## RegistreWeb vs doceo vs data.europarl.europa.eu

This is the single most common point of confusion for EU policy professionals. The three surfaces serve entirely different purposes.

| Surface | URL | Purpose | When to use it |
|---|---|---|---|
| **RegistreWeb** | `europarl.europa.eu/RegistreWeb/` | Transparency register under Reg 1049/2001; legal access mechanism; document discovery by keyword, date or type | When you do not know the exact reference; when you need to request a classified or unreleased document; when you need an audit trail of what documents exist on a topic |
| **doceo** | `europarl.europa.eu/doceo/document/...` | Document repository; constructible references (A10-, P10_TA, B10-, RC-B, PE-NNN); fast content delivery | When you have a specific reference and want the document text directly |
| **data.europarl.europa.eu** | `data.europarl.europa.eu/api/v2` | Developer API; 339 datasets (CC BY 4.0); machine-readable vote results, MEP data, procedure metadata | For bulk data, structured queries and integration work |

Key routing rule for Brubru chat: send the user to RegistreWeb when they need document discovery or a formal access request. Send them to doceo when they have a reference and need the text. Send them to the API when they need structured or bulk data. See `ep_documents_and_open_data.md` for the full data-architecture map.

## Annual Transparency Report Cadence

Under Article 17 of Regulation 1049/2001, each institution must publish an annual report on the applications received and their outcomes (granted in full, granted in part, refused). The EP publishes its report at:

`https://www.europarl.europa.eu/RegistreWeb/en/home/annualReport.htm`

Typical contents: total applications received; breakdown by type of applicant (citizen, NGO, business, academic, journalist); breakdown by outcome; breakdown by document type; trend data versus prior year; confirmatory applications and their outcomes; referrals to the Ombudsman or CJEU.

**Advocacy use case:** The annual report is a transparency-benchmarking tool. A rising proportion of refusals or confirmatory applications signals an issue for NGO/civil society engagement, and the trend data feeds into the PETI committee's oversight of the EP's transparency obligations and into the Ombudsman's own annual report.

## Brubru Chat Usage

**Route the user to RegistreWeb when:**
- They ask "how do I access EP documents that are not publicly available", "request an EP document" or "how do I find what the EP has on topic X."
- They are conducting a document-discovery exercise across a broad topic (use the keyword search on RegistreWeb, then follow up with doceo for the actual text).
- They want to understand what documents exist on a legislative procedure without already knowing the specific references.
- They ask about transparency rights or the access-to-documents procedure at the EP.

**Route to doceo when:**
- The user has a specific document reference (A-series report, B-series motion, P-series adopted text, PE-number committee document) and needs the document text.

**Route to data.europarl.europa.eu when:**
- The user needs bulk data, vote results, MEP data or procedure metadata for integration or structured analysis. See `ep_documents_and_open_data.md` and `ep_open_data_portal_developer_api.md` (planned guide).

**Route to `public_access_to_documents_1049_2001.md` when:**
- The user asks about the legal framework governing access, the exceptions in Article 4, CJEU case law, the dormant 2011 revision or the 2026 PETI revival.

## Cross-References
- `ep_documents_and_open_data.md`: the full map of where EP data and documents live, covering doceo, OEIL and the developer API
- `ep_open_data_portal_developer_api.md`: the developer API at `data.europarl.europa.eu/api/v2` in depth (planned guide)
- `public_access_to_documents_1049_2001.md`: Regulation 1049/2001, the exceptions, CJEU case law, the revision history and the 2026 PETI revival
- `european_ombudsman.md`: the Ombudsman's jurisdiction, complaint procedure and own-initiative investigations (planned guide)
- `finding_and_citing_eu_law.md`: how to cite EU legal acts and where legal data lives across Cellar, EUR-Lex and CELEX
