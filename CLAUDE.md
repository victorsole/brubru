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

**All files use `snake_case`** - no exceptions.

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

## Learned Rules (Add corrections here)

*When Claude makes a mistake, add a rule below so it never happens again.*

### Brubru Supports 6 Languages, Not 23 (March 2026)

Brubru supports **6 languages**: English, French, Dutch, Spanish, Catalan, and Italian. These are the languages Victor speaks and can support users in directly. **Never claim 23 EU languages** in any material, code comment, tour step, application, or business plan. The EU has 24 official languages, but Brubru's interface and support covers 6. i18next locales: `en, fr, nl, es, ca, it`.

### Founder Name: Victor Solé (March 2026)

The founder's surname is **Solé** (with an accent on the e). Never write "Sole" without the accent. In HTML, use `Sol&eacute;`. This applies to all contexts: emails, documents, business plans, investment memos, and code comments.

### Gmail Daily Send Volume Planning (March 2026)

~2,000 recipients/day limit. Priority order: daily brief first, campaigns second, news alerts last (BCC batches of 90). **Never schedule all three on the same day.** Pick two. Gmail resets at midnight Pacific.

### Daily Brief URL Verification (March 2026)

**Never guess EP document reference numbers** (TA, A, B, P, RC). Always look up from the Texts Adopted TOC page. Append `_EN.html` suffix. Wrong number = 404 sent to all subscribers.

### Legislative Train Scraper - Data Source Unification (January 2025)

Use `get_all_files_unified()` for comprehensive scraping with OEIL refs (~500+ files). `get_all_files_fast()` for fast mode without OEIL refs. Old methods (`get_all_carriages()`, `get_package_files()`) preserved for backward compatibility. File: `backend/services/scrapers/legislative_train_scraper.py`.

### Modal Z-Index Stacking Context (January 2025)

**Always use `createPortal` for modals in My EU Bubble pages.** The `.my-eu-bubble-page > *` rule creates a stacking context that traps modal z-index values. Portal to `document.body` to escape it.

### EPRS Service Architecture (January 2025)

Always use `EPRSService` (not individual components) for EPRS operations: `from services.eprs import get_eprs_service`. Coordinates ThinkTankScraper, EPRSArchiveClient, EPRSIndexer, EPRSMatcher. File: `services/eprs/eprs_service.py`.

### OEIL XML Feed Integration (January 2026)

**Full reference:** See `memory/integrations.md` -> OEIL XML Feed section. Key files: `services/api_clients/oeil_client.py`, `services/scrapers/oeil_sync_service.py`. CLI: `python scripts/sync_oeil_feeds.py --days 7`. API: `POST /api/legislative-train/sync/oeil` (Blue tier).

**OEIL XML feed limit:** The procedures feed has a **30-day server-side limit** (`maxDays=30`). For older procedures, use `OEILClient.lookup_procedure(ref)` or `OEILSyncService.sync_single_procedure(ref)` which scrape individual OEIL pages. API: `POST /api/legislative-train/sync/oeil/lookup?reference=2025/0726(COD)` (Blue tier).

### Knowledge Guide Truncation (March 2026)

Two truncation points: **storage** at 8,000 chars (`guide_content[:8000]` in search results), **AI prompt injection** at 4,000 chars (`item['content'][:4000]` in `format_context_for_ai`). The prompt injection was the real bottleneck: it was 1,000 chars until 23 March 2026, causing document references (T9-xxx, A9-xxx) at char 1424+ to be invisible to the AI. Put key detail in **QUICK FACTS** block at top of guides. File: `context_builder.py`.

### Data-Driven Chat Follow-Ups (February 2026)

Legislative file matches trigger OEIL enrichment (Documentation Gateway + procedure page) for data-driven follow-up questions. Cached on `LegislativeCarriage.oeil_procedure_data` (7-day TTL, max 3 files/request). Key files: `context_builder.py` (`_enrich_train_files_with_actions()`), `ai_service.py` (Phase D3), `oeil_client.py`.

### EUR-Lex RSS Feed Integration (January 2026)

**Full reference:** See `memory/integrations.md` -> EUR-Lex RSS section. Key files: `services/api_clients/eurlex_client.py`, `services/scrapers/eurlex_sync_service.py`. CLI: `python scripts/sync_eurlex_feeds.py --days 7`. API: `POST /api/legislative-train/sync/eurlex` (Blue tier).

