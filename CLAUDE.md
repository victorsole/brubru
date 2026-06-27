# CLAUDE.md - AI Assistant Context for Brubru

This file provides context for AI assistants working on this codebase.

---

## AI Workflow Principles (Cherny Paradigm)

### Mindset

You are part of a **workforce**, not just an assistant. The human orchestrates multiple AI instances in parallel—think fleet commander, not typist.

### Institutional Memory Protocol

- Every mistake you make should be documented here as a rule
- Read this file completely—it contains lessons from past errors
- The longer this codebase evolves, the smarter you become
- **Document corrections**: If you do something wrong, expect a rule to be added

### Verification First

Always verify your own work:
- Run tests after code changes (`pytest` for backend, `npm test` for frontend)
- Check that builds succeed before considering work complete
- For UI changes, describe what should be tested manually
- **The AI doesn't just write code—it proves the code works**

### Checkpoint Commits During Long Sessions

During multi-step work sessions (morning routine, feature builds, knowledge base overhauls), commit checkpoints after each logical phase:

- After knowledge guide updates: `chore: checkpoint -- N guides updated`
- After system prompt changes: `chore: checkpoint -- system prompt rules added`
- After context builder fixes: `chore: checkpoint -- context builder improvements`

This enables "try and rollback" methodology: if a later step breaks something, revert to the last checkpoint. Start from a clean git state, commit frequently, accept or roll back.

### Quality Over Speed

Use thorough reasoning. The "compute tax" upfront eliminates the "correction tax" later. Fewer corrections = faster overall.

---

## Project Overview

Brubru is an AI-powered strategic advocacy assistant for EU policy professionals. It combines conversational AI with legislative tools to help users analyse policies, draft amendments, and navigate EU institutional processes.

## Tech Stack

**Frontend:** React 18 + TypeScript + Vite 7.x
**Backend:** FastAPI (Python 3.11+) + SQLAlchemy 2.0
**Database:** PostgreSQL 15+ (Supabase → migrating to Google Cloud SQL)
**AI (Chat):** Free open-model chain since 11 June 2026 (€0 at current volume). `multi_provider_service.py` order = **Cerebras gpt-oss-120b (primary) → Gemini → NVIDIA Llama-3.3-70B → Mistral → Groq → Anthropic (opportunistic) → OpenAI**. Full-context readers (Cerebras/Gemini/NVIDIA) come first; Mistral reads only ~30% of the injected KB context so it is a degraded last-resort, and Groq's 12K TPM can't fit the prompt (see `memory/feedback_mistral_ignores_context.md`). Both the generator (`ai_service.chat()`/`chat_stream()`) and the anti-hallucination validator (`response_validator.py`) run on this chain; `prefer_claude` is now a no-op (`sonnet_primary_provider` left None). Anthropic is reached only when every free tier is exhausted and fails fast when unfunded — Chat is Anthropic-independent end to end. See `memory/project_chat_oss_migration.md` and `memory/feedback_chat_must_use_anthropic.md` (SUPERSEDED). The broader "no new Anthropic code" hard rule still governs all NON-chat code.
**Hosting:** SiteGround (frontend), Railway.app (backend)

## Key Commands

```bash
# Frontend development
cd frontend && npm run dev

# Backend development
cd backend && python -m uvicorn main:app --reload

# Build frontend
cd frontend && npm run build

# Run backend tests
cd backend && pytest

# Database migrations
cd backend && alembic upgrade head

# Seed test users (13 users with Professional/Starter tiers)
python3.12 -m backend.scripts.seed_test_users
```

## File Naming Convention

**All files use `snake_case`** — with one documented exception.

**Exception:** `frontend/src/App.tsx` and `frontend/src/App.css` retain Vite's default PascalCase because they are the framework-conventional root component and stylesheet referenced directly by Vite's build pipeline. Do not rename without auditing every Vite/Vitest config and package-lock reference.

- `chat_interface.tsx` (correct)
- `ChatInterface.tsx` (incorrect)
- `ai_service.py` (correct)
- `AiService.py` (incorrect)

React components are exported in PascalCase despite snake_case filenames.

## Project Structure

```
brubru/
├── frontend/src/
│   ├── pages/          # Route pages (main_page.tsx, etc.)
│   ├── components/     # UI components by feature
│   ├── services/       # API clients
│   ├── hooks/          # Custom React hooks
│   └── i18n/           # Internationalization (6 languages: EN, FR, NL, ES, CA, IT)
│
├── backend/
│   ├── api/            # FastAPI routers
│   ├── models/         # SQLAlchemy ORM models
│   ├── schemas/        # Pydantic request/response models
│   ├── services/       # Business logic
│   │   ├── ai/         # AI-specific services
│   │   ├── scrapers/   # EU institutional data scrapers
│   │   └── compliance/ # EU law compliance checking
│   ├── core/           # Config, database, security
│   └── knowledge_base/ # Static EU institutional data
```

## Main Features

1. **Brubru Chat** - AI chat with EU policy context (`backend/api/chat.py`)
2. **Amendator** - Legislative amendment editor (Akoma Ntoso XML)
3. **My EU Bubble** - RSS feed aggregator from EU sources
4. **EU Law Comply** - Compliance gap analysis
5. **Document Generator** - AI-powered position papers, MEP briefings, talking points (`backend/api/generate.py`)
6. **My EU Calendar** - Multi-source institutional calendar (`backend/api/eu_calendar.py`)
7. **Admin Panel** - User/subscription management (restricted)

