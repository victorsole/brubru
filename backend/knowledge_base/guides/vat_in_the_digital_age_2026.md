# VAT in the Digital Age (ViDA): 2026 Work Programme and Implementation Timeline

## QUICK FACTS
- **LATEST (Monday 27 July 2026 — OSS/IOSS DETAILED RULES REWRITTEN FOR THE FOURTH SPECIAL SCHEME)**: **Commission Implementing Regulation (EU) 2026/1869** (CELEX **32026R1869**, ELI `http://data.europa.eu/eli/reg_impl/2026/1869/oj`) amends **Implementing Regulation (EU) 2020/194**, which lays down the detailed rules applying **Council Regulation (EU) No 904/2010** to the VAT special schemes. It is the administrative-cooperation plumbing for the changes Directive (EU) 2025/516 made to Directive 2006/112/EC. **What changes substantively**: "special schemes" is now defined as **four** schemes, not three — the non-Union scheme, the Union scheme, the import scheme and the **new transfer of own goods scheme** (Title XII, Chapter 6, **Section 5** of Directive 2006/112/EC). The **Union scheme definition is widened** to cover certain supplies of goods **within a single Member State** made by a taxable person, alongside intra-Community distance sales and services. The electronic-reporting rules are harmonised **across all four schemes** so Member States apply them uniformly. **The date that binds: it applies from 1 July 2028**, in step with the Single VAT Registration phase of ViDA — so this is a rule to design systems against now, not a duty that bites today. Adopted on the opinion of the **Standing Committee on Administrative Cooperation**. Source: OJ L, 2026/1869, 28.7.2026.
- **LATEST (Wednesday 20 May 2026, DG TAXUD)**: **ViDA 2026 Work Programme published** — DG TAXUD released the ViDA 2026 implementation work programme detailing the 2026 deliverables on the Digital Reporting Requirements (DRR) standard, Platform Economy adjustments, and Single VAT Registration. The Work Programme is a companion to the September 2025 implementation strategy. Source: taxation-customs.ec.europa.eu/news/vat-digital-age-2026-work-programme-available-2026-05-20_en
- **Main legal acts**:
  - **Directive (EU) 2025/516** (CELEX **32025L0516**) — amending Directive 2006/112/EC on the common system of VAT (Directive on VAT in the Digital Age)
  - **Council Regulation (EU) 2025/517** (CELEX **32025R0517**) — amending Regulation (EU) 904/2010 as regards VAT administrative cooperation requirements
  - **Council Implementing Regulation (EU) 2025/518** (CELEX **32025R0518**) — amending Implementing Regulation 282/2011 on technical rules
- **Adopted**: 11 March 2025 (Council) after EP consultation; published in OJ L of 25 March 2025
- **Application milestones**:
  - **1 January 2027**: One-Stop-Shop (OSS) extension to B2C e-charging supplies + legislative clarifications for OSS/IOSS users
  - **1 July 2028**: Platform economy "deemed supplier" rules for short-term accommodation rentals + road passenger transport via digital platforms; Single VAT Registration (SVR) reforms including mandatory reverse charge for non-established suppliers
  - **1 July 2030**: Mandatory e-invoicing as standard method for cross-border B2B transactions; Digital Reporting Requirements (DRR) using a harmonised e-invoice format
  - **1 January 2035**: Final alignment deadline — Member States with pre-existing domestic transaction-reporting systems must conform to the cross-border DRR framework
- **Lead DG**: DG TAXUD — Commissioner **Wopke Hoekstra** (Climate, Net Zero and Clean Growth — Tax dossier overlap; **Maria Luís Albuquerque** for Financial Services and Investment Union holds adjacent files)
- **EP lead committee**: ECON (consultative role under Article 113 TFEU)
- **Council configuration**: ECOFIN (unanimity required)
- **Legal basis**: Article 113 TFEU (harmonisation of indirect taxation)
- **Procedure**: Special legislative procedure (consultation), unanimity in Council
- **Cross-link**: `eu_one_stop_shop_oss_ioss`, `digital_services_act`, `short_term_rentals_regulation`, `eu_administrative_cooperation_directive`

