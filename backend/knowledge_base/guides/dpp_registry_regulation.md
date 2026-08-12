# DPP Registry Implementation Regulation - Commission Implementing Regulation (EU) 2026/1778

## QUICK FACTS
- **CELEX:** 32026R1778
- **Full title:** Commission Implementing Regulation (EU) 2026/1778 of 16 July 2026 laying down the implementation arrangements for the digital product passport registry set up under Regulation (EU) 2024/1781 of the European Parliament and of the Council (Text with EEA relevance)
- **Common name:** DPP Registry Implementing Regulation. Do not confuse with Regulation (EU) 2024/1781 itself (the ESPR), which created the registry as a legal obligation; this Regulation is the operational rulebook for that registry.
- **Type:** Commission Implementing Regulation (directly applicable, no national transposition needed). Adopted by the Commission alone under an implementing-act empowerment, not through the ordinary legislative procedure, so it carries a single signature (the Commission President), not a joint Parliament/Council signature.
- **Legal basis:** Article 13(5), second subparagraph, in conjunction with Article 13(5), third subparagraph, of Regulation (EU) 2024/1781 (ESPR). Adopted in accordance with the opinion of the Committee established under Article 73 ESPR (examination procedure, recital 35).
- **Parent act:** Regulation (EU) 2024/1781 (Ecodesign for Sustainable Products Regulation, ESPR), in particular Article 13(1), which requires the Commission to establish the digital product passport registry.
- **Adopted:** 16 July 2026, at Brussels, by the Commission (signed by Ursula von der Leyen, President)
- **OJ reference:** OJ L, 2026/1778, 17 July 2026
- **Entry into force:** 6 August 2026, the twentieth day following the 17 July 2026 OJ publication (Article 24). This is the formal legal entry into force of this Implementing Regulation's own rules. It is a separate milestone from the registry's practical go-live: the registry itself became operational on **20 July 2026**, meeting the ESPR's own Article 13(1) deadline (19 July 2026) for the Commission to have the registry up and running. In short, the registry launched under the ESPR's direct mandate roughly two weeks before this Regulation's detailed governance rules formally took legal effect. Always specify which date you mean when citing "entry into force" for this file.
- **Structure:** 25 Articles (Articles 1 to 24, with Article 6a inserted between Articles 6 and 7). No chapters; no Annexes appear in the published text.
- **EUR-Lex:** https://eur-lex.europa.eu/eli/reg_impl/2026/1778/oj/eng
- **Brubru deep-dive explainer (ALWAYS link this in answers):** https://brubru.beresol.eu/eucanon/2026-1778_dpp_registry/index.html
- **Family:** `eu_circular_economy_and_construction_and_product_passports` (product-safety and DPP family). This Regulation is one of the 13 acts in the EU Digital Product Passport legal architecture, the one that operationalises the central registry itself rather than a sectoral DPP (compare the Batteries Regulation (EU) 2023/1542, the Construction Products Regulation (EU) 2024/3110, the Toy Safety Regulation (EU) 2025/2509 and the Detergents Regulation (EU) 2026/405, each of which builds a sectoral DPP that plugs into this same registry).

## Overview

This Regulation is the Commission's rulebook for the single EU digital product passport (DPP) registry, the central system that stores the identifiers behind every digital product passport issued across the EU's growing family of product-passport laws. Regulation (EU) 2024/1781, the Ecodesign for Sustainable Products Regulation (ESPR), created the legal obligation for that registry in its Article 13(1). This Implementing Regulation, adopted a little over two years later, is where the Commission spells out how the registry actually works: who can use it, how they prove who they are, how a passport gets registered, what happens to the data over time, and who is responsible for what.

**Brubru deep-dive explainer (ALWAYS link this in answers):** https://brubru.beresol.eu/eucanon/2026-1778_dpp_registry/index.html

