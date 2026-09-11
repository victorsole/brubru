"""Build the Public Procurement Act deep-dive page.

Generated rather than hand-typed. The act has 149 articles in 7 Parts, 15 Titles
and 23 Chapters; typing that by hand is how article numbers drift from the
source. The structure and every gloss below were read out of the proposal's own
enacting terms, and the article count was verified against the text: exactly 149
"Article N" headings, each appearing once.

Sources, all six read 11 September 2026:
  IP/26/1817 press release, COM(2026) 590 final (200 pp), the Annex (74 pp),
  SWD(2026) 590 subsidiarity grid, SWD(2026) 591 impact assessment (432 pp),
  SWD(2026) 592 executive summary.

  python3.12 scripts/build_ppa_deepdive.py
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])
ROOT = pathlib.Path(_REPO_ROOT)
OUT = ROOT / "frontend/public/public-procurement-act/index.html"
REF = ROOT / "frontend/public/european-innovation-act/index.html"

# (Part number, Part title, palette colour, [(chapter heading, [(art, title, gloss)])])
STRUCTURE = [
("Part I", "General provisions", "blue", [
 ("Title I &middot; Subject-matter and scope (Articles 1 to 3)", [
  (1, "Subject-matter and scope", "Sets the perimeter: contracts for works, supplies or services and concessions, procured by public buyers, at or above the Article 2 thresholds. It covers not only the award but the procurement-related aspects of planning and execution."),
  (2, "Thresholds", "EUR 5 404 000 for works and concessions; EUR 140 000 for central government supplies and services; EUR 216 000 for sub-central; EUR 432 000 in utilities; EUR 750 000 for social, health and educational services. All net of VAT."),
  (3, "Revision of thresholds", "Every two years the Commission checks the thresholds against the WTO Government Procurement Agreement and revises them where needed. The figures track an international commitment, not a domestic policy choice."),
 ]),
 ("Title II &middot; Principles, policy objectives and definitions (Articles 4 to 6)", [
  (4, "Principles of procurement", "Procurement is guided by best quality for public money. Union operators and covered operators are treated equally and without discrimination, transparently and proportionately."),
  (5, "Policy objectives", "Five strategic objectives are written into the law itself: competitiveness and the clean industrial base, environment and climate, social justice and fair working conditions, security and economic security, and innovation."),
  (6, "Definitions", "The interpretive spine of the act. It defines classified information, research and development services, innovative solution, labour-intensive and the rest of the vocabulary the operative articles rely on."),
 ]),
]),
("Part II", "Relevant actors", "purple", [
 ("Title I, Chapter 1 &middot; Identification of public buyers (Articles 7 to 10)", [
  (7, "Contracting authorities", "Central government (listed in Annex I), sub-central government, bodies governed by public law and their associations, regardless of which internal unit actually runs the procedure."),
  (8, "Contracting entities", "The utilities side: contracting authorities, public undertakings and holders of special or exclusive rights carrying out an activity in Articles 12 to 18, unless that activity is directly exposed to competition."),
  (9, "Central purchasing bodies", "A central purchasing body may act as a wholesaler, buying and reselling, or as an intermediary, publishing summaries and awarding on others' behalf."),
  (10, "Joint procurement", "Two or more public buyers, including from different Member States, may award jointly. An agreement between them must allocate responsibilities."),
 ]),
 ("Title I, Chapter 2 &middot; Activities in the field of utilities (Articles 11 to 20)", [
  (11, "Common provisions", "Defines supply for the utilities articles as covering generation or production, wholesale and retail. Gas extraction is pushed into Article 18 rather than Article 12."),
  (12, "Gas and heat", "Fixed networks serving the public for the production, transport or distribution of gas or heat, and supply to those networks."),
  (13, "Electricity", "The same structure as gas and heat, applied to electricity networks and supply to them."),
  (14, "Water", "Drinking water networks and supply, plus connected hydraulic engineering, irrigation, land drainage and sewage disposal or treatment."),
  (15, "Transport services", "Networks providing a public transport service by railway, automated systems, tramway, trolley bus, bus or cable. A network exists where a competent authority lays down operating conditions."),
  (16, "Ports and airports", "Exploiting a geographical area to provide airports, maritime or inland ports, or other terminal facilities to carriers."),
  (17, "Postal services", "Postal services, and services other than postal provided by an entity that also provides postal services, subject to the Article 19 competition test."),
  (18, "Energy sources extraction and exploration", "Exploiting a geographical area to extract oil or gas, or to explore for or extract coal or other solid fuels."),
  (19, "Activities directly exposed to competition", "The act does not apply to a utilities activity in a given geographical area where that activity is directly exposed to competition on a market to which access is not restricted, once an implementing act says so."),
  (20, "Exemption procedure", "How a Member State or contracting entity asks for that finding: an optional preliminary question first, or a formal exemption request directly."),
 ]),
 ("Title II, Chapter 1 &middot; Economic operators, general provisions (Articles 21 to 24)", [
  (21, "Economic operators", "No specific legal form may be required to take part, and an operator entitled to supply at home cannot be rejected merely because the buyer's Member State would have required a different legal personality."),
  (22, "Groups of economic operators", "A consortium must not face different selection criteria. It satisfies a criterion where one member has the capacity, or where members can combine it."),
  (23, "Reliance on the capacity of other entities", "An operator may lean on another entity's capacity whatever the legal link. The buyer must check that entity against the same criteria and exclusion grounds."),
  (24, "Subcontracting", "Parts may be subcontracted, but a contract must not be subcontracted in its entirety, nor further subcontracted in its entirety. Tenderers must state the share they intend to subcontract and name proposed subcontractors."),
 ]),
 ("Title II, Chapter 2 &middot; Exclusion grounds and selection criteria (Articles 25 to 27)", [
  (25, "Mandatory exclusions", "Exclusion at any point in the procedure for a final conviction of the listed offences, reaching not only the operator but a key person in the functioning of the legal person."),
  (26, "Optional exclusion grounds", "The discretionary list: breach of applicable Union obligations, insolvency, grave professional misconduct, distortion of competition, conflicts of interest and prior involvement, among others."),
  (27, "Selection criteria", "Selection criteria are optional, and when used may relate only to technical and professional ability or to legal, economic and financial standing. Requirements must be limited to what is appropriate."),
 ]),
 ("Title II, Chapter 3 &middot; Means of proof and database access (Articles 28 to 29)", [
  (28, "Means of proof of the eligibility of economic operators", "Proof of the absence of exclusion grounds and of compliance with selection criteria runs through the electronic eligibility service of Article 133, including for entities relied on and for subcontractors."),
  (29, "Connection of databases to the electronic eligibility service", "Member States must give the digital business credential tool free access to the relevant national registers by 15 June 2029, starting with criminal and professional registers."),
 ]),
]),
("Part III", "Procedures for public contracts", "green", [
 ("Title I, Chapter 1 &middot; Preliminary steps and general provisions (Articles 30 to 33)", [
  (30, "Market consultations", "Buyers may consult the market before procuring, and must announce the consultation. They may take information and advice from the public, independent experts, authorities or market participants."),
  (31, "Choice of procedures", "Open and dynamic procedures are available for anything. The innovation procedure is reserved for a societal challenge with no identified suitable solution. The special procedure of Article 46 is confined to the listed cases."),
  (32, "Estimation of the value of the contract", "Value is estimated on the maximum to be spent over the whole duration, including premiums, fees, commissions, interest, options and renewals."),
  (33, "Conduct of negotiations", "Negotiation becomes an ordinary feature rather than an exception. Buyers must keep genuine competition in each round and must not disclose information that harms a participant's commercial interests. Only non-essential characteristics may be negotiated."),
 ]),
 ("Title I, Chapter 2 &middot; Open procedure (Articles 34 to 35)", [
  (34, "Launch and conduct of the open procedure", "The buyer publishes a public summary of competition stating whether selection criteria apply and whether it intends to negotiate. Any interested operator may express interest and submit a first tender."),
  (35, "Finalisation of the procedure and award of the contract", "Award goes to the tender offering the best quality for money under Article 98, without prejudice to the standstill period in the existing remedies directives."),
 ]),
 ("Title I, Chapter 3 &middot; Dynamic procedure (Articles 36 to 40)", [
  (36, "Dynamic procedure", "A standing procedure that only joined operators compete within, and which operators may ask to join at any point during its validity."),
  (37, "Launch and validity of the dynamic procedure", "The launch summary fixes how long the procedure stays open. The buyer chooses up front whether to use selection criteria and whether to negotiate."),
  (38, "Conduct of the dynamic procedure without selection criteria", "The lighter variant: operators join without a qualification gate, and compete for individual contracts as they arise."),
  (39, "Conduct of the dynamic procedure with selection criteria", "Operators join by sharing their profile through the eligibility service, declaring they are qualified, and the buyer admits them on the stated criteria."),
  (40, "Finalisation of the procedure and award of the contract", "Final tenders are evaluated under Article 98 and all tenderers are ranked, with the ranking disclosed to them. Every contract signed under the procedure gets a public summary of result."),
 ]),
 ("Title I, Chapter 4 &middot; Innovation procedure (Articles 41 to 45)", [
  (41, "Design and conduct of the innovation procedure", "Five phases: define the societal challenge and the value assessment framework, launch, select proposals, test and validate, then award."),
  (42, "Launch of the innovation procedure", "A market consultation of at least two months must precede launch, publishing a preliminary description of the challenge and a preliminary value assessment framework."),
  (43, "Selection of innovative solution proposals", "Eligibility is assessed in two phases, first exclusion and any selection criteria plus minimum functional requirements, then the substantive comparison."),
  (44, "Testing, validation and assessment of innovative solution proposals", "A structured phase of at most two years unless justified, which may include laboratory testing, field trials and pilots against the value assessment framework."),
  (45, "Award of the public contract for deployment of the innovative solution proposal", "Those with a positive decision are invited to negotiate. The buyer must set out a clear exit strategy for ending the procedure without an award."),
 ]),
 ("Title I, Chapter 5 &middot; Special procedures and tools (Articles 46 to 49)", [
  (46, "Contracts requiring only publication of public summary of result", "The direct-award route: a solution requested from one or more operators with no competition and no prior publication, but with a public summary of result afterwards."),
  (47, "Conditions for the use of contracts with publication of a public summary of result only", "The exhaustive grounds, including a unique work of art, absence of competition for technical reasons, and exclusive rights."),
  (48, "Emergency and crisis", "The same route where extreme urgency not attributable to the buyer makes the ordinary time limits impossible, and where a Union emergency framework has been activated."),
  (49, "Qualification list for contracting entities", "Utilities may run a standing qualification list and award individual contracts from it, keeping it open to admission requests throughout its stated duration."),
 ]),
 ("Title II, Chapter 1 &middot; Green public procurement (Articles 50 to 54)", [
  (50, "Green public procurement", "Buyers may take environmental and climate considerations into account across the life-cycle, to prevent, reduce or mitigate harm or to pursue positive effects, compared with alternatives serving the same function."),
  (51, "Circular economy and resource efficiency", "Durability, reparability, upgradeability, reuse, refurbishment, remanufacturing, recycled content, secondary raw materials and waste prevention may all be written into specifications, selection, award or performance conditions."),
  (52, "Energy efficiency", "An obligation, not an option: buyers shall purchase only products, services and works with high energy efficiency performance unless that is not technically feasible. This is where the Energy Efficiency Directive's Article 7 lands."),
  (53, "Food procurement", "Food quality and sustainability may be taken into account, including fairness and transparency in supply chains, seasonality and the length of the chain."),
  (54, "Requirements for green public procurement for certain products", "For products covered by the Union acts listed in Annex VII, environmental characteristics must be required. This is the article into which the ecodesign, batteries, construction products and packaging procurement provisions are folded."),
 ]),
 ("Title II, Chapter 2 &middot; Socially responsible public procurement (Articles 55 to 58)", [
  (55, "Socially responsible public procurement", "Social considerations across the life-cycle, pursuing social inclusion, labour market integration, fair working conditions and the Union's social objectives."),
  (56, "Accessibility", "Where goods, services or works are intended for use by people, accessibility for persons with disabilities must be required except in duly justified cases, taking design for all into account."),
  (57, "Reserved contracts", "Participation may be reserved to organisations integrating persons with disabilities or disadvantaged persons, where at least 30% of their employees are such workers, and to non-profit welfare organisations for the services in Annex VI."),
  (58, "Contracts for social, health and educational services", "For the Annex VI services, buyers may follow national procedures, provided transparency and equal treatment and the obligations in paragraph 2 are respected."),
 ]),
 ("Title II, Chapter 3 &middot; Public procurement of innovation (Articles 59 to 65)", [
  (59, "Innovation objectives in public procurement", "Deploying Union research results, bringing in start-ups, scale-ups and SMEs, and growing innovative firms are recognised objectives a buyer may pursue."),
  (60, "Public procurement of innovation", "A buyer must classify a procurement as innovation procurement in the competition summary where the object is an innovative solution, meaning new characteristics giving better performance than what is commercially available at scale."),
  (61, "Techniques to pursue innovation objectives in public procurement", "The toolkit: market consultation advice, open-source solutions, functional requirements only, explicit variants, and limits on the scope of what is specified."),
  (62, "Specification of intellectual property rights", "The buyer must state in the procurement detail which intellectual property rights it considers relevant, clearly enough for operators to price their obligations."),
  (63, "Granting licences", "The operator grants appropriate, sufficient and non-exclusive licences covering both pre-existing rights and rights created in performance, for as long as the buyer needs them."),
  (64, "Limits to transfer of ownership", "Pre-existing intellectual property stays with the operator and is not subject to ownership transfer, save where transfer is necessary for performance, operation and maintenance."),
  (65, "Building information modelling", "For works contracts of EUR 25 000 000 or more, building information modelling is mandatory in execution, with derogations where it would impose a disproportionate burden."),
 ]),
 ("Title II, Chapter 4 &middot; Security and resilience (Articles 66 to 69)", [
  (66, "Security considerations in public procurement", "Where a procedure presents a security or public safety risk, the buyer must take appropriate measures at every stage from planning to execution."),
  (67, "Security measures during contract implementation", "A contract may be terminated in whole or in part where the contractor fails to comply with security measures, or where a risk materialises or is likely to."),
  (68, "Cybersecurity", "For products with digital elements within the Cyber Resilience Act, compliance with its essential cybersecurity requirements, including vulnerability handling, must be taken into account in the procurement process."),
  (69, "Resilience and security of supply for critical entities or infrastructures", "Where the buyer is a critical entity, resilience and security-of-supply requirements may be imposed, with delegated acts available to specify them."),
 ]),
 ("Title II, Chapter 5 &middot; European preference (Articles 70 to 77)", [
  (70, "Covered economic operators, goods, services or works", "Defines who is covered: operators originating in a GPA party within the scope of the Union's commitments, or in a country with a bilateral or multilateral agreement, on that agreement's terms."),
  (71, "Determining the scope of coverage for third-country covered economic operators, goods, services or works", "The Commission must build and give away a free public online tool setting out the Union's procurement commitments, and buyers determine coverage on that basis."),
  (72, "Restrictions on covered economic operators, goods, services or works", "The switch. The Commission may adopt delegated acts removing covered status from a third country's operators, goods, services or works, on a factual market access analysis, to avoid dependencies threatening security of supply, or under an applicable agreement's exceptions."),
  (73, "European preference requirements", "What a buyer may then do: restrict participation to Union and covered operators, or reject a tender from others. Alternatively require Union origin fully, partly or for specific components; apply a price reduction or extra award points for evaluation and ranking only, without changing the price paid; or reject a tender whose Union or covered content is below 50% of its total estimated value."),
  (74, "Origin", "Operator origin follows the International Procurement Instrument, goods follow the Union Customs Code, services follow the operator providing them, and works follow the operator or subcontractor providing them."),
  (75, "Union restrictions for third-country non-covered economic operators, goods, services and works", "The Commission may by delegated act oblige buyers to apply the Article 73 requirements to non-covered operators where that is in the Union's interest. The preference stops being optional."),
  (76, "Exceptions", "Buyers may decline to apply preference requirements, including those imposed by delegated act, in the listed situations."),
  (77, "European preference in sectoral Union legislation", "Where other Union law sets origin-based conditions in procurement, this chapter governs unless that legislation says otherwise."),
 ]),
 ("Title III, Chapter 1 &middot; Excluded and mixed contracts (Articles 78 to 87)", [
  (78, "Defence and security contracts", "Contracts within the defence procurement directive are out, including below its thresholds, as are contracts where essential security interests cannot be protected by less intrusive means."),
  (79, "R&amp;D procurement excluded", "Contracts exclusively for research and development services fall outside the act. Mixed contracts do not, notably where testing and validation forms part of the innovation procedure."),
  (80, "Contracts awarded to controlled entities", "The in-house exemption, requiring control similar to that over the buyer's own departments and decisive influence over strategy and significant decisions."),
  (81, "Public-public cooperation", "Cooperation between contracting authorities is outside the act where it genuinely implements a joint public service objective."),
  (82, "Local and regional administrative cooperation", "Regional or local authorities may entrust each other with their own tasks, or use each other's own resources, including for remuneration, provided they perform by their own resources."),
  (83, "Contracts awarded to affiliated undertakings", "The utilities affiliate exemption, conditioned on at least 80% of the affiliate's average turnover coming from the group."),
  (84, "Contracts awarded in a joint venture", "Awards within a joint venture of contracting entities, where the venture was set up for at least three years and the members are committed for a comparable period."),
  (85, "Other excluded public contracts", "The residual list, including exclusive-right service contracts between public buyers and contracts for providing electronic communications networks."),
  (86, "Mixed procurement involving defence or security aspects", "How to split or combine a contract that straddles this act and either Article 346 of the Treaty or the defence directive."),
  (87, "Other mixed contracts", "A contract covering more than one type of procurement follows the rules for whichever type characterises its main subject."),
 ]),
 ("Title III, Chapter 2 &middot; Subject-matter and means of proof (Articles 88 to 92)", [
  (88, "Specifications", "Specifications must be objective, clear and measurable, letting operators identify the subject-matter and letting the buyer assess alignment."),
  (89, "Variants", "Unless specifications are purely functional, the buyer must consider allowing variants, and must state in the procurement detail whether it does and, if not, the main reasons."),
  (90, "Link to the subject-matter", "Every criterion, requirement and performance condition must be linked to the subject-matter, directly or through any stage of the life-cycle."),
  (91, "Labels", "A specific label may be required as proof, provided its requirements concern criteria linked to the subject-matter and the listed conditions are met."),
  (92, "Means of proof for product requirements", "Conformity may be proved through the digital product passport under the ecodesign regulation, or by equivalent electronic means where no passport yet exists."),
 ]),
 ("Title III, Chapter 3 &middot; Conduct of the procedure (Articles 93 to 103)", [
  (93, "Confidentiality", "Information designated confidential by an operator, including technical and trade secrets, must not be disclosed unless this act or other law requires it."),
  (94, "Conflicts of interest", "Buyers must prevent, identify and remedy conflicts of interest across design, preparation, staffing, the procurement detail, selection and award."),
  (95, "Prior involvement in the preparation of the procurement procedure", "Where an operator helped prepare, the buyer must ensure competition is not distorted. Taking part in a market consultation does not count as preparation."),
  (96, "Setting time limits", "Time limits must reflect the nature and complexity of the contract, on-site inspections and the time genuinely needed to tender, and must be extended proportionately after significant changes."),
  (97, "Availability of procurement detail", "Unrestricted, full, direct and free electronic access to the procurement detail from publication until three years after award."),
  (98, "Award criteria", "The heart of the reform. Award goes to the best quality for money, evaluated by best price-quality ratio, with quality criteria weighing at least 30% of total points and at least 50% where the subject-matter is labour-intensive. Life-cycle costs and specified environmental criteria count inside that percentage, not on top."),
  (99, "Life-cycle costing", "Where used, it covers purchase, use, energy and resource consumption, maintenance and end-of-life costs, and may cover environmental and climate externalities."),
  (100, "Division into lots", "Buyers must consider dividing into lots, weighing SME participation, dependency on a single supplier, supply chain resilience and innovation against efficiency and integrity risks."),
  (101, "Abnormally low tenders", "Explanations must be required where a price looks abnormally low against the other tenders, the market price including labour costs, or past contract values for the same subject-matter."),
  (102, "Corrections during procedures and cancellation", "A buyer may correct the procurement detail without restarting, provided the correction does not substantially alter the subject-matter and is clearly flagged to everyone concerned."),
  (103, "Framework agreements", "Capped at three years with a single operator and five years with several, longer only where duly justified by complexity or specialised nature. The competition summary must state duration and the maximum cumulative value or volume."),
 ]),
 ("Title III, Chapter 4 &middot; Contract execution (Articles 104 to 108)", [
  (104, "Conditions for the performance of contracts", "Performance conditions may carry the strategic considerations, environmental, social, innovation, security, alongside ordinary contractual, technical, quality and economic terms such as price indexation."),
  (105, "Adjustment mechanisms", "Clauses adjusting contract conditions over time are allowed where objectively justified, where they maintain the economic balance, and where they are clear, precise and unequivocal."),
  (106, "Modifications of contracts during their term", "Modification without a new procedure is possible where it is not substantial or falls in the listed cases, must answer an objective need, and must not alter the initial economic balance."),
  (107, "Termination of contracts", "Termination is mandatory on a final conviction under Article 25, or where the contract should not have been awarded, subject to an overriding public interest carve-out."),
  (108, "Payments", "Timely payment of contractors and subcontractors, and buyers may require equivalent payment terms to be passed down the supply chain."),
 ]),
 ("Title III, Chapter 5 &middot; Publication and documentation rules (Articles 109 to 113)", [
  (109, "Individual documentation of procedures", "Every stage must be documented in the buyer's eProcurement service and made available in the national data space, including negotiations and internal decisions."),
  (110, "Publication information in public summaries", "Six public summaries carry the procedure's life: consultation, competition, result, contract, modification and completion."),
  (111, "Publication of public summary of result, of contract and of completion", "Summaries must be sent no later than 20 days after the triggering event, whether the close of a consultation, an award decision, a cancellation or the conclusion of a contract."),
  (112, "Form and manner of publication", "Summaries travel through the national data space to the Publications Office and appear in the Supplement to the Official Journal within five days of validated receipt."),
  (113, "Publication at national level", "National publication must not precede Union publication, unless the buyer has heard nothing within 48 hours of confirmed receipt."),
 ]),
]),
("Part IV", "Concessions", "amber", [
 ("Title I &middot; General provisions (Articles 114 to 118)", [
  (114, "Scope", "Concessions for works and services. Everything else in the Regulation applies to them unless this Part says otherwise."),
  (115, "Definition and characteristics of concessions", "A concession entrusts execution or management for the benefit of users, remunerated by the right to exploit, and transfers an operating risk to the concessionaire."),
  (116, "Mixed concession contracts", "How to treat a contract mixing concession and non-concession elements, depending on whether the parts are objectively separable."),
  (117, "Excluded concessions", "Air transport under an operating licence, public passenger transport under Regulation 1370/2007 and the other listed categories fall outside."),
  (118, "Threshold and estimation of the value of a concession", "The works threshold applies, EUR 5 404 000, and value means the projected total turnover net of VAT over the maximum duration."),
 ]),
 ("Title II &middot; Preparation, design and procedure (Articles 119 to 123)", [
  (119, "Contractual obligations relating to public needs", "The buyer must fix mandatory performance conditions covering continuity, quality, accessibility, safety and effectiveness for users."),
  (120, "Structured risk assessment", "Before launching, the buyer must assess the main economic risks, separating operating risk from the rest. This is new and it is the discipline that makes the risk transfer real."),
  (121, "Parameters for assessing performance", "Concession contracts must include provisions securing long-term efficiency, including environmental sustainability and technological innovation over the whole duration."),
  (122, "Duration of concessions", "Duration is limited to what is needed to recoup the investment with a normal return, judged against investment, operating and maintenance costs and the allocation of risk."),
  (123, "Procedures for the award of a concession", "Concessions are awarded through this Regulation's procedures, with the competition summary additionally disclosing the estimated value components and the allocation of demand, construction and regulatory risk."),
 ]),
 ("Title III &middot; Management of concessions (Articles 124 to 126)", [
  (124, "Adjustment mechanisms", "As for contracts, with one addition: the mechanism must preserve the transfer of operating risk to the concessionaire, or it is no longer a concession."),
  (125, "Modifications of concessions during their term", "Modification without a new procedure where not substantial or within the listed cases, without altering the initial economic balance in the concessionaire's favour."),
  (126, "Termination of concessions", "Early termination for overriding reasons of public interest, which must be proportionate, reasoned, and used only where no less restrictive measure would do."),
 ]),
]),
("Part V", "Digital ecosystem", "blue", [
 ("Title I, Chapter 1 &middot; Electronic communication and interoperability (Articles 127 to 130)", [
  (127, "Electronic communication", "All exchanges with operators go through electronic tools that are generally available, non-discriminatory and conformant with the harmonised standard for procurement detail."),
  (128, "Interoperability network", "The Commission establishes or designates a secure data exchange network so buyers and operators on different eProcurement platforms can still talk to each other."),
  (129, "Harmonised standards for public procurement", "A standardisation request may be issued for the semantic data model and interoperability of procurement procedures and of the procurement detail."),
  (130, "Common specifications", "Where standardisation does not deliver, the Commission may adopt implementing acts laying down common specifications instead."),
 ]),
 ("Title I, Chapter 2 &middot; eProcurement service providers (Articles 131 to 132)", [
  (131, "Obligations of eProcurement service providers", "Platforms must comply with the harmonised standards or the common specifications, and must enable the use of European Business Wallets."),
  (132, "Commission eProcurement platform", "The Commission builds and runs its own platform, available to buyers and operators, meeting the same requirements it sets for everyone else."),
 ]),
 ("Title I, Chapter 3 &middot; Electronic eligibility (Article 133)", [
  (133, "Electronic eligibility service", "A Commission-run service verifying exclusion grounds, selection criteria and origin for each procedure, through European Business Wallets or interoperable alternatives. This is the single piece of plumbing most of the savings depend on."),
 ]),
]),
("Part VI", "Transparency and governance", "purple", [
 ("Title I &middot; Data spaces (Articles 134 to 136)", [
  (134, "National Public Procurement Data Spaces", "Every Member State establishes a national data space as the central access point. It must be established in the EEA, owned and controlled by EEA persons with no third-country decisive influence, and the data must be stored in the EEA."),
  (135, "Public Procurement Data Space", "The Union-level repository built on the eProcurement ontology and the FAIR principles, fed from the national spaces within ten days of information becoming available."),
  (136, "PPDS data exchange", "The Commission runs the access management and secure exchange between the Union and national data spaces."),
 ]),
 ("Title II &middot; Governance (Articles 137 to 140)", [
  (137, "Monitoring of the performance of public procurement markets", "Member States must monitor their own systems on their data space, assessing barriers to competition and access for SMEs and identifying integrity vulnerabilities."),
  (138, "National coordinating authority", "One designated authority per Member State, coordinating national authorities, easing information exchange and making standardised contract documents and guidance available."),
  (139, "Professionalisation and capacity building", "Member States must treat professionalisation as long-term public governance and adopt, implement and periodically update a national professionalisation strategy. Given what the evidence base says about administrative capacity, this is more load-bearing than its position suggests."),
  (140, "Integrity governance", "Buyers must take proportionate and effective measures against fraud, favouritism, collusion and corruption, and against conflicts of interest in procedure and execution."),
 ]),
]),
("Part VII", "Final provisions", "red", [
 ("Title I &middot; Delegation and cross-cutting provisions (Articles 141 to 145)", [
  (141, "Exercise of delegation", "Delegation is conferred for an indeterminate period across thirteen provisions, including Article 72(1) and Article 75, the two that carry European preference."),
  (142, "Urgency procedure", "Urgent delegated acts enter into force immediately and apply until the Parliament or Council objects, in which case the Commission repeals without delay."),
  (143, "Committee procedure", "The Advisory Committee on Public Contracts, established by Council Decision 71/306/EEC, assists the Commission."),
  (144, "Outermost regions", "Member States may adapt specific aspects of Part III for the outermost regions, notifying the Commission and the other Member States, without touching equal treatment, non-discrimination or transparency."),
  (145, "Procurement with Union support", "Contracts backed by a Union programme carry the additional conditions needed to satisfy the Financial Regulation."),
 ]),
 ("Title II &middot; Amendments, repeals, transitional provisions, entry into force (Articles 146 to 149)", [
  (146, "Repeal", "Directives 2014/23/EU, 2014/24/EU and 2014/25/EU are repealed, and references to them are read against the correlation table in Annex VIII, Part A."),
  (147, "Amendments to horizontal public procurement provisions", "Fourteen numbered points, each deleting a procurement provision from another act and redirecting its references here. This is the consolidation, and it is where the act reaches into ecodesign, net-zero industry, batteries, construction products, packaging, energy efficiency, waste, critical raw materials, accessibility, gender balance, cyber resilience, due diligence, waste shipments and public passenger transport."),
  (148, "Review", "The Commission evaluates the Regulation every seven years and reports to the Parliament, the Council, the Economic and Social Committee and the Committee of the Regions."),
  (149, "Entry into force and application", "In force on the twentieth day after publication, applicable two years after that. Binding in its entirety and directly applicable, with no transposition step."),
 ]),
]),
]

# The fourteen acts amended, in the order Article 147 lists them.
AMENDED = [
 ("Regulation (EU) 2024/1781", "Ecodesign for Sustainable Products", "Article 65 and part of Article 74(3) deleted, redirected to Articles 54 and 26"),
 ("Regulation (EU) 2024/1735", "Net-Zero Industry Act", "Article 25(4) and (5) deleted, redirected to Article 54"),
 ("Regulation (EU) 2023/1542", "Batteries and waste batteries", "Article 85 deleted, redirected to Article 54"),
 ("Regulation (EU) 2024/3110", "Construction products", "Article 83 deleted, redirected to Article 54"),
 ("Regulation (EU) 2025/40", "Packaging and packaging waste", "Article 63 deleted, redirected to Article 54"),
 ("Directive (EU) 2023/1791", "Energy Efficiency Directive", "Article 7 and Annex IV deleted, redirected to Article 52"),
 ("Directive 2008/98/EC", "Waste Framework Directive", "the words procurement criteria deleted from Article 11(1)"),
 ("Regulation (EU) 2024/1252", "Critical Raw Materials Act", "Article 26(1)(d) replaced, redirected to Article 51"),
 ("Directive (EU) 2019/882", "European Accessibility Act", "Article 24(1) deleted, redirected to Article 56"),
 ("Directive (EU) 2022/2381", "Gender balance on corporate boards", "Article 8(3) deleted, redirected to Article 4(4)"),
 ("Regulation (EU) 2024/2847", "Cyber Resilience Act", "Article 5 deleted, redirected to Article 68"),
 ("Directive (EU) 2024/1760", "Corporate Sustainability Due Diligence", "Article 31 deleted, redirected to Article 55"),
 ("Regulation (EU) 2024/1157", "Shipments of waste", "Article 63(3)(c) deleted, redirected to Article 26"),
 ("Regulation (EC) No 1370/2007", "Public passenger transport by rail and road", "a subparagraph added to Article 5(1), applying security, resilience and European preference"),
]

MONEY = [
 ("New burden: simplification and negotiation (FLX.2)", "78", "&mdash;", "78"),
 ("New burden: the quality rule, comply or explain (ESI.2)", "55", "<strong>457</strong>", "512"),
 ("New burden: voluntary EU Ecolabel", "&mdash;", "12", "12"),
 ("New burden: European preference (BEU.2)", "7.4", "7.4", "15"),
 ("Removed burden: simplification (FLX.2)", "&minus;166", "&mdash;", "&minus;166"),
 ("Removed burden: the digital marketplace (MPL.1)", "<strong>&minus;220</strong>", "<strong>&minus;881</strong>", "<strong>&minus;1 101</strong>"),
]

EXTRA_CSS = """

  /* ---- table of contents -------------------------------------------------
     Replaces the inherited two-column `columns` flow, which could not cope with
     the sub-list under entry 8. A grid places the ten entries in two columns and
     lets entry 8 span the full width, so the Parts sit in their own block. */
  .toc ol.toc__main { columns:initial; column-gap:normal; margin:0; padding:0;
    list-style:none; counter-reset:toc; display:grid; gap:.15rem 1.5rem;
    grid-template-columns:repeat(2,minmax(0,1fr)); }
  .toc ol.toc__main > li { counter-increment:toc; margin:0; }
  .toc ol.toc__main > li > a { display:flex; align-items:baseline; gap:.6rem;
    padding:.5rem .65rem; border-radius:9px; border-bottom:none;
    transition:background .14s ease, color .14s ease; }
  .toc ol.toc__main > li > a::before { content:counter(toc);
    font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:.72rem;
    font-weight:700; color:var(--sec); background:var(--bg);
    border:1px solid var(--border); border-radius:6px; min-width:1.45rem;
    padding:.1rem 0; text-align:center; flex:0 0 auto; }
  .toc ol.toc__main > li > a:hover { background:var(--bg); color:var(--purple);
    border-bottom:none; }
  .toc ol.toc__main > li > a:hover::before { border-color:var(--purple);
    color:var(--purple); }
  .toc__wide { grid-column:1 / -1; }

  /* The seven Parts, indented under entry 8 with the article range set quiet
     and right-aligned so the eye can scan titles and ranges separately. */
  .toc ol.toc__parts { columns:initial; column-gap:normal; list-style:none;
    display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:.1rem 1.5rem;
    margin:.3rem 0 .5rem 2.05rem; padding-left:.9rem;
    border-left:2px solid var(--border); }
  .toc ol.toc__parts > li { margin:0; }
  .toc ol.toc__parts a { display:flex; align-items:baseline; gap:.5rem;
    padding:.32rem .5rem; border-radius:7px; font-size:.92rem; border-bottom:none;
    transition:background .14s ease, color .14s ease; }
  .toc ol.toc__parts a:hover { background:var(--bg); color:var(--purple);
    border-bottom:none; }
  .toc__pn { font-weight:700; white-space:nowrap; flex:0 0 auto; }
  .toc__pt { flex:1 1 auto; min-width:0; }
  .toc__pr { color:var(--muted); font-size:.78rem; white-space:nowrap;
    flex:0 0 auto; font-variant-numeric:tabular-nums; }

  @media (max-width:900px) {
    .toc ol.toc__parts { grid-template-columns:1fr; }
  }
  @media (max-width:767px) {
    .toc ol.toc__main { grid-template-columns:1fr; }
    .toc ol.toc__parts { margin-left:1.2rem; padding-left:.7rem; }
    .toc__pr { font-size:.74rem; }
  }
  /* The header is sticky and 81px tall, so an anchor jump used to land the Part
     heading at top 0, underneath it. scroll-padding-top offsets every in-page
     jump at once, including the table of contents links. */
  html { scroll-padding-top: 96px; }
  /* Tables. The reference deep-dive has none, so these are additive and keep
     the same tokens. Every table sits in .table-wrap so a wide row scrolls
     inside its own box and never widens the page. */
  .table-wrap { overflow-x:auto; -webkit-overflow-scrolling:touch; margin:1.4rem 0;
    border:1px solid var(--border); border-radius:var(--r); }
  table.tbl { border-collapse:collapse; width:100%; min-width:540px; font-size:.92rem; }
  table.tbl th, table.tbl td { padding:.62rem .8rem; text-align:left;
    border-bottom:1px solid var(--border); vertical-align:top; }
  table.tbl thead th { background:var(--alt); font-size:.78rem; text-transform:uppercase;
    letter-spacing:.04em; color:var(--sec); white-space:nowrap; }
  table.tbl td.num, table.tbl th.num { text-align:right; white-space:nowrap;
    font-variant-numeric:tabular-nums; }
  table.tbl tr:last-child td { border-bottom:none; }
  table.tbl tr.total td { background:var(--alt); font-weight:700; }
  table.tbl code { font-size:.86em; }
  /* Part heading. The chapter labels use the reference's .chap, which is
     uppercased, so the Part needs its own larger, sentence-case heading. */
  .part { font-size:1.3rem; font-weight:700; color:var(--text);
    margin:3.2rem 0 .2rem; padding-top:1.4rem; border-top:2px solid var(--border); }
  section .part:first-of-type { border-top:none; padding-top:0; margin-top:2rem; }