## Important Patterns

- **AI Context:** `backend/services/ai/context_builder.py` injects EU-specific context
- **Scrapers:** `backend/services/scrapers/` fetch data from 15+ EU sources
- **Auth:** Custom JWT with Google/LinkedIn OAuth (no Supabase SDK dependency)
- **Payments:** Stripe integration for modular subscriptions (9 products, 18 price IDs)
- **i18n:** 6 supported languages: English, French, Dutch, Spanish, Catalan, Italian (the languages Victor speaks). **Never claim 23 EU languages.** i18next locales: en, es, ca, fr, it, nl

## Environment Variables

Required in `.env`:
- `SUPABASE_URL`, `SUPABASE_KEY` - Database/auth
- `MISTRAL_API_KEY` - Primary AI
- `ANTHROPIC_API_KEY` - Fallback AI 1
- `OPENAI_API_KEY` - Fallback AI 2
- `GOOGLE_GEMINI_API_KEY` - Fallback AI 3 (optional)
- `STRIPE_SECRET_KEY` - Payments
- 18 Stripe Price IDs (see Pricing Model section below)

## Code Style

- British English for all user-facing text (analyse, colour, behaviour)
- Irvin font (The New Yorker) for typography
- WCAG 2.1 Level AA accessibility compliance
- Conventional Commits for git messages

## API Endpoints

Backend runs on `http://localhost:8000`:
- `POST /api/chat` - AI chat endpoint
- `GET /api/amendments` - Amendment CRUD
- `GET /api/rss-feeds` - RSS feed management
- `POST /api/generate/*` - AI document generation (position papers, MEP briefings, talking points)
- `GET /api/eu-calendar/events` - EU Calendar events with filters
- `POST /api/eu-calendar/sync` - Calendar sync from all sources (Professional/Admin)
- `GET /api/subscriptions/plans` - Full pricing breakdown (all plans, modules, bundles)
- `POST /api/stripe/create-checkout-session` - Create Stripe checkout (`{plan, billing_period}`)
- API docs at `/docs` (Swagger UI)

## Database

PostgreSQL via Supabase. Key tables:
- `users` - User profiles
- `chat_conversations` / `chat_messages` - Chat history
- `amendments` - Legislative amendments
- `eu_laws` - Cached EU legislation
- `rss_feeds` / `rss_entries` - RSS data
- `eu_calendar_events` - EU institutional calendar events
- `user_calendar_subscriptions` - Calendar reminders/subscriptions

## Canonical Numbers of the EU Legal Corpus

LEG_2025-11 (Nov 2025 Publications Office bulk export): **8,710 distinct laws / 28,513 OJ publications / 61,219 translatable XML files**. One law can span multiple files (REACH=7, AI Act=14). Always cite the triple. `28,505` is deprecated.

## Testing

```bash
# Backend
cd backend && pytest

# Frontend
cd frontend && npm test

# E2E
npx playwright test
```

## Test Users

13 pre-configured test users for development and training (see `docs/users.md`):

- **Professional plan / Blue tier (5):** Charlotte Berends, Marga Payola, Daniel Roldán, Aleix Sarri, Nick Ligthart
- **Starter/Advocate plan / Yellow tier (8):** Robin Loos, Joan González, Sergi Duarte, Meritxell Vicheto, Bo, Marc Desmond, Andrés López, Jaume Bernis

Password: `test123` (except Meritxell: `test23`)

Seed script: `backend/scripts/seed_test_users.py`

## Deployment

- **Frontend:** SiteGround (brubru.beresol.eu) - static build from `frontend/dist/`
- **Backend:** Railway.app (brubru-production.up.railway.app) - auto-deploys from main branch
- **Database:** Supabase PostgreSQL (migrating to Google Cloud SQL)
- **Docker:** `docker-compose up -d` for local development

---

## Predictions Feature (February 2026)

**Full reference:** See `memory/predictions.md`. AI-powered legislative outcome predictions in My EU Bubble. 6 API endpoints under `/api/predictions/`. Yellow tier: 10/month. Blue tier: unlimited + Council. Key files: `api/predictions.py`, `services/predictions/`, `predictions_tab.tsx`.

## EU Calendar Feature (February 2026)

**Full reference:** See `memory/eu_calendar.md`. 6 data sources, month/week/day views. Key files: `api/eu_calendar.py`, `services/scrapers/eu_calendar_sync_service.py`, `eu_calendar_tab.tsx`. CLI: `python scripts/sync_eu_calendar.py`. Yellow tier: full access. Blue tier: AI summary + sync.

## Pricing Model: Modular A La Carte + Bundles (February 2026)

**Full reference:** See `memory/pricing.md`. Internal gating still uses white/yellow/blue tiers.

**Quick reference:** Starter 39/mo, Advocate 59/mo, Professional 99/mo (only blue tier), EP 49/mo. 14-day free trial, no permanent free tier. 9 Stripe Products, 18 Price IDs.

**User-facing text rules:** Never reference White/Yellow/Blue tiers. Use plan names. CTA: "Start Free Trial", "Subscribe", "Get Professional".

---

## Learned Rules

