# Brubru API — Victor's 12 points, analysed

Prepared 20 April 2026. Companion to Jordi's 13-point email (his feedback is point 13, kept separate).

Execution plan at the bottom: Monday = P0 bugs, Tuesday = docs + pricing removal + soft-paywall. Wednesday = Jordi meeting.

---

## Point 1 — Documentation

**Current state**
- `/api/docs` serves Scalar auto-rendered from FastAPI's OpenAPI spec. Endpoint-by-endpoint reference only.
- No Introduction, no Authorization page, no EU-institutions-covered page, no glossary.
- Field descriptions come from Pydantic `description=` inline — incomplete and uneven.
- No example request/response bodies stored in the spec (we add them manually in Postman but not in FastAPI).
- Zero beginner-friendly content — someone who doesn't know what CELEX means cannot use our API.

**What we need (Stripe/GitHub standard order)**
1. **Introduction** — what Brubru API is, motivation, data sources + refresh cadence (real-time / daily / weekly per source), limitations.
2. **Authentication** — API key lifecycle, rotation, Bearer vs `X-API-Key`, what happens on leak.
3. **Requests & responses** — canonical envelope spec, pagination model, filter-alias rules, error shape, rate-limit headers.
4. **Endpoints** — one page per endpoint group with parameters table + enum values + 3 example calls (success, filtered, error).
5. **EU institutions covered** — matrix: institution × what Brubru has × refresh cadence × source URL. Explicit about what we *don't* have.
6. **Glossary** — CELEX, OEIL, trilogue, rapporteur, shadow rapporteur, ECOM/EPRS/CRE, directive vs regulation vs decision, committee role (responsible / opinion / associated), legislative procedure types (OLP / consultation / consent), transposition deadline. Each 2-3 sentence lay explanation.
7. **Use cases** (overlaps with point 12) — by persona.
8. **Changelog** — versioning policy + dated endpoint changes.

**Build**
- Static microsite at `brubru.beresol.eu/api/docs/` — multi-page React subapp or plain HTML site.
- Source of truth: markdown collection in `docs/api-reference/`.
- Endpoint reference pages can embed Scalar for try-it-live, surrounded by written context.

**Effort:** 4-5 days writing + styling.

**Decision:** English first, translate after Wednesday's meeting ✅

---

## Point 2 — Introduce parameter `full`

**Current state**
- `detail_level` **exists** in the envelope (`_envelope.py`: `Literal["Minimal", "Summary", "Full"]`).
- **Accepted** as a query param in some endpoints but **not honoured** — setting `?detail_level=Full` changes nothing. Ornamental.
- GovClipping's convention is `detail_level=summary|full` (lowercase); we use capitalised.

**What `full` should return**

| Endpoint | `Summary` (default) | `Full` adds |
|---|---|---|
| `/laws` | celex, title, doc_type, adopted_on, policy_area | `legal_basis`, `citations`, `subject_matter`, `defined_terms_count`, `recital_count`, `text_excerpt` (first 2000 chars) |
| `/procedures` | id, title, oeil_procedure_ref, current_status, lead_committee | `oeil_key_events`, `rapporteur_mep_id` + name, `shadow_rapporteurs`, `committees_roles`, `celex_numbers`, `ai_summary` |
| `/eprs` | id, title, publication_type, publication_date, summary | `full_text` (first 10k chars), `related_celex_resolved` with titles |
| `/publications` | id, title, url, institution, date | `html_content` (first 5k chars), `tags_resolved` |
| `/commissioners/{name}/agenda` | date, title, location | `detail_url`, full description, attendees |

**Decision:** accept both `full` and `Full` ✅. Canonical response echoes whatever the client sent.

**Effort:** 2 days.

---

## Point 3 — Connect Brubru API / MCP to Claude, ChatGPT, Gemini

**Current state**
- **Claude:** `backend/mcp_server.py` exposes 6 MCP tools. Does NOT yet cover our 24 v1 REST endpoints.
- **ChatGPT:** Nothing. Needs GPT Action definition (OpenAPI 3.1 spec + CustomGPT setup).
- **Gemini:** Nothing. Needs Google Function Calling spec.

**Plan**

