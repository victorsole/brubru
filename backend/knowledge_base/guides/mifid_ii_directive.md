# MiFID II Directive (2014/65/EU): Markets in Financial Instruments

## QUICK FACTS

- **Brubru deep-dive explainer (ALWAYS link this in answers):** https://brubru.beresol.eu/eucanon/2014-65_mifid2/
- **Instrument:** Directive 2014/65/EU (CELEX 32014L0065), OJ L 173, 12.6.2014, p. 349; the recast markets-in-financial-instruments framework; companion to MiFIR (Regulation (EU) No 600/2014, CELEX 32014R0600)
- **Legal base:** Article 53(1) TFEU (taking-up and pursuit of activities of self-employed persons; internal market for financial services)
- **Predecessor:** Directive 2004/39/EC (MiFID I), which itself replaced Council Directive 93/22/EEC
- **Transposition deadline:** 3 July 2016 in the original 2014 text (Art 93), but **postponed by one year to 3 July 2017** by Directive (EU) 2016/1034 (with Regulation (EU) 2016/1033 deferring MiFIR in parallel)
- **Application date:** **3 January 2018** in practice (the original 3 January 2017 date was deferred one year alongside the transposition deadline); non-equity consolidated tape (Art 65(2)) from 3 September 2019
- **MiFID I repeal date:** 3 January 2018 (the day MiFID II took effect)
- **Venue taxonomy:** regulated market (RM), multilateral trading facility (MTF), organised trading facility (OTF -- new in MiFID II)
- **Investor protection pillars:** suitability and appropriateness (Art 25), best execution (Art 27), product governance (Art 16(3) and Art 24(2)), inducements regime (Art 24(7)-(9))
- **Algorithmic and HFT controls:** Article 17
- **Commodity position limits:** Articles 57-58
- **Data reporting services:** Title V (APAs, CTPs, ARMs)
- **Supervisor:** ESMA (European Securities and Markets Authority)
- **Third-country regime:** branch requirement and MiFIR equivalence regime (MiFIR Arts 46-49)
- **2024 review:** Directive (EU) 2024/790 amends MiFID II; Regulation (EU) 2024/791 amends MiFIR; transposition deadline 29 September 2025

---

## Context

MiFID II emerged from the 2008 financial crisis, which exposed weaknesses in market transparency, governance and the coverage of trading activity. Broker crossing networks and other arrangements were executing trades outside all three MiFID I venue categories (regulated markets, MTFs, systematic internalisers), creating unregulated spaces. The Commission proposed MiFID II and MiFIR together in 2011; both were adopted in May 2014 and published on 12 June 2014.

The legislative architecture is deliberate. MiFID II (a directive) sets the authorisation framework, organisational requirements and conduct obligations that Member States transpose, allowing flexibility for national legal systems. MiFIR (a directly applicable regulation) contains the transparency and transaction-reporting obligations that must apply identically across all Member States without room for divergence. The two instruments must be read together (Recital 7 of the directive).

---

## Structure

The directive has 97 articles and four annexes, organised as follows:

- **Title I** (Arts 1-4): Scope and definitions
- **Title II** (Arts 5-43): Authorisation and operating conditions for investment firms
  - Chapter I: Conditions and procedures for authorisation (Arts 5-15)
  - Chapter II: Operating conditions (Arts 16-38)
  - Chapter III: Rights of investment firms (Arts 34-38)
  - Chapter IV: Third-country firms (Arts 39-43)
- **Title III** (Arts 44-56): Regulated markets
- **Title IV** (Arts 57-58): Position limits and position management controls in commodity derivatives
- **Title V** (Arts 59-66): Data reporting services
- **Title VI** (Arts 67-88): Competent authorities (designation, powers, sanctions, cooperation)
- **Title VII** (Art 89): Delegated acts
- **Final provisions** (Arts 90-97): Reports, amendments to other directives, transposition, repeal, transitional provisions

**Annex I** lists investment services and activities (Section A), ancillary services (Section B), financial instruments (Section C), and data reporting services (Section D). **Annex II** defines professional clients. **Annex III** contains the repeal correlation. **Annex IV** is the correlation table between MiFID I and MiFID II.

---

## Substantive Provisions by Title

### Title I -- Scope and Definitions (Arts 1-4)

