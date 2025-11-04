# Brubru Technical Specification & Development Guide

## Project Overview

Brubru is a strategic advocacy assistant for EU policy work, built as a multi-agent system. This document focuses on **Brubru Amendator**, the first component to be developed - a modern web-based legislative amendment authoring tool.

### Historical Context

This project draws inspiration from AT4AM (Authoring Tool for Amendments), the European Parliament's revolutionary amendment editor that transformed legislative drafting from 2010-2013. AT4AM replaced a chaotic Microsoft Word template system with an elegant web-based XML editor, processing over 285,000 amendments for 2,300+ users. It succeeded by separating content from formatting, automating structural validation, and enabling drafters to focus on substance rather than layout rules.

Brubru modernizes this approach with 2025 technologies and AI capabilities that were impossible in 2010, while preserving the core insight: **legislative amendment authoring deserves purpose-built tools, not repurposed office software**.

## Design & Branding

### Typography
**Primary Font**: The New Yorker's Irvin Font
- Source: https://www.dafontfree.co/new-yorker-font/
- Use throughout the application interface
- Provides professional, editorial aesthetic appropriate for legislative work

### File Naming Convention
**ALL files must use snake_case format**
- ✅ Correct: `amendment_editor.tsx`, `xml_service.py`, `two_column_layout.tsx`
- ❌ Wrong: `AmendmentEditor.tsx`, `XmlService.py`, `TwoColumnLayout.tsx`

Exception: React component files may use PascalCase for the component name, but the file should still be snake_case (e.g., file: `amendment_editor.tsx`, export: `AmendmentEditor`)

## Product Scope

### What We're Building First

**Brubru Amendator**: A legislative amendment editor page that allows users to:
1. View legislative documents (European Parliament proposals, directives, regulations)
2. Create amendments by clicking on amendable elements
3. See amendments in a two-column format (original text | proposed changes)
4. Manage amendments with status workflow (Candidate → Tabled → Withdrawn)
5. Export amendments in multiple formats (XML, HTML, PDF, Word)
6. Use AI assistance for drafting, consistency checking, and translation

### What We're NOT Building Yet

- Main dashboard with chatbot (comes later)
- Full Brubru Strategist (advocacy strategy tool)
- Full Brubru Analyser (policy analysis tool)
- Web scraper infrastructure

### Initial Landing Page

The first page users see is the **amendment editor interface** - similar in function to AT4AM but:
- Branded completely as "Brubru"
- No references to AT4AM
- Modern, clean design with Irvin font
- Simplified workflow optimized for first-time users

Later, we'll build a proper dashboard that becomes the main entry point, with the amendment editor as one of several tools.

## Technical Architecture

### Core Problem Solved

Legislative amendment drafting has traditionally been painful:
- Hundreds of Microsoft Word templates with complex formatting rules
- Formatting used to convey workflow information (misusing bold/italic)
- Manual position references causing errors
- Multilingual documents hampering parallel revision
- Slow, error-prone process from drafting to publication

**Brubru's Solution**: XML-first architecture where:
- Akoma Ntoso XML feeds the legislative chain from inception
- Automatic validation ensures document structure correctness
- Multi-language coherence guaranteed at structural level
- Position references automated and error-free
- WYSIWYG web editor hides XML complexity from users

### Technology Stack

**Frontend**
- React 18 with TypeScript
- Vite for build tooling
- CSS with Irvin font (custom @font-face)
- i18next for internationalization (23 EU languages)

**Backend**
- Python 3.11+ with FastAPI
- SQLAlchemy ORM with Alembic migrations
- PostgreSQL 15+ database
- lxml for XML processing (Akoma Ntoso)
- Pydantic for data validation

**AI Integration**
- OpenAI SDK (GPT-4)
- Anthropic SDK (Claude)
- Server-side integration for data sovereignty

**Deployment**
- Docker Compose for local development
- Docker containers for production
- Nginx reverse proxy