"""


# Keys whose wording is identical across every deep-dive. They are lifted from the
# reference page rather than retyped, so the footer and the call to action read in
# Catalan exactly as the rest of Brubru reads in Catalan.
SHARED_FROM_REF = (
    "ft_trademark", "ft_links", "ft_about", "ft_contact", "ft_privacy",
    "ft_terms", "ft_cookies", "ft_subproc", "cta_h", "cta_b", "cta_btn",
    "header_cta",
)
LANGS = ("es", "ca", "fr", "it", "nl")

# (part id, first article, last article), derived from STRUCTURE so it cannot
# drift from the page.
PART_RANGES = [
    (pno.lower().replace(" ", "-"),
     min(n for _, items in groups for n, _, _ in items),
     max(n for _, items in groups for n, _, _ in items),
     pno.split()[1])
    for pno, _, _, groups in STRUCTURE
]


def _ref_lang_object(ref: str, lang: str) -> dict:
    """Pull one language object out of the reference page's translations literal."""
    i = ref.find(f'"{lang}": {{')
    if i < 0:
        raise SystemExit(f"[ERROR] reference page has no {lang} object")
    j = ref.index("{", i)
    depth = 0
    for k in range(j, len(ref)):
        if ref[k] == "{":
            depth += 1
        elif ref[k] == "}":
            depth -= 1
            if depth == 0:
                break
    return json.loads(ref[j:k + 1])