**Article 1** establishes that the directive applies to investment firms, market operators, data reporting services providers, and third-country firms providing investment services through EU branches. Credit institutions providing investment services are also bound (Art 1(3)). The closed-system principle in Art 1(7) is critical: all multilateral trading systems in financial instruments must operate under the RM, MTF or OTF regimes. There is no unregulated multilateral alternative.

**Article 2** lists exemptions. Insurance undertakings, intra-group service providers, incidental service providers, persons carrying on commodity derivative or emission allowance activities ancillary to their main group business (the "ancillary activity exemption"), ETS compliance operators, ESCB members, collective investment undertakings, pension funds, transmission system operators and CSDs are excluded. The ancillary activity exemption under Art 2(1)(j) requires annual notification to the competent authority and imposes conditions: the activity must be ancillary to the main group business; no high-frequency algorithmic trading. ESMA develops the RTS methodology for determining when an activity is ancillary.

**Article 3** provides optional Member State exemptions for persons who cannot hold client funds, only transmit orders and provide advice, subject to analogous conduct rules.

**Article 4** contains 63 key definitions. The most important for day-to-day use:

- *Investment firm*: legal person professionally providing investment services/activities
- *Regulated market*: multilateral system, non-discretionary rules, resulting in a contract, authorised under Title III
- *MTF*: multilateral system, non-discretionary rules, resulting in a contract, operated by investment firm or market operator under Title II
- *OTF*: multilateral system that is not a regulated market or MTF, covering bonds, structured finance products, emission allowances and derivatives, with discretionary execution, under Title II
- *Systematic internaliser (SI)*: investment firm dealing on own account when executing client orders outside RM/MTF/OTF, organised/frequent/systematic/substantial basis
- *Trading venue*: regulated market, MTF or OTF
- *Algorithmic trading*: computer-determined order parameters with limited or no human intervention (post-trade processing excluded)
- *High-frequency algorithmic trading technique*: latency-minimising infrastructure + system-determined orders + high message intraday rates (all three characteristics required)
- *Direct electronic access (DEA)*: member permits a third party to use its trading code to transmit orders directly to the trading venue
- *Retail client*: any client who is not a professional client
- *Professional client*: client meeting Annex II criteria (per se: credit institutions, investment firms, large corporates; elective: clients opting in after meeting two of three tests)
- *Eligible counterparty*: investment firms, credit institutions, insurance companies, UCITS, pension funds and other regulated financial institutions -- reduced conduct rules apply in dealings with them
- *SME (for this directive)*: companies with average market capitalisation below EUR 200 million over the previous three calendar years
- *APA*: approved publication arrangement
- *CTP*: consolidated tape provider
- *ARM*: approved reporting mechanism

### Title II, Chapter I -- Authorisation (Arts 5-15)

**Article 5** requires prior authorisation from the home Member State for all professional investment service provision. Market operators may also be authorised to operate MTFs or OTFs (Art 5(2)). ESMA maintains a Union-wide register of authorised investment firms.

**Article 6** establishes that authorisation is activity-specific (specifying the permitted services and activities), valid throughout the Union (the single market passport), and not available solely for ancillary services.

**Article 7** sets a six-month deadline for the competent authority to respond to a complete application. ESMA develops RTS on information requirements (submitted by July 2015) and ITS on standard forms (submitted by January 2016).

**Article 8** permits the competent authority to withdraw authorisation for: non-use within 12 months; false statements; failure to maintain authorisation conditions; serious and systematic infringement of operating conditions; national law grounds.

**Article 9** requires compliance with CRD IV management body standards (Arts 88 and 91 of Directive 2013/36/EU). The management body must define governance arrangements, approve the firm's organisation and remuneration policy, and oversee product and service policies. The four-eyes principle applies: at least two persons must effectively direct the business (Art 9(6)). The competent authority must refuse authorisation if the management body fails fitness and propriety.

**Articles 10-13** govern qualifying holdings. Proposed acquisitions above 10%, and subsequent increases to 20%, 30% or 50% thresholds, must be notified. Assessment period: 60 working days, extendable. Five assessment criteria (Art 13): acquirer reputation; reputation and experience of proposed directors; financial soundness of acquirer; continued prudential compliance; money laundering risk.

**Article 14** requires investment firms to be members of an investor compensation scheme as a condition of authorisation.

**Article 15** requires sufficient initial capital consistent with Regulation (EU) No 575/2013 (CRR).