## Project Structure

```
brubru/
├── apps/
│   └── amendator/
│       ├── frontend/
│       │   ├── public/
│       │   │   ├── index.html
│       │   │   ├── fonts/
│       │   │   │   └── irvin/          # New Yorker Irvin font files
│       │   │   └── locales/
│       │   │       ├── en/
│       │   │       │   └── translation.json
│       │   │       ├── fr/
│       │   │       ├── de/
│       │   │       └── [21 more EU languages]/
│       │   │
│       │   ├── src/
│       │   │   ├── components/
│       │   │   │   ├── editor/
│       │   │   │   │   ├── document_viewer.tsx       # Display legislative text
│       │   │   │   │   ├── amendment_editor.tsx      # Main editing interface
│       │   │   │   │   ├── two_column_layout.tsx     # Original | Amendment view
│       │   │   │   │   ├── element_selector.tsx      # Clickable elements
│       │   │   │   │   ├── context_menu.tsx          # Amend/New/Delete actions
│       │   │   │   │   ├── amendment_modal.tsx       # Creation dialog
│       │   │   │   │   └── track_changes.tsx         # Bold/italic markup
│       │   │   │   │
│       │   │   │   ├── amendments/
│       │   │   │   │   ├── amendment_list.tsx
│       │   │   │   │   ├── amendment_card.tsx
│       │   │   │   │   ├── status_selector.tsx       # Candidate/Tabled/Withdrawn
│       │   │   │   │   ├── bulk_actions.tsx
│       │   │   │   │   └── export_panel.tsx          # XML/HTML/PDF/Word
│       │   │   │   │
│       │   │   │   ├── ai/
│       │   │   │   │   ├── ai_drafting_panel.tsx     # Natural language → amendment
│       │   │   │   │   ├── consistency_checker.tsx   # Legal conflict detection
│       │   │   │   │   ├── translation_assist.tsx    # Multi-language suggestions
│       │   │   │   │   └── justification_gen.tsx     # Auto-generate explanations
│       │   │   │   │
│       │   │   │   └── common/
│       │   │   │       ├── header.tsx
│       │   │   │       ├── sidebar.tsx
│       │   │   │       └── button.tsx
│       │   │   │
│       │   │   ├── hooks/
│       │   │   │   ├── use_amendment.ts
│       │   │   │   ├── use_document.ts
│       │   │   │   ├── use_ai.ts
│       │   │   │   └── use_auth.ts
│       │   │   │
│       │   │   ├── services/
│       │   │   │   ├── api.ts                        # Backend client
│       │   │   │   ├── xml_parser.ts                 # Client-side XML parsing
│       │   │   │   └── diff_renderer.ts              # Track changes UI
│       │   │   │
│       │   │   ├── types/
│       │   │   │   ├── amendment.ts
│       │   │   │   ├── document.ts
│       │   │   │   └── akoma_ntoso.ts
│       │   │   │
│       │   │   ├── styles/
│       │   │   │   ├── global.css
│       │   │   │   ├── fonts.css                     # @font-face for Irvin
│       │   │   │   └── variables.css
│       │   │   │
│       │   │   ├── app.tsx
│       │   │   └── main.tsx
│       │   │
│       │   ├── package.json
│       │   ├── vite.config.ts
│       │   └── tsconfig.json
│       │
│       └── backend/
│           ├── app/
│           │   ├── api/
│           │   │   ├── __init__.py
│           │   │   ├── amendments.py
│           │   │   ├── documents.py
│           │   │   ├── ai.py
│           │   │   ├── export.py
│           │   │   └── auth.py
│           │   │
│           │   ├── core/
│           │   │   ├── __init__.py
│           │   │   ├── config.py
│           │   │   ├── database.py
│           │   │   └── security.py
│           │   │
│           │   ├── models/
│           │   │   ├── __init__.py
│           │   │   ├── amendment.py
│           │   │   ├── document.py
│           │   │   └── user.py
│           │   │
│           │   ├── schemas/
│           │   │   ├── __init__.py
│           │   │   ├── amendment.py
│           │   │   ├── document.py
│           │   │   └── ai.py
│           │   │
│           │   ├── services/
│           │   │   ├── __init__.py
│           │   │   ├── amendment_service.py
│           │   │   ├── xml_service.py                # Akoma Ntoso parsing
│           │   │   ├── diff_service.py               # Text comparison
│           │   │   ├── ai_service.py                 # OpenAI/Anthropic integration
│           │   │   └── export_service.py             # Format conversion
│           │   │
│           │   └── utils/
│           │       ├── __init__.py
│           │       ├── xml_parser.py
│           │       ├── validators.py
│           │       └── diff_algorithm.py
│           │
│           ├── schemas/                               # XSD validation files
│           │   ├── akoma_ntoso_3.0.xsd
│           │   └── eli_schema.xsd
│           │
│           ├── tests/
│           │   ├── __init__.py
│           │   ├── conftest.py
│           │   ├── test_amendments.py
│           │   ├── test_xml_service.py
│           │   └── test_ai_service.py
│           │
│           ├── alembic/                               # Database migrations
│           │   ├── versions/
│           │   └── env.py
│           │
│           ├── main.py
│           ├── requirements.txt
│           └── .env.example
│
├── infrastructure/
│   ├── docker/
│   │   ├── frontend.dockerfile
│   │   ├── backend.dockerfile
│   │   └── nginx.dockerfile
│   │
│   └── docker-compose.yml
│
├── docs/
│   ├── getting_started.md
│   ├── architecture.md
│   ├── akoma_ntoso_guide.md
│   └── api.md
│
├── scripts/
│   ├── setup.sh
│   └── seed_db.py
│
├── .gitignore
├── README.md
└── LICENSE
```