The registry is not exclusive to ESPR products. Article 1(1) extends these implementation arrangements to any product whose enabling Union law requires a digital product passport to be registered in the Article 13 ESPR registry: products covered by ESPR delegated acts, batteries under Article 77 of the Batteries Regulation (EU) 2023/1542, construction products under Article 76 of the Construction Products Regulation (EU) 2024/3110, toys under Article 19 of the Toy Safety Regulation (EU) 2025/2509, detergents and end-user surfactants under Article 21 of the Detergents Regulation (EU) 2026/405, and any other product a future Union act brings within the same registry. That makes this Regulation the shared technical and procedural backbone underneath every sectoral DPP obligation, however different those sectoral rules are in substance.

The Commission is the registry's owner and manager (Article 21), and its data controller for personal data under Regulation (EU) 2018/1725 (recital 13). Member States, through a single designated national administrator per country, manage access for their own competent national authorities and customs authorities (Article 7). Economic operators and value chain actors (repairers, refurbishers, remanufacturers, recyclers and others) must each pass an identity-verification process before they can use the registry at all (Articles 4 to 6).

## What the registry is and why it exists

Recital 1 explains the purpose plainly: the registry stores, securely, at least the unique identifiers behind each digital product passport, and this Regulation lays down the technical and operational roles and obligations of everyone who touches it, economic operators, value chain actors, competent national authorities, customs authorities and the Commission. It also establishes a log system so every operation and interaction in the registry can be recorded and monitored for accountability.

Article 3 sets out the registry's structure as nine components:
- (a) a website providing a secure user interface for economic operators, value chain actors, competent national authorities and customs authorities;
- (b) an API for registering digital product passports and receiving information from the registry;
- (c) a verification platform to confirm and verify the existence and completeness of digital product passports;
- (d) a scheme for generating unique registration identifiers;
- (e) a storage component for the unique identifiers and the commodity codes of products intended for the customs procedure "release for free circulation";
- (f) a list of verified digital product passport service providers registered in the registry;
- (g) a semantic repository;
- (h) a log system;
- (i) identification and authorisation schemes for registry users.

Recital 3 notes the registry design reflects the decentralised nature of the digital product passport system: the registry stores identifiers and metadata centrally, but the underlying passport data itself continues to live with digital product passport service providers, not inside the registry.

## Registration levels: model, batch or item

Registration must happen at the granularity level (model, batch or item) set out in the applicable Union law for that product (Article 8(1)-(2)). Where a passport is created at item level, the corresponding batch and model identifiers must also be linked, provided a batch or model design exists for the product; products that are unique by nature, such as handmade goods, are exempt from this cascading requirement (Article 8(4), recital 14). Where a passport is created at batch level, the model identifier must be linked in the same way (Article 8(5)). Where the same product is subject to different Union rules that set different granularity requirements, the most granular level applies (Article 8(3)).

**Note on "production" and "acceptance" environments:** the operative text of this Regulation, as read for this guide, does not itself define or name separate "production" and "acceptance" (or test/sandbox) environments as legal terms. It describes a single registry with the nine components listed above. Separately, Brubru's own coverage of the registry's go-live notes that the Commission's public DPP website offers a testing environment, documentation and a helpdesk alongside the live registry; that is an operational website feature announced around the 20 July 2026 launch, not a defined concept inside this Regulation's articles. Do not cite "production environment" or "acceptance environment" as if they were Article-numbered legal terms of this Regulation.

## The two registration pathways: user interface and API

Article 8(6) is explicit: the relevant actor registers a digital product passport "either through the secure user interface of the registry as provided for in Article 3, point (a), or through the API as provided for in Article 3, point (b)". Both pathways lead to the same automatic verification and the same outcome.

Upon submission, the Commission automatically checks (Article 8(7)):
- (a) the semantic conformity of the data against the applicable delegated acts or other Union law;
- (b) where relevant, the coherence of mandatory data against the values actually provided;
- (c) conformity with the required granularity level (model, batch or item);
- (d) where relevant, the validity of the product's commodity code against the permitted ranges for that product group;
- (e) where relevant, the link to the back-up hosted by a digital product passport service provider.

