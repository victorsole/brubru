# EP Parliamentary Questions: Written, Oral, Question Time, Priority

## QUICK FACTS
- **What this is**: the four types of parliamentary question MEPs may put to EU institutions, their Rules of Procedure (RoP) basis, document-code prefixes, answer deadlines, and how to find them.
- **Governing rules (EP10 RoP)**: Rule 138 (priority written questions, suffix **P-**), Rule 142 (oral questions for plenary debate, suffix **O-**, may produce a resolution), Rule 143 (Question Time, suffix **H-**), Rule 144 (written questions for written answer, suffix **E-**), Rule 145 (major interpellations, suffix **O-000XXX/YYYY** with specific plenary slot).
- **Addressees**: European Commission, Council of the EU, Vice-President/High Representative (VP/HR), and the European Central Bank (ECB). Questions to other bodies (EIB, European Ombudsman) follow the same written-question track.
- **Answer deadlines**: written questions (Rule 144): **6 weeks**; priority written questions (Rule 138): **3 weeks**; oral questions (Rule 142): tabled at least 1 week before the plenary session where they will be debated; Question Time (Rule 143): no written answer required, the institution replies live in the chamber.
- **Document-code prefixes on doceo**: **E-** (written question, Rule 144), **P-** (priority written question, Rule 138), **O-** (oral question, Rule 142 or major interpellation Rule 145), **H-** (Question Time, Rule 143). Search at `europarl.europa.eu/plenary/en/parliamentary-questions.html`.
- **MEP cap on written questions**: MEPs may submit a maximum of **5 written questions per calendar month** (Rule 144(1)) plus **1 priority written question per calendar month** (Rule 138(2)); the Conference of Presidents may further limit totals.
- **Publication**: questions and answers are published in the **Official Journal C series** (OJ C); they are also available on the EP website and via the EP Open Data API (Questions and Answers dataset family, 14 datasets).
- **Brubru ingests EP questions** for chat use: the `ep_documents_and_open_data.md` data map describes the API paths; questions feed the Chat knowledge base via the Open Data API v2 Questions and Answers family.

---

## 1. The Four Rules and Their Use Cases

### Rule 138: Priority Written Questions (P-)

Priority questions are addressed to the Commission and carry a shortened answer deadline of **3 weeks** (extendable by a further 3 weeks on reasoned request). They are used when urgency requires a faster Commission response: for example, when a trade measure is imminent, an infringement deadline passes, or a crisis situation unfolds. Each MEP may file one priority question per calendar month.

On doceo the reference reads: **P-000XXX/YYYY** (e.g. P-000042/2025).

### Rule 142: Oral Questions for Plenary Debate (O-)

An MEP, a committee, or a political group may put an oral question to the Commission, Council or VP/HR for debate in plenary. The body replies orally; the plenary may then vote a resolution. Rule 142 oral questions are the instrument behind many high-profile EP positions: the institution's live answer creates a parliamentary record, and a subsequent resolution gives MEPs a formal vehicle to press their view.

On doceo the reference reads: **O-000XXX/YYYY**.

Oral questions must be filed at least **one week** before the plenary session and appear on the agenda once confirmed by the President. Each political group may table one per part-session on any subject within the EU's field of competence.

### Rule 143: Question Time (H-)

Question Time takes place during plenary sessions (usually Wednesdays or Thursdays). MEPs put brief questions directly to the Commission or Council; the institution replies live and there is an opportunity for a supplementary question. No written answer follows. The prefix is **H-** (from the French "Heure des questions"). Question Time is a fast-track oral-scrutiny tool and is used heavily to raise constituency cases, current affairs and time-sensitive policy points.

### Rule 144: Written Questions for Written Answer (E-)

The workhorse scrutiny instrument. Any MEP may submit a written question to the Commission, Council, VP/HR or ECB at any time. The addressee must reply in writing within **6 weeks** (extendable). Written questions are the most frequently used EP scrutiny tool: several hundred are tabled per plenary part-session.

On doceo the reference reads: **E-000XXX/YYYY** (e.g. E-003872/2025).

Answers are published together with the question in the OJ C series and on the EP website. This creates a permanent, citable parliamentary record useful for advocacy (an MEP's question places a policy concern on the institutional agenda; the Commission's answer is a public statement of its position).

### Rule 145: Major Interpellations

Major interpellations are a variant of the oral question: a political group or at least 10% of the EP's component Members may put a question of major importance to the Commission, Council or VP/HR for **written** answer and subsequent plenary debate. They follow the same O- prefix convention but use a separate tab on the EP website. See the interpellations tab at `europarl.europa.eu/plenary/en/parliamentary-questions.html?tabType=oq`.

---

## 2. Document-Code Prefixes and Where to Find Them

| Prefix | Rule | Type | Addressee(s) | Answer format |
|---|---|---|---|---|
| E- | 144 | Written | Commission, Council, VP/HR, ECB | Written, OJ C |
| P- | 138 | Priority written | Commission | Written (3-week deadline), OJ C |
| O- | 142 / 145 | Oral / major interpellation | Commission, Council, VP/HR | Oral (plenary) + possible resolution |
| H- | 143 | Question Time | Commission, Council | Oral (chamber), no OJ publication |

**Searching on the EP website**: `https://www.europarl.europa.eu/plenary/en/parliamentary-questions.html`

- Written questions tab: `?tabType=wq` (covers E- and P-)
- Oral questions tab: `?tabType=oq` (covers O- and H-)

