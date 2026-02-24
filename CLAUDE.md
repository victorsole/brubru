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

# Seed test users (13 users with Blue/Yellow tiers)
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
│   └── i18n/           # Internationalization (23 EU languages)
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
- **Payments:** Stripe integration for subscriptions
- **i18n:** All frontend text supports 23 EU languages via i18next

## Environment Variables

Required in `.env`:
- `SUPABASE_URL`, `SUPABASE_KEY` - Database/auth
- `ANTHROPIC_API_KEY` - Primary AI
- `OPENAI_API_KEY` - Fallback AI
- `STRIPE_SECRET_KEY` - Payments (optional)

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
- `POST /api/eu-calendar/sync` - Calendar sync from all sources (Blue/Admin)
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

- **Blue tier (5):** Charlotte Berends, Marga Payola, Daniel Roldán, Aleix Sarri, Nick Ligthart
- **Yellow tier (8):** Robin Loos, Joan González, Sergi Duarte, Meritxell Vicheto, Bo, Marc Desmond, Andrés López, Jaume Bernis

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

**Tier Access:**
- White: Locked (upgrade CTA)
- Yellow: 10 predictions/month
- Blue: Unlimited + Council analysis

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

**Tier Access:**
- White: Upgrade CTA (`eu_calendar_cta.tsx`)
- Yellow+: Full read access, all views and filters
- Blue: AI daily summary + sync trigger

**Commission College OJ Scraper Notes:**
- EC Register paginated search returns 503; individual lookup `GET /api/search/OJ(YYYY)NNNN?lang=en` works
- Sequential reference enumeration with 3-second delay, browser-like headers
- Baseline: OJ(2026)2550 = 14 Jan 2026
- Fuzzy date matching (+/-1 day) for Strasbourg Tuesday meetings vs Brussels Wednesday meetings

---

## Learned Rules (Add corrections here)

*When Claude makes a mistake, add a rule below so it never happens again.*

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

### EUR-Lex RSS Feed Integration (January 2026)

**Full reference:** See `memory/integrations.md` -> EUR-Lex RSS section. Key files: `services/api_clients/eurlex_client.py`, `services/scrapers/eurlex_sync_service.py`. CLI: `python scripts/sync_eurlex_feeds.py --days 7`. API: `POST /api/legislative-train/sync/eurlex` (Blue tier).

### EC Register of Commission Documents (February 2026)

**Full reference:** See `memory/integrations.md` -> Commission Documents section. Dual strategy: EUR-Lex RSS for discovery, RegDoc API for enrichment. Paginated search still returns 503. Individual document lookup works (requires browser-like headers). Key files: `services/api_clients/commission_doc_register_client.py`, `api/commission_documents.py`.

### Beresol Knowledge Bundle (January 2026)

**Full reference:** See `memory/integrations.md` -> Beresol section. 11 reports + 7 monitors in `knowledge_base/brubru-knowledge-bundle/`. **Attribution required**: Always cite "Beresol Open Report/Monitor" + `https://beresol.eu/public-affairs`. Key file: `knowledge_base/beresol_knowledge_loader.py`.

### EP Committee Work In Progress (January 2026)

**Full reference:** See `memory/integrations.md` -> Committee Work section. 26 EP committees tracked. CLI: `python scripts/sync_committee_work.py`. API: `GET /api/committee-work/items`, `POST /api/committee-work/sync` (Blue tier). Key files: `services/scrapers/committee_work_scraper.py`, `models/committee_work.py`.

### EC Public Consultations (January 2026)

**Full reference:** See `memory/integrations.md` -> Consultations section. "Have Your Say" portal integration. Yellow/Blue: full access. Blue only: AI proposals. White: CTA. CLI: `python scripts/sync_consultations.py --status open`. API: `GET /api/consultations`, `POST /api/consultations/sync` (Admin). Key files: `services/scrapers/public_consultation_scraper.py`, `api/public_consultations.py`.

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

When displaying AI-generated content that uses Markdown formatting, use the `marked` library to render it as HTML.

**Pattern:**
```tsx
import { marked } from 'marked';

// Render Markdown content
<div
  className="markdown-content"
  dangerouslySetInnerHTML={{ __html: marked.parse(content) as string }}
/>
```

**CSS for Markdown content:**
```css
.markdown-content h1 { font-size: 1.5rem; border-bottom: 2px solid #0066cc; }
.markdown-content h2 { font-size: 1.25rem; margin: 1.5rem 0 0.75rem 0; }
.markdown-content p { margin: 0 0 1rem 0; line-height: 1.7; }
.markdown-content ul, .markdown-content ol { padding-left: 1.5rem; }
.markdown-content li { margin-bottom: 0.5rem; }
```

**Used in:**
- `frontend/src/components/bubble/document_generator_wizard.tsx`

### EUR-Lex Parser: COM Documents vs OJ Documents (January 2025)

The `EurlexParser` now handles **two distinct document formats**:

| Format | CELEX Pattern | Document Type | Example |
|--------|---------------|---------------|---------|
| **OJ (Official Journal)** | Starts with `3` | Adopted legislation | `32024R1689` (AI Act) |
| **COM (Commission)** | Starts with `5` | Legislative proposals | `52021PC0206` (AI Act proposal) |

**Why this matters:** The Legislative Train tracks **proposals** (COM documents), not adopted laws. The parser auto-detects the format and uses appropriate extraction methods.

**CSS classes by format:**

| Element | OJ Format | COM Format |
|---------|-----------|------------|
| Recitals | `div.eli-subdivision[id^="rct_"]` | `p.ManualConsidrant` |
| Articles | `p.oj-ti-art` | `p.ManualHeading1/2/3` or actual "Article X" |
| Title | `.oj-doc-ti` | `.Titreobjet`, `.Titreobjet_cp` |

**Detection logic** (`_detect_com_document()`):
```python
# COM documents have specific CSS classes
com_indicators = [
    soup.select_one('.ManualConsidrant'),
    soup.select_one('.ManualHeading1'),
    soup.select_one('.Typedudocument'),
]
# Also checks for "COM(2021) 206" pattern in text
```

**File:** `backend/services/parsers/eurlex_parser.py`

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

**Never use emojis in the codebase.** Use Material Design Icons (MDI) instead.

**Why:** Emojis render inconsistently across platforms and don't match the professional UI aesthetic.

**Frontend - Use MDI icon classes:**
```tsx
// Bad - emoji
<span>📄 Document</span>
<li>✓ Feature included</li>

// Good - MDI icons
<span className="mdi mdi-file-document"></span> Document
<li><span className="mdi mdi-check"></span> Feature included</li>
```

**Common MDI replacements:**
| Emoji | MDI Class | Usage |
|-------|-----------|-------|
| ✓ ✅ | `mdi-check` | Success, included |
| ✗ ❌ | `mdi-close` | Error, excluded |
| ⚠️ | `mdi-alert` | Warning |
| 📄 | `mdi-file-document` | Document |
| 📎 | `mdi-paperclip` | Attachment |
| 🔍 | `mdi-magnify` | Search |
| ▶ | `mdi-chevron-right` | Expand/navigate |
| 🤍 💛 💙 | `mdi-heart-outline` / `mdi-heart` | Tier badges (with CSS color) |

**Backend console logging - Use text prefixes:**
```python
# Bad - emoji
print("🚀 Starting server...")
print("✅ Database connected")

# Good - text prefix
print("[START] Starting server...")
print("[OK] Database connected")
```

**Standard logging prefixes:**
- `[OK]` - Success
- `[INFO]` - Information
- `[WARN]` - Warning
- `[ERROR]` - Error
- `[START]` / `[STOP]` - Lifecycle events

**Note:** The € symbol and accented characters (é, ñ, etc.) are NOT emojis and should be used as-is.

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

**Font declaration template (copy into every standalone HTML):**

```html
<style>
@font-face {
  font-family: 'Adobe Caslon Pro';
  src: url('../New-Yorker-Font/ACaslonPro-Regular.otf') format('opentype');
  font-weight: 400; font-style: normal; font-display: swap;
}
@font-face {
  font-family: 'Adobe Caslon Pro';
  src: url('../New-Yorker-Font/ACaslonPro-Semibold.otf') format('opentype');
  font-weight: 600; font-style: normal; font-display: swap;
}
@font-face {
  font-family: 'Adobe Caslon Pro';
  src: url('../New-Yorker-Font/ACaslonPro-Bold.otf') format('opentype');
  font-weight: 700; font-style: normal; font-display: swap;
}
body {
  font-family: 'Adobe Caslon Pro', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, serif;
}
</style>
```

**Why relative paths:** Absolute paths (`/assets/...`) only work when served by the web server. Relative paths (`../assets/...`) work both when opened locally as a file AND when served. Since standalone HTML files live in `public/analytics/`, use `../` to reach `public/assets/` and `public/New-Yorker-Font/`.

### Header Icon Navigation (January 2025)

The header navigation uses **animated icon buttons** instead of text links. Each button displays only an icon by default, expands to show a label on hover, and maintains its accent color when active.

**Navigation items and colours:**

| Route | Icon | Colour | Label |
|-------|------|--------|-------|
| `/main` | `mdiChatProcessingOutline` | Blue (`#0693e3`) | Main |
| `/my-eu-bubble` | `mdiGlassMugVariant` | Purple (`#9b51e0`) | My EU Bubble |
| `/amendator` | `mdiFileEditOutline` | Green (`#059669`) | Amendator |
| `/eulawcomply` | `mdiScaleBalance` | Silver (`#9ca3af`) | EU Law Comply |
| `/tenderator` | `mdiPiggyBankOutline` | Gold (`#d97706`) | Tenderator (Blue tier only) |

