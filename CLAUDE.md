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

The Predictions tab in My EU Bubble provides AI-powered legislative outcome predictions.

**Key Files:**
- `backend/api/predictions.py` - All prediction API endpoints
- `backend/services/predictions/` - Prediction services (timeline, outcome, group vote, QMV, etc.)
- `backend/services/matching/resolution_legislation_matcher.py` - Resolution leading indicators
- `frontend/src/components/bubble/predictions_tab.tsx` - Main UI component
- `frontend/src/components/bubble/predictions_tab.css` - Styling (1,400+ lines)
- `frontend/src/services/prediction_service.ts` - API client
- `frontend/src/hooks/use_predictions.ts` - Zustand state management
- `docs/predictions.md` - Full technical documentation

**API Endpoints:**
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/predictions/timeline/{ref}` | POST | Timeline prediction |
| `/api/predictions/outcome/{ref}` | POST | Outcome prediction |
| `/api/predictions/vote/ep/{ref}` | POST | EP plenary vote |
| `/api/predictions/council/vote/{ref}` | POST | Council vote (Blue tier) |
| `/api/predictions/resolutions/{ref}` | GET | Resolution leading indicators |
| `/api/predictions/qmv/calculate` | POST | QMV calculator |

**Access:**
- No subscription: Locked (upgrade CTA)
- Starter/Advocate/EP (yellow tier): 10 predictions/month
- Professional (blue tier): Unlimited + Council analysis

**EP Groups (in `use_predictions.ts`):**
EPP (188), S&D (136), PfE (84), ECR (78), Renew (77), Greens/EFA (53), The Left (46), NI (33), ESN (25)

## EU Calendar Feature (February 2026)

My EU Calendar tab in My EU Bubble aggregates institutional events from 6 data sources (274 events).

**Key Files:**
- `backend/api/eu_calendar.py` - API endpoints (events, institutions, policy areas, sync)
- `backend/models/eu_calendar.py` - `EUCalendarEvent` model + enums
- `backend/services/scrapers/eu_calendar_sync_service.py` - Sync coordinator (all sources)
- `backend/services/scrapers/ep_calendar_loader.py` - EP calendar JSON loader
- `backend/services/scrapers/council_calendar_loader.py` - Council + ECB JSON loader
- `backend/services/scrapers/ec_college_scraper.py` - Commission College meeting generator
- `backend/services/scrapers/college_oj_scraper.py` - Commission OJ agenda scraper (RegDoc API)
- `backend/services/scrapers/college_oj_sync_service.py` - OJ agenda sync/enrichment
- `backend/services/scrapers/committee_agenda_scraper.py` - EP committee draft agenda scraper
- `backend/services/scrapers/committee_agenda_sync_service.py` - Committee agenda sync
- `backend/knowledge_base/eu_calendar_institutions.py` - Institution + policy area mappings
- `backend/schemas/eu_calendar_schemas.py` - Pydantic response models
- `frontend/src/components/bubble/eu_calendar_tab.tsx` - Calendar UI (month/week/day views)
- `frontend/src/components/bubble/eu_calendar_tab.css` - Calendar styling (1,250+ lines)
- `frontend/src/hooks/use_eu_calendar.ts` - Zustand state management
- `frontend/src/services/eu_calendar_service.ts` - API client

**Sync CLI:**
```bash
python scripts/sync_eu_calendar.py              # Full sync (all sources)
python scripts/sync_committee_agendas.py        # EP committee agendas
python scripts/sync_college_agendas.py --verbose # Commission College OJ
```

**Access:**
- No subscription: Upgrade CTA (`eu_calendar_cta.tsx`)
- Starter/Advocate/EP+ (yellow tier): Full read access, all views and filters
- Professional (blue tier): AI daily summary + sync trigger

**Commission College OJ Scraper Notes:**
- EC Register paginated search returns 503; individual lookup `GET /api/search/OJ(YYYY)NNNN?lang=en` works
- Sequential reference enumeration with 3-second delay, browser-like headers
- Baseline: OJ(2026)2550 = 14 Jan 2026
- Fuzzy date matching (+/-1 day) for Strasbourg Tuesday meetings vs Brussels Wednesday meetings

## Pricing Model: Modular A La Carte + Bundles (February 2026)

The old 3-tier model (White free / Yellow 79/month / Blue 599/month) has been replaced with a modular pricing system. **Internal feature gating still uses white/yellow/blue tiers** -- the new plans map to these internally.

### Plans and Pricing

**Individual Modules:**

| Module | Monthly | Annual | Internal Tier |
|--------|---------|--------|---------------|
| Brubru Chat | 29 | 288/year | yellow |
| My EU Bubble | 29 | 288/year | yellow |
| Amendator | 19 | 109/year | yellow |
| EU Law Comply | 29 | 288/year | yellow |
| Tenderator | 49 | 539/year | yellow |

**Bundles:**

| Bundle | Monthly | Annual | Internal Tier |
|--------|---------|--------|---------------|
| Starter (Chat + Bubble) | 39 | 396/year | yellow |
| Advocate (Chat + Bubble + Amendator) | 59 | 499/year | yellow |
| Professional (all 5 modules) | 99 | 799/year | blue |

**EP Plan (APAs/MEPs):** 49/month, 539/year -> yellow tier

**Free Trial:** 14 days on all plans. No permanent free tier.

### Plan-to-Tier Mapping

```python
PLAN_TO_TIER = {
    "chat": "yellow", "bubble": "yellow", "amendator": "yellow",
    "comply": "yellow", "tenderator": "yellow",
    "starter": "yellow", "advocate": "yellow",
    "professional": "blue",  # Only Professional maps to blue
    "ep": "yellow",
}
```

### Stripe Configuration

9 Stripe Products with 18 Price IDs (monthly + annual for each). Environment variables:

```env
# Individual modules (monthly + annual each)
STRIPE_CHAT_MONTHLY_PRICE_ID / STRIPE_CHAT_ANNUAL_PRICE_ID
STRIPE_BUBBLE_MONTHLY_PRICE_ID / STRIPE_BUBBLE_ANNUAL_PRICE_ID
STRIPE_AMENDATOR_MONTHLY_PRICE_ID / STRIPE_AMENDATOR_ANNUAL_PRICE_ID
STRIPE_COMPLY_MONTHLY_PRICE_ID / STRIPE_COMPLY_ANNUAL_PRICE_ID
STRIPE_TENDERATOR_MONTHLY_PRICE_ID / STRIPE_TENDERATOR_ANNUAL_PRICE_ID

