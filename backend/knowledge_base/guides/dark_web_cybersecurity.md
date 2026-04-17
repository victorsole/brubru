# Dark Web and EU Cybersecurity Policy

## QUICK FACTS
- Topic: Dark web technology, criminal marketplaces, EU law enforcement response, cybersecurity policy intersection
- EPRS Blog briefing (15 April 2026): "Understanding the dark web" -- EPRS briefing on dark web technology (Tor, I2P), licit/illicit uses, EU regulatory response, law enforcement cooperation. Ref: EPRS_BLOG_understanding-the-dark-web
- Dark web definition: Network layer accessible only via anonymising software (Tor, I2P, Freenet); content not indexed by surface-web search engines
- Distinct from "deep web" (unindexed but not anonymised content like password-protected pages)
- Licit uses: whistleblowing (SecureDrop), journalism, privacy tools, censorship circumvention, legal marketplaces
- Illicit uses: drug markets, weapons, stolen data, malware-as-a-service, CSAM distribution, ransomware command-and-control
- EU relevant laws: Cybersecurity Act (Reg (EU) 2019/881), NIS 2 Directive (Dir (EU) 2022/2555), Cyber Resilience Act (Reg (EU) 2024/2847), CSAM Regulation proposal (2022/0155(COD)), UN Cybercrime Convention
- Lead DG: DG CNECT (digital), DG HOME (law enforcement)
- Key EU bodies: ENISA (cybersecurity agency), Europol EC3 (European Cybercrime Centre), CERT-EU, EU Internet Organised Crime Threat Assessment (IOCTA)
- Estimated illicit dark web economy: EUR 1-3 billion/year turnover in EU-linked darknet markets (Europol estimate)
- 2025 major takedowns: Archetyp Market, Kraken Market (multi-country Europol operations)

## Dark Web Architecture

### Tor (The Onion Router)
- Most widely used anonymisation network
- Traffic routed through 3 random relays; each relay decrypts one layer
- Hidden services use .onion addresses
- Tor Project: non-profit based in Seattle, USA
- Funding historically from US State Department DRL + NDI (criticised); now diversified

### I2P (Invisible Internet Project)
- Decentralised alternative to Tor
- "Garlic routing" bundles multiple messages
- Preferred for peer-to-peer and longer sessions

### Freenet
- Censorship-resistant distributed datastore
- Content hosted by participating nodes

## Criminal Activity Categories

### Drug Markets (40-50% of illicit darknet trade)
- Cocaine, cannabis, synthetic drugs, pharmaceuticals
- 2023-2025 takedowns: Hydra (2022), Archetyp Market (May 2024 + June 2025), Kraken (June 2025)
- Payment primarily Bitcoin, Monero (privacy coin)

### Stolen Data Markets
- Personal data, credit card dumps, credentials
- GDPR breach notifications + darknet monitoring tools (SpyCloud, Recorded Future)
- Identity theft victim rate: ~3% of EU adults/year

### Ransomware-as-a-Service (RaaS)
- Affiliates rent ransomware; operators take % cut
- Major groups: LockBit (disrupted 2024), BlackCat/ALPHV, Cl0p, BianLian
- 2024-2025 surge in EU hospital attacks

### CSAM (Child Sexual Abuse Material)
- Covered by `csam_regulation_online` guide
- Europol + INHOPE cooperation; Internet Watch Foundation sharing
- Proposed CSAM Regulation (2022/0155(COD)) would require platforms to detect

### Weapons, Counterfeits, Document Fraud
- Smaller share; EU Firearms Directive intersection
- Counterfeit COVID certificates peak 2021-2022

## EU Response Instruments

### 1. Cybersecurity Act (Reg (EU) 2019/881)
- ENISA permanent mandate
- EU-wide cybersecurity certification framework
- See `cybersecurity_act` guide

### 2. NIS 2 Directive (Dir (EU) 2022/2555)
- Cybersecurity obligations for essential and important entities
- Transposition deadline: 17 October 2024 (many MS late)
- Scope: energy, transport, banking, health, digital infrastructure, public administration, space, food, manufacturing, waste, research
- National CSIRTs cooperation

### 3. Cyber Resilience Act (Reg (EU) 2024/2847)
- Adopted 23 October 2024
- CE marking for cybersecurity of digital products
- Applicable from 11 December 2027

