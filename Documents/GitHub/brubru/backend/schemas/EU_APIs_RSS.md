# EU Institutional Websites: API and RSS Integration Guide

European institutions have launched significant open data infrastructure since 2018, with **data.europa.eu** and **data.europarl.europa.eu** serving as primary API gateways. The most mature systems—EUR-Lex, IATE, and Publications Office—offer production-ready APIs, while newer tools like EU Law Tracker lack programmatic access entirely.

This technical reference documents all available integration methods across 14 EU institutional websites, from comprehensive REST APIs with SPARQL endpoints to basic RSS feeds. Seven websites provide robust API access, four offer limited integration options, and three have no programmatic access capabilities. Authentication requirements vary from completely open to EU Login registration, though most read operations require no credentials.

## 1. European Parliament

The European Parliament launched its **Open Data Portal** in January 2023, representing the institution's most significant API initiative. This provides structured access to legislative data, MEP information, and parliamentary activities through multiple interfaces.

### REST API capabilities

**Primary endpoint**: https://data.europarl.europa.eu/

The Open Data Portal delivers data in RDF (Turtle format), JSON-LD, CSV (all 24 EU languages), and XML formats. The API provides access to seven major datasets: organizational structure (political groups, delegations, committees), MEP membership records with complete biographical data, calendar events linked to documents, plenary documents including reports and amendments, adopted texts covering resolutions and legislative acts, complete plenary session records with voting results, and parliamentary questions with answers.

**Standards compliance**: The portal implements DCAT-EP (DCAT-AP extension), W3C Organization Ontology for organizational data, ELI and ELI-DL ontologies for legislative documents, Dublin Core metadata standards, and full Linked Open Data compliance.

**Developer resources**: https://data.europarl.europa.eu/en/developer-corner

The Developer's Corner includes comprehensive OpenAPI documentation for the Registry API, which enables programmatic dataset management. Create or update operations use PUT requests to `https://data.europa.eu/api/hub/repo/catalogues/[catalogueId]/datasets/origin?originalId=[dataset_id]`, while DELETE requests to the same endpoint remove datasets. List operations use GET requests to `https://data.europa.eu/api/hub/repo/datasets?limit=50&valueType=identifiers`.

**Authentication**: Read access requires no authentication. Write operations to catalogues require OpenID Connect authentication with party tokens for dataset contribution.

**SPARQL endpoint**: Integrated with data.europa.eu at https://data.europa.eu/sparql, providing full RDF query capabilities across European Parliament datasets.

### Third-party APIs

**api.epdb.eu**: Independent API providing EU legislation data including OEIL information in JSON format. Operates under Open Database License with no API key requirement. Integrates EUR-Lex, PreLex, and OEIL data.

**itsyourparliament.eu/api**: Voting records API delivering XML format MEP voting data from 2004 to October 2025. Free to use with attribution.

### RSS feed infrastructure

**Feed directory**: https://www.europarl.europa.eu/at-your-service/en/stay-informed/rss-feeds

The Parliament maintains 33+ RSS feeds organized by topic and committee. Topic feeds cover areas including EU institutions (901), justice and citizenship (902), external relations (903), agriculture and fisheries (904), budget (905), culture and education (906), economic and monetary affairs (907), employment and social affairs (908), internal market and industry (909), regions and transport (910), and health and environment (911). All follow the URL pattern `/rss/topic/[number]/en.xml`.

**Committee feeds**: All 22 parliamentary committees provide dedicated RSS feeds following `/rss/committee/[code]/en.xml` structure, including Foreign Affairs (AFET), Economic and Monetary Affairs (ECON), and Civil Liberties, Justice and Home Affairs (LIBE).

**News feed**: https://webcomm-api-rss.ep-lavinia.eu/en/feeds/european-parliament-news-website delivers real-time updates from the Parliament's news website.

All RSS feeds support all 24 EU official languages with real-time updates as content publishes. No rate limits apply to RSS access.

### Usage terms and updates

European Parliament Legal Notice governs all data access. Open data license permits free reuse for commercial and non-commercial purposes with recommended but non-mandatory attribution. No explicit rate limits exist for public read access. Data synchronizes with legislative activities regularly, with SPARQL endpoint updates reflecting changes to data.europa.eu.

### GitHub resources

**Primary repository**: https://github.com/europarl (9 repositories)  
**Beta testing**: https://github.com/europarl/open-data-beta-testing for community feedback  
**ELI-EP Ontology**: https://github.com/europarl/eli-ep for legislative identifier specifications

## 2. OEIL - Legislative Observatory

OEIL operates as the European Parliament's comprehensive legislative tracking database, documenting over 21,606 procedure files from July 1994 forward. Unlike modern APIs, OEIL provides data access primarily through **XML exports** and **RSS subscriptions**.

### Data export capabilities

