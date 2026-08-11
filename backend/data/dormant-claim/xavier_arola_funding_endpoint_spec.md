# API v2 ad-hoc endpoint spec: entrepreneur financial instruments (for Xavier Arola / KinEtix Impact)

Hand-off to the "API" session. Do NOT build here; this session owns only the spec.
Requested 6 Aug 2026: an endpoint serving "instruments financers per suport a
emprenedors a traves de plataformes o stakeholders de sistema" (EU financial
instruments that support entrepreneurs, delivered through intermediaries/platforms).

## Proposed endpoint
`GET /api/v2/funding/entrepreneur-instruments`

Belongs in the funding folder alongside the surface that already powers the
Tenderator. It READS existing tables, so no new scraper/cron is needed (point
that is easy to over-build in the 8-point registration).

## Data source
`v_funding_unified` (unified funding view) OR `ft_calls_for_proposals` (canonical
English titles + `topic_id`, `framework_programme`, `status`, `deadline`,
`indicative_budget`, `keywords`, `target_audience`).

Scope to the intermediated-entrepreneur-finance programme set, matched by
`topic_id` prefix (reliable) rather than free-text title:
- `HORIZON-EIC%`  -> EIC (Pathfinder / Transition / Accelerator / STEP) - blended finance via the EIC Fund
- `SMP-%`         -> Single Market Programme SME strand - via EISMEA + Enterprise Europe Network
- `I3-%`          -> Interregional Innovation Investments - via regional innovation ecosystems
- `DIGITAL-%`     -> European Digital Innovation Hubs (EDIH platforms)
- `ESF-%` / `SOCPL%` -> ESF+ / EaSI - microfinance + social entrepreneurship via intermediaries
- `ERASMUS%` (EYE topics) -> Erasmus for Young Entrepreneurs

Add a derived `intermediary` label per family (EIF, EISMEA, EIC Fund, national
managing authority, EDIH) so the payload answers "who delivers it", which is the
whole point of Xavier's question.

## Query params
- `status` (default `open,forthcoming`), `programme`, `deadline_before`,
  `q` (free text over title/summary), `limit` (default 20, cap 50), `page`.

## Payload (v2 contract: items under `data`, plus total/has_more/next_page)
```
{ "data": [ {
    "topic_id": "HORIZON-EIC-2026-ACCELERATOR-01",
    "programme": "HORIZON (EIC)",
    "instrument_family": "EIC Accelerator",
    "intermediary": "EIC Fund (direct equity) + EISMEA",
    "title": "EIC Accelerator 2026",
    "status": "open",
    "deadline": "2026-12-16",
    "budget": null,
    "source_url": "https://ec.europa.eu/.../topic-details/HORIZON-EIC-2026-ACCELERATOR-01"
  } ],
  "total": N, "has_more": true, "next_page": 2 }
```

## Verified live rows to smoke-test against (snapshot 6 Aug 2026)
- `HORIZON-EIC-2026-TRANSITIONOPEN` - open, deadline 2026-09-15
- `HORIZON-EIC-2026-STEP` - open, deadline 2026-11-24
- `HORIZON-EIC-2026-ACCELERATOR-01` - open, deadline 2026-12-16
- `DIGITAL-2026-BESTUSE-10-NETWORKSICs` - open, deadline 2026-09-30

## Registration checklist (8-point, API session)
Folder router + register in the v2 app; plain-English `summary=`; 5-section
Markdown `description=` (What it does / When to use it / Input / Try it / You get
back); add to the ONE v2 Postman collection via `/postman`; update the /api and
/api/docs pages AND the sidebar nav (reachable); no new cron (reads existing
tables); smoke-test the four topic IDs above return non-empty.

## Note
The Tenderator already covers Xavier's day-to-day need (profile-matched open
calls). This endpoint is the machine-readable/API version of the same, so KinEtix
can pull the intermediated-instrument list into its own systems.