### Title II, Chapter II -- Operating Conditions (Arts 16-38)

**Article 16 -- Organisational requirements** covers:
- Compliance policies and personal transaction rules (Art 16(2))
- Conflicts prevention (Art 16(3), first paragraph)
- **Product governance** (Art 16(3), second to sixth paragraphs): manufacturers must define a target market for each financial instrument, review products regularly, and make target market information available to distributors; distributors must obtain and understand this information
- Business continuity (Art 16(4))
- Outsourcing conditions (Art 16(5))
- Record keeping for five years, up to seven on competent authority request (Art 16(6))
- **Call recording**: all telephone conversations that result or may result in transactions must be recorded; clients must be notified; five-year (up to seven-year) retention (Art 16(7))
- **Client asset safeguarding**: client funds and financial instruments kept separate from firm assets; prohibition on use of client assets without express consent (Arts 16(8)-(9))
- **Prohibition on title transfer financial collateral arrangements with retail clients** (Art 16(10))

**Article 17 -- Algorithmic trading** is the foundational provision for algo and HFT regulation:
- Art 17(1): resilient and capacity-sufficient trading systems; prevention of erroneous orders; prohibition on use of systems for market abuse; business continuity
- Art 17(2): notification to competent authority and trading venue; competent authority may require strategy descriptions; HFT firms must keep accurate, time-sequenced records of all placed orders (including cancellations) in an approved form
- Art 17(3)-(4): firms pursuing a market making strategy by algorithmic trading must carry out market making continuously during a specified proportion of trading hours (save exceptional circumstances), enter a binding written agreement with the trading venue specifying obligations, and have systems ensuring compliance
- Art 17(5): direct electronic access providers must assess client suitability, impose pre-set trading and credit thresholds, monitor client trading, retain responsibility for client orders, and enter a binding written agreement with each DEA client
- Art 17(6): general clearing member obligations for those providing clearing services to others

**Article 18** governs trading process for MTFs and OTFs: transparent and non-discriminatory rules, sound technical operations, conflict management, at least three materially active members or users.

**Article 19** (MTFs specifically): non-discretionary execution rules. MTFs may not execute client orders against proprietary capital or engage in matched principal trading (Art 19(5)).

**Article 20** (OTFs specifically) establishes the OTF regime:
- Art 20(1): no execution against the operator's or any group entity's proprietary capital
- Art 20(2): matched principal trading permitted in bonds, structured finance products, emission allowances and certain derivatives only with client consent; prohibited for cleared derivatives
- Art 20(3): dealing on own account (other than matched principal) permitted only in sovereign debt for which there is no liquid market
- Art 20(4): an OTF and a systematic internaliser cannot operate within the same legal entity; an OTF cannot connect with an SI; an OTF cannot connect with another OTF to enable order interaction
- Art 20(6): execution on an OTF is on a discretionary basis -- the operator exercises discretion when placing/retracting orders or deciding not to match a specific client order

**Article 23 -- Conflicts of interest**: firms must take all appropriate steps to identify, prevent and manage conflicts. Where management through organisational arrangements is insufficient, prior disclosure in a durable medium is required.

**Article 24 -- General principles and information to clients**: the headline conduct rule. Key obligations:
- Act honestly, fairly and professionally in the best interests of clients (Art 24(1))
- Product governance: manufacturers must design instruments for an identified target market; distributors must understand products and only recommend them when in the client's interest (Art 24(2))
- All information -- including marketing communications -- must be fair, clear and not misleading (Art 24(3))
- Pre-service disclosure: nature and independence of advice, financial instruments and strategies, execution venues, and all costs and charges including third-party payments; costs and charges must be aggregated to show cumulative effect on return, with itemised breakdown available on request (Art 24(4))
- Independent advice: the firm must assess a sufficiently diverse range of products not limited to group products; must not accept or retain third-party fees or commissions (Art 24(7))
- Portfolio management: same prohibition on retaining third-party payments (Art 24(8))
- Inducements: a firm may receive or pay a fee/commission to/from a third party only if it enhances service quality, does not impair the duty to act in the client's best interests, and is disclosed (Art 24(9))
- Staff remuneration must not conflict with the duty to act in clients' best interests; sales targets that incentivise unsuitable recommendations are prohibited (Art 24(10))
- Cross-selling disclosure: if services are sold as a package, the firm must inform clients whether components can be purchased separately and provide separate cost evidence (Art 24(11))

