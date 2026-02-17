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
6. **Admin Panel** - User/subscription management (restricted)

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
- API docs at `/docs` (Swagger UI)

## Database

PostgreSQL via Supabase. Key tables:
- `users` - User profiles
- `chat_conversations` / `chat_messages` - Chat history
- `amendments` - Legislative amendments
- `eu_laws` - Cached EU legislation
- `rss_feeds` / `rss_entries` - RSS data

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

OEIL provides XML export feeds for automatic procedure syncing. These were discovered in January 2026 and are now integrated into the OEIL client.

**XML Feed Endpoints:**

| Feed | URL | Content |
|------|-----|---------|
| Latest Procedures | `/en/predefined-search/latest-procedures/export/XML?maxDays=7` | COD, INI, RSP, DEA, IMM, BUD procedures |
| Latest Documents | `/en/predefined-search/latest-information-documents/export/XML?maxCount=50&maxDays=7` | COM, SWD documents |
| Latest Reports | `/en/predefined-search/latest-committees-reports-tabled/export/XML?maxDays=30` | Committee reports |

**Using the OEIL Client:**

```python
from services.api_clients.oeil_client import OEILClient

client = OEILClient()

# Get latest legislative procedures
procedures = await client.get_latest_procedures_xml(max_days=7)
for proc in procedures:
    print(f"{proc.reference}: {proc.title}")
    print(f"  Type: {proc.procedure_type}, Committee: {proc.committees}")

# Get all feeds at once
feeds = await client.get_all_latest_xml()
```

**Automatic Sync Service:**

```python
from services.scrapers.oeil_sync_service import OEILSyncService

# Sync new procedures to database
service = OEILSyncService()
result = await service.sync_all(procedures_days=7, skip_existing=True)
print(f"Added: {result['added']}, Skipped: {result['skipped']}")
```

**API Endpoint:**

```bash
# Sync via API (Blue tier required)
POST /api/legislative-train/sync/oeil?days=7&force=false
```

**Manual Sync Script:**

```bash
# Run from backend directory
python scripts/sync_oeil_feeds.py --days 7
python scripts/sync_oeil_feeds.py --days 7 --force  # Update existing
```

**Files:**
- `services/api_clients/oeil_client.py` - XML feed fetching and parsing
- `services/scrapers/oeil_sync_service.py` - Database sync logic
- `scripts/sync_oeil_feeds.py` - CLI sync script
- `api/legislative_train.py` - API endpoint

### EUR-Lex RSS Feed Integration (January 2026)

EUR-Lex provides predefined RSS feeds for monitoring EU legislation. These are now integrated into the EUR-Lex client for automatic legislation tracking.

**Predefined RSS Feeds:**

| Feed | RSS ID | Content |
|------|--------|---------|
| Parliament & Council Legislation | `162` | Adopted regulations, directives, decisions |
| Commission Proposals | `161` | COM documents and legislative proposals |
| Official Journal L | `222` | Official Journal L series (legislation) |
| Official Journal C | `221` | Official Journal C series (information) |
| Court Case Law | `163` | All CJEU case law |
| ECJ Case Law | `164` | European Court of Justice only |

**URL Pattern:** `https://eur-lex.europa.eu/EN/display-feed.rss?rssId={ID}`

**Using the EUR-Lex Client:**

```python
from services.api_clients.eurlex_client import EURLexClient

client = EURLexClient()

# Get latest legislation with CELEX numbers
legislation = await client.get_latest_legislation(days=7)
for item in legislation:
    print(f"{item['celex']}: {item['title']}")
    print(f"  Type: {item['doc_type']}")

# Get Commission proposals
proposals = await client.get_latest_commission_proposals(days=7)

# Get all predefined feeds
feeds = await client.get_all_predefined_feeds()
```

**Automatic Sync Service:**

```python
from services.scrapers.eurlex_sync_service import EURLexSyncService

# Sync new legislation to database
service = EURLexSyncService()
result = await service.sync_all(legislation_days=7, proposals_days=7)
print(f"Added: {result['added']}, Skipped: {result['skipped']}")
```