# Bundles (monthly + annual each)
STRIPE_STARTER_MONTHLY_PRICE_ID / STRIPE_STARTER_ANNUAL_PRICE_ID
STRIPE_ADVOCATE_MONTHLY_PRICE_ID / STRIPE_ADVOCATE_ANNUAL_PRICE_ID
STRIPE_PROFESSIONAL_MONTHLY_PRICE_ID / STRIPE_PROFESSIONAL_ANNUAL_PRICE_ID

# EP Plan
STRIPE_EP_MONTHLY_PRICE_ID / STRIPE_EP_ANNUAL_PRICE_ID
```

### Key Files

- `backend/api/stripe_payment.py` - Checkout session creation with plan-to-price mapping
- `backend/api/subscriptions.py` - `/plans` endpoint with full pricing breakdown
- `backend/core/config.py` - All 18 STRIPE_*_PRICE_ID environment variables
- `backend/schemas/subscription_schemas.py` - `UpgradeRequest` with `plan` field (9 valid values)
- `frontend/src/hooks/use_subscription.ts` - `createCheckoutSession(plan, billingPeriod)`
- `frontend/src/pages/subscription_page.tsx` - Redesigned UI: billing toggle, 3 bundle cards, EP banner, 5 module cards, feature comparison table
- `frontend/src/pages/subscription_page.css` - Grid layouts for bundles (3 cols) and modules (5 cols)
- `frontend/src/pages/landing_page.tsx` - Pricing section with Starter/Advocate/Professional cards
- `docs/marketing/pricing_strategy.md` - Full pricing strategy document with Stripe Product/Price IDs

### User-Facing Text Rules

- **Never reference** White/Yellow/Blue tiers in user-facing text
- Use plan names: Starter, Advocate, Professional, EP Plan, or individual module names
- CTA buttons: "Start Free Trial", "Subscribe", "Get Professional"
- Generic upgrade: "Subscribe -- from 39/month"
- All 6 locales (en, es, ca, fr, it, nl) updated with new pricing text

---

## Learned Rules (Add corrections here)

*When Claude makes a mistake, add a rule below so it never happens again.*

### Brubru Supports 6 Languages, Not 23 (March 2026)

Brubru supports **6 languages**: English, French, Dutch, Spanish, Catalan, and Italian. These are the languages Victor speaks and can support users in directly. **Never claim 23 EU languages** in any material, code comment, tour step, application, or business plan. The EU has 24 official languages, but Brubru's interface and support covers 6. i18next locales: `en, fr, nl, es, ca, it`.

### Founder Name: Victor Solé (March 2026)

The founder's surname is **Solé** (with an accent on the e). Never write "Sole" without the accent. In HTML, use `Sol&eacute;`. This applies to all contexts: emails, documents, business plans, investment memos, and code comments.

### Gmail Daily Send Volume Planning (March 2026)

Google Workspace has a ~2,000 recipient/day limit, but in practice Gmail closes SMTP connections after ~100-150 individual sends per session. When combining daily brief (~100 recipients) + campaigns in the same day, the second batch gets rate-limited.

**Rule:** Plan email volume across the day:
1. Daily brief first (~100 recipients, highest priority)
2. Campaigns with remaining capacity (~100 sends before limit)
3. News alerts last (BCC batches of 90, most recipients)
4. If limit hit, retry next day. Gmail resets at midnight Pacific.

**Never schedule daily brief + large campaign + news alerts all on the same day.** Pick two.

### Daily Brief URL Verification (March 2026)

EP Texts Adopted URLs use sequential reference numbers (TA-10-2026-NNNN) that **cannot be guessed**. A wrong number = 404 = broken link sent to all subscribers.

**Rule:** Before inserting any EP document URL into `daily_briefs`, **verify it exists** by fetching the actual Texts Adopted TOC page:
- `https://www.europarl.europa.eu/doceo/document/TA-10-2026-MM-DD-TOC_EN.html`
- Find the exact TA number for the resolution title
- Always append `_EN.html` suffix to TA URLs