OEIL enables direct XML export of procedure files, PDF downloads of individual procedures, and RSS subscription to search results. The Observatory Tracker functionality allows users to save searches and receive email notifications when tracked dossiers change.

### Search and filtering

The system supports searching by unique procedure reference numbers (e.g., 2023/0156(COD)), filtering by parliamentary term, procedure type (COD for ordinary legislative procedure, CNS for consultation), committee assignment, and status categories (announced, tabled, close to adoption, blocked, withdrawn, completed). EuroVoc thesaurus classification enables subject-based searches with full-text capability across all procedure files.

Each procedure file contains basic information, key players, key events, technical information, and a documentation gateway linking to related documents across EU institutions. Status tracking follows the entire legislative process from announcement to completion.

### Alternative access methods

**Third-party integration**: The api.epdb.eu service includes OEIL data dumps in JSON format. Integration with data.europa.eu makes Legislative Observatory data accessible through the European Parliament Open Data Portal's APIs.

**Update frequency**: Daily database uploads ensure real-time legislative tracking with no authentication required for public access.

OEIL lacks a documented REST API, but XML export functionality enables bulk data access for procedure files individually or via search results.

## 3. Legislative Train Schedule

The Legislative Train Schedule launched as an interactive visualization tool for the EU Commission's legislative priorities, using a train metaphor where priority areas represent "trains" and individual legislative files become "carriages."

### Platform characteristics

Maintained by EPRS Members' Research Service, the platform covers 7 main Commission priority "trains" and 21 committee-specific trains, tracking approximately 490 individual legislative files. Each file includes concise descriptions, progress indicators, and topical briefings.

**Status tracking**: Files move through announced status (expected initiatives), legislative initiative (Parliament requests to Commission), tabled (submitted to Parliament), close to adoption (near completion), completed/done, blocked (no progress for 9+ months), and withdrawn.

### Technical access limitations

**No dedicated API exists** for the Legislative Train Schedule. The platform operates as a web-based interactive application without RSS feeds specific to train schedule updates. Content integrates with OEIL Legislative Observatory data, and each carriage links to underlying OEIL procedure files (which support XML export) and related European Parliament research briefings.

**Alternative access**: Content publishes on epthinktank.eu blog with analysis. Underlying legislative data remains accessible via OEIL XML exports. Research briefings become available through EPRS Think Tank RSS feeds.

**Monthly updates**: The platform refreshes at each month's end with real-time status changes reflected in linked OEIL files. For specific data needs, contact legislative-train@europarl.europa.eu.

## 4. European Parliament Think Tank

The European Parliamentary Research Service (EPRS) operates the Think Tank platform (also known as epthinktank.eu), delivering research, analysis, and policy briefings for MEPs and the public.

### RSS feed access

**Primary feed**: https://epthinktank.eu/feed delivers RSS 2.0 standard XML format content including research briefings and reports, legislative analysis, policy studies, blog posts on EU legislation and politics, impact assessments, "At a Glance" briefings, and in-depth analysis papers.

RSS feed features include full-text articles with summaries, links to PDF publication downloads, metadata with publication dates, authors, and topics, and categorization by subject area and committee. The feed updates in real-time as content publishes.

### Alternative notification systems

**Email alerts**: The system offers an alternative to RSS for publication notifications. A PDF guide available at https://www.europarl.europa.eu/EPRS/Alerts_External.pdf explains setup allowing filtering by publications, events, and topics. Internal alerts for MEPs and staff include additional features beyond public access.

### Data integration options

**European Parliament Open Data Portal**: Think Tank publications metadata becomes available via data.europarl.europa.eu, searchable through Open Data Portal datasets with full metadata in RDF/JSON-LD formats.

**EU Publications Office**: Think Tank publications appear in the CELLAR database with SPARQL endpoint access at http://publications.europa.eu/webapi/rdf/sparql and RESTful API for document retrieval following Common Data Model (CDM) standards.

**Document formats**: Publications primarily deliver as PDF files, with metadata available in RDF, XML, and JSON-LD via the Open Data Portal, and RSS in XML format.

No authentication applies for public access. Open access governs all publications with free reuse for educational and research purposes under European Parliament copyright with attribution requirements. Multiple publications per week maintain the platform with RSS feeds updating immediately upon content publication, aligned with the legislative calendar.

**Social media integration**: Twitter account @EP_ThinkTank (39.1K followers) provides additional notification channels beyond RSS.

## 5. European Commission

The European Commission main website operates without a dedicated standalone API, instead leveraging **data.europa.eu** as its primary data infrastructure along with several specialized systems.

### data.europa.eu APIs

The official European data portal provides comprehensive API access to EU institutional data through four primary interfaces:

**Search API endpoint**: https://data.europa.eu/api/hub/search/ accepts GET requests returning JSON format responses. No authentication applies for read operations. The OpenAPI format documentation at the endpoint URL details full-text search capabilities, pagination controls, and filtering by multiple criteria. Example calls follow the pattern `GET https://data.europa.eu/api/hub/search/search?page=0&limit=100&q=water`.

**Registry API endpoint**: https://data.europa.eu/api/hub/repo/ supports GET (read), PUT (create/update), and DELETE operations. Formats include JSON, RDF/XML, Turtle, JSON-LD, N-Triples, Trig, and N3. Write operations require OpenID Connect authentication with Bearer tokens. OpenAPI documentation at https://data.europa.eu/api/hub/repo/index.html details direct DCAT-AP metadata access and dataset management. Example calls use `GET https://data.europa.eu/api/hub/repo/datasets/91f2aec3-1aaf-42d3-8730-c567a46c0116.ttl`.

**SPARQL endpoint**: https://data.europa.eu/sparql implements SPARQL 1.1 Query Language protocol for RDF triples. W3C documentation at https://www.w3.org/TR/rdf-sparql-query/ governs query syntax. Complex queries over linked data provide full RDF capabilities.

**MQA (Metadata Quality Assessment) API**: https://data.europa.eu/api/mqa/cache/ with OpenAPI documentation at the same base URL plus /index.html retrieves metadata quality metrics. Parameters filter by findability, accessibility, interoperability, reusability, contextuality, and score.

**Technical specifications**: Data follows DCAT-AP (Data Catalog Application Profile) v2.1.1 standard with OpenAPI 3.x documentation format. Queries execute in real-time while metadata updates come from contributing institutions. Open access permits free commercial and non-commercial use under Creative Commons CC-BY-4.0 and CC0-1.0 licenses.

### EUR-Lex web service

**Protocol**: SOAP-based with XML format and WSDL available after registration

Registration requires EU Login account approval via EUR-Lex website. Authenticated users receive username and password via email. Documentation appears at https://eur-lex.europa.eu/content/help/data-reuse/webservice.html with user manual at https://eur-lex.europa.eu/content/tools/webservices/SearchWebserviceUserManual_v2.01.pdf.

Features include expert query syntax, metadata retrieval, and document search using expert search format with SELECT and ORDER BY clauses. Daily call limits apply but adjust upon request. The system targets legal document retrieval and legislation tracking. Cellar RESTful API provides alternative document download capability.

### RSS feeds

**Press release infrastructure**: http://europa.eu/rapid/rss.htm and https://commission.europa.eu/about/contact/press-services/press-releases-and-notifications_en provide real-time highlights, press releases, and speeches. Since September 2014, only EC press releases publish here, with other EU institutions using EU Newsroom. Searchable press release database enables custom RSS alerts.

**EUR-Lex RSS**: https://eur-lex.europa.eu/content/help/my-eurlex/my-rss-feeds.html delivers predefined feeds for all Parliament and Council legislation, Court of Justice case-law, Commission proposals, and Official Journal acts. Custom feeds allow alerts for documents, procedures, or custom searches. EU Login account registration enables custom alerts with maximum 50 saved searches per user in RSS 2.0 XML format.

**Publications Office RSS**: https://op.europa.eu/en/web/webtools/notifications-and-rss offers RSS feeds for saved searches and publication updates in RSS 2.0 format.

### Related EU APIs

**EU Funding & Tenders Portal**: https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/support/apis provides API support for funding opportunities and tenders.

**ESCO Classification API**: https://esco.ec.europa.eu/en/use-esco/use-esco-services-api delivers skills, competences, qualifications, and occupations taxonomy via web-based API and downloadable version under EUPL 1.2 license with Apache License 2.0 components.

**Agri-food Data Portal API**: https://agridata.ec.europa.eu/extensions/DataPortal/API_Documentation.html provides machine-to-machine interface for agricultural and food market data.

## 6. Joint Research Centre

JRC maintains two primary API infrastructures: a comprehensive data catalogue system and the specialized PVGIS solar energy calculation service.

### JRC data catalogue API

**Primary portal**: https://data.jrc.ec.europa.eu/ provides access through CKAN action API (legacy, RPC-style) and ODCAT action API (recommended, RPC-style). OpenAPI specification documents both interfaces.

Formats include JSON and RDF with no authentication for read access. Write access requires contacting JRC-DATA-SUPPORT@ec.europa.eu. Data follows DCAT-AP extended for scientific data. Metadata retrieval supports RDF and JSON formats via URL extension (.rdf, .rj), such as `https://data.jrc.ec.europa.eu/collection/emm.rdf`.

Features enable dataset discovery, collection browsing, and metadata retrieval. Integration with data.europa.eu ensures JRC datasets appear in the European data portal.

### PVGIS API for solar energy

**Base URLs**: PVGIS 5.3 at https://re.jrc.ec.europa.eu/api/v5_3/ and PVGIS 5.2 at https://re.jrc.ec.europa.eu/api/v5_2/