**Searching on doceo**: go to `europarl.europa.eu/doceo/document/{PREFIX}-10-YYYY-NNNNNN_EN.html`: substitute the prefix, parliamentary term, year and sequence number. This is reliable for term-10 (EP10) questions filed from July 2024.

**EP Open Data API**: the Questions and Answers family (14 datasets) exposes questions in JSON-LD, RDF, CSV and Turtle. Use `https://data.europarl.europa.eu/api/v2` with appropriate filters. Brubru wraps this via `services/api_clients/ep_open_data_client.py`.

---

## 3. Addressees and Answer Deadlines

| Addressee | Rule 144 written | Rule 138 priority |
|---|---|---|
| European Commission | 6 weeks (extendable +3) | 3 weeks (extendable +3) |
| Council of the EU | 6 weeks | N/A (Council not addressee of Rule 138) |
| VP/HR (EEAS) | 6 weeks | N/A |
| European Central Bank | 6 weeks (informal arrangement) | N/A |

The Commission is by far the most frequent addressee of written questions (roughly 85-90% of total volume). If no answer arrives within the deadline the EP President may notify the institution formally; the question and a note recording the absence of a reply are still published in OJ C.

---

## 4. The Cap on Written Questions per MEP

Rule 144(1) caps each MEP at **5 written questions per calendar month**. Rule 138(2) caps priority questions at **1 per MEP per calendar month**. The Conference of Presidents may reduce these figures if overall volume would impair the functioning of the institution (the cap was tightened progressively after some MEPs filed 50+ questions a month in earlier terms).

These limits make each written question a deliberate political or policy signal. APAs (parliamentary assistants) and advocacy teams typically identify the right timing and the right committee rapporteur or politically aligned MEP to table a question that maximises impact.

---

## 5. How to Search EP Parliamentary Questions

**On the EP website**:
1. Go to `https://www.europarl.europa.eu/plenary/en/parliamentary-questions.html`
2. Use the search box to filter by keyword, MEP name, document reference, or date range.
3. Written questions tab shows E- and P- references; oral questions tab shows O- and H-.
4. Each result links to the full question text and, once available, the institution's answer.

**On doceo**: construct a reference using the known prefix, term (10), year and sequence. Doceo hosts the full text as HTML and PDF.

**Via EUR-Lex / OJ C**: answered written questions appear in the OJ C series and are searchable on EUR-Lex under the "Questions" document type. Search by MEP name, keyword, or CELEX-style identifier (questions receive a CELEX number in the format `E{year}{sequence}` once published).

**Via the EP Open Data API v2**: the Questions and Answers family lets developers pull questions by MEP, by date range, by addressee and by keyword. See `ep_documents_and_open_data.md` for the API map.

---

## 6. Recent High-Profile Question Patterns

Written and priority questions in EP10 (2024 onwards) cluster heavily around:
- **AI and platform regulation**: follow-up to the AI Act implementation timeline, DSA enforcement actions, algorithmic accountability cases.
- **Energy and climate**: questions tracking the Affordable Housing Initiative, ETS reform, grid permitting, and energy poverty definitions.
- **Trade and CBAM**: questions about CBAM third-country equivalence, the Border Carbon Adjustment registry, and anti-dumping investigations.
- **Rule of law**: questions about Article 7 procedure enforcement, Media Freedom Act implementation, and judicial independence in Member States.
- **Health and food safety**: questions triggered by EFSA opinions, novel food authorisations, and antimicrobial-resistance data gaps.

Priority questions (P-) most often appear after a specific Commission announcement, infringement decision, or crises event where the 6-week window would be too slow to serve the political moment.

Oral questions (O-, Rule 142) ending in resolutions are used by political groups to register a formal EP position between plenary part-sessions -- notably on foreign-affairs crises, sanctions regimes, and humanitarian situations.

---

## 7. Brubru Chat Usage

Brubru ingests EP parliamentary questions via the EP Open Data API v2 and surfaces answers in chat. When a user asks:

- "Has any MEP asked the Commission about X?" -- Brubru queries the Questions and Answers dataset family and returns matching E- or P- references with the Commission's answer.
- "What is the Commission's official position on Y?" -- if a written answer exists, Brubru cites it with the document reference and OJ C publication link.
- "Which MEP put a question about Z?" -- Brubru searches by keyword and returns the MEP name, political group, and question reference.

Chat answers citing parliamentary questions must include the document reference (E-/P-/O-/H- prefix + year + sequence) and a link to the doceo page or the EP questions portal so users can verify the source.

---

## 8. Interpellations (Rule 145): Cross-link

Major interpellations (Rule 145) are a group instrument used for systemic policy concerns. They follow the oral-question O- prefix but appear on a distinct tab and always generate a plenary debate + written answer. They are rarer than standard written questions but politically weightier because they require group-level backing. See the interpellations section on the EP questions portal (oral questions tab).

---

## Cross-references
- `ep_documents_and_open_data.md` -- the EP data map (doceo, OEIL, Open Data API v2, document prefixes)
- `european_parliament_powers.md` -- the supervisory power that parliamentary questions serve
- `european_parliament_personnel.md` -- MEP profiles, political groups, committee membership
- `ep_committees_overview.md` -- committee work, rapporteurs, and committee own-initiative questions
- `ep_plenary_how_it_works.md` -- how questions enter the plenary agenda and how debates are structured
- `working_with_apas.md` -- how APAs prepare and file parliamentary questions on behalf of MEPs
- `ep_open_data_portal_developer_api.md` (planned) -- engineering guide to the EP Open Data API v2
- `ep_legislative_own_initiative_proposal_union_act.md` (planned) -- the Art 225 TFEU request for legislation, the legislative counterpart to scrutiny questions