### 4. Cyber Solidarity Act (Reg (EU) 2025/38)
- Adopted January 2025
- European Cyber Shield (SOCs), Cybersecurity Emergency Mechanism, Cybersecurity Review Mechanism
- EUR 1.1 billion budget

### 5. Anti-Money Laundering (AML) Package
- AMLR (Reg (EU) 2024/1624) crypto-asset integration
- Travel Rule for crypto transfers (Reg (EU) 2023/1113)
- AMLA (EU Authority) operational 2025
- See `eu_anti_money_laundering` guide

### 6. MiCA Regulation
- Reg (EU) 2023/1114 on crypto-asset markets
- CASP (crypto-asset service providers) licensing
- KYC/CDD obligations
- See `financial_supervision_eba` for DORA/MiCA context

### 7. UN Cybercrime Convention
- Convention against cybercrime adopted UN GA December 2024
- EU signed December 2024; Council Decision on signature under way
- Concerns: human rights safeguards, scope creep
- See `un_cybercrime_convention` guide

## Law Enforcement Cooperation

### Europol EC3 (European Cybercrime Centre)
- Established 2013, based in The Hague
- Operational support to MS
- **EMPACT Cybercrime**: 2022-2025 priority area continuing 2026-2029
- **Internet Referral Unit (EU IRU)**: terrorist content + extremist content online

### EMPACT Policy Cycle
- European Multidisciplinary Platform Against Criminal Threats
- 15 priority crime areas including cybercrime, online CSAM, drug trafficking
- 2022-2025 priorities extended to 2026-2029

### J-CAT (Joint Cybercrime Action Taskforce)
- Europol-led taskforce
- Permanent liaison with FBI, NCA (UK), AFP (Australia)
- High-value darknet market takedowns coordinated here

## Legitimate Uses — Not All Dark Web is Criminal

Important context the EPRS briefing stresses:
- **Whistleblowing**: SecureDrop platforms for journalists (New York Times, Guardian, Reuters)
- **Journalism**: protection of sources in authoritarian regimes
- **Human rights**: activist communication in Iran, Russia, China
- **Privacy**: users seeking anonymity from advertisers, ISPs
- **Legal commerce**: some vendors of privacy tools, second-hand goods

EU policy tension: fighting illicit dark web use while protecting fundamental rights (Article 7 CFR privacy, Article 11 CFR expression).

## Tor Funding and Geopolitics

- 80% of Tor Project funding historically from US government (State Department, DARPA, BBG/USAGM)
- Diversification since 2020: donations, Mozilla, Open Technology Fund
- Geopolitical sensitivity: Russia, Iran, China block Tor; EU does not but regulates operator cooperation

## Emerging Challenges

### AI-Generated CSAM
- Covered by `csam_regulation_online`; generative AI enables mass production
- EU response: AI Act + CSAM Regulation synergy

### Ransomware Payment Ban Debate
- UK banning public sector payments (2025-2026)
- EU: no blanket ban; payment-reporting obligation in proposed Cyber Solidarity 2.0

### Quantum-Resistant Encryption
- NIST post-quantum standards (ML-KEM, ML-DSA) adopted August 2024
- ENISA post-quantum transition guidance 2025-2027
- Threat: "harvest now, decrypt later" attacks

### Crypto-Asset Regulation
- MiCA privacy coin restrictions (Monero, Zcash)
- AMLA darknet market transaction monitoring

## Related Brubru Guides
- `cybersecurity_act` -- Cybersecurity Act and ENISA
- `csam_regulation_online` -- Child safety online
- `eu_anti_money_laundering` -- AMLR/AMLAR/AMLA
- `financial_supervision_eba` -- DORA + MiCA
- `un_cybercrime_convention` -- UN convention
- `ai_act_regulation` -- AI Act scope
- `gdpr_data_protection` -- personal data on darknet breach markets

## Sources

- EPRS blog briefing EPRS_BLOG_understanding-the-dark-web (15 April 2026): "Understanding the dark web"
- Europol IOCTA (Internet Organised Crime Threat Assessment) annual reports: https://www.europol.europa.eu/publications-events/main-reports/internet-organised-crime-threat-assessment-iocta-2024
- ENISA Threat Landscape 2025: https://www.enisa.europa.eu/publications/enisa-threat-landscape-2025
- NIS 2 Directive: https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32022L2555
- Cyber Resilience Act: https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32024R2847
- Cyber Solidarity Act: https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32025R0038