**Available tools**: PVcalc (grid-connected PV systems), SHScalc (off-grid PV systems), MRcalc (monthly radiation), DRcalc (daily radiation), seriescalc (hourly radiation), tmy (Typical Meteorological Year), and printhorizon (horizon profile).

**Technical specifications**: GET-only method with HEAD for existence checks. **Critical rate limit**: 30 calls per second per IP address. HTTP status codes include 429 (Too Many Requests) and 529 (Site Overloaded - retry after delay).

Output formats deliver JSON (recommended), CSV, basic (raw CSV), and EPW (Energy Plus format for TMY). Parameters include lat, lon, peakpower, loss, angle, and aspect. Example call: `GET https://re.jrc.ec.europa.eu/api/v5_3/PVcalc?lat=45&lon=8&peakpower=1&loss=14&outputformat=json`

CORS policy blocks AJAX access. Documentation at https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis/getting-started-pvgis/api-non-interactive-service_en includes Python, NodeJS, Perl, and Java code examples.

### OGC API services

**GitHub repository**: https://github.com/justb4/ogc-api-jrc  
**Production server**: https://jrc.map5.nl

Implementation uses pygeoapi (Python-based OGC API suite) following OGC API standards. GitOps approach with CI/CD enables deployment with documentation available at production server.

### RSS feeds

**JRC news RSS**: https://ec.europa.eu/dgs/jrc/rss.cfm?type=HLN&lang=en provides headlines and news in multiple EU languages with direct RSS feed URLs per language.

**Europe Media Monitor (EMM)**: https://emm.newsbrief.eu/overview.html monitors 10,000+ key news portals worldwide plus 20 commercial feeds, processing 400,000+ article links daily across 70 languages. Hundreds of subject and country categories support email and RSS reader subscriptions with 24/7 real-time monitoring for media analysis, epidemiology, and policy monitoring.

**MedISys**: https://medisys.newsbrief.eu/ focuses on public health and food safety monitoring from 900+ specialist medical sites and 20,000 generic news sites. RSS availability covers all disease categories with breaking news alerts, statistical tracking, and subscription options for breaking news notifications organized by diseases, symptoms, and chemical agents.

**Press center**: https://joint-research-centre.ec.europa.eu/press-centre_en publishes press releases, news announcements, and media materials multiple times monthly. Monthly JRC Science for Policy newsletter supplements press releases.

### Data access characteristics

JRC Data Policy promotes open access to research data aligned with Horizon 2020 requirements, based on Commission Decision 2011/833/EU. Licensing varies by dataset with mostly open licenses. Contact JRC-DATA-SUPPORT@ec.europa.eu for catalogue enquiries.

Real-time APIs include PVGIS (solar data) and EMM/MedISys (news monitoring). Scientific datasets update per research project schedules with catalogue metadata updated continuously as new datasets emerge.

## 7. EUR-Lex

EUR-Lex represents the most mature API infrastructure among EU legal databases, offering **SOAP web services**, **Cellar RESTful API**, **SPARQL endpoint**, and comprehensive **RSS feeds**.

### SOAP web service

**Registration**: Requires free EU Login account registration at https://eur-lex.europa.eu/EURLexWebService. Registration form collects user data, organization details, intended use, and maximum daily API calls. After approval, users receive username and password via email with WSDL access.

**Documentation**: Help page at https://eur-lex.europa.eu/content/help/data-reuse/webservice.html, user manual at https://eur-lex.europa.eu/content/tools/webservices/SearchWebserviceUserManual_v2.01.pdf, data extraction guide at https://eur-lex.europa.eu/content/tools/webservices/DataExtractionUsingWebServices-v1.00.pdf.

**Format**: XML only via SOAP envelope structure supporting query options similar to expert search on website, full text search, SELECT clause for metadata selection, ORDER BY for sorting, and webservice template generator for each query.

**Rate limits**: Maximum daily calls limit configurable per user during registration. Default page size limit reaches 1000 results per query with adjustable limits by request.

**Constraints**: Cannot directly download document files via SOAP service. Must retrieve documents via Cellar REST API or stable URLs. Requires acceptance of EUR-Lex terms of use.

### Cellar RESTful API

**Description**: Cellar serves as the common repository of metadata and content for EUR-Lex, providing HTTP RESTful access to legal documents and metadata.

**Endpoint base**: http://publications.europa.eu/resource/cellar/  
**Documentation**: https://op.europa.eu/en/web/cellar/home

No authentication required for read access. Formats include PDF, HTML, XHTML, XML (Formex format), and RDF. Notices (metadata) deliver in XML/RDF format.

Features enable retrieving specific metadata notices, downloading document content files, and accessing via Cellar URIs or CELEX identifiers. Supports Work-Expression-Manifestation-Item (WEMI) hierarchy.

