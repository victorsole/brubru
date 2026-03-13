# Brubru: Your AI-Powered Strategic Advocacy Assistant

## What is Brubru?

Brubru is an AI-powered strategic advocacy assistant designed specifically for EU policy professionals, lobbyists, and organisations working within the Brussels institutional ecosystem. Developed by Beresol BV, Brubru combines cutting-edge conversational AI with specialised legislative tools to help users analyse policies, draft amendments, monitor EU legislative procedures, and navigate institutional processes with confidence.

The name "Brubru" is a playful nod to Brussels, the heart of the European Union's political machinery, where lobbyists, policy advisors, MEPs, and institutional staff navigate a complex web of legislation, procedures, and stakeholders every day.

---

## The Six Core Features

### 1. Brubru Chat - The AI Policy Advisor

Brubru Chat is the main interface - a context-aware conversational AI assistant powered by Anthropic Claude and OpenAI GPT-4. Unlike generic chatbots, Brubru is trained specifically on EU institutional knowledge.

**What you can ask Brubru:**
- "What's the current status of the AI Act?"
- "Which MEPs are most influential on digital policy?"
- "How does the ordinary legislative procedure work?"
- "What are the key deadlines for the Packaging Regulation?"

**Key capabilities:**
- Natural language queries about EU legislation and policy
- Strategic guidance on advocacy approaches
- Stakeholder mapping and voting pattern analysis
- Procedural coaching on EU institutional processes
- Document uploads (PDF, DOCX) for contextual analysis
- Citation tracking with source references

The AI models include Anthropic Claude (Sonnet 4 and Opus 4) as the primary engine, with OpenAI GPT-4 as a fallback, plus specialised legal models for document analysis.

---

### 2. Amendator - The Legislative Amendment Editor

