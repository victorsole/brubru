# BrubruBel: AI-Powered Innovative Public Procurement for Belgium

## Implementation Proposal for Belgian Public Administration

---

## 1. Executive Summary

**BrubruBel** is a proposed implementation of the Brubru platform within Belgian public administration, purpose-built for **Belgian public procurement professionals**. While Brubru serves EU policy advocates, BrubruBel targets the domestic Belgian procurement ecosystem: the EUR 50 billion/year, 20,000+ contracts/year market where AI can transform how public buyers discover, evaluate, and award contracts that drive innovation.

BrubruBel repositions Brubru's proven GenAI architecture (multi-provider AI, legislative data integration, document generation, and compliance checking) for the specific needs of Belgian public buyers at municipal, regional, and federal levels. It is designed as an **innovative public procurement tool implemented within public administration**, creating a virtuous loop between the tool and the policy objective it serves.

**Anchoring partners:** Innoviris (Brussels-Capital Region innovation agency) and sustAIn.brussels (European Digital Innovation Hub).

---

## 2. Market Context

### Belgian Public Procurement

| Metric | Value |
|--------|-------|
| Annual procurement spend | EUR 50 billion |
| Public contracts per year | ~20,000 |
| Contracting authorities | Federal + 3 Regions + 10 Provinces + 581 municipalities + 100s of agencies |
| Legal framework | Belgian Public Procurement Act (2016), transposing EU Directives 2014/24/EU and 2014/25/EU |
| Innovation procurement share | <2% (EU average ~3.5%) |
| Digital maturity of buyers | Low to medium (especially municipalities) |

### Problem Statement

Belgian public buyers face three interlocking challenges:

1. **Complexity overload:** The intersection of Belgian federal/regional procurement law, EU directives, sector-specific regulations, and jurisprudence creates a legal maze that discourages innovation-friendly procedures (competitive dialogue, innovation partnerships, pre-commercial procurement).

2. **Language fragmentation:** Belgium's multilingual reality (Dutch, French, German, English) means procurement documents, market research, and supplier communications must work across language barriers. Most municipalities lack resources for multilingual procurement. Brussels in particular has a large international population that operates in English.

3. **Innovation gap:** Despite Innoviris's efforts to promote innovative procurement, most Belgian public buyers default to lowest-price open procedures. They lack the tools and confidence to use innovation-friendly procurement instruments.

### Opportunity

AI can address all three challenges simultaneously:
- **Simplify complexity** by providing natural-language explanations of procurement rules and procedures
- **Bridge language gaps** through real-time multilingual support in NL, FR, DE, and EN, with automatic translation between all four languages
- **Enable innovation** by guiding buyers through innovation-friendly procurement procedures step by step

---

## 3. Product Vision

### BrubruBel = Brubru's Architecture + Belgian Procurement Domain

BrubruBel inherits Brubru's core architecture and adapts each module for Belgian public procurement:

| Brubru Module | BrubruBel Adaptation | Use Case |
|---------------|---------------------|----------|
| **Brubru Chat** | **ProcureChat** | AI assistant answering procurement questions in NL/FR/DE/EN. "Can I use a competitive dialogue for this IT contract?" |
| **My EU Bubble** | **My Procurement Feed** | Aggregated procurement news from Belgian Official Journal (Bulletin der Aanbestedingen), TED, regional portals, jurisprudence databases |
| **Amendator** | **Tender Drafter** | AI-assisted drafting of procurement documents: specifications, selection criteria, award criteria, innovation clauses |
| **EU Law Comply** | **Procurement Comply** | Compliance checking against Belgian procurement law, EU directives, and regional regulations. Flag risks before publication |
| **Predictions** | **Market Intelligence** | Predict supplier interest, estimate number of bids, benchmark pricing from historical TED data |
| **Document Generator** | **Template Generator** | Generate standard procurement templates (open procedure, restricted, competitive dialogue, innovation partnership) with AI customisation |
| **EU Calendar** | **Procurement Calendar** | Track procurement deadlines, standstill periods, contract milestones, budget cycle dates |