**Technical documentation**: End-user manual at https://op.europa.eu/documents/2050822/0/CEM-EEU-External+End+User+manual-v15+00.pdf, developer guide available, Cellar booklet at https://op.europa.eu/en/publication-detail/-/publication/605733b9-f045-11ec-a534-01aa75ed71a1/language-en, training materials including Postman collections.

**Example patterns**: Work URI follows http://publications.europa.eu/resource/cellar/{UUID}. Content stream uses {work-uri}/{expression-id}/{manifestation-id}/{content-stream-id}.

### SPARQL endpoint

**Endpoint**: http://publications.europa.eu/webapi/rdf/sparql

No authentication required for read-only queries by anonymous users. Features enable querying all metadata in Cellar, accessing relationships between entities, and queries based on Common Data Model (CDM) ontology with RDF Schema and OWL foundations.

**Query builder**: https://op.europa.eu/en/advanced-sparql-query-editor

**Data model**: Common Data Model (CDM) at https://op.europa.eu/en/web/eu-vocabularies/dataset/-/resource?uri=http://publications.europa.eu/resource/dataset/cdm, Named Authority Lists (NAL) at http://publications.europa.eu/resource/authority/, Resource types at http://publications.europa.eu/resource/authority/resource-type, Corporate bodies at http://publications.europa.eu/resource/authority/corporate-body.

**Namespaces**: CDM at http://publications.europa.eu/ontology/cdm#, Annotation at http://publications.europa.eu/ontology/annotation#.

**Rate limits**: Results capped at 1 million rows per query.

### RSS feeds

**Predefined RSS feeds**: Available for predefined document categories including Official Journal editions (L and C series), all Parliament and Council legislation, Commission proposals. No authentication required.

**Custom RSS alerts**: Requires EUR-Lex account (free EU Login registration). Create alerts from searches, documents, or procedures. Maximum 50 saved searches/alerts per account. Alerts automatically update when matching documents publish.

**Documentation**: Predefined RSS at https://eur-lex.europa.eu/content/help/search/predefined-rss.html, custom RSS alerts at https://eur-lex.europa.eu/content/help/my-eurlex/my-rss-feeds.html.

### Bulk downloads

**Data dump**: https://datadump.publications.europa.eu/ contains all legal acts in force (CELEX sector 3) per language in bulk download format. Requires EU Login account (free).

**data.europa.eu integration**: Official Journals (L and C series) from 2004 onward available in CSV format with links to XML Formex documents, organized per year and language.

### Usage terms

Free to reuse EUR-Lex data subject to copyright conditions in legal notice. Commercial and non-commercial use permitted under Commission's document reuse policy based on Decision 2011/833/EU. Attribution recommended but not mandatory.

Real-time updates apply for new publications. Official Journal publishes daily when issued. RSS feeds update immediately upon publication. SPARQL endpoint reflects latest metadata.

**Technical support**: EURLEX-HELPDESK@publications.europa.eu

## 8. Publications Office

The Publications Office operates the shared Cellar infrastructure with EUR-Lex while maintaining additional services including the Search API and TED (Tenders Electronic Daily) API.

### Search API

**Documentation**: https://op.europa.eu/en/web/webtools/search-api

Elasticsearch-based search API covers general and legal publications, persons, organizations, vocabularies, and web pages. Features include full-text and metadata search, autocomplete suggestions, similar publication recommendations, search widget for embedding on external websites, and saved searches with notifications for logged-in users.

Read operations require no authentication while advanced features need EU Login account. Data sources include legal publications (EUR-Lex content), general EU publications, persons and organizations, vocabularies, and web pages.

### TED API

**Description**: API for public procurement notices and eForms

**Documentation**: https://docs.ted.europa.eu/api/latest/index.html

TED Developer Portal access required. EU Login credentials generate API keys via "Manage API Keys" section. Free API keys enable access.

**Features**: Publication API for submitting and managing eForms notices, Validation API (Central Validation Service) for notice compliance, search and query capabilities, notices lifecycle management from submission to publication.

**Environments**: Production for live publication, Preview for testing without actual publication.

**Data formats**: eForms XML input, JSON responses for API operations.

Operations include submitting eForms notices, validating notices before and upon submission, querying published notices, and retrieving notice metadata. Rate limits manage per API key.

**Update frequency**: Published notices appear at 09:00 CET on publication date. Export process completes around 15:00 CET on publication date. Status updates arrive around 16:00 CET previous working day.

**Developer resources**: https://ted.europa.eu/en/simap/developers-corner-for-reusers

### SPARQL and Cellar REST

Publications Office shares SPARQL endpoint at http://publications.europa.eu/webapi/rdf/sparql with EUR-Lex, providing access to all Publications Office metadata beyond just legal documents, including books, leaflets, and general publications.