This guide covers the **VAT in the Digital Age (ViDA)** package: a three-act reform of the EU VAT system that modernises reporting, fights cross-border fraud (estimated EUR 11+ billion annual loss in carousel + missing-trader fraud), and adapts the platform economy treatment for accommodation and passenger transport.

## What ViDA does — the three pillars

### Pillar 1 — Digital Reporting Requirements (DRR)

From **1 July 2030**, intra-EU B2B transactions must be invoiced using a **structured electronic invoice** that conforms to the **EN 16931** European e-invoicing standard (currently the standard used in the eInvoicing Directive 2014/55/EU public-procurement context).

Practical changes:
- The current recapitulative statement (EU sales list) is replaced by **near-real-time DRR transmission** to the Member State tax authority and onward to a Central VIES (VAT Information Exchange System) repository
- Each invoice carries 14 structured data elements (supplier VAT, customer VAT, supply date, taxable amount, applicable VAT rate, etc.)
- Transmission must occur **within 10 days** of invoice issuance (down from monthly summary reporting today)
- The DRR data model is harmonised at EU level; Member States may not impose additional national reporting fields beyond the EN 16931 core data set

Member States operating an existing domestic e-invoicing/DRR system (notably **Italy** with SDI, **France** with the Chorus Pro + Y-scheme, **Spain** with TicketBAI/Verifactu, **Germany** with the e-invoicing mandate from January 2025, **Hungary** with the NAV Online Számla, **Poland** with the KSeF) must converge to the EU model by **1 January 2035**.

### Pillar 2 — Platform Economy (deemed supplier)

From **1 July 2028**, digital platforms facilitating B2C supplies in two specific sectors become **VAT-deemed suppliers**:

- **Short-term accommodation rentals** (continuous rental ≤ 30 days per stay) — applies to Airbnb, Booking, Vrbo, etc.
- **Road passenger transport** — applies to Uber, Bolt, FreeNow, etc.

What "deemed supplier" means:
- The platform is treated as if it bought the service from the underlying provider and resold it to the consumer
- The platform charges and accounts for VAT on the consumer-facing transaction (with proportional treatment if the underlying provider is itself VAT-registered)
- Small underlying providers (below the SME threshold) effectively see the platform handle their VAT compliance for the platform-facilitated supplies
- This closes the "Airbnb gap" where many small hosts were below national VAT registration thresholds and entire platform supplies effectively escaped VAT

This pillar interacts directly with **Regulation (EU) 2024/1028** on STR transparency (see `short_term_rentals_regulation` guide).

### Pillar 3 — Single VAT Registration (SVR)

From **1 July 2028**, the **One-Stop-Shop (OSS)** is extended substantially to cover:
- B2C movements of own goods cross-border (today these require multiple national VAT registrations)
- B2C supplies to a Member State other than the supplier's establishment
- B2C electronic chargers (e-mobility) supplies (from 1 January 2027 — earlier than the main SVR date)
- **Mandatory domestic reverse charge** for B2B supplies by non-established suppliers (Article 194 reform) — non-established suppliers no longer need to VAT-register in each Member State where they supply B2B; the customer self-accounts under reverse charge

For businesses, the practical effect is one VAT registration in a single Member State of identification + OSS return to cover most cross-border B2C and intra-EU B2B activity. Estimated administrative cost saving: EUR 8.7 billion over 10 years (Commission impact assessment).

## The 2026 Work Programme

The 20 May 2026 Work Programme details the deliverables DG TAXUD will pursue during 2026 to prepare for the 2027 OSS extension and the 2028 deemed-supplier launch:

1. **EN 16931 alignment**: technical work with CEN on the next-version e-invoice standard (closes gaps in B2B intra-EU use cases)
2. **DRR pilot programmes**: voluntary early adoption by large multinational corporates (designed jointly with the Permanent Committee on Administrative Cooperation, SCAC)
3. **Platform deemed-supplier guidance**: Q&A explanatory notes for digital platforms in scope from 1 July 2028 (consultation Q3 2026)
4. **SDEP–OSS interaction note**: how STR platform data flows from the SDEP (Reg 2024/1028) interact with the OSS reporting from 1 July 2028
5. **OSS/IOSS technical updates**: 2027 OSS extension for e-mobility chargers
6. **Member State implementation tracking dashboard**: similar to the eInvoicing Directive monitoring, public dashboard showing each Member State's DRR readiness
7. **SME impact study**: targeted micro/small-business support package (estimated 1.6M SMEs affected by the reverse-charge change)

The Work Programme also lists the **secondary legislation** the Commission will table in 2026:
- Updated Implementing Regulation on the OSS/IOSS technical rules (Q4 2026)
- Implementing Act on the DRR data model (Q3 2026)
- Implementing Act on the deemed-supplier rules for platforms (Q1 2027)

## Who is affected

- **All VAT-registered businesses** in the EU active in B2B intra-EU trade — DRR from 1 July 2030
- **Online platforms** for short-term accommodation rentals and road passenger transport — deemed-supplier from 1 July 2028 (Airbnb, Booking, Uber, Bolt, FreeNow, MyTaxi, Cabify in scope as applicable)
- **B2C cross-border sellers** — OSS extension from 1 July 2027 + 1 July 2028
- **Non-established B2B suppliers** — mandatory reverse charge from 1 July 2028 (current voluntary regime under Article 194 becomes mandatory)
- **VAT administrations** in 27 Member States — DRR infrastructure + SCAC coordination
- **E-invoicing service providers** (BasWare, Pagero, Tradeshift, eDOC, Doc Process, Generix, OpenText, SAP Ariba, Coupa, OpenPeppol) — interoperability via PEPPOL BIS Billing 3.0 + EN 16931

## Interaction with the corporate-tax agenda

ViDA is the indirect-tax flagship; it sits alongside:
- **BEFIT (Business in Europe: Framework for Income Taxation)** — Commission proposal COM(2023)532 (procedure 2023/0321(CNS), still in trilogue/negotiation)
- **TP (Transfer Pricing) Directive** — COM(2023)529 (procedure 2023/0322(CNS))
- **Pillar Two** (Reg (EU) 2022/2523 implementation continuing)

## Practical implications for Brubru users

- **For multinational tax teams**: budget 18-24 months from January 2027 for DRR readiness; the EN 16931 + PEPPOL integration is the longest lead-time work item
- **For platform operators**: the 1 July 2028 deemed-supplier shift requires legal entity restructuring decisions (Member State of identification choice for OSS) and significant systems work — start scoping Q3 2026
- **For SMEs**: the SVR + reverse-charge changes are largely **simplifications** — fewer registrations, more consistent compliance flow; the DRR is the disruptive bit
- **For tax administrators**: the SCAC-coordinated DRR rollout requires national IT investment (estimated EUR 200-500M per Member State)

## Source list

- Directive text: EUR-Lex CELEX 32025L0516
- Council Regulation: CELEX 32025R0517
- Implementing Regulation: CELEX 32025R0518
- DG TAXUD Work Programme landing page (20 May 2026): taxation-customs.ec.europa.eu/news/vat-digital-age-2026-work-programme-available-2026-05-20_en
- DG TAXUD ViDA dossier: taxation-customs.ec.europa.eu/taxation-1/value-added-tax-vat/vat-digital-age_en
- EU Inventory of VAT rates per Member State: taxation-customs.ec.europa.eu/taxation-1/economic-analysis-taxation/data-taxation-trends_en
- EN 16931 specification: CEN (TC 434)

## See also

- `eu_one_stop_shop_oss_ioss` — OSS/IOSS context and current pre-ViDA rules
- `short_term_rentals_regulation` — Reg (EU) 2024/1028 STR transparency, applying from 20 May 2026
- `digital_services_act` — DSA platform classification overlay
- `eu_administrative_cooperation_directive` — Member State VAT administrative cooperation framework