### EC Register of Commission Documents (February 2026)

**Full reference:** See `memory/integrations.md` -> Commission Documents section. Dual strategy: EUR-Lex RSS for discovery, RegDoc API for enrichment. Paginated search still returns 503. Individual document lookup works (requires browser-like headers). Key files: `services/api_clients/commission_doc_register_client.py`, `api/commission_documents.py`.

### Beresol Knowledge Bundle (January 2026)

**Full reference:** See `memory/integrations.md` -> Beresol section. 11 reports + 7 monitors in `knowledge_base/brubru-knowledge-bundle/`. **Attribution required**: Always cite "Beresol Open Report/Monitor" + `https://beresol.eu/public-affairs`. Key file: `knowledge_base/beresol_knowledge_loader.py`.

### EP Committee Work In Progress (January 2026)

**Full reference:** See `memory/integrations.md` -> Committee Work section. 26 EP committees tracked. CLI: `python scripts/sync_committee_work.py`. API: `GET /api/committee-work/items`, `POST /api/committee-work/sync` (Blue tier). Key files: `services/scrapers/committee_work_scraper.py`, `models/committee_work.py`.

### EC Public Consultations (January 2026)

**Full reference:** See `memory/integrations.md` -> Consultations section. "Have Your Say" portal integration. Subscribers: full access. Professional only: AI proposals. No subscription: CTA. CLI: `python scripts/sync_consultations.py --status open`. API: `GET /api/consultations`, `POST /api/consultations/sync` (Admin). Key files: `services/scrapers/public_consultation_scraper.py`, `api/public_consultations.py`.

### EPRS Database Integration (February 2026)

**Full reference:** See `memory/integrations.md` -> EPRS Database Integration section. EPRS publications synced from RSS to PostgreSQL. **Chatbot-only** -- no UI tab. CLI: `python scripts/sync_eprs_publications.py --days 14` (metadata), `--enrich` (PDF extraction). API: `GET /api/eprs/publications`, `POST /api/eprs/sync` (Blue tier). Context builder does two-pass search: PostgreSQL first (CELEX/procedure/text), ChromaDB semantic second. Key files: `models/eprs_publication.py`, `services/scrapers/eprs_sync_service.py`, `api/eprs.py`.

### SQLAlchemy `metadata` Reserved Attribute (January 2025)

Use `doc_metadata` instead of `metadata` for document metadata fields in SQLAlchemy models. `metadata` conflicts with the built-in declarative_base attribute.

### Frontend Services Must Include Auth Headers (March 2026)

**Every frontend API service** must include `authHeaders()` on authenticated endpoints. No global axios interceptor exists. Pattern: `const token = useAuth.getState().token; return token ? { Authorization: \`Bearer ${token}\` } : {};` applied to every axios call. Lesson: missing auth headers caused calendar to show zero events for a month (fixed 16 March 2026).

### Development Server Ports (January 2025)

Frontend: port 5173 (kill existing first: `lsof -ti:5173 | xargs kill -9 2>/dev/null`). Backend: port 8000. Never let Vite auto-pick another port.

### Markdown Rendering in React (January 2025)

Use `marked` library: `<div dangerouslySetInnerHTML={{ __html: marked.parse(content) as string }} className="markdown-content" />`. CSS class `.markdown-content` styles headings/lists. Used in `document_generator_wizard.tsx`.

### EUR-Lex Parser: COM Documents vs OJ Documents (January 2025)

`EurlexParser` handles two formats: **OJ** (CELEX starts with `3`, adopted legislation, CSS: `.oj-doc-ti`, `.oj-ti-art`) and **COM** (CELEX starts with `5`, proposals, CSS: `.Titreobjet`, `.ManualConsidrant`). Auto-detects via `_detect_com_document()`. File: `backend/services/parsers/eurlex_parser.py`.

### Legislative Train OEIL Data Quality (January 2025)

**Known issue:** Some carriages have incorrect/duplicate OEIL procedure refs. Causes wrong OEIL links and file matching. Needs database cleanup: remove duplicates, re-scrape refs, validate mappings. File: `backend/services/scrapers/legislative_train_scraper.py`.

### No Emojis - Use MDI Icons (January 2025)