Cellar REST API infrastructure matches EUR-Lex implementation with RSS + ATOM feeds for new publications and updates, metadata notices via HTTP RESTful services, and content files in multiple formats.

**Technical documentation**: Cellar website at https://op.europa.eu/en/web/cellar/home, API connectivity guide, code repository at https://code.europa.eu/cellar.

### RSS feeds and notifications

**Service**: Publications Office Notifications and RSS

**Documentation**: https://op.europa.eu/en/web/webtools/notifications-and-rss

Features include RSS feeds for search results and email notifications option. Saved feeds appear in user profile "My RSS feeds" section. RSS feeds have no file size restrictions unlike email notifications.

Access requires no authentication for basic RSS. Free access with no file size limits on RSS feeds.

### Open data integration

**URL**: https://data.europa.eu/ with API documentation at https://dataeuropa.gitlab.io/data-provider-manual/api-documentation/

Registry API enables creating, updating, and deleting datasets. Features include metadata management, dataset CRUD operations, DCAT-AP 2.1.0 compliance, and RDF format support (Turtle, RDF/XML, JSON-LD, N-Triples).

Methods use POST for API calls and PUT for dataset submission. Read access requires no authentication while write access needs Party Token obtained by contacting data.europa.eu team.

### EU vocabularies

**Access**: https://publications.europa.eu/en/web/eu-vocabularies

Provides authority tables, controlled vocabularies, taxonomies, EuroVoc thesaurus, and Named Authority Lists (NAL) in RDF and SKOS formats.

**Formex format**: XML format for Official Journal documents with information at https://op.europa.eu/en/web/eu-vocabularies/formex/.

### Usage terms

Free access and reuse under open data principles. Commercial and non-commercial use permitted based on EU open data policy with recommended attribution.

Real-time updates apply for new publications with RSS feeds updating immediately. TED notices follow daily updates per publication schedule.

**Technical support**: Via Publications Office contact forms for general inquiries, TED Developer Portal support for TED API, GitHub discussions at https://github.com/OP-TED/eForms-SDK/discussions.

## 9. Council of the EU

The Council of the EU maintains **no dedicated REST or SOAP APIs** for direct programmatic access to Council-specific data, representing a significant gap compared to other EU institutions.

### RSS feeds

**Primary access method for automated updates**

**Main RSS page**: https://www.consilium.europa.eu/en/about-site/rss/

RSS (Really Simple Syndication) feeds deliver Council website content in machine-readable format. Subscribe to specific website texts, multimedia file updates, and language-specific feeds available in all EU languages.

Features include Council news and press releases, meeting announcements, policy updates, and institutional information. Format follows RSS 2.0 with real-time updates as content publishes and no specified rate limits.

No authentication required for subscription. Visit RSS page, select desired feed, copy RSS URL to RSS reader, and choose preferred language version.

### Meeting documents

**Public Register Access**: https://www.consilium.europa.eu/en/documents-publications/public-register/meeting-documents/

Contains meeting documents from 1999 to present including agendas, conclusions, outcomes, minutes, votes, and summary records. Covers Council, European Council, and preparatory bodies.

Meeting calendar provides detailed planning and coverage since 2014 available through Council website with additional documents not in public register. Access method uses web-based search and browse interface without API capabilities.

### Alternative data access

**Via data.europa.eu**: Council datasets appear in EU Open Data Portal catalogued for access through data.europa.eu APIs. Search at https://data.europa.eu/data/datasets?catalog=council-european-union.

**Third-party APIs**: Some Council legislative voting data available through third-party aggregators. Example: api.epdb.eu provides Council voting records from 2006 onwards (third-party, not official Council service).

No OAI-PMH protocol documentation exists. No dedicated Council SPARQL endpoint operates. Council legal acts remain accessible through Publications Office SPARQL endpoint (Cellar).

### Data export limitations

No bulk downloads available as structured bulk download. Individual document download from public register in PDF and other formats per document. No programmatic bulk export documented.

### Usage terms

Follow Council website legal notice under standard EU institutional reuse principles with copyright notices applying to documents. RSS feeds and public register content accessible without authentication. No specified rate limits for RSS feeds or public access.

Standard EU copyright and reuse conditions apply. No specific API usage restrictions exist as no APIs operate. Document reuse subject to Council legal notice.

**Technical support**: Through Council website contact forms with general inquiries section. No dedicated developer support portal exists.

### Integration recommendations

Given limited API availability, use RSS feeds for notifications and updates as primary method. Access legal acts through EUR-Lex APIs using Council as document author filter. Manual access via public register web interface for meeting documents. Use EUR-Lex/Cellar APIs filtering for Council documents for bulk data. Consider api.epdb.eu for historical voting data (unofficial third-party).

## 10. OEIL, Legislative Train, Think Tank

*See sections 2-4 above for complete details on these European Parliament platforms.*

## 11. EU Law Tracker

