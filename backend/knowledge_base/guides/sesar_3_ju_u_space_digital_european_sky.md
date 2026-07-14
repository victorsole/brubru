# SESAR 3 JU, U-space and the Digital European Sky

## QUICK FACTS
- Full name: SESAR 3 Joint Undertaking (Single European Sky ATM Research 3 Joint Undertaking)
- Legal basis: Council Regulation (EU) 2021/2085 of 19 November 2021 establishing the Joint Undertakings under Horizon Europe (the "Single Basic Act", CELEX 32021R2085) -- SESAR 3 JU is one of nine Horizon Europe institutionalised partnerships created under this Regulation
- Mandate: 2021-2031 (10 years, aligned with Horizon Europe 2021-2027), plus an additional completion phase to close out the Multiannual Work Programme
- Mission: "the technological pillar of the EU's Single European Sky policy" -- defines, develops and deploys the technologies to deliver the **Digital European Sky**: digitalisation and automation of European air traffic management (ATM) covering conventional aircraft, drones, air taxis and higher-altitude vehicles in one integrated airspace
- Type: institutionalised European public-private partnership under Horizon Europe
- Members: European Commission, Eurocontrol, and more than 50 organisations spanning the full aviation value chain (air navigation service providers/ANSPs, airlines/airspace users, airports, manufacturers of ground and aircraft equipment, the scientific/research community, and drone operators) -- Founding Members plus Associated Members admitted via periodic calls
- Governing Board: European Commission + Eurocontrol + SESAR 3 JU + Members representatives; approves the Multiannual/Bi-Annual Work Programme and the European ATM Master Plan
- Executive Director: Andreas Boschen (appointed May 2022; European Commission official, previously managed EU CEF co-funding for SESAR deployment)
- Budget: co-funding exceeding EUR 1.6 billion for SESAR 3 (2021-2031) -- EUR 600 million from Horizon Europe, up to EUR 500 million from Eurocontrol (in-kind and financial), at least EUR 500 million from industry members (in-kind and financial), and at least EUR 200 million for Digital Sky Demonstrators from the Connecting Europe Facility (CEF)
- Steering document: **European ATM Master Plan**, 2025 edition published 12 December 2024 -- structured around 10 Strategic Deployment Objectives (SDOs) to be implemented by 2035, five technological levers (trajectory-based operations, greater air-ground/ground-ground data volumes, automation between flight deck and ground, human-machine teaming, dynamic airspace), targeting the most efficient and environmentally friendly sky in the world by 2045
- Expected benefits: up to 400 million tonnes of CO2 saved by 2050 (100 Mt by 2035, 200 Mt by 2040); EUR 17 return per euro invested by 2050 for SESAR investors, rising to EUR 53 counting broader socio-economic benefits
- U-space regulatory framework: Commission Implementing Regulation (EU) 2021/664 (U-space regulatory framework, CELEX 32021R0664), Commission Implementing Regulation (EU) 2021/665 (amending Reg 923/2012 on operations of manned aircraft in U-space airspace, CELEX 32021R0665), Commission Delegated Regulation (EU) 2021/666 (requirements for manned aircraft operating in U-space airspace, CELEX 32021R0666) -- all applicable from 26 January 2023
- U-space service delivery: U-space Service Providers (USSPs, certified/authorised at national level) plus a Common Information Service (CIS) that shares static and dynamic airspace data; drone operators must use USSP services (network identification, geo-awareness, flight authorisation, traffic information, conflict information) within designated U-space airspace
- Maturity roadmap (SESAR U-space Blueprint): U1 Foundation (e-registration, e-identification, geofencing) -> U2 Initial (flight planning/approval, tracking, ATM coordination) -> U3 Advanced (automated conflict detection/collision avoidance for dense/complex operations) -> U4 Full (comprehensive automation and connectivity)
- Key adjacencies: Eurocontrol (intergovernmental ANS coordination, co-funder, Performance Review Body for SES2+), EASA (certification of drones/U-space service providers and manned/unmanned airworthiness), DG MOVE (Single European Sky policy owner), DG DEFIS/RTD (Horizon Europe partnership oversight), EU Space Programme/Galileo (positioning for U-space), Clean Aviation JU (separate Horizon Europe partnership on propulsion/airframe decarbonisation -- do not conflate)
- Related file: Single European Sky 2+ (SES2+), procedure 2013/0186(COD), long-running trilogue -- SESAR 3 JU is the R&I delivery arm of the same policy family
- Verify live: current Governing Board membership roster, latest Bi-Annual Work Programme (2026-2027, adopted end 2025), and any newer ATM Master Plan edition before citing exact figures in client-facing material