**API Endpoint:**

```bash
# Sync via API (Blue tier required)
POST /api/legislative-train/sync/eurlex?days=7&force=false
```

**Manual Sync Script:**

```bash
# Run from backend directory
python scripts/sync_eurlex_feeds.py --days 7
python scripts/sync_eurlex_feeds.py --days 7 --force  # Update existing
```

**Files:**
- `services/api_clients/eurlex_client.py` - RSS feed fetching and CELEX parsing
- `services/scrapers/eurlex_sync_service.py` - Database sync logic
- `scripts/sync_eurlex_feeds.py` - CLI sync script
- `api/legislative_train.py` - API endpoint

### EC Register of Commission Documents Integration (February 2026)

The EC Register of Commission Documents API (`ec.europa.eu/transparency/documents-register/api/`) is partially back online. Brubru uses a **dual strategy**: EUR-Lex RSS + CELLAR SPARQL for **discovery** (finding new documents), and the live RegDoc API for **enrichment** (filling in titles, DGs, languages).

**API Status (February 2026):**

| Endpoint | Status | Returns |
|----------|--------|---------|
| `GET /search/{reference}?lang=en` | Works | Full document detail (titles in 24 EU languages, DG, attachments) |
| `GET /search/{reference}/related?lang=en` | Works | Related documents (e.g. SWD accompanying a COM) |
| `GET /search/{reference}/correctedBy` | Works | Corrections to a document |
| `GET /topDocuments/{category}` | Works | Homepage widget (3 items, not paginated) |
| `GET /maintenance` | Works | Returns `null` when no maintenance |
| `GET /search?category=COM&...` (paginated) | 503 | General search still down |

**Critical: Browser-like headers required:**
```python
headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) ...",
    "Referer": "https://ec.europa.eu/transparency/documents-register/",
}
```
Without these headers, the API returns 503.

**API Response Structure:**
- Title is inside `attachments[0].linguisticVersions.{lang}.title` (top-level `title` is always `null`)
- `responsibleDepartment` maps to DG code (e.g. "CNECT", "GROW")
- `category` maps to doc type (COM, SWD, SEC, C, JOIN, OJ, PV)

**Reference Format Conversion (CELEX to API):**

| DB Format (CELEX) | API Format | Conversion |
|-------------------|------------|------------|
| `52026PC0090` | `COM(2026)90` | Strip `5`, `PC`, leading zeros |
| `52025SC0420` | `SWD(2025)420` | Strip `5`, `SC`, leading zeros |
| `SWD(2026) 65` | `SWD(2026)65` | Strip internal spaces |
| `32024R1689` | N/A | OJ docs not in RegDoc register |

**Using the Commission Document Client:**

```python
from services.api_clients.commission_doc_register_client import get_commission_doc_register_client

client = get_commission_doc_register_client()

# Fetch individual document by reference
doc = await client.fetch_document_by_reference("SWD(2025)420")
print(f"Title: {doc.title}")
print(f"DG: {doc.dg_responsible}")
print(f"Languages: {doc.languages}")

# Fetch related documents
related = await client.fetch_related_documents("COM(2025)100")
```

**Sync & Enrichment Services:**

```python
from services.scrapers.commission_doc_sync_service import CommissionDocSyncService

service = CommissionDocSyncService()

# Sync new documents from EUR-Lex RSS + SPARQL
result = await service.sync_all(days=7)
print(f"Added: {result['added']}, Skipped: {result['skipped']}")

# Enrich existing documents from RegDoc API
result = await service.enrich_documents(limit=50)
print(f"Enriched: {result['enriched']}, Skipped: {result['skipped']}")
```

**API Endpoints:**

```bash
# List Commission documents with filters
GET /api/commission-documents/items?doc_type=COM&dg=GROW&search=AI

# Get document detail
GET /api/commission-documents/items/{id}

# Track/untrack a document
POST /api/commission-documents/track/{id}
DELETE /api/commission-documents/track/{id}

# Get tracked documents
GET /api/commission-documents/tracked

# Trigger sync (Blue tier required)
POST /api/commission-documents/sync?days=7&force=false

# Trigger enrichment from RegDoc API (Blue tier required)
POST /api/commission-documents/enrich?limit=50
```