Launched April 30, 2024, EU Law Tracker represents a joint project of European Parliament, Council, and Commission monitoring the EU legislative process from proposal to adoption.

### API and RSS availability

**Status**: No public API or RSS feeds identified. New tool without technical integration capabilities documented.

Platform covers ordinary legislative procedure files since launch with future plans for special legislative procedures. Tracks EU's legislative priorities through web-based user interface only.

No API documentation found. No RSS feed URLs identified. No developer portal or technical documentation pages discovered. Website operates as user-interface only.

### Alternative data sources

**EUR-Lex integration**: EUR-Lex provides comprehensive API access including CELLAR SPARQL endpoint for querying EU legislation metadata, RESTful API for retrieving documents and metadata, and RSS feeds with predefined alerts at EUR-Lex for new publications.

**EUR-Lex technical details**: SPARQL endpoint at https://publications.europa.eu/webapi/rdf/sparql, data formats including RDF, JSON-LD, Turtle, XML (Formex), PDF, and HTML. Webservices available for registered users. Data dump enables bulk download of legal acts in force (requires EU Login). RSS alerts at https://eur-lex.europa.eu/content/help/search/predefined-rss.html.

**Recommendation**: For legislative tracking, use EUR-Lex APIs and the R package "eurlex" providing simplified access to EU law data.

## 12. Who's Who

The official directory of EU personnel operates at https://op.europa.eu/en/web/who-is-who as an electronic directory of EU institutions, bodies, and agencies.

### API and RSS availability

**Status**: No public API identified. Directory rebuilt in April 2023 (version update) with search interface only.

Tool provides organizational charts in all 24 official EU languages with contact information, staff listings, and personnel data for EU institutions. No API documentation found. No developer portal exists.

### Data access characteristics

vCard export available for individual contacts. Permanent links to organizational entities exist. No bulk data access identified. No RSS feeds operate for updates.

Data protection follows Processing operation managed by Publications Office Unit A.5 under GDPR compliance (Regulation EU 2018/1725). Personal data restrictions apply.

**Alternative access**: Manual search through web interface, individual vCard downloads, create alerts functionality (nature unclear - may be email alerts).

**Recommendation**: No programmatic API access available. Data appears restricted to web interface queries only due to GDPR considerations for personnel information.

## 13. Interinstitutional Style Guide

The reference tool for EU document production operates at https://style-guide.europa.eu/ as an internal reference for EU institutions available in all 24 official EU languages.

### API and RSS availability

**Status**: No API or RSS feeds exist. First published 1997 with continuous updates, the guide contains uniform style rules and conventions for authors, translators, terminologists, and editors.

Website interface only provides access. No API documentation exists. No developer resources operate. No RSS feeds deliver updates.

### Available formats

Online web version constantly updates. PDF download offers print-quality edition available via EU Publications. Print-on-demand version available through EU Publications system.

**Access methods**: User accounts allow saving preferences and bookmarks. Web browsing only with search functionality within website. Check "News" page for latest changes as website updates regularly without automated notification system.

**PDF version**: Static snapshot of website content available at https://op.europa.eu/en/publication-detail/-/publication/01ed788a-d266-11ec-a95f-01aa75ed71a1/language-en for download and offline reference.

**Recommendation**: No programmatic access exists. Manual consultation only via website or downloaded PDF.

## 14. IATE - Interactive Terminology Database

IATE provides the **most accessible API** among specialized EU databases, with a full REST API launched in late 2018.

### REST API infrastructure

**API endpoint base**: https://iate.europa.eu/em-api/  
**Search endpoint**: https://iate.europa.eu/em-api/entries/_search?expand=true&offset=0&limit=100  
**Documentation**: https://iate.europa.eu/developers (primarily descriptive content)

Public API access available with user account creation recommended for advanced features (bookmarks, preferences). No API key required for basic search functionality. Username/password authentication available for advanced features.

### Data characteristics

Contains 8+ million terms across 100+ domains in 24 EU official languages plus Latin. JSON format responses support POST requests with JSON-encoded request bodies returning structured terminology entries with metadata.

**Search capabilities**: Search parameters include query text, source language, target languages, domains, term types, and search operators. Supports filtering by domain, term type, searchable fields, and reliability indicators. Returns term values, definitions, contexts, references, and domain classifications.

Rate limits remain unspecified in available documentation.

### Example API implementation

```python
import requests
import json

datapost = {
    'query': 'your_search_term',
    'source': 'en',
    'targets': ['fr', 'de'],
    'search_in_fields': [0],
    'search_in_term_types': [0, 1, 2, 3, 4, 5],
    'query_operator': 5,
    'mediaType': 'application/json'
}

url = 'https://iate.europa.eu/em-api/entries/_search?expand=true&offset=0&limit=100'
response = requests.post(url, data=json.dumps(datapost), headers={'Content-type': 'application/json'})
```