**CSS pattern:**
```css
/* Base icon button */
.header__nav-icon-btn {
  width: 40px;
  height: 40px;
  border-radius: 20px;
  overflow: hidden;
}

/* Hover: expand and show label */
.header__nav-icon-btn:hover {
  width: auto;
  gap: 8px;
}

/* Colour variants */
.header__nav-icon-btn--blue.header__nav-icon-btn--active {
  color: var(--nav-color-main);
}
```

**React pattern:**
```tsx
import Icon from '@mdi/react';
import { mdiChatProcessingOutline } from '@mdi/js';

const navItems = [
  { path: '/main', icon: mdiChatProcessingOutline, labelKey: 'header.main', color: 'blue' },
  // ...
];

{navItems.map((item) => (
  <Link
    to={item.path}
    className={`header__nav-icon-btn header__nav-icon-btn--${item.color}${active ? ' header__nav-icon-btn--active' : ''}`}
    aria-label={t(item.labelKey)}
  >
    <Icon path={item.icon} size={1} />
    <span className="header__nav-icon-label">{t(item.labelKey)}</span>
  </Link>
))}
```

**Files:**
- `frontend/src/components/shared/header.tsx`
- `frontend/src/components/shared/header.css`

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

### Multi-Provider AI System (January 2026)

Brubru uses a **4-tier AI provider fallback chain** for cost-effectiveness and resilience:

| Priority | Provider | Model | Cost (per 1M tokens) | Use Case |
|----------|----------|-------|---------------------|----------|
| 1 (Primary) | **Mistral** | `mistral-small-latest` | $0.20 input / $0.60 output | Default for all requests |
| 2 (Fallback) | Anthropic | `claude-sonnet-4-20250514` | $3.00 input / $15.00 output | Complex reasoning |
| 3 (Fallback) | OpenAI | `gpt-4-turbo-preview` | $10.00 input / $30.00 output | If Claude fails |
| 4 (Fallback) | Google | `gemini-1.5-pro` | $1.25 input / $5.00 output | Last resort |

**Why Mistral is primary:** 15x cheaper than Claude with comparable quality for EU policy questions.

**Environment Variables:**
```env
MISTRAL_API_KEY=xxx      # Get from console.mistral.ai
ANTHROPIC_API_KEY=xxx    # Fallback 1
OPENAI_API_KEY=xxx       # Fallback 2
GOOGLE_GEMINI_API_KEY=xxx  # Fallback 3 (optional)
```

**Key Files:**
- `backend/services/ai/multi_provider_service.py` - Provider abstraction + fallback chain
- `backend/core/config.py` - API key configuration

**Testing the provider chain:**
```python
from services.ai.multi_provider_service import get_multi_provider_service

service = get_multi_provider_service()
print(service.available_providers)  # ['Mistral', 'Anthropic', 'OpenAI', 'Gemini']
print(service.primary_provider)     # 'Mistral'
```

### RSS AI Enrichment - On-Demand Only (January 2026)

**Problem:** Automatic AI enrichment of RSS entries was costing ~$5/day by calling Claude for every entry.

**Solution:** AI enrichment is now **on-demand only**. The `RSSProcessor` defaults to `enable_ai_enrichment=False`.

**How to trigger enrichment:**
```bash
# API endpoint for on-demand enrichment
POST /api/rss/entries/{entry_id}/enrich
```

**What gets enriched:**
- Policy area classification
- Entity extraction (people, organizations, places)
- CELEX number detection (regex - no AI cost)
- Procedure reference detection (regex - no AI cost)
- Sentiment analysis

**Files changed:**
- `backend/services/rss/rss_processor.py` - Default changed to `enable_ai_enrichment=False`
- `backend/api/rss_feeds.py` - Added `/entries/{entry_id}/enrich` endpoint

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

### Resolution Leading Indicators Implementation (February 2026)

Resolution Leading Indicators show EP resolutions (INL, INI, RSP) that preceded legislative procedures as predictive signals.

**Backend:**
- `services/matching/resolution_legislation_matcher.py` - Added `find_resolutions_for_legislation()` and `find_related_resolutions_by_similarity()` functions
- `api/predictions.py` - Added `GET /api/predictions/resolutions/{procedure_ref:path}` endpoint

**Frontend:**
- `services/prediction_service.ts` - Added `ResolutionIndicator` types and `getResolutionLeadingIndicators()` function
- `components/bubble/predictions_tab.tsx` - Added `ResolutionIndicatorRow` component
- `components/bubble/predictions_tab.css` - Added 200+ lines of resolution styling

**Match Methods (confidence):**
- `OEIL_CROSSREF` (1.0) - Explicit OEIL link
- `COMMISSION_FOLLOWUP` (0.9) - Commission follow-up document
- `TITLE_SIMILARITY` (0.5-0.8) - Title word overlap

**Documentation:** `docs/predictions.md` Section 12.9

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

<!-- Example:
- Never use `moment.js` — use `date-fns` instead
- Always run `npm run lint` before committing frontend changes
- The RSS scraper requires a 2-second delay between requests
-->
