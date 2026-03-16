# EP Plenary Debate Transcripts (CRE) -- Implementation Spec

## Origin

Maria Alemany (Council staff) tested Brubru by uploading debate notes from an EP plenary debate on "cutting red tape" and asking for a structured summary. Brubru responded with a "critical limitation" message saying it couldn't access EP transcript data. The improved document upload UX (item 5) partially addresses this, but the real fix is auto-fetching CRE transcripts so users don't need to copy-paste debate content.

## User Story

> As a Council staffer, I need Brubru to summarise EP plenary debates by political group and MEP, following a specific format, so I can brief Council delegations without manually transcribing hours of debate.

**Trigger:** User asks "Summarise the March 10 plenary debate on cutting red tape" or "What did MEPs say about the Omnibus proposal in plenary?"

**Expected output:** Structured summary with:
- Debate title + procedure reference
- Commission position (if Commissioner spoke)
- Council position (if Council representative spoke)
- By political group: key speakers, positions taken, quotes
- Links to CRE source + video

## Data Source

### CRE XML Files

**URL pattern:**
```
https://www.europarl.europa.eu/doceo/document/CRE-{TERM}-{YYYY-MM-DD}_{LANG}.xml
```

- `TERM`: Parliamentary term (10 for 2024-2029)
- `YYYY-MM-DD`: Plenary session date
- `LANG`: Two-letter language code (EN, ES, FR, etc.)

**Example:**
```
https://www.europarl.europa.eu/doceo/document/CRE-10-2025-03-10_EN.xml
```

- Publicly available, no authentication required
- All 24 EU languages
- English file size: ~350-500 KB per session day
- Publication delay: 3-5 days (provisional may be available within 24h -- needs verification)

### XML Structure

```xml
<DEBATS>
  <CHAPTER>
    <TL-CHAP VL="EN">Debate title</TL-CHAP>
    <NUMERO>2024/0035(COD)</NUMERO>           <!-- procedure reference -->
    <INTERVENTION>
      <ORATEUR MEPID="118859" PP="EPP" LANG="EN">
        <NOM>Speaker Name</NOM>
      </ORATEUR>
      <PARA>Spoken text paragraph...</PARA>
      <PARA>Another paragraph...</PARA>
    </INTERVENTION>
    <!-- More interventions -->
  </CHAPTER>
  <!-- More chapters/debates -->
</DEBATS>
```

**Key fields per intervention:**
- `MEPID`: MEP identifier (matches EP Open Data API)
- `PP`: Political group code (EPP, S&D, Renew, Greens/EFA, ECR, The Left, PfE, NI, ESN)
- `LANG`: Language spoken
- `VOD-START`/`VOD-END`: Video timestamps (ISO 8601)

## Architecture

### Phase 1: CRE Client + On-Demand Fetch (Minimal)

No database storage. Fetch CRE XML on demand when the context builder detects a plenary debate query.

| File | Action | Description |
|------|--------|-------------|
| `services/api_clients/cre_client.py` | CREATE | Fetch + parse CRE XML. Methods: `fetch_debate(date, lang)`, `search_debate_by_topic(date, topic)`, `get_speakers_by_group(debate)` |
| `services/ai/context_builder.py` | EDIT | Add `_search_plenary_debates()`. Detect debate intent via keywords. Inject transcript excerpt into AI context. |
| `services/ai_service.py` | EDIT | Add system prompt section on how to structure debate summaries |

**Intent detection keywords:** "plenary debate", "debate in parliament", "MEPs discussed", "what did MEPs say", "EP debate on", "plenary session", "parliament discussed"

**Context injection format:**
```
EP PLENARY DEBATE TRANSCRIPT (official CRE record)
Date: 2026-03-10
Topic: Cutting red tape -- Omnibus simplification package
Procedure: 2025/0380(COD)

COMMISSION (Commissioner Dombrovskis):
[Summary of Commission statement, max 500 chars]

COUNCIL (Minister X, Presidency):
[Summary of Council statement, max 500 chars]

EPP (3 speakers):
- Weber (DE): [key point, max 200 chars]
- Gonzalez (ES): [key point]
- ...

S&D (2 speakers):
- Garcia (ES): [key point]
- ...

[Other groups...]

Source: https://www.europarl.europa.eu/doceo/document/CRE-10-2026-03-10_EN.xml
```

### Phase 2: Database Storage + Sync (Medium)

Store debate metadata for faster retrieval and cross-referencing with legislative files.

| File | Action | Description |
|------|--------|-------------|
| `models/ep_plenary_debate.py` | CREATE | `EPPlenaryDebate` model: id, cre_reference, debate_date, title, chapter_number, procedure_refs (ARRAY), speakers (JSONB), political_groups (ARRAY), transcript_summary (Text), source_url |
| `migrations/033_add_ep_plenary_debates.sql` | CREATE | Table + indexes on debate_date, procedure_refs (GIN) |
| `services/scrapers/ep_plenary_debate_sync_service.py` | CREATE | Sync CRE data to database. Supports `--days N` and `--date-from/to` |
| `scripts/sync_plenary_debates.py` | CREATE | CLI: `python scripts/sync_plenary_debates.py --days 7` |
| `api/plenary_debates.py` | CREATE | `GET /api/plenary-debates`, `POST /api/plenary-debates/sync` (Blue tier) |