### Core Differentiators

1. **Multilingual with auto-translation:** Every feature works in Dutch, French, German, and English. The AI responds in the user's language and automatically translates procurement documents between all four languages. Any document created in one language is instantly available in the other three.

2. **Belgian law first:** The knowledge base is grounded in Belgian procurement legislation (Wet Overheidsopdrachten / Loi sur les marches publics), not generic EU directives. Regional specificities (Brussels, Flanders, Wallonia) are built in.

3. **Innovation procurement guidance:** Dedicated workflows for innovation-friendly procedures, including competitive dialogue, innovation partnerships, and pre-commercial procurement (PCP), with step-by-step AI guidance that demystifies these instruments for first-time users.

4. **European AI supply chain:** Mistral (French) as primary provider aligns with European digital sovereignty. No data leaves EU jurisdictions.

---

## 4. Technical Architecture

### Inherited from Brubru

| Component | Technology | Adaptation |
|-----------|-----------|------------|
| Frontend | React 18 + TypeScript + Vite | New procurement-specific UI components |
| Backend | FastAPI + SQLAlchemy 2.0 | New procurement API endpoints |
| Database | PostgreSQL | New procurement tables (tenders, suppliers, compliance) |
| AI | Mistral (primary) + Claude/GPT-4/Gemini fallback | Belgian procurement knowledge fine-tuning |
| Auth | JWT + OAuth | Belgian eID / itsme integration |
| i18n | i18next (6 languages: EN, FR, NL, ES, CA, IT) | Priority: NL-BE, FR-BE, DE-BE, EN |

### New Data Sources

| Source | Type | Content |
|--------|------|---------|
| Bulletin der Aanbestedingen / Bulletin des Adjudications | Official gazette | All Belgian public procurement notices |
| TED (Tenders Electronic Daily) | EU portal | Cross-border procurement opportunities |
| e-Procurement (Belgium) | Government portal | Belgian electronic procurement platform |
| Staatsblad / Moniteur Belge | Legal gazette | Procurement legislation and amendments |
| Council of State jurisprudence | Case law | Procurement disputes and rulings |
| Vlaamse Overheid / SPW / Brussels Gewest | Regional portals | Regional procurement policies and guidelines |

### Belgian eID Integration

Belgian public servants authenticate using the national electronic identity system. BrubruBel integrates:
- **itsme** app (mobile authentication)
- **eID card reader** (traditional)
- **CSAM** (federal authentication platform for civil servants)

This replaces Brubru's Google/LinkedIn OAuth for the Belgian public sector context.

---

## 5. Innovation Procurement Use Cases

### Use Case 1: First-Time Innovation Partnership

A Brussels municipality wants to procure an AI-powered citizen service chatbot but has never used an Innovation Partnership procedure.

**BrubruBel guides them:**
1. ProcureChat explains the Innovation Partnership procedure in plain Dutch/French
2. Procurement Comply validates the choice is legally appropriate for this contract type
3. Tender Drafter generates the procurement documents with innovation-specific clauses
4. Market Intelligence estimates supplier interest from TED historical data
5. Template Generator produces the notice for publication in the Bulletin

**Without BrubruBel:** 6 to 12 months of legal consultation, external advisors, and uncertainty.
**With BrubruBel:** 2 to 4 weeks of guided, confident procurement.

### Use Case 2: Cross-Regional Procurement Harmonisation

The Brussels-Capital Region, a Flemish municipality, and a Walloon province want to jointly procure a smart energy management system.

**BrubruBel supports:**
1. ProcureChat explains joint procurement rules across regions
2. Tender Drafter generates multilingual specifications (NL/FR/DE/EN) from a single brief, with automatic translation between all four languages
3. Procurement Comply checks compliance with all three regional frameworks
4. Procurement Calendar tracks the joint timeline across different administrative calendars

