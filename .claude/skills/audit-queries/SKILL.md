---
name: audit-queries
description: Daily audit of real user queries to Brubru Chat. Pulls queries from the database for a given date range, diagnoses each answer against quality criteria, and implements fixes (knowledge guides, system prompt rules, context builder improvements). Run this daily to improve chatbot retention.
argument-hint: [YYYY-MM-DD or "yesterday" or "today" or date range "2026-02-25 2026-02-27"]
allowed-tools: ["Read", "Edit", "Write", "Bash", "Glob", "Grep"]
---

# Daily User Query Audit

You are performing the daily Brubru Chat query audit. This is the most important retention activity: pre-users make 1-2 queries and leave if the answer is poor. Every query is a retention opportunity.

Read `memory/query_audit.md` for the full process documentation and previous findings, and `memory/project_chat_audit_fixes_log.md` for the running ledger of audit-driven fixes.

**Updated 10 August 2026** after the 6-7 August Chat rework (latency 130.9s → 8-13s, refusals 19% → 0, system prompt 17.9K → 7.3K tokens, four blind datasets given retrieval). Four things changed that alter how you audit: **Anthropic is out of the chat chain** (Step 1, Important Notes), **the validator now logs a verdict on every answer** (Step 1c), **feature names are enforced in code** (Step 2), and **`/api/chat/stream` is the only path worth testing** (Step 4). Baseline: `memory/project_chat_rework_2026_08_06.md`.

## Step 1: Pull Queries

Connect to the database and pull all chat queries for the requested date: $ARGUMENTS

If the argument is "yesterday", use yesterday's date. If "today", use today's date. If a date range (two dates), pull for the full range.

```sql
SELECT
  c.id as chat_id,
  c.pre_user_id,
  c.user_id,
  u.email as user_email,
  u.full_name as user_name,
  u.subscription_tier as user_tier,
  m.role,
  m.content,
  m.created_at
FROM chats c
JOIN chat_messages m ON m.chat_id = c.id
LEFT JOIN users u ON u.id = c.user_id
WHERE DATE(m.created_at AT TIME ZONE 'UTC') >= 'START_DATE'
  AND DATE(m.created_at AT TIME ZONE 'UTC') <= 'END_DATE'
  -- Drop our own deploy/verification probes. TWO signals are needed, because
  -- they cover different eras and neither alone is sufficient (audit, 19 Aug 2026):
  --   (a) chat_metadata.is_probe -- stamped when the caller sends the
  --       `X-Brubru-Probe: 1` header (api/chat.py). This is the RELIABLE
  --       signal and the only one that catches modern probes.
  --   (b) the old slug heuristic -- pre-header probes wore typed slugs
  --       ('deploy-probe', 'verify-prod-0807'); real pre_user_ids are
  --       client-generated UUIDs. Catches nothing after ~8 Aug 2026.
  -- On 5 Aug, 38 of 38 probes were slug-shaped and 0 carried the flag; on
  -- 17 Aug, 4 of 4 carried the flag and 0 were slug-shaped. Using either
  -- filter alone reports our own probes as user traffic.
  -- COALESCE is NOT optional: chat_metadata is NULL on most historic rows and
  -- (NULL ->> 'is_probe')::boolean is NULL, not false, so a bare NOT (...)
  -- silently drops every genuine row. See feedback_null_propagation_and_silent_fallback_hide_failures.
  AND NOT COALESCE((c.chat_metadata ->> 'is_probe')::boolean, false)
  AND NOT (c.pre_user_id IS NOT NULL AND c.pre_user_id !~ '^[0-9a-f]{8}-[0-9a-f]{4}-')
ORDER BY c.id, m.created_at;
```

**Neither filter is sufficient, and you must still read the rows.** A third probe
variant defeats both: a verification sweep fired WITHOUT the header and with freshly
minted UUID `pre_user_id`s is indistinguishable from real traffic by any column. The
tell is only visible by eye -- identical or near-identical titles repeating seconds
apart, topically aligned with that day's session work:

```
13:57:21  Quan va entrar en funcionament el registre del passaport digital de producte?
13:57:27  When does the digital product passport become mandatory for textiles?
13:57:37  Which harmonised standards give a presumption of conformity ...?
```

On 11-19 August 2026 the two filters left 33 "real" chats; reading them reduced the
genuine human total to **three**. Always report the count you actually verified by
reading, and say which one you are giving. A filtered count presented as a user count
is the same class of defect as a check that cannot fail.

**Every verification path you fire must send `X-Brubru-Probe: 1`** so the next audit
does not have to do this by hand:

```bash
curl -s -N -X POST https://brubru-production.up.railway.app/api/chat/stream \
  -H "Content-Type: application/json" -H "X-Brubru-Probe: 1" \
  -d '{"message": "...", "use_context": true}'
```

