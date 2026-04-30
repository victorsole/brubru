# Brubru API audit against Jordi feedback — 30 April 2026, 14h25 UTC

Audit script: `backend/scripts/audit_jordi_feedback.py`. Sample responses saved under `/tmp/jordi_audit/`.

Pulled one representative call from every collection at `detail_level=Full`, captured envelope keys, item keys, body-content presence, URL presence, and HTTP status.

---

## Executive summary

| Issue (Jordi #) | Severity | Confirmed on | Notes |
|---|---|---|---|
| #2 `meta` envelope still in body | HIGH | **31 / 36 list endpoints** | Easy global fix: drop the block in the envelope serialiser. |
| #1 / #8 raw body content missing | HIGH | 13+ endpoints | Some columns exist but are NULL (parl-questions, tris, tenders, knowledge-guides Full); some are not in the schema at all (laws-detail has no `summary`/`body`). |
| #3 commissioners profile vs. agenda not separated | HIGH | confirmed | `/commissioners/{slug}` returns 404 (no profile endpoint exists). `/commissioners/{slug}/agenda` injects profile fields next to events. |
| #4 rate limit too low for partner | HIGH | confirmed | `whoami` returns `rate_limit_limit: 60` for the blue tier. No Enterprise tier wired. |
| #6 EP committee meeting documents | TODO | needs DB count vs. EP page | Run `services/scrapers/ep_committee_meetings_scraper.py` count vs. live HTML count per committee. |
| #7 calendar per-event URLs | HIGH | confirmed | `committee_week` rows all point to the generic `committees/en/documents/latest-documents`. Same for plenary roll-ups. |
| Regression: 4 endpoints return 4xx/5xx | BLOCKING | `/meta/dgs`, `/meta/committees`, `/meta/policy-areas`, `/commissioners/{slug}`, `/citations/verify`, `/predictions/{ref}/timeline` | Either un-routed, removed, or upstream broken. |

---

## Cross-cutting fixes (do these first — they touch every endpoint)

### CC-1. Drop the `meta` envelope block (Jordi #2)

**Where:** the canonical `PaginatedResponse[T]` Pydantic schema in `backend/api/v1/_envelope.py` (or wherever the envelope is serialised). The `meta: { source, powered_by, fetched_at }` is added unconditionally.

**Fix:** make `meta` optional, drop it from the default serialiser. Keep the same information on response headers (already there as `X-Powered-By`, `X-Source`, `Date`). Newman/Postman will keep working — neither asserts on `meta`.

**Verification:** `audit_jordi_feedback.py` re-run; expect `meta_envelope` count to drop from 31 → 0.

---

### CC-2. Default `detail_level=Full` to ship the body (Jordi #1, #8)

**Pattern.** For every endpoint, the SQL row already has the body column we need; the Pydantic Full schema needs to expose it.

| Endpoint | Body field to surface at Full | Status today |
|---|---|---|
| `/laws/{celex}` | `summary`, `text_plain` (or link to `/laws/{celex}/text`) | NEITHER. Only metadata. |
| `/laws/{celex}/text` | `content` | OK (351 KB GDPR) — but `text` field name in audit hint missed it. Field is `content`. |
| `/parliamentary-questions` | `text_question`, `text_answer` | Schema exists, **rows are NULL** — backfill needed |
| `/tris-notifications` | `full_text_summary`, `main_content` | Schema exists, NULL — backfill |
| `/tenders` | `summary` | NULL |
| `/knowledge-guides` (detail at Full) | `content` (full body, not preview) | Truncated to `content_preview`. `?detail_level=Full` should ship the whole body. |
| `/reports`, `/opinions`, `/resolutions`, `/texts-adopted`, `/texts-submitted` | `body_text`, `body_html` | not in schema — would need column + backfill from `document_url` PDFs |
| `/commission-register-documents` | `pdf_text` (extracted) | not in schema — column + backfill |
| `/research-publications` | `abstract`, `pdf_text` | partial: `abstract` sometimes; `pdf_text` not extracted |
| `/publications`, `/press-releases` | `summary` (already there in some rows), `body_html` | inconsistent across sources |
| `/consultations` | `description` | OK, present in the call we sampled |
| `/council-documents` | `summary`, `body` | NULL on the sampled row |

**Decision needed.** Two paths:
- **(a) Schema-only fix** — expose the columns we already have (parliamentary-questions, tris, tenders, knowledge-guides body). One-day work, no scrape backlog. Many rows will still be NULL.
- **(b) Backfill** — run text-extraction scrapers / PDF OCR over the document_url backlog so the body fields are actually populated. Multi-day work; ranks by row count (56k amendments are already populated; 1k reports + 1.4k procedures + parl-questions are not).

Recommend **(a) this sprint**, **(b) over the next 2 weeks** as a separate ingest task that doesn't block the partner deal.

---

### CC-3. Fix the four broken endpoints (BLOCKING)

| Endpoint | Status | Diagnosis |
|---|---|---|
| `/api/v1/meta/dgs` | 404 | Earlier sprint moved metadata under different paths. Need to map back: `/meta/dgs` → `/metadata/dgs` rename, OR re-add `/meta/*` aliases. |
| `/api/v1/meta/committees` | 404 | Same. |
| `/api/v1/meta/policy-areas` | 404 | Same. |
| `/api/v1/commissioners/{slug}` | 404 | **No detail endpoint exists.** Only `/commissioners` (list) and `/commissioners/{slug}/agenda`. Profile is bundled into agenda response (#3). |
| `/api/v1/citations/verify?q=...` | 404 | Endpoint documented but not deployed. Check `backend/api/v1/__init__.py` registration. |
| `/api/v1/predictions/{ref}/timeline` | 502 | Upstream error from prediction service. Either ML pickle not loaded on Railway, or feature builder failing. Investigate logs. |

---

### CC-4. Separate commissioner profile from agenda (Jordi #3)

**Today:**
```
GET /commissioners              -> list with profile fields
GET /commissioners/{slug}       -> 404
GET /commissioners/{slug}/agenda -> agenda DATA + commissioner_name/portfolio/country/bio_url/agenda_url/agenda_pdf_url/unified_calendar_url at top level
```

**Target:**
```
GET /commissioners              -> list, profile only
GET /commissioners/{slug}       -> profile only (name, portfolio, country, bio_url)
GET /commissioners/{slug}/agenda -> events only (data array + envelope), no profile mixed in
```

Add `?include=profile` flag if a future client really needs both in one call (rare).

---

### CC-5. Calendar events: per-event source URL (Jordi #7)

**Today:** `committee_week` events row has `source_url: https://www.europarl.europa.eu/committees/en/documents/latest-documents` — same for every committee_week. Plenary `source_url` similarly generic.

**Target:**
- For specific committee meetings (rows where `event_type=committee_meeting`): point to the per-meeting page on `europarl.europa.eu/committees/en/{COMMITTEE}/meetings/{YYYYMMDD}` or to the EP day-of-meeting agenda PDF.
- For plenary sessions: point to `europarl.europa.eu/plenary/en/agendas.html?day={YYYYMMDD}`.
- For College meetings: point to the specific calendar item URL on `commission.europa.eu`.
- Keep `agenda_url` and `webstream_url` next to `source_url` for one-shot consumption.

Where the underlying scraper doesn't yet capture the per-event URL, mark the row `source_url_specific = false` and don't ship the generic URL.

---

### CC-6. Rate-limit tiers + Enterprise key (Jordi #4)

**Today.** All keys hit the same 60 req/min sliding window.

**Target.**
| Tier | Limit | Bucket key | Comment |
|---|---|---|---|
| Free / trial | 60 / min | `rate_limit:free:{user_id}` | unchanged |
| Professional | 300 / min | `rate_limit:pro:{user_id}` | new |
| **Enterprise** | **6000 / min** OR `unlimited` flag | `rate_limit:ent:{user_id}` | new — for partners (GovClipping et al.) |

**Implementation.**
- Column `users.api_tier` (`free|pro|enterprise`); resolved in `_deps.api_user_with_rate_limit`.
- Provision Jordi an Enterprise key today; bump his cap to 6000/min as a soft proxy for "infinite enough that he never hits it".
- Surface `X-RateLimit-Tier` on every response.
- Document at `/api/docs/rate-limits.html`.

---

## Endpoint-by-endpoint findings (all 36 folders)

Status legend: ✓ OK · ⚠ improve · ✗ broken · ◌ field exists but NULL on row sampled

### Legislation

| Folder | Status | Body content | URL field | Issue / recommendation |
|---|---|---|---|---|
| laws (list) | ⚠ | n/a (0 results) | — | empty data — query `q=GDPR&limit=1` returned 0; CELEX corpus likely indexed differently. Check TSVECTOR. |
| laws (detail) | ⚠ | ✗ no `summary`, no `text_plain` link | eurlex_url ✓ | add `summary` (one-paragraph) + `text_url: /laws/{celex}/text` link |
| laws/{celex}/text | ✓ | content (351 KB) ✓ | eurlex_url ✓ | rename `content` → `text` for clarity (current name shadows envelope) |
| procedures | ⚠ | ◌ probably no full description | source_url ✓ | confirm description field at Full |
| legal-text/recital-article-map | ✓ | n/a (analysis output) | — | works |
| legal-text/defined-terms | ✓ | n/a | — | works |
| delegated-acts | ⚠ | ◌ no `summary`/`body` | source_url ✓ | add `summary` |
| implementing-acts | ⚠ | ◌ same | source_url ✓ | add `summary` |
| tris-notifications | ⚠ | ◌ `full_text_summary` and `main_content` NULL | source_url ✓, pdf_url ◌ | backfill body from TRIS portal HTML |
| commission-register | ⚠ | ◌ no body | pdf_url ✓ | extract `pdf_text` from the PDF (60 % already on Cellar) |
| council-documents | ⚠ | ◌ `summary` NULL on sample | url ✓ | backfill `summary` from consilium pages |

### Institutions & people

| Folder | Status | Issue / recommendation |
|---|---|---|
| meta/dgs | ✗ 404 | route mapping broken — fix CC-3 |
| meta/committees | ✗ 404 | same |
| meta/policy-areas | ✗ 404 | same |
| commissioners (list) | ✓ | OK; profile-only as Jordi wants |
| commissioners/{slug} | ✗ 404 | endpoint missing — create profile-only detail (CC-4) |
| commissioners/{slug}/agenda | ⚠ | strip the profile fields out (CC-4); keep envelope tidy |
| officials | ⚠ | confirm body fields (bio? mandate?) at Full |
| meps | ⚠ | profile shape OK; consider `/meps/{id}/votes` and `/meps/{id}/amendments` aggregator endpoints |
| meetings | ✓ | Transparency-Register meetings, well-shaped |
| rsb-opinions | ⚠ | needs `summary` body field |

### EP detail

| Folder | Status | Issue / recommendation |
|---|---|---|
| committees/{code}/work-items | ⚠ | confirm `description` body at Full |
| committees/{code}/minutes | ⚠ | confirm `summary`/`text` body at Full + add `pdf_url` |
| ep-documents | ⚠ | unified branching ok; needs body field passthrough |
| amendments | ✓ | `original_text`, `proposed_text`, `justification` all surfaced. Best example of what every endpoint should look like. |
| votes | ✓ | well-shaped; 3 count fields + result + procedure ref |
| texts-adopted | ⚠ | needs `body_text` or `pdf_url` |
| texts-submitted | ⚠ | empty data on sample; check filter; needs body |
| resolutions | ⚠ | needs body |
| reports | ⚠ | sample has `document_url` (PDF) — extract `body_text` once |
| opinions | ⚠ | needs body |
| parliamentary-questions | ◌ | schema has `text_question`/`text_answer` but rows NULL — backfill from doceo HTML |
| webstreams | ⚠ | `video_url` NULL but `multimedia_url` set — clarify the two; ensure both populated when applicable |

### Live data

| Folder | Status | Issue / recommendation |
|---|---|---|
| publications | ⚠ | `summary` present but truncated to 256 chars; expose `body_html` at Full |
| press-releases | ⚠ | `summary` ships raw HTML — strip tags or expose both `summary_html` + `summary_text` |
| calendar | ✗ | `source_url` is the generic `/committees/en/documents/latest-documents` page, not per-event (CC-5) |
| consultations | ✓ | well-shaped — best example after `amendments` |
| research-publications | ⚠ | `abstract` sometimes, no `pdf_text`; backfill |
| tenders | ⚠ | `summary` NULL on sample; check ingest |
| predictions | ✗ 502 | upstream error |
| knowledge-guides | ⚠ | `content_preview` only at Full — should ship full `content` |
| citations/verify | ✗ 404 | endpoint not deployed |

---

## Recommended iteration order

Goal: Jordi can re-pull every endpoint and find the data he needs without each call requiring a follow-up. Focus on high-leverage cross-cutting fixes first, then unblock the 4 broken endpoints, then per-folder body backfills.

1. **CC-1 + CC-3** (drop `meta` block, fix the 4 broken routes) — same PR, ~1 hour.
2. **CC-4** (commissioners profile vs. agenda) — same PR, ~30 min.
3. **CC-5** (calendar per-event URLs) — needs scraper enrichment + DB column for the specific URL → 2-3 hours.
4. **CC-6** (rate-limit tiers + Enterprise key for Jordi) — ~1 hour, plus key provisioning.
5. **CC-2(a)** schema fixes — surface columns that already exist but aren't in the Full Pydantic schema (parl-q, tris, knowledge-guides body, laws-detail summary). ~2 hours.
6. **CC-2(b)** backfill — multi-day, parallelisable: PDF text extraction for reports/opinions/resolutions/commission-register; HTML body scrape for parl-q/tris/tenders. Run in background while other items go through verification.
7. **Per-folder verification loop** — after each PR lands, re-run `audit_jordi_feedback.py`; share Jordi the deltas; iterate until every column is green.