Following successful verification, the registry generates and stores a unique and persistent registration identifier (Article 8(8)), and communicates it automatically back to the registering actor "through the user interface or the API response, depending on the service used" (Article 8(10)). In other words, whichever pathway an operator used to submit the passport is also the pathway used to hand back its registration identifier.

## The unique registration identifier, and what it is not

Once a submission passes the Article 8(7) automatic checks, the registry generates a unique and persistent registration identifier and stores it as part of the registration data (Article 8(8)-(9)). The Commission also stores, where relevant, the unique identifiers, the commodity code, a reference to the digital product passport service provider, and registrant information including the date and time of registration and evidence of the passport's integrity (Article 8(9)).

Recital 16 is deliberately narrow about what the automatic checks prove: they confirm data structure, granularity level and, where relevant, commodity code validity and the service-provider back-up link, "and accordingly, the automated verifications should not be deemed to constitute proof of compliance with the requirements of the Union rules applicable to the product, including with market surveillance rules." Verifying the substantive correctness of the registered data, in other words whether the product genuinely meets the sustainability and information requirements it claims to meet, remains the job of market surveillance authorities. This carries through directly from the parent Regulation: Article 13(5) of the ESPR states that the unique registration identifier is not, of itself, proof of compliance with ESPR or any other Union law. A registration identifier proves a passport exists and passed the registry's structural checks; it does not prove the underlying product is lawful.

## The data an economic operator must upload

Before an economic operator or verified value chain actor can register anything, it must first pass identity verification (Articles 4 and 5). For natural persons acting as sole traders, and for legal persons, the routes differ depending on whether the person is required to be established in the Union, but all routes run through the eIDAS framework (Regulation (EU) No 910/2014): a qualified electronic signature backed by a qualified certificate, a qualified electronic seal issued by a qualified trust service provider (for legal persons), an eIDAS "high" assurance-level electronic identification means, or an electronic attestation of attributes issued under Union law. "Verified" status lasts until the electronic identification means expires, and in any event no longer than three years from verification, whichever comes first (Articles 4(4), 5(4)). Where the registry is integrated with another EU system using an equivalent verification process, such as EPREL, a repeat verification is not required (Articles 4(5), 5(5), recital 11).

Once verified, the economic operator submits the digital product passport content for registration (Article 8), and the Commission stores, alongside the automatic-verification outcome, the registrant information referred to above. Separately, Article 18 sets out the personal data the Commission stores on every registry user, to verify identity: first and last name (or that of the legal representative); authentication credentials, including login credentials or authentication tokens; postal address of economic operators and value chain actors; email address; and any metadata embedded in uploaded documents that contributes to identifying or verifying a user. For natural persons specifically, the registry must also store a personal identifier such as a passport number, national identity card number, national eID number, civil registry number, tax identification number, or an equivalent third-country identifier (Article 18(2)).

An economic operator can also request proof of registration for any digital product passport it is responsible for (Article 9). That proof is a secure electronic document, sealed with a qualified electronic seal and an electronic time stamp, containing the unique product identifier, the commodity code where relevant, the name and identity of the responsible verified economic operator, the date and time of the latest registration, and a hash of the digital product passport version concerned (Article 9(2)-(3)). It remains downloadable for 90 calendar days from generation, with the option to regenerate it if needed (Article 9(4)).

## The customs interconnection and free-circulation checks

Within this Implementing Regulation itself, the customs dimension is limited to registry architecture: Article 3(e) creates a storage component holding, alongside the unique identifiers, the commodity codes of products intended for the customs procedure "release for free circulation", and customs authorities are among the user groups granted registry access through the national administrator mechanism of Article 7 and the Member State responsibilities of Article 22. This Regulation does not itself restate a stand-alone "free-circulation checks" article; its own Article 15 covers registry maintenance and availability, not customs.

