# Brubru Business Plan

**Company:** Beresol BV
**Product:** Brubru -- AI-Powered Strategic Advocacy Platform for EU Policy
**Version:** 1.0
**Date:** February 2026
**Stage:** Pre-revenue, product built
**Location:** Brussels, Belgium

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem](#2-problem)
3. [Solution](#3-solution)
4. [Product](#4-product)
5. [Market Opportunity](#5-market-opportunity)
6. [Competitive Landscape](#6-competitive-landscape)
7. [Business Model](#7-business-model)
8. [Technology & Architecture](#8-technology--architecture)
9. [Traction & Current State](#9-traction--current-state)
10. [Go-to-Market Strategy](#10-go-to-market-strategy)
11. [Financial Model](#11-financial-model)
12. [Team](#12-team)
13. [Risks & Mitigations](#13-risks--mitigations)
14. [Roadmap](#14-roadmap)
15. [Funding & Use of Proceeds](#15-funding--use-of-proceeds)
16. [Appendices](#16-appendices)

---

## 1. Executive Summary

**All the EU with AI.**

Brubru is an AI-powered strategic advocacy platform purpose-built for EU policy professionals. It combines a conversational AI assistant with specialised legislative tools -- amendment drafting, compliance analysis, funding intelligence, legislative monitoring, and predictive analytics -- to replace the fragmented workflow of lobbyists, consultants, trade associations, and government affairs teams operating within the Brussels ecosystem.

The EU public affairs market is valued at EUR 3-5 billion annually. Today, this work is done by expensive human consultants charging EUR 250-500/hour, using generic tools (Word, Excel, email forwards, ChatGPT) that have no understanding of EU institutional procedures. Brubru encodes deep procedural knowledge from 15+ EU institutional data sources into an AI platform that produces analyst-grade work at software costs.

**Vision:** From AI-powered advocacy platform to the **system of record for EU affairs** -- the single workspace where a professional's entire dossier lives: tracked legislation, drafted amendments, MEP relationships, stakeholder positions, predictions, documents, and campaign history. Then expand nationally: 27 Member States, every level of governance, one platform per country. Nobody in EU affairs has a dossier management system powered by real-time institutional data and AI. That's the product.

**Key facts:**
- Product fully built: 9 core features, 45+ API endpoints, 35 data scrapers, 30+ database models
- 4-tier AI provider chain (Mistral primary) keeping costs at EUR 8/user/month
- Modular pricing: Individual modules (from EUR 19/month), Bundles (Starter EUR 39, Advocate EUR 59, Professional EUR 99), EP Plan (EUR 49/month)
- Gross margins of ~85% across all plans
- Break-even at ~55 subscribers at blended ARPU of EUR 55/month (EUR 3,025 MRR)
- **Primary metric: Weekly Active Paid Users (WAPU) -- target 10 by Month 3**
- Founder: 7+ years European Parliament, 10+ years EU policy advisory

---

## 2. Problem

### The EU Policy Professional's Daily Reality

EU policy professionals -- lobbyists, trade association staff, corporate government affairs teams, NGO advocacy officers, law firm associates -- face a uniquely complex working environment:

**Fragmented information landscape.** Legislative activity is scattered across 15+ institutional sources: EUR-Lex, OEIL, the Legislative Train Schedule, EP committee agendas, Council working groups, the Commission's "Have Your Say" portal, EPRS research briefings, and more. There is no single interface. Professionals spend 2-4 hours daily just monitoring developments.

**Arcane procedural knowledge.** The ordinary legislative procedure, consent procedure, consultation procedure, comitology, trilogues, conciliation committees -- EU institutional processes are genuinely difficult. A misunderstanding of procedure can render months of advocacy work moot. This expertise takes years to develop and is currently locked inside the heads of senior consultants.

**Expensive, manual deliverables.** Position papers, MEP briefings, amendment packages, stakeholder mappings, compliance assessments -- these are the core work products of advocacy. They are produced manually, by expensive humans, from scratch each time. A typical Brussels consultancy charges EUR 5,000-15,000 for a position paper that takes a senior consultant 3-5 days.

**No purpose-built tools.** US political intelligence has FiscalNote, Quorum, and Bloomberg Government. Legal AI has Harvey (valued at $3B+). EU policy has nothing. Professionals use Word, email, and generic ChatGPT -- tools that don't understand the difference between a COD procedure and a CNS procedure, or why a rapporteur's draft matters more than a shadow rapporteur's.

### Quantifying the Pain

| Pain Point | Time Wasted | Cost Impact |
|------------|------------|-------------|
| Monitoring 15+ EU sources daily | 2-4 hours/day | EUR 500-1,000/day in consultant time |
| Drafting a position paper | 3-5 days | EUR 5,000-15,000 per deliverable |
| Understanding procedure for new dossier | 1-2 days research | EUR 2,000-4,000 per dossier |
| Tracking amendments across committees | Continuous | EUR 2,000+/month in staff time |
| Compliance gap analysis for new regulation | 2-4 weeks | EUR 20,000-50,000 per assessment |
| Finding relevant EU tenders | 1-2 hours/day | Missed opportunities worth EUR 100K+ |

---

## 3. Solution

Brubru replaces fragmented workflows with a single AI-powered platform that understands EU institutional procedures natively. It is not a chatbot with EU data bolted on -- it is a purpose-built advocacy workbench where every feature is designed around the specific deliverables and workflows EU policy professionals produce daily.

### Core Thesis

**All the EU with AI.** Encode 20 years of Brussels expertise into software. The EU institutional knowledge that currently resides in the minds of senior consultants -- procedural understanding, political dynamics, institutional contacts, legislative history -- can be systematised, kept current through automated data pipelines, and made accessible through AI at a fraction of the cost. And then extend it: from EU institutions to every Member State, from legislation to funding, from Brussels to every European capital.

### From Workflow Platform to System of Record

Brubru has built an exceptionally strong **vertical workflow platform** (Layer 3) with 10 feature verticals, 35 scrapers, 18 API clients, and 11 prediction services. The next strategic step is the transition to **system of record** (Layer 4): tying all features together around the concept of a **user-owned dossier** -- a workspace per legislative file where tracking, amendments, contacts, predictions, and documents accumulate into an asset the user cannot replicate elsewhere.

| Layer | Description | Brubru Status |
|-------|-------------|---------------|
| **Layer 1** -- Foundation models | OpenAI, Claude, Mistral, Gemini | Done (4-provider chain, model-agnostic) |
| **Layer 2** -- Generic wrappers | Chat interfaces over LLMs | Present (Brubru Chat) but not the core |
| **Layer 3** -- Workflow platform | Domain-specific tools, structured data, automation | Substantially built (10 verticals) |
| **Layer 4** -- System of record | Where work accumulates; user data creates switching costs | Next phase (dossier workspaces) |

**Why this matters:** Today, the system of record for EU affairs is fragmented across Outlook, Excel, shared drives, and mental models. Nobody owns this. A lobbyist who has 50 annotated dossiers, 200 MEP contacts with meeting notes, and 18 months of prediction history inside Brubru will never leave -- regardless of what happens with foundation models. That is structural lock-in.

### How Brubru Solves Each Pain Point

| Pain Point | Brubru Solution | Time Saved |
|------------|----------------|------------|
| Monitoring 15+ sources | My EU Bubble: unified RSS dashboard with 33+ feeds + My EU Calendar (274+ events from EP, Council, Commission, ECB) | 80% reduction |
| Drafting deliverables | Document Generator: AI position papers, MEP briefings in minutes | 90% reduction |
| Understanding procedure | Chat: AI assistant trained on EU institutional knowledge | 70% reduction |
| Tracking amendments | Amendator: XML-first amendment editor + MEP Amendment Analysis with AI comparative scoring (best allies, coverage gaps, political landscape) | 60% reduction |
| Compliance assessment | EU Law Comply: automated gap analysis with severity ratings | 85% reduction |
| Finding funding & tenders | Tenderator / GrantBru: AI-matched funding feed with bid checklists | 75% reduction |

---

## 4. Product

Brubru is a fully built platform with nine core features including a predictive analytics engine, an institutional calendar, MEP amendment analysis with AI-powered comparative scoring, and comprehensive legislative tracking infrastructure.

### 4.1 Brubru Chat -- The AI Policy Advisor

The primary interface. A context-aware conversational AI assistant powered by a 4-tier provider chain (Mistral, Claude, GPT-4, Gemini) with EU-specific context injection.

**Capabilities:**
- Natural language queries about EU legislation, procedure, and policy
- Strategic advocacy guidance (how to approach a dossier, who to talk to, what arguments work)
- Document uploads (PDF, DOCX) for contextual analysis
- Citation tracking with source references
- Conversation memory and quality scoring
- Beresol Knowledge Bundle integration (11 policy reports, 7 live monitors)

**Context sources injected per query:**
- Legislative procedure status (from OEIL, Legislative Train)
- EPRS research briefings (matched by procedure reference)
- Committee work in progress (26 EP committees tracked)
- Commission documents (COM, SWD, SEC, C, JOIN, OJ, PV from EC Register)
- Public consultations (from Commission's "Have Your Say" portal)
- Beresol open reports and monitors
- EUR-Lex legislation and case law

### 4.2 Amendator -- The Legislative Amendment Editor

An XML-first legislative amendment authoring tool modelled on the European Parliament's AT4AM system, enhanced with AI.

**Features:**
- Two-column layout: original text vs. proposed amendment
- Click-to-amend on any article, paragraph, or recital
- AI drafting: describe changes in natural language, get legal text
- Akoma Ntoso XML compliance (OASIS LegalDocumentML standard)
- Track changes visualisation (bold for additions, strikethrough for deletions)
- Multi-format export: XML, HTML, PDF, Word
- Amendment workflow: Candidate, Tabled, Withdrawn
- Link amendments to Legislative Train carriages

**MEP Amendments -- Real Parliamentary Data:**

Brubru fetches and parses actual EP committee amendment documents from the European Parliament Open Data Portal and OEIL, giving users access to the real amendments tabled by MEPs for any legislative procedure.

- Browse all committee amendments by procedure, with political group breakdown and hotspot analysis (most-amended articles/recitals)
- Filter by political group, amendment type (modification, suppression, addition), element reference, or MEP name
- Word-level diff highlighting: additions in bold-italic, deletions struck-through -- exactly how amendments appear in EP documents
- Group activity bars showing which political groups are most active on a dossier
- Justification text and "on behalf of group" indicators

**AI-Powered Comparative Analysis:**

The signature differentiator. Users provide their policy position (free text), and Brubru's AI scores every MEP amendment on a -2 to +2 alignment scale:

| Score | Meaning |
|-------|---------|
| +2 | Strongly aligned -- directly advances the user's goals |
| +1 | Partially aligned -- moves in a similar direction |
| 0 | Neutral or unrelated |
| -1 | Partially opposed -- moves against the user's goals |
| -2 | Strongly opposed -- directly contradicts the user's position |

From these scores, Brubru computes three strategic outputs:

1. **Best Allies** -- Top 15 MEPs ranked by average alignment score. Identifies who is pushing amendments closest to the user's position, enabling targeted outreach.
2. **Coverage Gaps** -- Compares elements the user has amended against elements MEPs have amended. Reveals "blind spots" (articles MEPs are amending that the user hasn't touched) and "user-unique" elements (the user's original contributions that no MEP has proposed).
3. **Political Landscape** -- Classifies political groups as supportive (avg >= 1.0), mixed (-0.5 to 1.0), or opposed (< -0.5). Gives the user an instant read on political dynamics for their position.

Scores are cached per user and policy position (SHA-256 hashed), so repeat analyses are instant.

**Unique advantage:** No other tool combines AT4AM-style amendment editing with AI drafting assistance, Akoma Ntoso compliance, real MEP amendment data, and AI-powered alignment scoring. Users can draft their own amendments, see what MEPs are proposing, and instantly identify allies and opponents -- all in one platform.

### 4.3 My EU Bubble -- The Personalised Intelligence Dashboard

A unified RSS feed aggregator and legislative monitoring hub.

**RSS Intelligence (33+ feeds):**
- European Parliament (committee feeds, plenary, press)
- European Commission (DG-specific feeds)
- Council of the EU
- OEIL Legislative Observatory
- EPRS Think Tank research briefings
- General EU news

**Legislative Tracking Tabs:**
- My EU Calendar (aggregated institutional calendar from 6 data sources -- EP sessions, committee weeks, 26 EP committee draft agendas, Council/European Council meetings, Commission College weekly meetings with published agenda enrichment via EC Register OJ documents, ECB Governing Council -- month/week/day views with institution, committee, and policy area filters, "My EU Today" daily digest with AI summary for Professional bundle, 274+ events synced)
- Legislative Train Schedule (490+ priority files from Commission work programme)
- Committee Work in Progress (26 EP committees, all procedure types)
- Commission Documents (COM, SWD, SEC, C, JOIN, OJ, PV from EC Register with RegDoc API enrichment)
- EC Public Consultations (open, closed, outcomes from "Have Your Say" portal)
- Predictions (AI-powered legislative outcome forecasting)
- Analytics (reading patterns, topic interests)

**Features per tab:**
- Subscribe/unsubscribe from feeds
- Track/untrack legislative files and consultations
- Save and bookmark entries to collections
- Filter by category, source, date, committee, procedure type
- Stage pipeline visualisation for legislative progress

### 4.4 EU Law Comply -- The Compliance Checker

Automated compliance gap analysis for EU regulations.

**Process:**
1. Upload organisational documents (PDF, DOCX, TXT)
2. AI extracts text and identifies regulatory requirements
3. Comparison against relevant law cluster requirements (AI Act, GDPR, NIS2, CSRD, etc.)
4. Gap analysis with severity ratings
5. Action plan timeline with prioritised remediation steps

**Output:**
- Overall compliance score (0-100%)
- Gap summary: missing, partial, unclear items
- Detailed findings per requirement
- Recommended actions with deadlines
- Export: PDF, Word, HTML, JSON

**Law browser:** Browse EU legal clusters, view individual requirements, track compliance history.

### 4.5 Tenderator / GrantBru -- The EU Funding Intelligence Engine

AI-powered EU funding matching and bid assistance (Professional bundle and Tenderator module).

**Current scope (Tenderator):** TED (Tenders Electronic Daily) via SPARQL and eForms API -- EU public procurement.

**Planned evolution (GrantBru):** Expand from procurement to cover ALL EU funding and subsidies:
- EU Funding & Tenders Portal (Horizon Europe, Digital Europe, CEF, LIFE, Erasmus+)
- AGRIP (agricultural grants and rural development funds)
- EIC Accelerator and EIC Pathfinder (innovation grants + equity)
- EIB / EIF instruments (InvestEU, venture debt, SME guarantees)
- Structural and Cohesion Funds (ERDF, ESF+, Cohesion Fund)
- Recovery and Resilience Facility (national recovery plans)
- Member State co-financing and national subsidy schemes

**Features:**
- Organisation profile setup (CPV codes, regions, capacity)
- AI-matched funding feed (scored by relevance to profile)
- SME suitability scoring (multi-criteria weighted analysis)
- Bid/application checklist generator
- Funding calendar with deadline tracking
- Funding detail view with requirements extraction
- SPARQL analytics for market intelligence
- HuggingFace-powered tender classification and summarisation

### 4.6 Document Generator -- AI Advocacy Documents

Produces professional EU advocacy documents through a step-by-step wizard.

**Document types:**
- **Position Papers** -- Executive summary, background analysis, key asks, recommendations
- **MEP Briefings** -- Concise briefings optimised for MEPs with clear asks and voting recommendations
- **Talking Points** -- Quick-reference bullet points for meetings and calls

**Features:**
- Link to specific EU legislation (CELEX numbers) or procedures
- Policy area and custom tag assignment
- Multiple key asks with article references
- Stakeholder identification
- Professional markdown formatting with Brubru branding

### 4.7 Predictions Engine -- AI Legislative Forecasting

AI-powered predictive analytics for legislative outcomes (February 2026).

**Prediction types:**

| Prediction | Method | Tier |
|------------|--------|------|
| Timeline prediction | Survival analysis on historical procedure durations | Bubble module / Bundles |
| Outcome prediction | Multi-feature analysis (procedure type, committee, political dynamics) | Bubble module / Bundles |
| EP plenary vote forecast | EP group position analysis (9 groups, 720 MEPs) | Bubble module / Bundles |
| Council vote prediction | QMV calculator + member state position inference | Professional only |
| Resolution leading indicators | Resolution-to-legislation matching (OEIL cross-ref, title similarity) | Bubble module / Bundles |
| QMV calculator | 27 member states, population-weighted qualified majority thresholds | Bubble module / Bundles |

**Built on existing algorithmic foundation:**
- BM25 + semantic search (hybrid, 60/40 weighted)
- Reciprocal Rank Fusion (k=60)
- Authority boosting (EUR-Lex=1.0, Parliament=0.9, OEIL=0.8)
- Recency boosting (180-day half-life exponential decay)
- EuroVoc classification
- HuggingFace multilingual embeddings

### 4.8 Feedback System -- The Improvement Engine

Every user interaction generates structured signals that systematically improve Brubru's AI quality, data coverage, and product roadmap. The full advocacy workflow becomes a loop: Analyse > Monitor > Draft > Comply > Bid > **Improve**.

**4 Feedback Channels:**

| Channel | Source | Mechanism |
|---------|--------|-----------|
| Brubru Chat (inline) | Every AI response | Three-button system: Helpful (+2.0), Not helpful (-1.0), Hallucination report (-3.0) with optional correction text |
| My EU Bubble | Dashboard pages | Feedback invitation cards (card + sidebar variants) linking to structured form or email |
| General Feedback Form | Amendator, EU Law Comply, Tenderator | Structured fields: type (bug/feature request/general), title, description, category, affected feature, screenshot URL. Auto-captures browser and device metadata |
| Passive Analytics | All AI interactions | Automatic logging of: provider used, tokens consumed, response time, sources cited, context tiers, knowledge gap indicators. Zero user friction |

**Processing Pipeline:**

| System | Function |
|--------|----------|
| `feedback_submissions` table | Central store with type, priority (low/medium/high/critical), status lifecycle (new > in_review > in_progress > resolved), admin notes, assignment, and full audit trail via `admin_activity_log` |
| Conversation Quality Service | Automated scoring (0-10) per conversation. Weighted signals: positive feedback (+2.0), negative (-1.0), hallucination (-3.0), knowledge gap (-1.0), follow-up engagement (+0.5), high-tier sources (+0.5 each). Ratings: Excellent (9-10), Good (7-8), Neutral (4-6), Poor (2-3), Critical (0-1) |
| Knowledge Gap Tracker | When AI cannot answer, the gap is categorised by missing data type (legislation, procedure, MEP, date, statistic, document) and root cause (not_indexed, not_fetched, not_exists, outdated). Each gap is tracked until resolved |

**5 Systematic Improvement Loops:**

1. **Knowledge Base Expansion.** Knowledge gaps (not_indexed, not_fetched) trigger new scraper runs or source additions. Gaps marked not_exists are flagged for future data partnerships. Resolved gaps include resolution notes for institutional memory.
2. **Context Builder Tuning.** Source tier usage analytics reveal which data sources produce the highest-quality answers. High-tier sources (Tier 1-2: OEIL, EUR-Lex) boost quality scores. Under-performing sources are deprioritised or replaced.
3. **Hallucination Suppression.** Hallucination reports carry the highest negative weight (-3.0). Patterns in flagged responses reveal prompt weaknesses or source gaps. Correction text from users provides ground truth for targeted fixes.
4. **Provider Optimisation.** Chat analytics track quality and cost per AI provider. If Mistral's quality drops on specific query types, fallback chain routing is adjusted. Response time, token usage, and satisfaction are correlated per provider.
5. **Product Roadmap Prioritisation.** Feature requests and bug reports flow into the admin panel with filtering by type, priority, and category. Aggregate statistics surface the most impactful improvements.

**Admin Dashboard** -- All feedback, analytics, hallucination reports, knowledge gaps, quality scores, and assignment tracking converge in a single command centre.

### 4.9 Admin Panel

Full back-office for platform management:
- User management and subscription oversight
- Feed management (add/edit/deactivate RSS sources)
- Amendment oversight
- Legislative tracking admin
- Chat analytics and conversation quality metrics
- Tender management
- EU Comply law cluster management
- Notifications centre
- Feedback management
- System monitoring

---

## 5. Market Opportunity

### 5.1 Market Sizing

**EU Public Affairs Market:**

| Segment | Estimated Size | Source |
|---------|---------------|--------|
| EU lobbying expenditure (declared) | EUR 3.1 billion/year | EU Transparency Register |
| Brussels-based consultancies | EUR 800 million/year | Industry estimates |
| In-house EU affairs teams (corporate) | EUR 1.5 billion/year | Trade association data |
| Law firms (EU regulatory practice) | EUR 500 million/year | Legal market data |
| Trade associations | EUR 300 million/year | Association surveys |

**Total Addressable Market (TAM):** EUR 3-5 billion

**Serviceable Addressable Market (SAM):** The portion addressable by software rather than human relationships -- information gathering, analysis, drafting, monitoring -- estimated at 40% of total: EUR 1.2-2 billion.

**Serviceable Obtainable Market (SOM):** Year 1 target of EUR 130K ARR represents 0.01% of SAM, implying massive headroom.

### 5.2 Target Segments

**Primary (Year 1):**

| Segment | Count in Brussels | Willingness to Pay | Tier Fit |
|---------|-------------------|---------------------|----------|
| Independent consultants/lobbyists | ~5,000 | Medium (EUR 19-59/mo) | Individual modules / Starter-Advocate bundles |
| SME trade associations (< 20 staff) | ~2,000 | Medium-High (EUR 59-99/mo) | Advocate-Professional bundles |
| Corporate government affairs teams | ~1,500 | High (EUR 99+/mo) | Professional bundle / EP Plan |

**Secondary (Year 2-3):**

| Segment | Count | Tier Fit |
|---------|-------|----------|
| Law firms with EU regulatory practice | ~500 | Professional bundle |
| NGOs with EU advocacy programmes | ~1,000 | Starter-Advocate bundles |
| National permanent representations | 27 | Professional (enterprise) |
| EU institutions (internal use) | 7 major bodies | Enterprise/custom |
| Academic/think tank researchers | ~2,000 | Individual modules / EP Plan |

### 5.3 Market Timing

Three forces create a once-in-a-generation window:

1. **Regulatory wave (2026-2028).** AI Act, MiCA, CSRD, NIS2, DORA, Packaging Regulation, CSDDD, Net-Zero Industry Act, Critical Raw Materials Act -- an unprecedented volume of EU regulation reaching implementation deadlines simultaneously. Every affected organisation needs compliance analysis and advocacy capacity *now*.

2. **AI capability threshold.** Large language models crossed the quality threshold for analyst-grade regulatory work in 2024-2025. For the first time, AI can produce position papers, amendment drafts, and compliance assessments that are genuinely useful to professionals rather than merely interesting.

3. **Market vacancy.** US political intelligence has FiscalNote ($1.5B at IPO), Quorum, Bloomberg Government. Legal AI has Harvey ($3B+ valuation). EU policy intelligence has *no* purpose-built AI platform. Brubru enters an empty category.

---

## 6. Competitive Landscape

### 6.1 Competitive Matrix

| Competitor | Type | EU Focus | AI Chat | Amendments | MEP Amendment Analysis | Calendar | Compliance | Predictions | Tenders | Price |
|------------|------|----------|---------|------------|------------------------|----------|------------|-------------|---------|-------|
| **Brubru** | AI platform | Deep (35 scrapers) | Yes | Yes (Akoma Ntoso XML) | Yes (AI alignment scoring) | Yes (6 sources) | Yes | Yes | Yes | EUR 19-99/mo |
| **Dixit** | AI monitoring | Yes (Brussels) | No | Analysis only | No | No | No | No | No | Mid-range (est.) |
| **POLITICO Pro** | Journalism | Yes (100+ reporters) | No | No | No | No | No | No | No | EUR 7K-50K+/yr |
| **SAVOIRR** | AI platform | Yes | No | No | No | No | No | No | No | Not disclosed |
| **FiscalNote EUIT** | Hybrid | Yes (Brussels analysts) | No | Generic text (new) | No | No | No | Partial | No | EUR 10K-30K/yr |
| **Moonlit.ai** | Legal AI | 16+ Member States | Partial (Luna) | No | No | No | No | No | No | Enterprise |
| **LEOS** | Open-source editor | EU institutions only | No | Yes (AKN XML) | No | No | No | No | No | Free (internal) |
| **Cogrant** | Grant AI | Grants only | No | No | No | No | No | No | Yes | Not disclosed |
| ChatGPT / Claude.ai | Generic AI | None | Yes | No | No | No | No | No | No | $20/mo |
| Traditional consultancy | Human services | Yes | No | Manual | Manual | No | Manual | No | No | EUR 10K+/mo |

**Competitor profiles:**

- **Dixit (Paris) -- Highest threat.** Built "by lobbyists, for lobbyists." 200+ users including APCO, Burson, FTI, and Grayling. Monitors legislative files, analyses amendments, tracks EP transcripts and EC consultations, maps stakeholders. However, Dixit only **analyses** amendments -- it cannot **draft** them. No AI chat, no compliance gap analysis, no legislative predictions, no QMV calculator, no document generation, no funding/tender matching.

- **POLITICO Pro -- Industry standard.** 850+ organisations, 45,000+ subscribers, 91% renewal. Massive journalistic moat (100+ reporters). Recently partnered with Capitol AI for AI-generated summaries. But it is a media product, not a workflow tool -- no amendment drafting, no compliance, no predictions, no AI chat. Costs EUR 7,000-50,000+/year (7-30x Brubru's price).

- **SAVOIRR -- AI-native PA platform.** Similar "AI for public affairs" positioning. Offers document insights, real-time alerts, AI stakeholder identification, and competition tracking (tracks allies and opponents). Lacks amendment drafting, legislative predictions, AI chat, QMV calculator, and funding matching.

- **FiscalNote EUIT -- NYSE-listed incumbent.** $180M+ raised, Brussels office with in-house analysts. Recently added AI legislative drafting, but generic text only (no Akoma Ntoso XML). US-first DNA means the EU product is secondary. Enterprise pricing (EUR 10K-30K/year) excludes individual professionals.

- **Moonlit.ai -- Legal AI, not advocacy.** Amsterdam-based Deloitte spinout (Aug 2024), VC-backed, Microsoft partner. 10M+ EU legal documents across 16+ Member States. Strong on cross-jurisdictional case law search. But Moonlit serves **lawyers doing legal research**, not **policy professionals doing advocacy**. No amendments, no compliance, no predictions, no document generation, no funding matching. Moonlit helps you find law; Brubru helps you influence it.

- **LEOS -- Only other Akoma Ntoso tool.** European Commission's open-source XML legislation editor. Used by EU institutions and some Member State parliaments. Institutional software only: requires technical deployment, no AI, no commercial model. Brubru wraps Akoma Ntoso in a commercial AI-powered platform accessible to external stakeholders.

- **Cogrant -- GrantBru competitor.** Lithuanian AI-powered grant writing for Horizon Europe, Erasmus+, Digital Europe. Direct competitor to Brubru's GrantBru module. But grant-only: no legislative context, no monitoring, no amendments, no compliance.

### 6.2 Competitive Advantages

**1. Workflow completeness vs. Dixit/SAVOIRR.** No competitor covers the full advocacy cycle: monitor (My EU Bubble, EU Calendar) > analyse (Chat, MEP Amendments) > draft (Amendator, Document Generator) > compare (AI Comparative Analysis: alignment scoring, best allies, coverage gaps, political landscape) > comply (EU Law Comply) > predict (Predictions) > bid (Tenderator). Dixit covers monitoring and analysis but not creation. SAVOIRR covers monitoring but not drafting or predictions. Each Brubru feature is useful alone; together they create compounding lock-in.

**2. Akoma Ntoso XML + MEP Amendment Intelligence vs. FiscalNote/LEOS.** Brubru's Amendator produces XML-compliant legislative amendments in the OASIS LegalDocumentML standard used by EU institutions, *and* lets users compare their amendments against real MEP committee amendments with AI-powered alignment scoring. FiscalNote's new AI drafting generates generic text, not standards-compliant XML, and has no MEP amendment analysis. LEOS uses AKN but is institutional-only software with no AI. No competitor offers the closed loop: draft your amendment, see what MEPs proposed, identify allies, spot gaps in your strategy.

**3. 10x price advantage vs. POLITICO Pro/FiscalNote.** POLITICO Pro costs EUR 7,000-50,000+/year; FiscalNote EUIT costs EUR 10,000-30,000/year. Brubru charges EUR 228-1,188/year (individual modules from EUR 19/mo, Professional bundle EUR 99/mo) with Mistral as primary AI (EUR 0.20/M tokens vs. Claude's EUR 3.00/M -- a 15x cost advantage), enabling ~85% gross margins. This opens the market to individual consultants, small associations, and NGOs that enterprise tools exclude.

**4. Domain depth vs. ChatGPT/generic AI.** 35 purpose-built scrapers, 15+ institutional data pipelines, structured procedural knowledge (committee codes, procedure types, EP group compositions, QMV thresholds), 11 policy reports and 7 live monitors. Generic AI hallucinates EU procedures and lacks real-time legislative data. This is 18 months of domain engineering that would take any competitor significant time to replicate.

**5. Founder-market fit vs. all.** 7+ years inside the European Parliament plus 10+ years in EU policy advisory. The product is built by someone who has personally produced every deliverable it automates. Dixit was built by lobbyists; Brubru was built by a parliamentary insider.

**6. Structural defensibility through accumulated user data.** Feature comparisons matter at launch. Long-term defensibility comes from switching costs. Brubru's path to un-replicable value is the user-owned dossier: when a professional has 50+ legislative files tracked, 200+ MEP contacts annotated, 18 months of amendment history, and 30+ generated position papers inside the platform, the cost of switching to a competitor -- or to raw ChatGPT -- becomes prohibitive. This is the difference between a workflow tool and a system of record.

**7. The foundation model threat -- and why Brubru is defended.** The risk is not another SaaS competitor replicating 35 scrapers and 10 workflow verticals. It is Anthropic, OpenAI, or Google adding EU policy plugins. Defence against this is threefold: (1) depth of structured pipelines that general-purpose plugins cannot match, (2) the workflow layer around the data -- amendment drafting in Akoma Ntoso, QMV calculation, compliance gap analysis -- that requires domain engineering, not just data access, and (3) the system-of-record layer: user-accumulated dossiers, contacts, and documents that live inside Brubru and nowhere else.

### 6.3 Defensibility Over Time

| Year | Moat Layer |
|------|------------|
| Year 1 | Domain expertise + first-mover in EU AI policy tools |
| Year 2 | Data network effects (user interactions improve AI context quality) |
| Year 3 | Switching costs (dossier workspaces, amendments, contacts, compliance history) |
| Year 4 | System of record: accumulated user data makes switching prohibitive |
| Year 5 | Institutional partnerships (if EU institutions adopt internally) |

---

## 7. Business Model

### 7.1 Revenue Model: Freemium SaaS + Services

**Primary revenue: Modular SaaS subscriptions**

**Individual Modules** (mix and match):

| Module | Price | Key Capability |
|--------|-------|----------------|
| Brubru Chat | EUR 29/mo | AI policy advisor with EU context injection |
| My EU Bubble | EUR 29/mo | RSS intelligence, legislative tracking, EU Calendar |
| Amendator | EUR 19/mo | Legislative amendment editor (Akoma Ntoso XML) |
| EU Law Comply | EUR 29/mo | Compliance gap analysis |
| Tenderator | EUR 49/mo | EU funding intelligence and tender matching |

**Bundles** (save vs. individual modules):

| Bundle | Price | Includes | Saving |
|--------|-------|----------|--------|
| Starter | EUR 39/mo (EUR 33/mo annual) | Chat + Bubble | ~33% vs. modules |
| Advocate | EUR 59/mo (EUR 50/mo annual) | Chat + Bubble + Amendator | ~23% vs. modules |
| Professional | EUR 99/mo (EUR 84/mo annual) | All 5 modules + Predictions + Council analysis + priority support | ~36% vs. modules |

**EP Plan** (purpose-built for European Parliament):

| Plan | Price | Target |
|------|-------|--------|
| EP Plan | EUR 49/mo (EUR 42/mo annual) | MEPs, parliamentary assistants, EP staff -- tailored feature set for in-house parliamentary work |

**Free Trial:** 14-day full access to all features, no credit card required.

**Upgrade triggers:**
- Free trial to modules: Trial expires, need continued access to specific tools
- Modules to bundles: Using 2+ modules individually costs more than a bundle
- Bundles to Professional: Need Tenderator, Council analysis, Predictions, priority support

**Secondary revenue (future):**
- AI-native agency model: Sell finished deliverables (position papers at EUR 3,000-5,000, compliance assessments at EUR 15,000) produced at software cost
- Custom enterprise contracts for large organisations
- API access for integration into existing workflow tools
- Training and onboarding services

**Pricing evolution.** The current modular model is appropriate for launch -- it lowers the entry barrier while rewarding deeper adoption through bundle savings. As AI agents increasingly augment or replace human workflow steps, Brubru will explore outcome-based pricing layers: per-dossier workspace fees, per-report generation credits, or enterprise flat-rate models tied to legislative portfolio size rather than headcount. The system-of-record layer (dossier workspaces, accumulated contacts, document archives) also opens a natural expansion revenue path: the more dossiers a user manages, the more value the platform delivers.

### 7.2 Unit Economics

| Metric | Module (avg) | Starter | Advocate | Professional | EP Plan |
|--------|-------------|---------|----------|-------------|---------|
| Monthly price | EUR 31 | EUR 39 | EUR 59 | EUR 99 | EUR 49 |
| AI cost/user | EUR 5 | EUR 5 | EUR 6 | EUR 8 | EUR 6 |
| Infrastructure/user | EUR 1 | EUR 1 | EUR 1 | EUR 2 | EUR 1 |
| Support/user | EUR 0 | EUR 0 | EUR 1 | EUR 3 | EUR 1 |
| **Total cost/user** | **EUR 6** | **EUR 6** | **EUR 8** | **EUR 13** | **EUR 8** |
| **Gross margin/user** | **EUR 25 (81%)** | **EUR 33 (85%)** | **EUR 51 (86%)** | **EUR 86 (87%)** | **EUR 41 (84%)** |
| Est. monthly churn | 7% | 5% | 4% | 2% | 4% |
| Avg. lifetime | 14 months | 20 months | 25 months | 50 months | 25 months |
| **LTV** | **EUR 350** | **EUR 660** | **EUR 1,275** | **EUR 4,300** | **EUR 1,025** |
| Target CAC (3:1 LTV:CAC) | EUR 117 | EUR 220 | EUR 425 | EUR 1,433 | EUR 342 |
| Max payback period | 5 months | 7 months | 8 months | 17 months | 8 months |

**Blended ARPU:** ~EUR 55/month (weighted mix of modules, bundles, and EP Plans)

### 7.3 Revenue Concentration

At Month 12 target (~190 subscribers across plans):
- Individual modules (~60 subs): EUR 1,860/mo (17%)
- Starter bundle (~40 subs): EUR 1,560/mo (15%)
- Advocate bundle (~35 subs): EUR 2,065/mo (19%)
- Professional bundle (~25 subs): EUR 2,475/mo (23%)
- EP Plan (~30 subs): EUR 1,470/mo (14%)
- Annual plan uplift: EUR 1,300/mo (12%)
- Total MRR: EUR 10,730
- ARR: EUR 128,760

Revenue is well-distributed across plan types. Professional bundle drives the largest share per subscriber, while the modular approach creates a broad base of entry-level subscribers who upgrade over time. No single plan type exceeds 25% of total revenue, reducing concentration risk.

---

## 8. Technology & Architecture

### 8.1 Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Frontend | React 18 + TypeScript + Vite 7.x | Modern, fast, strong typing |
| Backend | FastAPI (Python 3.11+) + SQLAlchemy 2.0 | Async-first, excellent for AI pipelines |
| Database | PostgreSQL 15+ (Supabase) | Relational + JSONB for flexible schemas |
| AI (Primary) | Mistral (`mistral-small-latest`) | 15x cheaper than Claude, comparable quality for EU policy |
| AI (Fallback 1) | Anthropic Claude (`claude-sonnet-4-20250514`) | Complex reasoning tasks |
| AI (Fallback 2) | OpenAI GPT-4 Turbo | High availability fallback |
| AI (Fallback 3) | Google Gemini 1.5 Pro | Last resort, cost-effective |
| Search | BM25 + Semantic (hybrid, 60/40 weighted) | Best of keyword and semantic retrieval |
| Vector DB | ChromaDB | Lightweight, sufficient for current scale |
| ML | HuggingFace (multilingual embeddings, classification) | Open-source, no API dependency |
| i18n | i18next (6 languages live, 23 supported) | All official EU languages planned |
| Payments | Stripe | Industry standard, EU-compliant |
| Frontend hosting | SiteGround | Static build, European CDN |
| Backend hosting | Railway.app | Auto-deploy from main branch |

### 8.2 Data Infrastructure

**33 Scrapers covering 15+ EU institutional sources:**

| Source Category | Scrapers | Data Type |
|-----------------|----------|-----------|
| EUR-Lex | `eurlex_scraper`, `eurlex_sync_service` | Legislation, case law, CELEX numbers |
| OEIL | `oeil_scraper`, `oeil_sync_service` | 21,600+ procedure records |
| Legislative Train | `legislative_train_scraper`, `_enricher`, `_analyzer`, `_scheduler` | 490+ priority Commission files |
| European Parliament | `european_parliament_scraper` | MEP data, committees, votes |
| European Commission | `european_commission_scraper` | DG publications, press |
| Council | `council_scraper` | Council positions, working groups |
| EPRS Think Tank | `think_tank_scraper` | Research briefings, studies |
| Committee Work | `committee_work_scraper`, `_sync_service` | 26 EP committees, WIP procedures |
| Public Consultations | `public_consultation_scraper`, `consultation_sync_service` | "Have Your Say" portal |
| Commission Documents | `commission_doc_register_client`, `commission_doc_sync_service` | EC Register (COM, SWD, SEC, OJ via EUR-Lex + RegDoc API) |
| EU Calendar | `ep_calendar_loader`, `council_calendar_loader`, `ec_college_scraper`, `college_oj_scraper`, `committee_agenda_scraper`, `eu_calendar_sync_service` | 274+ institutional events (EP, Council, European Council, Commission, ECB) |
| MEP Amendments | `ep_open_data_client`, `ep_amendment_sync_service`, `ep_amendment_parser`, `alignment_scorer`, `comparison_analyzer` | Committee amendments, AI alignment scoring, comparative analysis |
| TED Tenders | `ted_client`, `ted_sparql_client` | EU public procurement |
| Who's Who | `who_is_who_scraper` | EU staff directories |
| IATE | `iate_scraper` | EU terminology (24 languages) |
| JRC | `jrc_scraper` | Scientific research |
| AssistEU | `assist_eu_scraper` | Procedural guidance |
| Style Guide | `style_guide_scraper` | EU writing standards |
| Data Europa | `data_europa_scraper` | Open data portal |

**Knowledge Base:**
- Beresol Knowledge Bundle: 11 policy reports + 7 live monitors
- EP Committees reference data (26 committees with codes, policy areas)
- EC Consultations reference data (DGs, types, statuses)
- EuroVoc thesaurus mapping

### 8.3 AI Architecture

```
User Query
    |
    v
Context Builder -----> Knowledge Base (reports, monitors)
    |                   OEIL (procedure status)
    |                   EPRS (research briefings)
    |                   Committee Work (WIP items)
    |                   Public Consultations
    |                   Legislative Train (Commission priorities)
    |                   Beresol Reports
    |
    v
Multi-Provider AI Service
    |
    ├── Mistral (primary, EUR 0.20/M input)
    ├── Claude  (fallback 1, EUR 3.00/M input)
    ├── GPT-4   (fallback 2, EUR 10.00/M input)
    └── Gemini  (fallback 3, EUR 1.25/M input)
    |
    v
Citation Tracker --> Response with sources
```

**Specialised AI services:**
- `rag_chatbot_service` -- RAG-powered chat with EU context
- `hybrid_legal_assistant` -- Legal analysis combining LLM + search
- `document_generator` -- Position papers, MEP briefings, talking points
- `consultation_analyser` -- Analyse consultation responses
- `consultation_proposal_generator` -- Draft consultation submissions
- `content_analyzer` -- Document analysis and classification
- `freshness_detector` -- Data staleness detection (90/180/365 day thresholds)
- `conversation_memory` -- Multi-turn context management
- `conversation_quality` -- Response quality scoring

### 8.4 Database Schema

30+ models across the full advocacy workflow:

| Domain | Models | Key Tables |
|--------|--------|------------|
| Users & Auth | 3 | `users`, `user_preferences`, `user_feed_subscriptions` |
| Chat | 4 | `chat_conversations`, `chat_messages`, `chat_analytics`, `chat_example_prompts` |
| Amendments | 1 | `amendments` (Akoma Ntoso XML storage) |
| RSS & News | 4 | `rss_feeds`, `rss_entries`, `user_feed_reads`, `user_saved_entries` |
| Legislation | 2 | `eu_laws`, `legislative_train_carriages` |
| Compliance | 1 | `compliance_reports` |
| Tenders | 1 | `tenders` |
| Documents | 1 | `user_documents` |
| Notifications | 1 | `notifications` |
| Feedback | 1 | `feedback` |
| Committee Work | 2 | `committee_work_items`, `committee_work_tracked` |
| Consultations | 2 | `public_consultations`, `consultation_tracking` |
| Commission Documents | 2 | `commission_documents`, `user_commission_doc_tracks` |
| EU Calendar | 2 | `eu_calendar_events`, `user_calendar_subscriptions` |
| MEP Amendments | 3 | `amendment_documents`, `mep_amendments`, `amendment_alignment_scores` |
| EP Voting | 2 | `ep_votes`, `ep_voting_records` |
| EP Resolutions | 1 | `ep_resolutions` |
| Council Voting | 1 | `council_voting_records` |
| Knowledge | 1 | `knowledge_gaps` |
| Newsletters | 1 | `newsletters` |

### 8.5 Security & Compliance Posture

- ISO 27001:2022 certification plan drafted (12-week implementation, EUR 15-25K)
- Current readiness: 35-40%
- GDPR-compliant data handling (EU-based hosting, no training on user data)
- JWT authentication with Google/LinkedIn OAuth
- Multi-provider AI ensures no single vendor dependency
- Secrets management via Railway encrypted variables

---

## 9. Traction & Current State

### 9.1 Product Development Status

| Component | Status | Scope |
|-----------|--------|-------|
| Brubru Chat | Production-ready | Full RAG pipeline, 4-provider AI, context injection |
| Amendator | Production-ready | Akoma Ntoso XML, multi-format export, AI drafting |
| My EU Bubble | Production-ready | 33+ RSS feeds, 9 tabs, tracking, bookmarks, institutional calendar |
| EU Law Comply | Production-ready | Gap analysis, action plans, multi-format export |
| Tenderator | Production-ready | TED integration, SME scoring, HF classification |
| Document Generator | Production-ready | Position papers, MEP briefings, talking points |
| Predictions | Production-ready | Timeline, outcome, EP vote, Council, QMV, resolutions |
| Legislative Tracking | Production-ready | OEIL, Legislative Train, Committee Work, Consultations, EU Calendar |
| MEP Amendments | Production-ready | EP Open Data sync, AI alignment scoring, comparative analysis |
| Admin Panel | Production-ready | 10+ management sections |
| Auth & Payments | Production-ready | Google/LinkedIn OAuth, Stripe subscriptions |
| i18n | Partial | 6 languages live (EN, ES, CA, FR, IT, NL), 23 planned |

**Lines of code:** 90+ frontend components, 37 API routers, 35 scrapers, 20 AI services, 30+ models, 25 database migrations.

### 9.2 What's Missing

| Gap | Impact | Plan |
|-----|--------|------|
| Paying customers | Critical -- no revenue validation | GTM launch (Section 10) |
| Usage analytics | Can't demonstrate engagement | Instrument after first users |
| Case studies | No social proof | Produce from first 3-5 customers |
| SEO / content marketing | No organic acquisition channel | Launch blog, LinkedIn presence |
| Mobile optimisation | Limited mobile experience | Responsive CSS pass (low priority) |
| Full 23-language support | 17 languages incomplete | Incremental translation |

---

## 9b. Primary Metric: WAPU (Weekly Active Paid Users)

**WAPU = a paid subscriber who performs at least one core action in the past 7 days.**

This is Brubru's north star metric. Not MRR, not subscriber count, not raw active users. WAPU measures the intersection of money AND usage -- the only honest signal of product-market fit.

### Why WAPU, Not MRR

MRR is a trailing indicator. At pre-revenue, it's just subscriber count times a multiplier. It tells you money came in but not if the product is working. A EUR 99/month Professional subscriber who hasn't logged in for 3 weeks is a churn event waiting to happen. That subscriber inflates MRR while masking a retention problem.

Similarly, subscriber count alone is misleading: a subscriber who signed up but doesn't use the product is a vanishing subscriber. Free trial users who never convert are noise. Only the intersection -- money AND usage -- counts.

### Core Actions

| Core Action | Why It Signals Value |
|-------------|---------------------|
| AI chat query | Using the policy advisor -- the primary interface |
| Document generated | A deliverable was produced -- direct labour replacement |
| Legislative file tracked/checked | Monitoring is happening -- daily workflow integration |
| Amendment drafted or MEP amendments analysed | Deep workflow engagement -- not just browsing |
| Compliance report run | High-value, high-switching-cost action |

One of these in a 7-day window = active.

### WAPU Targets

| Timeline | WAPU Target | Milestone |
|----------|-------------|-----------|
| Month 3 | **10** | Seed of product-market fit -- 10 paid users active weekly |
| Month 6 | **25** | Validated retention -- users return without prompting |
| Month 12 | **50** | System of record -- users accumulate irreplaceable dossiers |

### The WAPU Test

Every initiative is scored by: "Does this get a paid user to perform a core action this week?" The business plan's own data supports this: break-even is 55 subscribers at EUR 3,025 MRR, but 55 subscribers with 7% module churn means replacing ~4 subscribers every month just to stand still. If instead we focus on WAPU, the churn problem solves itself: active users don't churn. Module churn at 7% vs Professional at 2% -- that 3.5x difference almost certainly correlates with usage depth, not plan features.

### Private Dashboard vs. Wall Metric

The wall metric -- the one number every sprint is judged against -- is WAPU. Privately, we also monitor: MRR and cash position (survival), AI cost per user (margin protection), trial-to-paid conversion (funnel health), and churn by plan type (guardrail). These are important but they are guardrails, not the goal.

---

## 10. Go-to-Market Strategy

### 10.1 Phase 1: Founder-Led Sales (Months 1-3)

**Goal:** 10 WAPU (10 paid users active weekly). Validate product-market fit through usage, not just subscriptions.

**Channel: Direct outreach from personal network.**

The founder's 17+ years in Brussels policy provide a warm network of potential customers. This is the fastest path to first revenue.

| Action | Target | Timeline |
|--------|--------|----------|
| Personal outreach to 50 contacts | 15 free trial signups | Month 1 |
| Approach 5 trade associations | 3 Professional bundle subscribers | Month 1-2 |
| Offer 14-day free trial (all features) | Conversion data | Month 1-3 |
| Collect 3 testimonials | Social proof | Month 2-3 |
| Demo at 2 EU policy events | Lead generation | Month 2-3 |

**Key message:** "I built the tool I wished I had when I worked at the Parliament."

### 10.2 Phase 2: Content-Led Growth (Months 4-6)

**Goal:** 25 WAPU, EUR 3K+ MRR. Deepen engagement through dossier workspaces and amendment analysis.

**Channels:**

| Channel | Tactic | Expected CAC |
|---------|--------|-------------|
| LinkedIn | Weekly EU policy insights using Brubru-generated analysis | EUR 50-100 |
| EU policy events | Speaking slots, booth presence | EUR 200-300 |
| Beresol open reports | Free analysis reports driving brand awareness | EUR 30-50 (content) |
| Referral programme | Existing users refer colleagues | EUR 0-50 |
| Partnerships | EU consultancy reseller agreements | EUR 0 (rev share) |

**Content strategy:** Publish Beresol open reports (already 11 written) on EU policy topics. Each report demonstrates Brubru's analytical capability and drives inbound interest.

### 10.3 Phase 3: Scalable Acquisition (Months 7-12)

**Goal:** 50 WAPU, EUR 7K+ MRR. Build switching cost through CRM, team layer, and activity tracking.

**Channels:**

| Channel | Tactic | Budget |
|---------|--------|--------|
| Google Ads | "EU compliance tool", "legislative monitoring software" | EUR 1,000/mo |
| LinkedIn Ads | Targeted at EU policy professionals | EUR 500/mo |
| Webinars | Monthly deep-dives on EU legislative topics | EUR 200/mo |
| Partnership with EU affairs training providers | Embedded in courses | Rev share |
| EU startup programmes | EIC, national innovation funds | Non-dilutive capital |

### 10.4 AI-Native Agency Model (Parallel Track)

In parallel with SaaS subscriptions, offer deliverable-based pricing for larger engagements:

| Deliverable | Price | Brubru Automation | Gross Margin |
|-------------|-------|-------------------|-------------|
| Position paper | EUR 3,000 | ~80% | ~70% |
| Stakeholder mapping | EUR 5,000 | ~80% | ~70% |
| Amendment package (full committee) | EUR 8,000 | ~80% | ~75% |
| Compliance assessment | EUR 15,000 | ~70% | ~60% |
| Consultation response draft | EUR 2,000 | ~85% | ~80% |

This model validates willingness-to-pay at higher price points and can operate alongside SaaS.

---

## 11. Financial Model

### 11.1 Cost Structure

**Fixed monthly costs:**

| Item | Cost/Month |
|------|-----------|
| Hosting (SiteGround + Railway) | EUR 35 |
| Database (Supabase PostgreSQL) | EUR 75 |
| Domain / SSL | EUR 5 |
| **Subtotal fixed** | **EUR 115** |

**Variable costs (scale with users):**

| Item | Cost/Month | Notes |
|------|-----------|-------|
| AI APIs (Mistral primary) | EUR 0-200 | EUR 5-8/user depending on plan |
| Google Translate | EUR 0-50 | 23 languages |
| Tavily Search | EUR 0-29 | Web intelligence |
| **Subtotal variable** | **EUR 0-279** | |

**Total platform cost: EUR 115-394/month** (no founder salary)

### 11.2 Break-Even Analysis

| Scenario | Subscribers | MRR |
|----------|-------------|-----|
| Modules only (avg EUR 31) | 98 | EUR 3,038 |
| Bundles only (avg EUR 66) | 46 | EUR 3,036 |
| Professional only (EUR 99) | 31 | EUR 3,069 |
| **Blended mix (ARPU EUR 55)** | **~55** | **EUR 3,025** |

### 11.3 12-Month Revenue Projection

| Month | Total Subs | Blended ARPU | MRR | Cumulative Cash |
|-------|-----------|-------------|-----|-----------------|
| 1 | 0 | - | EUR 0 | EUR 9,750 |
| 2 | 0 | - | EUR 0 | EUR 9,500 |
| 3 | 5 | EUR 35 | EUR 175 | EUR 9,395 |
| 4 | 12 | EUR 40 | EUR 480 | EUR 9,535 |
| 5 | 22 | EUR 45 | EUR 990 | EUR 10,145 |
| 6 | 35 | EUR 48 | EUR 1,680 | EUR 11,385 |
| 7 | 55 | EUR 50 | EUR 2,750 | EUR 13,655 |
| 8 | 75 | EUR 52 | EUR 3,900 | EUR 17,035 |
| 9 | 100 | EUR 53 | EUR 5,300 | EUR 21,735 |
| 10 | 125 | EUR 54 | EUR 6,750 | EUR 27,805 |
| 11 | 155 | EUR 55 | EUR 8,525 | EUR 35,490 |
| 12 | 190 | EUR 55 | EUR 10,450 | EUR 45,000 |

**Assumptions:**
- First paying customers Month 3 (lower entry price drives faster adoption)
- ARPU rises from EUR 35 to EUR 55 as early adopters on modules upgrade to bundles
- 5-25 new subscribers per month (growing with marketing spend and bundle adoption)
- AI costs scale at ~EUR 5-8/user
- No founder salary included
- Blended churn ~4% applied from Month 6 (mix of module 7%, bundle 4%, Professional 2%)

### 11.4 Scenario Analysis

| Scenario | Month 12 MRR | Month 12 Cash | Assessment |
|----------|-------------|---------------|------------|
| Bear (50%) | EUR 5,225 | EUR 22,000 | Sustainable, slow growth |
| **Base (target)** | **EUR 10,450** | **EUR 45,000** | **Seed-fundable** |
| Bull (150%) | EUR 15,675 | EUR 72,000 | Series A candidate |

---

## 12. Team

### Current Team

**Victor Sole -- Founder & CEO**
- 7+ years at the European Parliament (policy, procedure, legislative drafting)
- 10+ years EU policy advisory (trade, digital, regulatory affairs)
- Full-stack developer: built entire Brubru platform (frontend, backend, AI, scrapers)
- Based in Brussels -- the epicentre of EU policy
- Fluent in EN, ES, CA, FR, IT, NL (maps to the 6 live language locales)

### Key Hire Priorities

| Role | When | Why |
|------|------|-----|
| Head of Sales / BD | Month 3 | Convert network into paying customers |
| Junior developer | Month 6 | Scale feature development, reduce bus factor |
| Customer success | Month 9 | Onboarding, retention, upsell |

### Advisory Board (to build)

Target profiles:
- Former MEP or Commission official (institutional credibility)
- EU SaaS founder (go-to-market expertise)
- Legal tech investor (fundraising introductions)

---

## 13. Risks & Mitigations

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| **Low conversion rate** | Medium | High | Improve onboarding, add feature gates, free-to-paid triggers |
| **Free trial costs** | Medium | High | 14-day trial limit; cap at 500 concurrent trials |
| **Single founder** | High | High | Document all processes; build recurring revenue that doesn't depend on founder availability; hire early |
| **AI costs spike** | Low | Medium | 4-provider fallback chain; Mistral primary at 15x cheaper; usage caps per tier |
| **Foundation model plugins** | Medium | Medium | Three-layer defence: pipeline depth (35 scrapers), domain engineering (AKN, QMV, compliance), system-of-record lock-in (dossiers, contacts, documents) |
| **EU regulation changes** | Low | Low | This is actually upside -- regulatory change drives demand for the product |
| **Data source changes** | Medium | Medium | 33 scrapers with redundancy; OEIL XML feeds as stable fallback; multiple sources per data type |
| **Slow enterprise sales** | High | Medium | Run parallel SaaS + agency model; consultancy revenue funds patience |
| **Security incident** | Low | High | ISO 27001 certification planned post-seed (2027); no user data used for training; EU-based hosting |

---

## 14. Roadmap

**Leitmotiv: All the EU with AI.**

### Q1 2026 -- Phase A: Activation (WAPU Target: 10)

| Priority | Deliverable | Status |
|----------|-------------|--------|
| **A1** | Fix chatbot bugs (MEP linking, policy taxonomy, extraction) | Complete |
| **A2** | AI daily/weekly briefing emails -- pull users back weekly, create daily habit | Not started |
| **A3** | Proactive notification engine -- alerts when tracked files change stage (the #1 WAPU machine) | Not started |
| **A4** | Pre-configured thematic dashboards -- reduce time-to-value for new users to <2 minutes | Not started |
| **A5** | Demo/booking flow + first 10 outreach from personal network | Not started |
| -- | Predictions tab fully live in production | Complete |
| -- | My EU Calendar: multi-source institutional calendar (EP, Council, Commission, ECB) | Complete |
| -- | MEP Amendments: real parliamentary amendment data with AI comparative analysis | Complete |
| -- | Landing page with pricing and demo video | In progress |

### Q2 2026 -- Phase B: Depth (WAPU Target: 25)

| Priority | Deliverable |
|----------|-------------|
| **B1** | **Dossier workspaces:** per-legislative-file workspace tying together tracked files, amendments, MEP analysis, predictions, generated documents, and calendar events into a single view |
| **B2** | **Amendment analysis view:** counter Dixit, make Amendator stickier with comparative amendment analysis |
| **B3** | **Document Generator improvements:** more deliverable types = more core actions per user |
| -- | Reach EUR 3K MRR (break-even) |
| -- | Complete i18n for DE, PT, PL, EL (top 4 missing languages by EU speaker count) |

### Q3-Q4 2026 -- Phase C: Lock-in (WAPU Target: 50)

| Priority | Deliverable |
|----------|-------------|
| **C1** | **Stakeholder CRM:** MEP relationship tracker, meeting notes linked to dossiers, stakeholder position mapping per legislative file |
| **C2** | **Team layer:** shared dossier workspaces, organisation accounts, permission model (admin/member/viewer) |
| **C3** | **Activity logging + ROI:** advocacy activity tracking and impact measurement for enterprise selling |
| -- | Reach EUR 7K+ MRR |
| -- | 50+ paying customers |
| -- | 3 enterprise case studies published |
| -- | Begin seed fundraising process |
| -- | Partnership with 2 EU affairs training providers |

### 2027 (Post-Seed -- Expand)

| Priority | Deliverable |
|----------|-------------|
| 1 | **GrantBru launch:** evolve Tenderator to cover ALL EU funding -- Funding & Tenders Portal (Horizon Europe, Digital Europe, CEF, LIFE), AGRIP, EIC, EIB/EIF instruments, Structural Funds, Recovery & Resilience Facility |
| 2 | **AI-native agency model at scale:** sell finished deliverables (position papers, amendment packages, compliance assessments, regulatory impact assessments) at consulting prices with 60-80% margins |
| 3 | **ISO/IEC 27001:2022 certification** (12-week programme, post-seed funding) |
| 4 | **Policy decision support module:** help in-house government affairs teams decide what positions to take by synthesising stakeholder submissions, EP voting patterns, Council signals, and lobbyist meeting disclosures |
| 5 | **Institutional pilot:** Amendator and consultation response processor positioned for EU institutional procurement (EP, Commission DGs) |
| 6 | UK regulatory expansion (post-Brexit regulatory divergence creates parallel market) |
| 7 | Multi-agent architecture (autonomous legislative monitoring agents) |
| 8 | EUR 15K+ MRR, seed round closed |

### 2028 (National Expansion -- All the EU with AI)

| Priority | Deliverable |
|----------|-------------|
| 1 | **Brubru National:** implement Brubru across all 27 EU Member State legal frameworks -- starting with Belgium, France, Germany, Spain, Italy, Netherlands |
| 2 | Each national instance covers the full legal stack: local, regional, and national legislation, parliamentary procedures, government gazettes, and public procurement |
| 3 | **GrantBru National:** extend EU funding intelligence to Member State co-financing schemes, national subsidy programmes, and regional development funds |
| 4 | National compliance modules: transpose EU directives into national implementation tracking (e.g. AI Act national transposition, NIS2 national measures) |
| 5 | Expand to remaining 21 Member States through localisation and legal framework mapping |
| 6 | Series A readiness: EUR 50K+ MRR, 200+ customers across 5+ countries |

### 2029+ Vision

- **Brubru in all 27 Member States:** Brubru Belgium, Brubru France, Brubru Germany, Brubru Italy, Brubru Spain, Brubru Netherlands, and 21 more -- every European legal framework covered and managed through AI at every level of governance
- **GrantBru as standalone product:** comprehensive EU and national funding intelligence platform, potentially spun off as a separate vertical
- **Government-as-customer:** EU institutions, national parliaments, and government ministries using Brubru as internal policy intelligence infrastructure
- **MiCA/stablecoin compliance vertical:** specialised compliance intelligence for crypto and financial services companies operating under EU regulation
- **EU fraud detection:** OLAF-adjacent tools for detecting irregularities in CAP payments, structural funds, and recovery fund disbursements
- Series A / B: international expansion beyond EU (UK, EEA, accession countries)

---

## 15. Funding & Use of Proceeds

### 15.1 Current Position

| Metric | Value |
|--------|-------|
| Cash on hand | EUR 10,000 |
| Monthly burn (platform only) | EUR 115 |
| Runway (platform only) | 87 months |
| Runway (with moderate AI usage) | 40 months |

The business is sustainable at current burn. External funding is not a survival requirement -- it is an acceleration tool.

### 15.2 Seed Round Parameters (Target: Month 12-18)

| Parameter | Target |
|-----------|--------|
| Round size | EUR 500,000 - EUR 1,000,000 |
| Valuation | EUR 3-5M pre-money (contingent on EUR 10K+ MRR) |
| Instrument | SAFE note or equity |
| Investors | EU-focused VCs, legal tech funds, angels with Brussels networks |

### 15.3 Use of Funds (EUR 500K Seed)

| Category | Allocation | Amount | Purpose |
|----------|------------|--------|---------|
| Engineering | 40% | EUR 200,000 | 2 junior devs, GrantBru development, national framework expansion, infrastructure scaling |
| Sales & Marketing | 35% | EUR 175,000 | Head of sales, events, ads, content |
| Operations | 15% | EUR 75,000 | Legal, ISO 27001 cert, accounting, office |
| Buffer | 10% | EUR 50,000 | Contingency |

**Expected runway with seed:** 18-24 months at EUR 20-25K/month burn.

### 15.4 Fundraising Readiness Checklist

| Criterion | Current | Target for Seed | Gap |
|-----------|---------|-----------------|-----|
| MRR | EUR 0 | EUR 10,000+ | Get customers |
| Paying customers | 0 | 50+ | Launch GTM |
| Free-to-paid conversion | N/A | 6%+ | Validate funnel |
| Monthly growth rate | N/A | 15%+ | Demonstrate traction |
| Churn | N/A | < 5% blended (modules < 7%, bundles < 4%, Professional < 2%) | Prove retention |
| Product | Built | Built | -- |

---

## 16. Appendices

### A. Key Assumptions

| Assumption | Value | Source |
|------------|-------|--------|
| EU public affairs market size | EUR 3-5B | EU Transparency Register, industry estimates |
| Module monthly churn | 7% | Higher churn for single-feature plans |
| Bundle monthly churn | 4% | B2B SaaS benchmark |
| Professional monthly churn | 2% | Enterprise SaaS benchmark |
| Free trial AI cost | EUR 2/trial (14 days) | Limited trial period |
| Module user AI cost | EUR 5/month | Single-feature usage |
| Bundle user AI cost | EUR 6/month | Multi-feature usage |
| Professional user AI cost | EUR 8/month | Full platform usage |
| Mistral input cost | $0.20/M tokens | Mistral pricing |
| Claude Sonnet input cost | $3.00/M tokens | Anthropic pricing |
| Avg tokens per message | 2,000 | Internal estimate |
| Trial-to-paid conversion | 10-15% | Higher than freemium due to 14-day urgency |
| Module-to-bundle upgrade | 20-25% | Natural upgrade path when using 2+ modules |
| Bundle-to-Professional upsell | 10-15% | B2B SaaS benchmark |

### B. Product Feature Matrix by Plan

| Feature | Free Trial (14 days) | Chat Module (EUR 29) | Bubble Module (EUR 29) | Amendator Module (EUR 19) | EU Law Comply Module (EUR 29) | Tenderator Module (EUR 49) | Starter Bundle (EUR 39) | Advocate Bundle (EUR 59) | Professional Bundle (EUR 99) | EP Plan (EUR 49) |
|---------|---------------------|---------------------|----------------------|-------------------------|------------------------------|---------------------------|------------------------|-------------------------|-----------------------------|--------------------|
| Brubru Chat | Full | Full | -- | -- | -- | -- | Full | Full | Full + priority | Full |
| My EU Bubble | Full | -- | Full | -- | -- | -- | Full | Full | Full + Council analysis | Full |
| Amendator | Full | -- | -- | Full | -- | -- | -- | Full | Full | Full |
| EU Law Comply | Full | -- | -- | -- | Full | -- | -- | -- | Full | -- |
| Predictions | Full | -- | Included | -- | -- | -- | Included | Included | Unlimited | Included |
| Tenderator | Full | -- | -- | -- | -- | Full | -- | -- | Full | -- |
| Document Generator | Full | Included | -- | Included | -- | -- | Included | Included | Full | Included |
| Export formats | All | All | All | All | All | All | All | All | All + white-label | All |
| Support | Email | Email | Email | Email | Email | Email | Email (48h) | Email (48h) | Priority (24/7) + SLA | Email (48h) |

### C. Data Source Inventory

**33 scrapers across 15+ EU institutional sources:**

1. EUR-Lex (legislation, case law, RSS feeds)
2. OEIL Legislative Observatory (21,600+ procedures, XML feeds)
3. Legislative Train Schedule (490+ Commission priority files)
4. European Parliament (MEPs, committees, votes, press)
5. European Commission (DG publications, speeches)
6. Council of the EU (positions, working groups)
7. EPRS Think Tank (research briefings, studies)
8. Committee Work in Progress (26 EP committees)
9. EC Public Consultations ("Have Your Say" portal)
10. EC Register of Commission Documents (COM, SWD, SEC, C, JOIN, OJ, PV -- EUR-Lex + RegDoc API)
11. EU Calendar (EP sessions, Council meetings, European Council summits, Commission college, ECB Governing Council -- 245+ events)
12. TED/eSender (EU public procurement, SPARQL)
13. Who's Who (EU staff directories)
14. IATE (EU terminology, 24 languages)
15. JRC (scientific research, technical reports)
16. AssistEU (procedural guidance)
17. EU Style Guide (writing standards)
18. Data Europa (open data portal)
19. EC newsletters (DG-specific newsletters)

### D. Comparable Transactions

| Company | Domain | Last Round | Valuation | ARR at Round |
|---------|--------|-----------|-----------|--------------|
| Harvey AI | Legal AI | Series D (2025) | $3B+ | $100M+ ARR |
| FiscalNote | US political intel | IPO (2022) | $1.5B | $100M+ ARR |
| Quorum | US political intel | Series B (2021) | ~$200M | ~$20M ARR |
| Legit.ai | Compliance AI | Series A (2024) | ~$50M | ~$5M ARR |
| Luminance | Legal AI | Series C (2024) | ~$1B | ~$30M ARR |

Brubru operates in a market with comparable dynamics to these companies but in an adjacent geography (EU) with zero direct competition.

### E. Glossary

| Term | Definition |
|------|-----------|
| COD | Ordinary legislative procedure (codecision) -- most common EU lawmaking procedure |
| CNS | Consultation procedure |
| APP | Consent procedure |
| CELEX | Unique identifier for EU legal documents |
| OEIL | Observatory of the European Parliament (legislative tracking) |
| Akoma Ntoso | OASIS XML standard for legislative documents |
| QMV | Qualified Majority Voting (Council of the EU) |
| DG | Directorate-General (European Commission department) |
| EPRS | European Parliamentary Research Service |
| MRR | Monthly Recurring Revenue |
| ARR | Annual Recurring Revenue |
| LTV | Customer Lifetime Value |
| CAC | Customer Acquisition Cost |

---

*Brubru Business Plan v1.0 -- February 2026*
*Beresol BV | Brussels, Belgium*
*Contact: hello@beresol.eu | brubru.beresol.eu*
