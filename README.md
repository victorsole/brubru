# Brubru

> Your AI-powered strategic advocacy assistant for navigating the EU bubble in Brussels

![Brubru Logo](frontend/public/assets/brubru_mainlogo.png)

**Developed by:** [Beresol BV](https://beresol.eu)
**Website:** [https://brubru.beresol.eu](https://brubru.beresol.eu)
**Contact:** hello@beresol.eu
**GitHub:** [https://github.com/victorsole/brubru](https://github.com/victorsole/brubru)

---

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Technology Stack](#technology-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Subscription Tiers](#subscription-tiers)
- [Data Sources](#data-sources)
- [Development Guidelines](#development-guidelines)
- [Deployment](#deployment)
- [Email Campaign System](#email-campaign-system)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)
- [Acknowledgments](#acknowledgments)

---

## Overview

**Brubru** is an AI-powered strategic advocacy assistant designed specifically for EU policy professionals, lobbyists, and organizations working within the Brussels institutional ecosystem. Combining cutting-edge conversational AI with specialized legislative tools, Brubru helps users analyze policies, draft amendments, monitor EU legislative procedures, and navigate institutional processes with confidence.

### What Brubru Does

- **AI Chat:** Context-aware conversational interface powered by Anthropic Claude and OpenAI GPT-4
- **Amendator:** Professional legislative amendment authoring tool (Akoma Ntoso XML compliant)
- **My EU Bubble:** Personalized RSS feed aggregation from 15+ EU institutional sources
- **EU Law Comply:** Automated compliance checking and gap analysis for EU regulations
- **Legislative Tracking:** Real-time monitoring of EU legislative procedures and timelines
- **Document Generator:** AI-powered generation of position papers, MEP briefings, and talking points
- **Multilingual:** Full support for all 23 official EU languages

---

## Key Features

### 1. **Brubru Chat** (Main Interface)

AI-powered conversational assistant for EU policy analysis with deep institutional context.

**Capabilities:**
- Natural language queries about EU legislation and policy
- Strategic guidance on advocacy approaches
- Stakeholder mapping and voting pattern analysis
- Procedural coaching on EU institutional processes
- Document uploads (PDF, DOCX) for contextual analysis
- Citation tracking with source references

**AI Models:**
- Primary: Mistral Small 3 (cost-effective, $0.20/1M input tokens)
- Fallback 1: Anthropic Claude (Sonnet 4, Opus 4)
- Fallback 2: OpenAI GPT-4 Turbo
- Fallback 3: Google Gemini 1.5 Pro
- Embeddings: BAAI/bge-m3 (multilingual)

### 2. **Amendator** (Legislative Amendment Editor)

XML-first legislative amendment authoring tool inspired by AT4AM, enhanced with modern AI capabilities.

**Features:**
- Akoma Ntoso XML compliance (OASIS LegalDocumentML standard)
- Two-column layout: Original text | Proposed amendment
- Click-to-amend interface with context menus
- AI-powered drafting assistance from natural language
- Position reference automation (Article X, paragraph Y, point (a))
- Track changes visualization (bold/strikethrough)
- Amendment workflow: Candidate → Tabled → Withdrawn
- Multi-format export: XML, HTML, PDF, Word

### 3. **My EU Bubble** (RSS Feed Aggregator)

Personalized news feed from EU institutional sources.

**Sources:**
- European Parliament (33+ topic & committee feeds)
- European Commission DGs
- Council of the EU
- OEIL Legislative Observatory
- Think Tank research (EPRS)
- General EU news feeds

**Features:**
- Subscribe/unsubscribe from feeds
- Mark entries as read
- Save/bookmark to collections
- Filter by category, source, date
- Email alerts (configurable)

### 4. **EU Law Comply** (Compliance Checker)

Automated compliance gap analysis for EU regulations.

**Process:**
1. Upload documents (PDF, DOCX, TXT)
2. Backend extracts text and identifies requirements
3. AI compares document against law cluster requirements
4. Gap analysis with severity ratings
5. Export detailed compliance report

**Reports Include:**
- Overall compliance score (0-100%)
- Gap summary (missing, partial, unclear)
- Detailed findings per requirement
- Recommended actions
- Export formats: PDF, Word, HTML, JSON

### 5. **Legislative Tracking**

Real-time monitoring of EU legislative procedures.

**Data Sources:**
- OEIL Legislative Observatory (21,600+ procedures)
- Legislative Train Schedule (490 priority files)
- EP Committee Work In Progress (26 committees)
- EC Register of Commission Documents (COM, SWD, SEC, C, JOIN, OJ, PV)
- European Parliament calendar
- Council working groups

**Tracking Features:**
- Procedure status updates
- Committee assignments and work-in-progress files
- Commission document tracking (COM, SWD, SEC, C, JOIN, OJ, PV) with RegDoc API enrichment
- Voting schedules
- Timeline visualization
- Track files from Legislative Train or by OEIL procedure reference

**Committee Work Integration:**
All 26 EP standing committees' work-in-progress data is scraped and integrated into the AI chatbot context. Ask about any committee (e.g., "What is INTA working on?") to get current legislative procedures.

### 5.1 **Predictions** (My EU Bubble Feature)

AI-powered legislative outcome predictions available in the My EU Bubble "Predictions" tab.

**Prediction Types:**
- **Timeline Prediction** - Estimated days/quarters until adoption
- **Outcome Prediction** - Likely final outcome (adopted, blocked, withdrawn)
- **EP Vote Prediction** - Plenary vote outcome with political group breakdown
- **Council Risk Assessment** - QMV analysis and blocking minority detection
- **Resolution Leading Indicators** - Historical resolution votes as predictive signals

**EP Political Group Breakdown:**
Shows predicted position (FOR/AGAINST/ABSTENTION) and confidence for all 9 EP groups:
- EPP, S&D, PfE, ECR, Renew, Greens/EFA, The Left, NI, ESN

**Council QMV Calculator:**
- 55% of states threshold (15/27)
- 65% population threshold
- Blocking minority detection (4+ states, 35%+ population)
- Swing state identification

**Resolution Leading Indicators:**
EP resolutions (INL, INI, RSP) that preceded legislation are displayed with vote statistics, showing historical support levels as predictive signals.

**Access:**
- White tier: Locked (upgrade CTA)
- Yellow tier: 10 predictions/month
- Blue tier: Unlimited predictions + Council analysis

### 6. **Document Generator** (AI-Powered Advocacy Documents)

Generate professional EU advocacy documents using AI, powered by Anthropic Claude.

**Document Types:**
- **Position Papers** - Structured policy positions with executive summary, background, key asks, and recommendations
- **MEP Briefings** - Concise briefings optimized for busy MEPs with clear asks and voting recommendations
- **Talking Points** - Quick-reference bullet points for meetings and calls

**Features:**
- Step-by-step wizard interface
- Link documents to EU legislation (CELEX numbers) or procedures
- Add policy areas and custom tags
- Multiple key asks with article references
- Stakeholder identification
- Markdown-rendered preview with professional formatting
- Copy to clipboard or save to document repository
- Export capabilities

**API Endpoints:**
- `POST /api/generate/position-paper` - Generate position paper
- `POST /api/generate/mep-briefing` - Generate MEP briefing
- `POST /api/generate/talking-points` - Generate talking points

### 7. **Admin Panel** (Restricted Access)

Backend management system accessible exclusively to Beresol team (hello@beresol.eu).

**Capabilities:**
- User management and subscription administration
- Usage analytics and dashboards
- Scraper management and monitoring
- Database administration
- Feature flag management

---

## Technology Stack

### Frontend
- **Framework:** React 18 with TypeScript
- **Build Tool:** Vite 7.x
- **Styling:** CSS (Irvin font from The New Yorker)
- **Internationalization:** i18next (23 EU languages)
- **State Management:** Zustand
- **UI Components:** Framer Motion (animations), Material Design Icons
- **Authentication:** Google OAuth, LinkedIn OAuth, Supabase Auth

### Backend
- **Framework:** FastAPI (Python 3.11+)
- **ORM:** SQLAlchemy 2.0 with Alembic migrations
- **Database:** PostgreSQL 15+ (Supabase managed)
- **API Standards:** REST with OpenAPI/Swagger docs
- **Data Validation:** Pydantic 2.5+
- **Task Scheduling:** APScheduler (RSS feed updates)

### AI & ML Services
- **Primary AI:** Mistral Small 3 (cost-effective at $0.20/1M tokens)
- **Fallback 1:** Anthropic Claude (Sonnet 4, Opus 4)
- **Fallback 2:** OpenAI GPT-4 Turbo
- **Fallback 3:** Google Gemini 1.5 Pro
- **Embeddings:** Hugging Face (BAAI/bge-m3 multilingual)
- **RAG Framework:** LangChain + ChromaDB
- **Vector Database:** FAISS (CPU) / pgvector (PostgreSQL)

### Document Processing
- **PDF:** PyPDF, pdfplumber, pikepdf
- **Word:** python-docx
- **XML:** lxml (Akoma Ntoso legislative standard)
- **Scraping:** BeautifulSoup4, aiohttp, feedparser

### Infrastructure
- **Hosting:** IONOS Deploy Now (frontend + backend on brubru.beresol.eu)
- **Database:** Supabase PostgreSQL (migrating to Google Cloud SQL)
- **Containers:** Docker with Nginx reverse proxy
- **SSL/TLS:** IONOS-managed certificates (1.3+)
- **Payment Processing:** Stripe

### Key Dependencies
```txt
# Backend (requirements.txt)
fastapi>=0.104.0
sqlalchemy>=2.0.0
alembic>=1.12.0
supabase>=2.0.0
anthropic>=0.7.0
openai>=1.3.0
lxml>=4.9.0
pydantic>=2.5.0
python-jose[cryptography]
passlib[bcrypt]
feedparser>=6.0.10
apscheduler>=3.10.4
chromadb>=0.4.15
sentence-transformers>=2.2.2

# Frontend (package.json)
react@18.x
react-router-dom@6.x
typescript@5.x
vite@7.x
i18next@23.x
zustand@4.x
framer-motion@11.x
axios@1.x
@anthropic-ai/sdk
```

---

## Project Structure

```
brubru/
├── frontend/                          # React SPA (Vite)
│   ├── src/
│   │   ├── pages/                    # Route pages
│   │   │   ├── landing_page.tsx
│   │   │   ├── login_page.tsx
│   │   │   ├── signup_page.tsx
│   │   │   ├── main_page.tsx         # Main chat interface
│   │   │   ├── amendator_page.tsx    # Amendment editor
│   │   │   ├── subscription_page.tsx # Pricing & billing
│   │   │   ├── profile_page.tsx      # User profile
│   │   │   ├── my_eu_bubble_page.tsx # RSS feeds
│   │   │   ├── eu_comply_page.tsx    # Compliance checker
│   │   │   ├── admin_panel_page.tsx  # Admin dashboard
│   │   │   ├── about_page.tsx        # About Brubru
│   │   │   ├── contact_page.tsx      # Contact information
│   │   │   ├── privacy_page.tsx      # Privacy Policy
│   │   │   ├── terms_page.tsx        # Terms of Service
│   │   │   ├── cookies_page.tsx      # Cookie Policy
│   │   │   └── subprocessors_page.tsx # Subprocessors list
│   │   │
│   │   ├── components/
│   │   │   ├── shared/               # Reusable components
│   │   │   ├── chat/                 # Chat interface components
│   │   │   ├── amendator/            # Amendment editor components
│   │   │   ├── bubble/               # My EU Bubble components
│   │   │   ├── eu_comply/            # Compliance checker components
│   │   │   └── admin/                # Admin panel components
│   │   │
│   │   ├── hooks/                    # Custom React hooks
│   │   ├── services/                 # API clients
│   │   ├── styles/                   # Global CSS (Irvin font)
│   │   └── i18n/                     # i18next configuration
│   │
│   ├── public/
│   │   └── assets/                   # Images, icons, backgrounds
│   │
│   ├── vite.config.ts
│   └── package.json
│
├── backend/
│   ├── api/                          # FastAPI routers
│   │   ├── auth.py                  # Authentication endpoints
│   │   ├── chat.py                  # Chat endpoints
│   │   ├── amendments.py            # Amendment CRUD
│   │   ├── subscriptions.py         # Subscription management
│   │   ├── stripe_payment.py        # Stripe integration
│   │   ├── my_eu_bubble.py          # RSS feed management
│   │   ├── eu_law_comply.py         # Compliance analysis
│   │   ├── legislative_train.py     # Legislative Train tracking
│   │   ├── documents.py             # Document upload & management
│   │   ├── generate.py              # AI document generation
│   │   ├── rss_feeds.py             # RSS feed configuration
│   │   ├── commission_documents.py  # EC Register Commission documents
│   │   └── admin_panel.py           # Admin dashboard
│   │
│   ├── models/                       # SQLAlchemy ORM models
│   │   ├── user.py                  # User profile
│   │   ├── chat.py                  # Chat conversations
│   │   ├── amendment.py             # Amendments
│   │   ├── eu_law.py                # EU laws database
│   │   ├── compliance.py            # Compliance analyses
│   │   ├── rss_feed.py              # RSS feeds
│   │   └── legislative_train.py     # Legislative train items
│   │
│   ├── schemas/                      # Pydantic request/response models
│   │
│   ├── services/
│   │   ├── ai_service.py            # Claude integration
│   │   ├── ai/                      # AI-specific services
│   │   │   ├── context_builder.py    # EU context injection
│   │   │   └── citation_tracker.py   # Source tracking
│   │   ├── compliance/              # Compliance checking
│   │   ├── scrapers/                # 15+ institutional scrapers
│   │   │   ├── european_parliament_scraper.py
│   │   │   ├── eurlex_scraper.py
│   │   │   ├── oeil_scraper.py
│   │   │   ├── legislative_train_scraper.py
│   │   │   └── scraper_orchestrator.py
│   │   ├── amendator/               # Amendment processing
│   │   ├── document_processing/     # PDF/DOCX parsing
│   │   ├── vector_db/               # Embeddings & similarity search
│   │   ├── rss/                     # RSS feed management
│   │   └── translation_service.py   # Google Translate integration
│   │
│   ├── core/
│   │   ├── config.py                # Environment configuration
│   │   ├── database.py              # Supabase/PostgreSQL setup
│   │   └── security.py              # Authentication utilities
│   │
│   ├── knowledge_base/              # Static EU institutional data
│   ├── migrations/                   # Alembic database migrations
│   ├── main.py                       # FastAPI app entry point
│   └── requirements.txt              # Python dependencies
│
├── docs/                             # Documentation
│   ├── brubru_technical_specification.md
│   ├── EU_APIs_RSS.md
│   ├── README_SCRAPERS.md
│   └── users.md                      # Test users for development
│
├── .env                              # Environment variables (not in repo)
├── docker-compose.yml                # Docker services
└── README.md                         # This file
```

**Note:** All files use `snake_case` naming convention. All frontend text is written in British English.

---

## Getting Started

### Prerequisites

- **Node.js** 18+ and npm
- **Python** 3.11+
- **PostgreSQL** 15+ (or use Supabase)
- **Docker** and Docker Compose (optional, recommended)

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/victorsole/brubru.git
cd brubru
```

2. **Set up environment variables**
```bash
cp .env.example .env
```

Edit `.env` with your credentials:
```env
# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-anon-key
SUPABASE_SERVICE_KEY=your-service-role-key

# AI Services (in fallback order)
MISTRAL_API_KEY=your-mistral-key        # Primary (get from console.mistral.ai)
ANTHROPIC_API_KEY=your-anthropic-key    # Fallback 1
OPENAI_API_KEY=your-openai-key          # Fallback 2
GOOGLE_GEMINI_API_KEY=your-gemini-key   # Fallback 3 (optional)

# OAuth (optional)
GOOGLE_CLIENT_ID=your-google-client-id
LINKEDIN_CLIENT_ID=your-linkedin-client-id

# Stripe (optional)
STRIPE_SECRET_KEY=your-stripe-secret-key
STRIPE_PUBLISHABLE_KEY=your-stripe-publishable-key

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/brubru
```

3. **Install frontend dependencies**
```bash
cd frontend
npm install
```

4. **Install backend dependencies**
```bash
cd ../backend
pip install -r requirements.txt
```

5. **Set up database**
```bash
cd backend
alembic upgrade head
```

6. **Run the application**

**Option A: Docker Compose (recommended)**
```bash
docker-compose up
```

**Option B: Manual**
```bash
# Terminal 1: Backend
cd backend
python -m uvicorn main:app --reload

# Terminal 2: Frontend
cd frontend
npm run dev
```

7. **Access the application**
- **Frontend:** http://localhost:5173 (Vite dev server)
- **Backend API:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs

8. **Populate EU Context Data** (Essential for AI responses)

The chat interface requires EU data for context-aware responses.

```bash
# Quick test (10 items, ~30 seconds)
python -m backend.scripts.populate_vector_db --limit 10

# Recommended (100 items, ~5 minutes)
python -m backend.scripts.populate_vector_db --limit 100

# Full population (1000+ items, ~30 minutes)
python -m backend.scripts.populate_vector_db --limit 1000
```

This fetches and indexes:
- Legislative documents from EUR-Lex
- MEP profiles from European Parliament
- Legislative procedures from OEIL
- Recent RSS feed entries

After populating, test with: *"What's the status of the AI Act?"*

9. **Seed Test Users** (Optional, for development/testing)

```bash
python3.12 -m backend.scripts.seed_test_users
```

This creates 13 pre-configured test users with different subscription tiers and policy interests. See `docs/users.md` for the full list.

| Tier | Users | Password |
|------|-------|----------|
| Blue | 5 | `test123` |
| Yellow | 8 | `test123` (except Meritxell: `test23`) |

---

## Subscription Tiers

Brubru offers three subscription tiers to meet different user needs:

### White (Free)
**Price:** Free
**Target:** Individuals exploring EU policy

**Features:**
- Basic chat with GPT-3.5-turbo
- 5 amendments/month
- Basic export (XML, HTML only)
- Community support
- Watermark on exports

### Yellow (Professional)
**Price:** €79/month or €790/year
**Target:** Individual consultants, lobbyists, advocacy professionals

**Features:**
- Advanced AI (GPT-4, Claude Sonnet)
- Unlimited amendments
- All export formats (XML, HTML, PDF, Word)
- No watermarks
- 1,000 API calls/month
- RSS alerts enabled
- Email support (48-hour response)

### Blue (Enterprise)
**Price:** €599/month (custom for 5+ users)
**Target:** Large organizations, government agencies, think tanks

**Features:**
- Everything in Yellow
- Unlimited API calls/month
- Claude Opus (most capable model)
- Multi-user accounts (5+ users)
- White-label support
- Dedicated account manager
- 24/7 priority support
- SLA with uptime guarantee
- Custom training modules

**Payment Processing:** Stripe (secure, PCI-compliant)
**Refund Policy:** 14-day money-back guarantee on first subscription

---

## Data Sources

Brubru aggregates information from 15+ authoritative EU institutional sources:

### Legislative & Legal Databases
- **[EUR-Lex](https://eur-lex.europa.eu)** - Official legislative texts, consolidated acts, case law
- **[OEIL](https://oeil.secure.europarl.europa.eu)** - Legislative procedure tracking (21,600+ files)
- **[EU Law Tracker](https://law-tracker.europa.eu)** - Commission legislative initiative tracking
- **[Publications Office](https://op.europa.eu)** - Official documents archive

### Parliamentary Data
- **[European Parliament](https://www.europarl.europa.eu)** - MEP data, committees, voting records
- **[Parliament Open Data](https://data.europarl.europa.eu)** - RDF/JSON-LD API (7+ datasets)
- **[Legislative Train Schedule](https://www.europarl.europa.eu/legislative-train)** - Commission priorities (490 files)
- **[Think Tank](https://epthinktank.eu)** - Research briefings and studies

### Institutional Intelligence
- **[Who's Who](https://op.europa.eu/en/web/who-is-who)** - Staff directories, org charts
- **[AssistEU](https://assist.eu)** - Procedural guidance
- **[Council of the EU](https://www.consilium.europa.eu)** - Council positions, working groups

### Commission Documents
- **[EC Register of Commission Documents](https://ec.europa.eu/transparency/documents-register/)** - COM proposals, SWD staff working documents, SEC, C, JOIN, OJ, PV documents with live RegDoc API enrichment

### Research & Standards
- **[JRC](https://joint-research-centre.ec.europa.eu)** - Scientific research, technical reports
- **[IATE](https://iate.europa.eu)** - EU terminology database (24 languages)
- **[Style Guide](https://style-guide.europa.eu)** - EU writing standards

---

## Development Guidelines

### Code Style

1. **File Naming:** All files use `snake_case`
   - ✅ `chat_interface.tsx`, `ai_service.py`, `amendment_grid.tsx`
   - ❌ `ChatInterface.tsx`, `AiService.py`, `AmendmentGrid.tsx`

2. **React Components:** Export in PascalCase
```typescript
// File: chat_interface.tsx
export const ChatInterface = () => { ... }
```

3. **Typography:** Use Irvin font universally (no exceptions)

4. **Language:** All frontend text in British English

5. **Accessibility:** WCAG 2.1 Level AA compliance

### Git Workflow

- **Main branch:** `main` (production-ready)
- **Feature branches:** `feature/description-in-kebab-case`
- **Commit messages:** Conventional Commits format

### Testing

- **Frontend:** Vitest + React Testing Library
- **Backend:** pytest with FastAPI TestClient
- **E2E:** Playwright

---

## Deployment

### Production Architecture

| Component | Platform | Domain |
|-----------|----------|--------|
| **Frontend** | IONOS Deploy Now | brubru.beresol.eu |
| **Backend** | IONOS Deploy Now (Docker) | brubru.beresol.eu/api |
| **Database** | Supabase PostgreSQL | (managed) |
| **SSL/TLS** | IONOS (auto-managed) | 1.3+ |

> **Migration Note:** The database will migrate from Supabase to Google Cloud SQL in a future phase. The backend uses pure SQLAlchemy with no Supabase SDK dependencies, making migration straightforward (change `DATABASE_URL` only).

### Environment Variables (Production)

```env
# Application
ENVIRONMENT=production
DEBUG=false
SECRET_KEY=your-secret-key
ALLOWED_ORIGINS=https://brubru.beresol.eu

# Database (Supabase → Google Cloud SQL in future)
DATABASE_URL=postgresql://user:password@host:5432/brubru
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-key

# AI Services (in fallback order)
MISTRAL_API_KEY=your-mistral-key        # Primary
ANTHROPIC_API_KEY=your-anthropic-key    # Fallback 1
OPENAI_API_KEY=your-openai-key          # Fallback 2
GOOGLE_GEMINI_API_KEY=your-gemini-key   # Fallback 3 (optional)

# OAuth
GOOGLE_CLIENT_ID=your-google-client-id
LINKEDIN_CLIENT_ID=your-linkedin-client-id

# Stripe Payments
STRIPE_SECRET_KEY=your-stripe-secret
STRIPE_PUBLISHABLE_KEY=your-stripe-publishable
```

### Docker Deployment (IONOS)

```bash
# Build backend image
cd backend
docker build -t brubru-backend .

# Run with docker-compose (includes nginx reverse proxy)
cd ..
docker-compose up -d

# View logs
docker-compose logs -f backend

# Health check
curl https://brubru.beresol.eu/api/health
```

### Manual Deployment Commands

```bash
# Backend only (without nginx)
cd backend
docker build -t brubru-backend .
docker run -d \
  --name brubru-backend \
  -p 8000:8000 \
  --env-file .env \
  brubru-backend

# Frontend (static build for IONOS)
cd frontend
npm run build
# Deploy dist/ folder to IONOS Deploy Now
```

### Database Migration Path (Supabase → Google Cloud)

When ready to migrate from Supabase to Google Cloud SQL:

1. **Export data:** `pg_dump` from Supabase PostgreSQL
2. **Create Cloud SQL instance:** PostgreSQL 15+ in desired region
3. **Import data:** `pg_restore` to Cloud SQL
4. **Update environment:** Change `DATABASE_URL` to Cloud SQL connection string
5. **Remove Supabase SDK:** Delete `backend/core/supabase.py` and `supabase` from `requirements.txt`
6. **Redeploy:** `docker-compose up -d --build`

No code changes required - SQLAlchemy handles database abstraction.

---

## Email Campaign System

Brubru includes a bulk email campaign infrastructure for outreach to EU institutions and lobby organisations registered in the EU Transparency Register. Built on Gmail SMTP via Google Workspace with no third-party email dependencies.

### Architecture

| Component | File | Purpose |
|-----------|------|---------|
| **Email Service** | `backend/services/email_service.py` | Singleton SMTP sender (TLS, port 587) |
| **BCC Campaign Sender** | `backend/scripts/send_campaign.py` | Bulk BCC batches (90 per batch) |
| **Institution Emails** | `backend/scripts/collect_institution_emails.py` | Tailored emails for 8 EU institutions |
| **Lobby Campaign** | `backend/scripts/send_lobby_campaign.py` | Multilingual lobby outreach (5 languages, 12 clusters) |
| **Bounce Cleaner** | `backend/scripts/clean_bounced_emails.py` | IMAP bounce detection and CSV cleanup |
| **Email Collection** | `backend/scripts/collect_institution_emails.py` | DNS MX discovery for institution emails |

### Institution Templates

8 tailored email templates, each speaking to the institution's specific policy domain:

| Key | Institution | Policy Angle |
|-----|-------------|--------------|
| `eeas` | European External Action Service | CFSP/CSDP, sanctions, trade agreements |
| `agencies` | EU Decentralised Agencies | Legislative context behind agency mandates |
| `eib` | European Investment Bank | InvestEU, REPowerEU, CBAM, Green Bond Standard |
| `ecb` | European Central Bank | MiCA, PSD3, AML, Banking Union |
| `eca` | Court of Auditors | MFF, RRF, CAP spending audits |
| `eesc` | Economic and Social Committee | Legislative proposals, opinion drafting |
| `omb` | European Ombudsman | Transparency, access to documents |
| `cor` | Committee of the Regions | Cohesion policy, ERDF, ESF+, Just Transition |

### Lobby Campaign (Multilingual)

4,053 lobby organisations from the EU Transparency Register, classified into 12 policy clusters with emails in 5 languages:

**Languages:** English (en), Spanish (es), French (fr), Italian (it), Dutch (nl)

**Policy Clusters:** Climate, Digital, Health, Agriculture, Finance, Trade, Energy, Transport, Civil Society, Research, Defence, Social

**Priority Countries:** Spain (253), France (408), Belgium (319), Italy (278), Netherlands (226), Luxembourg (30) = 1,514 orgs (37.3%)

### Campaign Commands

```bash
# Institution campaigns
python3.12 -c "from scripts.collect_institution_emails import send_from_csv; send_from_csv('eeas', dry_run=False)"

# Lobby classification preview
python3.12 scripts/send_lobby_campaign.py --classify-only
python3.12 scripts/send_lobby_campaign.py --classify-only --country spain

# Lobby campaign (multilingual)
python3.12 scripts/send_lobby_campaign.py --send --country spain --cluster climate
python3.12 scripts/send_lobby_campaign.py --dry-run --country spain,italy

# Test templates
python3.12 scripts/send_lobby_campaign.py --test-templates --lang es

# Bounce cleaning
python3.12 scripts/clean_bounced_emails.py --days 7 --apply
```

### Gmail Limits

- Daily sending limit: ~2,000 recipients (Google Workspace)
- Max recipients per message: 100 (we use 90 for safety)
- Limit resets ~24 hours after hitting it

---

## Roadmap

### ✅ Completed Phases
- **Phase 1:** Foundation (project setup, architecture)
- **Phase 2:** Chat implementation (Anthropic integration)
- **Phase 3:** Amendator (XML processing, UI)
- **Phase 4:** Intelligence layer (15+ scrapers)
- **Phase 5:** RSS feeds (My EU Bubble)
- **Phase 6:** Compliance checker (EU Law Comply)
- **Phase 7:** Subscription system (Stripe integration)
- **Phase 8:** Multi-language support (i18next, 23 languages)
- **Phase 14:** Predictions (Feb 2026)
  - Timeline and outcome predictions
  - EP political group vote breakdown
  - Council QMV calculator and blocking minority analysis
  - Resolution leading indicators
- **Phase 15:** Commission Document Register (Feb 2026)
  - EC Register of Commission Documents integration (COM, SWD, SEC, C, JOIN, OJ, PV)
  - Discovery via EUR-Lex RSS + CELLAR SPARQL
  - Enrichment via live RegDoc API (titles, DGs, languages for 240+ documents)
  - CELEX-to-reference conversion for cross-system lookups

### 🔄 Current Phase
- **Phase 13:** AI Context Injection (hybrid legal assistant)
  - Improving EU context relevance
  - Citation accuracy enhancement
  - Legislative file analysis

### 🚀 Planned Future Features
- Real-time collaboration (WebSocket support)
- Fine-tuned models (LORA adapters for EU context)
- Multi-language amendment validation
- Integration with EP systems (direct submission)
- Advanced analytics (usage patterns, success metrics)

---

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

Please read our [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

---

## License

This project is proprietary software owned by Beresol BV. All rights reserved.

The Brubru trademark is registered with the European Union Intellectual Property Office (EUIPO).

For licensing inquiries, contact hello@beresol.eu.

---

## Acknowledgments

- **AT4AM:** Inspiration for Amendator component
- **NSESA:** Reference implementation for legislative XML processing
- **European Parliament:** Akoma Ntoso standard and legislative procedures
- **Anthropic & OpenAI:** AI capabilities powering the intelligence layer
- **EU Institutions:** Open data access enabling comprehensive EU context

---

## Contact

- **Website:** [https://brubru.beresol.eu](https://brubru.beresol.eu)
- **Email:** hello@beresol.eu
- **Company:** [Beresol BV](https://beresol.eu)
- **GitHub:** [https://github.com/victorsole/brubru](https://github.com/victorsole/brubru)

---

**Brubru** - Empowering strategic advocacy in the EU bubble

*Built with care in Brussels by Beresol BV*
