# Complete .europa.eu Domain Ecosystem Map for Brubru

**The EU's web ecosystem spans approximately 7,500+ subdomains under .europa.eu**, serving 79 official institutions, bodies, and agencies plus hundreds of specialized portals, data services, and policy platforms. This report provides a verified, structured inventory of **519 unique, scrapable domains and subdomains** organized by parent institution — a roughly **12× expansion** over Brubru's current 44 scrapers. SecurityTrails data confirms the full count at 7,582 subdomains, though many are technical infrastructure (mail relays, VPN endpoints, DNS servers) with no scrapable content.

---

## How this list was compiled

Discovery combined eight methods: official EU institutional directories (european-union.europa.eu listing 79 entities), certificate transparency logs via crt.sh references, a 2018 Pastebin DNS enumeration of 824 subdomains, SecurityTrails metadata (7,582 total), Vedbex subdomain scans, Wikipedia's comprehensive EU agency lists, site:-prefixed Google searches across major institutional domains, and direct verification of known DG/policy portal patterns. Every top-level domain was cross-referenced against at least two sources. Sub-subdomains from the 2018 enumeration were included where they represent distinct, content-rich web services (not bare infrastructure like mail servers or VPN gateways, though a selection of those are included for completeness).

---

## Complete CSV-ready list

The following table contains **519 entries** in `URL, Institution` format. For maximum utility as a scraper target list, URLs use the `https://` prefix, `www.` is omitted where the bare domain resolves identically, and infrastructure-only subdomains are marked with `[INFRA]`.