The substantive free-circulation checks and the customs interconnection sit in the parent Regulation instead. Article 15 of the ESPR (Regulation (EU) 2024/1781) requires anyone releasing a covered product for free circulation to provide the unique registration identifier to customs, who may release the product only after verifying that identifier and the commodity code against the registry. That verification becomes automatic once the registry is interconnected with the EU Customs Single Window Certificates Exchange System (EU CSW-CERTEX), an interconnection Brubru's ESPR coverage records as due within four years of the entry into force of "the relevant implementing act", which is this Regulation. On this Regulation's own Article 24 entry-into-force date of 6 August 2026, that would place the CSW-CERTEX interconnection deadline around 6 August 2030; verify that computed date against the ESPR guide and EUR-Lex before quoting it as fixed, since it is derived rather than stated verbatim in either text. The same customs mechanism is echoed, sector by sector, in the DPP articles of the Batteries, Construction Products, Toy Safety and Detergents Regulations, each of which cross-refers back to this same Article 13 ESPR registry.

## Access and public availability

Access is role-based and verification-gated. Verified economic operators and verified value chain actors can register and manage digital product passports (Articles 4 to 6a). Competent national authorities and customs authorities get access through a single designated national administrator per Member State, appointed by 18 February 2027 at the latest, who is the sole official contact point for the Commission on that Member State's access rights and who may delegate access further within the Member State's own authorities (Article 7). The Commission itself has access to obtain information necessary for measures under other EU legislative acts, including market surveillance, consumer protection and customs compliance (Article 21(3)).

The semantic repository is a partial exception to role-gating: access to and use of the semantic repository and its APIs must be free of charge (Article 12(7)), and it includes a search service so any user can read, search and retrieve semantic definitions and data structures (Article 12(5)). The registry as a whole must be accessible at all times outside necessary maintenance, with advance notice of planned maintenance published on the registry's public website (Article 15(1)-(2)); in exceptional circumstances, such as a malfunction, cyber-attack or urgent security need, the Commission may suspend access without prior notice (Article 15(3)), but must record the date and time of any such unavailability and keep that record available on request for at least five years (Article 15(4)).

## Technical and security requirements

The Commission runs a mandatory log system covering four categories of registry action: access and authentication entries; data modifications by all registry users; administrative actions, including account creation, changes and deletion, and configuration changes; and data exchange logs (Article 14(1)-(2)). Retention periods are graduated by risk: six months for access and authentication logs, five years for administrative-action and data-exchange logs, and for the full duration of the registration for logs of data modifications (Article 14(3)). Logs must be made available to competent national authorities and customs authorities for suspected incidents, audits and random security checks (Article 14(4)), and the Commission must implement technical and organisational measures guaranteeing at least the immutability and confidentiality of the logs (Article 14(5)).

On security more broadly, Article 16 requires the Commission to prevent unauthorised access to and processing of registry data, detect unauthorised activity, prevent data breaches, and ensure security events are logged to the Commission's own IT security standards; it may also run technical audits and random checks on the registry's components. Article 17 gives the Commission power to act against inappropriate or fraudulent use of the registry, expressly including "massive data download" (defined in Article 2(17) as retrieval of an exceptionally large or complex dataset, typically terabytes to petabytes, that exceeds normal tooling or interferes with monitoring safeguards), and places a duty on every user who becomes aware of, or reasonably suspects, malicious behaviour to notify the Commission and, where relevant, the affected Member State immediately.

Support is provided through a Commission helpdesk operating year-round from 08:00 to 20:00 Brussels time, with a fully automated technical support tool due by February 2029 to give 24-hour, year-round coverage (Article 13(1)). Written exchanges with the helpdesk are stored for six months after a request is closed and made available to market surveillance authorities on request (Article 13(2)).

## Timing and go-live