### Why This Structure?

**Single backend application**: All services (XML processing, diff engine, AI, CRUD operations) live in one FastAPI application. No microservices complexity.

**Inline service modules**: XML processing, diff generation, and AI integration are service classes within the backend, not separate deployed services. They're library code, not microservices.

**Simple deployment**: Three containers (frontend, backend, database) orchestrated with docker-compose. No Kubernetes unless we reach massive scale.

**Manageable by 1-3 developers**: The alternative microservices architecture would require a DevOps team. This structure one developer can manage.

## Core Features & User Workflows

### 1. Document Viewing & Navigation

**User Story**: As a legislative drafter, I want to view EU legislative proposals so I can identify what needs amendment.

**Implementation**:
- Documents stored as Akoma Ntoso XML
- Frontend parses XML and renders as readable, hierarchical text
- Articles, paragraphs, points displayed with proper numbering
- Hover over elements highlights them as amendable
- Document outline sidebar for navigation

### 2. Creating Amendments

**User Story**: As a legislative drafter, I want to amend specific text with just two clicks.

**Workflow**:
1. User hovers over amendable element (article, paragraph, point)
2. Context menu appears: "Amend" | "New" | "Delete"
3. Click "Amend" → modal opens with two tabs:
   - **Original**: Source text from proposal
   - **Amendment**: Editable version where user makes changes
4. Additional tabs for Author (with autocomplete) and Meta (justification)
5. Click "Save" → amendment created in "Candidate" status
6. Amendment displays inline with track changes (additions bold, deletions strikethrough)

**Schema-Aware Restrictions**:
- "New" only shows element types permitted at that document location
- Can't create invalid structures (e.g., point outside an article)
- Follows Akoma Ntoso schema rules automatically

### 3. Two-Column Amendment View

**User Story**: As a reviewer, I want to see original and amended text side-by-side to understand changes clearly.

**Implementation**:
- Left column: Original legislative text
- Right column: Proposed amendment text
- Changes marked with bold (additions) and ~~strikethrough~~ (deletions)
- Position reference shown at top (e.g., "Article 3, paragraph 2, point (a)")
- Author and justification displayed below columns

