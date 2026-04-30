# Jordi feedback — meeting 30 April 2026, 15h

Live notes from the GovClipping meeting. Punch list for the next iteration sprint. Each item has a status, a target, and a verification step. We iterate endpoint-by-endpoint until Jordi signs off.

---

## Cross-cutting (apply to ALL endpoints)

### 1. Expose raw content of every item — not just the title

**Problem.** RegTech users (Jordi's audience) tend to enter keywords as their item "title", so the title alone is useless for matching. The API must return the actual body / raw content for every record so consumers can full-text match against it themselves.

**Target.** Every list and detail endpoint must, at `detail_level=Full`, expose the body field that exists in our DB:
- `/laws` → `text_html`, `text_plain`, `text_xml_url`
- `/amendments` → `original_text`, `proposed_text`, `justification`
- `/parliamentary-questions` → `question_text`, `answer_text`
- `/research-publications` → `abstract`, `pdf_url` (already present), `pdf_text` (extracted)
- `/commission-register-documents` → `pdf_url` (present), `pdf_text` (extracted), `description`
- `/reports`, `/opinions`, `/resolutions`, `/texts-adopted`, `/texts-submitted` → `body_text`, `pdf_url`
- `/publications`, `/press-releases` → `summary`, `body_html`, `body_plain`
- etc.

**Verification.** For each endpoint, hit `?detail_level=Full&limit=1` and check the response includes the body field. If the field is null because the underlying row hasn't been enriched yet, flag the row count for backfill.

Status: TODO

---

### 2. Remove the `meta` envelope wrapper

**Problem.** Every paginated response currently includes a `meta: { source, powered_by, fetched_at }` block. Jordi: "this should not be incorporated, remove it from every single endpoint."

**Target.** Drop the `meta` block entirely. The same information already lives on response headers (`X-Powered-By`, `X-Source`) for clients who care; the envelope is noise for everyone else.

**Verification.** `curl ... | jq 'has("meta")'` returns `false` on every response.

Status: TODO

---

### 3. Separate person profiles from their agendas (commissioners)

**Problem.** The `/commissioners/{name}` endpoint currently bundles the profile AND the agenda fields together. Jordi: "agendas are NOT metadata. If the user types `/api/v1/commissioners/fitto/agenda` they should see the AGENDA, not the profile."

**Target.** Two clearly separated endpoints:
- `GET /api/v1/commissioners` — list of all 27 College members with profiles only
- `GET /api/v1/commissioners/{name}` — profile + bio + portfolio + URLs
- `GET /api/v1/commissioners/{name}/agenda` — events only, NOT the profile

**Verification.** `curl /api/v1/commissioners/fitto` returns only profile fields; `curl /api/v1/commissioners/fitto/agenda` returns only event fields.

Note: same pattern probably applies to `/officials/{id}` (profile vs. anything time-bound), `/meps/{id}` (profile vs. votes/amendments tabled).

Status: TODO

---

### 4. Rate limit clarification + an Enterprise tier

**Problem.** Jordi asked whether 60 is per minute, hour, day, or week. He needs much higher — effectively unlimited.

**Current.** 60 requests / minute, sliding window, per API key. Documented in `/api/docs/rate-limits.html`.

**Target.**
- **Tier-based rate limits**: Starter 60/min, Professional 300/min, **Enterprise: 6000/min** (or `unlimited` flag).
- Surface `X-RateLimit-Tier` header so the client knows which bucket they're in.
- For GovClipping specifically: provision an Enterprise key with the high-rate flag.

**Verification.** Issue an Enterprise key, hit `/api/v1/whoami`, confirm `rate_limit_limit` ≥ 6000. Document in `/api/docs/rate-limits.html`.

Status: TODO

---

### 8. Detail level must be Full by default and complete

**Problem.** Detail levels Minimal / Summary / Full exist but the Full level is incomplete — it doesn't ship every column we have in the DB (subtitle, author, doc_type, publication_date, raw_content, source_url, etc.).

**Target.**
- Audit every endpoint's Full schema against its DB columns. Anything in the DB that is not personal-data / not a join key should ship at Full.
- Default `detail_level=Full` on detail endpoints (`/{id}`); keep `Summary` as default on list endpoints to keep payloads sane.
- Fields that must always be present at Full: `id`, `title`, `subtitle`, `summary`, `body_text` or `body_html`, `pdf_url`, `source_url`, `published_at`, `updated_at`, `author` (or rapporteur / DG / committee), `doc_type`, `language`, `metadata` (whatever is genuinely metadata after item #2).

**Verification.** Per-endpoint diff between SQLAlchemy model columns and Pydantic schema fields at Full.

Status: TODO

---

## Data storage

### 6. Are we fetching every single EP committee agenda?

**Source URL.** `https://www.europarl.europa.eu/committees/en/meetings/meeting-documents`

**Problem.** Jordi wants confirmation we ingest every committee meeting agenda. These are typically PDF.

**Target.**
- Audit `committee_meeting_agendas` (or whatever the table is) — count of agendas per committee per year vs. count on the EP page.
- Surface the PDF URL at every layer: in `/calendar/events`, in `/committees/{code}/work-items`, in `/webstreams`.
- Consider OCR/text extraction so the body becomes searchable (item #1).

**Verification.**
- For each of the 22 committees, scrape the EP meeting-documents page with the committee filter, count published agendas in the last 90 days, compare to DB count. Report any > 5 % delta.

Status: TODO

---

## API itself

### 7. Calendar events need per-event URLs

**Problem.** Every event currently points to a generic `committees/en/documents/latest-documents` URL. That's useless.

**Target.** Every `calendar/events` row must carry:
- `source_url` — the URL of the specific event (committee meeting page, plenary session page, college meeting page).
- `agenda_pdf_url` — link to the agenda PDF when the event is a committee/plenary meeting.
- `webstream_url` — already done for `committee_meeting` events; ensure it's also there for plenary.

**Verification.** `curl /api/v1/calendar/events?limit=20` — every row must have a `source_url` that is unique to that event (not a list-index page).

Status: TODO

---

## How we work this sprint

1. **Audit phase** — Run a programmatic audit of every endpoint, capture a sample response, flag every breach of items 1–8 above, surface in a single report.
2. **Iteration phase** — Endpoint by endpoint: change → restart → re-test → re-audit → mark resolved → move on.
3. **Sign-off phase** — Final pass with Jordi against a known set of his own real queries.

Updates land in this file (status field per item) and in `docs/govclipping/brubru-api-analysis.md` as a Section L.