def build_translations(ref: str) -> dict:
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    out = {}
    for lang in LANGS:
        mod = __import__(f"ppa_i18n.{lang}", fromlist=["T"])
        d = dict(mod.T)
        shared = _ref_lang_object(ref, lang)
        for k in SHARED_FROM_REF:
            if k not in shared:
                raise SystemExit(f"[ERROR] {lang}: reference lacks shared key {k}")
            d[k] = shared[k]
        # "Article N" is mechanical; generating it keeps 149 keys per language
        # out of the hand-written files, where a typo would be invisible.
        for n in range(1, 150):
            d[f"a{n}_l"] = f"{mod.ARTICLE_WORD} {n}"
        # The contents shows an article range per Part. It used to be hardcoded
        # English with no key at all, so it stayed English in all five languages.
        for pid, first, last, roman in PART_RANGES:
            d[f"r_{pid}"] = mod.RANGE_TMPL.format(a=first, b=last)
            d[f"pn_{pid}"] = f"{mod.PART_WORD} {roman}"
        out[lang] = d
    return out


def audit_translations(html: str, translations: dict) -> None:
    """Every data-i18n key in the page must exist in every language, plus the four
    head keys that are not DOM nodes. A missing key is a silent English fallback,
    which is exactly the defect the per-language snapshot is meant to prevent."""
    keys = set(re.findall(r'data-i18n="([^"]+)"', html[html.index("<body"):]))
    keys |= {"page_title", "page_desc", "og_title", "og_desc"}
    bad = False
    for lang, d in translations.items():
        missing = sorted(keys - set(d))
        extra = sorted(set(d) - keys)
        if missing:
            bad = True
            print(f"[ERROR] {lang}: {len(missing)} missing key(s): {missing[:8]}")
        if extra:
            print(f"[WARN]  {lang}: {len(extra)} unused key(s): {extra[:8]}")
    if bad:
        raise SystemExit("[ERROR] translations incomplete")
    print(f"[OK] translations complete: {len(keys)} keys x {len(translations)} languages")



