---
name: dpp-brief
description: A /news for one regime and one reader — everything that moved on the EU digital product passport (ESPR, the registry, the 13 acts that impose a passport, standards, sector rollout dates, who is lobbying it), written for a lawyer who has to comply and delivered as a Catalan Gmail draft. Runs inside /morning as Phase 1d on the days the user asks for it. Triggered by "/dpp-brief", "DPP brief", "what moved on the product passport".
user_invocable: true
---

# /dpp-brief — the digital product passport brief

A `/news` for one regime and one reader. Where `/news` sweeps the whole EU and
`/brief` sells the product, this collects everything that moved on the digital
product passport and says what it means for a project that has to comply. Built
for Joana Castella (Terraqui, LIFE DPP-TEX), and usable for any subscriber who
ticks the ecodesign interest.

**Cadence, set by Joana herself on 19 August 2026: MONTHLY, plus an URGENT brief
whenever something genuinely new lands.** Not weekly, not "whenever something
moved". Two tracks:

- **Monthly**: a scheduled round-up, sent even in a quiet month, because the
  value is partly the "nothing moved" line. She has been away and wants to know
  she has not missed anything.
- **Urgent**: out of cycle, only when something actually binds, opens or shifts.
  This is where the Step 5 gate applies in full.

**A quiet month is NOT a reason to skip the monthly brief; it IS a reason to skip
an urgent one.** On 19 August 2026 the gate technically passed (PPWR applicable
12 Aug, ELV Art 53 amending the Batteries Regulation 13 Aug) and Victor still
decided not to send, because none of it was significant enough for an out-of-cycle
mail on the DPP regime specifically. **Her attention is the scarce resource.**
When in doubt between urgent and monthly, hold it for the monthly.

## What counts as DPP news

The regime is wider than the ESPR. An item belongs in this brief if it touches
any of:

- **The framework**: ESPR (32024R1781), its delegated and implementing acts.
- **The registry**: Implementing Reg. (EU) 2026/1778, the registry environments,
  the unique registration identifier, customs and CSW-CERTEX.
- **The twelve other acts that impose a passport** (Art. 1 of 2026/1778):
  batteries, construction products, toys, detergents, critical raw materials,
  textile EPR, PPWR, textile fibre labelling, unsold goods, standards decision.
- **Standards**: CEN/CENELEC work, the harmonised-standards decisions.
- **Sector rollout**: any date moving for textiles, steel, aluminium, tyres,
  furniture, mattresses, ICT, toys, detergents.
- **Who is lobbying it**: transparency-register meetings and position papers on
  ecodesign, DPP, textile EPR.

## Step 1 — read Brubru's own DPP folder first

```bash
curl -s -H "X-API-Key: $KEY" \
  "https://brubru-production.up.railway.app/api/v2/dpp/guidance"
```

`/api/v2/dpp` is the regime as data: `legal-framework` (13 acts, full text),
`sectors` (11, with rollout dates), `registry`, `standards` (6), `data-points`
(71 battery fields), `guidance` (Commission guidance, news and events).
Anything here that postdates the last brief is a candidate.

## Step 2 — sweep the institutions

Read, in this order, and never paraphrase press as primary:

1. **Commission**: DG GROW and DG ENV newsrooms via the DG-specific subdomains
   (`single-market-economy.ec.europa.eu/news/`, `environment.ec.europa.eu/news/`),
   never the generic presscorner, which 404s often.
2. **Have Your Say**: consultations and delegated-act feedback periods on
   ecodesign, textiles, unsold goods. Initiative 16116 is the apparel-textiles
   ecodesign act and is the one that matters most to a textile project.
3. **EUR-Lex / Cellar**: anything new in the OJ carrying an ESPR legal basis.
4. **EP**: ENVI and IMCO committee agendas, questions, own-initiative reports.
5. **Council**: Environment and COMPET configurations.
6. **Agencies and bodies**: JRC (the Ecodesign product bureau), EEA, ECHA on
   substances of concern, CEN/CENELEC.
7. **Lobby**: transparency-register meetings whose subject mentions ecodesign,
   digital product passport or textile EPR.

Brubru's own aggregators cover most of this:
`/api/v2/news/all?days=N` and `/api/v2/events/all?days=N`.

**Run `scripts/dpp_watch.py` first — it does steps 1 and 2 in one pass** across
`economy_items`, `eu_news_items`, `social_posts` and `public_consultations`,
deduplicated, and prints an explicit URGENT / ROUTINE / NOTHING / UNPROVEN
verdict plus a freshness check on the watchlist bodies:

```bash
python3.12 scripts/dpp_watch.py --days 7          # the daily gate decision
python3.12 scripts/dpp_watch.py --days 30 --json  # the monthly round-up
```

It carries the three scopes as data (DPP-TEX core with the eight consortium
partners by name, Blue Room's other sectors, Terraqui's eight practice areas),
so widening coverage is a one-line edit rather than a rewrite. **A zero from it
is only a verdict when the watchlist bodies are fresh** — otherwise it reports
UNPROVEN, because "nothing happened" and "nothing was ingested" are different
answers.

## Step 3 — classify, and show everything

Group into: **Binding** (in force or adopted), **Moving** (proposed, consulted,
in committee), **Money** (LIFE and other calls), **Diary** (dates ahead).

Show every item found, including the low-priority ones. The classifier is
keyword-crude; the reader is the one who decides what matters. This mirrors the
`/news` rule.

## Step 4 — write it for a lawyer, not a marketer

**The format is LOCKED, from Victor's edited-and-sent version of 24 Aug 2026.**
Full diff and rationale: `memory/feedback_joana_brief_format.md`. Follow it
exactly rather than re-deriving it.

- **Catalan** for Joana. Accented properly: sóc, perquè, política, Brussel·les.
  EU Regulation is **Reglament**, never "Regulació".
- **Open with `Bon dia, Joana,` then a lowercase continuation.**
- **Every date carries its weekday**, computed and never guessed:
  `["dilluns","dimarts","dimecres","dijous","divendres","dissabte","diumenge"][d.weekday()]`.
  "Es tanca el **diumenge** 30 d'agost", "a partir de **dijous** 18 de febrer de
  2027". Vary a repeated date: "Es tanca **també el mateix** dimecres 16".
- **Hedge every inference; assert only what is verified.** Dates, article numbers
  and what a document literally says stay flat. Anything forward-looking or
  analogical becomes conditional: "**potser podria** marcar el to", "**sembla
  que** s'aplica abans", "**podria ser** la plantilla". Victor made this edit
  three times in one email; it is the difference between a briefing and a pitch.
- **`Reglament 2023/1542`, without `(UE)`**, for this reader specifically. This
  departs from `feedback_catalan_instrument_names`, which still governs
  everywhere else.
- Name the DG in full with its acronym: "Direcció General de Mercat Interior
  (DG GROW)".
- Sentence-case section headings. No em-dashes, no emojis, no institutional
  codes in the subject line.
- Each item: what happened, what it changes, and the date that binds.
- **ZERO calls to action.** Not "at most two" — none. Victor deletes them.
- Keep an **`Un senyal a verificar`** section for anything unconfirmed, stating
  its provenance and that no legislative text has been located.
- **Sign `Victor` + `hello@beresol.eu`, with no `brubru.beresol.eu` link.** It is
  correspondence from a person, not a send from a platform.
- Link every act to EUR-Lex, every consultation to Have Your Say, every call to
  the Funding and Tenders portal — hyperlinked on the title in the HTML part.

## Step 5 — the send-worthiness gate

Do not send unless at least one of these is true:

- something entered into force, was adopted or was published in the OJ;
- a consultation opened or closes within 30 days;
- a rollout date moved;
- a call for proposals on her remit opened or closes within 45 days;
- a standard was cited or withdrawn.

Otherwise, hold. Recording "nothing moved" is a legitimate outcome and should
be written to the session note rather than emailed.

## Step 6 — deliver as a Gmail draft, never a send

Compose the HTML, create it as a **draft** in the Gmail account of
hello@beresol.eu, and tell the user it is waiting. Never send. Multipart with an
HTML part; Catalan needs UTF-8 and real hyperlinks, per
`memory/feedback_catalan_email_html_hyperlink_pattern.md`.

## Step 7 — audit before handing over

- Every date verified against the primary source, not against our own cache.
- Every CELEX resolves (Cellar is the oracle; EUR-Lex returns 202 for real and
  fake alike).
- Every URL fetched once and checked for a 200.
- Read each headline aloud: could a lawyer who has never used Brubru understand
  the consequence without looking anything up?

## Key files

- `backend/api/v2/dpp/__init__.py` — the folder, 9 resources.
- `backend/scripts/publish_dpp_to_meub.py` — how DPP news reaches MEUB.
- `backend/knowledge_base/guides/ecodesign_digital_product_passport.md` — the guide.
- `memory/project_terraqui_dpp_engagement.md` — the client, and what was built.