**Files:**
- `services/api_clients/commission_doc_register_client.py` - RegDoc API client (live API + EUR-Lex fallback)
- `services/scrapers/commission_doc_sync_service.py` - Sync + enrichment orchestrator
- `models/commission_document.py` - SQLAlchemy models (CommissionDocument, UserCommissionDocTrack)
- `schemas/commission_document_schemas.py` - API Pydantic schemas
- `schemas/scrapers/commission_doc_register_schemas.py` - Scraper schemas (CommissionDocItem, CommissionDocType)
- `api/commission_documents.py` - API endpoints

### Beresol Knowledge Bundle Integration (January 2026)

Beresol (Brubru's company) publishes open reports and monitors on EU policy topics. These are now integrated into the Main chatbot context.

**Content Location:** `backend/knowledge_base/brubru-knowledge-bundle/`

**Content Types:**

| Type | Description | Location |
|------|-------------|----------|
| **Reports** | In-depth analysis on EU policy topics (markdown) | `reports/*.md` |
| **Monitors** | Live dashboards tracking EU policy areas (React components) | `monitors/` |

**Available Reports (11 topics):**
- AI Act Implementation
- CBAM (Carbon Border Adjustment)
- EU-Mercosur Agreement
- Iberian Blackout (Critical Infrastructure)
- Ukraine EU Path
- EU Recovery and Resilience Facility
- Mediterranean Fisheries
- EU Agri-Food Days 2025
- Anti-Coercion Instrument (ACI)
- Letta-Draghi-Niinisto Strategic Reports
- Catalan Railway Crisis (in Catalan)

**Available Monitors (7 dashboards):**
- EU Defence Monitor
- Capital Markets Union (CMU)
- Tariff & Trade War Monitor
- AI Market Monitor
- EU Quantum Monitor
- EU Startup Monitor
- Gold Trading Monitor

**Attribution Requirements:**

When referencing Beresol content in AI responses, ALWAYS mention:
- Source: "Beresol Open Report" or "Beresol Monitor"
- Publisher: "Beresol, Brubru's company"
- Link: `https://beresol.eu/public-affairs`

**Usage in Context Builder:**

```python
from knowledge_base.beresol_knowledge_loader import get_beresol_knowledge_loader

loader = get_beresol_knowledge_loader()

# Search reports
results = loader.search_reports("AI Act")

# Get relevant content for AI context
content = loader.get_relevant_content_for_query(
    query="What are the CBAM compliance requirements?",
    max_reports=2,
    max_content_length=3000
)
```

**Files:**
- `knowledge_base/beresol_knowledge_loader.py` - Loader service
- `knowledge_base/brubru-knowledge-bundle/reports/` - Markdown reports
- `knowledge_base/brubru-knowledge-bundle/monitors/` - Monitor components
- `services/ai/context_builder.py` - Integration with chatbot context

### EP Committee Work In Progress Integration (January 2026)

All 26 EP committees have "Work in Progress" pages showing legislative procedures in progress. This is now integrated into Brubru for tracking and chatbot context.

**26 EP Committees:**

| Code | Name | Policy Area |
|------|------|-------------|
| AFET | Foreign Affairs | External relations |
| DROI | Human Rights | External relations |
| SEDE | Security and Defence | External relations |
| DEVE | Development | External relations |
| INTA | International Trade | External relations |
| BUDG | Budgets | Economic/Financial |
| CONT | Budgetary Control | Economic/Financial |
| ECON | Economic and Monetary Affairs | Economic/Financial |
| FISC | Tax Matters | Economic/Financial |
| EMPL | Employment and Social Affairs | Social |
| ENVI | Environment, Public Health and Food Safety | Environment/Health |
| SANT | Public Health | Environment/Health |
| ITRE | Industry, Research and Energy | Industry/Tech |
| IMCO | Internal Market and Consumer Protection | Internal Market |
| TRAN | Transport and Tourism | Infrastructure |
| REGI | Regional Development | Cohesion |
| AGRI | Agriculture and Rural Development | Agriculture |
| PECH | Fisheries | Agriculture |
| CULT | Culture and Education | Culture/Education |
| JURI | Legal Affairs | Legal/Institutional |
| LIBE | Civil Liberties, Justice and Home Affairs | Justice/Home Affairs |
| AFCO | Constitutional Affairs | Legal/Institutional |
| FEMM | Women's Rights and Gender Equality | Social |
| PETI | Petitions | Citizens |
| EUDS | EU-US Relations | External relations |
| HOUS | Housing and Urban Development | Social |

**Procedure Type Relevance Scores:**

| Type | Score | Description |
|------|-------|-------------|
| COD | 100 | Ordinary legislative procedure (codecision) |
| APP | 80 | Consent procedure |
| CNS | 70 | Consultation procedure |
| NLE | 50 | Non-legislative procedure |
| INI | 40 | Own-initiative report |

**Using the Committee Work Scraper:**

```python
from services.scrapers.committee_work_scraper import CommitteeWorkInProgressScraper

scraper = CommitteeWorkInProgressScraper()

# Scrape single committee
items = await scraper.scrape_committee("AFET", max_pages=5)
for item in items:
    print(f"{item.procedure_ref}: {item.title}")
    print(f"  Type: {item.procedure_type}, Status: {item.status}")

# Scrape all committees
all_items = await scraper.scrape_all_committees(max_pages_per_committee=3)
```

**Sync Service:**

```python
from services.scrapers.committee_work_sync_service import CommitteeWorkSyncService

service = CommitteeWorkSyncService()
result = await service.sync_all(max_pages_per_committee=5)
print(f"Added: {result['added']}, Updated: {result['updated']}")
```

**CLI Sync Script:**

```bash
# Sync all committees
python scripts/sync_committee_work.py

# Sync specific committees
python scripts/sync_committee_work.py --committees AFET LIBE ECON

# List available committees
python scripts/sync_committee_work.py --list-committees

# Dry run (test without database)
python scripts/sync_committee_work.py --dry-run
```

**API Endpoints:**

```bash
# List work items with filters
GET /api/committee-work/items?committee_code=AFET&procedure_type=COD

# Get item details
GET /api/committee-work/items/{id}

# Track a work item
POST /api/committee-work/track/{id}

# Untrack
DELETE /api/committee-work/track/{id}

# Get tracked items
GET /api/committee-work/tracked

# Trigger sync (Blue tier required)
POST /api/committee-work/sync?committees=AFET,LIBE&max_pages=5
```

**Files:**
- `knowledge_base/ep_committees.py` - Committee definitions
- `schemas/scrapers/committee_work_schemas.py` - Pydantic schemas
- `services/scrapers/committee_work_scraper.py` - Main scraper
- `services/scrapers/committee_work_sync_service.py` - Sync orchestrator
- `models/committee_work.py` - SQLAlchemy models
- `api/committee_work.py` - API endpoints
- `schemas/committee_work_schemas.py` - API schemas
- `scripts/sync_committee_work.py` - CLI script
- `migrations/012_add_committee_work_tables.sql` - Database migration
- `services/ai/context_builder.py` - Chatbot context integration
- `frontend/src/hooks/use_committee_work.ts` - Zustand state management
- `frontend/src/components/bubble/my_tracked_files_tab.tsx` - UI integration (Committee Work tab)

### EC Public Consultations Integration (January 2026)

The European Commission's "Have Your Say" portal consultations are now integrated into Brubru. Users can discover, track, and participate in EU policy-making.

**Access Control:**
- Yellow/Blue tiers: Full access to consultations, tracking, notifications
- Blue tier only: AI-powered proposal generation, alignment assessment
- White tier: CTA invitation to upgrade

**Consultation Types:**

| Type | Description |
|------|-------------|
| public_consultation | Standard public consultation |
| roadmap | Policy roadmap feedback |
| initiative | Citizens' initiative |
| feedback | Feedback on adopted acts |

**Consultation Statuses:**

| Status | Description |
|--------|-------------|
| open | Currently accepting responses |
| closed | Deadline passed |
| outcome_published | Results published |

**Using the Public Consultation Scraper:**

```python
from services.scrapers.public_consultation_scraper import PublicConsultationScraper

scraper = PublicConsultationScraper()

# Get open consultations
items = await scraper.get_open_consultations(limit=20)
for item in items:
    print(f"{item.title}")
    print(f"  DG: {item.dg_responsible}, Deadline: {item.end_date}")

# Get consultations by policy area
items = await scraper.get_consultations_by_policy_area("CLIMA", limit=10)
```

**Sync Service:**

```python
from services.scrapers.consultation_sync_service import ConsultationSyncService

service = ConsultationSyncService()
result = await service.sync_all(max_pages=10)
print(f"Added: {result['added']}, Updated: {result['updated']}")
```

**CLI Sync Script:**

```bash
# Sync open consultations
python scripts/sync_consultations.py --status open

# Sync with page limit
python scripts/sync_consultations.py --status open --max-pages 5

# Dry run
python scripts/sync_consultations.py --dry-run
```

**API Endpoints:**

```bash
# List consultations with filters
GET /api/consultations?status=open&dg=GROW&limit=20

# Get consultation details
GET /api/consultations/{id}

# Track a consultation
POST /api/consultations/{id}/track

# Untrack
DELETE /api/consultations/{id}/track

# Get tracked consultations
GET /api/consultations/tracked

# Get reference data (DGs, policy areas)
GET /api/consultations/dgs
GET /api/consultations/policy-areas

# Trigger sync (Admin only)
POST /api/consultations/sync?status=open&max_pages=5
```

**Files:**
- `knowledge_base/ec_consultations.py` - Constants (types, statuses, DGs, policy areas)
- `schemas/scrapers/public_consultation_schemas.py` - Scraper Pydantic schemas
- `services/api_clients/have_your_say_client.py` - HTTP client for EC portal
- `services/scrapers/public_consultation_scraper.py` - Main scraper
- `services/scrapers/consultation_sync_service.py` - Sync orchestrator
- `models/public_consultation.py` - SQLAlchemy models
- `api/public_consultations.py` - API endpoints
- `schemas/public_consultation_schemas.py` - API schemas
- `scripts/sync_consultations.py` - CLI script
- `migrations/013_add_public_consultations_tables.sql` - Database migration
- `services/ai/context_builder.py` - Chatbot context integration
- `frontend/src/hooks/use_consultations.ts` - Zustand state management
- `frontend/src/services/consultation_service.ts` - API client
- `frontend/src/components/bubble/ec_consultations_tab.tsx` - Main tab component
- `frontend/src/components/bubble/consultation_detail.tsx` - Detail modal
- `frontend/src/components/bubble/consultations_cta.tsx` - White tier CTA

**Frontend Integration:**

The EC Consultations tab appears in My EU Bubble after "My Files". It uses:
- Icon: `mdiCalendarCollapseHorizontal`
- Colour: `#f97316` (orange)
- Portal rendering for modals (escape z-index stacking context)

**Chatbot Context:**

Public consultations are included in chatbot context (Tier 3 - official EC source). The context builder:
- Searches for DG codes mentioned in queries
- Searches for policy area keywords
- Prioritises open consultations with upcoming deadlines
- Shows deadline warnings (closing soon, days remaining)

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

Brubru has a complete email campaign infrastructure for outreach to EU institutions and lobby organisations. Uses Gmail SMTP (Google Workspace) with no third-party email dependencies.

**Architecture:**

| Component | File | Purpose |
|-----------|------|---------|
| EmailService | `services/email_service.py` | Singleton SMTP sender (transactional + bulk) |
| Institution Campaign | `scripts/collect_institution_emails.py` | PDF parsing + tailored institution emails |
| Lobby Campaign | `scripts/send_lobby_campaign.py` | Multilingual lobby org emails by cluster + country |
| Bounce Cleaner | `scripts/clean_bounced_emails.py` | IMAP bounce detection + CSV cleanup |
| Lobby Collector | `scripts/collect_lobby_orgs.py` | Transparency Register scraping + LobbyFacts data |
| Email Discoverer | `scripts/collect_lobby_emails.py` | DNS MX record checking for contact emails |

**SMTP Configuration (`.env`):**

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=hello@beresol.eu
SMTP_PASSWORD=xxxx xxxx xxxx xxxx   # Google Workspace App Password
SMTP_FROM_NAME=Brubru by Beresol
```

**Gmail Limits:**
- Google Workspace: ~2,000 recipients/day
- Max per message: 100 recipients (we use 90 for safety)
- Error when exceeded: `550 5.4.5 Daily user sending limit exceeded`
- Limit resets ~24 hours after hitting it

**BCC Batch Sending Pattern:**
```python
from scripts.collect_institution_emails import send_bcc_campaign

result = send_bcc_campaign(
    recipients=email_list,
    subject="Subject line",
    html_body=html_content,
    dry_run=False,  # True for preview
)
```

**Institution Email Templates (8 tailored + 1 generic):**

| Key | Institution | Subject Angle |
|-----|-------------|---------------|
| `eeas` | External Action Service | Sanctions, CFSP/CSDP, trade agreements |
| `agencies` | EU Agencies (EMA, etc.) | Legislative context behind agency mandates |
| `eib` | European Investment Bank | InvestEU, REPowerEU, Green Bond Standard |
| `ecb` | European Central Bank | MiCA, PSD3, AML, Banking Union |
| `eca` | Court of Auditors | MFF, RRF, CAP spending, BUDG/CONT |
| `eesc` | Economic & Social Committee | Legislative proposals, opinion drafting |
| `omb` | Ombudsman | Transparency, access to documents, AFCO/LIBE |
| `cor` | Committee of the Regions | Cohesion policy, ERDF, ESF+, REGI |
| `generic` | Fallback (COM, CONSIL) | General EU policy features |

**Lobby Campaign - Multilingual Templates:**

12 policy clusters with keywords in 6 languages (en/fr/es/it/nl/de):
`digital`, `climate`, `finance`, `trade`, `agriculture`, `health`, `energy`, `transport`, `defence`, `social`, `research`, `civil_society`

6 priority countries with language mapping:
- Spain -> `es`, Italy -> `it`, France/Belgium/Luxembourg -> `fr`, Netherlands -> `nl`

**Campaign Commands:**

```bash
# Institution campaigns
python3.12 scripts/collect_institution_emails.py --send --institution eeas
# Or from pre-existing CSV:
python3.12 -c "from scripts.collect_institution_emails import send_from_csv; send_from_csv('eeas', dry_run=False)"

# Lobby campaigns
python3.12 scripts/send_lobby_campaign.py --classify-only                    # Preview classification
python3.12 scripts/send_lobby_campaign.py --classify-only --country spain    # Filter by country
python3.12 scripts/send_lobby_campaign.py --test-templates --lang es         # Test Spanish templates
python3.12 scripts/send_lobby_campaign.py --dry-run --country spain          # Preview send
python3.12 scripts/send_lobby_campaign.py --send --country spain --cluster climate  # Send

# Bounce cleaning (run before each send)
python3.12 scripts/clean_bounced_emails.py --days 7           # Preview bounces
python3.12 scripts/clean_bounced_emails.py --days 7 --apply   # Remove from CSVs
```

**Data Files (`data/emails/`):**

| File | Rows | Source |
|------|------|--------|
| `lobby_org_ids.json` | 16,738 IDs | EU Transparency Register |
| `lobby_orgs_raw.csv` | 16,731 | LobbyFacts CSV export |
| `lobby_orgs_emails.csv` | 4,053 | MX-verified contact emails |
| `mep_emails.csv` | 667 | EU Who is Who PDF |
| `com_emails.csv` | 1,725 | EU Who is Who PDF |
| `consil_emails.csv` | 226 | EU Who is Who PDF |
| `eeas_emails.csv` | 283 | EU Who is Who PDF |
| `agencies_emails.csv` | 229 | EU Who is Who PDF |
| `eib_emails.csv` | 258 | EU Who is Who PDF |
| `ecb_emails.csv` | 161 | EU Who is Who PDF |
| `eca_emails.csv` | 153 | EU Who is Who PDF |
| `eesc_emails.csv` | 107 | EU Who is Who PDF |
| `omb_emails.csv` | 42 | EU Who is Who PDF |
| `cor_emails.csv` | 16 | EU Who is Who PDF |

**Campaign Sending History (February 2026):**

| Date | Target | Sent | Status |
|------|--------|------|--------|
| 11 Feb | MEPs | 682 | Complete |
| 11-12 Feb | Commission | 1,725 | Complete |
| 12 Feb | Council | 226 | Complete |
| 13 Feb | EEAS + Agencies + EIB + ECB + ECA + EESC + Ombudsman + CoR | 1,249 | Scheduled |
| 16 Feb | Lobby: Spain (es) + Italy (it) | 531 | Scheduled |
| 17 Feb | Lobby: FR+BE+LU (fr) top 4 clusters | 461 | Scheduled |
| 18 Feb | Lobby: FR+BE+LU (fr) remaining + Netherlands (nl) | 522 | Scheduled |

**Excluded from campaigns:** CURIA (Court of Justice), EDPS (Data Protection Supervisor)

**Documentation:** Full reusable setup guide at `docs/email_system_prompt.md`

### SPA Pre-rendering for AI Crawlers (February 2026)

Brubru is a React SPA. AI crawlers (ChatGPT, Perplexity, Claude) don't execute JavaScript, so they see an empty `<div id="root"></div>`. Pre-rendering solves this by generating static HTML for public routes at build time.

**Build commands:**

```bash
cd frontend

# Normal SPA build (no pre-rendering)
npm run build

# Build + pre-render public pages (use for production deploys)
npm run build:prerender
```

**How it works:**
1. `vite build` produces the normal SPA bundle in `dist/`
2. `scripts/prerender.mjs` boots a local server (sirv), visits each public route with Puppeteer, captures rendered HTML, writes to `dist/{route}/index.html`
3. SiteGround's Apache serves `{route}/index.html` via `DirectoryIndex` -- crawlers get real content
4. Real users still get the full SPA (JS entry point is preserved in all pre-rendered files)
5. `main.tsx` uses conditional hydration: `hydrateRoot` when pre-rendered content exists, `createRoot` otherwise

**Pre-rendered routes (9):**

| Route | Title |
|-------|-------|
| `/` | Brubru - AI Companion for EU Advocacy |
| `/login` | Login - Brubru |
| `/signup` | Sign Up - Brubru |
| `/about` | About - Brubru |
| `/contact` | Contact - Brubru |
| `/privacy` | Privacy Policy - Brubru |
| `/terms` | Terms of Service - Brubru |
| `/cookies` | Cookie Policy - Brubru |
| `/subprocessors` | Subprocessors - Brubru |

**When to update the route list:** If you add a new public (unauthenticated) route, add it to the `ROUTES` array in `frontend/scripts/prerender.mjs` with a title and meta description.

**robots.txt AI crawler rules:** `frontend/public/robots.txt` has explicit `Allow` rules for GPTBot, ClaudeBot, PerplexityBot, and Google-Extended.

**Files:**
- `frontend/scripts/prerender.mjs` - Puppeteer pre-render script
- `frontend/src/main.tsx` - Conditional hydration (hydrateRoot vs createRoot)
- `frontend/public/robots.txt` - AI crawler Allow rules
- `frontend/package.json` - `build:prerender` script, puppeteer + sirv devDeps

**Dependencies (devDependencies):**
- `puppeteer` - Headless Chrome for rendering
- `sirv` - Lightweight static file server

<!-- Example:
- Never use `moment.js` — use `date-fns` instead
- Always run `npm run lint` before committing frontend changes
- The RSS scraper requires a 2-second delay between requests
-->