### Phase 3: Deep Integration (Advanced)

| Feature | Description |
|---------|-------------|
| Full-text search | PostgreSQL GIN index on transcript text |
| MEP contribution tracking | Word count, speech count per MEP per debate |
| Group position inference | AI classifies each group's stance (for/against/nuanced) |
| Debate-to-amendment linking | Match amendments to debate topics |
| Automatic CRE fetch in /morning | Add to daily routine: fetch yesterday's CRE if plenary week |

## Existing Infrastructure to Leverage

| Component | Location | How to Use |
|-----------|----------|------------|
| EP Open Data Client | `services/api_clients/ep_open_data_client.py` | Template for CRE client (rate limiting, async httpx) |
| Texts Adopted Scraper | `services/scrapers/texts_adopted_scraper.py` | Template for XML parsing + BaseScraper pattern |
| EU Calendar Events | `models/eu_calendar.py` | Plenary session dates already in DB |
| EP Political Groups | `hooks/use_predictions.ts` | EPP (188), S&D (136), PfE (84), ECR (78), Renew (77), etc. |
| MEP Directory | `EuropeanParliamentClient.get_mep_list()` | MEPID -> name/country/group mapping |
| EP Voting Results | `models/ep_voting.py` | Vote data for same debate day |
| Plenary Week Knowledge | `knowledge_base/guides/ep_plenary_march_2026.md` | Agenda items for cross-referencing |

## Data Volume

| Metric | Value |
|--------|-------|
| Plenary sessions per year | ~50 |
| Debates per session day | 5-50 |
| Speakers per debate | 5-100+ |
| EN XML size per day | 350-500 KB |
| Total annual storage (metadata only) | ~50 MB |
| Total annual storage (with transcripts) | ~1 GB |

## Performance Considerations

- XML parsing: <1s per session day (ElementTree)
- On-demand fetch (Phase 1): 1-3s network latency per CRE file
- Database sync (Phase 2): ~5s per 100 debates
- Context window: Large debates (50+ speakers) must be summarised before injection. Max 3-4 key speakers per group, truncate to 4,000 chars total.

## Publication Delay Workaround

CRE transcripts have a 3-5 day delay. For same-day or next-day summaries:

1. **Document upload** (already implemented): User uploads their own debate notes
2. **EP multimedia centre**: Video available same day, but no text transcript
3. **Provisional CRE**: May be available within 24h -- needs testing
4. **Hybrid approach**: If CRE not yet available for requested date, tell user and suggest uploading their notes

## Access Control

| Tier | Access |
|------|--------|
| No subscription | Upgrade CTA |
| Starter/Advocate (yellow) | On-demand CRE fetch for debates linked to tracked files |
| Professional (blue) | Full CRE access + sync + search across all debates |

## Open Questions

1. **Provisional CRE availability**: Need to test if provisional transcripts exist at a different URL pattern before the official version
2. **Non-plenary debates**: Committee meetings also have transcripts (different URL pattern) -- scope for later
3. **Multilingual handling**: Should we fetch EN by default and offer other languages on request?
4. **Storage vs on-demand**: Phase 1 is on-demand only. Phase 2 stores metadata. Full transcript storage (Phase 3) adds ~1 GB/year -- worth it?
5. **Integration with /morning**: Should CRE sync run automatically during plenary weeks?

## Implementation Order

**Recommended: Phase 1 first** (2-3 hours of work). This gives Maria immediate value with zero database changes. Phase 2 only needed if multiple users query historical debates frequently.

### Phase 1 Checklist -- COMPLETED (16 March 2026)

- [x] `services/api_clients/cre_client.py` -- fetch + parse CRE XML (CREClient, Speaker, Debate, PlenarySession dataclasses)
- [x] `services/ai/context_builder.py` -- `_detect_plenary_debate_intent()` (22 multilingual intent phrases + date extraction) + `_fetch_plenary_debate()` (on-demand CRE fetch + topic matching) + `plenary_debate_transcript` field on ContextData + debate phrases added to INFO_INTENT_PHRASES
- [x] `services/ai_service.py` -- CRITICAL system prompt section for EP plenary debate summary structure
- [x] Test with real CRE file: March 10, 2026 plenary (34 debates, 510 speakers). Housing (97), Energy (86), Defence (54), Single Market (40), Red Tape (35) all found correctly.
- [x] Publication delay: CRE available within 3-5 days. March 10-12 all returned 200 as of March 16.

**Implementation notes:**
- XML structure differs from spec: speaker name in `LIB` attribute (pipe-separated), not `NOM` element. Role in `SPEAKER_TYPE` attribute.
- Chapter NUMBER can be fractional (e.g. "12.1") -- handled with `int(float(...))`.
- "Summarise the debate" was triggering false drafting intent -- fixed by adding debate phrases to INFO_INTENT_PHRASES.
- Topic extraction uses word-boundary splitting (not substring replace) to avoid mangling words like "housing" -> "housg".
- Context injection: max 4,000 chars per debate, 3 speakers per group, 200 chars per speaker excerpt.