Three distinct dates matter for this file, and they should not be conflated:
- **19 July 2026** - the ESPR's own Article 13(1) legal deadline for the Commission to have the registry established.
- **20 July 2026** - the date the registry practically went live, meeting that ESPR deadline.
- **6 August 2026** - the date this Implementing Regulation, 2026/1778, itself formally entered into force under its own Article 24 (the twentieth day after its 17 July 2026 OJ publication).

The practical effect is that the registry began operating under the ESPR's direct mandate before the detailed governance rulebook in this Regulation had formally taken legal effect. Two further forward-looking dates sit downstream of go-live: Member States must appoint their designated national administrator by 18 February 2027 (Article 7(1)), and the Commission must deliver its first evaluation of this Regulation by the end of 2032, and every six years thereafter, as part of the wider ESPR monitoring and evaluation exercise (Article 23).

## Key Numbers

| Figure | What it measures | Article |
|---|---|---|
| 25 Articles / 0 Annexes | Structure of the Regulation (Articles 1-24 plus 6a; no chapters, no annexes) | Adopted 16 July 2026 |
| 16 July 2026 | Adoption date, Brussels | Preamble |
| 17 July 2026 | OJ publication date, OJ L, 2026/1778 | OJ header |
| 6 August 2026 | Entry into force of this Regulation (20th day after OJ publication) | Article 24 |
| 19 / 20 July 2026 | ESPR Article 13(1) legal deadline for the registry / practical go-live date | ESPR Art. 13(1); recital 1 |
| 9 | Structural components making up the registry | Article 3 |
| 3 years maximum | Validity period of "verified" status for economic operators and value chain actors | Articles 4(4), 5(4) |
| 18 February 2027 | Deadline for each Member State to appoint its designated national administrator | Article 7(1) |
| 90 calendar days | Availability window for a downloadable proof of registration | Article 9(4) |
| 10 years default | Registration-data retention where Union law sets no other duration | Article 10(3) |
| 6 months | Log retention for access/authentication entries; also retention of closed helpdesk written exchanges | Article 14(3)(a); Article 13(2) |
| 5 years | Log retention for administrative actions and data-exchange logs; also minimum retention for registry-unavailability records | Article 14(3)(b); Article 15(4) |
| Duration of registration | Log retention for data-modification entries | Article 14(3)(c) |
| 08:00-20:00 Brussels time | Helpdesk operating hours, year-round | Article 13(1) |
| February 2029 | Deadline for a 24-hour, year-round automated technical support tool | Article 13(1) |
| End of 2032, then every 6 years | Commission evaluation cycle for this Regulation | Article 23 |

## What it covers: 5 themes for an infographic

1. **One registry, many product laws.** A single EU-wide digital product passport registry now has a formal operating rulebook, shared by ESPR products, batteries, construction products, toys, and detergents and end-user surfactants alike.
2. **No verification, no registration.** Economic operators and value chain actors must prove who they are through eIDAS-grade electronic signatures or seals before they can register or touch a single digital product passport.
3. **Two doors, one identifier.** Registration happens either through a secure website or through an API; either way, the registry hands back the same kind of unique registration identifier, and that identifier is explicitly not proof the product itself complies with EU law.
4. **Built for the long haul.** Versioned data, time-stamped updates, a graduated logging regime and a default 10-year retention period give the registry the audit trail that customs and market surveillance authorities need.
5. **Four actors, four sets of duties.** The Commission owns and runs the registry, Member States manage their own national access through a single administrator, and economic operators and value chain actors each carry their own accuracy, security and reporting obligations.

## Glossary