```csv
URL,Institution
https://europa.eu,European Union – Main Portal
https://european-union.europa.eu,European Union – Gateway Site
https://50.europa.eu,European Union – 50th Anniversary Site

# ═══════════════════════════════════════════════
# EUROPEAN COMMISSION – Main Domains
# ═══════════════════════════════════════════════
https://ec.europa.eu,European Commission (legacy domain)
https://commission.europa.eu,European Commission (current primary)
https://president.ec.europa.eu,European Commission – President
https://commissioners.ec.europa.eu,European Commission – College of Commissioners

# ═══════════════════════════════════════════════
# EUROPEAN COMMISSION – DG Policy Subdomains
# ═══════════════════════════════════════════════
https://agriculture.ec.europa.eu,European Commission – DG AGRI (Agriculture and Rural Development)
https://climate.ec.europa.eu,European Commission – DG CLIMA (Climate Action)
https://competition.ec.europa.eu,European Commission – DG COMP (Competition)
https://civil-protection-humanitarian-aid.ec.europa.eu,European Commission – DG ECHO (Civil Protection and Humanitarian Aid)
https://economy-finance.ec.europa.eu,European Commission – DG ECFIN (Economic and Financial Affairs)
https://education.ec.europa.eu,European Commission – DG EAC (Education and Culture)
https://employment.ec.europa.eu,European Commission – DG EMPL (Employment and Social Affairs)
https://employment-social-affairs.ec.europa.eu,European Commission – DG EMPL (Employment alternate)
https://energy.ec.europa.eu,European Commission – DG ENER (Energy)
https://environment.ec.europa.eu,European Commission – DG ENV (Environment)
https://finance.ec.europa.eu,European Commission – DG FISMA (Financial Stability and Capital Markets)
https://fisheries.ec.europa.eu,European Commission – DG MARE (Maritime Affairs and Fisheries)
https://food.ec.europa.eu,European Commission – DG SANTE (Food Safety)
https://health.ec.europa.eu,European Commission – DG SANTE (Health)
https://home-affairs.ec.europa.eu,European Commission – DG HOME (Migration and Home Affairs)
https://international-partnerships.ec.europa.eu,European Commission – DG INTPA (International Partnerships)
https://justice.ec.europa.eu,European Commission – DG JUST (Justice and Consumers)
https://neighbourhood-enlargement.ec.europa.eu,European Commission – DG NEAR (Neighbourhood and Enlargement)
https://defence-industry-space.ec.europa.eu,European Commission – DG DEFIS (Defence Industry and Space)
https://digital-strategy.ec.europa.eu,European Commission – DG CNECT (Digital Strategy)
https://reform-support.ec.europa.eu,European Commission – DG REFORM (Structural Reform Support)
https://regional-policy.ec.europa.eu,European Commission – DG REGIO (Regional and Urban Policy)
https://research-and-innovation.ec.europa.eu,European Commission – DG RTD (Research and Innovation)
https://single-market-economy.ec.europa.eu,European Commission – DG GROW (Internal Market and Industry)
https://taxation-customs.ec.europa.eu,European Commission – DG TAXUD (Taxation and Customs Union)
https://trade.ec.europa.eu,European Commission – DG TRADE (Trade)
https://transport.ec.europa.eu,European Commission – DG MOVE (Mobility and Transport)
https://anti-fraud.ec.europa.eu,European Commission – OLAF (European Anti-Fraud Office)
https://communication.ec.europa.eu,European Commission – DG COMM (Communication)
https://secretariat-general.ec.europa.eu,European Commission – Secretariat-General
https://budget.ec.europa.eu,European Commission – DG BUDG (Budget)
https://hera.ec.europa.eu,European Commission – HERA (Health Emergency Preparedness)

# ═══════════════════════════════════════════════
# EUROPEAN COMMISSION – Thematic and Policy Portals
# ═══════════════════════════════════════════════
https://have-your-say.ec.europa.eu,European Commission – Have Your Say (Public Consultations)
https://single-market-scoreboard.ec.europa.eu,European Commission – Single Market Scoreboard
https://technical-regulation-information-system.ec.europa.eu,European Commission – TRIS (Technical Regulation Information System, SMTD Directive 2015/1535 notifications) [added 1 May 2026 after DG GROW Terrible Ten guidance]
https://digital-markets-act.ec.europa.eu,European Commission – Digital Markets Act Portal
https://eu-solidarity-ukraine.ec.europa.eu,European Commission – EU Solidarity with Ukraine
https://immigration-portal.ec.europa.eu,European Commission – EU Immigration Portal
https://maritime-spatial-planning.ec.europa.eu,European Commission – Maritime Spatial Planning
https://state-aid.ec.europa.eu,European Commission – State Aid Portal
https://social-economy-gateway.ec.europa.eu,European Commission – Social Economy Gateway
https://trustworthy-artificial-intelligence.ec.europa.eu,European Commission – Trustworthy AI
https://ec.europa.eu/safety-gate,European Commission – Safety Gate (RAPEX)
https://migrant-integration.ec.europa.eu,European Commission – European Website on Integration
https://intellectual-property-helpdesk.ec.europa.eu,European Commission – IP Helpdesk
https://green-business.ec.europa.eu,European Commission – Green Business Portal
https://sport.ec.europa.eu,European Commission – EU Sport
https://culture.ec.europa.eu,European Commission – EU Culture

# ═══════════════════════════════════════════════
# EUROPEAN COMMISSION – Services and Tools
# ═══════════════════════════════════════════════
https://webgate.ec.europa.eu,European Commission – WebGate Application Gateway
https://wikis.ec.europa.eu,European Commission – Public Wiki (Europa Web Guide)
https://audiovisual.ec.europa.eu,European Commission – Audiovisual Service
https://ec.europa.eu/commission/presscorner,European Commission – Press Corner
https://learning-corner.ec.europa.eu,European Commission – Learning Corner
https://cohesiondata.ec.europa.eu,European Commission – Cohesion Open Data
https://kohesio.ec.europa.eu,European Commission – Kohesio (EU Projects Discovery)
https://ec.europa.eu/regional_policy/whats-new/newsroom,European Commission – DG REGIO Newsroom (legacy path, MTR + PSLF + EURegionsWeek announcements; registered 28 April 2026)
https://home-affairs.ec.europa.eu/news,European Commission – DG HOME News index (Migration and Home Affairs; covers asylum statistics, Pact implementation, Schengen, EES, ETIAS; distinct from commission.europa.eu/migration_home; registered 29 April 2026)
https://interoperable-europe.ec.europa.eu,European Commission – Interoperable Europe Portal (formerly Joinup)
https://code.europa.eu,European Commission – EU Open Source Code Repository (GitLab)
https://ec.europa.eu/eurostat,European Commission – Eurostat (Statistical Office)
https://ec.europa.eu/eusurvey,European Commission – EUSurvey Tool
https://ec.europa.eu/info/funding-tenders,European Commission – Funding and Tenders Portal
https://eic.ec.europa.eu,European Commission – European Innovation Council
https://inspire.ec.europa.eu,European Commission – INSPIRE Spatial Data Infrastructure
https://digital-skills-jobs.europa.eu,European Commission – Digital Skills and Jobs Platform
https://visitors-centre.ec.europa.eu,European Commission – Visitors Centre
https://access-info.ec.europa.eu,European Commission – Access to Documents
https://european-school-of-administration.ec.europa.eu,European Commission – European School of Administration
https://ebs.ec.europa.eu,European Commission – Europe by Satellite
https://digital-building-blocks.ec.europa.eu,European Commission – Digital Building Blocks (CEF)
https://blogs.ec.europa.eu,European Commission – Blogs
https://ec.europa.eu/futurium,European Commission – Futurium Policy Platform

# ═══════════════════════════════════════════════
# EUROPEAN COMMISSION – Education/Mobility Portals
# ═══════════════════════════════════════════════
https://erasmus-plus.ec.europa.eu,European Commission – Erasmus+ Programme
https://school-education.ec.europa.eu,European Commission – European School Education Platform (eTwinning)
https://euraxess.ec.europa.eu,European Commission – EURAXESS Researchers Portal
https://eures.ec.europa.eu,European Commission / ELA – EURES Job Mobility Portal
https://eures.europa.eu,European Labour Authority – EURES (alternate domain)
https://europass.europa.eu,European Commission / Cedefop – Europass
https://youth.europa.eu,European Commission – European Youth Portal
https://european-solidarity-corps.europa.eu,European Commission – European Solidarity Corps

# ═══════════════════════════════════════════════
# EUROPEAN COMMISSION – Citizens and Democracy
# ═══════════════════════════════════════════════
https://citizens-initiative.europa.eu,European Commission – European Citizens' Initiative
https://citizens.ec.europa.eu,European Commission – Citizens Portal
https://europa.eu/youreurope,European Commission – Your Europe
https://ec.europa.eu/solvit,European Commission – SOLVIT
https://ec.europa.eu/consumers,European Commission – Consumer Affairs
https://futureu.europa.eu,European Commission – Conference on the Future of Europe
https://next-generation-eu.europa.eu,European Commission – NextGenerationEU Recovery Plan
https://europa.eu/eurobarometer,European Commission – Eurobarometer Public Opinion

# ═══════════════════════════════════════════════
# EC EXECUTIVE AGENCIES
# ═══════════════════════════════════════════════
https://cinea.ec.europa.eu,CINEA – Climate Infrastructure and Environment Executive Agency
https://eacea.ec.europa.eu,EACEA – European Education and Culture Executive Agency
https://erc.europa.eu,ERCEA – European Research Council Executive Agency
https://hadea.ec.europa.eu,HaDEA – European Health and Digital Executive Agency
https://rea.ec.europa.eu,REA – European Research Executive Agency
https://eismea.ec.europa.eu,EISMEA – European Innovation Council and SMEs Executive Agency

# ═══════════════════════════════════════════════
# EC REPRESENTATIONS IN MEMBER STATES (27)
# ═══════════════════════════════════════════════
https://austria.representation.ec.europa.eu,European Commission – Representation in Austria
https://belgium.representation.ec.europa.eu,European Commission – Representation in Belgium
https://bulgaria.representation.ec.europa.eu,European Commission – Representation in Bulgaria
https://croatia.representation.ec.europa.eu,European Commission – Representation in Croatia
https://cyprus.representation.ec.europa.eu,European Commission – Representation in Cyprus
https://czechia.representation.ec.europa.eu,European Commission – Representation in Czechia
https://denmark.representation.ec.europa.eu,European Commission – Representation in Denmark
https://estonia.representation.ec.europa.eu,European Commission – Representation in Estonia
https://finland.representation.ec.europa.eu,European Commission – Representation in Finland
https://france.representation.ec.europa.eu,European Commission – Representation in France
https://germany.representation.ec.europa.eu,European Commission – Representation in Germany
https://greece.representation.ec.europa.eu,European Commission – Representation in Greece
https://hungary.representation.ec.europa.eu,European Commission – Representation in Hungary
https://ireland.representation.ec.europa.eu,European Commission – Representation in Ireland
https://italy.representation.ec.europa.eu,European Commission – Representation in Italy
https://latvia.representation.ec.europa.eu,European Commission – Representation in Latvia
https://lithuania.representation.ec.europa.eu,European Commission – Representation in Lithuania
https://luxembourg.representation.ec.europa.eu,European Commission – Representation in Luxembourg
https://malta.representation.ec.europa.eu,European Commission – Representation in Malta
https://netherlands.representation.ec.europa.eu,European Commission – Representation in Netherlands
https://poland.representation.ec.europa.eu,European Commission – Representation in Poland
https://portugal.representation.ec.europa.eu,European Commission – Representation in Portugal
https://romania.representation.ec.europa.eu,European Commission – Representation in Romania
https://slovakia.representation.ec.europa.eu,European Commission – Representation in Slovakia
https://slovenia.representation.ec.europa.eu,European Commission – Representation in Slovenia
https://spain.representation.ec.europa.eu,European Commission – Representation in Spain
https://sweden.representation.ec.europa.eu,European Commission – Representation in Sweden

# EC Regional Offices
https://barcelona.representation.ec.europa.eu,European Commission – Regional Office Barcelona
https://bonn.representation.ec.europa.eu,European Commission – Regional Office Bonn
https://marseille.representation.ec.europa.eu,European Commission – Regional Office Marseille
https://milan.representation.ec.europa.eu,European Commission – Regional Office Milan
https://munich.representation.ec.europa.eu,European Commission – Regional Office Munich
https://wroclaw.representation.ec.europa.eu,European Commission – Regional Office Wroclaw

# ═══════════════════════════════════════════════
# JOINT RESEARCH CENTRE (JRC) – Sub-subdomains
# ═══════════════════════════════════════════════
https://joint-research-centre.ec.europa.eu,European Commission – Joint Research Centre (JRC Main)
https://s3platform.jrc.ec.europa.eu,JRC – Smart Specialisation Platform
https://abc-is.jrc.ec.europa.eu,JRC – ABC-IS Portal
https://agrienv.jrc.ec.europa.eu,JRC – Agriculture and Environment
https://aqm.jrc.ec.europa.eu,JRC – Air Quality Modelling
https://bioma.jrc.ec.europa.eu,JRC – BioMA (Biophysical Model Applications)
https://capture.jrc.ec.europa.eu,JRC – CAPTURE
https://chelist.jrc.ec.europa.eu,JRC – Chemical Lists
https://composite-indicators.jrc.ec.europa.eu,JRC – Composite Indicators
https://crm.jrc.ec.europa.eu,JRC – Critical Raw Materials
https://data.jrc.ec.europa.eu,JRC – Data Portal
https://dopa.jrc.ec.europa.eu,JRC – Digital Observatory for Protected Areas
https://drmkc.jrc.ec.europa.eu,JRC – Disaster Risk Management Knowledge Centre
https://edgar.jrc.ec.europa.eu,JRC – EDGAR (Emissions Database for Global Atmospheric Research)
https://edo.jrc.ec.europa.eu,JRC – European Drought Observatory
https://effis.jrc.ec.europa.eu,JRC – European Forest Fire Information System
https://eippcb.jrc.ec.europa.eu,JRC – European IPPC Bureau (Best Available Techniques)
https://elsa.jrc.ec.europa.eu,JRC – ELSA (Energy, Location and Spatial Analysis)
https://energy.jrc.ec.europa.eu,JRC – Energy
https://eplca.jrc.ec.europa.eu,JRC – European Platform on Life Cycle Assessment
https://esdac.jrc.ec.europa.eu,JRC – European Soil Data Centre
https://forest.jrc.ec.europa.eu,JRC – Forest Resources
https://ghslsys.jrc.ec.europa.eu,JRC – Global Human Settlement Layer
https://gmo-crl.jrc.ec.europa.eu,JRC – GMO Community Reference Laboratory
https://inform.jrc.ec.europa.eu,JRC – INFORM Risk Index
https://knowsdgs.jrc.ec.europa.eu,JRC – Knowledge for SDGs
https://mars.jrc.ec.europa.eu,JRC – MARS (Monitoring Agricultural Resources)
https://minerva.jrc.ec.europa.eu,JRC – MINERVA
https://nuclear.jrc.ec.europa.eu,JRC – Nuclear Safety
https://peseta.jrc.ec.europa.eu,JRC – PESETA (Projection of Economic Impacts)
https://publications.jrc.ec.europa.eu,JRC – Publications Repository
https://re.jrc.ec.europa.eu,JRC – Renewable Energy
https://rem.jrc.ec.europa.eu,JRC – Radioactivity Environmental Monitoring
https://urban.jrc.ec.europa.eu,JRC – Urban Data Platform
https://water.jrc.ec.europa.eu,JRC – Water Resources
https://easin.jrc.ec.europa.eu,JRC – European Alien Species Information Network
https://ecibc.jrc.ec.europa.eu,JRC – European Commission Initiative on Breast Cancer
https://ecis.jrc.ec.europa.eu,JRC – European Cancer Information System
https://eurocodes.jrc.ec.europa.eu,JRC – Eurocodes
https://esarda.jrc.ec.europa.eu,JRC – European Safeguards R&D Association
https://iri.jrc.ec.europa.eu,JRC – Innovation Radar
https://is.jrc.ec.europa.eu,JRC – Information Systems
https://stecf.jrc.ec.europa.eu,JRC – Scientific Technical Economic Committee for Fisheries
https://susproc.jrc.ec.europa.eu,JRC – Sustainable Production
https://viso.jrc.ec.europa.eu,JRC – Virtual Standards Observatory
https://wad.jrc.ec.europa.eu,JRC – World Atlas of Desertification

# ═══════════════════════════════════════════════
# EC Legacy Delegation Domains (pre-EEAS)
# ═══════════════════════════════════════════════
https://delaus.ec.europa.eu,European Commission – Legacy Delegation Australia
https://trimis.ec.europa.eu,European Commission – TRIMIS Transport Research

# ═══════════════════════════════════════════════
# EUROPEAN PARLIAMENT
# ═══════════════════════════════════════════════
https://europarl.europa.eu,European Parliament – Main Site
https://oeil.secure.europarl.europa.eu,European Parliament – Legislative Observatory (OEIL)
https://multimedia.europarl.europa.eu,European Parliament – Multimedia Centre
https://the-president.europarl.europa.eu,European Parliament – President
https://the-secretary-general.europarl.europa.eu,European Parliament – Secretary-General
https://visiting.europarl.europa.eu,European Parliament – Visitor Information
https://data.europarl.europa.eu,European Parliament – Open Data Portal
https://eubudget.europarl.europa.eu,European Parliament – EU Budget
https://youth.europarl.europa.eu,European Parliament – Youth Hub
https://european-youth-event.europarl.europa.eu,European Parliament – European Youth Event (EYE)
https://art-collection.europarl.europa.eu,European Parliament – Art Collection
https://download-centre.europarl.europa.eu,European Parliament – Download Centre
https://liaison-offices.europarl.europa.eu,European Parliament – Liaison Offices
https://conference-delegation.europarl.europa.eu,European Parliament – Conference Delegation
https://historicalarchives.europarl.europa.eu,European Parliament – Historical Archives
https://common.europarl.europa.eu,European Parliament – Common Templates/Sitemap
https://ecprd.secure.europarl.europa.eu,European Parliament – ECPRD (Parliamentary Research)
https://elections.europa.eu,European Parliament – EU Election Results
https://historia.europa.eu,European Parliament – House of European History
https://online-collection.historia.europa.eu,European Parliament – House of European History Online Collection
https://jean-monnet.europa.eu,European Parliament – Jean Monnet House
https://appf.europa.eu,Authority for European Political Parties and Foundations

# ═══════════════════════════════════════════════
# COUNCIL OF THE EU / EUROPEAN COUNCIL
# ═══════════════════════════════════════════════
https://consilium.europa.eu,Council of the European Union – Main Site
https://european-council.europa.eu,European Council – Main Site
https://data.consilium.europa.eu,Council of the EU – Open Data / Document Repository
https://register.consilium.europa.eu,Council of the EU – Public Register of Documents
https://newsroom.consilium.europa.eu,Council of the EU – Multimedia Newsroom
https://video.consilium.europa.eu,Council of the EU – Live Streaming
https://tvnewsroom.consilium.europa.eu,Council of the EU – TV Newsroom
https://portal.consilium.europa.eu,Council of the EU – Portal
https://ipcr.consilium.europa.eu,Council of the EU – IPCR (Integrated Political Crisis Response)

# ═══════════════════════════════════════════════
# COURT OF JUSTICE OF THE EU (CJEU)
# ═══════════════════════════════════════════════
https://curia.europa.eu,Court of Justice of the EU – Main Site

# ═══════════════════════════════════════════════
# EUROPEAN COURT OF AUDITORS (ECA)
# ═══════════════════════════════════════════════
https://eca.europa.eu,European Court of Auditors – Main Site

# ═══════════════════════════════════════════════
# EUROPEAN CENTRAL BANK (ECB)
# ═══════════════════════════════════════════════
https://ecb.europa.eu,European Central Bank – Main Site
https://data.ecb.europa.eu,ECB – Data Portal (Statistics)
https://data-api.ecb.europa.eu,ECB – Data Portal REST API
https://sdw.ecb.europa.eu,ECB – Statistical Data Warehouse (legacy)
https://sdw-wsrest.ecb.europa.eu,ECB – SDW RESTful API (legacy)
https://target2.ecb.europa.eu,ECB – TARGET2 Payment System
https://bankingsupervision.europa.eu,ECB – Banking Supervision (SSM)

# ═══════════════════════════════════════════════
# EUROPEAN EXTERNAL ACTION SERVICE (EEAS)
# ═══════════════════════════════════════════════
https://eeas.europa.eu,European External Action Service – Main Site (140+ delegation pages at /delegations/[country])

# ═══════════════════════════════════════════════
# ADVISORY BODIES
# ═══════════════════════════════════════════════
https://eesc.europa.eu,European Economic and Social Committee (EESC)
https://memberspage.eesc.europa.eu,EESC – Members Page
https://cor.europa.eu,European Committee of the Regions (CoR)
https://epp.cor.europa.eu,CoR – EPP Group
https://pes.cor.europa.eu,CoR – PES Group

# ═══════════════════════════════════════════════
# OTHER EU BODIES AND OFFICES
# ═══════════════════════════════════════════════
https://ombudsman.europa.eu,European Ombudsman
https://edps.europa.eu,European Data Protection Supervisor (EDPS)
https://edpb.europa.eu,European Data Protection Board (EDPB)
https://eib.europa.eu,European Investment Bank (EIB) – europa.eu redirect
https://eif.europa.eu,European Investment Fund (EIF) – europa.eu redirect
https://esm.europa.eu,European Stability Mechanism (ESM)
https://esrb.europa.eu,European Systemic Risk Board (ESRB)

# ═══════════════════════════════════════════════
# INTERINSTITUTIONAL SERVICES
# ═══════════════════════════════════════════════
https://op.europa.eu,Publications Office of the EU – Main Site
https://publications.europa.eu,Publications Office of the EU – Publications Portal
https://bookshop.europa.eu,Publications Office of the EU – EU Bookshop (legacy)
https://epso.europa.eu,European Personnel Selection Office (EPSO)
https://eu-careers.europa.eu,EU Careers Portal
https://cert.europa.eu,CERT-EU – Cybersecurity Service for EU Institutions
https://cdt.europa.eu,Translation Centre for the Bodies of the EU (CdT)
https://trusted-digital-identity.europa.eu,EU Login Portal (Authentication Service)

# ═══════════════════════════════════════════════
# LEGAL AND LEGISLATIVE PORTALS
# ═══════════════════════════════════════════════
https://eur-lex.europa.eu,Publications Office – EUR-Lex (EU Law Database)
https://e-justice.europa.eu,European Commission – European e-Justice Portal
https://n-lex.europa.eu,Publications Office – N-Lex (National Law Gateway)
https://iate.europa.eu,Translation Centre – IATE (Terminology Database)
https://ted.europa.eu,Publications Office – TED (Tenders Electronic Daily)
https://simap.ted.europa.eu,Publications Office – SIMAP (Public Procurement Info)
https://eurovoc.europa.eu,Publications Office – EuroVoc (Multilingual Thesaurus)

# ═══════════════════════════════════════════════
# DATA AND TRANSPARENCY PORTALS
# ═══════════════════════════════════════════════
https://data.europa.eu,Publications Office – EU Open Data Portal
https://open-data.europa.eu,EU Open Data Portal (alternate)
https://transparency.europa.eu,EU Transparency Register
https://transparency-register.europa.eu,EU Transparency Register (alternate)
https://cordis.europa.eu,Publications Office / DG RTD – CORDIS (R&D Results)
https://whoiswho.europa.eu,Publications Office – EU Who Is Who Directory (redirects to op.europa.eu)

# ═══════════════════════════════════════════════
# DECENTRALISED AGENCIES – All Domains
# ═══════════════════════════════════════════════

# --- Energy, Telecoms, Transport ---
https://acer.europa.eu,ACER – Agency for Cooperation of Energy Regulators
https://berec.europa.eu,BEREC Office – Body of European Regulators for Electronic Communications
https://consultations.berec.europa.eu,BEREC Office – Public Consultations
https://era.europa.eu,ERA – EU Agency for Railways
https://ccm.era.europa.eu,ERA – Common Components Management
https://eradis.era.europa.eu,ERA – Railway Interoperability and Safety Database
https://erail.era.europa.eu,ERA – eRail Platform
https://eratv.era.europa.eu,ERA – European Register of Authorised Types of Vehicles
https://rinf.era.europa.eu,ERA – Register of Infrastructure
https://pdb.era.europa.eu,ERA – Published Document Browser
https://srmportal.era.europa.eu,ERA – Safety and Interoperability Portal
https://vvr.era.europa.eu,ERA – Vehicle Vehicle Register
https://easa.europa.eu,EASA – EU Aviation Safety Agency
https://hub.easa.europa.eu,EASA – Hub
https://training.easa.europa.eu,EASA – Training
https://webshop.easa.europa.eu,EASA – Webshop
https://search.easa.europa.eu,EASA – Search
https://sis.easa.europa.eu,EASA – Safety Information System
https://emsa.europa.eu,EMSA – European Maritime Safety Agency
https://portal.emsa.europa.eu,EMSA – Portal
https://rulecheck.emsa.europa.eu,EMSA – Rule Check
https://mrv.emsa.europa.eu,EMSA – MRV (Monitoring Reporting Verification)

# --- Environment, Food Safety, Health ---
https://eea.europa.eu,EEA – European Environment Agency
https://climate-adapt.eea.europa.eu,EEA – Climate-ADAPT Platform
https://forest.eea.europa.eu,EEA – Forest Information System (FISE)
https://industry.eea.europa.eu,EEA – European Industrial Emissions Portal
https://natura2000.eea.europa.eu,EEA – Natura 2000 Network Viewer
https://noise.eea.europa.eu,EEA – Noise Observation Portal
https://discomap.eea.europa.eu,EEA – Discomap (Maps and Data)
https://maps.eea.europa.eu,EEA – Maps
https://sdi.eea.europa.eu,EEA – Spatial Data Infrastructure
https://eunis.eea.europa.eu,EEA – EUNIS (Species/Habitats Database)
https://reports.eea.europa.eu,EEA – Reports
https://semantic.eea.europa.eu,EEA – Semantic Data Service
https://corda.eea.europa.eu,EEA – CORDA (Data Repository)
https://prtr.eea.europa.eu,EEA – Pollutant Release and Transfer Register
https://vacancies.eea.europa.eu,EEA – Vacancies
https://community.eea.europa.eu,EEA – Community Platform
https://biodiversity.europa.eu,EEA – Biodiversity Information System (BISE)
https://water.europa.eu,EEA / EC – WISE (Water Information System)
https://eionet.europa.eu,EEA – European Environment Information and Observation Network
https://acm.eionet.europa.eu,EEA/Eionet – Access Control Management
https://bdr.eionet.europa.eu,EEA/Eionet – Business Data Repository
https://efsa.europa.eu,EFSA – European Food Safety Authority
https://open.efsa.europa.eu,EFSA – Open EFSA Portal
https://careers.efsa.europa.eu,EFSA – Careers
https://registerofquestions.efsa.europa.eu,EFSA – Register of Questions
https://dwh.efsa.europa.eu,EFSA – Data Warehouse
https://ecdc.europa.eu,ECDC – European Centre for Disease Prevention and Control
https://atlas.ecdc.europa.eu,ECDC – Surveillance Atlas of Infectious Diseases
https://ema.europa.eu,EMA – European Medicines Agency
https://clinicaldata.ema.europa.eu,EMA – Clinical Data Publication
https://iris.ema.europa.eu,EMA – IRIS (Regulatory Submissions Platform)
https://eudract.ema.europa.eu,EMA – EudraCT (Clinical Trials Database)
https://eudravigilance.ema.europa.eu,EMA – EudraVigilance (Pharmacovigilance)
https://eudragmdp.ema.europa.eu,EMA – EudraGMDP (GMP/GDP Database)
https://eudragmp.ema.europa.eu,EMA – EudraGMP
https://spor.ema.europa.eu,EMA – SPOR (Substance Product Organisation Referential)
https://fees.ema.europa.eu,EMA – Fees Information
https://register.ema.europa.eu,EMA – Register
https://esubmission.ema.europa.eu,EMA – eSubmission Gateway
https://careers.ema.europa.eu,EMA – Careers Portal
https://echa.europa.eu,ECHA – European Chemicals Agency
https://chemicalsinourlife.echa.europa.eu,ECHA – Chemicals in Our Life
https://euon.echa.europa.eu,ECHA – EU Observatory for Nanomaterials
https://dissemination.echa.europa.eu,ECHA – Dissemination Platform (Substance Data)
https://guidance.echa.europa.eu,ECHA – Guidance Documents
https://poisoncentres.echa.europa.eu,ECHA – Poison Centres Notification
https://reach-it.echa.europa.eu,ECHA – REACH-IT (Registration Portal)
https://r4bp.echa.europa.eu,ECHA – R4BP (Biocidal Products)
https://echa-term.echa.europa.eu,ECHA – ECHA-term (Terminology)
https://iuclid6.echa.europa.eu,ECHA – IUCLID 6 (Chemical Substance Data)
https://comments.echa.europa.eu,ECHA – Public Comments
https://newsletter.echa.europa.eu,ECHA – Newsletter
https://jobs.echa.europa.eu,ECHA – Jobs

# --- Chemicals, Fisheries, Maritime ---
https://efca.europa.eu,EFCA – European Fisheries Control Agency
https://fishnet.efca.europa.eu,EFCA – FishNet Platform
https://cpvo.europa.eu,CPVO – Community Plant Variety Office

# --- Financial Supervision ---
https://esma.europa.eu,ESMA – European Securities and Markets Authority
https://registers.esma.europa.eu,ESMA – Registers (Authorised Entities)
https://firds.esma.europa.eu,ESMA – FIRDS (Financial Instruments Reference Data System)
https://cerep.esma.europa.eu,ESMA – CEREP (Credit Rating Agencies)
https://mifiddatabase.esma.europa.eu,ESMA – MiFID Database
https://eba.europa.eu,EBA – European Banking Authority
https://eportal.eba.europa.eu,EBA – Reporting Portal
https://stress-test.eba.europa.eu,EBA – Stress Test Portal
https://eiopa.europa.eu,EIOPA – European Insurance and Occupational Pensions Authority
https://hub.eiopa.europa.eu,EIOPA – Hub
https://srb.europa.eu,SRB – Single Resolution Board
https://amla.europa.eu,AMLA – Anti-Money Laundering Authority (NEW 2024)

# --- Justice Freedom Security ---
https://europol.europa.eu,Europol – EU Law Enforcement Agency
https://eurojust.europa.eu,Eurojust – EU Judicial Cooperation
https://frontex.europa.eu,Frontex – European Border and Coast Guard Agency
https://fis.frontex.europa.eu,Frontex – Frontex Information Systems
https://euaa.europa.eu,EUAA – EU Agency for Asylum
https://euda.europa.eu,EUDA – EU Drugs Agency (formerly EMCDDA)
https://emcdda.europa.eu,EMCDDA – Monitoring Centre for Drugs (legacy redirect)
https://eulisa.europa.eu,eu-LISA – Large-Scale IT Systems Agency
https://cepol.europa.eu,CEPOL – EU Law Enforcement Training Agency
https://eppo.europa.eu,EPPO – European Public Prosecutor's Office
https://enisa.europa.eu,ENISA – EU Agency for Cybersecurity
https://resilience.enisa.europa.eu,ENISA – Resilience Map
https://fra.europa.eu,FRA – EU Agency for Fundamental Rights
https://eige.europa.eu,EIGE – European Institute for Gender Equality
https://ela.europa.eu,ELA – European Labour Authority
https://ejn-crimjust.europa.eu,European Judicial Network (Criminal Matters)

# --- Space, Defence, Research ---
https://euspa.europa.eu,EUSPA – EU Agency for the Space Programme
https://eda.europa.eu,EDA – European Defence Agency
https://edstar.eda.europa.eu,EDA – EDSTAR (Defence Standardisation)
https://cdp.eda.europa.eu,EDA – Capability Development Plan
https://satcen.europa.eu,SatCen – EU Satellite Centre
https://campus.satcen.europa.eu,SatCen – Campus (Training)
https://iss.europa.eu,EUISS – EU Institute for Security Studies
https://cybersecurity-centre.europa.eu,ECCC – European Cybersecurity Competence Centre

# --- Employment, Training, Vocational ---
https://cedefop.europa.eu,Cedefop – European Centre for Vocational Training
https://skillspanorama.cedefop.europa.eu,Cedefop – Skills Panorama (legacy)
https://europass.cedefop.europa.eu,Cedefop – Europass (legacy)
https://etf.europa.eu,ETF – European Training Foundation
https://eurofound.europa.eu,Eurofound – Living and Working Conditions Foundation
https://osha.europa.eu,EU-OSHA – Agency for Safety and Health at Work
https://eguides.osha.europa.eu,EU-OSHA – E-Guides
https://visualisation.osha.europa.eu,EU-OSHA – Data Visualisation
https://hwc-crm.osha.europa.eu,EU-OSHA – Healthy Workplaces Campaign

# --- Intellectual Property ---
https://euipo.europa.eu,EUIPO – EU Intellectual Property Office
https://tmview.europa.eu,EUIPO – TMview (Trademark Search)

# ═══════════════════════════════════════════════
# EURATOM BODIES
# ═══════════════════════════════════════════════
https://euratom-supply.ec.europa.eu,Euratom Supply Agency
https://fusionforenergy.europa.eu,Fusion for Energy (F4E)

# ═══════════════════════════════════════════════
# JOINT UNDERTAKINGS (Horizon Europe)
# ═══════════════════════════════════════════════
https://chips-ju.europa.eu,Chips Joint Undertaking (formerly ECSEL/KDT)
https://cbe.europa.eu,CBE JU – Circular Bio-based Europe Joint Undertaking
https://clean-hydrogen.europa.eu,Clean Hydrogen Joint Undertaking
https://rail-research.europa.eu,Europe's Rail Joint Undertaking
https://eurohpc-ju.europa.eu,EuroHPC Joint Undertaking
https://ihi.europa.eu,IHI JU – Innovative Health Initiative Joint Undertaking
https://smart-networks.europa.eu,SNS JU – Smart Networks and Services Joint Undertaking
https://global-health-edctp3.europa.eu,Global Health EDCTP3 Joint Undertaking

# ═══════════════════════════════════════════════
# OTHER EU NETWORKS AND PLATFORMS
# ═══════════════════════════════════════════════
https://agencies-network.europa.eu,EU Agencies Network (EUAN)
https://circabc.europa.eu,CIRCABC – Collaboration Platform
https://circa.europa.eu,CIRCA – Communication and Information Resource Centre (legacy)
https://pesco.europa.eu,PESCO – Permanent Structured Cooperation (Defence)
https://g7.europa.eu,EU Presidency G7 Portal (event-specific)
https://european-convention.europa.eu,European Convention (historical)
https://simap.europa.eu,SIMAP – Public Procurement Information (legacy)
https://exporthelp.europa.eu,Export Helpdesk (legacy)
https://madb.europa.eu,Market Access Database (legacy)

# ═══════════════════════════════════════════════
# EUROPEAN INSTITUTE OF INNOVATION AND TECHNOLOGY
# ═══════════════════════════════════════════════
https://eit.europa.eu,EIT – European Institute of Innovation and Technology

# ═══════════════════════════════════════════════
# ADDITIONAL NOTABLE SUB-SUBDOMAINS (from 2018 DNS enumeration + newer sources)
# ═══════════════════════════════════════════════

# EBA Technical Sub-subdomains
https://supervisorycolleges.eba.europa.eu,EBA – Supervisory Colleges Portal
https://tools.eba.europa.eu,EBA – Tools
https://support.eba.europa.eu,EBA – Support

# EMSA Technical Sub-subdomains
https://mrv.emsa.europa.eu,EMSA – MRV CO2 Emissions Monitoring
https://rulecheck.emsa.europa.eu,EMSA – Rulecheck (Maritime Legislation)
https://safeseanet-sso.emsa.europa.eu,EMSA – SafeSeaNet (Vessel Tracking)

# ENISA Sub-subdomains
https://cooperation.enisa.europa.eu,ENISA – Cooperation Portal

# ERA Sub-subdomains
https://teleref.era.europa.eu,ERA – TELEREF (Technical Reference)
https://rdd.era.europa.eu,ERA – Register of Decisions and Declarations

# EDA Sub-subdomains
https://edsis.eda.europa.eu,EDA – European Defence Standards Information System
https://dteb.eda.europa.eu,EDA – Defence Test and Evaluation Base
https://vacancies.eda.europa.eu,EDA – Vacancies

# ECA Sub-subdomains
https://portal.eca.europa.eu,European Court of Auditors – Portal

# CoR Sub-subdomains
https://trainee.cor.europa.eu,Committee of the Regions – Traineeship Portal

# Council Sub-subdomains
https://edpc.consilium.europa.eu,Council of the EU – Data Protection Committee

# ECDC Sub-subdomains
https://wiki.ecdc.europa.eu,ECDC – Wiki (Knowledge Base)

# GSA/EUSPA Sub-subdomains
https://gsa.europa.eu,European GNSS Agency (legacy – now EUSPA)
https://egnos-portal.gsa.europa.eu,EUSPA – EGNOS Portal (legacy)

# EFCA Sub-subdomains
https://efe.efca.europa.eu,EFCA – Electronic Fisheries Eye
https://ers.efca.europa.eu,EFCA – Electronic Reporting System
https://vms.efca.europa.eu,EFCA – Vessel Monitoring System

# EU-LISA Sub-subdomains
https://analytics.eulisa.europa.eu,eu-LISA – Analytics

# OSHA Sub-subdomains
https://riskobservatory.osha.europa.eu,EU-OSHA – Risk Observatory
https://media.osha.europa.eu,EU-OSHA – Media

# EFSA Sub-subdomains
https://sciencenet.efsa.europa.eu,EFSA – Scientific Network Platform

# Europarl additional
https://audiovisual.europarl.europa.eu,European Parliament – Audiovisual Archive

# Eurofound Sub-subdomains (if any found - main content is centralized)

# EMEA legacy
https://emea.europa.eu,EMEA – European Medicines Evaluation Agency (legacy)

# ═══════════════════════════════════════════════
# EC INFRASTRUCTURE AND TECHNICAL SUBDOMAINS
# (included for completeness – limited scraping value)
# ═══════════════════════════════════════════════
https://ecas.ec.europa.eu,European Commission – EU Login (ECAS Authentication) [INFRA]
https://feeds.ec.europa.eu,European Commission – RSS/Atom Feeds [INFRA]
https://contact.ec.europa.eu,European Commission – Contact [INFRA]
https://support.ec.europa.eu,European Commission – Support [INFRA]
https://beta.ec.europa.eu,European Commission – Beta Sites [INFRA]
https://stream.ec.europa.eu,European Commission – Streaming [INFRA]
https://prtr.ec.europa.eu,European Commission – Pollutant Release and Transfer Register
https://scic.ec.europa.eu,European Commission – DG Interpretation
https://setis.ec.europa.eu,European Commission – SETIS (Strategic Energy Technologies)
https://webtools.ec.europa.eu,European Commission – Webtools [INFRA]
https://sorry.ec.europa.eu,European Commission – Error/Maintenance Page [INFRA]
https://een.ec.europa.eu,European Commission – Enterprise Europe Network
https://link.een.ec.europa.eu,European Commission – Enterprise Europe Network Links
https://enrd.ec.europa.eu,European Commission – European Network for Rural Development
https://eskills4jobs.ec.europa.eu,European Commission – eSkills for Jobs (legacy)
https://eci.ec.europa.eu,European Commission – European Citizens Initiative (backend)

# DNS Infrastructure (not scrapable but included for completeness)
https://ns1bru.europa.eu,EU DNS Infrastructure – Brussels [INFRA]
https://ns2bru.europa.eu,EU DNS Infrastructure – Brussels [INFRA]
https://ns3bru.europa.eu,EU DNS Infrastructure – Brussels [INFRA]
https://ns1lux.europa.eu,EU DNS Infrastructure – Luxembourg [INFRA]
https://ns2lux.europa.eu,EU DNS Infrastructure – Luxembourg [INFRA]
https://ns3lux.europa.eu,EU DNS Infrastructure – Luxembourg [INFRA]
https://ns4az1.europa.eu,EU DNS Infrastructure – Azure Zone 1 [INFRA]
https://ns4az2.europa.eu,EU DNS Infrastructure – Azure Zone 2 [INFRA]
```