def main() -> int:
    ref = REF.read_text(encoding="utf-8")
    style = re.search(r"<style>(.*?)</style>", ref, re.S).group(1)
    footer = ref[ref.index("<footer"):ref.index("</footer>") + len("</footer>")]

    total_arts = sum(len(items) for _, _, _, gs in STRUCTURE for _, items in gs)
    if total_arts != 149:
        raise SystemExit(f"[ERROR] {total_arts} articles, expected 149")

    # ---- the article-by-article section, and the table of contents ----
    parts, toc_parts = [], []
    for pno, ptitle, colour, groups in STRUCTURE:
        first = min(n for _, items in groups for n, _, _ in items)
        last = max(n for _, items in groups for n, _, _ in items)
        count = sum(len(items) for _, items in groups)
        pid = pno.lower().replace(" ", "-")
        toc_parts.append(
            f'<li><a href="#{pid}">'
            f'<span class="toc__pn" data-i18n="pn_{pid}">{pno}</span>'
            f'<span class="toc__pt" data-i18n="toc_{pid}">{ptitle}</span>'
            f'<span class="toc__pr" data-i18n="r_{pid}">'
            f'Articles {first} to {last}</span></a></li>')
        buf = [f'<h3 class="part" id="{pid}" data-i18n="ph_{pid}">{pno} &middot; '
               f'{ptitle}, {count} articles</h3>']
        for gi, (gtitle, items) in enumerate(groups, 1):
            # .chap is the chapter LABEL and it is uppercased by the stylesheet.
            # It must stay a sibling of the list: as a wrapper it uppercases every
            # gloss inside, because text-transform inherits.
            buf.append(f'<div class="chap" data-i18n="g{pid}_{gi}">{gtitle}</div>')
            buf.append('<ul class="arts">')
            for n, title, gloss in items:
                buf.append(
                    f'<li class="art"><div class="art__n" data-i18n="a{n}_l">Article {n}</div>'
                    f'<div class="art__t" data-i18n="a{n}_t">{title}</div>'
                    f'<p data-i18n="a{n}_b">{gloss}</p></li>')
            buf.append('</ul>')
        parts.append("\n".join(buf))

    money_rows = "\n".join(
        f'<tr><td data-i18n="mt{i}">{lbl}</td><td class="num">{a}</td>'
        f'<td class="num">{b}</td><td class="num">{c}</td></tr>'
        for i, (lbl, a, b, c) in enumerate(MONEY, 1))
    amended_rows = "\n".join(
        f'<tr><td><code>{ref_}</code></td><td data-i18n="an{i}">{name}</td>'
        f'<td data-i18n="aw{i}">{what}</td></tr>'
        for i, (ref_, name, what) in enumerate(AMENDED, 1))

    title = ("The Public Procurement Act explained: 149 articles, the 30% quality "
             "rule and European preference | Brubru")
    desc = ("The EU Public Procurement Act, article by article. What Article 98 really "
            "requires when it says quality must weigh 30%, how European preference works "
            "under Articles 70 to 77, where the EUR 649 million of savings actually comes "
            "from, and the research in the Commission's own impact assessment that cuts "
            "against its central instrument.")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="brubru:last-reviewed" content="2026-09-11">