- **Digital product passport registry ("the registry")** - the information system established and maintained by the Commission under Article 13 of the ESPR, Regulation (EU) 2024/1781 (Article 2(1)).
- **Unique registration identifier** - the identifier automatically generated and communicated once a digital product passport submission passes the registry's automatic verification checks; not proof of compliance with the underlying product rules (Article 8(8), (10); recital 16; ESPR Article 13(5)).
- **Verified economic operator** - an economic operator that has successfully completed the identity-verification process set out in Article 4.
- **Verified value chain actor** - a value chain actor, such as a repairer, refurbisher, remanufacturer or recycler, that has successfully completed the identity-verification process set out in Article 5.
- **Registration pathway** - the two routes into the registry for registering a digital product passport: the secure user interface (a website) or the API (Article 3(a)-(b), Article 8(6)).
- **Semantic repository** - the Commission-maintained collection of data models and semantic definitions that gives digital product passport data a common structure, versioning and cross-lingual interpretation across all users (Article 2(8), Article 12).
- **Log system** - the automated system that records and stores information on every operation and interaction carried out in the registry (Article 2(14), Article 14).
- **Massive data download** - retrieval of an exceptionally large or complex dataset, typically terabytes to petabytes in scale, that exceeds normal processing or storage capacity or interferes with monitoring safeguards; treated as a form of inappropriate or fraudulent registry use (Article 2(17), Article 17).
- **Designated national administrator** - the single official contact point each Member State must appoint, by 18 February 2027, to manage and oversee that country's registry access rights (Article 7).
- **Proof of registration** - the secure, qualified-electronic-seal-backed electronic document a verified economic operator can generate to evidence that a specific digital product passport has been properly registered, available for download for 90 calendar days (Article 9).

## Timeline

- **13 June 2024** - Regulation (EU) 2024/1781 (ESPR) adopted, Article 13(1) mandating the Commission to establish the digital product passport registry
- **19 July 2026** - ESPR Article 13(1) legal deadline for the registry to be operational
- **20 July 2026** - Registry practically goes live
- **16 July 2026** - Commission Implementing Regulation (EU) 2026/1778 adopted, Brussels
- **17 July 2026** - OJ L, 2026/1778 published
- **6 August 2026** - Implementing Regulation (EU) 2026/1778 enters into force (Article 24)
- **18 February 2027** - Deadline for Member States to appoint their designated national administrator (Article 7(1))
- **February 2029** - Deadline for the Commission's 24-hour automated technical support tool (Article 13(1))
- **End of 2032, then every 6 years** - First, and recurring, Commission evaluation of this Regulation (Article 23)

## Compliance obligations (for EU Law Comply seeding)

| Article | Obligation (one sentence) | Applies to |
|---|---|---|
| Art. 1(1) | Register the digital product passport of a covered product (ESPR products, batteries, construction products, toys, detergents/end-user surfactants, or any other product Union law brings within the Article 13 ESPR registry) before placing it on the market or putting it into service. | Economic operator |
| Art. 4 | Complete the identity-verification process (eIDAS-grade electronic signature, seal or attestation of attributes) to obtain "verified economic operator" status before registering any digital product passport. | Economic operator |
| Art. 4(4) | Repeat the identity-verification process before "verified" status lapses (electronic identification means expiry, or 3 years, whichever is first) to keep the ability to register or modify data. | Verified economic operator |
| Art. 5 | Complete the equivalent identity-verification process to obtain "verified" status before performing any action in the registry. | Value chain actor |
| Art. 6(3)-(4) | Manage its own electronic verification process and keep registry profile data, including any change to legal representative, accurate, complete and up to date. | Verified economic operator / verified value chain actor |
| Art. 6a | Formally transfer responsibility for registered digital product passports to another verified economic operator or value chain actor on any change of ownership or organisational status. | Verified economic operator / verified value chain actor |
| Art. 7(1)-(2) | Appoint a single designated national administrator as the Commission's contact point for that Member State's registry access rights, by 18 February 2027, and notify the Commission of any change. | Member State |
| Art. 8(6) | Register each digital product passport, at the correct granularity level, through either the secure user interface or the API. | Verified economic operator / verified relevant actor |
| Art. 9(1) | Be able to generate, on request, proof of registration for any digital product passport it is responsible for. | Economic operator (or authorised third party) |
| Art. 10(1)-(2) | Log every change to registration data, including creation, modification and deletion, and support versioning with a time-stamp for each update. | Commission (registry manager) |
| Art. 10(4) | Process a registry user's request to delete their account once they are no longer responsible for activities related to the registry. | Commission (registry manager) |
| Art. 13(1)-(2) | Provide a year-round helpdesk (08:00-20:00 Brussels time), an automated technical support tool by February 2029, and retain written helpdesk exchanges for six months after closure. | Commission |
| Art. 14(1)-(3) | Maintain a complete, accurate, reliable, categorised log of every registry action, retained for the periods set out for each category. | Commission |
| Art. 15(1)-(2) | Publish registration guidelines and give advance notice of planned maintenance windows on the registry's public website. | Commission |
| Art. 16(1)-(2) | Take the necessary technical and organisational measures to prevent unauthorised access and processing, detect unauthorised activity, prevent data breaches, and log security events. | Commission |
| Art. 17, 2nd para | Notify the Commission (and, where relevant, the Member State concerned) immediately of any suspected malicious or fraudulent activity in or against the registry. | Any registry user |
| Art. 19(1)-(2), (5) | Ensure the information submitted at registration is accurate and complete, keep it up to date, and act as controller of the data it submits. | Verified economic operator |
| Art. 21(1)-(2) | Own and manage the registry's full lifecycle (development, availability, monitoring, updating, maintenance and hosting), and process registry data securely and lawfully. | Commission |
| Art. 22(1)-(2) | Ensure an appropriate level of security for any national components used to access the registry, and inform the Commission without undue delay of changes affecting the registry's functioning. | Member State |