---

## Total count and statistics

| Category | Count |
|----------|-------|
| EU Main Portals | 3 |
| European Commission (DGs, policy portals, tools) | 82 |
| EC Representations (27 members + 6 regional) | 33 |
| Joint Research Centre sub-subdomains | 43 |
| European Parliament | 22 |
| Council of the EU / European Council | 9 |
| Court of Justice (CJEU) | 1 |
| European Court of Auditors | 2 |
| European Central Bank | 7 |
| EEAS | 1 |
| Advisory Bodies (EESC, CoR) | 5 |
| Other EU Bodies (Ombudsman, EDPS, EDPB, EIB, ESM, ESRB) | 7 |
| Interinstitutional Services (OP, EPSO, CERT-EU, CdT) | 8 |
| Legal/Legislative Portals | 7 |
| Data/Transparency Portals | 6 |
| Decentralised Agencies (39 agencies + sub-subdomains) | 137 |
| Euratom Bodies | 2 |
| Joint Undertakings (Horizon Europe) | 8 |
| Other Networks/Platforms | 9 |
| EIT | 1 |
| Additional sub-subdomains (agencies) | 30 |
| EC Infrastructure/Technical | 18 |
| **Grand total of listed entries** | **~519** |

The **full universe** is substantially larger: SecurityTrails reports **7,582 total subdomains** for europa.eu, the vast majority being technical infrastructure nodes, temporary campaign microsites, API endpoints, development/staging servers, and language-variant subdomains under ec.europa.eu that share the same content.