### Use Case 3: SME-Friendly Green Procurement

A federal agency wants to reserve lots for SMEs in a green public procurement of office supplies.

**BrubruBel enables:**
1. ProcureChat explains SME-friendly provisions in Belgian law
2. Tender Drafter includes appropriate lot division, proportionate selection criteria, and sustainability award criteria
3. Procurement Comply flags any provisions that might inadvertently exclude SMEs
4. Market Intelligence identifies potential Belgian SME suppliers

---

## 6. Implementation Strategy

### Phase 1: Innoviris Pilot (Months 1 to 6)

**Partnership with Innoviris** as regional support centre for innovative public procurement:
- Innoviris provides access to Brussels public buyers already engaged in their programme
- BrubruBel deployed as a pilot within 5 to 10 Brussels administrations
- Feedback loop informs development
- Innoviris validates the tool as part of their support mechanism (training, technical support)

**Cost:** Covered by Innoviris's existing budget for innovative procurement support tools.

### Phase 2: sustAIn.brussels Acceleration (Months 3 to 12)

**Partnership with sustAIn.brussels** as European Digital Innovation Hub:
- "Test Before Invest" programme: public administrations trial BrubruBel at no cost
- Skills & Training: sustAIn.brussels delivers training sessions on BrubruBel
- Matchmaking: connect BrubruBel with public buyers through the EDIH network
- EU AI Week 2026 (March 16): showcase BrubruBel as a case study

### Phase 3: Flemish and Walloon Expansion (Months 6 to 18)

- Partner with **Vlaio** (Flanders Innovation & Entrepreneurship) and **Digital Wallonia** for regional rollout
- Leverage Flemish and Walloon innovative procurement networks
- Target 50 municipalities per region

### Phase 4: Federal and National (Months 12 to 24)

- Engage **Federal Procurement Office** (Kanselarij / Chancellerie)
- Target federal ministries and agencies
- Position for inclusion in federal digital transformation programme

### Phase 5: Cross-Border (Months 18 to 36)

- Extend to **Benelux**: Netherlands (PIANOo) and Luxembourg
- Leverage EDIH network for cross-border procurement support
- Align with **eafip.eu** at EU level

---

## 7. Funding Strategy

### Primary: Innoviris Innovation Grant

| Programme | Amount | Purpose |
|-----------|--------|---------|
| Innoviris Innovative Public Procurement | EUR 50,000 to 150,000 | Pilot development and deployment in Brussels |
| Innoviris R&D SME Grant | EUR 25,000 to 100,000 | Technical development of Belgian-specific features |

### Secondary: DIGITAL Europe Programme

BrubruBel is a natural output of the DIGITAL-2026-AI-09-GENAI-PA application (see `grant_application_genai_pa.md`). If the GenAI-PA grant is awarded, BrubruBel becomes a **replication case study**, demonstrating how a European GenAI solution can be adapted for national/regional public administration.

### Tertiary: Regional Programmes

| Programme | Region | Potential |
|-----------|--------|-----------|
| Vlaio Innovation mandate | Flanders | EUR 50,000 feasibility study |
| Digital Wallonia | Wallonia | Co-development partnership |
| ERDF Innovation Brussels | Brussels | Infrastructure co-funding |

### Bootstrap Path (No Grant)

If no grant funding is secured, BrubruBel can be bootstrapped as:
1. A configuration layer on top of existing Brubru codebase (minimal new development)
2. Belgian legal knowledge base as a content module (EUR 5,000 to 10,000 investment)
3. Pilot with 5 Innoviris contacts as beta testers (relationship-based)
4. Iterative development based on pilot feedback

---

## 8. Competitive Landscape