**Never use emojis in the codebase.** Frontend: use MDI icon classes (`mdi-check`, `mdi-close`, `mdi-alert`, `mdi-file-document`, `mdi-magnify`). Backend logging: use text prefixes `[OK]`, `[INFO]`, `[WARN]`, `[ERROR]`, `[START]`/`[STOP]`. The € symbol and accented characters (é, ñ) are NOT emojis.

### Standalone HTML Files Must Follow Brubru Aesthetics (February 2026)

**Every standalone HTML file** MUST use: Adobe Caslon Pro font (`@font-face` from `New-Yorker-Font/`), Brubru palette (`#0693e3` blue, `#059669` green, `#9b51e0` purple, `#d97706` amber, `#dc2626` red), white background, `brubru_mainlogo.png` logo, relative paths. No double dashes (`--`), rainbow gradient CTAs, lowercase after colons. Neutrals: `#111827` text, `#6b7280` secondary, `#e5e7eb` border, `#f3f4f6` bg-alt.

### Header Icon Navigation (January 2025)

Header uses animated MDI icon buttons (icon-only, expand on hover). Nav colours: Main=Blue(`#0693e3`), Bubble=Purple(`#9b51e0`), Amendator=Green(`#059669`), Comply=Silver(`#9ca3af`), Tenderator=Gold(`#d97706`). CSS class: `.header__nav-icon-btn--{color}`. Files: `frontend/src/components/shared/header.tsx`, `header.css`.

### Feature Completion Checklist (January 2026)

Before marking a feature COMPLETE, verify end-to-end: (1) DB has data, (2) API returns data, (3) frontend builds, (4) hook is used in a component, (5) manual browser test, (6) chatbot context works if applicable. **Never mark "PARTIAL" and move on.**

### Multi-Provider AI System (March 2026)

**Claude Sonnet 4 is the primary model** (switched from Haiku 4.5 on 23 March 2026). $10/day cap. Haiku was ignoring document retrieval instructions. Fallback: Mistral -> GPT-4 -> Gemini. Routing: `has_knowledge = internal_knowledge OR eu_institutional_results` (virtually all queries). **Streaming is the default chat mode** (switched 7 April 2026): `/api/chat/stream` SSE endpoint with token-by-token text + status events ("Searching EU legislation...", "Composing response..."). Automatic fallback to non-streaming `/api/chat/message` if stream fails. **SSE newline escaping:** Backend escapes `\n` as `\\n` in text chunks (`chat.py`), frontend decodes back to `\n` (`chat_interface.tsx`). Markdown rendered continuously via `marked.parse()` during streaming (no mode switch). File: `multi_provider_service.py`, `ai_service.py` (`chat_stream`), `chat_interface.tsx`.

### EU Institutional Source Search Fallback (March 2026)

When no knowledge guide matches, Tavily searches 25 trusted EU domains. **Also fires when user has procedure-intent keywords** (timeline, status, rapporteur, vote, INI, COD) even if a generic guide matched, as long as no procedure details were found. Additionally, OEIL topic search via Tavily fires when keyword OR results are noise (no confident title match). Key files: `context_builder.py` (`_fetch_eu_institutional_search()`, `_fetch_legislative_train_files()` OEIL topic search block).

### EP Plenary Debate Transcripts (CRE) (March 2026)

On-demand CRE XML fetch from Doceo (no DB storage). 22 intent triggers in 6 languages. Max 4,000 chars per debate. 3-5 day publication delay. Key files: `cre_client.py`, `context_builder.py` (`_detect_plenary_debate_intent()`), `ai_service.py` (debate summary structure). Spec: `docs/maria/ep_cre_transcripts.md`.

### Featured Chatbot Questions Source (March 2026)

From `chat_example_prompts` table (scope=`'main_chat'`, is_active=`true`), NOT `daily_briefs.suggested_query`. API: `GET /api/chat/examples?scope=main_chat&limit=4`. Fallback: i18n keys `chat.example1-4`.

### EPRS Enrichment: Skip During Morning Routine (March 2026)

`python3.12 scripts/sync_eprs_publications.py --enrich` downloads PDFs and runs CPU-only embedding (BAAI/bge-m3). This takes **15+ minutes** for even a handful of publications. **Do not run `--enrich` during the `/morning` routine.** Run metadata-only sync (`--days 7` without `--enrich`) instead. Schedule `--enrich` overnight or skip entirely.