**Full reference:** `memory/learned_rules.md` — full history of rules accumulated from past corrections. Read when working on a topic you have not touched recently.

**Always-on critical rules** (most common pitfalls — full detail in `memory/learned_rules.md`):

- **Audit every implementation (set 27 June 2026).** After shipping any code change, script, migration, scraper edit, prompt rewrite, deploy — run a self-audit pass for inconsistencies, bugs, false positives, edge cases the prompt didn't name. Document the lesson. Two steps: ship + audit; never combine. Full pattern: `memory/feedback_audit_implementation_after_every_change.md`.
- **Learn the EU, teach Brubru (set 27 June 2026).** The strategic posture every session: deepen Claude's own EU expertise (treaties, institutions, files, actors, jurisprudence, OJ, OEIL, doceo, EUR-Lex, Cellar, EuroVoc) and feed every learning back into Brubru via knowledge guides + triggers + API endpoints + MEUB surfaces. If Claude's EU knowledge plateaus, Brubru plateaus. Read primary sources, never paraphrase press as primary. Full pattern: `memory/feedback_learn_eu_teach_brubru.md`.
- **Brubru = 6 languages** (EN, FR, NL, ES, CA, IT). Never claim 23.
- **Founder name: Victor Solé** (with accent; HTML: `Sol&eacute;`).
- **No emojis in codebase.** Use MDI icons (frontend) or `[OK]`/`[INFO]`/`[ERROR]` prefixes (backend).
- **Document retrieval:** AI MUST present T9-/A9-/PE-/COM- references with clickable URLs from knowledge guides. Never say "search EUR-Lex yourself."
- **Daily brief send protocol:** `--verify-urls` → `--test` to hello@beresol.eu → wait for explicit OK → `--send`. Never `--send --extra` without test-first.
- **Responsive design (hard rule, every frontend change):** every page must work cleanly at smartphone 375px (iPhone SE), 393px (iPhone 14 Pro), tablet portrait 768px (iPad), tablet landscape 1024px (iPad Pro), laptop 1440px (14-inch MacBook), desktop 2560px (27-inch monitor). Mandatory CSS breakpoints: `>1024px` full-width grids, `@media (max-width: 1024px)` drop 4-col grids to 2 cols, `@media (max-width: 900px)` drop any remaining 3-col grids to 2 cols (cards get cramped at ~245px each between 768-1024 without this), `@media (max-width: 767px)` stack to 1 col + hero font ≤1.9rem + hide header CTA + shrink padding to 1.25rem. Post-build: drag-test the browser window from 375px to 2560px, verify zero horizontal scroll and zero cramped cards. Set 15 May 2026 after the EU Canon landing page shipped with a 768-1024 gap.
- **CTA-strip Pexels background on canon + deep-dive pages** (set 15 May 2026): Pexels image + brand gradient overlay, different from hero, photographer credit in footer. Full template: `memory/feedback_canon_cta_strip_pexels.md` (if missing, reconstruct from canon HTML pattern in `frontend/public/eucanon/*/index.html`).
- **5 headlines/day** in daily brief (default). Every headline has a `suggested_query` → pre-verified the chatbot can answer.
- **Canonical tree (updated 19 June 2026).** 6 products: **My EU Bubble** (25 sub-tabs in order: 1.1 Overview, 1.2 Policy Interests, 1.3 My Documents, 1.4 News, 1.5 My Tracked Files, 1.6 My OJ, 1.7 Amendments, 1.8 Comparator, 1.9 Legislative Train: state of play, 1.10 Votes, 1.11 My EU Calendar, 1.12 Transcripts, 1.13 Council Watch, 1.14 MEP Watch, 1.15 Plenary Order of Business, 1.16 Parliamentary Questions, 1.17 EU Public Consultations, 1.18 Lobby Meetings, 1.19 Position Analysis, 1.20 Predictions, 1.21 Brubru Databases, 1.22 Research & Evidence, 1.23 Stakeholder Mapping, 1.24 Strategy Docs, 1.25 Tender Docs), **Amendator**, **Chat**, **EU Law Comply**, **Tenderator**, **API**. Never invent non-canonical tabs.
- **Catalan output must be accented:** sóc, perquè, política, Brussel·les, regulació, Víctor Solé.
- **Supabase Data API grants are mandatory on new `public.*` tables (set 15 May 2026).** Order in every new-table migration: CREATE TABLE → ENABLE RLS → CREATE POLICY → GRANT (public-read: anon+authenticated SELECT, service_role ALL; user-owned: authenticated CRUD, service_role ALL). Default grant removed 30 Oct 2026 — replay (staging spin-up / restore / new env) breaks without explicit GRANT. Full template + audit + 5 backfilled migrations (041/042/064/065/069): `memory/feedback_supabase_data_api_grants.md`.
- **API endpoint documentation is mandatory.** Every new `/api/v1/*` route ships with a plain-English `summary=` (no CELEX/ECLI/EURIO/CORDIS/SPARQL jargon as primary names) and a 5-section Markdown `description=` (**What it does** / **When to use it** / **Input** / **Try it** / **You get back**). When the endpoint is added or its description changes, run `/postman` in the same session to mirror the rename + description into the published collection. Touching an undocumented endpoint = retrofit it in the same commit. Full template + anti-patterns: `memory/feedback_api_endpoint_documentation_required.md`.
- **Week-ahead (Friday brief):** verify every item against primary EU source (doceo, college-agenda, consilium) before sending. Never trust `eu_calendar_events` DB blindly.
- **Verify any Commission meeting date / College announcement against the EC Transparency Register tentative-agenda PDF before asserting it anywhere (brief, LinkedIn, guide, calendar) — set 26 May 2026.** Trade press + a stale `college_agenda.md` are not enough. Two register URLs + the Playwright→`api/files`→`pdftotext` recipe (highest `SEC(YYYY)NNNN` = live agenda): `memory/feedback_ec_tentative_agenda_primary_source.md`. If the agenda date says "(tbc)", hedge — never assert hard adoption.
- **.env in shell:** never `source .env`. Use `grep '^VAR=' .env | cut -d= -f2-`.
- **Frontend module mismatch:** `rm -rf node_modules package-lock.json && npm install --legacy-peer-deps`.
- **Knowledge guides:** QUICK FACTS block at top. Prompt injection cap 4,000 chars in `format_context_for_ai`. After bulk trigger changes, run orphan audit.
- **`legislation_acronyms.json` only holds REAL legislation acronyms (set 19 May 2026, after EEC + GATT linkify incident).** The linkifier in `ai_service.py::_linkify_legislation` wraps any acronym in this file with an EUR-Lex CELEX URL. Institutional / treaty / organisation acronyms must NEVER be added: ECB, EIOPA, ESMA, EBA, EEC (= European Economic Community, pre-Maastricht EU), GATT (= WTO framework), WTO, OECD, NATO, IMF, EFTA, UN, UNECE, IMO are all NOT legislation. They are organisation or treaty markers. If they're in the file, every answer mentioning them produces a hallucinated EUR-Lex URL (incident 18 May 2026: EEC and GATT both mapped to fake CELEX `32658R0087`, surfaced on 3 anon Combined-Transport queries + 1 blue-tier subscriber GATT XXVIII query). Audit on every `/audit-queries` run; remove with `Edit` + verify `json.load()` parses + verify acronym count decreased. UNECE → 32018D1875 + IMO → 32016D0807 are narrow but technically point to real Council Decisions on EU positions in those bodies — leave only if the linker target is a real EU legal act, never a treaty/organisation by itself.
- **/session-summary must overwrite memory/day_before.md every session** as its first persistent action. This file is the ONLY context-recovery input for the next morning's `/day-before`. Skipped on 18/20/21 April 2026 — cost the 22 April session a reconstruction from git log. Fix shipped: `.claude/skills/session-summary/SKILL.md` Step 6a is now mandatory-first; `.claude/skills/day-before/SKILL.md` runs a staleness check on the `# Previous Session:` heading. **Companion rule (set 28 May 2026):** Session MD (`docs/sessions/YYYY-MM-DD.md`) must be populated in real-time — write each step's output immediately after the step completes, before moving to the next step. Delayed or batch population forces the user to remind Claude mid-session (happened 3× on 28 May).
- **Seed / test fixtures in production-shared tables must be filterable at query time.** Incident (22 April 2026): a `committee_meeting_transcripts` row with `event_id=libe-seed-20260417`, status=COMPLETED, 340 words of synthetic dialogue (fake plenary vote 228/311/92, fake T10-0095/2026, fake rapporteur quotes) was feeding the chatbot, which faithfully cited the fabricated facts in every CSAM / ePrivacy query. Fix pattern: exclude seed rows via `event_id ILIKE '%seed%'`/`%test%'` + `title ILIKE '%seed test transcript%'`/`%synthetic%'` at every retrieval stage. See `context_builder.py::_fetch_committee_transcript_block`. Memory: `memory/feedback_seed_fixtures_contaminate_prod.md`. Better long-term pattern: add an `is_test` boolean column at table-creation time for any fixture-prone table.
- **/morning Phase 3 cadence — DAILY vs FRIDAY split (27 April 2026, API moved to DAILY 28 April).** DAILY: Chat (KB/triggers/system prompt) + Calendar + Archive sweep + passive My Files/Tracker (OEIL sync) + API hero URL. FRIDAY only: EU Law Comply matrix + Tenderator + Documents templates + Predictions/Position snapshot invalidation. ON USER REQUEST: Amendator example URL, EC Consultations. Codified in `.claude/skills/morning/SKILL.md` Phase 3 (3D + 3F); Mon-Thu carry-overs queue to `memory/friday_sweep_queue.md`.
- **Archive feature for items with lifespan (migration 041, 27 April 2026).** Migration 041 added `archived_at TIMESTAMPTZ + archived_reason TEXT` to all 6 user_*_tracks tables, plus new `user_calendar_event_archives` join table (RLS-enabled). API: `POST/restore /api/archive/{entity_type}/{track_id}`, `GET /api/archive/list`, `POST /api/archive/calendar/{event_id}`. Auto-archive script: `scripts/auto_archive_old_items.py` (dry-run + apply); rules: carriages 90d post-adoption, consultations 30d post-deadline, commission_docs 180d stale. **Run during /morning Phase 3D as part of daily Archive sweep.** Existing tracking list endpoints still need `WHERE archived_at IS NULL` filter — TODO follow-up for full UI integration.
- **/news Step 5b LinkedIn post is mandatory (set 27 April 2026).** Every /news run must end with a draft LinkedIn post saved to `docs/marketing/linkedin_YYYY_MM_DD_daily_update.md`. Goal: institutional drumbeat showing Brubru is updated daily across the whole product. Template + quality bar in `.claude/skills/news/SKILL.md` Step 5b. Victor publishes manually; Claude never posts to LinkedIn directly.
- **Negation paradox in guide WARNINGs + system prompt (27-28 April 2026).** Never name a forbidden identifier inside its own "do not cite X" warning — that RE-PRIMES the model to emit X. Applies to BOTH knowledge guides AND `_build_system_prompt()` in `services/ai_service.py`. Fix: scrub all named identifier values; describe the FORMAT only (e.g. "PE-numbers: PE + digits + sub-version") never the value. Also: named-MEP / fabricated-tally seed fixtures move to `tests/` with `is_test=True` markers — production grep-paths are themselves a re-priming surface. Memory: `feedback_negation_paradox_in_warnings.md`.
- **CLI wrapper parity (set 27 April 2026).** When a parameter is added to a service function (`services/*.py`), audit every CLI wrapper that calls it (`scripts/*.py`) and ensure it accepts and passes through the new parameter. Otherwise the feature ships dead. Incident: Friday's commit `235086d4` added `feature_map` to `_build_brief_email_html` + `send_daily_brief_batch` but never wired it to `scripts/send_daily_brief.py`; per-headline feature CTAs were absent from bulk sends for 3 days. Fix shipped 27 Apr: added `--feature INDEX:LABEL:URL` flag. Memory `feedback_cli_wrapper_parity.md`.
- **Bulk outreach must use SMTP-level BCC (set 27 April 2026).** Any send_batch_*.py script must use a SINGLE SMTP connection with multiple RCPT TO calls (one MIMEText, To=hello@beresol.eu visible, each recipient sees only that address). Per-recipient `EmailService.send()` opens a fresh SMTP connection each time and hits Gmail throttle around the 80-100 mark. Env-var name is **SMTP_PASSWORD** (not SMTP_PASS or EMAIL_PASSWORD). 0.5s delay between RCPT TOs. If SMTP_PASSWORD is unset, abort the send rather than fall back to per-recipient. Memory `feedback_send_batch_use_bcc.md`.
- **CELEX numbering ≠ OEIL procedure numbering (set 30 April 2026).** Never derive a CELEX from an OEIL ref — independent counters. Look up the COM document number first, then convert. When in doubt, read `legislative_carriages.celex_numbers` from the DB. Full chain + incident (Greek financial assistance mis-derived as Firearms Trafficking) + pre-flight verifier: `memory/feedback_celex_vs_oeil.md` + `memory/feedback_amendator_url_verification.md`.
- **addyosmani/agent-skills plugin** — engineering-discipline skills; on-demand only, not inside Brubru daily routines. Full guide: `memory/reference_addyosmani_agent_skills.md`.
- **Don't ship EUR-Lex URLs to user-facing surfaces without verifying each one parses (set 30 April 2026).** Same incident: 10 URLs went into the Amendator example list, only some loaded correctly. Mandate: every rotation script that adds a URL to a user-visible list must call `POST /api/documents/fetch-eurlex` first and confirm at least 5 recitals + 3 articles. Communications (DC), agreements, recommendations, staff working documents, and inter-service consultation refs (`intcom:Ares(...)`) are NOT amendable — exclude them via the `document_type IN AMENDABLE_TYPES` filter at query time. Amendable set: `regulation`, `directive`, `decision_legislative`, `proposal_cod`, `proposal_app`, `proposal_cns`. Codified in `api/amendator_examples.py` + `migrations/042_amendator_featured_examples.sql`.
- **Argparse `nargs="+"` is an anti-pattern for repeatable flags (29 April 2026, 3rd incident).** Any CLI flag intended to be REPEATED must use `action="append"`, never `nargs="+"`. With `nargs="+"`, repeated invocations silently overwrite earlier values. Three confirmed incidents in `scripts/send_daily_brief.py` (`--feature`, `--news`, `--week-ahead`). Mandate: (a) new repeatable flags default to `action="append"`; (b) when fixing one occurrence, audit ALL argparse decorators in the same file in the same commit. Memory: `feedback_cli_wrapper_parity.md`.
- **NEVER jump between /morning phases without explicit user OK (set 1 May 2026, after 2nd documented violation).** This was a memory-only rule (`feedback_morning_routine.md`, 19 March 2026 origin) but was ignored on 1 May 2026 — Claude went 1 → 1b → 2 → 3D → 3F → 4 with only one consent check after Phase 0. Promoted to always-on CLAUDE.md rule. Every phase transition in `/morning` (and any multi-phase orchestrator skill: `/news`, `/audit-queries`, `/daily-brief`, `/send-batch`, etc.) requires an explicit "ok" / "proceed" / "go" from the user before the next phase fires. ONE consent at the top is NOT a global pass — each phase is a separate gate. The cost of pausing is low; the cost of an unwanted side-effect (deploy / email / DB write) is high. If user pre-authorises multiple phases ("do all of them"), still announce each transition with a one-line "starting Phase X" before firing the next skill. Memory: `feedback_morning_routine.md`.
- **DG-specific subdomains beat the generic presscorner for Commission press releases (set 1 May 2026).** When fetching a Commission announcement (DG GROW, DG ENV, DG ENER, DG FISMA, DG MARE, DG SANTE, etc.), the canonical URL pattern is the **DG-specific subdomain** + `/news/<slug>_en` — for example `single-market-economy.ec.europa.eu/news/`, `environment.ec.europa.eu/news/`, `energy.ec.europa.eu/news/`, `finance.ec.europa.eu/news/`. The generic `ec.europa.eu/commission/presscorner/api/files/document/print/en/<ip_ref>/...` endpoint 404s frequently and is unreliable as a primary fetch target. Use the DG subdomain first; fall back to presscorner only if you have a confirmed working URL. Incident: 1 May 2026 fetched IP/26/948 (Terrible Ten) via the wrong endpoint → 404 → retry with single-market-economy.ec.europa.eu succeeded.
- **/morning Phase 3F template is aspirational, not literal (1 May 2026).** No global `compliance_matrix`, no `predictions_cache`, no EU-funding-calls schema in `tenders` (TED-only). Honest 3F scope: (a) DELETE stale `file_position_snapshots` rows for force-recompute; (b) add 0-1 new sub-portals to `data/europa_eu/europa.eu_all_sources.md`; (c) capture Comply/Tenderator/Documents items inline in chat KB guides + carry-over notes. Schema-level expansions (compliance_matrix / prediction_snapshots / funding-calls tenders) tracked as separate carry-over.
- **Beresol logo in every design footer (set 1 May 2026).** Every `/design` output (slide, post, hero, infographic, deep-dive, quote/table card) must include `/assets/beresol-logo.png` on a LIGHT footer (white/cream) paired with the Brubru CTA. NEVER apply `filter: brightness(0) invert(1)` to brand logos. Hero can be dark; footer is a light rest zone. Full template: `.claude/skills/design/SKILL.md` (hard rule #7).
- **lftp `--only-newer` silently skips files (set 4 May 2026).** Post-/siteground, curl `last-modified` on every changed user-visible HTML; force-push via `lftp put -O` if stale. Template: `feedback_lftp_only_newer_skips.md`.
- **Raw smtplib needs explicit `load_dotenv()` (set 4 May 2026).** Send scripts using `smtplib` directly (not via `services.email_service.EmailService`) must call `load_dotenv()` at the top or `os.environ.get("SMTP_PASSWORD")` returns None. `EmailService` auto-loads .env; raw smtplib does NOT. Memory: `feedback_send_script_dotenv_required.md`.
- **OEIL is the source of truth for rapporteur identity (set 4 May 2026).** Every deep-dive / chat KB refresh anchors on the OEIL procedure-file FIRST. Press, partner emails, cached content all lag. OEIL contradictions override local cache. Codified in `.claude/skills/deep-dive-refresh/SKILL.md` Step 1. Memory: `feedback_oeil_source_of_truth.md`.
- **RocketReach pattern guesses bounce ~50% on B2B firms (set 4 May 2026).** Email sourcing precedence: (a) Crunchbase contact-email, (b) live website /contact page, (c) RocketReach as tie-breaker only. Downgrade any "deduced" / "pattern-guessed" CSV row after 1 bounce; never reuse. Full incident (Bonsai Partners 2x bounce, 5/10 = 50% on 4 May VC retry): `memory/feedback_rocketreach_unreliable.md`. Reinforced by `feedback_no_generic_inbox_sends.md` (18 May 2026 — generic-inbox local-parts now filtered at SQL time).
- **Sonnet for /design + LinkedIn drafting (set 4 May 2026).** Delegate via Agent tool with `model: "sonnet"`. Opus orchestrates (planning, audit-queries, judgment); Sonnet writes. Stall fallback: on 600s no-progress retry once, then fall back to Opus with `[stalled-Sonnet-fallback]` note. Memory: `feedback_use_sonnet_for_design_and_linkedin.md`.
- **Phase 0 staleness check must BLOCK on TODAY-dated unhandled drops (set 4 May 2026).** `/day-before` Step 5 already mandates reading `memory/scheduled_content_drops.md` but the check ran on 4 May and did NOT surface the "Spanish VC funds outreach batch (publish Monday 4 May 2026)" entry as a flagged item — Victor had to flag it manually mid-session. Lesson: when a drop is dated TODAY and is not yet marked `[DELIVERED YYYY-MM-DD]`, the morning routine must HARD-BLOCK at Phase 0 and require explicit user acknowledgement before proceeding to Phase 1. Codified in the next /day-before SKILL.md patch. (Step 5 was already mandatory but the *blocking* semantics weren't — soft surfacing failed.)
- **/design Hard Rule #9 — no "Day X of N" badges (set 4 May 2026).** Even for multi-day event coverage (Politico AI Tech Week, conference series, week-long campaigns), the day position belongs in the overline / hero text ("Politico AI & Tech Week — opening" / "Bruxelles oggi" / "Closing day"), not as a separate small badge in the corner. Badges of this kind read as gimmicky template-design; the slide is more elegant when day-context lives inside the title. Codified in `.claude/skills/design/SKILL.md` Hard Rule #9. Set 4 May 2026 after the Tue/Wed/Thu summit slides shipped with "Day 1 / 2 / 3 of 3" badges that Victor immediately flagged.
- **Modal portal mandate (set 6 May 2026).** Any `position: fixed` overlay rendered inside an AnimatedPage (framer-motion adds `transform: translate3d(...)` which creates a new containing block per CSS spec) MUST `createPortal(modal, document.body)` to escape the transformed parent. Otherwise the overlay scopes to the AnimatedPage's box, not the viewport — siblings outside that box (FeedbackInvitation card at the bottom of My EU Bubble) bleed through and the dim background covers only part of the page. Use `z-index: 9999`, `role="dialog"`, `aria-modal="true"`. Pattern shipped in `frontend/src/components/bubble/comparator_tab.tsx`. Memory candidate: `feedback_modal_portal_required.md`.
- **OEIL URL pattern (set 6 May 2026).** Legacy `oeil.secure.europarl.europa.eu/oeil/popups/ficheprocedure.do?reference=...` 404s for recent procedures. Working endpoint: `oeil.secure.europarl.europa.eu/oeil/en/procedure-file?reference=...` (encoded `%28` or raw both work). Canonical builder: `_oeil_url()` in `services/comparator/cell_extractors.py`. Sweep complete 25 May 2026 (24 occurrences / 20 files). Generalised lesson: when fixing a URL/string-template bug, grep ALL generation paths (system prompt + guides too), not just the obvious service. Full detail: `feedback_oeil_url_endpoint.md`.
- **`EurlexFetcher.CELEX_PATTERN` is too narrow for proposals (set 6 May 2026).** Pattern `^[0-9]{5}[A-Z][0-9]{4}$` only allows ONE letter — adopted CELEX (`32016R0679` = R/L/D/H/X) match, but **Commission proposals (PC, JC, DC, …) silently fail** because they have TWO letters in the type position (`52026PC0321`, `52020DC0098`, `52022JC0XXX`). The fetcher's `normalize_celex` returns `None` and the pipeline drops the request silently. Two ways forward: (a) widen the regex to `^[0-9]{5}[A-Z]{1,2}[0-9]{4}$` in `services/parsers/eurlex_fetcher.py`; (b) bypass the fetcher entirely and call Cellar directly (current Comparator implementation in `services/comparator/structure_extractor.py`). Memory candidate: `feedback_eurlex_fetcher_celex_regex_too_narrow.md`.
- **Cellar PDF fallback for proposals (set 6 May 2026).** When Cellar XHTML 404s (proposals are PDF-only), fetch `publications.europa.eu/resource/celex/<celex>` with `Accept: application/pdf` → HTTP 300 multi-choice → grep `DOC_1` → parse with `pypdf`. Article/recital counts via regex max. Pattern shipped in `services/comparator/structure_extractor.py`. Cache to `eu_laws.extra_metadata.structure_counts`. Full template: `memory/feedback_cellar_pdf_fallback.md`.
- **Footer sidebar margin must match sidebar side (set 6 May 2026).** `frontend/src/components/shared/footer.tsx` had `pagesWithSidebar = ['/main', '/amendator', '/my-eu-bubble']` which adds `margin-left: 300px` when `isSidebarOpen` is true. But My EU Bubble's NewsSidebar is on the **RIGHT**, not the left, so the footer rendered 300px off-axis from the rest of the page chrome. Pages with right-side sidebars must NOT be in `pagesWithSidebar`. Current correct list: `['/main', '/amendator']`. If a future page adds a right-side sidebar, do NOT add it to `pagesWithSidebar` — keep the footer flush.
- **Brief headlines + snippets + suggested_query NEVER contain institutional codes (7 May 2026).** No COM/COD/INI/CELEX/A-/PE-/T-/IP-codes/Reg/Dir numbers in newsletter hero text. Use plain-language aliases ("AI Act", "Affordable Housing Plan", "EU Inc.", "28th Regime", etc.). Codes allowed inside URL targets + inside guides + sparingly in detailed snippets, never in the lead. Acceptance test before `--test`: read each headline aloud — could a journalist in Tokyo understand the so-what without Googling any code? If no, rewrite. Memory: `feedback_daily_brief_no_institutional_codes.md` (full scrub list + alias allowlist).
- **Brubru Brief replaces the daily brief (11 May 2026).** "Brubru Brief: What nobody else tells you about the EU Bubble". Variable cadence 1-3/week, no-overlap vs 6 mainstream sources (Politico/Euractiv/Euronews/FT/Bloomberg/Reuters), 3-10 headlines, send-worthiness gate. Hard rules: no em-dashes, no emojis, no institutional codes in hero text — extends to ALL Brubru-branded content (posts/slides/emails/brief). Unsubscribe endpoint: 3 pools (users/pre-users/EUTR) + always logs the event. Memory: `feedback_brubru_brief_new_format.md`.
- **EUTR sends require `email_verified=true` (11 May 2026, after 52+ bounces in 10 min).** Migration 063 added the column; all bulk sends filter `email_verified=true AND outreach_status NOT IN ('bounced','unsubscribed')`. Synthetic `info@<domain>` guesses are forbidden — they caused the bounce wave. EUTR send pool today is ZERO (47 named-prefix all pre-bounced) until manual internet-search verifies addresses. Memory: `feedback_eutr_email_verification_required.md`.
- **LinkedIn posts fact-checked line by line before publish (11 May 2026).** Every post draft (Brubru/Beresol/Victor) passes a fact-check table BEFORE being presented as ready: claim / source / verdict (TRUE/PARTIAL/SPECULATIVE/FALSE/UNVERIFIED) / note. Apply fixes to every non-TRUE row. Companion artefacts (slides, infographics) inherit the rule. Sonnet sub-agent drafts are NOT trusted without your own fact-check pass. Memory: `feedback_linkedin_post_factcheck_mandatory.md`.
- **Chat readiness verified via `/api/chat/message`, not MCP `top_guides` (11 May 2026).** MCP's `ask_brubru.top_guides` is a content-overlap retrieval-debug view, not what users see. Pass-1 keyword-trigger + LLM mediation produces the right answer even when overlap-ranking buries the right guide. Before any Brubru Brief / outreach claim about chat readiness, probe production directly via curl on `/api/chat/message`. 2 of 5 headlines on 11 May flagged red by top_guides actually worked perfectly on the real endpoint.
- **Marketing cadence Mon-Thu inside /morning (11 May 2026).** Mon = post + /design slide; Tue = reel (new every ~2 weeks, `frontend/public/europa-2026/` pattern); Wed = outreach; Thu = long-form. Fri = `/competitors`. 6 mandatory languages: EN+FR+IT+ES+CA+NL. Tier-1 import from `coreyhaines31/marketingskills` (MIT, 41 skills): 7 selected. Full plan: `memory/project_brubru_marketing_gtm_strategy_2026_05.md`.
- **Pack-objects SIGBUS bypass on `git push` (set 22 May 2026).** If `git push` returns `error: pack-objects died of signal 10` on this Mac, retry with `git -c pack.window=0 -c pack.depth=0 -c pack.compression=0 push origin main` (disables delta+compression, the crashing parts). Root cause is an mmap fault on the `~/Documents/`-mounted repo, not disk pressure. Detail: `feedback_git_push_sigbus_pack_objects`, `feedback_git_commit_hangs_use_plumbing`.
- **EP10 URL discipline (set 22 May 2026).** EP10 doceo URLs use `-10-` not `-9-`; adopted texts are `P10_TA(YYYY)NNNN`; reports `A10-NNNN/YYYY`; resolutions `B10-NNNN/YYYY`. When an EP URL returns 404, **switch tool — never re-guess a similar path**. First fallback: Tavily with date range. Second fallback: the scraper output file. Third fallback: ask the user. Verified-working anchors: `europarl.europa.eu/news/en/press-room`, `/plenary/en/votes.html?tab=votes`, `/plenary/en/texts-adopted.html`, `/plenary/en/agendas.html`. Memory: `feedback_ep_url_no_guessing`.
- **Public-marketing posts: no codes + code-grep before competitor claims (set 22 May 2026).** Rule (1): LinkedIn / public marketing copy must NEVER contain institutional codes (P10_TA, COM, COD/INI, CELEX, A-/B-/T-/PE-/IP-numbers, directive/regulation numbers). Use plain-language titles. Treaty articles + popular acronyms (GDPR, DSA, AI Act, ETS, CBAM) are common vocab and OK. Rule (2): when a counterattack/comparison post makes a feature claim against a competitor, **grep the actual Brubru code FIRST**. Incident 22 May 2026: a draft action item claimed "Brubru EP committee transcription in 6 languages" — `language="en"` is hardcoded at `services/committee_transcription_service.py:194` (Whisper uses the EN interpretation booth feed, same as competitors). The 5-second grep prevented an inflated LinkedIn post. Memory: `feedback_linkedin_no_institutional_codes`.

---

## Strategic North Star: WAPU (Weekly Active Paid Users)

**WAPU = paid subscriber + 1 core action in 7 days.** Every feature must answer: "Does this grow WAPU?"

**Core actions:** AI chat query, document generated, file tracked/checked, amendment drafted/analysed, compliance report run.

**Targets:** 10 (Phase A, months 1-3), 25 (Phase B, months 4-6), 50 (Phase C, months 7-12).

**Full details:** See `memory/strategy.md` and `docs/business_plan/strategy.html`.

---

## Catalan EU Legislation Translation Pipeline (March 2026)

**Primary engine:** Softcatala NMT (`eng-cat-2024-09-24`, CTranslate2, local, free). **Fallback:** Claude Sonnet (`--engine sonnet`). Post-processing glossary corrects known errors (d'execució, ha adoptat, Comitè dels Estats membres). When in doubt on terminology, check Spanish EUR-Lex and assess the Catalan equivalent.

**Source:** 28,513 Formex V4 XML files in `docs/LEG_2025-11/`. **Output:** `frontend/public/legislacio-ue-catala/[celex]/index.html`.

**CLI:** `cd backend && python3.12 scripts/catalan_translate.py --translate path/to.xml --celex 32016R0679`. Add `--engine sonnet` for paid high-quality.

**Key files:** `backend/scripts/catalan_translate.py` (parser + translation + HTML generator). Spec: `docs/catalan-implementation.md`. Skill: `/catalan`. Memory: `memory/catalan_translation.md`.

**Brubru Catalan standard:** D'execució (not d'implementació), Ha adoptat (not ha aconseguit), Tenint en compte, Dictamen, Paràgraf, Comitè dels Estats membres. Always regenerate `frontend/public/guides/index.html` after guide changes.
