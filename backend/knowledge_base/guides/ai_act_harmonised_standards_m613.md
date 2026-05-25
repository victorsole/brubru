# AI Act Harmonised Standards — M/613 + M/606 Programme

## QUICK FACTS
- **LATEST (Friday 22 May 2026 — TRANSPARENCY CODE OF PRACTICE, 3rd WG ROUND)**: DG CNECT held the **third round of working-group meetings** on the **AI Act transparency Code of Practice** (the Article 50 instrument on labelling AI-generated/manipulated content — deepfakes, synthetic media — distinct from the M/613 harmonised standards tracked in this guide). It is a separate soft-law deliverable accompanying the Article 50 transparency obligations that apply from **August 2026**. Source: digital-strategy.ec.europa.eu (22 May 2026). Cross-link: `ai_act_regulation.md` for the Article 50 timeline; this guide tracks the M/613 + M/606 harmonised-standards stream.
- Topic: EU Commission Standardisation Requests that operationalise the AI Act's and Cyber Resilience Act's essential requirements
- Standardisation Requests: **M/613** (AI Act) to CEN/CENELEC JTC 21, and **M/606** (CRA) to CEN/CENELEC
- Legal function: harmonised standards create a **presumption of conformity** with AI Act essential requirements (Chapters III + V) for high-risk systems and GPAI models
- Status (April 2026): working drafts under M/613 circulating. Draft adoption + OJ publication expected 2026-2027.
- Canonical source: Nannini et al. April 2026 "AI Agents Under EU Law" (arXiv 2604.04604v1) -- see dedicated guide `ai_agents_compliance_architecture_eu.md`
- Responsible committee: CEN/CENELEC JTC 21 (Artificial Intelligence)
- Parallel work: ISO/IEC JTC 1/SC 42 (international) -- convergence/divergence risk
- Brubru coverage: /news scrapes JTC 21 publications and EU Commission Digital Strategy AI pages on each morning run

## Eight Working Drafts Under M/613 (January 2026 snapshot)

| Draft | Topic | Role in dependency graph |
|---|---|---|
| **prEN 18286** | Quality Management System (QMS) for AI systems | **Coordinating framework.** Other standards plug into its QMS processes. |
| **prEN 18228** | Risk management for AI systems | Operationalises AI Act Articles 9 (risk management system for high-risk) |
| **prEN 18229-1** | Trustworthiness — Part 1 | Fundamental concepts, trustworthiness properties |
| **prEN 18229-2** | Trustworthiness — Part 2 | Specific operational requirements |
| **prEN 18282** | Cybersecurity for AI systems | Article 15(4); interacts with M/606 CRA standards. API-layer least-privilege is the key theme. |
| **prEN 18284** | Data governance | Article 10; interacts with GDPR Data Protection Impact Assessments |
| **prEN 18283** | Bias + fundamental rights | Article 10(5); integration with non-discrimination and equality law |

All are working drafts -- NOT adopted. Numbers and scopes may change before OJ publication. After publication, the standards become "harmonised" only when referenced in the OJ L-series under Article 41 AI Act.

## Standards as a Dependency Graph (Not a Checklist)

The key regulatory-design insight: compliance with a single standard in isolation is **structurally insufficient**. Standards reference each other normatively. The QMS standard (prEN 18286) is the coordinating framework, with risk management, trustworthiness, cybersecurity, data governance, and bias all feeding into and drawing from it.

A provider must demonstrate compliance with the relevant set collectively; cherry-picking is not an option.

## M/606 — Cyber Resilience Act Standardisation Programme

- Parent regulation: Regulation (EU) 2024/2847 (Cyber Resilience Act, CELEX 32024R2847)
- First delegated regulation: (EU) 2026/881 of 11 December 2025 on vulnerability handling obligations (see `cybersecurity_act.md`)
- Bridges M/613 prEN 18282 (AI cybersecurity) with horizontal CRA cybersecurity for products with digital elements
- Manufacturer obligations: vulnerability handling, security updates, essential cybersecurity requirements (Annex I CRA), SBOM, 5-year support minimum

## Why M/613 + M/606 matter for agentic systems

The Nannini et al. paper establishes that **high-risk agentic systems with untraceable behavioural drift cannot currently satisfy essential requirements** — not because the requirements themselves are unmet, but because **published evaluation infrastructure for multi-agent behavioural stability does not yet exist in harmonised-standard form**.

In practice this means:
- Deploying a high-risk agent today requires the provider to document the risk assessment themselves, without a published standard to follow
- Once M/613 standards are adopted, providers gain a clear conformity path
- The 2026-2027 window is when providers who act early shape the standards; providers who wait inherit whatever is adopted

## Application Dates + Obligations Timeline

| Date | Obligation |
|---|---|
| 2 February 2025 | AI Act prohibitions applied (Article 5) |
| 2 August 2025 | GPAI obligations applied + Code of Practice for GPAI Models (July 2025) |
| 2 August 2026 | High-risk AI systems obligations (Annex III) apply |
| 11 December 2027 | Cyber Resilience Act core obligations apply |
| 2028 (expected) | M/613 harmonised standards published in OJ, presumption-of-conformity available |

## Brubru's Role

- Daily /news monitors JTC 21 publications + Commission Digital Strategy AI pages
- Provides per-company compliance readings (9-instrument surface) for the 8 outreach platforms
- Tracks proposals through OEIL + EUR-Lex as they move toward adoption

## Related Brubru Guides

- `ai_agents_compliance_architecture_eu.md` — full 9-instrument mapping and agentic-system risks
- `ai_act_regulation.md` — the AI Act itself
- `cybersecurity_act.md` — CRA + Delegated Regulation 2026/881 on vulnerability handling
- `ai_act_amendments_2026.md` — 2026 amendments
- Platform guides: `discord_platform_regulation.md`, `coinbase_platform_regulation.md`, `roblox_platform_regulation.md`, etc.

## Sources

- Commission Standardisation Request M/613: https://ec.europa.eu/growth/tools-databases/enorm/mandate/613_en
- Commission Standardisation Request M/606 (CRA): https://ec.europa.eu/growth/tools-databases/enorm/mandate/606_en
- CEN/CENELEC JTC 21 page: https://www.cencenelec.eu/european-standardization/sector-forums/digital-single-market/
- ISO/IEC JTC 1/SC 42: https://www.iso.org/committee/6794475.html
- Nannini et al. April 2026, arXiv 2604.04604v1: https://arxiv.org/html/2604.04604v1