### Daily Brief BCC Batching (March 2026)

`send_daily_brief_batch()` in `services/daily_brief_email.py` now uses **BCC batching** (90 recipients per SMTP connection) instead of individual sends. This avoids the Gmail rate limit (~80-100 individual sends per session). Greeting is generic ("Good morning") with no personalisation. The `daily_brief_sends` table still tracks per-recipient duplicate prevention.

### Document Retrieval Rule (March 2026)

The AI MUST present all document references (T9-xxx, A9-xxx, PE-xxx, COM-xxx) from knowledge guides immediately with clickable URLs. NEVER say "I don't have the texts" when the guide lists them. NEVER tell users to "search EUR-Lex yourself." NEVER ask "which version do you need?" This is Brubru's core value: fetching buried EU documents and delivering them efficiently. System prompt rule in `ai_service.py`. Also: Document Gateway references with doceo URLs are now injected via `key_documents` in `available_actions` from `context_builder.py`.

### Audit Queries: Check User Identity (March 2026)

Always join `chat_messages -> chats (user_id) -> users (email)` when auditing queries. Victor's test queries (victor@hellobo.eu) should be noted but not treated as real user issues. Focus on external users. The EU-ESOP queries on 19 March were all Victor's tests, not real users.

### RSS AI Enrichment - On-Demand Only (January 2026)

AI enrichment is **on-demand only** (`enable_ai_enrichment=False` by default) to avoid $5/day cost. Trigger via `POST /api/rss/entries/{entry_id}/enrich`. Files: `services/rss/rss_processor.py`, `api/rss_feeds.py`.

### Predictions: EP Group Colours + Resolution Indicators (February 2026)

**Full reference:** See `memory/predictions.md`. FOR=green, AGAINST=red, ABSTENTION=yellow, SPLIT=gold. Resolution leading indicators: OEIL_CROSSREF (1.0), COMMISSION_FOLLOWUP (0.9), TITLE_SIMILARITY (0.5-0.8).

### Knowledge Loader Orphan Guide References (April 2026)

**Every trigger in `GUIDE_KEYWORD_TRIGGERS` must point to an existing `.md` file in `knowledge_base/guides/`.** If a trigger references a guide ID with no corresponding file, `search_guides()` silently drops the match (the guide ID is not in `self.guides`). This means the trigger exists but does nothing. Found 3 orphans on 1 April 2026, then **17 more on 3 April 2026** (298 dead mappings total, including `eu_justice_security`, `eu_agriculture_policy`, `eu_consumer_protection`, `eu_taxation_policy`, etc.). All fixed by rerouting to existing guides. **After any bulk trigger changes, run the orphan audit:** `python3.12 -c "from knowledge_base.knowledge_loader import KnowledgeLoader, GUIDE_KEYWORD_TRIGGERS; kl = KnowledgeLoader(); kl.load_all(); orphans = {gid for t, ids in GUIDE_KEYWORD_TRIGGERS.items() for gid in ids if gid not in kl.guides}; print(f'Orphans: {orphans}' if orphans else 'No orphans')"`.

### Responsive Design Requirement (February 2026)

**ALL UI changes MUST be responsive.** Breakpoints: Desktop >1024px (default), Tablet 768-1024px (`max-width: 1024px`), Mobile <768px (`max-width: 767px`). Mobile: single column, overlay sidebars, min 44px touch targets. Use `createPortal` for modals. **Never ship without testing all three breakpoints.**

### Email Campaign System (February 2026)

**Full reference:** See `memory/email_campaigns.md`. Gmail SMTP (Google Workspace), no third-party dependencies. Gmail limit: ~2,000 recipients/day, 90 per BCC batch. 8 tailored institution templates + 12 multilingual lobby cluster templates. Key files: `services/email_service.py`, `scripts/send_lobby_campaign.py`, `scripts/collect_institution_emails.py`. Data: `data/emails/`. Docs: `docs/email_system_prompt.md`.

### SPA Pre-rendering for AI Crawlers (February 2026)

**Full reference:** See `memory/deployment.md`. Production deploy: `npm run build:prerender`. 9 public routes pre-rendered with Puppeteer. `main.tsx` uses conditional hydration. Add new public routes to `ROUTES` array in `frontend/scripts/prerender.mjs`. AI crawler rules in `frontend/public/robots.txt`.