### 4. Amendment Management

**User Story**: As a legislative drafter, I want to manage multiple amendments and track their status.

**Features**:
- Amendment list view with filters (All, Candidate, Tabled, Withdrawn)
- Click amendment marker in right margin to jump to it
- Expanded action menu per amendment:
  - **Table**: Submit amendment formally
  - **Withdraw**: Retract amendment
  - **Delete**: Remove amendment
  - **Export**: XML, HTML, PDF, or Word format
- Bulk operations for multiple amendments
- Search and sort functionality

**Status Workflow**:
```
Candidate → Tabled → Withdrawn
    ↓         ↓
  Delete   Delete
```

### 5. AI-Assisted Drafting

**User Story**: As a legislative drafter, I want AI to help me write amendment text based on my policy intent.

**Features**:
- Natural language input: "This article should include provisions for small businesses"
- AI (GPT-4 or Claude) generates amendment text
- User reviews and edits generated text
- Option to regenerate with different prompt
- AI suggestions marked as "AI-generated, requires review"

**Privacy**: All AI calls happen server-side to keep sensitive legislative text within controlled infrastructure, not sent directly to external APIs from client.

### 6. Legal Consistency Checking

**User Story**: As a legislative drafter, I want to know if my amendment conflicts with existing legislation or creates internal contradictions.

**Features**:
- Scan amendment against base document for logical conflicts
- Check references to other articles/directives/regulations
- Highlight potential inconsistencies
- Suggest corrections
- Flag undefined terms or broken cross-references

### 7. Translation Assistance

**User Story**: As a legislative drafter, I need initial translations in all 23 EU languages.

**Features**:
- Generate AI translations from source language to all required languages
- Display translations with "AI-generated, expert review required" warning
- Side-by-side view of all language versions
- Export translation package for linguistic experts
- Track which translations have been human-reviewed

### 8. Multi-Format Export

**User Story**: As a legislative drafter, I need to share amendments in various formats for different audiences.

**Export Formats**:
- **XML (Akoma Ntoso)**: Complete structural information for automated processing
- **HTML**: Human-readable web format
- **PDF**: Archival documents for printing
- **Word (.docx)**: Bridge to legacy workflows

**Export Options**:
- Single amendment
- All amendments for a document
- Amendments by status (e.g., only "Tabled")
- Include/exclude metadata (author, justification, timestamps)

## Technical Deep Dives

### Akoma Ntoso XML Processing

**What is Akoma Ntoso?**
- OASIS LegalDocumentML standard v1.0 (formerly Akoma Ntoso v3.0)
- XML vocabulary with 500+ elements for parliamentary documents
- "Akoma Ntoso" means "linked hearts" in Akan language (West Africa)
- Used by UN, EU institutions, Italian Senate, African parliaments

**FRBR Model** (Functional Requirements for Bibliographic Records):
1. **Work**: Abstract intellectual creation (e.g., "the Directive on renewable energy")
2. **Expression**: Specific version/translation (e.g., "English version, 2024 amendment")
3. **Manifestation**: Physical format (e.g., PDF, XML)
4. **Item**: Individual copy

**Key Elements for Amendment Markup**:
```xml
<mod>                        <!-- Modification wrapper -->
  <quotedStructure>          <!-- Proposed text -->
    <article eId="art_3">
      <num>Article 3</num>
      <paragraph eId="art_3_para_1">
        <content>
          <p>Text with <ins>additions</ins> and <del>deletions</del>.</p>
        </content>
      </paragraph>
    </article>
  </quotedStructure>
</mod>
```

**Amendment Types in XML**:
- `<mod>`: Modification to existing text
- `<ins>`: Insertion of new text
- `<del>`: Deletion of existing text
- `<subst>`: Substitution (delete + insert)