| Competitor | Scope | AI? | Belgian Law? | Innovation Procurement? | Multilingual (NL/FR/DE/EN)? |
|-----------|-------|-----|-------------|------------------------|--------------------------|
| e-Procurement.be | Federal platform | No | Yes | No | NL/FR (no DE, no EN) |
| TED (EU) | EU-wide | No | No | No | All EU languages |
| Mercell / TenderNed | Nordics/NL | Partial | No | No | No |
| Ivalua / Jaggaer | Enterprise | Partial | No | No | No |
| **BrubruBel** | **Belgium-focused** | **Yes (GenAI)** | **Yes** | **Yes (core feature)** | **Yes (NL/FR/DE/EN + auto-translation)** |

**BrubruBel's unique positioning:** No existing tool combines AI-powered assistance, Belgian procurement law expertise, innovation procurement guidance, and multilingual support with automatic translation. The closest alternatives are generic e-procurement platforms (no AI, no guidance) or international suites (no Belgian specialisation).

---

## 9. Team and Partners

### Beresol (BrubruBel Developer)

Beresol develops Brubru, an operational GenAI platform for EU policy professionals. The team has:
- 3+ years of experience building AI tools for the EU institutional context
- Multi-provider AI architecture (Mistral, Claude, GPT-4, Gemini)
- Integration with 15+ EU institutional data sources
- 23-language internationalisation framework

### Innoviris (Brussels Innovation Partner)

- Regional support centre for innovative public procurement in Brussels-Capital Region
- Direct access to Brussels public buyers (municipalities, agencies)
- Existing programmes for awareness, training, and financial/legal/technical support
- EU-level connection via eafip.eu
- Contact: Gaetan Danneels (gdanneels@innoviris.brussels)

### sustAIn.brussels (EDIH Partner)

- European Digital Innovation Hub in Brussels
- "Test Before Invest" programme for AI adoption
- Skills & Training for digital transformation
- Coordinated by Sirris, Agoria, BeCentral, VUB, ULB
- Supported by European Commission, Innoviris, and hub.brussels
- Contact: info@sustain.brussels | +32 474 96 44 89

### Advisory Network

- **eafip.eu**, European Assistance for Innovation Procurement
- **PIANOo**, Dutch Public Procurement Expertise Centre (Benelux expansion)
- **Vlaio**, Flanders Innovation & Entrepreneurship
- **Digital Wallonia**, Walloon digital transformation agency

---

## 10. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Low public sector AI adoption | Medium | High | Partner with Innoviris for trust-building; "Test Before Invest" via sustAIn.brussels |
| Belgian law complexity (3 regions) | High | Medium | Start with Brussels only; expand region by region with legal validation |
| Language model accuracy in legal context | Medium | High | Human-in-the-loop validation; legal disclaimer; expert review for templates |
| Procurement budget constraints | Medium | Medium | Implement within existing Innoviris support infrastructure; shared cost model |
| Competition from generic AI tools | Low | Low | Deep Belgian specialisation is the moat; ChatGPT cannot provide procurement-specific compliance |
| Data privacy concerns in public sector | Medium | High | GDPR compliance; Belgian eID integration; EU-hosted infrastructure; no data leaves EU |

---

## 11. Deployment Timeline

| Quarter | Milestone |
|---------|-----------|
| Q2 2026 | Innoviris partnership formalised; pilot scope defined |
| Q3 2026 | BrubruBel MVP: ProcureChat + Belgian legal knowledge base |
| Q4 2026 | Pilot with 5 to 10 Brussels administrations via Innoviris |
| Q1 2027 | sustAIn.brussels "Test Before Invest" programme launch |
| Q2 2027 | Tender Drafter and Procurement Comply modules |
| Q3 2027 | Flemish pilot (Vlaio partnership) |
| Q4 2027 | Walloon pilot (Digital Wallonia) |
| Q1 2028 | Federal engagement; 300+ users |
| Q2 2028 | Full deployment; Benelux exploration |

---

## 12. Contact

**Beresol contact:**
- Website: https://beresol.eu
- Brubru platform: https://brubru.beresol.eu