**Never guess EP document reference numbers.** Always look them up from the TOC or plenary results page. This applies to all EP document types (TA, A, B, P, RC).

### Legislative Train Scraper - Data Source Unification ✅ RESOLVED (January 2025)

The `LegislativeTrainScraper` had TWO scraping methods with only 23% overlap. This is now **SOLVED**.

**New unified method:**
```python
# Use this for comprehensive scraping with OEIL refs
files = await scraper.get_all_files_unified()

# Fast mode (no detail fetching, no OEIL refs)
files = await scraper.get_all_files_fast()
```

**Old methods (preserved for backward compatibility):**

| Method | Source | Files | Has OEIL Refs |
|--------|--------|-------|---------------|
| `get_all_carriages()` | Train/theme pages | ~366 | No |
| `get_package_files()` | Package pages | ~441 | Yes |
| **`get_all_files_unified()`** | **Both sources** | **~500+** | **Yes (95%+)** |

See: `backend/services/scrapers/legislative_train_scraper.py`
See: `docs/architecture/scraper_knowledge_base_consolidation.md`

### Modal Z-Index Stacking Context (January 2025)

Modals on the "My EU Bubble" page get hidden behind the sticky header due to CSS stacking contexts.

**Root cause:** `.my-eu-bubble-page > *` applies `position: relative; z-index: 1;` to all children, creating a stacking context that traps modal z-index values.

**Solution:** Use React's `createPortal` to render modals to `document.body`, escaping the stacking context:

```tsx
import { createPortal } from 'react-dom';

// In component return:
{showModal && createPortal(
  <div className="modal-overlay">...</div>,
  document.body
)}
```