**Processing Pipeline**:
1. **Parse**: Load XML document with lxml
2. **Validate**: Check against XSD schema
3. **Extract**: Identify amendable elements (articles, paragraphs, points)
4. **Generate**: Create amendment XML with proper mod/ins/del markup
5. **Transform**: Convert XML to HTML for display
6. **Export**: Output to multiple formats

### Diff Algorithm for Track Changes

**Challenge**: Show meaningful legislative changes, not just character-level diffs.

**Approach**:
1. **Tokenize**: Split text into words and punctuation
2. **Myers Diff**: Standard algorithm for finding longest common subsequence
3. **Semantic Grouping**: Merge small adjacent changes into coherent edits
4. **Legislative Context**: Understand that changing "may" to "shall" is significant

**Example**:
```
Original:  "Member States may adopt national measures."
Amendment: "Member States shall adopt harmonized measures."

Render as:
Member States <del>may</del> <ins>shall</ins> adopt <del>national</del> <ins>harmonized</ins> measures.
```

**Implementation Libraries**:
- Python: `difflib` (standard library) + custom semantic grouping
- JavaScript: `diff-match-patch` or `jsdiff` for client-side preview

### AI Service Architecture

**Provider Abstraction**:
```python
class AIProvider(ABC):
    @abstractmethod
    async def draft_amendment(self, context: str, intent: str) -> str:
        pass
    
    @abstractmethod
    async def check_consistency(self, base_text: str, amendment: str) -> List[Issue]:
        pass
    
    @abstractmethod
    async def translate(self, text: str, from_lang: str, to_lang: str) -> str:
        pass

class OpenAIProvider(AIProvider):
    # Implementation using OpenAI SDK
    
class AnthropicProvider(AIProvider):
    # Implementation using Anthropic SDK
```

**Configuration**:
```python
AI_PROVIDER = "openai"  # or "anthropic"
OPENAI_API_KEY = "..."
ANTHROPIC_API_KEY = "..."
OPENAI_MODEL = "gpt-4-turbo-preview"
ANTHROPIC_MODEL = "claude-3-opus-20240229"
```

**Cost Management**:
- Token counting before API calls
- Caching frequent translations
- Rate limiting per user
- Cost tracking in database

**Privacy & Security**:
- All AI calls server-side (never from client JavaScript)
- API keys in environment variables, never in code
- Audit log of all AI requests
- Option to disable AI features for sensitive documents

### Database Schema

**Documents Table**:
```sql
CREATE TABLE documents (
    id UUID PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    celex_number VARCHAR(50),           -- EUR-Lex identifier
    document_type VARCHAR(50),          -- proposal, directive, regulation
    language VARCHAR(5) NOT NULL,       -- ISO 639-1 code
    xml_content TEXT NOT NULL,          -- Akoma Ntoso XML
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    created_by UUID REFERENCES users(id)
);
```

**Amendments Table**:
```sql
CREATE TABLE amendments (
    id UUID PRIMARY KEY,
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    element_id VARCHAR(200) NOT NULL,   -- Akoma Ntoso eId (e.g., "art_3_para_2")
    amendment_type VARCHAR(20) NOT NULL, -- modify, insert, delete
    status VARCHAR(20) DEFAULT 'candidate', -- candidate, tabled, withdrawn
    original_text TEXT,                 -- Text before amendment
    amended_text TEXT,                  -- Text after amendment
    justification TEXT,                 -- Explanation for amendment
    xml_content TEXT NOT NULL,          -- Akoma Ntoso amendment markup
    position_reference VARCHAR(500),    -- Human-readable position
    author_id UUID REFERENCES users(id),
    co_authors UUID[],                  -- Array of user IDs
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    tabled_at TIMESTAMP,
    withdrawn_at TIMESTAMP
);
```