<title>{title}</title>
<meta name="description" content="{desc}">
<meta property="og:title" content="The Public Procurement Act: one Regulation for fifteen per cent of Europe's economy">
<meta property="og:description" content="Three directives become one directly applicable Regulation of 149 articles. Quality must carry at least 30% of the award, and the Commission can switch off a third country's access by delegated act.">
<meta property="og:type" content="article">
<link rel="icon" type="image/x-icon" href="../assets/favicon.ico">
<link rel="icon" type="image/png" href="../favicon.png">
<link href="https://cdn.jsdelivr.net/npm/@mdi/font@7.4.47/css/materialdesignicons.min.css" rel="stylesheet">
<style>
{style}
{EXTRA_CSS}
</style>
</head>
<body>

<header class="header">
  <img class="header__logo" src="../assets/brubru_mainlogo.png" alt="Brubru">
  <div class="header__text">
    <div class="header__title" data-i18n="header_title">Brubru Deep Dive Library</div>
    <div class="header__subtitle" data-i18n="header_subtitle">Public Procurement Act</div>
  </div>
  <a class="header__cta" href="https://brubru.beresol.eu" data-i18n="header_cta">Try Brubru Free</a>
</header>

<nav class="lang-bar">
  <button class="lang-btn active" data-lang="en">English</button>
  <button class="lang-btn" data-lang="fr">Fran&ccedil;ais</button>
  <button class="lang-btn" data-lang="es">Espa&ntilde;ol</button>
  <button class="lang-btn" data-lang="ca">Catal&agrave;</button>
  <button class="lang-btn" data-lang="it">Italiano</button>
  <button class="lang-btn" data-lang="nl">Nederlands</button>
</nav>

<div class="hero">
  <div class="hero__tag" data-i18n="htag">COM(2026) 590 final &middot; 2026/0265(COD) &middot; 9 September 2026</div>
  <h1 class="hero__title" data-i18n="htitle">The Public Procurement Act
    <span>one Regulation for fifteen per cent of Europe's economy</span></h1>
  <p class="hero__sub" data-i18n="hsubt">Three directives become a single directly applicable Regulation of 149 articles. Quality must carry at least 30% of every award. And the Commission gains the power to switch off a third country's access to the Union's procurement market by delegated act.</p>
</div>

<div class="figs">
  <div class="fig"><div class="fig__n" style="color:var(--blue)">EUR 2.5tn</div><div class="fig__l" data-i18n="f1">Spent each year on public procurement, about 15% of EU GDP</div></div>
  <div class="fig"><div class="fig__n" style="color:var(--green)">EUR 649m</div><div class="fig__l" data-i18n="f2">Net annual burden reduction, the figure behind the rounded 650</div></div>
  <div class="fig"><div class="fig__n" style="color:var(--purple)">149</div><div class="fig__l" data-i18n="f3">Articles, in seven Parts, fifteen Titles and twenty-three Chapters</div></div>
  <div class="fig"><div class="fig__n" style="color:var(--amber)">30% / 50%</div><div class="fig__l" data-i18n="f4">Minimum weight of quality, the higher figure for labour-intensive contracts</div></div>