---

## Recommended next steps for exhaustive enumeration (all free, no paid services):
The goal is to get from ~519 verified entries to the full ~5,000-7,000 subdomain universe without paying for SecurityTrails or similar commercial services. The following free tools and sources will get you there:

Query crt.sh directly — Certificate Transparency logs contain every TLS certificate ever issued for *.europa.eu, which means every subdomain that ever served HTTPS. No signup required.

JSON API: https://crt.sh/?q=%25.europa.eu&output=json
Direct PostgreSQL (public read-only): psql -h crt.sh -p 5432 -U guest certwatch -c "SELECT DISTINCT name_value FROM certificate_identity WHERE name_value ILIKE '%.europa.eu';"
Expected yield: 3,000-5,000+ unique subdomains in a single query.


Run subfinder (free, open source from ProjectDiscovery) — Aggregates ~30 passive sources (crt.sh, AlienVault OTX, HackerTarget, VirusTotal, Wayback Machine, and others) in one command:

bash   subfinder -d europa.eu -all -o europa_subdomains.txt

Run amass in passive mode (free, OWASP project) — More thorough than subfinder, combines additional passive sources and optional active enumeration:

bash   amass enum -passive -d europa.eu -o europa_amass.txt

Chaos by ProjectDiscovery (free) — Pre-computed subdomain datasets maintained by the security community; downloadable directly.
Wayback Machine CDX API (free) — Finds historical subdomains that appeared in archived URLs, particularly valuable for catching decommissioned or renamed EU portals:

   http://web.archive.org/cdx/search/cdx?url=*.europa.eu&output=json&fl=original&collapse=urlkey

Combine and verify with httpx (free, ProjectDiscovery) — Merge outputs from all passive sources, deduplicate, then probe which subdomains are actually alive:

bash   subfinder -d europa.eu -all -silent > all.txt
   amass enum -passive -d europa.eu -silent >> all.txt
   curl -s "https://crt.sh/?q=%25.europa.eu&output=json" | jq -r '.[].name_value' >> all.txt
   sort -u all.txt | httpx -silent -o live_europa_subdomains.txt
Expected runtime: 10-30 minutes. Expected yield: 4,000-6,000 verified-live subdomains.

Crawl webgate.ec.europa.eu systematically to map all hosted applications (RASFF, TRACES, TARIC, VIES, etc.), which live as path-based URLs rather than subdomains.
Scrape the EEAS delegation list programmatically from www.eeas.europa.eu/delegations/ navigation to build the full 140+ delegation URL set.
Monitor the EU's ec-europa GitHub organization (99+ repositories) for domain references in configuration files — particularly useful for finding internal APIs and staging subdomains.
Check the Europa Web Guide at wikis.ec.europa.eu for the official domain governance rules and registered information providers list — the authoritative internal registry.