**Affected components fixed:**
- `LegislativeFileDetail` - uses portal
- `my_tracked_files_tab.tsx` - "Add File" modal uses portal

**Always use `createPortal` for modals in My EU Bubble pages.**

### EPRS Service Architecture (January 2025)

The EPRS (European Parliament Research Service) functionality is now unified under `services/eprs/`:

```
services/eprs/
├── __init__.py
├── eprs_service.py                    # Unified coordinator
└── legislation_in_progress_scraper.py # epthinktank.eu curated list
```

**Related components (pre-existing, now coordinated by EPRSService):**

| Component | Location | Purpose |
|-----------|----------|---------|
| `ThinkTankScraper` | `services/scrapers/` | RSS feeds + PDF extraction |
| `ThinkTankRSSClient` | `services/api_clients/` | RSS feed fetching |
| `EPRSArchiveClient` | `services/api_clients/` | CELLAR SPARQL queries |
| `EPRSIndexer` | `services/indexing/` | ChromaDB vector indexing |
| `EPRSMatcher` | `services/matching/` | Find explainer briefings |

**Always use `EPRSService` (not individual components) for EPRS operations:**

```python
from services.eprs import get_eprs_service

service = get_eprs_service()
explainers = await service.find_explainers(procedure_ref="2021/0106(COD)")
```

### OEIL XML Feed Integration (January 2026)

**Full reference:** See `memory/integrations.md` -> OEIL XML Feed section. Key files: `services/api_clients/oeil_client.py`, `services/scrapers/oeil_sync_service.py`. CLI: `python scripts/sync_oeil_feeds.py --days 7`. API: `POST /api/legislative-train/sync/oeil` (Blue tier).

**OEIL XML feed limit:** The procedures feed has a **30-day server-side limit** (`maxDays=30`). For older procedures, use `OEILClient.lookup_procedure(ref)` or `OEILSyncService.sync_single_procedure(ref)` which scrape individual OEIL pages. API: `POST /api/legislative-train/sync/oeil/lookup?reference=2025/0726(COD)` (Blue tier).

### Data-Driven Chat Follow-Ups (February 2026)

When Brubru Chat matches a legislative file, it enriches the AI context with **structured procedural metadata** scraped from OEIL (Documentation Gateway + procedure page). The AI uses this to craft follow-up questions grounded in real data.

**Available actions detected:** Draft report (PR), MEP amendments (AM), committee report for plenary (RD), committee opinions (AD), committee vote, plenary vote, plenary debate, rapporteur name/group, shadow rapporteurs, upcoming events.

**Key files:**
- `services/ai/context_builder.py` - `_enrich_train_files_with_actions()`, `_extract_actions_from_cached_data()`
- `services/ai_service.py` - System prompt Phase D3: DATA-DRIVEN FOLLOW-UPS
- `services/api_clients/oeil_client.py` - `get_documentation_gateway()`, `lookup_procedure()`

**Caching:** Results cached on `LegislativeCarriage.oeil_procedure_data` (JSON) with 7-day TTL via `enriched_at` field. Max 3 files enriched per request, parallel fetches.

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

SQLAlchemy models have a **built-in `metadata` attribute** that conflicts with custom fields named `metadata`.

**Error symptom:** `'metadata' is a reserved name for declarative_base classes`

**Solution:** Use `doc_metadata` instead of `metadata` for document metadata fields:

```python
# ❌ Wrong - conflicts with SQLAlchemy
class UserDocument(Base):
    metadata = Column(JSONB, nullable=True)

# ✅ Correct - use doc_metadata
class UserDocument(Base):
    doc_metadata = Column(JSONB, nullable=True)
```

**Also update corresponding Pydantic schemas:**
```python
# In schemas
doc_metadata: Optional[Dict[str, Any]] = None
```

**Affected files:**
- `backend/models/user_document.py`
- `backend/schemas/user_document_schemas.py`

### Development Server Ports (January 2025)

**Frontend must always run on port 5173.** Before starting the frontend dev server, kill any process occupying port 5173:

```bash
# Check and kill process on port 5173
lsof -ti:5173 | xargs kill -9 2>/dev/null; cd frontend && npm run dev
```

**Standard ports:**
- Frontend (Vite): `http://localhost:5173`
- Backend (FastAPI): `http://localhost:8000`

If Vite reports "Port 5173 is in use, trying another one...", stop and free the port first.

### Markdown Rendering in React (January 2025)

Use `marked` library: `<div dangerouslySetInnerHTML={{ __html: marked.parse(content) as string }} className="markdown-content" />`. CSS class `.markdown-content` styles headings/lists. Used in `document_generator_wizard.tsx`.

### EUR-Lex Parser: COM Documents vs OJ Documents (January 2025)

`EurlexParser` handles two formats: **OJ** (CELEX starts with `3`, adopted legislation, CSS: `.oj-doc-ti`, `.oj-ti-art`) and **COM** (CELEX starts with `5`, proposals, CSS: `.Titreobjet`, `.ManualConsidrant`). Auto-detects via `_detect_com_document()`. File: `backend/services/parsers/eurlex_parser.py`.

### Legislative Train OEIL Data Quality (January 2025)

**Known Issue:** Some legislative carriages have incorrect or duplicate OEIL procedure references stored in the database. This causes:
1. Wrong "Open in OEIL" links in the Amendator context banner
2. Incorrect file matching when loading from tracked files

**Root cause:** The Legislative Train scraper may store incorrect OEIL refs or create duplicate entries.

**Example:** "Revision of the Tobacco Taxation Directive" has:
- Correct OEIL: `2025/0580(CNS)` (not in database)
- Wrong entry: `2025/0102(COD)` (this is actually Critical Medicines Act)

**To fix:** Run a database cleanup script to:
1. Remove duplicate carriage entries
2. Re-scrape OEIL references from official sources
3. Validate OEIL→title mappings

**Affected file:** `backend/services/scrapers/legislative_train_scraper.py`

### No Emojis - Use MDI Icons (January 2025)

**Never use emojis in the codebase.** Frontend: use MDI icon classes (`mdi-check`, `mdi-close`, `mdi-alert`, `mdi-file-document`, `mdi-magnify`). Backend logging: use text prefixes `[OK]`, `[INFO]`, `[WARN]`, `[ERROR]`, `[START]`/`[STOP]`. The € symbol and accented characters (é, ñ) are NOT emojis.

### Standalone HTML Files Must Follow Brubru Aesthetics (February 2026)

**Every standalone HTML file** (analytics pages, reports, visualisations, landing pages) **MUST** use Brubru's design system. Never use generic system fonts or default colour schemes.

**Mandatory checklist for standalone HTML files:**

| Element | Requirement |
|---------|-------------|
| **Font** | Adobe Caslon Pro via `@font-face` (`.otf` files in `New-Yorker-Font/`) |
| **Colours** | Brubru palette: `#0693e3` (blue), `#059669` (green), `#9b51e0` (purple), `#d97706` (amber), `#dc2626` (red) |
| **Neutrals** | `#111827` (text), `#6b7280` (secondary), `#9ca3af` (muted), `#e5e7eb` (border), `#f3f4f6` (bg-alt), `#ffffff` (bg) |
| **Logo** | Include `brubru_mainlogo.png` in header/hero area |
| **Background** | White (`#ffffff`) -- never dark/black backgrounds |
| **Paths** | Use **relative paths** (`../assets/`, `../New-Yorker-Font/`) so files work both locally and when served |

**Font:** Use `@font-face` with Adobe Caslon Pro (Regular/Semibold/Bold `.otf` from `New-Yorker-Font/`). Use **relative paths** (`../New-Yorker-Font/`, `../assets/`) since files live in `public/analytics/`.

### Header Icon Navigation (January 2025)

Header uses animated MDI icon buttons (icon-only, expand on hover). Nav colours: Main=Blue(`#0693e3`), Bubble=Purple(`#9b51e0`), Amendator=Green(`#059669`), Comply=Silver(`#9ca3af`), Tenderator=Gold(`#d97706`). CSS class: `.header__nav-icon-btn--{color}`. Files: `frontend/src/components/shared/header.tsx`, `header.css`.