Amendator is an XML-first legislative amendment authoring tool inspired by AT4AM (the European Parliament's official amendment tool), but enhanced with modern AI capabilities.

**How it works:**
- Two-column layout showing original text alongside your proposed amendment
- Click on any article, paragraph, or recital to propose changes
- AI-powered drafting assistance - describe what you want in natural language, and Brubru drafts the legal text
- Automatic position references (Article X, paragraph Y, point (a))
- Track changes visualisation with bold text for additions and strikethrough for deletions

**Technical compliance:**
- Full Akoma Ntoso XML compliance (the OASIS LegalDocumentML standard used by EU institutions)
- Multi-format export: XML, HTML, PDF, and Word
- Amendment workflow tracking: Candidate, Tabled, or Withdrawn status

---

### 3. My EU Bubble - The Personalised News Feed

My EU Bubble aggregates RSS feeds from over 15 EU institutional sources into one personalised dashboard.

**Sources include:**
- European Parliament (33+ topic and committee feeds)
- European Commission Directorate-Generals
- Council of the EU
- OEIL Legislative Observatory
- EPRS Think Tank research briefings
- General EU news feeds

**Features:**
- Subscribe and unsubscribe from feeds based on your interests
- Mark entries as read
- Save and bookmark items to collections
- Filter by category, source, or date
- Configurable email alerts

---

### 4. EU Law Comply - The Compliance Checker

EU Law Comply provides automated compliance gap analysis for EU regulations. This is particularly useful for organisations that need to assess how well their internal policies or products align with EU law.

**The process:**
1. Upload your documents (PDF, DOCX, or TXT)
2. The backend extracts text and identifies requirements
3. AI compares your document against relevant law cluster requirements
4. Receive a gap analysis with severity ratings
5. Export a detailed compliance report

**Reports include:**
- Overall compliance score (0-100%)
- Gap summary showing what's missing, partial, or unclear
- Detailed findings per requirement
- Recommended actions
- Export in PDF, Word, HTML, or JSON formats

---

### 5. Document Generator - AI-Powered Advocacy Documents

The Document Generator uses AI to create professional EU advocacy documents in seconds.

**Document types:**
- **Position Papers** - Structured policy positions with executive summary, background analysis, key asks, and recommendations
- **MEP Briefings** - Concise briefings optimised for busy Members of European Parliament, with clear asks and voting recommendations
- **Talking Points** - Quick-reference bullet points for meetings and calls

**Features:**
- Step-by-step wizard interface
- Link documents to specific EU legislation (via CELEX numbers) or procedures
- Add policy areas and custom tags
- Multiple key asks with article references
- Stakeholder identification
- Professional markdown formatting
- Copy to clipboard or save to your document repository

---

### 6. Legislative Tracking

Brubru provides real-time monitoring of EU legislative procedures through integration with official EU data sources.

**Data sources:**
- OEIL Legislative Observatory (over 21,600 procedures)
- Legislative Train Schedule (490 priority files from the Commission's work programme)
- European Parliament calendar
- Council working groups

**Tracking features:**
- Procedure status updates
- Committee assignments
- Voting schedules
- Timeline visualisation

---

## Who Uses Brubru?

Brubru is designed for anyone working in or around EU policy:

- **Lobbyists and consultants** tracking legislation affecting their clients
- **Trade association staff** drafting position papers and amendments
- **Corporate public affairs teams** monitoring regulatory developments
- **NGO advocacy officers** preparing briefings for MEPs
- **Think tank researchers** analysing legislative trends
- **Law firm associates** conducting EU regulatory research
- **Government affairs professionals** in EU member states

---

## Subscription Tiers

### White (Free)
For individuals exploring EU policy:
- Basic chat with GPT-3.5-turbo
- 5 amendments per month
- Basic export (XML and HTML only)
- Watermark on exports

### Yellow (Professional) - 79 euros per month
For individual consultants, lobbyists, and advocacy professionals:
- Advanced AI (GPT-4, Claude Sonnet)
- Unlimited amendments
- All export formats (XML, HTML, PDF, Word)
- No watermarks
- 1,000 API calls per month
- RSS alerts enabled
- Email support with 48-hour response

### Blue (Enterprise) - 599 euros per month
For large organisations, government agencies, and think tanks:
- Everything in Yellow
- Unlimited API calls
- Claude Opus (the most capable model)
- Multi-user accounts (5+ users)
- White-label support
- Dedicated account manager
- 24/7 priority support
- SLA with uptime guarantee
- Custom training modules

---

## Data Sources and Intelligence

Brubru aggregates information from over 15 authoritative EU institutional sources:

**Legislative and Legal Databases:**
- EUR-Lex - Official legislative texts, consolidated acts, and case law
- OEIL - Legislative procedure tracking
- EU Law Tracker - Commission legislative initiative tracking
- Publications Office - Official documents archive

**Parliamentary Data:**
- European Parliament - MEP data, committees, voting records
- Parliament Open Data - RDF/JSON-LD API with 7+ datasets
- Legislative Train Schedule - Commission priorities
- Think Tank (EPRS) - Research briefings and studies

**Institutional Intelligence:**
- Who's Who - Staff directories and organisation charts
- AssistEU - Procedural guidance
- Council of the EU - Council positions and working groups

**Research and Standards:**
- Joint Research Centre - Scientific research and technical reports
- IATE - EU terminology database in 24 languages
- EU Style Guide - Writing standards

---

## Technology

Brubru is built with modern, scalable technology:

**Frontend:** React 18 with TypeScript, built with Vite
**Backend:** FastAPI (Python) with SQLAlchemy
**Database:** PostgreSQL
**AI:** Anthropic Claude (primary), OpenAI GPT-4 (secondary)
**Multilingual:** Available in 6 languages (EN, FR, NL, ES, CA, IT) via i18next

The platform follows WCAG 2.1 Level AA accessibility standards and uses the Irvin font (inspired by The New Yorker) for a distinctive typographic identity.

---

## Contact

- **Website:** brubru.beresol.eu
- **Email:** hello@beresol.eu
- **Company:** Beresol BV

---

*Brubru - Empowering strategic advocacy in the EU bubble*

*Built with care in Brussels by Beresol BV*
