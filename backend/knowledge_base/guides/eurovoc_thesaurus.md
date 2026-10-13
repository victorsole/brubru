# EuroVoc: the EU's Multilingual Subject Thesaurus

## QUICK FACTS
- **What it is**: **EuroVoc** is the EU's multilingual, multidisciplinary **thesaurus** covering the activities of the EU, managed by the Publications Office. Terms exist in the **24 EU languages** plus **Albanian, Macedonian and Serbian**. Users include the EU institutions, national and regional parliaments and governments. Current release **4.24, published 8 July 2026**, on the EU Vocabularies site: https://op.europa.eu/en/web/eu-vocabularies/dataset/-/resource?uri=http://publications.europa.eu/resource/dataset/eurovoc (dataset URI `http://publications.europa.eu/resource/dataset/eurovoc`).
- **Size (Cellar SPARQL, 13 Oct 2026)**: **7,515 concepts**, **127 microthesauri**, **21 domains**. 473 of the concepts have a non-numeric id of the form `c_` + 8 hex characters (for example `http://eurovoc.europa.eu/c_5a195ffd`, "smart technology").
- **Concept URIs**: `http://eurovoc.europa.eu/{id}`, language-independent; the label is resolved per language. Relations are SKOS: **broader**, **narrower**, **related**. Many concepts also carry `exactMatch` / `closeMatch` links to other thesauri (Library of Congress subjects, UN thesaurus, UNESCO thesaurus, GEMET).
- **Never write a EuroVoc id from memory.** Two "verified" examples in an earlier version of this guide were wrong: `2517` is **social policy** and `4651` is **vehicle**. Correct ids: **data protection = 5181**, **personal data = 5595**, **artificial intelligence = 3030**, **single market = 3299**. Look an id up by its English label (see "Looking an id up") and quote the label next to it.
- **Cellar link**: every act in Cellar carries its subject concepts in `cdm:work_is_about_concept_eurovoc`. GDPR (`32016R0679`) carries 9: data protection, personal data, protection of privacy, data-processing law, cross-frontier data flow, access to information, disclosure of information, natural person, area of freedom, security and justice. The AI Act (`32024R1689`) carries 7: artificial intelligence, market approval, harmonisation of standards, single market, new technology, innovation, smart technology.
- **In the LEG_2026-10 export**: each OJ publication's `tree_non_inferred.rdf` lists its EuroVoc concept URIs, so subjects can be joined to CELEX without a network call.

## Structure
- **21 domains**, each a two-digit code and capitalised name: 04 POLITICS, 08 INTERNATIONAL RELATIONS, 10 EUROPEAN UNION, 12 LAW, 16 ECONOMICS, 20 TRADE, 24 FINANCE, 28 SOCIAL QUESTIONS, 32 EDUCATION AND COMMUNICATIONS, 36 SCIENCE, 40 BUSINESS AND COMPETITION, 44 EMPLOYMENT AND WORKING CONDITIONS, 48 TRANSPORT, 52 ENVIRONMENT, 56 AGRICULTURE, FORESTRY AND FISHERIES, 60 AGRI-FOODSTUFFS, 64 PRODUCTION, TECHNOLOGY AND RESEARCH, 66 ENERGY, 68 INDUSTRY, 72 GEOGRAPHY, 76 INTERNATIONAL ORGANISATIONS.
- **127 microthesauri**, each labelled with a four-digit code (for example `2826 social affairs`, `4811 organisation of transport`). A concept sits in one or more microthesauri; `data protection` (5181) sits in microthesaurus `3231 information and information processing`.
- **Concepts** have a preferred label in each language (stored as SKOS-XL label resources), alternative labels (synonyms) and the broader / narrower / related relations. A concept can be a top concept of its microthesaurus.
- Names of organisations, institutions and treaties are concepts too; Brubru's classifier uses the microthesaurus code to keep them out of subject tags.

## Where to get it
- **Downloads** (release page): `eurovoc_metadata.ttl`, SKOS-AP files (`eurovoc-skos-ap-act.zip`, `eurovoc-skos-ap-eu.zip`, `.rdf`), SKOS core concepts, XML (`eurovoc_xml.zip`, ATTO), Excel export, MarcXML, TBX2.
- **Online**: the EU Vocabularies site offers a Query Wizard, a Flint editor and a **SPARQL endpoint**; VocBench and ShowVoc are listed among the online tools. The Cellar endpoint `https://publications.europa.eu/webapi/rdf/sparql` answers EuroVoc queries too.
- **Brubru copy**: `backend/data/eu_vocabularies/eurovoc_descriptors.json` (7,029 descriptors with id, English label and microthesaurus code; numeric ids only, so the 473 newest `c_` concepts are missing).

## Looking an id up
- Exact English label, Cellar SPARQL:
  `SELECT DISTINCT ?c WHERE { ?c <http://www.w3.org/2008/05/skos-xl#prefLabel>/<http://www.w3.org/2008/05/skos-xl#literalForm> "data protection"@en ; a <http://www.w3.org/2004/02/skos/core#Concept> }`
  (results include non-EuroVoc URIs such as `data.europa.eu/uxp/...` and EuroSciVoc; keep the one that starts `http://eurovoc.europa.eu/`).
- Subjects of an act: `?w cdm:resource_legal_id_celex "32016R0679"^^xsd:string ; cdm:work_is_about_concept_eurovoc ?c`.
- A concept URI that is not in the Brubru table, or a label that does not match the id, means the id is wrong: leave the field empty rather than guess.

## How Brubru uses EuroVoc
- **Guide tagging**: guides may list 2 to 3 EuroVoc URIs so `services/vocabularies/glossary_injector.py` can add label glossaries to chat context and the DCAT-AP catalogue gets `dcat:theme` values. Each URI must be written with its English label as a comment and must match the authority.
- **Topic grouping**: acts under a concept via the Cellar client (`get_acts_by_eurovoc`).
- **Search enrichment**: EuroVoc keywords filter EP Open Data and the `data.europa.eu` portal.

## Cross-references
- `celex_number_format.md`: the identifier EuroVoc concepts attach to
- `eli_european_legislation_identifier.md`: the ELI URI that sits beside the CELEX in the same metadata
- `finding_and_citing_eu_law.md`: the data hub (Cellar, CDM, authority tables)
- `docs/api/eu_legal_data_access.md`: engineering reference (CDM `work_is_about_concept_eurovoc`)
- `services/vocabularies/glossary_injector.py`: how labels reach chat context