### 3.1 Claude (MCP)
- Expand `mcp_server.py` from 6 → 24 tools, one-for-one with v1 endpoints.
- Each MCP tool = thin `httpx.get(BASE + path, headers={"Authorization": f"Bearer {api_key}"})` wrapper.
- Publish to `claude-mcp-registry` and `smithery.ai`.
- Claude Desktop config snippet: `{ "brubru": { "command": "npx", "args": ["-y", "@brubru/mcp"] } }`.

### 3.2 ChatGPT (GPT Actions)
- Export OpenAPI 3.1 spec (already at `/api/v1/openapi.json`).
- ChatGPT: **Create GPT → Configure → Add Actions → Import from URL** → auto-creates one action per endpoint.
- Publish the "Brubru EU Data" CustomGPT to ChatGPT's GPT Store.
- Requires clean spec (no 500s — legal-text/recital-map is blocking).

### 3.3 Gemini (Function Calling)
- Write `backend/scripts/openapi_to_gemini.py` converting OpenAPI → Gemini tool schema.
- Publish as code sample: `from brubru import gemini_tools; model = genai.GenerativeModel("gemini-1.5-pro", tools=gemini_tools)`.
- No marketplace; distribution is a blog post + docs page.

**Effort:** Claude 2 days / ChatGPT 0.5 day / Gemini 1 day.

**Decision:** publish `@brubru/*` npm + `brubru` pip packages ✅

---

## Point 4 — Dashboard for GovClipping's clients

**Current state:** API exists. Jordi has frontend. Nothing bridges them.

**Three options**

### 4.1 Embeddable web components (lowest effort, highest leverage)
Publish `@brubru/widgets` npm package with custom elements:
- `<brubru-law celex="32016R0679"></brubru-law>`
- `<brubru-procedure ref="2025/0232(COD)"></brubru-procedure>`
- `<brubru-eu-calendar institution="EP" days="14"></brubru-eu-calendar>`
- `<brubru-stakeholder-feedback initiative="13174"></brubru-stakeholder-feedback>`
- `<brubru-transposition spanish-doc-id="...">` — resolves Spanish BOE decree → parent EU directive.

Jordi drops a `<script>` tag, injects his client's API key from cookie/session, ships a UE tab in two days. "Powered by Brubru" stamped automatically.

### 4.2 React SDK (`@brubru/react`)
Higher-level hooks: `useBrubruLaw(celex)`, `useBrubruProcedure(ref)`, `<BrubruContextSidebar doc={bocDoc} />`.

### 4.3 Full dashboard blueprint
Reference "UE module" — complete React app Jordi forks/copies, restyled to GovClipping palette.

**Recommendation for Wednesday:** propose 4.1. Validate the 5 most valuable widgets directly with Jordi in the meeting.

**Effort:** 1-2 weeks for 5 widgets + npm publish + docs.

---

## Point 5 — Remove pricing from `/api/`

**Current state:** `frontend/src/pages/api_page.tsx` lines 231-260 render full pricing table (Starter 39 / Advocate 59 / Professional 99). Sidebar nav includes "Pricing" link.

**Fix**
- Delete `<section id="pricing">` block.
- Remove `"pricing"` from `navItems`.
- Remove `api.pricing.*` i18n keys from six locale JSONs (or keep but stop using).
- Replace with a CTA: *"Ready to integrate? Contact hello@beresol.eu to activate Professional access."*
- Link CTA to `/subscription`.

**Effort:** 30 min.

---

## Point 6 — Commissioners `detail_url` is null

**Current state:** `commissioner_agenda_client.py` line 262 sets `AgendaItem(..., detail_url=href)`. `href` comes from parsed HTML. v1 endpoint maps it straight to JSON.

**Why null**
- Commission calendar HTML scraped; `<a>` tag `href` is blank or doesn't exist.
- Possibly relative `href="#"` or anchors evaluating to empty.
- `_parse_items()` selector expects `article.ecl-content-item--inline > a[href]` but DOM may have link nested deeper or page structure changed.

