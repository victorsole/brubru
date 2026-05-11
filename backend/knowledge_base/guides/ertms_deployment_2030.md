# ERTMS Deployment Plan and Decision (EU) 2023/1095

## QUICK FACTS

- **Topic**: European Rail Traffic Management System (ERTMS) — deployment plan, technical specifications, and the cross-border signalling backbone for the EU rail network
- **Core deployment instrument**: **Commission Implementing Decision (EU) 2023/1095** of 8 June 2023 amending Decision 2017/1474 as regards the European deployment plan for the European Rail Traffic Management System
- **CELEX**: 32023D1095
- **EUR-Lex**: https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023D1095
- **Technical baseline**: TSI Control-Command and Signalling (TSI CCS) — Regulation (EU) 2023/1695 of 10 August 2023, CELEX 32023R1695
- **TSI baseline (consolidated)**: Commission Implementing Regulation (EU) 2023/1695 — replaces Reg 2016/919
- **Lead DG**: DG MOVE
- **EU Coordinator for ERTMS**: Matthias Ruete (since 2014, EU Coordinator role) — appointment renewed under TEN-T 2024/1679
- **EU Agency for Railways (ERA)**: Regulation (EU) 2016/796 — system authority for ERTMS
- **Commissioner**: Apostolos Tzitzikostas (Sustainable Transport and Tourism)

## What ERTMS is

**ERTMS = ETCS + GSM-R (or FRMCS)**:
- **ETCS (European Train Control System)**: in-cab signalling that supersedes ~30 incompatible national systems
- **GSM-R**: GSM-Railway radio (legacy) being phased out by **FRMCS** (Future Railway Mobile Communication System, 5G-based) post-2030

ETCS comes in three baselines:
- **Baseline 2**: legacy stable version
- **Baseline 3 (Release 2)**: enhanced functionality, deployed since 2016
- **Baseline 4**: integrated with FRMCS, target deployment 2027-2030

ETCS levels:
- **Level 1**: trackside balises + driver display
- **Level 2**: continuous radio-based train detection (most common for new rollouts)
- **Level 3**: moving block (ultimate capacity, post-2030 vision)

## Deployment plan — 2030 / 2040 / 2050

Decision 2023/1095 sets binding deployment milestones aligned with TEN-T:

| Layer | Deadline | Coverage required |
|---|---|---|
| **TEN-T Core Network** | **31 December 2030** | ETCS deployed |
| **TEN-T Extended Core Network** | **31 December 2040** | ETCS deployed |
| **TEN-T Comprehensive Network** | **31 December 2050** | ETCS deployed |

The plan also sets **interim milestones** by corridor and Member State to track progress.

## Member State progress (illustrative, late 2025 figures)

The deployment is uneven across Member States:
- **Leaders**: Switzerland (~70% Core Network), Belgium, Netherlands, Spain
- **Mid-pack**: Italy, Germany (Stuttgart 21 + key freight corridors), France
- **Lagging**: parts of Austria, Slovakia, Hungary

Brubru's `legislative_carriages` table tracks specific deployment-decision implementing acts per Member State.

## Cost + funding

Estimated total deployment cost (2014 figures, escalated) ~€100-150 billion across the EU. Funding sources:
- **CEF Transport** Reg 2021/1153 — typically up to 50% co-financing for ERTMS works
- **EU Recovery and Resilience Facility** — several Member States included ERTMS in their National RRPs
- **EIB loans** — long-tenor financing for infrastructure managers
- **National investment plans** — each Member State has its own deployment plan submitted to ERA

## Key TSIs (Technical Specifications for Interoperability)

| TSI | CELEX | Scope |
|---|---|---|
| TSI Control-Command and Signalling (CCS) | 32023R1695 | The ERTMS technical specification proper |
| TSI Locomotives + Passenger Rolling Stock | 32014R1302 (consolidated) | On-board equipment side |
| TSI Telematics Applications for Freight (TAF) | 32014R0454 | Freight train management data interfaces |
| TSI Operations and Traffic Management | 32019R0773 | Cross-border operations procedures |

## Recent legislative + adoption milestones

- **8 June 2023**: Commission adopts Decision 2023/1095 (deployment plan amendment)
- **10 August 2023**: TSI CCS Reg 2023/1695 published
- **June 2024**: TEN-T Regulation 2024/1679 adopted, locks ERTMS deployment to TEN-T deadlines
- **Q4 2025**: ERA reports first batch of FRMCS pilot deployment outcomes
- **2027-2030**: Baseline 4 + FRMCS rollout
- **2030**: Core Network ERTMS coverage deadline (binding)

## How this flows through Brubru answers

When users ask about:
- "What's the ERTMS deployment deadline for the Mediterranean Corridor?"
- "When does Spain's national plan expire and how is progress tracked?"
- "How does Baseline 4 differ from Baseline 3 Release 2?"
- "What is FRMCS replacing?"
- "Can ERTMS works be co-financed under CEF?"
- "Who is the EU Coordinator for ERTMS?"

→ Brubru anchors responses on CELEX 32023D1095 + 32023R1695, links to ERA's ERTMS dashboard (era.europa.eu/domains/ertms), and surfaces specific deployment-decision implementing acts.

## Cross-link with other Brubru guides

- `ten_t_regulation_2024_1679.md` — TEN-T deadlines locked to ERTMS
- `cef_transport_funding.md` — funding instrument
- `eu_railway_regulation.md` — 4th Railway Package + ERA role
- `military_mobility_dual_use_logistics.md` — dual-use infrastructure overlap (ERTMS is a baseline for cross-border military mobility too)

## Sources

- Decision (EU) 2023/1095 — EUR-Lex CELEX 32023D1095
- TSI CCS Reg 2023/1695 — EUR-Lex CELEX 32023R1695
- ERA ERTMS dashboard: era.europa.eu/domains/ertms
- DG MOVE ERTMS page: transport.ec.europa.eu/transport-themes/infrastructure-and-investment/european-rail-traffic-management-system_en
- EU Coordinator annual reports
