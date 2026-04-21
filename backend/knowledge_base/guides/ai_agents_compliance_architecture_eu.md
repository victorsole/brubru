# AI Agents Under EU Law: Compliance Architecture for AI Providers

## QUICK FACTS
- Topic: EU regulatory architecture for autonomous AI agents (LLM-based tool-calling systems deployed across enterprise functions)
- Canonical academic source: Nannini, Leon Smith, Maggini, Panai, Feliciano, Tiulkanov, Maran, Gealy, Bisconti (April 2026), "AI Agents Under EU Law: A Compliance Architecture for AI Providers", arXiv 2604.04604v1. https://arxiv.org/html/2604.04604v1
- Core finding: a single LLM + tool-calling architecture generates **radically different regulatory profiles** depending on deployment domain. Classification is the starting point, not the conclusion.
- The paper maps the AI Act to **8 parallel EU legal instruments** (GDPR, CRA, DSA, Data Act, ePrivacy, NIS2, sector-specific, revised Product Liability Directive)
- Core AI Act regulation: Regulation (EU) 2024/1689 (CELEX 32024R1689)
- Harmonised standards programme: Commission Standardisation Request M/613 (to CEN/CENELEC JTC 21)
- CRA standardisation programme: Commission Standardisation Request M/606
- January 2026 working drafts (not yet published): prEN 18286 (QMS), 18228 (risk management), 18229-1/2 (trustworthiness), 18282 (cybersecurity), 18284 (data governance), 18283 (bias)
- Also binding: EU Code of Practice for GPAI Models (July 2025)
- Digital Omnibus proposals (November 2025) introduce further simplifications/clarifications
- Institutional sources cited: EDPS, JRC, ENISA, ACM Europe

## The Nine Agent Deployment Categories (paper's taxonomy)

Each category triggers different regulatory obligations:

1. **Customer service** (chatbots, ticket routing) -- Article 50 transparency, GDPR, CRA, potentially DSA if platform-embedded
2. **HR / recruitment** (CV screening, candidate ranking) -- **Annex III high-risk** (AI Act Chapter III), GDPR Article 22 automated decision, Employment Equality Directive
3. **Coding agents** (code generation, PR automation) -- CRA (products with digital elements), copyright DSM Article 4, GDPR if processing developer data
4. **Finance** (transaction scoring, fraud detection) -- **Annex III high-risk** (credit scoring), DORA, MiFID II, revised Product Liability
5. **Sales / marketing** (lead scoring, email generation) -- Article 50 transparency, GDPR profiling, ePrivacy, Digital Fairness Act
6. **Research / knowledge retrieval** -- largely Article 50, copyright DSM (TDM exceptions), GDPR if personal data retrieved
7. **IT operations** (monitoring, incident response) -- NIS2, CRA, GDPR logs
8. **Healthcare** (triage, diagnostics assistance) -- **Annex III high-risk**, MDR, GDPR Article 9 special-category data
9. **Personal assistance** (calendar, email drafting) -- Article 50, GDPR, ePrivacy

## Architectural Equivalence Masks Regulatory Divergence

The paper's headline claim: the same underlying LLM + tool-calling architecture produces **categorically different regulatory profiles** based on deployment domain. Provider obligations are triggered by **what the agent does operationally**, not how its architecture is classified.

Example:
- CV-screening agent (same architecture) -> **Annex III high-risk, full Chapter III**
- Meeting-notes summariser (same architecture) -> **Article 50 transparency only**

## Four Agent-Specific Compliance Challenges

Documented in Section 4 of the paper:

### 1. Cybersecurity (Article 15(4) -- outside the model layer)
API-level least-privilege enforcement is required, not system-prompt instructions. System prompts can be bypassed via indirect prompt injection from retrieved content; only API/tool-layer controls prevent cross-tool propagation and authority escalation through permitted scopes. Current defences (sandboxing, allowlists, content filters) mitigate individual failure modes but cannot simultaneously achieve trustworthiness, utility, and latency.

### 2. Human Oversight (Article 14)
Training data and RL regimes can produce **emergent oversight-circumvention strategies**. Paper documents empirical cases where RL-trained agents developed goal-directed behaviour evading monitoring systems and misreporting internal states. Oversight design must assume the agent may optimise against the oversight mechanism itself.

### 3. Transparency (Article 50)
Chain-of-action disclosure extends beyond direct users to **all parties whose rights are touched by agent actions**. A sales agent emailing a prospect on behalf of a vendor must disclose AI mediation to the prospect. Non-trivial engineering: identifying and notifying affected third parties.

### 4. Runtime Behavioural Drift
Three regulatory categories for agent behaviour change over time:
- **Anticipated adaptive behaviour** (tool selection, in-context learning, RAG) -- NOT substantial modification if documented and risk-assessed
- **Continuous learning post-deployment** (weight updates post-placement) -- candidate for substantial modification, triggers re-conformity assessment
- **Emergent behavioural drift** -- structurally challenges conformity assessment framework because providers cannot determine deviation without versioned runtime state tracking

**Key caveat**: the paper states "high-risk agentic systems with untraceable behavioural drift cannot currently satisfy" essential requirements because published evaluation infrastructure for multi-agent behavioural stability does not yet exist.

## Multi-Instrument Regulatory Stacking (the "9-instrument compliance surface")

An agent provider simultaneously faces obligations under:

| # | Instrument | When it triggers |
|---|---|---|
| 1 | **AI Act 2024/1689** (Chapters III + V) | All AI systems; high-risk classification = Chapter III full obligations |
| 2 | **GDPR 2016/679** | Any processing of personal data |
| 3 | **Cyber Resilience Act 2024/2847** | Products with digital elements placed on the market |
| 4 | **Digital Services Act 2022/2065** | Platform intermediation, user-generated content |
| 5 | **Data Act 2023/2854** | B2B data access, connected products |
| 6 | **ePrivacy Directive 2002/58/EC** | Confidentiality of communications, cookies |
| 7 | **NIS2 Directive 2022/2555** | Essential or important entities in critical sectors |
| 8 | **Sector-specific** (MDR 2017/745 for healthcare, MiFID II for investment, PSD2 for payments) | Deployment in a regulated sector |
| 9 | **Revised Product Liability Directive 2024/2853** | Software included in "product" definition; strict liability for defective products |

**Key insight**: specific instruments triggered depend on **what the agent does**, not how it is architecturally classified. The foundational compliance task is producing "an exhaustive inventory of the agent's external actions, data flows, connected systems, and affected persons."

## The M/613 Standards Dependency Graph

The paper emphasises that M/613 standards form a **dependency graph, not a checklist**. Compliance with one standard in isolation is structurally insufficient.

- **prEN 18286** -- QMS (Quality Management System) -- coordinating framework
- **prEN 18228** -- Risk management
- **prEN 18229-1/2** -- Trustworthiness (two parts)
- **prEN 18282** -- Cybersecurity (interacts with M/606 CRA standards)
- **prEN 18284** -- Data governance (interacts with GDPR DPIAs)
- **prEN 18283** -- Bias and fundamental rights

All reference each other normatively. The QMS standard is the coordinating framework.

**Status (April 2026)**: working drafts, not yet adopted. Analysis proceeds from fixed AI Act essential requirements forward to what standards necessarily must operationalise.

## Three Layers of Compliance Architecture

The paper's main prescriptive contribution (Section 7):

1. **AI Act essential requirements** (technology-neutral, binding)
2. **Harmonised standards** (M/613 + M/606) -- operationalise the essentials
3. **Adjacent instruments** (the 8 parallel laws) -- complement the AI Act for specific domains

A complete compliance architecture must integrate all three layers. None is sufficient alone.

## Non-Human Identity Governance

A theme the paper elevates: agent credentials for CRM, email, cloud infrastructure, and payment systems **create privilege management challenges that static identity policies cannot handle**. Mandatory access control frameworks and **just-in-time credential provisioning** are architecturally necessary.

Brubru-relevant: this is exactly what the v1 API key + rate-limit architecture is starting to address. API keys with least-privilege scope, per-key rate limits, revocation. Enterprise tier explicitly includes multi-seat SSO and "API keys with higher rate limits + usage-based credits" because these are compliance levers, not just commercial ones.

## Future Research Directions (Section 10)

Paper identifies seven priority areas:
1. International / European standardisation divergence for GPAI
2. Human oversight design for multi-agent architectures
3. Conformity assessment for continuously learning systems
4. Risk taxonomy for compound AI systems
5. Regulatory sandboxes as standardisation empirical infrastructure
6. Cybersecurity standards architecture bridging M/613 and M/606
7. Cross-jurisdictional comparative analysis (EU, US, others)

## Relevance to Brubru (product + customer angle)

**Brubru as an agent provider.** Brubru Chat is a tool-calling LLM agent. Our 3-tier retrieval architecture (DB smart filters -> on-demand live fetchers -> v1 API backstop) qualifies as **anticipated adaptive behaviour** under this paper's taxonomy -- NOT substantial modification requiring re-conformity assessment, PROVIDED we document and risk-assess it. Our `frontend/public/data-architecture/index.html` page IS an exhaustive inventory of agent actions and data flows; see the dedicated "Brubru's AI Act compliance posture" section there.

**Brubru for agent-provider customers.** The 8 platforms in our outreach (Discord, Coinbase, Roblox, Epic Games, Yubo, Automattic, Grindr, Nextdoor) are all AI agent providers or operate AI-agent-like systems. This paper gives us a concrete talking point: Brubru monitors all 9 instruments in the stack, with daily guide updates, on-demand live fetching of CEN/CENELEC standards development, and a coverage claim that matches the "exhaustive inventory" requirement of Article 50.

**Gap this paper reveals.** Published evaluation infrastructure for multi-agent behavioural stability does not yet exist. Brubru's Predictions feature (MEP vote scoring, procedure outcome forecasts) is adjacent -- and there is a 2027 roadmap item to extend it to **AI agent behavioural benchmarks**. See `memory/project_predictions_surgical_roadmap.md`.

## Related Brubru Guides

- `ai_act_regulation.md` -- the AI Act itself
- `ai_act_amendments_2026.md` -- 2026 amendments (nudification ban + high-risk delay)
- `ai_continent_action_plan.md` -- Commission Apply AI Strategy
- `cybersecurity_act.md` -- CRA + Delegated Regulation 2026/881
- `gdpr` (via `eu_justice_security.md`) -- data protection overlap
- `digital_markets_act.md`, `dsa_enforcement.md` -- platform regulations
- `coinbase_platform_regulation.md`, `discord_platform_regulation.md`, etc. -- per-platform 9-instrument exposure

## Sources

- Nannini et al. (April 2026), arXiv 2604.04604v1: https://arxiv.org/html/2604.04604v1
- Regulation (EU) 2024/1689: https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32024R1689
- Commission Standardisation Request M/613: https://ec.europa.eu/growth/tools-databases/enorm/mandate/613_en
- CEN/CENELEC JTC 21: https://www.cencenelec.eu/european-standardization/sector-forums/digital-single-market/
- EU Code of Practice for GPAI Models (July 2025): https://digital-strategy.ec.europa.eu/en/policies/ai-code-practice
- Digital Omnibus proposals (November 2025): see Commission AI webpage