</div>

<div class="container">

<nav class="toc">
  <h2 data-i18n="toc_h">On this page</h2>
  <ol class="toc__main">
    <li><a href="#s1" data-i18n="toc1">What it actually changes</a></li>
    <li><a href="#s2" data-i18n="toc2">The four ways to buy</a></li>
    <li><a href="#s3" data-i18n="toc3">The 30% quality rule, as written</a></li>
    <li><a href="#s4" data-i18n="toc4">Where the EUR 649 million comes from</a></li>
    <li><a href="#s5" data-i18n="toc5">The finding in the Commission's own file</a></li>
    <li><a href="#s6" data-i18n="toc6">European preference, Articles 70 to 77</a></li>
    <li><a href="#s7" data-i18n="toc7">The fourteen acts it amends</a></li>
    <li class="toc__wide"><a href="#s8" data-i18n="toc8">The Regulation, article by article</a>
      <ol class="toc__parts">{''.join(toc_parts)}</ol></li>
    <li><a href="#s9" data-i18n="toc9">What happens next</a></li>
    <li><a href="#s10" data-i18n="toc10">Official sources</a></li>
  </ol>
</nav>

<section id="s1">
  <h2 class="sec" data-i18n="s1_h">1. What it actually changes</h2>
  <p class="lead" data-i18n="s1_1">The act repeals Directives 2014/23/EU, 2014/24/EU and 2014/25/EU and replaces all three with one directly applicable Regulation. That single word carries more weight than the page count.</p>
  <p data-i18n="s1_2">A directive is transposed. Twenty-seven national transpositions of the 2014 rules are the reason a Spanish contractor bidding in Poland meets a different procedural world from the one it knows at home, even though both were built from the same Brussels text. A Regulation is not transposed. Article 149 says it is binding in its entirety and directly applicable, so the rules reach the bidder without a national intermediary rewriting them on the way.</p>
  <p data-i18n="s1_3">Inside that container, three structural moves. Procedures are rebuilt around an open procedure, a dynamic procedure that stays open for operators to join at any time, and a genuinely new innovation procedure for societal challenges with no known solution. Negotiation stops being exceptional: Article 33 makes it an ordinary feature of any procedure, and Article 102 lets a buyer correct an error mid-procedure instead of cancelling and starting again. And the whole life-cycle becomes data: six public summaries under Article 110, filed into a national data space under Article 134 and a Union-level one under Article 135.</p>
  <div class="note">
    <h3 data-i18n="s1_n_h">What does not change</h3>
    <p data-i18n="s1_n_b">The thresholds. Article 2 keeps EUR 5 404 000 for works and concessions, EUR 140 000 for central government supplies and services, EUR 216 000 for sub-central, EUR 432 000 in utilities and EUR 750 000 for social, health and educational services. They are set by the WTO Government Procurement Agreement, not by this reform, and Article 3 has the Commission re-checking them against it every two years.</p>
  </div>
</section>

<section id="s2">
  <h2 class="sec" data-i18n="s2_h">2. The four ways to buy</h2>
  <p data-i18n="s2_1">Article 31 governs the choice. The first two are available for anything at all; the other two are confined.</p>
  <div class="steps">
    <div class="step"><h3 data-i18n="s2_a_h">Open procedure (Articles 34 to 35)</h3><p data-i18n="s2_a_b">The buyer publishes a summary of competition saying whether selection criteria apply and whether it intends to negotiate. Anyone interested expresses interest and tenders. Award follows Article 98.</p></div>
    <div class="step"><h3 data-i18n="s2_b_h">Dynamic procedure (Articles 36 to 40)</h3><p data-i18n="s2_b_b">A standing procedure with a stated period of validity. Operators may ask to join at any point during it, which is the part that matters: a supplier that missed the opening is not locked out for years.</p></div>
    <div class="step"><h3 data-i18n="s2_c_h">Innovation procedure (Articles 41 to 45)</h3><p data-i18n="s2_c_b">For a societal challenge with no identified suitable solution. Five phases, a mandatory market consultation of at least two months, and a testing and validation phase of up to two years that can include field trials and pilots.</p></div>
    <div class="step"><h3 data-i18n="s2_d_h">Direct award (Articles 46 to 48)</h3><p data-i18n="s2_d_b">A solution requested directly, with no competition and no prior publication, in the exhaustive cases of Article 47 or the extreme urgency of Article 48. A public summary of result still follows.</p></div>
  </div>
  <p data-i18n="s2_2">Research and development bought on its own sits outside the act entirely under Article 79. Defence and security contracts remain with their own directive under Article 78.</p>
</section>

<section id="s3">
  <h2 class="sec" data-i18n="s3_h">3. The 30% quality rule, as written</h2>
  <p class="lead" data-i18n="s3_1">This is the provision the press release leads with, and the one most often paraphrased into something the text does not say.</p>
  <p data-i18n="s3_2">Article 98(1) requires award to the operator offering the best quality for money, evaluated by the best price-quality ratio. Article 98(4) puts a floor under it: the weight of quality criteria shall represent <strong>at least 30% of total points awarded</strong>, and <strong>at least 50% for contracts where the subject-matter is labour-intensive</strong>.</p>
  <div class="note">
    <h3 data-i18n="s3_n_h">Two details the summaries drop</h3>
    <p data-i18n="s3_n_b">Where life-cycle costing is applied under Article 99, its weight is <strong>counted within</strong> that percentage rather than added on top. The same applies to environmental criteria set by Union legislation. A buyer who reaches 30% by counting life-cycle costs has satisfied the article without weighing a single further quality factor.</p>
  </div>
  <p data-i18n="s3_3">Article 98(5) is the escape, and it is a comply-or-explain mechanism rather than an exemption. A buyer may depart from the floor where quality is secured instead through specifications, through contract performance conditions, or through a combination of those with quality-based award criteria. It must say which route it took in the public summary of competition. What it may not do is dress up bare compliance with obligations as an award criterion.</p>
  <p data-i18n="s3_4">Article 98(2) lists what quality can mean: technical merit, aesthetic and functional characteristics, accessibility and design for all, production methods, environmental and social considerations, innovation objectives, security and resilience, the qualification and experience of the staff actually assigned, after-sales service and delivery conditions. A buyer may also fix the price outright and have operators compete on quality alone.</p>
</section>

<section id="s4">
  <h2 class="sec" data-i18n="s4_h">4. Where the EUR 649 million comes from</h2>
  <p data-i18n="s4_1">The press release claims about EUR 650 million in annual administrative savings. The impact assessment's own table gives EUR 649 million net, and it repays reading rather than rounding, because it shows which part of the reform pays for the rest. Figures are annualised present values over a seven-year application period at a 3% discount rate, in millions of euro per year.</p>
  <div class="table-wrap"><table class="tbl">
    <thead><tr><th data-i18n="mth1">Measure</th><th class="num" data-i18n="mth2">Public buyers</th><th class="num" data-i18n="mth3">Economic operators</th><th class="num" data-i18n="mth4">Total</th></tr></thead>
    <tbody>
      {money_rows}
      <tr class="total"><td data-i18n="mt_tot">Net</td><td class="num">&minus;79</td><td class="num">&minus;570</td><td class="num">&minus;649</td></tr>
    </tbody>
  </table></div>
  <p data-i18n="s4_2">Two things follow, and neither is in the press release.</p>
  <div class="grid2">
    <div class="card"><h3 data-i18n="s4_c1_h">The simplification story is a digitisation story</h3><p data-i18n="s4_c1_b">The digital marketplace delivers EUR 1 101 million of the EUR 1 267 million of removed burden. That is 87% of every saving in the file. Procedural simplification, the part the headlines describe, contributes EUR 166 million. If the eProcurement platform, the electronic eligibility service and the data spaces underdeliver, so does the entire business case.</p></div>
    <div class="card"><h3 data-i18n="s4_c2_h">The flagship policy is the single largest new cost</h3><p data-i18n="s4_c2_b">The quality rule adds EUR 512 million of new burden, EUR 457 million of it falling on economic operators rather than on the administrations that chose it. It is the biggest single new cost in the reform, and it is the bill for the policy the communication leads with.</p></div>
  </div>
  <p data-i18n="s4_3">The executive summary quotes about EUR 1 billion and EUR 220 million in places. Those are gross removed burdens before the new ones are subtracted, not a competing estimate.</p>
</section>

