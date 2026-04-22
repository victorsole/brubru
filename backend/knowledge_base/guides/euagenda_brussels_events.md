# euagenda.eu -- Brussels Events Aggregator (Third-Party Events)

## QUICK FACTS
- Topic: Third-party EU events (think tanks, conferences, webinars, training, associations) aggregated from https://euagenda.eu/
- Brubru source tag: `source='euagenda'` in `eu_calendar_events`
- Brubru institution tag: `institution='THIRD_PARTY'` (added 22 April 2026)
- Event types covered: conference, webinar, roundtable, training, workshop (in addition to existing `agency_event`)
- Scraper: `backend/services/scrapers/euagenda_scraper.py`
- Sync CLI: `python3.12 backend/scripts/sync_euagenda.py --max N [--no-details]`
- Sync service: `services.scrapers.eu_calendar_sync_service.EUCalendarSyncService.sync_euagenda()`
- Cadence: daily via `/news` Step 1
- API surface: same `/api/eu-calendar/events` endpoint (filter by `source=euagenda` or `institution=THIRD_PARTY`) -- Yellow+ tier gate
- MCP tool: `mcp__brubru__get_calendar_events` surfaces these automatically (shared data layer)
- Frontend: same My EU Calendar tab in My EU Bubble with a THIRD_PARTY filter chip

## What euagenda.eu Is

EU Agenda (operated by EU Agenda Network SL, Spain) is the Brussels policy community's go-to aggregator for events, publications, news, and videos from **thousands of authoritative channels**: EU-funded projects, public affairs consultancies, European associations, conference organisers, training centres, public bodies. It is distinct from the EU's own institutional calendars (EP, Council, Commission) which Brubru already covers via the 6 primary calendar sources.

For Brubru users, euagenda fills the "**what's happening in Brussels this week on [topic]**" gap: the 3pm Bruegel roundtable, the CEPS energy debate, the ERA training course in Trier, the EPC Brexit retrospective. These never appear in Commission or Parliament calendars.

## Scope in Brubru

**In scope (scraped):**
- Public event listing pages (`/events`, `/events/{sector}`)
- Public event detail pages (`/events/YYYY/MM/DD/slug`)
- Fields: title, subtitle, start/end datetime, venue (physical or "Online Webinar"), organiser, description, source URL, image

**Out of scope (by explicit decision, 22 April 2026):**
- euagenda's **news** and **publications** sections (Brubru already has 44 news portals + EPRS + STOA + JRC + ART)
- Speakers / sponsors / indicators directories
- Behind-login / publisher-only content
- A dedicated Brubru tab for these events (they merge into My EU Calendar with a filter chip)

## How Events Are Classified

- `institution = THIRD_PARTY` -- distinguishes from EP/COUNCIL/COMMISSION/ECB/etc.
- `event_type` -- inferred from title/subtitle keywords:
  - "webinar" or "online course/seminar/session" -> `webinar`
  - "conference/congress/summit/symposium" -> `conference`
  - "roundtable/round table" -> `roundtable`
  - "training/course/academy/bootcamp" -> `training`
  - "workshop/seminar" -> `workshop`
  - otherwise -> `agency_event` (safe default)

## Data Flow

```
euagenda.eu/events
   -> EuAgendaScraper.scrape_listing()  [card extraction]
   -> EuAgendaScraper.scrape_detail()   [per-event HTML -> When/Where/Organised by]
   -> EUCalendarSyncService.sync_euagenda()
   -> _upsert_event() with institution=THIRD_PARTY, source='euagenda'
   -> eu_calendar_events table
   -> /api/eu-calendar/events + mcp__brubru__get_calendar_events
   -> My EU Calendar tab (Yellow+ tier)
```

## Rate Limits

- Polite: 2 seconds between requests, via `BaseScraper._coordinator`
- Typical run: 150 events x detail fetch = ~7 minutes
- Fast path (--no-details): listing only, ~30 seconds, but missing venue/organiser/description precision

## First Live Sync

- Date: 22 April 2026
- Events synced: 10 (smoke test batch)
- Coverage examples: FOE 2026 Education Conference (Florence), ERA Summer Courses on Antitrust / IP / State Aid (Trier, Online), EU Savings and Investments Union webinar

## Related Guides

- `memory/eu_calendar.md` -- full EU Calendar feature reference (6 primary sources + this one = 7)
- `memory/integrations.md` -- data source inventory
- No guide overlap with news / publications -- those stay in existing scrapers

## Sources

- https://euagenda.eu/ -- landing
- https://euagenda.eu/events -- events listing
- https://euagenda.eu/policy/{sector} -- sector-filtered events (energy, environment, digital, health, economy, security, justice, agriculture, transport, culture)
- https://euagenda.eu/dossiers/{country} -- country-filtered
- Operator: EU Agenda Network SL (Spain), Terms of Use: https://euagenda.eu/about/terms
