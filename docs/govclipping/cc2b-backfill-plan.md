# CC-2(b) — Body-content backfill plan

Prep doc for the multi-day backfill that populates the body fields Jordi explicitly asked for ("show what we have in our DB"). Categorises every endpoint by what's needed: schema-only, NULL-row backfill, or extraction-from-source.

Audit baseline: `/tmp/jordi_audit/thorough.json` (90 sample calls, 1 May 2026).

---

## Three categories

| Category | Action | Scope | Risk |
|---|---|---|---|
| **A. Schema-only** | Add field to Pydantic Full schema, populate from existing column. | 7 folders | low — code-only, no migration |
| **B. NULL-row backfill** | Schema is fine; rows just have NULL in the body column. Need a script that fills them. | 8 folders | medium — DB writes, source-fetch costs |
| **C. Extraction-from-source** | Body lives in a PDF or HTML page; extract text and store in a new column. | 4 folders | high — PDF/HTML extraction, big rows, may need new schema |

---

## Category A — schema-only fixes

These rows already have the body column populated in the DB; we just need to expose the field at the Full detail level. One PR each, ~20 minutes per folder.

| Folder | DB column to expose | Pydantic model |
|---|---|---|
| `delegated-acts` | `summary` | `SecondaryActItem` (w4_endpoints.py) |
| `implementing-acts` | `summary` | `SecondaryActItem` (w4_endpoints.py) |
| `commission-register` | `summary` | `CommissionRegisterDocItem` |
| `texts-adopted` | `body_text` | `TextsAdoptedItem` |
| `texts-submitted` | `body_text` | `TextsSubmittedItem` |
| `reports` | `summary` | `ReportItem` |
| `consultations` | `summary` | `ConsultationItem` |

**Verification:** for each folder, after deploy, re-run `audit_thorough.py` and confirm the body field appears in `body_audit.present_value`.

---

## Category B — NULL-row backfill (column exists, fields NULL)

The Pydantic schema already exposes these fields; the rows in the DB are NULL. Need a script that fetches the source and fills them. **Crucially: in many cases the source is a PDF**, so the same script doubles as Category C extraction.

| Folder | NULL fields | Source URL field | Source format |
|---|---|---|---|
| `tris-notifications` | `full_text_summary`, `main_content` | `source_url` (TRIS portal) | HTML |
| `parliamentary-questions` | `text_question`, `text_answer` | `source_url` + `answer_url` (doceo) | HTML |
| `tenders` | `summary` | `ted_url` | TED HTML or API |
| `council-documents` | `summary` | `url` (consilium) | HTML (anti-bot) |
| `resolutions` | `summary` | (none — needs scraping) | doceo PDF |
| `amendments` | `justification` (NULL on some rows) | `source_url` (doceo DOCX) | DOCX |
| `knowledge-guides` | `summary` (NULL — guides have content but no summary) | (curated) | hand-write or AI-summarise |
| `laws-list` (search shows celex empty when title-only match) | `text_url` derives from celex | n/a | needs CELEX populated on TSVECTOR matches |

---

## Category C — extraction-from-source (column NEEDS to be added)

Body lives in a PDF the row already points at. Need: (a) DB column, (b) extraction script, (c) Pydantic field, (d) rate-limited fetch + cache.

| Folder | Source PDF field | Proposed new column | Rough row count |
|---|---|---|---|
| `commission-register` | `pdf_url` | `pdf_text` (TEXT) | 528 |
| `reports` | `document_url` | `body_text` (TEXT) | 1,026 |
| `opinions` | (no URL today) | needs `document_url` then `body_text` | ~? |
| `research-publications` | `pdf_url` | `pdf_text` (TEXT) | 210 |
| `texts-adopted` | `pdf_url` | `body_text` (TEXT) | ~ |
| `publications` / `press-releases` | `url` (HTML) | `body_html`, `body_plain` | ~thousands |

**Extraction stack already in repo:**
- `pypdf` (4.0.1), `pdfplumber` (0.11.0), `pdfminer.six`, `pypdfium2` — all in `backend/requirements-light.txt`.
- `services/parsers/recital_article_store.py` — example of stored-text + cache pattern.
- `services/api_clients/eurlex_text_client.py` — Cellar fetch fallback for laws.

**Pattern to follow** (used for laws/{celex}/text):
```python
# 1. New column, e.g. commission_documents.pdf_text TEXT NULL
# 2. Backfill script: scripts/backfill_commission_pdf_text.py
#    - SELECT id, pdf_url FROM commission_documents WHERE pdf_text IS NULL
#    - For each row: download PDF (with 1.5 s gap), extract text via pdfplumber,
#      truncate at 200,000 chars, write back to DB.
#    - Resumable: skip already-populated rows.
# 3. Pydantic Full schema: add pdf_text: Optional[str] = None
# 4. Re-audit: confirm body_audit.present_value includes the new field.
```

---

## Run order

Pick the highest leverage first. Recommendation:

1. **Category A (one PR, all 7 folders)** — 1-2 hours. Immediately moves 7 folders from "no body at Full" to "summary visible at Full". No DB writes.
2. **Category B HTML scrape (parl-questions, tris, tenders, council-documents)** — script per source, throttled, resumable. Each one ~2-4 hours including verification.
3. **Category C PDF extraction (commission-register first, then reports/research)** — biggest impact for Jordi. Probably 1-2 days end-to-end including 528 + 1,026 + 210 PDFs.
4. **Category C HTML body** (publications, press-releases) — lowest priority since we already ship `summary` (truncated) and the URL.

Each phase:
1. Migration adds column.
2. Backfill script runs in batches with resume support.
3. Pydantic Full schema exposes the field.
4. Re-run `audit_thorough.py` and confirm `present_value` grows.

---

## Cost estimate

- **PDF downloads:** EUR-Lex Cellar 60 req/min ceiling. 528 commission docs ÷ 60 = ~9 minutes. 1,026 reports = 17 minutes. 210 research = 3.5 minutes. Total ~30 min of downloads, but each PDF text-extraction adds 0.5-2s on local CPU. Realistic budget: 4-6 hours wall-clock for the Cat C pass.
- **HTML scrapes (Cat B):** TRIS / doceo / TED have varying rate limits and anti-bot quirks. Throttle at 1.5s/req. parl-questions ~5,000 rows = 2 hours.
- **DB storage:** 1,500-2,000 rows × ~50 KB extracted text = ~100 MB total. Negligible.

---

## Out of scope

- Full HTML body for publications/press-releases (high volume, low marginal value — `summary` already there, `url` already shipped).
- Rich layout / footnote preservation in PDF extraction. Plain text is enough for keyword matching.
- Translation. Body stays in source language.

---

## Open questions for the user

1. Should `pdf_text` be returned inline at Full level, or behind a separate `/pdf-text` sub-endpoint (like `/laws/{celex}/text`)? Inline is simpler for Jordi but bloats list responses.
2. Do we OCR scanned PDFs (some old ones) or skip them? `pdfplumber` extracts only embedded text; OCR adds days of compute.
3. Is the storage ceiling 200 KB / row reasonable, or should we keep full text uncapped?