### Available resources

Collections API provides access to terminology collections. Domains/institutions listing organizes terms by subject area. Languages metadata covers all 24 EU languages. Query operators define search logic. Term types classify terminology entries. Searchable fields specifications detail query capabilities.

### Third-party integration

Trados Studio plugin available on RWS AppStore. Python library "piate" at GitHub: drewsonne/piate. Various CAT tool integrations support translation workflows.

**Data export**: Users can export bookmarked entries. Export to file functionality available for registered users. No bulk database download mentioned.

**RSS feeds**: No RSS feeds identified for IATE.

**Update frequency**: Continuously updated by EU institutions with real-time search against live database. Receives 50M+ queries annually.

## 15. AssistEU

Research discovered extremely limited information about AssistEU at https://assist.eu/.

### API and RSS availability

**Status**: No information found. No search results returned for "assist.eu API". No documentation pages identified. Website existence confirmed but no technical documentation found.

May represent a newer tool or internal-only system. Unable to confirm any API, RSS, or data access capabilities.

**Recommendation**: Direct inquiry to EU Publications Office or the tool's administrators necessary to determine technical integration options.

---

## Cross-platform integration architecture

### Common infrastructure patterns

**Shared repositories**: EUR-Lex and Publications Office share Cellar repository infrastructure, SPARQL endpoint at http://publications.europa.eu/webapi/rdf/sparql, REST API systems, Common Data Model (CDM), and EU Vocabularies.

**data.europa.eu integration**: All three major institutions (Parliament, Commission, Council) make data theoretically accessible through EU Open Data Portal APIs at https://data.europa.eu/, REST API at https://data.europa.eu/api/hub/, and SPARQL at https://data.europa.eu/sparql.

### Authentication patterns

**No authentication required**: SPARQL queries, Cellar REST reads, RSS feeds, basic search, IATE basic search, data.europa.eu read operations.

**EU Login required (free)**: EUR-Lex SOAP registration, data dump access, custom RSS alerts, TED API access.

**API keys required (free)**: TED API access after EU Login.

**Special access**: Database RSS feeds, OAI-PMH requires contacting EUR-Lex team.

### Rate limit summary

**EUR-Lex SOAP**: Configurable daily limits per user.  
**SPARQL**: 1 million rows per query.  
**PVGIS API**: 30 calls per second per IP address (strictly enforced).  
**TED API**: Managed per API key.  
**RSS Feeds**: No limits.  
**Cellar REST**: No documented limits.  
**data.europa.eu APIs**: Not publicly specified.

### Data format matrix

| Format | EUR-Lex | Publications Office | Parliament | JRC | IATE | Commission |
|--------|---------|-------------------|------------|-----|------|------------|
| **JSON** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| **XML** | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ |
| **RDF** | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ |
| **CSV** | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ |
| **PDF** | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ |
| **Turtle** | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ |
| **JSON-LD** | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ |

### Integration best practices

**For EUR-Lex legal documents**: Use SPARQL for metadata queries, SOAP for complex searches (requires registration), REST API (Cellar) for document retrieval, and RSS for real-time updates.

**For Publications Office general publications**: Use Search API for discovery, Cellar REST for content, TED API for procurement (separate registration), and RSS for notifications.

**For European Parliament data**: Use Open Data Portal API for structured datasets, RSS feeds for news and updates, SPARQL for complex queries, and third-party api.epdb.eu for aggregated legislative data.

**For JRC research data**: Use JRC Data Catalogue API for dataset discovery, PVGIS API for solar calculations (respect 30 calls/second limit), EMM/MedISys RSS for news monitoring, and OGC APIs for geospatial data.

**For Council documents**: Use EUR-Lex APIs with Council filters, RSS feeds for Council-specific updates, manual access for meeting documents, and consider third-party aggregators for historical data.

**For terminology**: Use IATE REST API for multilingual term lookups in 24 languages.

## Conclusion

European institutions demonstrate widely varying API maturity levels. EUR-Lex, Publications Office, and IATE provide production-ready APIs with comprehensive documentation. The European Parliament's Open Data Portal launched in 2023 represents significant progress but remains in active development. The Joint Research Centre offers specialized APIs like PVGIS with strict rate limiting requirements.

Critical gaps exist in Council of the EU technical integration, which lacks any dedicated API infrastructure. Newer tools like EU Law Tracker (launched 2024) provide no programmatic access. Personnel directories like Who's Who remain web-interface only due to GDPR considerations.

Developers should prioritize EUR-Lex SOAP and REST APIs for legal document access, data.europa.eu APIs for cross-institutional queries, IATE API for terminology services, and PVGIS API for solar energy calculations while carefully managing its 30 calls/second rate limit. RSS feeds provide the most reliable real-time notification mechanism across all institutions, operating without authentication or rate limits.