### Feature Completion Checklist (January 2026)

**Context:** Committee Work In Progress feature was marked "complete" but didn't work because:
1. Database sync was never run (0 rows)
2. Frontend UI wasn't integrated (hook existed but wasn't used)

**Root cause:** Verified components in isolation without end-to-end testing.

**Mandatory checklist before marking a feature COMPLETE:**

| Step | Verification |
|------|-------------|
| 1. Database | Run migrations AND sync scripts. Verify data exists: `SELECT COUNT(*) FROM table` |
| 2. API | Test endpoint returns data: `curl http://localhost:8000/api/endpoint` |
| 3. Frontend | Build succeeds: `npm run build` |
| 4. UI Integration | Hook is imported AND used in a component (not just created) |
| 5. End-to-end | Manually test the feature in browser or ask user to verify |
| 6. Chatbot context | If integrated with AI, ask a test question and verify context appears |

**Never mark a phase "PARTIAL" and move on.** Either complete it or document what's blocking completion.

### Multi-Provider AI System (January 2026, updated March 2026)

4-tier fallback: Mistral (`mistral-small-latest`) -> Claude (`claude-sonnet-4-20250514`) -> GPT-4 -> Gemini. Key file: `backend/services/ai/multi_provider_service.py`.

**Hybrid routing (March 2026):** Claude Haiku 4.5 is now the de facto primary model. Routing signal: `has_knowledge = internal_knowledge OR eu_institutional_results`. Since EU institutional search (Tavily) fires for all no-guide queries, virtually all queries route to Haiku. Mistral only used when Haiku daily cap ($2.50/day) is reached.

### EU Institutional Source Search Fallback (March 2026)

When no knowledge guide matches a user query, Brubru searches 25 trusted EU domains via Tavily before generating an answer. Results are injected into context with source attribution so the AI cites sources by name.

**Key files:**
- `backend/services/ai/context_builder.py` — `_fetch_eu_institutional_search()`, `EU_INSTITUTIONAL_DOMAINS` (25 domains), `DOMAIN_TO_SOURCE_NAME` (21 mappings)
- `backend/services/ai_service.py` — `has_knowledge` routing includes `eu_institutional_results`, source hierarchy tier 4.5

**Domains searched:** eur-lex.europa.eu, europarl.europa.eu, consilium.europa.eu, ec.europa.eu, commission.europa.eu, cor.europa.eu, eesc.europa.eu, curia.europa.eu, ecb.europa.eu, op.europa.eu, data.europa.eu, eba.europa.eu, esma.europa.eu, eiopa.europa.eu, joint-research-centre.ec.europa.eu, epthinktank.eu, politico.eu, contexte.com, bruegel.org, euractiv.com, euronews.com

**Source attribution rule:** When using EU institutional search results, the AI MUST name the source explicitly: "According to Bruegel...", "Euractiv reports that...", "The European Commission published...". Include the URL.

### EP Plenary Debate Transcripts (CRE) (March 2026)

On-demand fetch of official EP verbatim debate records (CRE XML) from Doceo. No database storage -- fetched live when user asks about a plenary debate.

**Key files:**
- `services/api_clients/cre_client.py` -- CREClient: fetch, parse, search, format
- `services/ai/context_builder.py` -- `_detect_plenary_debate_intent()`, `_fetch_plenary_debate()`, `DEBATE_INTENT_PHRASES`
- `services/ai_service.py` -- CRITICAL system prompt section for debate summary structure

**URL pattern:** `https://www.europarl.europa.eu/doceo/document/CRE-10-{YYYY-MM-DD}_EN.xml`
**Publication delay:** 3-5 days after plenary session.
**Intent triggers:** "plenary debate", "EP debate", "what did MEPs say", "debate on", "who spoke in plenary" (22 phrases, 6 languages).
**Context injection:** Max 4,000 chars per debate. Commission/Council positions first, then by political group (3 speakers per group, 200 chars each).
**Spec:** `docs/maria/ep_cre_transcripts.md` (Phase 1 complete, Phase 2-3 pending).

