# Brubru

  > Your AI multiagent companion for navigating the EU bubble in Brussels

  ![Brubru Logo](public/brubru-logo.svg)

  Brubru is brought to you by Beresol BV: https://beresol.eu

  GitHub repository: https://github.com/victorsole/brubru

  ## Overview

  Brubru is an AI-powered strategic advocacy assistant designed for EU policy professionals, lobbyists, and organizations working within the Brussels institutional ecosystem. Built as a multiagent system, Brubru combines conversational AI with specialized legislative tools to help users analyze policies, strategize advocacy campaigns, and draft amendments for European Parliament proposals.

  ### What Brubru Does

  - **Analyses** EU legislation, policy documents, and institutional positions
  - **Strategises** advocacy approaches based on procedural knowledge and stakeholder mapping
  - **Drafts** legislative amendments with AI assistance and Akoma Ntoso XML compliance
  - **Maps** institutional actors, committees, and decision-making timelines
  - **Coaches** users on EU procedural best practices

  ## Architecture

  Brubru consists of two main interfaces:

  ### 1. **Brubru** (Main Page)

  A Claude- and ChatGPT-inspired conversational interface for strategic policy analysis and advocacy planning.

  **Features:**
  - Main chat interface for natural language queries
  - Left sidebar for chat history and session management
  - Document upload functionality (PDFs, Word docs, legislative texts)
  - Multi-source intelligence fetching from EU institutions
  - Strategic guidance and procedural coaching

  **Core Capabilities:**
  - Analyse legislative proposals and their political context
  - Map stakeholder positions and voting patterns
  - Suggest advocacy strategies and timing
  - Provide institutional procedural guidance
  - Answer questions about EU decision-making processes

  ### 2. **Amendator** (Secondary Page)

  A specialised legislative amendment authoring tool inspired by AT4AM, enhanced with modern AI capabilities, linked to Brubru's chat interface.

  **Features of Amendator:**
  - XML-first architecture using Akoma Ntoso legislative standard
  - Two-column view: original text | proposed amendment
  - Click-to-amend interface (hover → context menu → "Amend/New/Delete")
  - AI-powered drafting assistance
  - Position reference automation (Article X, paragraph Y, point (a))
  - Track changes visualization (bold for additions, strikethrough for deletions)
  - Amendment workflow: Candidate → Tabled → Withdrawn
  - Multi-format export: XML, HTML, PDF, Word

  **How It Works:**
  1. Load EU legislative document (directive, regulation, proposal)
  2. Load own text (e.g., policy paper, one-pager, "About", a research study, etc.)
  3. Click on amendable elements (articles, paragraphs, points) within the grid
  4. Use integrated AI to draft amendment text from natural language intent
  5. Review and edit AI-generated amendments
  6. Manage amendment status and export for submission

  ### 3. **Admin Panel** (Restricted Access)

  A comprehensive backend management system accessible exclusively to the Beresol team (helloberesol@gmail.com).

  **Access Control:**
  - Restricted to Beresol profile only
  - Separate authentication layer
  - Admin-specific routing within Brubru application

  **Planned Features:**
  - User management and subscription administration
  - System monitoring and analytics dashboard
  - Content moderation and quality control
  - Data source configuration and scraper management
  - API usage monitoring and rate limiting
  - Database backup and maintenance tools
  - Feature flag management for gradual rollouts

  **Implementation Status:** Planned for Phase 7 (Post-Launch)

  ## Technology Stack

  ### Frontend
  - **React 18** with TypeScript
  - **Vite** for build tooling
  - **CSS** with Irvin font (The New Yorker typography)
  - **i18next** for internationalization (23 EU languages)

  ### Backend
  - **Python 3.11+** with FastAPI
  - **SQLAlchemy 2.0** ORM with Alembic migrations
  - **Supabase Python Client** for auth, storage, realtime
  - **lxml** for Akoma Ntoso XML processing
  - **Pydantic** for data validation

  ### Database & Auth
  - **Supabase** (managed PostgreSQL + auth + storage + realtime)
  - **PostgreSQL 15+** (via Supabase)

  ### AI Services
  - **Anthropic Claude** (primary) - Legislative analysis, consistency checking
  - **OpenAI GPT-4** (secondary) - Text generation, translation, summarization

  ### Deployment
  - **Local Development**: Docker Compose (frontend + backend + local Postgres)
  - **Frontend**: Vercel (React app on port 3000)
  - **Backend**: IONOS.fr (FastAPI in Docker, connects to Supabase)
  - **Database**: Supabase (managed PostgreSQL with connection pooling)
  - **Reverse Proxy**: Nginx on IONOS.fr

  ## Project Structure

  brubru/
  ├── frontend/                      # Single React application (port 3000)
  │   ├── src/
  │   │   ├── pages/
  │   │   │   ├── chat_page.tsx      # Main chat interface (/)
  │   │   │   ├── amendator_page.tsx # Amendator (/amendator)
  │   │   │   └── admin/             # Admin Panel (restricted - /admin)
  │   │   │       ├── dashboard_page.tsx
  │   │   │       ├── users_page.tsx
  │   │   │       ├── analytics_page.tsx
  │   │   │       └── scrapers_page.tsx
  │   │   │
  │   │   ├── components/
  │   │   │   ├── shared/
  │   │   │   │   ├── header.tsx     # Navigation: Chat | Amendator | Admin (if authorized)
  │   │   │   │   ├── footer.tsx
  │   │   │   │   └── sidebar.tsx
  │   │   │   │
  │   │   │   ├── chat/              # Chat-specific components
  │   │   │   │   ├── chat_interface.tsx
  │   │   │   │   ├── message_list.tsx
  │   │   │   │   └── document_upload.tsx
  │   │   │   │
  │   │   │   ├── amendator/         # Amendator-specific components
  │   │   │   │   ├── document_viewer.tsx
  │   │   │   │   ├── amendment_editor.tsx
  │   │   │   │   ├── two_column_layout.tsx
  │   │   │   │   └── amendment_grid.tsx
  │   │   │   │
  │   │   │   └── admin/             # Admin Panel components
  │   │   │       ├── user_management.tsx
  │   │   │       ├── analytics_dashboard.tsx
  │   │   │       └── scraper_monitor.tsx
  │   │   │
  │   │   ├── app.tsx                # React Router setup
  │   │   └── main.tsx
  │   │
  │   ├── vite.config.ts             # Port 3000 configuration
  │   └── package.json
  │
  ├── backend/
  │   ├── api/
  │   │   ├── chat.py
  │   │   ├── amendments.py
  │   │   ├── documents.py
  │   │   ├── ai.py
  │   │   └── auth.py
  │   │
  │   ├── services/
  │   │   ├── ai_service.py          # Anthropic + OpenAI integration
  │   │   ├── xml_service.py         # Akoma Ntoso processing
  │   │   ├── scrapers/              # EU institutional scrapers
  │   │   │   ├── base_scraper.py
  │   │   │   ├── european_parliament_scraper.py
  │   │   │   ├── eurlex_scraper.py
  │   │   │   └── ...
  │   │   └── ...
  │   │
  │   └── models/
  │       ├── chat.py
  │       ├── amendment.py
  │       ├── document.py
  │       └── user.py
  │
  ├── shared/
  │   └── styles/
  │       ├── globals.css            # Global styles
  │       └── fonts.css              # Irvin font definitions
  │
  ├── public/
  │   └── New-Yorker-Font/
  │       └── NY Irvin.ttf           # The New Yorker Irvin font
  │
  ├── .env                           # API keys (Anthropic, OpenAI, Google, LinkedIn)
  ├── docker-compose.yml
  └── README.md

  **Note:** All file names use `snake_case` convention (e.g., `chat_interface.tsx`, `amendment_grid.tsx`). Always written in British English.

  ## Core Components

  ### Shared Components
  - **header.tsx** - Navigation between chat (main Brubru page) and Amendator
  - **footer.tsx** - Copyright, links, language selector
  - **sidebar.tsx** - Collapsible sidebar (used in chat interface and Amendator)

  ### Chat Components
  - **chat_interface.tsx** - Main conversational UI
  - **message_list.tsx** - Chat message display with streaming
  - **document_upload.tsx** - Drag-and-drop document uploads

  ### Amendator Components
  - **document_viewer.tsx** - Display legislative XML as readable text
  - **amendment_editor.tsx** - Click-to-amend interface
  - **two_column_layout.tsx** - Original | Amendment side-by-side view
  - **amendment_grid.tsx** - List/grid of amendments with status
  - **ai_drafting_panel.tsx** - Natural language → amendment text

  ## Design System

  ### Typography
  **Primary Font:** Irvin (The New Yorker Font)
  - All text throughout the application uses Irvin
  - Includes regular, bold, italic, and bold-italic variants
  - Font file: `public/New-Yorker-Font/NY Irvin.ttf`

  ### Colour Palette

  Based on brubru.world aesthetic:

  ```css
  /* Primary Colors */
  --color-primary: #000000;        /* Black */
  --color-secondary: #ffffff;      /* White */
  --color-accent-blue: #0693e3;    /* Cyan Blue */
  --color-accent-purple: #9b51e0;  /* Vivid Purple */

  /* Status Colors */
  --color-success: #059669;        /* Green - "Tabled" */
  --color-warning: #d97706;        /* Orange - "Candidate" */
  --color-danger: #dc2626;         /* Red - "Withdrawn" */

  /* Neutrals */
  --color-gray-50: #f9fafb;
  --color-gray-100: #f3f4f6;
  --color-gray-200: #e5e7eb;
  --color-gray-700: #374151;
  --color-gray-900: #111827;

### Spacing & Layout

  - Maximum content width: 800px (reading), 1200px (wide layouts)
  - Block gap spacing: 24px
  - Responsive breakpoints:
    - Mobile: 767px
    - Tablet: 1024px
    - Desktop: 1200px+

  ###  Aesthetic

  Clean, modern, professional with European institutional credibility. Tech-forward but approachable. Minimalist design emphasizing content over decoration.

  Data Sources

  Brubru fetches information from authoritative EU institutional sources:

  ### EU Institutions & Decision-Making Bodies

  - **[European Parliament](https://www.europarl.europa.eu/portal/en)** - Legislative proposals, MEP information, committee activities
  - **[European Commission](https://commission.europa.eu/index_en)** - Policy initiatives, impact assessments, Commission portfolios
  - **[Council of the EU](https://www.consilium.europa.eu/en/council-eu/)** - Council positions, presidency priorities, working groups

  ### Legislative & Legal Databases

  - **[EUR-Lex](https://eur-lex.europa.eu/homepage.html)** - Official legislative texts, consolidated acts, case law
  - **[Publications Office](https://op.europa.eu/en/home)** - Official EU documents, publications archive
  - **[OEIL (Legislative Observatory)](https://oeil.secure.europarl.europa.eu/oeil/en)** - Legislative procedure tracking, document trails
  - **[Legislative Train Schedule](https://www.europarl.europa.eu/legislative-train/)** - Visual procedure tracking, priority files
  - **[EU Law Tracker](https://law-tracker.europa.eu/homepage?lang=en)** - European Commission's official tool for tracking legislative initiatives from inception to national implementation. It's a comprehensive end-to-end monitoring system covering the entire legislative lifecycle.

  ### Institutional Intelligence

  - **[Who's Who](https://op.europa.eu/en/web/who-is-who)** - Institutional contacts, organizational charts, staff directories
  - **[AssistEU](https://assist.eu/)** - Legislative assistant tool, procedural guidance

  ### Research & Analysis

  - **[Joint Research Centre (JRC)](https://joint-research-centre.ec.europa.eu/index_en)** - Scientific research, technical reports
  - **[European Parliament Think Tank](https://www.europarl.europa.eu/thinktank/en/home)** - Policy analysis, briefings, studies

  ### Standards & Terminology

  - **[Interinstitutional Style Guide](https://style-guide.europa.eu/en/)** - EU writing standards, formatting conventions
  - **[IATE (Terminology Database)](https://iate.europa.eu/home)** - Official EU terminology in 24 languages

  Business Model

  Brubru operates as a strategic advisory SaaS platform with multiple revenue streams:

  1. Subscription Tiers

  - Professional: Individual advocates, consultants
  - Team: Small advocacy firms, NGOs
  - Enterprise: Large corporations, government agencies

  2. Service Offerings

  - Strategic Guidance: AI-powered policy analysis and advocacy roadmaps
  - Procedural Coaching: Step-by-step guidance on EU institutional processes
  - Document Drafting: Amendment authoring with AI assistance
  - Institutional Mapping: Updated stakeholder positions, voting patterns, committee memberships
  - Legislative Intelligence: Calendars, deadlines, procedure tracking

  3. Custom Consultancy

  - Bespoke packages for organizations targeting specific policy areas
  - White-label versions for large institutions
  - Training modules on EU advocacy best practices

  4. Data & Intelligence

  - Subscription-based access to curated institutional data
  - Regular updates on legislative calendars and committee activities
  - Stakeholder analysis reports

  Getting Started

  Prerequisites

  - Node.js 18+ and npm
  - Python 3.11+
  - PostgreSQL 15+
  - Docker and Docker Compose (optional, for containerized development)

  Installation

  1. Clone the repository
  git clone https://github.com/yourusername/brubru.git
  cd brubru
  2. Set up environment variables
  cp .env.example .env
  # Edit .env with your API keys:
  # - ANTHROPIC_API_KEY
  # - OPENAI_API_KEY
  # - GOOGLE_API_KEY (optional)
  # - LINKEDIN_CLIENT_ID (optional)
  # - DATABASE_URL
  3. Install frontend dependencies
  cd frontend
  npm install

  4. Install backend dependencies
  cd ../backend
  pip install -r requirements.txt

  5. Set up database
  alembic upgrade head

  6. Run the application

  Option A: Docker Compose (recommended)
  ```bash
  docker-compose up
  ```

  Option B: Manual
  ```bash
  # Terminal 1: Backend
  cd backend
  uvicorn main:app --reload

  # Terminal 2: Frontend
  cd frontend
  npm run dev
  ```

  7. Access the application
     - Brubru Application: **http://localhost:3000**
       - Chat Interface: http://localhost:3000/
       - Amendator: http://localhost:3000/amendator
     - Backend API: **http://localhost:8000**
     - API Docs: http://localhost:8000/docs

  Development Guidelines

  Code Style

  1. All files use snake_case naming
    - ✅ chat_interface.tsx, ai_service.py, amendment_grid.tsx
    - ❌ ChatInterface.tsx, AiService.py, AmendmentGrid.tsx
  2. React components export in PascalCase
  // File: chat_interface.tsx
  export const ChatInterface = () => { ... }
  3. Use Irvin font universally
    - No exceptions - all text uses Irvin
    - Define in globals.css and apply to body
  4. Follow EU accessibility standards
    - WCAG 2.1 Level AA compliance
    - Multilingual support (23 EU languages)
    - Keyboard navigation
  5. All new text for the frontend is written in British English.

  Git Workflow

  - Main branch: main (production-ready)
  - Feature branches: feature/description-in-kebab-case
  - Commit messages: Conventional Commits format

  Testing

  - Frontend: Vitest + React Testing Library
  - Backend: pytest with FastAPI TestClient
  - E2E: Playwright

  Roadmap

  Phase 1: Foundation (Current)

  - Project setup and architecture
  - Design system and branding
  - Environment configuration
  - Chat interface skeleton
  - Amendator interface skeleton

  Phase 2: Chat Implementation

  - Anthropic Claude integration
  - Message streaming
  - Document upload and parsing
  - Chat history persistence
  - Multi-source data fetching

  Phase 3: Amendator Implementation

  - Akoma Ntoso XML parsing
  - Click-to-amend interface
  - Two-column amendment view
  - AI drafting assistance
  - Amendment status workflow
  - Multi-format export

  Phase 4: Intelligence Layer

  - EU institutional scrapers
  - Stakeholder database
  - Legislative calendar integration
  - Committee and MEP tracking

  Phase 5: Advanced Features

  - Real-time collaboration
  - Translation to 23 EU languages
  - Amendment success prediction
  - Voting pattern analysis

  Phase 6: Production & Launch

  - Performance optimization
  - Security hardening
  - Beta user testing
  - Public launch

  Phase 7: Admin Panel (Post-Launch)

  - Admin authentication and authorization
  - User management dashboard
  - Subscription and billing administration
  - System analytics and monitoring
  - Data source configuration interface
  - Scraper status and logs monitoring
  - Database administration tools
  - Feature flag management system

  Contributing

  Contributions are welcome! Please read our CONTRIBUTING.md for details on our code of conduct and submission process.

  License

  LICENSE - see LICENSE file for details

  Acknowledgments

  - AT4AM: Inspiration for Amendator component
  - NSESA: Reference implementation for legislative XML processing
  - European Parliament: Akoma Ntoso standard and legislative procedures
  - Anthropic & OpenAI: AI capabilities powering the intelligence layer

  Contact

  - Website: https://brubru.beresol.eu
  - Email: helloberesol@gmail.com

  ---
  Brubru - Empowering strategic advocacy in the EU bubble