**Fix**
1. Fetch live commissioner page (e.g. Fitto's calendar) and inspect current DOM.
2. Adjust parser selector.
3. If no per-item detail URL exists, build one: `https://commission.europa.eu/.../calendar/calendar-item/{leader_id}/{item-slug}`.
4. Fallback: populate with `profile.bio_url + "#agenda"` so never null.

**Effort:** 2-3 hours.

---

## Point 7 — Show the official source of the URLs

**Current state**

| Endpoint | Source URL field | Status |
|---|---|---|
| `/laws` | `eurlex_url` | ✅ |
| `/laws/{celex}/text` | `eurlex_url` | ✅ |
| `/procedures` | `url` (OEIL) + `legal_text_url` | ✅ |
| `/publications` | `url` | ✅ |
| `/eprs` | `html_url`, `pdf_url` | ✅ |
| `/commissioners/{name}/agenda` | `detail_url` | ⚠️ often null (point 6) |
| `/consultations/by-initiative/{id}/feedback` | `public_url`, `portal_url`, `feedback_url` | ⚠️ some stale per Jordi |
| `/calendar/events` | `source_url`, `agenda_url` | ✅ |
| `/committees/{code}/work-items` | ❌ missing | Add `ep_url` |
| `/committees/{code}/minutes` | `pdf_url`, `doc_url`, `source_url` | ✅ |
| `/meps` | `profile_url` | ⚠️ often null |
| `/knowledge-guides` | ❌ N/A (our content) | Add `canonical_source` pointing to EUR-Lex/EC page |
| `/predictions/{ref}/*` | ❌ missing | Add `procedure_url` pointing to OEIL |

**Fix**
- Add `source_url` to every envelope item where we source externally. Where sourced from Brubru's own (knowledge guides, predictions), add `canonical_source` pointing to the underlying EU page.
- **Mandatory in Pydantic** (not Optional) so we can't ship null source URLs.
- OpenAPI description: every data item has a traceable source — this is the "Powered by Brubru" attribution anchor.

**Effort:** 1 day.

---

## Point 8 — Total at-the-moment EU monitoring

**Current state:** zero unified feed. Clients call 8+ endpoints and merge client-side.

**Design: `GET /api/v1/activity`**

```
GET /api/v1/activity?since=2026-04-13&until=2026-04-20&limit=100&detail_level=Summary
```

Chronological union of:
- Laws published in OJ (`eu_laws.date`)
- Procedures that changed stage (`legislative_carriages.status_history`)
- New Commission proposals (`commission_documents`)
- New amendments tabled (`mep_amendments`)
- New draft reports (`amendment_documents.document_type='PR'`)
- EP resolutions (`ep_resolutions`)
- Council meetings held (`eu_calendar_events` where `institution='COUNCIL' AND status='adopted'`)
- Commissioner appointments / portfolio changes
- Consultations opened/closed (`public_consultations`)
- New EPRS publications

Item shape:

```json
{
  "activity_type": "law_published" | "procedure_stage_change" | "amendment_tabled" | ...,
  "timestamp": "2026-04-15T14:00:00Z",
  "title": "...",
  "summary": "...",
  "entity_type": "law" | "procedure" | "amendment" | ...,
  "entity_id": "32016R0679",
  "source_url": "...",
  "related_refs": { "celex": "...", "procedure": "...", "committee": "..." }
}
```

**Weekly cadence** (Victor's ask: "in an incremental way, see what has been compounded in a weekly cadence"):
- `/api/v1/activity?since=<monday>&until=<sunday>&group_by=day` → 7 daily buckets.
- `/api/v1/activity/digest?week_of=2026-04-13` returns curated briefing (top 10 by importance) for email.

**Decision:** chronological first ✅. Ranking is v2.

**Effort:** 4-5 days. Needs DB indexes on every source table's date column.

---

## Point 9 — B2B: each client needs their own API key

**What we have**
- `api_keys` table with `user_id FK`, SHA-256 hash, `scopes` JSONB (unused), prefix, revoked_at.
- Admin endpoints to mint/list/revoke keys.
- 60 req/min soft rate limit per key.
- Auth accepts Bearer and `X-API-Key`.

**What we're missing for real B2B**
- No **organisation** concept — keys are tied to individual users. If Jordi's CTO also wants a key, they need a second user.
- No self-serve key generation UI. Admin mints manually.
- `scopes` field exists but is ignored. All keys have full API access.
- No per-key monthly quota.
- No usage analytics visible to the customer.
- No per-key audit log visible to the customer.

**Plan**

| Step | Scope |
|---|---|
| 9.1 | Add `organisations` table; `api_key` belongs to an org. Users belong to orgs with roles (admin/member). |
| 9.2 | Self-serve UI at `/account/api-keys` for Professional subscribers to mint/revoke/name keys. |
| 9.3 | Enforce `scopes` at auth time — `read:all`, then per-endpoint-group (`read:laws`, `read:meps`). |
| 9.4 | Monthly request-count quota + `X-RateLimit-Monthly-Remaining` header. |
| 9.5 | Usage dashboard at `/account/api-keys/{id}/usage`: requests/day, top endpoints, error rate. |

**Decision:** wait until 3+ paying partners ✅. Jordi alone = one org = one user is fine.

**Effort:** 1 week for 9.1-9.4. +1 week for 9.5.

---

## Point 10 — Paywall `/api/docs` for paying customers

**Current state**
- `/api/` public — full endpoint list, envelope schema, pricing table, curl example. Indexed by Google.
- `/api/docs` public — full OpenAPI reference via Scalar.
- `/api/v1/openapi.json` public (needed for Postman).
- `/api/v1/ping` public (health check).

**Soft-paywall plan**

| Page | Who sees | Behaviour |
|---|---|---|
| `/api` (marketing) | Everyone | Endpoints summary, envelope, auth overview, CTA to Professional. **No pricing** (point 5). |
| `/api/docs` (Scalar) | Everyone but gated | Spec renders. Each "Try it" button checks Professional tier. Non-auth users see tooltip: *"Upgrade to Professional to execute live calls."* Spec viewable, execution gated. |
| `/api/v1/openapi.json` | Everyone | Keep public; Postman needs it. No key leak. |
| `/api/guides` (new, point 12) | Everyone | Short versions public; full versions Professional. |
| `/account/api-keys` | Professional only | Self-serve key management (point 9). |

**Alternative path** (Victor's suggestion): `/api/developer/` = paying-customer detailed reference. `/api/` remains marketing.

**Decision:** soft-paywall ✅

**Effort:** 1 day.

---

## Point 11 — Laws filter bug (`published_to` + `published_end`)

**Current state after inspection:** `laws.py` accepts `published_from`, `published_to`, `published_end` (alias). Code: `if published_end and not published_to: published_to = published_end`. Live test with `published_from=2026-01-01&published_to=2026-03-31&limit=3` returned `total: 0` — filter IS working.

**Why Jordi saw 25,510**
- Most likely: he passed **only `published_end`**, mapped to `published_to`, but DB has laws from 1950s-2026 so `date <= 2026-03-31` matches almost everything. He interpreted this as "ignored the filter".
- Alternate: both `published_to` and `published_end` passed with different values. My code picks `published_to` silently and discards `published_end`. If he sent `published_to=2026-01-01, published_end=2026-03-31`, code filters `date <= 2026-01-01` → most of the DB (pre-2026 laws).

**Root causes**
1. Silent parameter mapping: if both sent, one is silently ignored.
2. No `published_from` required when `published_to` present — partners think they're bounding a range.
3. Parameter naming is confusing (`published_to` vs `published_end` look like a range pair).

**Fix**
1. **Keep both params** (Victor's decision).
2. **Clarify semantics**:
   - `published_from` = lower bound (`date >= value`).
   - `published_to` = upper bound (`date <= value`). Preferred name.
   - `published_end` = exact alias of `published_to` for GovClipping-compatibility. Documented as alias, not different semantic.
3. **Reject conflicting values**: if both passed with different values → 422 `reason_code: "conflicting_params"`.
4. **OpenAPI description**: *"omit `published_from` to match everything up to `published_to`"*.
5. **Tests**: `test_laws_date_filter_combinations.py` — 6 combinations (from only, to only, both, end only, both+end conflict).

**Effort:** 4 hours.

---

## Point 12 — User-persona API guides

**Current state**
- `brubru_client_pitch.html` defines 6 personas: public-affairs consultant, corporate in-house, trade association policy lead, EU official, parliamentary assistant, NGO/civil society.
- `brubru_business_plan.html` "Competitive" section lists competitors.
- Zero API documentation by persona — endpoint-first, not use-case-first.

**Addition to docs microsite: `/api/guides/`**

One page per persona + one page per competitor integration pattern. Each answers: *"I am a [persona]. What do I call, in what order, to do my job?"*

### Persona pages (~800 words each)

**1. Public-affairs consultant**
- Morning monitoring: `/activity?since=yesterday` → filter client's policy areas → `/laws` + `/procedures` per hit.
- Briefing prep: `/procedures/{ref}` + `/eprs?procedure_ref={ref}` + `/committees/{code}/minutes` + `/predictions/{ref}/timeline`.
- Draft prep: `/legal-text/{celex}/defined-terms`.

**2. Corporate in-house / compliance officer**
- Regulation detection: `/laws?q=<keywords>` + `/publications?q=<keywords>` alert loop.
- Transposition check: `/legal-text/resolve-aliases` on national gazette → find EU parent → `/procedures/{ref}/timeline`.
- Stakeholder watch: `/consultations/by-initiative/{id}/feedback?country={iso3}`.

**3. Trade association policy lead**
- Committee calendar: `/calendar/events?institution=EP&committee={code}` + `/committees/{code}/work-items`.
- Amendment intelligence: (future) `/amendments?procedure={ref}`.
- Position coordination: `/meps?group={party}&country={iso2}`.

**4. EU official (Commission/EP/Council/agency)**
- Cross-institution snapshot: `/activity?institution_filter=all`.
- Historical: `/laws?q=<topic>&published_from=<year>` + `/procedures?committee=<code>`.
- Semantic layer: `/legal-text/resolve-aliases` to standardise internal memos.

**5. Parliamentary assistant (MEP staff)**
- MEP's file tracking: `/procedures?rapporteur_mep_id={id}`.
- Committee prep: `/committees/{code}/minutes?date_from=<last-meeting>` + `/committees/{code}/work-items`.
- Draft support: `/eprs?procedure_ref={ref}`.

**6. NGO / civil society advocate**
- Campaign monitoring: `/consultations?status=open&policy_area=environment` → `/consultations/by-initiative/{id}/feedback`.
- Amendment drafting: `/laws/{celex}/text?format=plain` + citations via `/legal-text/resolve-references`.
- Media-ready briefs: `/knowledge-guides?q=<topic>` + `/predictions/{ref}/outcome`.

### Competitor integration patterns

- **GovClipping pattern:** Spanish-gazette-triggers-EU-context loop (the three demos in the partnership proposal).
- **RegTech platform pattern:** how a Spaak-style competitor would consume us without losing their data moat (we're the EU layer; they keep sector expertise).
- **Consultancy firm internal:** Boston Consulting Group / EY style — `/activity` as daily stand-up input.
- **Academic/researcher:** policy-school researcher builds a dataset of all amendments in a legislative term.

**Tone requirement:** written for someone who has *never* used an API *and* for someone who has. Each page opens with plain-language summary (2 paragraphs, no jargon), then actual calls (curl + Python + JS), then glossary inline.

**Effort:** 2-3 days writing + 1 day persona review.

---

## Execution plan (confirmed)

### Monday 20 April — P0 bugs
- Fix 11 correctness bugs surfaced by Jordi.
- Fix point 6 (commissioner `detail_url`).
- Fix point 11 (laws filter + 422 on conflicting params).
- Wire point 2 (`detail_level=full` actually does something).
- Wire point 7 (`source_url` mandatory everywhere).
- Ship as 3 commits, verified by `/training api`.

### Tuesday 21 April — Docs & pricing
- Point 5 (remove pricing from `/api/`).
- Point 10 (soft-paywall `/api/docs`).
- Point 1 docs microsite skeleton at `/api/docs/` with 8 sections (Introduction, Authentication, Requests & responses, Endpoints, EU institutions, Glossary, Use cases, Changelog).

### Wednesday 22 April — Jordi meeting
- Final prod sweep.
- Walk into the call with every point checked.
- Validate point 4 (widgets vs SDK vs full dashboard) and point 8 (activity endpoint design) directly with him.

### Week of 28 April
- Point 12 (persona + competitor guides, 10 pages).
- Point 1 glossary fleshed out.

### Week of 5 May
- Point 3 (MCP expansion + ChatGPT GPT + Gemini Function Calling).

### Week of 12 May
- Point 8 (`/api/v1/activity` endpoint).

### Later (deferred)
- Point 4 (widgets package).
- Point 9 (multi-tenant B2B) — wait for 3+ paying partners.

---

## Decisions captured

| Point | Decision |
|---|---|
| 1 | Docs in English first, translate after Wednesday |
| 2 | Accept both `full` and `Full` |
| 3 | Publish `@brubru/*` npm and `brubru` pip packages |
| 8 | Chronological first, ranking in v2 |
| 9 | Wait for 3+ paying partners before multi-tenant |
| 10 | Soft-paywall |
| 11 | Keep both `published_to` and `published_end`, clarify semantics |