### SiteGround FTP Deploy (April 2026)

`lftp` can upload `frontend/dist/` directly to SiteGround: `lftp -c "set ftp:ssl-allow no; open -u ftp@beresol.eu,PASSWORD ftp.beresol.eu; mirror --reverse --verbose --only-newer --exclude .DS_Store --exclude .htaccess dist/ brubru.beresol.eu/public_html/; bye"`. Credentials in `.env` (`SITEGROUND_FTP_*`). Always exclude `.htaccess` (managed by SiteGround). Old JS bundles (`index-*.js`) accumulate on the server -- not harmful but could be cleaned up periodically.

### Brubrufied Daily Brief System (April 2026)

**5 headlines per day** (default, more only if justified). Each headline has three layers: (1) headline text linking to source, (2) **suggested question** in italics as the engagement hook, (3) **"Ask Brubru" button** linking to `/main?q=...` which pre-fills the chat input. The `suggested_query` column in `daily_briefs` drives both the question and the CTA link. **Every headline MUST have a suggested_query.** Before sending, verify Brubru can answer each suggested query well (test against knowledge base, fix gaps first). Feature line at the bottom is dynamic (reads real guide/file counts). Frontend `ChatInterface` reads `?q=` from `window.location.search` on mount. Chat route is `/main` (NOT `/chat`). Files: `services/daily_brief_email.py`, `scripts/send_daily_brief.py`, `components/chat/chat_interface.tsx`.

### Daily Brief Send Protocol (March 2026)

**CRITICAL.** On 25 March 2026, daily brief was sent to 70 subscribers with fabricated URLs (404 errors). Two compounding failures: (1) used `--send --extra` which sends to ALL subscribers not just test address, (2) constructed URLs from patterns instead of verifying they exist. **Mandatory protocol:** (1) `--verify-urls` to check all headline URLs return HTTP 200, (2) `--test` to send ONLY to hello@beresol.eu, (3) wait for Victor's OK, (4) only then `--send`. Code guardrails added: `--send` now blocks if any URL fails verification. File: `scripts/send_daily_brief.py`.

### Catalan Legal Translation Glossary (March 2026)

Softcatala NMT does not distinguish legal context. Key corrections applied via `GLOSSARY_CORRECTIONS` in `scripts/catalan_translate.py`: "Mentre que:" -> "Atenent que:" (EU recitals "Whereas"), "d'implementacio" -> "d'execucio" (Implementing), "ha aconseguit" -> "ha adoptat" (has adopted). "Having regard to" -> "Tenint en compte" is already correct. Confirmed by Catalan legal expert (25 March 2026). After any glossary update, patch existing translated HTML files too.

### macOS Tahoe iCloud File Eviction (March 2026)

If `~/Documents` is synced to iCloud with "Optimise Mac Storage" enabled, macOS Tahoe (26.x) can evict git pack files and working tree files to iCloud, marking them `compressed,dataless`. Any process trying to read them gets `Need authenticator` (errno 81). `com.apple.provenance` xattr is a red herring -- the real cause is `dataless`. **Fix:** Disable iCloud optimisation for the GitHub folder, or move it outside iCloud-synced directories. To recover a broken repo: `rm -rf .git && git init && git remote add origin <url> && git fetch origin && git reset origin/main`, then `rm -f` and `git checkout origin/main --` for any locked working tree files.

### EUR-Lex Cellar API for Document Fetch (March 2026)

EUR-Lex WAF (`eur-lex.europa.eu`) blocks all automated requests (returns HTTP 202 / 0 bytes or WAF cookie challenge). **Bypass:** Use `publications.europa.eu/resource/celex/{celex}` with `Accept: application/xhtml+xml, text/html` and `Accept-Language: eng` for document content (follows redirects through Cellar UUID). Returns OJ-format XHTML. Also works with `Accept: application/rdf+xml` for metadata. **OJ discovery:** RSS feed at `eur-lex.europa.eu/EN/display-feed/OJ/L/rss.xml` works from non-sandboxed environments but may be WAF-blocked from Claude Code. Fallback: SPARQL at `publications.europa.eu/webapi/rdf/sparql` (may have indexing delay for same-day OJ). CLI: `python3.12 scripts/catalan_translate.py --cellar 32026R0722`.

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