<section id="s5">
  <h2 class="sec" data-i18n="s5_h">5. The finding in the Commission's own file</h2>
  <p data-i18n="s5_1">The reform is justified by declining competition, and in particular by the European Court of Auditors on the rise of single-bid procedures. The impact assessment then cites research suggesting that the chosen instrument may deepen that very problem wherever administrative capacity is weakest.</p>
  <div class="quote">
    <p data-i18n="s5_q">Countries with weaker public administrations experienced an increase in single bidding of approximately 10 to 11 percentage points, which was associated with their increased use of the most economically advantageous tender criteria. In contrast, countries with strong public administrations saw a reduction in single bidding by 4 to 7 percentage points, while their use of those criteria remained largely unchanged.</p>
    <cite data-i18n="s5_c">Impact assessment SWD(2026) 591 final, page 40, summarising Loxbo and Pircher (2025)</cite>
  </div>
  <p data-i18n="s5_2">Single bidding is the standard proxy for irregularity risk, so this is not a marginal indicator. The impact assessment states the consequence plainly: more flexible award criteria may improve or worsen procurement outcomes depending on the capacity of the contracting authority. The same file notes a growing divergence between northern and western Member States and the rest.</p>
  <p data-i18n="s5_3">The act makes quality-weighted award the default across the whole Union, for every buyer, from a national ministry to a municipality of four thousand people. That is not an argument against the reform, and the Commission did not hide the evidence. It is the reason Article 139 on professionalisation and capacity building carries far more weight than its position near the end of the act suggests, and the reason the comply-or-explain derogation in Article 98(5) is worth watching through the negotiation: it is the pressure valve for exactly the administrations the research is about.</p>
</section>

<section id="s6">
  <h2 class="sec" data-i18n="s6_h">6. European preference, Articles 70 to 77</h2>
  <p class="lead" data-i18n="s6_1">Politically this is the decisive chapter, and it works in two layers that are easy to conflate.</p>
  <div class="grid2">
    <div class="card"><h3 data-i18n="s6_c1_h">Layer one: who counts as covered</h3><p data-i18n="s6_c1_b">Article 70 defines covered operators, goods, services and works by reference to the Union's international commitments, chiefly the WTO Government Procurement Agreement and bilateral trade agreements. Article 71 obliges the Commission to publish a free online tool mapping those commitments, so a buyer can tell.</p></div>
    <div class="card"><h3 data-i18n="s6_c2_h">Layer two: the Commission's switch</h3><p data-i18n="s6_c2_b">Article 72 empowers the Commission to adopt <strong>delegated acts removing covered status</strong> from a given third country. Three grounds: a factual market access analysis showing it failed to give Union operators national treatment contrary to its commitments; avoiding dependencies that threaten security of supply; or any other exception under the applicable agreement, in particular protecting economic security interests.</p></div>
  </div>
  <p data-i18n="s6_2">Article 73 is what a public buyer may then actually do, and the options differ sharply in severity.</p>
  <ul class="checks">
    <li data-i18n="s6_l1"><strong>Restrict participation</strong> to Union and covered operators outright, including rules for consortia where most but not all members qualify (Article 73(1)(a)).</li>
    <li data-i18n="s6_l2"><strong>Reject a tender</strong> during the procedure where it does not come from Union or covered operators or their subcontractors (Article 73(1)(b)).</li>
    <li data-i18n="s6_l3"><strong>Require Union origin</strong> for the goods, services or works, either fully, to a certain degree, or for specific components (Article 73(2)(a)).</li>
    <li data-i18n="s6_l4"><strong>Apply a price reduction or extra award points</strong>, solely for evaluation and ranking, without changing the price actually payable under the contract (Article 73(2)(b)).</li>
    <li data-i18n="s6_l5"><strong>Reject a tender whose Union or covered content is below 50%</strong> of the tender's total estimated value (Article 73(2)(c)).</li>
  </ul>
  <p data-i18n="s6_3">Anything under Article 73(2) must be stated in the competition public summary before tenders are prepared, with the specific goods required to be of Union origin and the exact percentage or points allocation spelled out. A buyer cannot discover a preference after seeing the bids.</p>
  <div class="note">
    <h3 data-i18n="s6_n_h">The provision to watch is Article 75</h3>
    <p data-i18n="s6_n_b">Article 73 is permissive: a buyer <em>may</em>. Article 75 lets the Commission adopt delegated acts that <strong>require</strong> buyers to apply those same requirements to non-covered operators, goods, services and works where it is in the Union's interest. That converts an option available to each buyer into an obligation imposed on all of them, through a delegated act rather than a new legislative proposal. Article 141 confers that power for an indeterminate period.</p>
  </div>
  <p data-i18n="s6_4">Article 72(2) lets Member States and interested parties put evidence of a qualifying situation to the Commission at any time, which makes this something industry can trigger rather than only wait for. Article 76 keeps a set of exceptions for buyers, and Article 77 makes this chapter the default wherever other Union legislation sets origin conditions in procurement.</p>
</section>

<section id="s7">
  <h2 class="sec" data-i18n="s7_h">7. The fourteen acts it amends</h2>
  <p data-i18n="s7_1">Repealing three directives is the headline. The quieter half of the reform is Article 147, which reaches into fourteen other instruments, deletes the procurement provision sitting inside each, and redirects its references here. Several are laws with live compliance deadlines of their own.</p>
  <div class="table-wrap"><table class="tbl">
    <thead><tr><th data-i18n="ath1">Instrument</th><th data-i18n="ath2">Known as</th><th data-i18n="ath3">What Article 147 does to it</th></tr></thead>
    <tbody>{amended_rows}</tbody>
  </table></div>
  <p data-i18n="s7_2">Read down the third column and the design becomes obvious: seven separate acts had each grown their own green procurement clause, and all seven now point at Article 54. That is the consolidation the reform is really performing, and it is why a compliance team that tracks the Ecodesign Regulation or the Batteries Regulation needs to read this proposal even though it is filed under procurement.</p>
  <div class="note">
    <h3 data-i18n="s7_n_h">One discrepancy worth knowing about</h3>
    <p data-i18n="s7_n_b">The proposal's own title, reproduced in the legislative financial statement, lists thirteen amended acts. Article 147 amends fourteen. The one missing from the title is Regulation (EC) No 1370/2007 on public passenger transport, which Article 147(14) does amend, by making public service contracts subject to the security, resilience and European preference chapters. Anyone building a compliance register from the title rather than from the enacting terms will miss it.</p>
  </div>
</section>

<section id="s8">
  <h2 class="sec" data-i18n="s8_h">8. The Regulation, article by article</h2>
  <p class="lead" data-i18n="s8_1">All 149 articles, in the order the proposal presents them, across seven Parts, fifteen Titles and twenty-three Chapters. Nothing is skipped.</p>
{chr(10).join(parts)}
</section>

<section id="s9">
  <h2 class="sec" data-i18n="s9_h">9. What happens next</h2>
  <p data-i18n="s9_1">This is a proposal under the ordinary legislative procedure, 2026/0265(COD), on the legal basis of Article 114 TFEU. It now goes to the European Parliament and the Council, and nothing in it binds anyone until both have agreed a text and it is published in the Official Journal.</p>
  <div class="steps">
    <div class="step"><h3 data-i18n="s9_a_h">Entry into force</h3><p data-i18n="s9_a_b">The twentieth day after publication in the Official Journal (Article 149).</p></div>
    <div class="step"><h3 data-i18n="s9_b_h">Application</h3><p data-i18n="s9_b_b">Two years after entry into force. Everything below the thresholds and every existing contract keeps running under the old regime until then.</p></div>
    <div class="step"><h3 data-i18n="s9_c_h">Database access</h3><p data-i18n="s9_c_b">Article 29 sets a hard date of 15 June 2029 for Member States to open the relevant national registers to the eligibility service, free of charge.</p></div>
    <div class="step"><h3 data-i18n="s9_d_h">Review</h3><p data-i18n="s9_d_b">Every seven years the Commission evaluates the Regulation and reports to Parliament, Council, the Economic and Social Committee and the Committee of the Regions (Article 148).</p></div>
  </div>
  <p data-i18n="s9_2">Three things are worth watching through the negotiation: whether the 30% floor in Article 98(4) survives at that level, whether the Article 98(5) derogation is widened or narrowed, and whether the delegated power in Article 75 stays as it is. The last of those is the one that changes the Union's trade posture without another legislative proposal.</p>
</section>