**Users Table**:
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(200),
    organization VARCHAR(200),
    role VARCHAR(50) DEFAULT 'user',    -- user, admin
    created_at TIMESTAMP DEFAULT NOW(),
    last_login TIMESTAMP
);
```

**AI Audit Log**:
```sql
CREATE TABLE ai_requests (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    provider VARCHAR(50),               -- openai, anthropic
    model VARCHAR(100),
    request_type VARCHAR(50),           -- draft, consistency, translate
    input_tokens INTEGER,
    output_tokens INTEGER,
    cost_usd DECIMAL(10,6),
    created_at TIMESTAMP DEFAULT NOW()
);
```

## Development Phases

### Phase 1: Foundation (Week 1-2)

**Backend Setup**:
- Initialize FastAPI project structure
- Set up PostgreSQL with SQLAlchemy
- Create database models and migrations (Alembic)
- Implement JWT authentication
- Basic CRUD API endpoints

**Frontend Setup**:
- Initialize React + TypeScript + Vite project
- Configure Irvin font with @font-face
- Set up routing (React Router)
- Create layout components (Header, Sidebar)
- Configure API client (Axios or Fetch)

**Deliverable**: Working authentication and empty editor page

### Phase 2: XML Processing (Week 3-4)

**Backend**:
- Implement Akoma Ntoso parser with lxml
- XSD schema validation
- Extract amendable elements from XML
- Generate amendment XML with mod/ins/del markup
- XML to HTML transformation

**Frontend**:
- Display parsed document as hierarchical text
- Clickable elements with hover effects
- Document outline sidebar
- Position reference display

**Deliverable**: Can load and display EU legislative documents

### Phase 3: Amendment Creation (Week 5-6)

**Backend**:
- Amendment CRUD endpoints
- Status workflow validation (Candidate → Tabled → Withdrawn)
- Position reference generation
- Store amendments with metadata

**Frontend**:
- Context menu (Amend/New/Delete)
- Amendment modal with Original/Amendment tabs
- Author autocomplete
- Track changes rendering (bold/italic)
- Amendment markers in right margin

**Deliverable**: Can create, edit, and view amendments

### Phase 4: Amendment Management (Week 7-8)

**Backend**:
- Amendment list filtering/sorting
- Bulk operations
- Search functionality

**Frontend**:
- Two-column amendment view
- Amendment list with status filters
- Bulk actions (Table multiple, Delete multiple)
- Amendment card component

**Deliverable**: Full amendment lifecycle management

### Phase 5: Export Functionality (Week 9-10)

**Backend**:
- XML export (native Akoma Ntoso)
- HTML export with CSS styling
- PDF generation (WeasyPrint or ReportLab)
- Word (.docx) generation (python-docx)

**Frontend**:
- Export panel with format options
- Single vs. bulk export
- Download handling

**Deliverable**: Amendments exportable in all formats

### Phase 6: AI Integration (Week 11-13)

**Backend**:
- OpenAI SDK integration
- Anthropic SDK integration
- Provider abstraction layer
- Drafting assistant endpoint
- Consistency checker endpoint
- Translation endpoint
- Cost tracking

**Frontend**:
- AI drafting panel
- Consistency checker UI
- Translation assistant
- Justification generator
- AI suggestions display with disclaimers

**Deliverable**: AI-powered amendment assistance

### Phase 7: Multi-Language Support (Week 14-15)

**Backend**:
- Language detection from Akoma Ntoso
- Multi-language document storage
- Translation package generation

**Frontend**:
- i18next integration for UI (23 EU languages)
- Language switcher
- Multi-language document viewer
- Translation status tracking

**Deliverable**: Full multi-language support

### Phase 8: Polish & Testing (Week 16-17)

- Comprehensive testing (unit, integration, E2E)
- Performance optimization
- Error handling improvements
- Documentation
- User acceptance testing

**Deliverable**: Production-ready Brubru Amendator

## API Specification

### Authentication

```
POST /api/auth/register
POST /api/auth/login
POST /api/auth/refresh
GET  /api/auth/me
```

### Documents

```
GET    /api/documents                  # List documents
POST   /api/documents                  # Upload document
GET    /api/documents/{id}             # Get document
PUT    /api/documents/{id}             # Update document
DELETE /api/documents/{id}             # Delete document
GET    /api/documents/{id}/parse       # Parse and return structure
```

### Amendments

```
GET    /api/amendments                 # List amendments
POST   /api/amendments                 # Create amendment
GET    /api/amendments/{id}            # Get amendment
PUT    /api/amendments/{id}            # Update amendment
DELETE /api/amendments/{id}            # Delete amendment
PATCH  /api/amendments/{id}/status     # Change status
POST   /api/amendments/bulk-action     # Bulk operations
```

### Export

```
POST   /api/export/xml                 # Export to XML
POST   /api/export/html                # Export to HTML
POST   /api/export/pdf                 # Export to PDF
POST   /api/export/docx                # Export to Word
```

### AI Services

```
POST   /api/ai/draft                   # Generate amendment text
POST   /api/ai/consistency             # Check for conflicts
POST   /api/ai/translate               # Translate to languages
POST   /api/ai/justify                 # Generate justification
POST   /api/ai/usage                   # Get usage stats
```

## EU Parliamentary Procedures

### Amendment Lifecycle

1. **Candidate Status**: Draft amendment being refined
2. **Tabled Status**: Formally submitted to committee/plenary
3. **Withdrawn Status**: Retracted before voting

### Position Referencing

Amendments must specify exact location in legislative text:
- Article number
- Paragraph number (if applicable)
- Point letter (if applicable)
- Subpoint number (if applicable)

Example: "Article 3, paragraph 2, point (a), subpoint (i)"

Brubru automates this by extracting position from Akoma Ntoso structure.

### Multi-Language Requirements

EU legislative proposals exist simultaneously in 23 official languages:
- Bulgarian, Croatian, Czech, Danish, Dutch, English, Estonian, Finnish, French, German, Greek, Hungarian, Irish, Italian, Latvian, Lithuanian, Maltese, Polish, Portuguese, Romanian, Slovak, Slovenian, Spanish, Swedish

**Structural Consistency**: Articles, paragraphs, and points must appear at identical positions across all language versions.

Brubru validates this through XML schema validation during document loading.

### European Legislation Identifier (ELI)

Standard for referencing EU legislation:
```
http://data.europa.eu/eli/{type}/{year}/{number}[/{version}]