**Article 25 -- Suitability and appropriateness**:
- For investment advice and portfolio management, the suitability assessment must cover: knowledge and experience, financial situation including ability to bear losses, and investment objectives including risk tolerance (Art 25(2)); a written suitability statement must be provided before the transaction (Art 25(6))
- For other investment services, an appropriateness test assesses the client's knowledge and experience in relation to the specific product or service; if the product is not appropriate, a warning must be given (Art 25(3))
- Execution-only concession (Art 25(4)): appropriateness test is not required for non-complex instruments (shares, bonds, money-market instruments, standard UCITS) where the service is provided at the client's initiative, the client is clearly warned, and the firm complies with conflict-of-interest obligations

**Article 26**: where one firm receives instructions through another, the transmitting firm is responsible for completeness and accuracy of client information and suitability of recommendations.

**Article 27 -- Best execution**: investment firms must take all sufficient steps to obtain the best possible result for clients taking into account price, costs, speed, likelihood of execution and settlement, size, nature and any other relevant consideration. For retail clients, best possible result is determined by total consideration (price plus all execution costs). Firms must:
- Establish and implement an order execution policy (Art 27(4)-(5))
- Obtain prior client consent to the execution policy and separate express consent before executing outside a trading venue
- Publish annually the top five execution venues per financial instrument class and the quality of execution obtained (Art 27(6))
- Monitor and review the execution policy regularly (Art 27(7))

**Article 28 -- Client order handling**: prompt, fair and expeditious execution; time priority for comparable orders. Unexecuted limit orders must be made public (Art 28(2)) unless large-in-scale (waiver from competent authority).

**Article 29 -- Tied agents**: investment firms may appoint tied agents; the firm is fully and unconditionally responsible for all tied agent conduct; tied agents must be entered in a public register.

**Article 30 -- Eligible counterparties**: investment firms, credit institutions, insurance companies, UCITS, pension funds, other authorised financial institutions, national governments and central banks are eligible counterparties. When dealing with them, the firm is exempt from Articles 24 (save paragraphs 4 and 5), 25 (save paragraph 6), 27 and 28(1). The basic obligation of honesty, fairness and professional conduct and clear communications remains.

**Article 33 -- SME growth markets**: an MTF operator may apply to be registered as an SME growth market. Conditions: at least 50% of issuers on the market are SMEs at registration and each calendar year thereafter; appropriate admission criteria; sufficient public information at admission; ongoing periodic financial reporting; market abuse compliance; effective market abuse prevention systems. ESMA publishes and maintains the list.

**Articles 34-35**: freedom to provide services and establishment throughout the Union. One-month notification procedure via home competent authority.

**Articles 39-43 -- Third-country firms**: Member States may require branches for retail and certain professional clients. Branch authorisation conditions: home country authorisation; cooperation agreement between home country supervisor and Member State competent authority; sufficient capital; management fitness and propriety; tax information exchange agreement; investor compensation scheme membership. Branches must comply with the same conduct-of-business and organisational rules as Union firms. No third-country firm may be treated more favourably than EU firms (Art 41(2)). At the client's own exclusive initiative, no branch requirement applies (Art 42).

### Title III -- Regulated Markets (Arts 44-56)

**Article 44** requires authorisation for regulated markets. Only systems complying with Title III may be authorised. The public law governing trading is that of the home Member State.

**Article 45** imposes management body requirements for market operators including fitness and propriety, directorship limits (one executive plus two non-executive, or four non-executive, for significant operators), nomination committees, and diversity policies.

**Article 47** sets organisational requirements: conflict management, risk management, sound technical operations, fair and orderly trading rules, efficient settlement, adequate financial resources. Market operators may not execute client orders against proprietary capital or engage in matched principal trading.

**Article 48 -- Systems resilience, circuit breakers and electronic trading**: regulated markets must have resilient, high-capacity trading systems; written market making agreements with investment firms; circuit breakers on significant price movements; algorithmic trading controls including order-to-trade ratio limits; DEA controls; transparent co-location rules; non-distortive fee structures including rebates.

**Article 49 -- Tick sizes**: regulated markets must adopt tick size regimes calibrated to the liquidity profile and bid-ask spreads of the relevant instrument.