<section id="s10">
  <h2 class="sec" data-i18n="s10_h">10. Technical annex</h2>
  <details class="annex">
    <summary data-i18n="s10_sum">Documents, figures and how we checked them</summary>

    <h3 data-i18n="annex_docs_h">Documents</h3>
    <ul>
      <li>Proposal for a Regulation on public contracts and concessions, repealing Directive 2014/23/EU, Directive 2014/24/EU and Directive 2014/25/EU and amending fourteen further acts (Public Procurement Act), <a href="https://single-market-economy.ec.europa.eu/document/download/59557310-3af0-426d-b6b6-0357b650065f_en?filename=Proposal%20for%20a%20Regulation%20-%20Public%20Procurement%20Act.pdf">COM(2026) 590 final</a>, 9 September 2026, procedure 2026/0265(COD), legal basis Article 114 TFEU</li>
      <li><a href="https://single-market-economy.ec.europa.eu/document/download/186521c1-e565-493e-a5b1-672491a472b0_en?filename=Annex%20-%20Public%20Procurement%20Act.pdf">Annexes I to VIII</a> to the proposal, including the correlation table in Annex VIII, Part A</li>
      <li>Accompanying documents SEC(2026) 590, <a href="https://single-market-economy.ec.europa.eu/document/download/a1946f76-deb8-4846-8766-6f8f57c13b63_en?filename=Subsidiarity%20grid%20-%20Public%20Procurement%20Act.pdf">SWD(2026) 590 final</a> (subsidiarity grid), <a href="https://single-market-economy.ec.europa.eu/document/download/a7bd4700-7601-4c63-b5ab-21f6a532e6b8_en?filename=Impact%20assessment%20-%20Public%20Procurement%20Act.pdf">SWD(2026) 591 final</a> (impact assessment, 432 pages), <a href="https://single-market-economy.ec.europa.eu/document/download/0ac75d0f-a769-41cd-a468-71e9fdbf26c4_en?filename=Resume%20impact%20assessment%20-%20Public%20Procurement%20Act.pdf">SWD(2026) 592 final</a> (executive summary)</li>
      <li>Press release <a href="https://ec.europa.eu/commission/presscorner/detail/en/ip_26_1817">IP/26/1817</a>, 9 September 2026</li>
      <li>Loxbo, K., &amp; Pircher, B. (2025). Complexity meets flexibility: unintended differentiation in EU public procurement. <em>Journal of European Public Policy</em>, 32(11), 2714 to 2740. Cited at footnote 193, page 40 of the impact assessment</li>
      <li>European Court of Auditors, Special Report 28/2023, Public procurement in the EU: less competition for contracts awarded for works, goods and services in the 10 years up to 2021. Cited at footnote 39 of the impact assessment, pages 33 and 49</li>
      <li>Council conclusions of 3 June 2024 on Special Report 28/2023, C/2024/3521</li>
      <li><a href="https://brubru.beresol.eu/guides/">Brubru knowledge guides</a>: the Public Procurement Act, and European preference in procurement</li>
    </ul>

    <h3 data-i18n="annex_law_h">Union law referenced in the articles</h3>
    <ul>
      <li>Directive 2014/23/EU, Directive 2014/24/EU and Directive 2014/25/EU, the 2014 procurement directives, all three repealed by Article 146</li>
      <li>Directive 89/665/EEC and Directive 92/13/EEC, the remedies directives, whose standstill period Article 35 expressly preserves</li>
      <li>Directive 2009/81/EC on defence and security procurement, excluded by Article 78</li>
      <li>The fourteen acts amended by Article 147, listed in full in section 7 above</li>
      <li>Regulation (EU) 2022/1031 (International Procurement Instrument) for the origin of operators, and Regulation (EU) No 952/2013 (Union Customs Code) for the origin of goods, both through Article 74</li>
      <li>Regulation (EU, Euratom) 2024/2509, the Financial Regulation, through Articles 10 and 145</li>
      <li>Regulation (EU) No 1025/2012 on standardisation (Articles 129 and 130) and Regulation (EU) No 182/2011 on comitology (Article 143), with the Advisory Committee on Public Contracts established by Council Decision 71/306/EEC</li>
      <li>Regulation (EU) 2017/1369 on energy labelling (Article 52), Directive 2011/7/EU on late payment (Article 108), Directive (EU) 2022/2555, NIS2 (Article 69), Regulation (EU) 2024/1781 for the digital product passport as means of proof (Article 92)</li>
      <li>Regulation (EC) No 1008/2008 on air services (Article 117) and Directive 97/67/EC on postal services (Article 17)</li>
      <li>Regulation (EU) 2024/2747 and Council Regulation (EU) 2022/2372, the Union emergency frameworks that switch on Article 48</li>
      <li>The proposed Regulation establishing the European Business Wallets, referenced but not yet numbered, in Articles 131 and 133</li>
    </ul>

    <h3 data-i18n="annex_fig_h">How the economic figures were produced</h3>
    <ul>
      <li>Every euro figure on this page is an <strong>annualised present value over a seven-year application period at a 3% discount rate</strong>, as the impact assessment states beneath each of its tables.</li>
      <li>The headline <strong>EUR 649 million</strong> is the net recurrent annual saving in the central scenario, reported under the <strong>one in, one out</strong> approach, alongside a one-off cost of <strong>EUR 1.14 million</strong> for economic operators.</li>
      <li>Per-procedure costs are scaled to EU-wide totals using <strong>304 000 procedures</strong> a year, and to per-operator figures using an average of <strong>3.3 bids per procedure</strong>.</li>
      <li>Measure codes used in the money table: <strong>MPL.1</strong> the digital marketplace (minus 1 101), <strong>FLX.2</strong> simplification and negotiation (minus 166 removed against 78 new), <strong>ESI.2</strong> the best price-quality ratio rule (512 new, of which 457 on operators), <strong>BEU.2</strong> European preference (15 new).</li>
      <li>On the Better Regulation toolbox, the impact assessment records that Tool #56 (typology of costs and benefits) <em>was applied</em>, Tool #58 (EU Standard Cost Model) <em>was considered</em> for implementation costs and savings, and Tool #63 (cost-benefit analysis) <em>was implemented</em>.</li>
      <li><strong>No general equilibrium model is used in this file.</strong> Unlike the European Innovation Act, whose figures come from a RHOMOLO simulation, these are administrative-cost estimates. They should not be read as a forecast of GDP or employment effects.</li>
    </ul>

    <h3 data-i18n="annex_method_h">How this page was checked</h3>
    <ul>
      <li data-i18n="annex_m1">Every source was read end to end rather than searched: the proposal, the annexes, the subsidiarity grid, the impact assessment, its executive summary and the press release.</li>
      <li data-i18n="annex_m2">All 149 articles were read in the published enacting terms, and the count was verified mechanically rather than trusted: the proposal contains exactly 149 "Article N" headings, each occurring once, and the numbering on this page runs 1 to 149 in order with no gaps.</li>
      <li data-i18n="annex_m3">Every figure was matched against the source with the whitespace collapsed first, because a PDF text extract wraps sentences mid-clause and a naive search fails on facts that are present and correct.</li>
      <li data-i18n="annex_m4">The number of amended acts was taken from Article 147, which amends fourteen, not from the proposal's own title, which names thirteen. Where the two disagree the enacting terms govern, and the discrepancy is reported in section 7 rather than quietly resolved.</li>
    </ul>
  </details>
</section>

</div>

<div class="cta">
  <h2 data-i18n="cta_h">Follow this file as it moves</h2>
  <p data-i18n="cta_b">Brubru tracks every EU legislative file from proposal to Official Journal, in six languages, and answers questions about them in plain language.</p>
  <a href="https://brubru.beresol.eu" data-i18n="cta_btn">Start free</a>
</div>

<div class="page-meta">
  <p data-i18n="pm">Public Procurement Act deep dive by <a href="https://brubru.beresol.eu">Brubru</a>, the AI-powered EU policy assistant by <a href="https://beresol.eu">Beresol</a>.<br>V&iacute;ctor Sol&eacute; &middot; Updated 11 September 2026</p>
  <p class="credit" data-i18n="pc">Hero photography by Aimee, section photography by Samuel W&ouml;lfl, both via Pexels.</p>
</div>

{footer}

<script>
const attr = (sel) => {{ const el = document.querySelector(sel); return el ? el.getAttribute('content') : undefined; }};
const EN_HEAD = {{ page_title: document.title, page_desc: attr('meta[name="description"]'),
                  og_title: attr('meta[property="og:title"]'), og_desc: attr('meta[property="og:description"]') }};
const translations = __TRANSLATIONS__;
function setLang(l) {{
  const dict = translations[l] || {{}};
  document.querySelectorAll('[data-i18n]').forEach(el => {{
    const k = el.getAttribute('data-i18n');
    if (l === 'en') {{ if (el.dataset.en !== undefined) el.innerHTML = el.dataset.en; return; }}
    if (el.dataset.en === undefined) el.dataset.en = el.innerHTML;
    if (dict[k] !== undefined) el.innerHTML = dict[k];
  }});
  // The body goes through innerHTML, which decodes entities. document.title and a
  // meta content attribute do NOT: assigning "expliqu&eacute;e&nbsp;:" puts those
  // seven literal characters in the browser tab. Decode before assigning.
  const decode = (s) => {{ const d = document.createElement('textarea'); d.innerHTML = s; return d.value; }};
  const head = (l === 'en') ? EN_HEAD : dict;
  if (head.page_title) document.title = decode(head.page_title);
  const setMeta = (sel, v) => {{ const el = document.querySelector(sel); if (el && v) el.setAttribute('content', decode(v)); }};
  setMeta('meta[name="description"]', head.page_desc);
  setMeta('meta[property="og:title"]', head.og_title);
  setMeta('meta[property="og:description"]', head.og_desc);
  document.documentElement.lang = l;
  document.querySelectorAll('.lang-btn').forEach(b =>
    b.classList.toggle('active', b.dataset.lang === l));
}}
document.querySelectorAll('.lang-btn').forEach(b =>
  b.addEventListener('click', () => setLang(b.dataset.lang)));
setLang('en');
</script>
</body>
</html>
"""
    translations = build_translations(ref)
    audit_translations(html, translations)
    html = html.replace("__TRANSLATIONS__",
                        json.dumps(translations, ensure_ascii=False, sort_keys=True))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    print(f"[OK] {OUT}")
    print(f"     {OUT.stat().st_size/1000:.0f} KB, {total_arts} articles, "
          f"{sum(len(gs) for _,_,_,gs in STRUCTURE)} chapter groups, "
          f"{len(AMENDED)} amended acts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