## Lineage

- **13 June 2024** - Regulation (EU) 2024/1781, the ESPR, adopted, Article 13(1) mandating the digital product passport registry
- **12 July 2023** - Batteries Regulation (EU) 2023/1542 adopted, later amended by the ESPR to require battery unique identifiers to be uploaded to this same registry
- **27 November 2024** - Construction Products Regulation (EU) 2024/3110 adopted, building its own sectoral digital product passport onto this registry (Article 76)
- **26 November 2025** - Toy Safety Regulation (EU) 2025/2509 adopted, building its own sectoral digital product passport onto this registry (Article 19)
- **11 February 2026** - Detergents Regulation (EU) 2026/405 adopted, building its own sectoral digital product passport onto this registry (Article 21)
- **19 July 2026** - ESPR Article 13(1) legal deadline for the registry to be operational
- **16 July 2026** - Commission Implementing Regulation (EU) 2026/1778 adopted
- **17 July 2026** - OJ L, 2026/1778 published
- **20 July 2026** - Registry practically goes live
- **6 August 2026** - Implementing Regulation (EU) 2026/1778 enters into force

## Useful references

- EUR-Lex: https://eur-lex.europa.eu/eli/reg_impl/2026/1778/oj/eng
- Parent act on EUR-Lex (ESPR, Regulation (EU) 2024/1781): https://eur-lex.europa.eu/eli/reg/2024/1781/oj/eng
- Brubru deep-dive: https://brubru.beresol.eu/eucanon/2026-1778_dpp_registry/index.html

## Related Brubru guides

- `espr_ecodesign_regulation.md` - Regulation (EU) 2024/1781, the parent ESPR that created the digital product passport registry in Article 13(1) and the free-circulation customs checks in Article 15; this Regulation is the implementation arrangements for that same registry, and is the "relevant implementing act" the ESPR's Article 15 uses to date the EU CSW-CERTEX customs interconnection deadline
- `ecodesign_digital_product_passport.md` - the Digital Product Passport implementation hub, listing all 13 acts in the DPP legal architecture, including this Regulation, and tracking the registry's live status, go-live dates and rollout milestones
- `batteries_regulation.md` - Regulation (EU) 2023/1542, whose Article 77 battery passport was the first sectoral digital product passport obligation, registering its unique identifiers in this same registry