SESAR 3 JU is the Horizon Europe institutionalised partnership responsible for researching, testing and validating the technologies needed to modernise European air traffic management -- the "Digital European Sky". It also runs the EU's U-space regulatory research strand, the framework that governs how drones share airspace safely with manned aviation. Brubru's Single European Sky coverage has so far centred on `aviation_transport_policy.md` (SES2+ legislative file); this guide adds the research/innovation and drone-integration layer that sits underneath it.

## What SESAR 3 JU Does

SESAR 3 JU does not itself operate airspace or certify equipment -- it funds and coordinates EU-wide research, development, validation and (via demonstrators) early deployment of ATM technologies, then feeds validated solutions into the regulatory and deployment pipeline (Eurocontrol, EASA, national ANSPs, the Commission's Pilot Common Project deployment framework).

Core work strands:
- **Trajectory-based operations (TBO)**: moving from sector-based air traffic control to 4D trajectory management (time, not just space)
- **Virtual centres and remote/digital towers**: decoupling physical control-tower location from the airspace being managed, enabling remote and consolidated air traffic control
- **AI in ATM**: automation support for controllers, conflict prediction, capacity/demand balancing
- **U-space**: the drone/UAS traffic management layer (see below)
- **Higher-airspace operations (HAO)**: integrating high-altitude platforms and future air taxi/UAM traffic above conventional controlled airspace
- **Digital Sky Demonstrators**: CEF-funded large-scale operational trials of validated solutions ahead of full deployment

## U-space: the Drone Layer

U-space is the EU's regulatory and technological framework for enabling routine, safe drone (unmanned aircraft) operations, particularly in low-level airspace and urban environments, while maintaining safe interfaces with manned aviation.

### Legal Basis

| Instrument | Subject | CELEX |
|---|---|---|
| Commission Implementing Regulation (EU) 2021/664 | U-space regulatory framework: designation of U-space airspace, U-space services, USSP requirements | 32021R0664 |
| Commission Implementing Regulation (EU) 2021/665 | Amends Reg (EU) 923/2012 (SERA) on rules for manned aircraft operating in U-space airspace | 32021R0665 |
| Commission Delegated Regulation (EU) 2021/666 | Requirements for manned aircraft operations in U-space airspace (e-conspicuity/electronic identification) | 32021R0666 |

All three apply from 26 January 2023. They build on the earlier drone operations framework (Implementing Regulation (EU) 2019/947 on rules and procedures for drone operation, and Delegated Regulation (EU) 2019/945 on drone product requirements), which remains the base layer for open/specific/certified drone-operation categories.

### How U-space Works

- Member States designate specific volumes of airspace as **U-space airspace** (typically urban, high-density or otherwise sensitive areas)
- Within that airspace, drone operators must interact with a certified **U-space Service Provider (USSP)** -- a commercial or public entity delivering mandatory services (network identification, geo-awareness/geofencing data, flight authorisation, traffic information) and optional services (weather, conformance monitoring, conflict/collision advisory)
- A **Common Information Service (CIS)**, designated by the Member State, distributes shared static and dynamic data (airspace restrictions, other traffic, weather) to all USSPs operating in the same volume, ensuring a level playing field and interoperability between competing USSPs
- Manned aircraft operating within U-space airspace must carry electronic conspicuity equipment (Reg 2021/666) so USSPs can track and deconflict against drone traffic

### Maturity Levels (SESAR U-space Blueprint, indicative -- not binding law)

| Level | Focus | Illustrative services |
|---|---|---|
| U1 Foundation | Registration and basic visibility | e-registration, e-identification, geofencing |
| U2 Initial | Structured operations | Flight planning and approval, tracking, procedural interfacing with ATC |
| U3 Advanced | Dense/complex operations | Capacity management, automated conflict detection and collision avoidance |
| U4 Full | Integrated automation | Full automation and connectivity, seamless manned/unmanned integration |

### Who Needs This

- Drone operators (commercial delivery, inspection, urban air mobility) operating in or near designated U-space airspace
- Prospective USSPs seeking national authorisation/certification
- ANSPs and airports managing the manned/unmanned interface
- Urban air mobility (UAM) and air-taxi developers whose certification and operational pathway depends on U-space maturity and higher-airspace-operations research from SESAR 3 JU

## Governance and Funding Structure

SESAR 3 JU sits alongside eight other Horizon Europe institutionalised partnerships created by the Single Basic Act (Regulation (EU) 2021/2085), including Clean Aviation JU, Clean Hydrogen JU, Innovative Health Initiative JU and others. Each has its own Governing Board, Work Programme and membership base but shares the common legal architecture (governance rules, financial rules, IP rules) set by the Single Basic Act.

- **Governing Board**: European Commission, Eurocontrol, and Members' representatives; adopts the Multiannual and Bi-Annual Work Programmes and endorses the ATM Master Plan
- **Members**: Founding Members (industry associations and major stakeholders present at establishment) plus Associated Members admitted through periodic Calls for Expression of Interest -- more than 50 organisations across ANSPs, airlines, airports, manufacturers, research bodies and drone-sector entities
- **Funding split** (2021-2031, over EUR 1.6 billion total): EUR 600 million Horizon Europe; up to EUR 500 million Eurocontrol; at least EUR 500 million industry members; at least EUR 200 million CEF for Digital Sky Demonstrators

## Relationship to the Single European Sky Policy File

SESAR 3 JU is the research and innovation delivery arm of the Single European Sky (SES) policy, which is legislated separately:

- **SES2+** (procedure 2013/0186(COD)) is the long-running legislative reform to reduce airspace fragmentation across 27 national systems -- still in trilogue (see `aviation_transport_policy.md`)
- **SES Performance and Charging Scheme** (Regulation (EU) 2019/317) sets binding cost-efficiency, capacity, safety and environment targets for ANSPs each Reference Period, monitored by the Performance Review Body at Eurocontrol
- SESAR 3 JU technologies validated through research feed into the **Pilot Common Project** deployment framework and, over time, into SES performance-scheme targets and mandated equipage rules
- Eurocontrol plays a dual role: intergovernmental coordinator of day-to-day airspace operations AND a founding co-funder/member of SESAR 3 JU

## Strategic Deployment Objectives (ATM Master Plan 2025 Edition)

The 2025 edition (published 12 December 2024) organises priorities around 10 Strategic Deployment Objectives to be implemented by 2035, delivered through five technological levers:

1. Trajectory-based operations (4D trajectory management)
2. Greater data volumes via improved air-ground and ground-ground communication
3. Higher levels of automation between flight deck and ground systems
4. Human-machine teaming (AI-assisted controller support)
5. Dynamic, flexible airspace design

Target: the most efficient and environmentally friendly airspace in the world by 2045, with up to 400 million tonnes of cumulative CO2 savings by 2050.

## Who This Matters To

- **ANSPs and airports** planning ATM system upgrades, remote-tower investment, or SES performance-scheme compliance
- **Airlines and airspace users** tracking trajectory-based operations and expected fuel/route efficiency gains
- **Drone operators and USSP candidates** needing to understand U-space authorisation requirements before entering EU airspace
- **Urban air mobility / air-taxi developers** whose market entry depends on higher-airspace-operations research and U-space maturity
- **Equipment manufacturers** (avionics, ground systems, electronic conspicuity) tracking SESAR 3 JU calls and CEF Digital Sky Demonstrator funding
- **Research organisations** eligible to participate in SESAR 3 JU calls under Horizon Europe rules

## Related Brubru Guides

- **aviation_transport_policy** -- Single European Sky legislative file (SES2+), EU261, ETS for aviation, broader aviation policy
- **eu_space_programme** -- Galileo/EGNOS positioning underpinning U-space and drone navigation
- **road_safety_autonomous_vehicles** -- adjacent EU framework for autonomous/connected mobility
- **eu_horizon_partnerships_joint_undertakings** -- other Horizon Europe institutionalised partnerships under the Single Basic Act (Regulation (EU) 2021/2085), including Clean Aviation JU
- **mobile_satellite_services_eu** -- satellite connectivity relevant to higher-airspace operations and drone command-and-control links
- **eu_commission_funding_programmes_map** -- how Horizon Europe and CEF funding streams combine to co-finance SESAR 3 JU