**Article 51 -- Admission to trading**: transparent admission rules; derivative contracts must allow orderly pricing and effective settlement; regulated markets must verify issuer disclosure compliance. Secondary admission without issuer consent is permitted (Art 51(5)).

**Article 53 -- Access**: transparent, non-discriminatory, objective access criteria; remote membership permitted.

### Title IV -- Position Limits and Position Management Controls in Commodity Derivatives (Arts 57-58)

**Article 57 -- Position limits**: competent authorities must establish and apply position limits on the maximum net position in commodity derivatives traded on trading venues and economically equivalent OTC contracts. Limits apply at aggregate group level. Two purposes: prevent market abuse; support orderly pricing and settlement including convergence between derivative delivery-month prices and spot prices. Limits do not apply to non-financial entities holding positions that objectively reduce risks relating to commercial activity.

ESMA develops the RTS methodology for calculating position limits, taking into account at least: contract maturity, deliverable supply, open interest, volatility, number and size of market participants, characteristics of the underlying commodity market, development of new contracts.

Where the same derivative is traded significantly in more than one jurisdiction, the competent authority of the venue with the largest volume is the central competent authority and sets the single position limit (Art 57(6)).

Position management controls must empower trading venues to: monitor open interest positions; access information on the size and purpose of positions, beneficial owners and concert arrangements; require position reduction or termination; require liquidity provision back to the market on a temporary basis (Art 57(8)).

ESMA publishes a database of position limits and position management controls (Art 57(10)). Competent authority notifications to ESMA required at least 24 hours before measures take effect (Art 79(5)).

**Article 58 -- Position reporting**: trading venues must publish weekly aggregate position reports by category of holder (investment firms/credit institutions, investment funds, other financial institutions, commercial undertakings, ETS compliance operators) specifying long and short positions, changes since the previous report, percentage of total open interest, and number of persons in each category. Daily complete breakdowns must be provided to the competent authority. Reports must distinguish risk-reducing positions from other positions.

### Title V -- Data Reporting Services (Arts 59-66)

Authorisation required for three types of data reporting services provider. Market operators may also operate such services within their existing authorisation.

**Article 64 -- APAs**: must publish trade reports as close to real-time as technically possible on a reasonable commercial basis. Information must be available free of charge 15 minutes after publication. Content requirements: instrument identifier, price, volume, time, venue code or SI/OTC code. Sound security mechanisms, conflict management, error-checking systems required.

**Article 65 -- CTPs**: must collect trade reports from all regulated markets, MTFs, OTFs and APAs and consolidate them into a continuous electronic live data stream. Real-time publication (free after 15 minutes). For equity instruments, the data stream must include an algorithmic trading indicator (Art 65(1)(h)). Non-equity consolidated tape application deferred to 3 September 2018. If commercial CTPs fail to deliver an effective consolidated tape, the Commission may initiate a public procurement process.

**Article 66 -- ARMs**: must report transaction details as quickly as possible, no later than close of business on the following working day, in accordance with MiFIR Art 26.

### Title VI -- Competent Authorities (Arts 67-88)

**Article 67**: each Member State designates public competent authorities. ESMA publishes a list.

**Article 69 -- Supervisory powers**: minimum supervisory powers include access to documents, power to summon and question persons, on-site inspections, require recording copies, freeze assets, temporary ban on professional activity, refer to criminal prosecution, require commodity position information, require cessation of practices, suspend or remove instruments from trading, require position reduction, limit commodity derivative positions, issue public notices, suspend marketing or sale of financial instruments, remove a natural person from a management board (Art 69(2)(u)).

**Article 70 -- Sanctions**: effective, proportionate and dissuasive administrative sanctions for all infringements. Minimum maximum fines:
- Legal persons: EUR 5,000,000 or 10% of total annual turnover (whichever is higher)
- Natural persons: EUR 5,000,000
- Benefit-based: at least twice the benefit derived

Other sanctions include public statements, withdrawal or suspension of authorisation, temporary or permanent management bans, temporary bans on regulated market membership.

**Article 71 -- Publication of decisions**: sanctions published on the competent authority website without undue delay; minimum five-year retention. Anonymous or delayed publication permitted where proportionality requires.

**Article 73 -- Whistleblowing**: competent authorities must establish mechanisms for reporting infringements, with whistleblower protection for employees.