Example:
http://data.europa.eu/eli/dir/2024/123/oj
```

Akoma Ntoso URIs align with ELI for precise, machine-readable document referencing.

## Design Guidelines

### Visual Hierarchy

1. **Primary**: Amendment editing interface
2. **Secondary**: Document viewing and navigation
3. **Tertiary**: Amendment list and management

### Color Palette

- **Primary**: Professional blue (#1E3A8A)
- **Success**: Green for "Tabled" (#059669)
- **Warning**: Orange for "Candidate" (#D97706)
- **Danger**: Red for "Withdrawn" (#DC2626)
- **Neutral**: Grays for text and backgrounds

### Typography Scale

- **Headings**: Irvin font, bold
- **Body**: Irvin font, regular
- **Code/XML**: Monospace (JetBrains Mono or Fira Code)

### Interactive Elements

- **Hover**: Subtle background color change
- **Active**: Border or shadow indication
- **Disabled**: Reduced opacity (60%)

### Track Changes Styling

- **Additions**: Bold text, green underline
- **Deletions**: Strikethrough, red text
- **Original text**: Black, regular weight
- **Amended text**: Black, bold weight in amendments column

## Testing Strategy

### Unit Tests

- XML parsing functions
- Diff algorithm accuracy
- Amendment validation logic
- AI response parsing

### Integration Tests

- API endpoint behavior
- Database operations
- Authentication flow
- Export generation

### End-to-End Tests

- Create document → Create amendment → Export
- AI-assisted drafting workflow
- Multi-user collaboration scenarios

### Test Data

- Sample Akoma Ntoso documents from EUR-Lex
- Real European Parliament proposals
- Various amendment types (modify, insert, delete)
- Edge cases (very long documents, complex nested structures)

## Security Considerations

### Authentication & Authorization

- JWT tokens with refresh mechanism
- Role-based access control (user, admin)
- Password hashing with bcrypt
- Rate limiting on auth endpoints

### Data Protection

- HTTPS only in production
- Database credentials in environment variables
- API keys never in frontend code
- Input sanitization on all endpoints

### XML Security

- Validate against XSD schema before processing
- Limit XML file size (prevent billion laughs attack)
- Disable external entity resolution in XML parser

### AI Security

- Server-side API calls only
- Cost limits per user
- Audit logging of all AI requests
- Option to disable AI for sensitive documents

## Performance Optimization

### Frontend

- Code splitting by route
- Lazy loading of heavy components
- Memoization of expensive computations
- Virtual scrolling for long amendment lists

### Backend

- Database query optimization (indexes on foreign keys)
- Caching of parsed XML structures (Redis)
- Async/await for I/O operations
- Connection pooling for database

### XML Processing

- Stream parsing for large documents (SAX vs. DOM)
- Caching of XSD validation results
- Pre-compiled XPath expressions

## Deployment

### Local Development

```bash
# Start all services
docker-compose up

