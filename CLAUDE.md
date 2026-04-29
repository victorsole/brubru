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
**AI:** Mistral (primary), Claude (fallback 1), GPT-4 (fallback 2), Gemini (fallback 3)
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

- **Brubru = 6 languages** (EN, FR, NL, ES, CA, IT). Never claim 23.
- **Founder name: Victor Solé** (with accent; HTML: `Sol&eacute;`).
- **No emojis in codebase.** Use MDI icons (frontend) or `[OK]`/`[INFO]`/`[ERROR]` prefixes (backend).
- **Document retrieval:** AI MUST present T9-/A9-/PE-/COM- references with clickable URLs from knowledge guides. Never say "search EUR-Lex yourself."
- **Daily brief send protocol:** `--verify-urls` → `--test` to hello@beresol.eu → wait for explicit OK → `--send`. Never `--send --extra` without test-first.
- **Responsive design:** all UI changes must work at desktop (>1024px), tablet (768-1024px), mobile (<768px).
- **5 headlines/day** in daily brief (default). Every headline has a `suggested_query` → pre-verified the chatbot can answer.
- **Canonical products:** Chat, Amendator, My EU Bubble, EU Law Comply, Tenderator, API. My EU Bubble sub-tabs in order: Dashboard, My Files, Position Analysis, My EU Calendar, Predictions, EC Public Consultations, Documents, Amendments, Legislative Tracker, Analytics. Never invent non-canonical tabs.
- **Catalan output must be accented:** sóc, perquè, política, Brussel·les, regulació, Víctor Solé.
- **Context formatter truncates at 32k** — on-demand blocks go near the TOP of `format_context_for_ai()`.
- **DB model / migration parity:** a new column in a migration must also appear on the SQLAlchemy model in the same commit.
- **Week-ahead (Friday brief):** verify every item against primary EU source (doceo, college-agenda, consilium) before sending. Never trust `eu_calendar_events` DB blindly.
- **Legal-text layer:** display/parse/query EU legal text through `services/parsers/` (recital-article linker, definition extractor, cross-reference resolver, law alias resolver, combined annotator). Frontend via `<LegalText>` + `use_legal_intelligence.ts`.
- **On-demand chatbot features** follow the 4-step template (client → intent detector → fetcher → system prompt rule). Block appended near top of context formatter.
- **.env in shell:** never `source .env`. Use `grep '^VAR=' .env | cut -d= -f2-`.
- **Frontend module mismatch:** `rm -rf node_modules package-lock.json && npm install --legacy-peer-deps`.
- **Knowledge guides:** QUICK FACTS block at top. Prompt injection cap 4,000 chars in `format_context_for_ai`. After bulk trigger changes, run orphan audit.
- **EUR-Lex WAF bypass:** use `publications.europa.eu/resource/celex/{celex}` with `Accept: application/xhtml+xml`. Never scrape `eur-lex.europa.eu` directly.
- **SiteGround FTP:** env var is `SITEGROUND_FTP_PASS` (not `_PASSWORD`). `.htaccess` MUST be uploaded. Catalan landing page at `data/legislacio-ue-catala/index.html` uploaded separately.
- **Daily brief unsubscribe filter:** `services/daily_brief_email.py::_get_all_recipient_emails()` must subtract `daily_brief_unsubscribe` events from BOTH `users` and `pre_user_events` pools. Fixing only the `--extra-file` branch leaks chronic bouncers.
- **/session-summary must overwrite memory/day_before.md every session** as its first persistent action. This file is the ONLY context-recovery input for the next morning's `/day-before`. Skipped on 18/20/21 April 2026 — cost the 22 April session a reconstruction from git log. Fix shipped: `.claude/skills/session-summary/SKILL.md` Step 6a is now mandatory-first; `.claude/skills/day-before/SKILL.md` runs a staleness check on the `# Previous Session:` heading.
- **Seed / test fixtures in production-shared tables must be filterable at query time.** Incident (22 April 2026): a `committee_meeting_transcripts` row with `event_id=libe-seed-20260417`, status=COMPLETED, 340 words of synthetic dialogue (fake plenary vote 228/311/92, fake T10-0095/2026, fake rapporteur quotes) was feeding the chatbot, which faithfully cited the fabricated facts in every CSAM / ePrivacy query. Fix pattern: exclude seed rows via `event_id ILIKE '%seed%'`/`%test%'` + `title ILIKE '%seed test transcript%'`/`%synthetic%'` at every retrieval stage. See `context_builder.py::_fetch_committee_transcript_block`. Memory: `memory/feedback_seed_fixtures_contaminate_prod.md`. Better long-term pattern: add an `is_test` boolean column at table-creation time for any fixture-prone table.
- **send_daily_brief.py URL verify uses GET + real browser User-Agent.** Never HEAD (consilium returns 405, some EP pages too), never the string "Brubru URL checker" (Cloudflare 403s it). The verify function in `backend/scripts/send_daily_brief.py` sends a Chrome UA + `Accept` + `Accept-Language` headers, reads 1 KB, closes — fast and reliable. Incident 22 April 2026.
- **/morning Phase 3 cadence — DAILY core vs FRIDAY sweep (set 27 April 2026, API moved to DAILY 28 April 2026).** After the first full feature-tree population on 27 April, the data layers split clearly: **DAILY** = Chat (KB/triggers/system prompt) + My EU Bubble Calendar + Archive auto-sweep + passive My Files/Tracker via OEIL sync + **API (hero URL rotation + new data-source registration)**. **FRIDAY ONLY** = EU Law Comply matrix + Tenderator + Documents Generator templates + Predictions/Position Analysis snapshot invalidation. **ON USER REQUEST ONLY** = Amendator example URL rotation, EC Public Consultations sync. **API moved to DAILY on 28 April 2026** because the API page is the public-facing surface that prospects and partners (GovClipping et al.) hit first; staleness on the hero example URL is a conversion liability. Reason for the rest: Comply/Tenderator/Documents don't move enough to justify daily updates; Predictions/Position recompute on-demand anyway. Codified in `.claude/skills/morning/SKILL.md` Phase 3 (sub-phases 3D + 3F) and `.claude/skills/news/SKILL.md` Step 3 cadence table. Friday-only items approved on Mon-Thu /news runs queue to `memory/friday_sweep_queue.md`.
- **Archive feature for items with lifespan (migration 041, 27 April 2026).** Migration 041 added `archived_at TIMESTAMPTZ + archived_reason TEXT` to all 6 user_*_tracks tables, plus new `user_calendar_event_archives` join table (RLS-enabled). API: `POST/restore /api/archive/{entity_type}/{track_id}`, `GET /api/archive/list`, `POST /api/archive/calendar/{event_id}`. Auto-archive script: `scripts/auto_archive_old_items.py` (dry-run + apply); rules: carriages 90d post-adoption, consultations 30d post-deadline, commission_docs 180d stale. **Run during /morning Phase 3D as part of daily Archive sweep.** Existing tracking list endpoints still need `WHERE archived_at IS NULL` filter — TODO follow-up for full UI integration.
- **/news Step 5b LinkedIn post is mandatory (set 27 April 2026).** Every /news run must end with a draft LinkedIn post saved to `docs/marketing/linkedin_YYYY_MM_DD_daily_update.md`. Goal: institutional drumbeat showing Brubru is updated daily across the whole product. Template + quality bar in `.claude/skills/news/SKILL.md` Step 5b. Victor publishes manually; Claude never posts to LinkedIn directly.
- **Negation paradox in guide WARNINGs AND in the system prompt (set 27 April 2026, scope extended 28 April 2026).** Never name a forbidden identifier inside its own "do not cite X" warning — that paradoxically RE-PRIMES the model to emit X. The rule applies to BOTH knowledge guides AND the `_build_system_prompt()` text in `services/ai_service.py`. Original 27 Apr incident: csam_regulation_online.md WARNING block listed "Birgit Sippel", "PE784.310", "PE784.377", "A10-0040/2026" inside the prohibition. **28 Apr regression**: the same identifiers were still listed verbatim in `ai_service.py` "NEVER INVENT IDENTIFIERS" CRITICAL block (lines 1143-1146 at the time) — Chat 01fd91a1 on 27 Apr 08:05 (LIBE / 2025/0429(COD)) still surfaced them in the answer. Fix pattern: scrub all named identifier values from BOTH guide content AND the system prompt; describe the FORMAT (e.g. "PE-numbers: PE followed by digits and a sub-version") never the value. Also: any production scripts (e.g. `sync_committee_transcripts.py`) carrying named-MEP / fabricated-tally seed fixtures must move them to a `tests/` directory with `is_test=True` row markers — keeping them in production grep-paths is itself a re-priming surface. Memory: `feedback_negation_paradox_in_warnings.md` + `feedback_seed_fixtures_contaminate_prod.md`.
- **CLI wrapper parity (set 27 April 2026).** When a parameter is added to a service function (`services/*.py`), audit every CLI wrapper that calls it (`scripts/*.py`) and ensure it accepts and passes through the new parameter. Otherwise the feature ships dead. Incident: Friday's commit `235086d4` added `feature_map` to `_build_brief_email_html` + `send_daily_brief_batch` but never wired it to `scripts/send_daily_brief.py`; per-headline feature CTAs were absent from bulk sends for 3 days. Fix shipped 27 Apr: added `--feature INDEX:LABEL:URL` flag. Memory `feedback_cli_wrapper_parity.md`.
- **Bulk outreach must use SMTP-level BCC (set 27 April 2026).** Any send_batch_*.py script must use a SINGLE SMTP connection with multiple RCPT TO calls (one MIMEText, To=hello@beresol.eu visible, each recipient sees only that address). Per-recipient `EmailService.send()` opens a fresh SMTP connection each time and hits Gmail throttle around the 80-100 mark. Env-var name is **SMTP_PASSWORD** (not SMTP_PASS or EMAIL_PASSWORD). 0.5s delay between RCPT TOs. If SMTP_PASSWORD is unset, abort the send rather than fall back to per-recipient. Memory `feedback_send_batch_use_bcc.md`.
- **Argparse `nargs="+"` is an anti-pattern for repeatable flags (set 29 April 2026, after 3rd incident).** Any CLI flag intended to be repeated **must** use `action="append"`, never `nargs="+"`. With `nargs="+"`, repeated flag invocations silently overwrite earlier values — only the last list survives, and earlier values are dropped without warning. Three confirmed incidents in `scripts/send_daily_brief.py`: 27 April `--feature` (5 CTAs collapsed to 1, only the 5th rendered to 128 recipients), 29 April `--news` (3 items collapsed to 1, daily-brief test caught it before send), 29 April `--week-ahead` (preventive fix during the same session). The earlier `feedback_cli_wrapper_parity.md` rule (27 April) was correct in spirit but not enforced retroactively across all argparse flags. **Mandate going forward**: (a) when adding any new repeatable CLI flag, default to `action="append"` and document why; (b) when auditing existing scripts, scan for `nargs="+"` + "repeat the flag" semantics and migrate; (c) when fixing one occurrence, audit ALL argparse decorators in the same file in the same commit. Memory: `feedback_cli_wrapper_parity.md` extended with the third-incident pattern.

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