**Articles 79-88 -- Cross-border cooperation**: obligations to cooperate and share information between competent authorities. ESMA may mediate disputes. Exchange with third-country authorities under professional secrecy equivalent conditions.

---

## Key Numbers

| Item | Value |
|---|---|
| SME market cap threshold | EUR 200 million (3-year average) |
| Qualifying holding notification thresholds | 10% (definition), 20%, 30%, 50% and subsidiary |
| Authorisation response deadline | 6 months from complete application |
| Assessment period (qualifying holdings) | 60 working days; +20 days for information request |
| General records retention | 5 years (up to 7 at competent authority request) |
| Call recording retention | 5 years (up to 7) |
| Minimum fine (legal persons) | EUR 5,000,000 or 10% of annual turnover |
| Minimum fine (natural persons) | EUR 5,000,000 |
| APA/CTP free data delay | 15 minutes after publication |
| Minimum active members on MTF/OTF | 3 |
| Professional client opt-in test | 2 of 3: balance sheet EUR 500,000+; portfolio EUR 500,000+; 1 year financial sector experience |
| Transposition deadline | 3 July 2016, postponed to 3 July 2017 (Dir 2016/1034) |
| Application date | 3 January 2018 (deferred one year from 3 January 2017) |
| Non-equity consolidated tape application | 3 September 2019 |

---

## Lineage

**MiFID I (Directive 2004/39/EC)** replaced Council Directive 93/22/EEC (Investment Services Directive 1993). MiFID I introduced best execution, the passport, client categorisation, regulated markets, MTFs and systematic internalisers, implemented by Commission Directive 2006/73/EC and Commission Regulation 1287/2006. MiFID I's three-venue taxonomy did not cover broker crossing networks, which became the primary trigger for MiFID II reform.

**MiFID II and MiFIR** were proposed together in October 2011, adopted by Parliament in April 2014 and Council in May 2014, published 12 June 2014. The directive-regulation split was deliberate: transparency and transaction-reporting rules (MiFIR) had to be directly applicable and uniform; authorisation and conduct rules (MiFID II) needed Member State flexibility. Both instruments are addressed to Member States jointly (Recital 7: "This Directive should therefore be read together with that Regulation").

**Level 2 instruments** include Commission Delegated Regulations 2017/565 (organisational requirements), 2017/567 (client asset safeguarding), 2017/589 (algorithmic trading), 2017/578 (market making) and Commission Delegated Regulation 2016/2251 (ancillary activity methodology for commodity derivatives exemption).

**2024 review**: Directive (EU) 2024/790 (MiFID II amendments) and Regulation (EU) 2024/791 (MiFIR amendments) entered into force 28 March 2024. The MiFID II amendment transposition deadline is 29 September 2025. Key changes: payment for order flow ban; mandatory consolidated tape for bonds and equities; revised consolidated tape provider selection via ESMA; updated systematic internaliser provisions; equity transparency waiver reform; partial re-bundling of research for SMEs.

---

## Useful References

- EUR-Lex text: https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32014L0065
- MiFIR (companion regulation, CELEX 32014R0600): https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32014R0600
- ESMA Interactive Single Rulebook (MiFID II): https://www.esma.europa.eu/publications-and-data/interactive-single-rulebook/mifid-ii
- ESMA register of authorised investment firms: https://registers.esma.europa.eu/
- ESMA MiFID II review page: https://www.esma.europa.eu/trading/mifid-ii-and-mifir-review
- 2024 MiFID II amendment: Directive (EU) 2024/790 (OJ L, 28.3.2024)
- 2024 MiFIR amendment: Regulation (EU) 2024/791 (OJ L, 28.3.2024)
- EPRS briefing on MiFID II review: PE 733.546

---

## Related Brubru Guides

- `eu_financial_markets_mifid.md` -- overview guide covering MiFID II/MiFIR including the 2024 review changes and advocacy context
- `esma_and_financial_supervision.md` (if available) -- ESMA role as technical standard-setter and supervisor
- `emir.md` (if available) -- EMIR (Regulation 648/2012) governs OTC derivatives clearing and margining; directly referenced in MiFID II for commodity derivative clearing obligations
- `eu_capital_markets_union.md` (if available) -- Capital Markets Union initiative, within which MiFID II/MiFIR review sits