# Frontend: http://localhost:5173
# Backend: http://localhost:8000
# PostgreSQL: localhost:5432
```

### Production

- Docker containers on cloud provider (AWS, GCP, Azure)
- Nginx reverse proxy with SSL
- PostgreSQL managed database service
- Environment-based configuration
- Automated backups
- Monitoring and logging (Sentry, LogRocket)

## Future Enhancements (Post-MVP)

### Collaboration Features

- Real-time co-editing (WebSockets)
- Comments on amendments
- Approval workflows
- Version history with diffs

### Advanced AI

- Fine-tuned models on EU legislative corpus
- Amendment success prediction
- Automatic categorization by policy area
- Sentiment analysis of justifications

### Integration with EU Systems

- Direct import from EUR-Lex
- Connection to European Parliament databases
- OEIL (Legislative Observatory) integration
- Automated submission to parliamentary systems

### Analytics

- Amendment statistics
- Usage patterns
- Success rate tracking
- Policy area trends

## Resources & References

### Standards

- OASIS LegalDocumentML (Akoma Ntoso): http://docs.oasis-open.org/legaldocml/akn-core/v1.0/akn-core-v1.0.html
- European Legislation Identifier (ELI): http://data.europa.eu/eli

### EU Institutions

- EUR-Lex: https://eur-lex.europa.eu
- European Parliament: https://www.europarl.europa.eu
- OEIL Legislative Observatory: https://oeil.secure.europarl.europa.eu

### Tools & Libraries

- lxml: https://lxml.de/
- FastAPI: https://fastapi.tiangolo.com/
- React: https://react.dev/
- OpenAI API: https://platform.openai.com/docs/api-reference
- Anthropic API: https://docs.anthropic.com/claude/reference

## Conclusion

Brubru Amendator modernizes legislative amendment drafting by combining proven XML-first architecture with cutting-edge AI capabilities. By separating content from formatting, automating structural validation, and providing intelligent assistance, it enables legislative drafters to focus on policy substance rather than technical complexity.

The phased development approach ensures we build a solid foundation (XML processing, amendment workflows) before adding sophisticated AI features. Starting with snake_case files and Irvin font establishes professional design standards from day one.

This is the first component of the larger Brubru ecosystem. Once Amendator is production-ready, we'll build the Strategist (advocacy strategy), Analyser (policy analysis), and Scraper (data collection) to create a comprehensive EU policy engagement platform.

---

**Document Version**: 1.0  
**Last Updated**: January 2025  
**For**: Claude Code development reference