### Featured Chatbot Questions Source (March 2026)

The 4 featured question cards on the Brubru Chat page come from the **`chat_example_prompts`** table (scope=`'main_chat'`, is_active=`true`, ordered by `sort_order`). They do NOT come from `daily_briefs.suggested_query`.

**API endpoint:** `GET /api/chat/examples?scope=main_chat&limit=4`
**Fallback:** If the API returns no results, the frontend uses i18n keys `chat.example1` through `chat.example4` from `frontend/src/i18n/locales/en.json`.
**Key files:** `backend/api/chat_examples.py`, `frontend/src/components/chat/chat_interface.tsx` (line ~170), `frontend/src/components/chat/daily_brief.tsx`

To update featured questions, insert into `chat_example_prompts` with `scope='main_chat'` and `is_active=true`. Deactivate old ones first.

### EPRS Enrichment: Skip During Morning Routine (March 2026)

`python3.12 scripts/sync_eprs_publications.py --enrich` downloads PDFs and runs CPU-only embedding (BAAI/bge-m3). This takes **15+ minutes** for even a handful of publications. **Do not run `--enrich` during the `/morning` routine.** Run metadata-only sync (`--days 7` without `--enrich`) instead. Schedule `--enrich` overnight or skip entirely.

### Daily Brief BCC Batching (March 2026)

`send_daily_brief_batch()` in `services/daily_brief_email.py` now uses **BCC batching** (90 recipients per SMTP connection) instead of individual sends. This avoids the Gmail rate limit (~80-100 individual sends per session). Greeting is generic ("Good morning") with no personalisation. The `daily_brief_sends` table still tracks per-recipient duplicate prevention.

### RSS AI Enrichment - On-Demand Only (January 2026)

AI enrichment is **on-demand only** (`enable_ai_enrichment=False` by default) to avoid $5/day cost. Trigger via `POST /api/rss/entries/{entry_id}/enrich`. Files: `services/rss/rss_processor.py`, `api/rss_feeds.py`.

### EP Group Position Colours (February 2026)

In the Predictions tab EP Political Group Breakdown, each position type needs a distinct colour:

| Position | Bar Class | Text Class | Colour |
|----------|-----------|------------|--------|
| FOR | `--for` | `--for` | Green (#059669) |
| AGAINST | `--against` | `--against` | Red (#dc2626) |
| ABSTENTION | `--abstention` | `--abstention` | Yellow (#eab308) |
| SPLIT | `--split` | `--split` | Gold (#d97706) |

**Files:**
- `frontend/src/components/bubble/predictions_tab.css` - CSS classes for bar fill and position text

### Resolution Leading Indicators (February 2026)

EP resolutions (INL, INI, RSP) as predictive signals for legislative procedures. Match methods: OEIL_CROSSREF (1.0), COMMISSION_FOLLOWUP (0.9), TITLE_SIMILARITY (0.5-0.8). Key files: `services/matching/resolution_legislation_matcher.py`, `api/predictions.py`, `predictions_tab.tsx`. Docs: `docs/predictions.md` Section 12.9.

### Responsive Design Requirement (February 2026)

**ALL UX/UI changes and implementations MUST be responsive across all screen sizes.** This is a mandatory requirement for every frontend change.

**Standard breakpoints:**

| Breakpoint | Target | CSS |
|------------|--------|-----|
| Desktop | >1024px | Default styles |
| Tablet | 768px - 1024px | `@media (max-width: 1024px)` |
| Mobile | <768px | `@media (max-width: 767px)` |

**Checklist for every UI change:**

1. **Desktop** (>1024px): Full layout with sidebars, multi-column grids
2. **Tablet** (768-1024px): Collapsed sidebars, reduced padding, stacked layouts where needed
3. **Mobile** (<768px): Single column, overlay sidebars with backdrop, touch-friendly targets (min 44px)

**Patterns:**
- Sidebars: Visible on desktop, collapsible on tablet, overlay on mobile
- Grids: Multi-column on desktop, fewer columns on tablet, single column on mobile
- Typography: Use relative units (rem), scale down on smaller screens
- Touch targets: Minimum 44x44px on mobile for all interactive elements
- Modals: Use `createPortal` to escape stacking contexts (see Modal Z-Index rule)

**Never ship a UI change without testing at all three breakpoints.**

### Email Campaign System (February 2026)

**Full reference:** See `memory/email_campaigns.md`. Gmail SMTP (Google Workspace), no third-party dependencies. Gmail limit: ~2,000 recipients/day, 90 per BCC batch. 8 tailored institution templates + 12 multilingual lobby cluster templates. Key files: `services/email_service.py`, `scripts/send_lobby_campaign.py`, `scripts/collect_institution_emails.py`. Data: `data/emails/`. Docs: `docs/email_system_prompt.md`.

### SPA Pre-rendering for AI Crawlers (February 2026)

**Full reference:** See `memory/deployment.md`. Production deploy: `npm run build:prerender`. 9 public routes pre-rendered with Puppeteer. `main.tsx` uses conditional hydration. Add new public routes to `ROUTES` array in `frontend/scripts/prerender.mjs`. AI crawler rules in `frontend/public/robots.txt`.

---

## Strategic North Star: WAPU (Weekly Active Paid Users)

**WAPU = a paid subscriber who performs at least one core action in the past 7 days.**

This is Brubru's primary metric. Not MRR, not subscriber count, not raw active users. WAPU measures the intersection of money AND usage -- the only honest signal of product-market fit.

### Core Actions (any one = active for the week)

| Core Action | Why It Signals Value |
|-------------|---------------------|
| AI chat query | Using the policy advisor -- the primary interface |
| Document generated | A deliverable was produced -- direct labour replacement |
| Legislative file tracked/checked | Monitoring is happening -- daily workflow integration |
| Amendment drafted or MEP amendments analysed | Deep workflow engagement -- not just browsing |
| Compliance report run | High-value, high-switching-cost action |

### The WAPU Test

Every feature, initiative, and sprint item must answer: **"Does this grow WAPU?"** If it doesn't directly increase the number of paid users performing core actions weekly, it is deprioritised.

### WAPU Targets

| Phase | Timeline | WAPU Target | Focus |
|-------|----------|-------------|-------|
| A: Activation | Months 1-3 | **10** | Fix bugs, briefing emails, notifications, dashboards, first 10 outreach |
| B: Depth | Months 4-6 | **25** | Dossier workspaces, amendment analysis, document generator improvements |
| C: Lock-in | Months 7-12 | **50** | Stakeholder CRM, team layer, activity logging + ROI |

### WAPU-Phased Priorities

**Phase A (Activation -- 10 WAPU):** A1 Fix chatbot bugs (DONE), A2 AI briefing emails, A3 Proactive notification engine, A4 Thematic dashboards, A5 Demo/booking flow + first 10 outreach

**Phase B (Depth -- 25 WAPU):** B1 Dossier workspaces, B2 Amendment analysis view, B3 Document generator improvements

**Phase C (Lock-in -- 50 WAPU):** C1 Stakeholder CRM, C2 Team layer, C3 Activity logging + ROI

**Deferred (post-50 WAPU):** MEP social media (P7), Grant proposal AI drafting (P8), National parliaments (P9), LEOS interop (P10)

### Spaak Competitive Posture

Spaak is the #1 direct competitor (VC-backed, 100+ PA teams, Brussels office). Their strength is **distribution** (sales team, events, webinars, content marketing). Brubru's strength is **feature depth** (Amendator, Predictions, EU Law Comply, Tenderator, Document Generator). Strategy: lean into feature depth to make Brubru irreplaceable, not match Spaak's monitoring breadth. Orbit strategy active (CEO connected on LinkedIn).

**Full strategy details:** See `memory/strategy.md` and `docs/business_plan/strategy.html`.

<!-- Example:
- Never use `moment.js` — use `date-fns` instead
- Always run `npm run lint` before committing frontend changes
- The RSS scraper requires a 2-second delay between requests
-->