Use the DATABASE_URL from `backend/.env` to connect (`grep '^DATABASE_URL=' .env | cut -d= -f2-` — never `source .env`). Use `python3.12` (not `python3`) for any Python commands.

Pull `m.provider` and `m.model` on the assistant rows too. **Never guess which model wrote an answer — it is recorded.** The streaming path used to persist provider/model as NULL, so ~22% of answers could not be traced; fixed 6 August 2026. Attribution is complete from 7 August onward; anything older reads NULL and cannot be attributed retrospectively.

Present a numbered summary table:

| # | User | Type | Query (first 60 chars) | Language | Provider |
|---|------|------|------------------------|----------|----------|

Where Type = "pre-user" (anonymous), "free" (white tier), "subscriber" (yellow/blue tier).

Provider matters diagnostically: a defect that only appears on Mistral rows is a provider problem (Mistral reads ~30% of injected context), not a retrieval or guide problem. Fixing the guide would not have helped.

**Two segmentation traps** (shared with `/users`; see that skill's Step 1):

1. The tier column is `users.subscription_tier`. There is no `users.tier` — a query naming it errors out and returns nothing.
2. An anonymous chat still writes a **non-NULL** `chats.user_id` (a synthetic UUID derived from `pre_user_id`, with no row in `users`). Classifying on `user_id IS NULL` files anonymous traffic as signed-in users. The correct test is `u.id IS NULL` after the LEFT JOIN.

## Step 1b: Dogfood Check (Brubru API / MCP)

**FIRST: the local `brubru` MCP is not a production oracle (added 24 August 2026).**
`mcp__brubru__*` reads the LOCAL filesystem. On 24 Aug it reported **555 guides and found both
payments guides**, while production served **553** and had neither. Taken at face value it would
have routed the diagnosis to "retrieval bug" when production simply did not hold the files.

- The production oracles are the **`claude_ai_Brubru` remote connector** and a **direct curl**
  against `brubru-production.up.railway.app` / `brubru.beresol.eu/guides/`.
- **The guide count is the cheap tell.** If the MCP's `total_guides` differs from the number on
  `brubru.beresol.eu/guides/`, you are looking at two different corpora and the dogfood result
  proves nothing about what the user got.
- A dogfood check that disagrees with production is a finding in itself, not evidence.


Before diagnosing the chat response in isolation, test every failing or partial query against the Brubru MCP tools (which are the v1 API exposed as MCP). The chat and the API share the same data layer, so every chat failure must be interpreted against what the API would have returned:

| MCP tool | When to use |
|---|---|
| `mcp__brubru__ask_brubru(q)` | Chat-equivalent retrieval + guide-search pipeline |
| `mcp__brubru__search_knowledge_guides(q)` | Guide-only retrieval (fast coverage check) |
| `mcp__brubru__get_calendar_events(days_ahead=N)` | Calendar queries |
| `mcp__brubru__search_eu_legislation(q)` | Legislation queries |
| `mcp__brubru__search_eprs(q)` | EPRS queries |
| `mcp__brubru__get_procedure_status(ref)` | Procedure-status queries |

Three possible outcomes per failing query:

1. **MCP returns good data → chat retrieval gap.** Fix in `context_builder.py` — the data is there but the chat didn't surface it. Example: Chat 5 on 17 Apr 2026 ("energy events next week?") — `get_calendar_events` returned the Fossil Fuel Conference but `_fetch_eu_calendar_events` filtered it out. Fixed 20 Apr.
2. **MCP fails the same way → data gap.** The right data isn't in the DB. Fix is to sync or add it (new guide, calendar entry, procedure sync), not to tweak retrieval.
3. **MCP returns OK but not great data → shared primitive needs improvement.** Refactor the underlying query function so both API and chat benefit.

**Record the outcome per query in the audit log**, so fixes are routed to the right layer (retrieval vs data vs shared primitive).

## Step 1c: Read the validator ledger (added 10 August 2026)

Since 6 August the response validator runs on the path users actually hit, in **shadow mode**: it computes a verdict on every answer and writes it to `chat_validations`, but never modifies what shipped. That table is now a second audit input, and it is free — the judging already happened.

```sql
SELECT created_at, generator, language, severity, passed,
       violation_count, violations, left(query, 80) AS query
FROM chat_validations
WHERE created_at::date BETWEEN 'START_DATE' AND 'END_DATE'
ORDER BY created_at;
```

Two jobs each run:

1. **Cross-check the verdicts against your own diagnosis.** A `critical` verdict on a query you judged fine is a validator false positive. A query you judged fabricated that the validator passed is a validator miss. Both are findings.
2. **Maintain the running false-positive rate**, because shadow mode is a measurement window with an open decision at the end of it. `VALIDATOR_SHADOW_MODE=false` restores the veto, and it should only be flipped once the logged FP rate on real queries justifies it.

The rate is not yet acceptable. Of the critical verdicts logged in the first days, "What is the AI Act?" and "What is the Ecodesign for Sustainable Products Regulation?" — plain questions, well-grounded answers — were both flagged critical. Under override mode each would have been replaced by the safe-refusal template. **Do not recommend flipping the veto back on while ordinary questions are still scoring critical.**

Why the defaults were wrong in the first place is worth carrying: they were set on 28 May for `chat()`, a path the UI never calls, so they had never executed against a single real user. See `memory/feedback_defaults_for_a_dead_code_path_are_untested.md`.

## Step 2: Diagnose Each Query

For each query-response pair, check against this **diagnostic checklist**:

### Factual Accuracy
- [ ] Every listed item is a real, specific legal act with a number (no vague categories like "Data Protection Laws")
- [ ] CELEX numbers are correct if mentioned
- [ ] Dates include the year (not just "May" but "May 2023")
- [ ] Counts match reality (not "177 members" when there are 88)

### Fabrication (highest severity — added 10 August 2026)

Chat does not say "I don't know" about a dataset it cannot retrieve. It invents a fluent, plausible answer with a source attached. Four instances were found in a single day on 7 August, all in datasets Brubru *holds* but `context_builder.py` could not read.

- [ ] Every named MEP vote is a retrieved record, not an inference from their political group (correct for the ~90% who follow the whip, confidently wrong for rebels, and rebels are exactly who the user is asking about)
- [ ] Every PE / A- / T- / E- reference is well-formed AND on file
- [ ] Lobbyist names are organisations from the register, never EU institutions
- [ ] Where nothing was retrieved, the answer SAYS so rather than filling the gap

When you find one, do not fix it with a system prompt rule. The prompt already forbade inventing PE numbers, tallies and rapporteur names; the rules lost because the real values were absent from context, and no instruction competes with an empty context. **Retrieval is the fix.**

Run the coverage audit periodically rather than waiting for a fabrication to surface:

```bash
# any user-facing table with real rows and 0 references is a fabrication waiting to happen
grep -c "<table_name>" backend/services/ai/context_builder.py
```

Retrieval was added on 7 August for `parliamentary_questions`, `ep_roll_call_records`, `mep_lobby_meetings` and `amendment_documents`. **Still unretrieved as of 10 August: `procedure_snapshots`, `eu_comitology_committees`** (both 0 references). Every new block needs a NOT-ON-FILE branch that names what not to do. Full pattern: `memory/feedback_chat_fabricates_what_it_cannot_retrieve.md`.

Test with a record that BREAKS the pattern the model would guess. An MEP who voted with their group proves nothing.

### Language
- [ ] Response is in the SAME language as the query (Catalan query = full Catalan response)
- [ ] Follow-up suggestions are also in the same language
- [ ] No mid-response language switching

The detected language is now stated twice (system prompt AND the last line of the user turn), so a **mis-detection is obeyed confidently in the wrong language** — the failure is louder than it used to be. `_detect_query_language()` in `services/ai_service.py` is bag-of-words, and it loses to EU acronyms and short homographs. Three shipped collisions found in one day: "ETS" folded to Catalan *ets* ("you are") and answered an English question entirely in Catalan; English "met" is Dutch for "with" and won a sentence containing no other EN marker; a Spanish question tied with French on the single word "la" and lost on dict declaration order.

If a language flag appears, check the detector BEFORE touching the guide or the prompt. Any word added to a marker or decisive list must be checked against the other five languages after accent folding, and against common EU acronyms (ETS, SOC, CAP, ECA, ESM). Full invariants: `memory/feedback_language_detector_acronym_collisions.md`.

### Citations & Links
- [ ] No orphan citation markers like [1], [2] without actual references
- [ ] No hallucinated EUR-Lex links
- [ ] EUR-Lex links use correct CELEX numbers

### Authority URI resolution (Phase 1+ infrastructure)

If the user query OR Brubru's response contains an authority URI (`http://publications.europa.eu/resource/authority/...`), label-resolve via `eu_authority_labels`:

```sql
SELECT lang, pref_label FROM eu_authority_labels
WHERE uri = '<the URI>' AND lang IN ('en','fr','es','ca','it','nl');
```

Flag:
- **Lang mismatch**: a CA user got a response with only EN labels available → log a "fallback hit" so we know which NAL/lang pairs to prioritise.
- **Hallucinated URI**: shape-valid but absent from `eu_authority_labels` (and table has >100 rows) → trace to root cause in retrieval/system prompt.
- **Empty table**: skip this check entirely. Note as "deferred — labels table not populated yet".

### Intent Detection
- [ ] If query contains an action word (justificacio, draft, redacta, escriu, write) + topic, the response helps PRODUCE the document, not explain the topic
- [ ] Ambiguous abbreviations are decoded (FR = Financial Regulation, not France)
- [ ] Short/concatenated queries are properly parsed (laFR = la FR)

### Completeness
- [ ] Committee member lists show ALL members, not capped at 10
- [ ] MEP info includes political group, committee, procedure reference
- [ ] Partial lists are honestly flagged as partial
- [ ] Country-specific MEP/rapporteur queries return data from `_fetch_rapporteurs_by_country()` (OEIL + committee_work + EP API name matching)

### Follow-ups
- [ ] Response offers specific, actionable follow-up suggestions
- [ ] No generic "check EUR-Lex yourself" deflection
- [ ] Follow-ups leverage Brubru features (Amendator, Predictions, Document Generator)

### Feature cross-link (MANDATORY)

Feature names are **canonical and enforced in code** since 7 August 2026. `MEUB_SUBTABS` (25 sub-tabs) and `BRUBRU_PRODUCTS` (6 products) in `services/ai_service.py` are the only valid names, and `_correct_invented_features()` rewrites anything else in post-processing. Do not audit against a name you remember; audit against those two tuples.

Three names this checklist itself used to teach are wrong and the code now rewrites them: **"My Files" → "My Tracked Files"**, **"Legislative Tracker" → "Legislative Train: state of play"**, **"EC Public Consultations" → "EU Public Consultations"**. "Analytics" and "Documents" are not features at all ("My Documents" is).

- [ ] Response surfaces at least one relevant Brubru feature beyond Chat, named exactly as `MEUB_SUBTABS` / `BRUBRU_PRODUCTS` spell it
- [ ] The named feature is the right one for the query (an amendments query → Amendator + My EU Bubble > Amendments; a deadline query → My EU Calendar; an MEP-vote-prediction query → Predictions)
- [ ] No vague "other Brubru features" mention — must be specifically named so the user can click into it
- [ ] **Non-English answers keep their translated tab label.** `MEUB_SUBTAB_LOCALISED` carries all six languages precisely so a correct Catalan answer naming "Els meus expedients en seguiment" is not rewritten as an invention. If a locale label changed, regenerate that tuple — otherwise the guard mangles five languages out of six, which is worse than the failure it prevents.
- [ ] If the right answer requires a feature that does NOT exist or is broken end-to-end, log the gap as a feature-tree issue (not a chat issue) and route the fix accordingly

An invented sub-tab is the canonical case for enforcing in code rather than in the prompt: the prompt listed all 25 and said plainly that anything else does not exist, and Chat still sent a user to "My EU Bubble > EU Who-is-Who".

## Step 3: Implement Fixes (Parallelise Where Possible)

When multiple fixes are independent (e.g. creating 3 new knowledge guides), use the Agent tool to run them in parallel:
- **Guide creation agents**: Each creates a guide + adds keyword triggers (can run simultaneously)
- **System prompt fixes**: Must be sequential (single file, conflicts)
- **Context builder fixes**: Must be sequential (single file)

### Choose the layer before choosing the words (added 10 August 2026)

A rule the model keeps ignoring is usually not badly worded. **It is too far from the question.** Escalate in this order, and do not skip a step by rewording harder:

1. **Can the model even see the data the rule is about?** If not, it is a retrieval bug wearing a prompt-rule costume.
2. **Does the answer have a deterministic correct form** (a URL, a canonical name, a reference format)? Then generate it in post-processing, not by asking. COM and procedure references went from 0 of 4 hyperlinked to 4 of 4 the moment `_linkify_references()` built them in code.
3. **Is the constraint per-query rather than universal?** Put it in a context block next to the question. A competitor rule written into the prompt twice, the second time naming the competitors and explicitly banning a two-column table, produced the table both times; a `[COMPARISON REQUEST -- ANSWER CONSTRAINT]` block next to the question fixed it on the first try.
4. **Only if it is true of every answer** does it belong in `_build_system_prompt()`. The prompt is 7.3K tokens and was cut from 17.9K precisely because rules accumulated there; adding to it dilutes the rules already earning their place.

Recency beats emphasis: the answer language is restated in the LAST line of the user turn because the system prompt lost to a 19,708-character Catalan guide. Full evidence: `memory/feedback_context_block_beats_prompt_rule.md`.

For each diagnosed problem, apply the appropriate fix:

| Problem Type | Fix Location | Action |
|-------------|-------------|--------|
| Dataset never retrieved (fabrication) | `backend/services/ai/context_builder.py` | Add a `_fetch_*_block` + wire it in all FOUR places (dataclass field, populate, pass to ContextData, render) + a NOT-ON-FILE branch |
| Missing domain knowledge | `backend/knowledge_base/guides/` | Create new .md guide + add keyword triggers in `knowledge_loader.py` GUIDE_KEYWORD_TRIGGERS dict |
| Wrong answer language | `services/ai_service.py` `_detect_query_language()` | Fix the marker/decisive lists; check the new word against the other 5 languages AND common acronyms |
| Invented feature name | `services/ai_service.py` `MEUB_SUBTABS` / `_correct_invented_features()` | Extend the canonical tuple or the guard, not the prompt |
| Reference not hyperlinked | `services/ai_service.py` `_linkify_references()` | Generate the link deterministically in post-processing |
| Per-query constraint ignored | `backend/services/ai/context_builder.py` | Emit a constraint block beside the question (see `_build_competitor_guard_block`) |
| Validator false positive | `backend/services/ai/validator*.py` | Tune the rule; keep `VALIDATOR_SHADOW_MODE=true` until the FP rate is measured |
| System prompt rule missing | `backend/services/ai_service.py` `_build_system_prompt()` | Add a new section with CRITICAL prefix — last resort, only if true of every answer |
| Context builder gap | `backend/services/ai/context_builder.py` | Fix data capping, formatting, missing lookups, or country/entity detection |
| Post-processing bug | `backend/services/ai_service.py` | Fix in `_strip_orphan_citations()`, `_linkify_legislation()`, etc. |
| Acronym/linking error | `backend/knowledge_base/institutions/legislation_acronyms.json` | Add/fix/remove entries |
| Missing feature cross-link | `backend/services/ai_service.py` `_build_system_prompt()` | Strengthen the CROSS-LINK BRUBRU FEATURES rule, or add a feature-specific follow-up template |
| Feature exists but is broken end-to-end | The relevant feature's code path (api + frontend tab) | Route the bug to the feature owner; do NOT mask it with a chat-only workaround |
| Feature does not exist yet | Product backlog | Open a tracked TODO; chat may acknowledge "this isn't yet a one-click feature in My EU Bubble" |

### Knowledge Guide Template

When creating a new guide in `backend/knowledge_base/guides/`:
- Include specific legal act numbers with CELEX codes
- Cover the regulation framework, key dates, institutional landscape
- Add a "Related Legislation" table with CELEX numbers
- Keep to 100-200 lines

Then add keyword triggers in `knowledge_loader.py`:
```python
"guide_filename_without_extension": [
    "keyword1", "keyword2", "multilingual_variant", ...
],
```
Include triggers in English + Catalan + Spanish + French at minimum.

## Step 4: Test Fixes

**Test `/api/chat/stream`, never `/api/chat/message`.** The UI calls the streaming endpoint exclusively. `/message` still exists and still answers, so testing it produces a confident green that proves nothing about what users get — code added to `chat()` alone has shipped dead before. See `memory/feedback_chat_stream_is_the_only_real_path.md`.

```bash
# Start backend if not running
cd /Users/victorsole/Developer/brubru/backend && python3.12 -m uvicorn main:app --reload --port 8000

# Test each query on the path users actually hit
curl -s -N -X POST http://localhost:8000/api/chat/stream \
  -H "Content-Type: application/json" \
  -H "X-Brubru-Probe: 1" \
  -d '{"message": "THE ORIGINAL QUERY", "use_context": true}' \
  --max-time 120
```

**`X-Brubru-Probe: 1` is mandatory on every verification call, local or production.**
It stamps `chat_metadata.is_probe` so tomorrow's audit and `/users` can tell your
traffic from a user's. Omitting it is how 30 of the 33 apparently-real chats in the
11-19 August window turned out to be ours.

**Then run the regression suite before claiming any fix is done:**

```bash
cd /Users/victorsole/Developer/brubru/backend
python3.12 scripts/train_chat_regression.py
```

It replays real production queries through `chat_stream()` in-process and scores language, canonical feature names and legal anchors. Two rules for reading it, learned the hard way: **flags are signals, not verdicts** (the first version of the scorer produced nine false positives out of eleven, and acting on them would have meant inventing fixes for things that already worked), and **`lang` flags use the production detector**, so a detector bug shows up as a language flag on a perfectly correct answer. Read the answer before believing the flag.

Report before/after per query. Verify against production after deploy, not against the branch: `git merge-base --is-ancestor <fix-sha> <deployed-tip>`, then `curl -s https://brubru-production.up.railway.app/api/chat/health | python3.12 -m json.tool` — it reports the running commit and the live provider chain. Railway takes roughly 20 minutes.

## Step 5: Update Audit Log

After completing the audit, update `memory/query_audit.md` with:
- Date audited
- Number of queries reviewed
- Fixes implemented (which files, what was added)
- Test results (before/after comparison)
- Any remaining issues for follow-up

## Step 5b: Regenerate Guides HTML + Sync Data-Architecture (MANDATORY when guides changed)

If any guide was created or updated in Step 3, run:

```bash
cd /Users/victorsole/Developer/brubru/backend
python3.12 scripts/generate_guides_html.py
```

This updates BOTH `frontend/public/guides/index.html` AND the hardcoded guide/trigger counts in `frontend/public/data-architecture/index.html` (via `update_data_architecture_counts()`). Never ship guide changes without this -- the public data-architecture page will display stale numbers otherwise. Both pages deploy with the next `/siteground` build.

## Step 5c: Log every guide change to the KB changelog (MANDATORY when guides changed -- set 8 June 2026)

For EACH guide created or updated in Step 3, append an entry to the KB changelog so it surfaces in MEUB > Brubru Databases > Knowledge Guides ("What's new in the KB" feed). This is a hard rule: KB content edits are otherwise invisible in the product (the Knowledge Guides sub-tab is count-only).

```bash
cd /Users/victorsole/Developer/brubru/backend
python3.12 scripts/kb_changelog.py --action updated --guide <stem> --title "<Title>" --summary "<one-line what changed>" --refs <CELEX...>
# --action: added | updated | canon | deep_dive. Idempotent (dedupes), safe to re-run.
```

The feed is served by `GET /api/databases/kb-changelog` (backend deploy) and rendered on the Knowledge Guides sub-tab (frontend deploy). Full rule + the 6-source Brubru Databases architecture: `memory/feedback_kb_changelog_sync_brubru_databases.md`.

## Step 5d: Hand off every fix to the Chat session via memory (MANDATORY when ANY query-response fix was applied -- set 19 June 2026)

**Every time this skill is run and one or more query-responses are fixed, write or update a memory so the dedicated "Chat" session knows about the fixes and can look at / assess them.** Chat-quality work (system prompt, context builder, guides, post-processing) is owned by a separate "Chat" session the same way API management is owned by the "API" session (see `memory/reference_api_session_owns_api_management.md`). Audit fixes are otherwise invisible to that session — it would re-discover or undo them.

This is a hard rule. The memory is the running ledger of audit-driven Chat fixes. The fix is NOT done until it is logged here.

1. **Append to the rolling Chat-fix ledger** `memory/project_chat_audit_fixes_log.md` (create it the first time). One dated block per audit run, each fix as its own row:
   - **Date** of the audit run + the query window audited.
   - **Defect** (one line) + **severity** + the **layer** it was routed to (system prompt / context builder / guide / post-processing / data).
   - **File(s) + function(s) touched** (e.g. `services/ai/context_builder.py::_fetch_procedure_from_carriage`), or the DB row updated.
   - **Verification** done (unit test, MCP dogfood, local curl) and result.
   - **Status:** `applied (pending deploy)` | `deployed <hash>` | `needs-review`.
   - **For-Chat-session note:** what to re-check or assess next (regression risk, broader pattern to sweep, follow-up owed).
2. **Update `MEMORY.md`** with (or refresh) a one-line index pointer to the ledger so the Chat session loads it on session start.
3. If a fix introduces a NEW reusable rule or a recurring-defect pattern, ALSO create/update the matching `feedback_*.md` memory and cross-link it `[[...]]` from the ledger block.

Keep the ledger append-only by run (newest block on top). It is the primary input when the Chat session next runs `/evaluation Chat` or a chat-quality pass.

## Important Notes

- **Check which interpreter actually has the dependencies before running anything.** The old rule here
  (prefer `python3.12` over `python3`, on the grounds that the latter resolved to 3.14) was measured false on 31 August
  2026: on this Mac `python3` is a **symlink to `python3.12`** (python.org 3.12.5 — same binary, so the
  distinction the old rule drew does not exist), and of the **60** packages in `backend/requirements.txt`
  that interpreter has **35 installed at any version, only 4 at the pinned version, and 25 missing
  entirely** — `pytest` and `python-multipart` among them. The provisioned
  environment is the unversioned **`python`** -> `/opt/anaconda3/bin/python` (3.12.2), with **58 of 60**
  requirements installed, `pytest` at its pinned 7.4.4 and `playwright` at its pinned 1.58.0.
  Enumerate before you choose, and never conclude "X is not installed" from one interpreter:
  ```bash
  for P in python python3 python3.12 python3.13 python3.14; do
    command -v $P >/dev/null || continue
    echo "$P $($P -c 'import sys;print(sys.version.split()[0])') $($P -c 'import pytest;print("pytest")' 2>/dev/null || echo '-')"
  done
  ```
  DB/scraper scripts run fine on python3.12 because they need only the installed subset; anything that
  imports the app or runs the tests needs the anaconda interpreter.
  [[feedback_never_generalise_from_one_dimension]]
- **Latency is 8-13 seconds, not minutes** (was 130.9s before 6 August 2026). A slow answer is now a defect worth investigating, not the normal cost of a knowledge query. Almost all of the old 126-second latency was the Anthropic SDK retrying a Cerebras 429 internally; every client now sets `max_retries=0` because the chain IS the retry.
- **Follow-up turns are still ~4x slower than first turns** (12s → 42-47s). Conversation history pushes the request past the fast providers' rate limits and down onto Mistral. Open and unmeasured — where the ~12,000 context tokens go has not been established, and one attempt to measure it was wrong. If you audit a slow multi-turn conversation, this is the likely cause; do not diagnose it as a retrieval problem.
- **There is no Anthropic in the chat chain.** Removed 6 August 2026 by explicit decision (too expensive: 12% of traffic at ~37,352 tokens an answer). Chain order in `services/ai/multi_provider_service.py`: **Cerebras gpt-oss-120b → Gemini 2.5-flash → Groq llama-3.3-70b → NVIDIA llama-3.3-70b → Mistral → OpenAI**. `prefer_claude` still appears in call signatures but is a **no-op** — do not read it as routing. An `AnthropicProvider` class survives for NON-chat services (AI summaries, content analysis, proactive notifications) via `get_extended_provider_service()`, placed last after every free tier; it must never be added to `get_multi_provider_service()`.
- Do not assume a provider when auditing — read `chat_messages.provider` (Step 1). Both the generator and the validator run on this same chain.
- Mistral reads only ~30% of injected context and may copy verbose system prompt examples verbatim. Use abstract pattern descriptions rather than concrete examples in the system prompt. It sits last among the free tiers for this reason, but follow-up turns still land on it.
- Rapporteur-by-country and drafting intent queries use focused context paths and are faster still
- Never add emojis to code. Use text prefixes for logging: [OK], [INFO], [WARN], [ERROR]
- ECB, EIOPA, ESMA, EBA are institutions, NOT legislation -- never add them to legislation_acronyms.json
- EP API `get_mep_list()` returns historical + current MEPs. Use `limit=500` to cover all alphabetical names (default 100 misses Z-surnames)

## Step 6: Outreach Campaign Monitoring

Check if any users from active outreach campaigns (EU Transparency Register) have signed up or made queries. This runs automatically as part of every audit.

### 6a: New signups from campaign targets

```sql
-- Users who registered from emailed org domains
SELECT u.email, u.created_at, t.name as org_name, t.policy_cluster
FROM users u
JOIN transparency_register_orgs t 
  ON u.email LIKE '%@' || SPLIT_PART(t.contact_email, '@', 2)
WHERE t.outreach_status = 'sent'
AND u.created_at >= t.updated_at
ORDER BY u.created_at DESC;
```

If found, update their status:
```sql
UPDATE transparency_register_orgs SET outreach_status = 'converted' WHERE contact_email LIKE '%@domain';
```

### 6b: Queries from campaign targets

```sql
-- Queries from users whose email domain matches a sent campaign org
SELECT u.email, cm.content, cm.created_at, t.name as org_name, t.policy_cluster
FROM chat_messages cm
JOIN chats c ON cm.chat_id = c.id
JOIN users u ON c.user_id = u.id
JOIN transparency_register_orgs t 
  ON u.email LIKE '%@' || SPLIT_PART(t.contact_email, '@', 2)
WHERE cm.role = 'user' AND t.outreach_status IN ('sent', 'converted')
AND cm.created_at >= '2026-04-08'
ORDER BY cm.created_at DESC;
```

If found, update status to 'responded' (or keep 'converted' if already converted):
```sql
UPDATE transparency_register_orgs SET outreach_status = 'responded' 
WHERE outreach_status = 'sent' AND contact_email LIKE '%@domain';
```

### 6c: Pre-user activity from campaign targets

```sql
-- Page loads, email captures, queries from pre-users with campaign org domains
SELECT event_type, event_metadata->>'email' as email, created_at
FROM pre_user_events
WHERE created_at >= '2026-04-08'
AND event_metadata->>'email' IS NOT NULL
ORDER BY created_at DESC;
```

Cross-reference with campaign org domains.

### 6d: Report

```
OUTREACH MONITORING (since campaign start):
  Campaigns active: Spain (157 orgs, 8 April 2026)
  Signups (converted): X
  Queries (responded): Y
  Pre-user activity: Z page loads, W email captures
  Conversion rate: X / 157 (Z.Z%)
```

Flag any queries that Brubru answered poorly -- these are high-priority fixes since the org was specifically invited.

## Context Builder Features Added (Feb 2026)

These features were added from query audit fixes and handle specific query types:

| Feature | Detection | What It Does |
|---------|-----------|-------------|
| Drafting intent | ACTION_WORD_MAP (50+ words, 6 langs) + DOC_TYPE_TO_TEMPLATE | Detects "draft/write/redacta" queries, boosts templates, injects DRAFTING MODE signal |
| Rapporteur by country | COUNTRY_DEMONYMS (60+ entries) + RAPPORTEUR_INTENT_PHRASES | Fetches OEIL + committee_work rapporteurs, matches against EP API country MEPs |
| Committee full list | Removed [:10] cap | Shows ALL members grouped by Full Members + Substitutes |

## Retrieval Blocks Added August 2026

Added after the fabrication audit. Same wiring pattern as the specialised clusters, each with an explicit NOT-ON-FILE branch.

| Block | Fetch method | Guard it carries |
|---|---|---|
| Parliamentary questions | `_fetch_parliamentary_questions_block` | Do not describe the contents of a question that is not on file |
| Roll-call votes | `_fetch_roll_call_block` | Do not infer an MEP's vote from their political group |
| Lobby meetings | `_fetch_lobby_meetings_block` | Do not name an EU institution as a lobbyist |
| Amendment documents | `_fetch_amendment_documents_block` | Do not invent a PE reference |
| Competitor guard | `_build_competitor_guard_block` | Per-query answer constraint, not a prompt rule |

## Known Open Defects (do not re-diagnose; carry forward)

State as of 10 August 2026. Confirm each is still open before spending audit time on it, and strike it here when fixed.

1. **`mep_lobby_meetings` scraper corruption.** 484 of 1,245 rows carry the literal string "Past meetings" as `mep_name`, with the meeting subject glued onto `organisation` — a scraped section header. Chat filters them at query time; the **Lobby Meetings tab still shows them**. Route to the feature, not to Chat.
2. **`eu_laws.policy_area` misclassification**, e.g. pesticide residue limits (32022R0085) tagged "Digital Policy and Digital Economy". Affects any answer that leans on policy_area filtering.
3. **`procedure_snapshots` and `eu_comitology_committees` are still unretrieved** — fabrication risk by the Step 2 rule.
4. **Validator false-positive rate is unmeasured and visibly non-zero** (Step 1c). Shadow mode stays on.
5. **Follow-up latency ~4x first-turn**, cause unmeasured (see Important Notes).
6. **Mobile chat rendering has never been visually verified.** The Chrome extension's `resize_window` does not reflow the page viewport, so 375/390px was never actually rendered. The CSS path is patched but unproven — if a mobile user reports layout trouble, believe them.

## Specialised EC Database Clusters (Layer 1, May 2026)

Ten on-demand context blocks added to `services/ai/context_builder.py`. Each fires when the user's query matches the cluster's intent regex, queries the backing table (or live API), formats a 4 kB block, and injects it at the TOP of `format_context_for_ai()` so it survives the 32 k truncation cap.

| Cluster | Intent regex tag | Fetch method | Source |
|---------|------------------|--------------|--------|
| sanctions | `sanction(s)/restrictive measures/asset freeze/CFSP/SDN list` | `_fetch_sanctions_block` | `eu_sanctions` DB |
| transparency_register | `lobby(ing/ist)/interest representative/transparency register/EP pass` | `_fetch_transparency_register_block` | `eu_transparency_register` DB |
| comitology | `comitology/implementing act/SCoPAFF/examination procedure/voting sheet` | `_fetch_comitology_block` | `eu_comitology_documents` DB |
| gi | `PDO/PGI/TSG/geographical indication/protected designation` | `_fetch_gi_block` | `eu_geographical_indications` DB |
| fta | `FTA/EPA/AA/PCA/CETA/trade agreement/EU-<partner>` | `_fetch_fta_block` | `eu_trade_agreements` DB |
| td | `anti-dumping/countervailing/safeguard/expiry review` | `_fetch_td_block` | `eu_trade_defence_measures` DB |
| comp | `state aid/cartel/merger/SA./M./AT./Article 101/102` | `_fetch_comp_block` | live api.tech.ec.europa.eu |
| jrc | `JRC dataset/Joint Research Centre/ESDAC/EFFIS/GHSL/LUISA` | `_fetch_jrc_block` | `eu_jrc_datasets` DB |
| cohesion | `ESF+/ERDF/cohesion fund/just transition/interreg/RRF` | `_fetch_cohesion_block` | `eu_cohesion_datasets` DB |
| cn | `CN code/HS code/tariff code/Combined Nomenclature` | `_fetch_cn_block` | live webgate.ec.europa.eu/nomen |

**Audit-time check:** any query matching one of these regexes should produce a specialised cluster block in the chatbot's response (cite a specific person/lobbyist/document/case/dataset rather than generic policy text). If the response is generic, diagnose in two steps:

1. **Does the intent fire?** Run `cb._detect_<cluster>_intent("<user query>")` in Python. If it returns `None`, fix the regex.
2. **Does the fetch return data?** Run `await cb._fetch_<cluster>_block(query, intent)`. If it returns `None`, either the term extraction missed (check stopwords, demonym map) OR the underlying table needs a delta backfill — queue in `memory/specialised_backfill_queue.md`.

Negative-query regression: every audit run should include 1-2 queries that should NOT light up any specialised cluster (e.g. "What is the AI Act?"). False positives on a generic query mean the regex is too broad — narrow with stricter word boundaries or specific anchor phrases.

Verified end-to-end on 11 May 2026: 10/10 positive queries pass; 0/6 negative queries trigger false positives. Reference: `memory/project_specialised_ec_databases.md`.
