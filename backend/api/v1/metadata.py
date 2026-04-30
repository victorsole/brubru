"""
/api/v1/{institutions, commissioners, committees, directorates-general, political-groups,
         countries, languages, document-types, procedure-types, legal-bases,
         policy-areas, event-types, procedure-statuses}

W2 P1 metadata hygiene — partner-grade per-resource enumeration endpoints.
Replaces the single-blob /meta/enums for serious integrations.

Rule: every record returned has at minimum a stable `slug`, a human `name`,
and a `type` label. NO field is NULL when we can avoid it.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.database import get_db
from models.eu_law import EULaw
from models.user import User

from ._deps import api_user_with_rate_limit

router = APIRouter(tags=["v1-metadata"])


# ============================================================================
# Static reference data
# ============================================================================

# All 27 EU member states + EEA + UK historical, ISO-3166-1 alpha-2 + alpha-3
COUNTRIES = [
    {"slug": "at", "iso2": "AT", "iso3": "AUT", "name": "Austria", "eu_member": True, "joined": "1995-01-01"},
    {"slug": "be", "iso2": "BE", "iso3": "BEL", "name": "Belgium", "eu_member": True, "joined": "1957-03-25"},
    {"slug": "bg", "iso2": "BG", "iso3": "BGR", "name": "Bulgaria", "eu_member": True, "joined": "2007-01-01"},
    {"slug": "hr", "iso2": "HR", "iso3": "HRV", "name": "Croatia", "eu_member": True, "joined": "2013-07-01"},
    {"slug": "cy", "iso2": "CY", "iso3": "CYP", "name": "Cyprus", "eu_member": True, "joined": "2004-05-01"},
    {"slug": "cz", "iso2": "CZ", "iso3": "CZE", "name": "Czechia", "eu_member": True, "joined": "2004-05-01"},
    {"slug": "dk", "iso2": "DK", "iso3": "DNK", "name": "Denmark", "eu_member": True, "joined": "1973-01-01"},
    {"slug": "ee", "iso2": "EE", "iso3": "EST", "name": "Estonia", "eu_member": True, "joined": "2004-05-01"},
    {"slug": "fi", "iso2": "FI", "iso3": "FIN", "name": "Finland", "eu_member": True, "joined": "1995-01-01"},
    {"slug": "fr", "iso2": "FR", "iso3": "FRA", "name": "France", "eu_member": True, "joined": "1957-03-25"},
    {"slug": "de", "iso2": "DE", "iso3": "DEU", "name": "Germany", "eu_member": True, "joined": "1957-03-25"},
    {"slug": "gr", "iso2": "GR", "iso3": "GRC", "name": "Greece", "eu_member": True, "joined": "1981-01-01"},
    {"slug": "hu", "iso2": "HU", "iso3": "HUN", "name": "Hungary", "eu_member": True, "joined": "2004-05-01"},
    {"slug": "ie", "iso2": "IE", "iso3": "IRL", "name": "Ireland", "eu_member": True, "joined": "1973-01-01"},
    {"slug": "it", "iso2": "IT", "iso3": "ITA", "name": "Italy", "eu_member": True, "joined": "1957-03-25"},
    {"slug": "lv", "iso2": "LV", "iso3": "LVA", "name": "Latvia", "eu_member": True, "joined": "2004-05-01"},
    {"slug": "lt", "iso2": "LT", "iso3": "LTU", "name": "Lithuania", "eu_member": True, "joined": "2004-05-01"},
    {"slug": "lu", "iso2": "LU", "iso3": "LUX", "name": "Luxembourg", "eu_member": True, "joined": "1957-03-25"},
    {"slug": "mt", "iso2": "MT", "iso3": "MLT", "name": "Malta", "eu_member": True, "joined": "2004-05-01"},
    {"slug": "nl", "iso2": "NL", "iso3": "NLD", "name": "Netherlands", "eu_member": True, "joined": "1957-03-25"},
    {"slug": "pl", "iso2": "PL", "iso3": "POL", "name": "Poland", "eu_member": True, "joined": "2004-05-01"},
    {"slug": "pt", "iso2": "PT", "iso3": "PRT", "name": "Portugal", "eu_member": True, "joined": "1986-01-01"},
    {"slug": "ro", "iso2": "RO", "iso3": "ROU", "name": "Romania", "eu_member": True, "joined": "2007-01-01"},
    {"slug": "sk", "iso2": "SK", "iso3": "SVK", "name": "Slovakia", "eu_member": True, "joined": "2004-05-01"},
    {"slug": "si", "iso2": "SI", "iso3": "SVN", "name": "Slovenia", "eu_member": True, "joined": "2004-05-01"},
    {"slug": "es", "iso2": "ES", "iso3": "ESP", "name": "Spain", "eu_member": True, "joined": "1986-01-01"},
    {"slug": "se", "iso2": "SE", "iso3": "SWE", "name": "Sweden", "eu_member": True, "joined": "1995-01-01"},
    # EEA non-EU
    {"slug": "is", "iso2": "IS", "iso3": "ISL", "name": "Iceland", "eu_member": False, "eea_member": True},
    {"slug": "li", "iso2": "LI", "iso3": "LIE", "name": "Liechtenstein", "eu_member": False, "eea_member": True},
    {"slug": "no", "iso2": "NO", "iso3": "NOR", "name": "Norway", "eu_member": False, "eea_member": True},
    # Former member
    {"slug": "gb", "iso2": "GB", "iso3": "GBR", "name": "United Kingdom", "eu_member": False, "eu_member_until": "2020-01-31"},
]


# 24 official EU languages with ISO-639 codes
LANGUAGES = [
    {"slug": "bg", "iso639_1": "bg", "iso639_3": "bul", "name": "Bulgarian", "native_name": "Български"},
    {"slug": "es", "iso639_1": "es", "iso639_3": "spa", "name": "Spanish", "native_name": "Español"},
    {"slug": "cs", "iso639_1": "cs", "iso639_3": "ces", "name": "Czech", "native_name": "Čeština"},
    {"slug": "da", "iso639_1": "da", "iso639_3": "dan", "name": "Danish", "native_name": "Dansk"},
    {"slug": "de", "iso639_1": "de", "iso639_3": "deu", "name": "German", "native_name": "Deutsch"},
    {"slug": "et", "iso639_1": "et", "iso639_3": "est", "name": "Estonian", "native_name": "Eesti"},
    {"slug": "el", "iso639_1": "el", "iso639_3": "ell", "name": "Greek", "native_name": "Ελληνικά"},
    {"slug": "en", "iso639_1": "en", "iso639_3": "eng", "name": "English", "native_name": "English"},
    {"slug": "fr", "iso639_1": "fr", "iso639_3": "fra", "name": "French", "native_name": "Français"},
    {"slug": "ga", "iso639_1": "ga", "iso639_3": "gle", "name": "Irish", "native_name": "Gaeilge"},
    {"slug": "hr", "iso639_1": "hr", "iso639_3": "hrv", "name": "Croatian", "native_name": "Hrvatski"},
    {"slug": "it", "iso639_1": "it", "iso639_3": "ita", "name": "Italian", "native_name": "Italiano"},
    {"slug": "lv", "iso639_1": "lv", "iso639_3": "lav", "name": "Latvian", "native_name": "Latviešu"},
    {"slug": "lt", "iso639_1": "lt", "iso639_3": "lit", "name": "Lithuanian", "native_name": "Lietuvių"},
    {"slug": "hu", "iso639_1": "hu", "iso639_3": "hun", "name": "Hungarian", "native_name": "Magyar"},
    {"slug": "mt", "iso639_1": "mt", "iso639_3": "mlt", "name": "Maltese", "native_name": "Malti"},
    {"slug": "nl", "iso639_1": "nl", "iso639_3": "nld", "name": "Dutch", "native_name": "Nederlands"},
    {"slug": "pl", "iso639_1": "pl", "iso639_3": "pol", "name": "Polish", "native_name": "Polski"},
    {"slug": "pt", "iso639_1": "pt", "iso639_3": "por", "name": "Portuguese", "native_name": "Português"},
    {"slug": "ro", "iso639_1": "ro", "iso639_3": "ron", "name": "Romanian", "native_name": "Română"},
    {"slug": "sk", "iso639_1": "sk", "iso639_3": "slk", "name": "Slovak", "native_name": "Slovenčina"},
    {"slug": "sl", "iso639_1": "sl", "iso639_3": "slv", "name": "Slovenian", "native_name": "Slovenščina"},
    {"slug": "fi", "iso639_1": "fi", "iso639_3": "fin", "name": "Finnish", "native_name": "Suomi"},
    {"slug": "sv", "iso639_1": "sv", "iso639_3": "swe", "name": "Swedish", "native_name": "Svenska"},
]


# Major EU institutions + agencies + bodies
INSTITUTIONS = [
    # Treaty institutions
    {"slug": "european-parliament", "short": "EP", "name": "European Parliament", "city": "Brussels / Strasbourg", "country": "BE/FR", "type": "treaty_institution", "website": "https://www.europarl.europa.eu"},
    {"slug": "european-council", "short": "EUCO", "name": "European Council", "city": "Brussels", "country": "BE", "type": "treaty_institution", "website": "https://www.consilium.europa.eu/en/european-council/"},
    {"slug": "council-of-the-eu", "short": "COUNCIL", "name": "Council of the European Union", "city": "Brussels", "country": "BE", "type": "treaty_institution", "website": "https://www.consilium.europa.eu"},
    {"slug": "european-commission", "short": "EC", "name": "European Commission", "city": "Brussels", "country": "BE", "type": "treaty_institution", "website": "https://ec.europa.eu"},
    {"slug": "court-of-justice", "short": "CJEU", "name": "Court of Justice of the European Union", "city": "Luxembourg", "country": "LU", "type": "treaty_institution", "website": "https://curia.europa.eu"},
    {"slug": "european-central-bank", "short": "ECB", "name": "European Central Bank", "city": "Frankfurt", "country": "DE", "type": "treaty_institution", "website": "https://www.ecb.europa.eu"},
    {"slug": "european-court-of-auditors", "short": "ECA", "name": "European Court of Auditors", "city": "Luxembourg", "country": "LU", "type": "treaty_institution", "website": "https://www.eca.europa.eu"},
    # Advisory bodies
    {"slug": "european-economic-and-social-committee", "short": "EESC", "name": "European Economic and Social Committee", "city": "Brussels", "country": "BE", "type": "advisory_body", "website": "https://www.eesc.europa.eu"},
    {"slug": "committee-of-the-regions", "short": "COR", "name": "European Committee of the Regions", "city": "Brussels", "country": "BE", "type": "advisory_body", "website": "https://cor.europa.eu"},
    {"slug": "european-investment-bank", "short": "EIB", "name": "European Investment Bank", "city": "Luxembourg", "country": "LU", "type": "financial_body", "website": "https://www.eib.org"},
    {"slug": "european-investment-fund", "short": "EIF", "name": "European Investment Fund", "city": "Luxembourg", "country": "LU", "type": "financial_body", "website": "https://www.eif.org"},
    {"slug": "european-ombudsman", "short": "OMBUDSMAN", "name": "European Ombudsman", "city": "Strasbourg", "country": "FR", "type": "advisory_body", "website": "https://www.ombudsman.europa.eu"},
    {"slug": "eeas", "short": "EEAS", "name": "European External Action Service", "city": "Brussels", "country": "BE", "type": "service", "website": "https://www.eeas.europa.eu"},
    # Decentralised agencies (selected high-profile)
    {"slug": "frontex", "short": "FRONTEX", "name": "European Border and Coast Guard Agency", "city": "Warsaw", "country": "PL", "type": "agency", "website": "https://frontex.europa.eu"},
    {"slug": "eea", "short": "EEA", "name": "European Environment Agency", "city": "Copenhagen", "country": "DK", "type": "agency", "website": "https://www.eea.europa.eu"},
    {"slug": "ema", "short": "EMA", "name": "European Medicines Agency", "city": "Amsterdam", "country": "NL", "type": "agency", "website": "https://www.ema.europa.eu"},
    {"slug": "echa", "short": "ECHA", "name": "European Chemicals Agency", "city": "Helsinki", "country": "FI", "type": "agency", "website": "https://echa.europa.eu"},
    {"slug": "efsa", "short": "EFSA", "name": "European Food Safety Authority", "city": "Parma", "country": "IT", "type": "agency", "website": "https://www.efsa.europa.eu"},
    {"slug": "easa", "short": "EASA", "name": "European Union Aviation Safety Agency", "city": "Cologne", "country": "DE", "type": "agency", "website": "https://www.easa.europa.eu"},
    {"slug": "era", "short": "ERA", "name": "European Union Agency for Railways", "city": "Valenciennes", "country": "FR", "type": "agency", "website": "https://www.era.europa.eu"},
    {"slug": "enisa", "short": "ENISA", "name": "European Union Agency for Cybersecurity", "city": "Heraklion / Athens", "country": "GR", "type": "agency", "website": "https://www.enisa.europa.eu"},
    {"slug": "esma", "short": "ESMA", "name": "European Securities and Markets Authority", "city": "Paris", "country": "FR", "type": "agency", "website": "https://www.esma.europa.eu"},
    {"slug": "eba", "short": "EBA", "name": "European Banking Authority", "city": "Paris", "country": "FR", "type": "agency", "website": "https://www.eba.europa.eu"},
    {"slug": "eiopa", "short": "EIOPA", "name": "European Insurance and Occupational Pensions Authority", "city": "Frankfurt", "country": "DE", "type": "agency", "website": "https://www.eiopa.europa.eu"},
    {"slug": "edps", "short": "EDPS", "name": "European Data Protection Supervisor", "city": "Brussels", "country": "BE", "type": "agency", "website": "https://www.edps.europa.eu"},
    {"slug": "edpb", "short": "EDPB", "name": "European Data Protection Board", "city": "Brussels", "country": "BE", "type": "advisory_body", "website": "https://edpb.europa.eu"},
    {"slug": "fra", "short": "FRA", "name": "European Union Agency for Fundamental Rights", "city": "Vienna", "country": "AT", "type": "agency", "website": "https://fra.europa.eu"},
    {"slug": "europol", "short": "EUROPOL", "name": "European Union Agency for Law Enforcement Cooperation", "city": "The Hague", "country": "NL", "type": "agency", "website": "https://www.europol.europa.eu"},
    {"slug": "eurojust", "short": "EUROJUST", "name": "European Union Agency for Criminal Justice Cooperation", "city": "The Hague", "country": "NL", "type": "agency", "website": "https://www.eurojust.europa.eu"},
    {"slug": "cedefop", "short": "CEDEFOP", "name": "European Centre for the Development of Vocational Training", "city": "Thessaloniki", "country": "GR", "type": "agency", "website": "https://www.cedefop.europa.eu"},
    {"slug": "eige", "short": "EIGE", "name": "European Institute for Gender Equality", "city": "Vilnius", "country": "LT", "type": "agency", "website": "https://eige.europa.eu"},
    {"slug": "ecdc", "short": "ECDC", "name": "European Centre for Disease Prevention and Control", "city": "Stockholm", "country": "SE", "type": "agency", "website": "https://www.ecdc.europa.eu"},
    {"slug": "etf", "short": "ETF", "name": "European Training Foundation", "city": "Turin", "country": "IT", "type": "agency", "website": "https://www.etf.europa.eu"},
    {"slug": "eu-osha", "short": "EU-OSHA", "name": "European Agency for Safety and Health at Work", "city": "Bilbao", "country": "ES", "type": "agency", "website": "https://osha.europa.eu"},
    {"slug": "eufound", "short": "EUROFOUND", "name": "European Foundation for the Improvement of Living and Working Conditions", "city": "Dublin", "country": "IE", "type": "agency", "website": "https://www.eurofound.europa.eu"},
    {"slug": "euipo", "short": "EUIPO", "name": "European Union Intellectual Property Office", "city": "Alicante", "country": "ES", "type": "agency", "website": "https://www.euipo.europa.eu"},
    {"slug": "cpvo", "short": "CPVO", "name": "Community Plant Variety Office", "city": "Angers", "country": "FR", "type": "agency", "website": "https://cpvo.europa.eu"},
    {"slug": "euda", "short": "EUDA", "name": "European Union Drugs Agency", "city": "Lisbon", "country": "PT", "type": "agency", "website": "https://www.euda.europa.eu"},
]


# EP committees with full names
EP_COMMITTEES_FULL = [
    {"slug": "afco", "code": "AFCO", "name": "Committee on Constitutional Affairs", "type": "standing",
     "homepage": "https://www.europarl.europa.eu/committees/en/afco/home/highlights",
     "streaming_url": "https://multimedia.europarl.europa.eu/en/webstreaming?committee=afco",
     "documents_url": "https://www.europarl.europa.eu/committees/en/afco/documents/latest-documents"},
    {"slug": "afet", "code": "AFET", "name": "Committee on Foreign Affairs", "type": "standing",
     "homepage": "https://www.europarl.europa.eu/committees/en/afet/home/highlights",
     "streaming_url": "https://multimedia.europarl.europa.eu/en/webstreaming?committee=afet",
     "documents_url": "https://www.europarl.europa.eu/committees/en/afet/documents/latest-documents"},
    {"slug": "agri", "code": "AGRI", "name": "Committee on Agriculture and Rural Development", "type": "standing",
     "homepage": "https://www.europarl.europa.eu/committees/en/agri/home/highlights",
     "streaming_url": "https://multimedia.europarl.europa.eu/en/webstreaming?committee=agri",
     "documents_url": "https://www.europarl.europa.eu/committees/en/agri/documents/latest-documents"},
    {"slug": "budg", "code": "BUDG", "name": "Committee on Budgets", "type": "standing",
     "homepage": "https://www.europarl.europa.eu/committees/en/budg/home/highlights",
     "streaming_url": "https://multimedia.europarl.europa.eu/en/webstreaming?committee=budg",
     "documents_url": "https://www.europarl.europa.eu/committees/en/budg/documents/latest-documents"},
    {"slug": "cont", "code": "CONT", "name": "Committee on Budgetary Control", "type": "standing",
     "homepage": "https://www.europarl.europa.eu/committees/en/cont/home/highlights",
     "streaming_url": "https://multimedia.europarl.europa.eu/en/webstreaming?committee=cont",
     "documents_url": "https://www.europarl.europa.eu/committees/en/cont/documents/latest-documents"},
    {"slug": "cult", "code": "CULT", "name": "Committee on Culture and Education", "type": "standing",
     "homepage": "https://www.europarl.europa.eu/committees/en/cult/home/highlights",
     "streaming_url": "https://multimedia.europarl.europa.eu/en/webstreaming?committee=cult",
     "documents_url": "https://www.europarl.europa.eu/committees/en/cult/documents/latest-documents"},
    {"slug": "deve", "code": "DEVE", "name": "Committee on Development", "type": "standing",
     "homepage": "https://www.europarl.europa.eu/committees/en/deve/home/highlights",
     "streaming_url": "https://multimedia.europarl.europa.eu/en/webstreaming?committee=deve",
     "documents_url": "https://www.europarl.europa.eu/committees/en/deve/documents/latest-documents"},
    {"slug": "econ", "code": "ECON", "name": "Committee on Economic and Monetary Affairs", "type": "standing",
     "homepage": "https://www.europarl.europa.eu/committees/en/econ/home/highlights",
     "streaming_url": "https://multimedia.europarl.europa.eu/en/webstreaming?committee=econ",
     "documents_url": "https://www.europarl.europa.eu/committees/en/econ/documents/latest-documents"},
    {"slug": "empl", "code": "EMPL", "name": "Committee on Employment and Social Affairs", "type": "standing",
     "homepage": "https://www.europarl.europa.eu/committees/en/empl/home/highlights",
     "streaming_url": "https://multimedia.europarl.europa.eu/en/webstreaming?committee=empl",
     "documents_url": "https://www.europarl.europa.eu/committees/en/empl/documents/latest-documents"},
    {"slug": "envi", "code": "ENVI", "name": "Committee on Environment, Climate Change and Food Safety", "type": "standing",
     "homepage": "https://www.europarl.europa.eu/committees/en/envi/home/highlights",
     "streaming_url": "https://multimedia.europarl.europa.eu/en/webstreaming?committee=envi",
     "documents_url": "https://www.europarl.europa.eu/committees/en/envi/documents/latest-documents"},
    {"slug": "femm", "code": "FEMM", "name": "Committee on Women's Rights and Gender Equality", "type": "standing",
     "homepage": "https://www.europarl.europa.eu/committees/en/femm/home/highlights",
     "streaming_url": "https://multimedia.europarl.europa.eu/en/webstreaming?committee=femm",
     "documents_url": "https://www.europarl.europa.eu/committees/en/femm/documents/latest-documents"},
    {"slug": "imco", "code": "IMCO", "name": "Committee on the Internal Market and Consumer Protection", "type": "standing",
     "homepage": "https://www.europarl.europa.eu/committees/en/imco/home/highlights",
     "streaming_url": "https://multimedia.europarl.europa.eu/en/webstreaming?committee=imco",
     "documents_url": "https://www.europarl.europa.eu/committees/en/imco/documents/latest-documents"},
    {"slug": "inta", "code": "INTA", "name": "Committee on International Trade", "type": "standing",
     "homepage": "https://www.europarl.europa.eu/committees/en/inta/home/highlights",
     "streaming_url": "https://multimedia.europarl.europa.eu/en/webstreaming?committee=inta",
     "documents_url": "https://www.europarl.europa.eu/committees/en/inta/documents/latest-documents"},
    {"slug": "itre", "code": "ITRE", "name": "Committee on Industry, Research and Energy", "type": "standing",
     "homepage": "https://www.europarl.europa.eu/committees/en/itre/home/highlights",
     "streaming_url": "https://multimedia.europarl.europa.eu/en/webstreaming?committee=itre",
     "documents_url": "https://www.europarl.europa.eu/committees/en/itre/documents/latest-documents"},
    {"slug": "juri", "code": "JURI", "name": "Committee on Legal Affairs", "type": "standing",
     "homepage": "https://www.europarl.europa.eu/committees/en/juri/home/highlights",
     "streaming_url": "https://multimedia.europarl.europa.eu/en/webstreaming?committee=juri",
     "documents_url": "https://www.europarl.europa.eu/committees/en/juri/documents/latest-documents"},
    {"slug": "libe", "code": "LIBE", "name": "Committee on Civil Liberties, Justice and Home Affairs", "type": "standing",
     "homepage": "https://www.europarl.europa.eu/committees/en/libe/home/highlights",
     "streaming_url": "https://multimedia.europarl.europa.eu/en/webstreaming?committee=libe",
     "documents_url": "https://www.europarl.europa.eu/committees/en/libe/documents/latest-documents"},
    {"slug": "pech", "code": "PECH", "name": "Committee on Fisheries", "type": "standing",
     "homepage": "https://www.europarl.europa.eu/committees/en/pech/home/highlights",
     "streaming_url": "https://multimedia.europarl.europa.eu/en/webstreaming?committee=pech",
     "documents_url": "https://www.europarl.europa.eu/committees/en/pech/documents/latest-documents"},
    {"slug": "peti", "code": "PETI", "name": "Committee on Petitions", "type": "standing",
     "homepage": "https://www.europarl.europa.eu/committees/en/peti/home/highlights",
     "streaming_url": "https://multimedia.europarl.europa.eu/en/webstreaming?committee=peti",
     "documents_url": "https://www.europarl.europa.eu/committees/en/peti/documents/latest-documents"},
    {"slug": "regi", "code": "REGI", "name": "Committee on Regional Development", "type": "standing",
     "homepage": "https://www.europarl.europa.eu/committees/en/regi/home/highlights",
     "streaming_url": "https://multimedia.europarl.europa.eu/en/webstreaming?committee=regi",
     "documents_url": "https://www.europarl.europa.eu/committees/en/regi/documents/latest-documents"},
    {"slug": "sant", "code": "SANT", "name": "Subcommittee on Public Health", "type": "subcommittee",
     "homepage": "https://www.europarl.europa.eu/committees/en/sant/home/highlights",
     "streaming_url": "https://multimedia.europarl.europa.eu/en/webstreaming?committee=sant",
     "documents_url": "https://www.europarl.europa.eu/committees/en/sant/documents/latest-documents"},
    {"slug": "sede", "code": "SEDE", "name": "Subcommittee on Security and Defence", "type": "subcommittee",
     "homepage": "https://www.europarl.europa.eu/committees/en/sede/home/highlights",
     "streaming_url": "https://multimedia.europarl.europa.eu/en/webstreaming?committee=sede",
     "documents_url": "https://www.europarl.europa.eu/committees/en/sede/documents/latest-documents"},
    {"slug": "tran", "code": "TRAN", "name": "Committee on Transport and Tourism", "type": "standing",
     "homepage": "https://www.europarl.europa.eu/committees/en/tran/home/highlights",
     "streaming_url": "https://multimedia.europarl.europa.eu/en/webstreaming?committee=tran",
     "documents_url": "https://www.europarl.europa.eu/committees/en/tran/documents/latest-documents"},
    {"slug": "droi", "code": "DROI", "name": "Subcommittee on Human Rights", "type": "subcommittee",
     "homepage": "https://www.europarl.europa.eu/committees/en/droi/home/highlights",
     "streaming_url": "https://multimedia.europarl.europa.eu/en/webstreaming?committee=droi",
     "documents_url": "https://www.europarl.europa.eu/committees/en/droi/documents/latest-documents"},
    {"slug": "fisc", "code": "FISC", "name": "Subcommittee on Tax Matters", "type": "subcommittee",
     "homepage": "https://www.europarl.europa.eu/committees/en/fisc/home/highlights",
     "streaming_url": "https://multimedia.europarl.europa.eu/en/webstreaming?committee=fisc",
     "documents_url": "https://www.europarl.europa.eu/committees/en/fisc/documents/latest-documents"},
    {"slug": "hous", "code": "HOUS", "name": "Special Committee on the Housing Crisis", "type": "special_temporary",
     "homepage": "https://www.europarl.europa.eu/committees/en/hous/home/highlights",
     "streaming_url": "https://multimedia.europarl.europa.eu/en/webstreaming?committee=hous",
     "documents_url": "https://www.europarl.europa.eu/committees/en/hous/documents/latest-documents"},
    {"slug": "euds", "code": "EUDS", "name": "Special Committee on the European Democracy Shield", "type": "special_temporary",
     "homepage": "https://www.europarl.europa.eu/committees/en/euds/home/highlights",
     "streaming_url": "https://multimedia.europarl.europa.eu/en/webstreaming?committee=euds",
     "documents_url": "https://www.europarl.europa.eu/committees/en/euds/documents/latest-documents"},
]


# Commission DGs (Directorates-General)
# Each DG carries: slug, code, name, type, website, twitter, linkedin, youtube.
# Verified URLs against ec.europa.eu redirects + each DG's social presence
# on 30 April 2026.
DGS = [
    {"slug": "dg-agri", "code": "AGRI", "name": "DG Agriculture and Rural Development", "type": "policy_dg",
     "website": "https://agriculture.ec.europa.eu", "twitter": "https://twitter.com/EUAgri",
     "linkedin": "https://www.linkedin.com/showcase/eu-agri/", "youtube": "https://www.youtube.com/user/EUagriculture"},
    {"slug": "dg-budg", "code": "BUDG", "name": "DG Budget", "type": "policy_dg",
     "website": "https://commission.europa.eu/about/departments-and-executive-agencies/budget_en", "twitter": "https://twitter.com/EU_Budget",
     "linkedin": None, "youtube": None},
    {"slug": "dg-clima", "code": "CLIMA", "name": "DG Climate Action", "type": "policy_dg",
     "website": "https://climate.ec.europa.eu", "twitter": "https://twitter.com/EUClimateAction",
     "linkedin": "https://www.linkedin.com/showcase/european-commission-dg-clima/", "youtube": "https://www.youtube.com/user/euclimateaction"},
    {"slug": "dg-cnect", "code": "CNECT", "name": "DG Communications Networks, Content and Technology", "type": "policy_dg",
     "website": "https://digital-strategy.ec.europa.eu", "twitter": "https://twitter.com/DigitalEU",
     "linkedin": "https://www.linkedin.com/showcase/european-commission-digital/", "youtube": "https://www.youtube.com/user/digitalagendaeu"},
    {"slug": "dg-comm", "code": "COMM", "name": "DG Communication", "type": "service_dg",
     "website": "https://commission.europa.eu/about/departments-and-executive-agencies/communication_en", "twitter": "https://twitter.com/EU_Commission",
     "linkedin": "https://www.linkedin.com/company/european-commission/", "youtube": "https://www.youtube.com/eutube"},
    {"slug": "dg-comp", "code": "COMP", "name": "DG Competition", "type": "policy_dg",
     "website": "https://competition-policy.ec.europa.eu", "twitter": "https://twitter.com/EU_Competition",
     "linkedin": "https://www.linkedin.com/showcase/eucompetition/", "youtube": None},
    {"slug": "dg-defis", "code": "DEFIS", "name": "DG Defence Industry and Space", "type": "policy_dg",
     "website": "https://defence-industry-space.ec.europa.eu", "twitter": "https://twitter.com/defis_eu",
     "linkedin": "https://www.linkedin.com/showcase/dg-defis/", "youtube": None},
    {"slug": "dg-echo", "code": "ECHO", "name": "DG European Civil Protection and Humanitarian Aid Operations", "type": "policy_dg",
     "website": "https://civil-protection-humanitarian-aid.ec.europa.eu", "twitter": "https://twitter.com/eu_echo",
     "linkedin": "https://www.linkedin.com/showcase/european-civil-protection-and-humanitarian-aid-operations/", "youtube": "https://www.youtube.com/user/ECHOEuropeanUnion"},
    {"slug": "dg-ecfin", "code": "ECFIN", "name": "DG Economic and Financial Affairs", "type": "policy_dg",
     "website": "https://economy-finance.ec.europa.eu", "twitter": "https://twitter.com/ecfin",
     "linkedin": "https://www.linkedin.com/showcase/dg-economic-and-financial-affairs/", "youtube": None},
    {"slug": "dg-empl", "code": "EMPL", "name": "DG Employment, Social Affairs and Inclusion", "type": "policy_dg",
     "website": "https://ec.europa.eu/social/", "twitter": "https://twitter.com/EU_Social",
     "linkedin": "https://www.linkedin.com/showcase/european-commission-dg-empl/", "youtube": "https://www.youtube.com/user/socialeurope"},
    {"slug": "dg-ener", "code": "ENER", "name": "DG Energy", "type": "policy_dg",
     "website": "https://energy.ec.europa.eu", "twitter": "https://twitter.com/Energy4Europe",
     "linkedin": "https://www.linkedin.com/showcase/dg-energy/", "youtube": "https://www.youtube.com/user/EUEnergy"},
    {"slug": "dg-env", "code": "ENV", "name": "DG Environment", "type": "policy_dg",
     "website": "https://environment.ec.europa.eu", "twitter": "https://twitter.com/EU_ENV",
     "linkedin": "https://www.linkedin.com/showcase/european-commission-dg-environment/", "youtube": "https://www.youtube.com/user/environmenteu"},
    {"slug": "dg-digit", "code": "DIGIT", "name": "DG Informatics", "type": "service_dg",
     "website": "https://commission.europa.eu/about/departments-and-executive-agencies/digital-services_en", "twitter": "https://twitter.com/EU_DIGIT",
     "linkedin": None, "youtube": None},
    {"slug": "dg-fisma", "code": "FISMA", "name": "DG Financial Stability, Financial Services and Capital Markets Union", "type": "policy_dg",
     "website": "https://finance.ec.europa.eu", "twitter": "https://twitter.com/EU_finance",
     "linkedin": "https://www.linkedin.com/showcase/eu-finance/", "youtube": None},
    {"slug": "dg-grow", "code": "GROW", "name": "DG Internal Market, Industry, Entrepreneurship and SMEs", "type": "policy_dg",
     "website": "https://single-market-economy.ec.europa.eu", "twitter": "https://twitter.com/EU_Growth",
     "linkedin": "https://www.linkedin.com/showcase/dg-grow---european-commission/", "youtube": None},
    {"slug": "dg-home", "code": "HOME", "name": "DG Migration and Home Affairs", "type": "policy_dg",
     "website": "https://home-affairs.ec.europa.eu", "twitter": "https://twitter.com/EUHomeAffairs",
     "linkedin": "https://www.linkedin.com/showcase/dg-migration-and-home-affairs/", "youtube": None},
    {"slug": "dg-hr", "code": "HR", "name": "DG Human Resources and Security", "type": "service_dg",
     "website": "https://commission.europa.eu/about/departments-and-executive-agencies/human-resources-and-security_en", "twitter": None,
     "linkedin": None, "youtube": None},
    {"slug": "dg-just", "code": "JUST", "name": "DG Justice and Consumers", "type": "policy_dg",
     "website": "https://commission.europa.eu/about/departments-and-executive-agencies/justice-and-consumers_en", "twitter": "https://twitter.com/EU_Justice",
     "linkedin": "https://www.linkedin.com/showcase/eu-justice-and-consumers/", "youtube": "https://www.youtube.com/user/EUJustice"},
    {"slug": "dg-mare", "code": "MARE", "name": "DG Maritime Affairs and Fisheries", "type": "policy_dg",
     "website": "https://oceans-and-fisheries.ec.europa.eu", "twitter": "https://twitter.com/EU_MARE",
     "linkedin": "https://www.linkedin.com/showcase/european-commission-oceans-and-fisheries/", "youtube": None},
    {"slug": "dg-move", "code": "MOVE", "name": "DG Mobility and Transport", "type": "policy_dg",
     "website": "https://transport.ec.europa.eu", "twitter": "https://twitter.com/Transport_EU",
     "linkedin": "https://www.linkedin.com/showcase/european-commission-mobility-and-transport/", "youtube": None},
    {"slug": "dg-near", "code": "NEAR", "name": "DG European Neighbourhood Policy and Enlargement Negotiations", "type": "policy_dg",
     "website": "https://neighbourhood-enlargement.ec.europa.eu", "twitter": "https://twitter.com/eu_near",
     "linkedin": "https://www.linkedin.com/showcase/eu-near/", "youtube": "https://www.youtube.com/user/EUenlargementtv"},
    {"slug": "dg-regio", "code": "REGIO", "name": "DG Regional and Urban Policy", "type": "policy_dg",
     "website": "https://ec.europa.eu/regional_policy/", "twitter": "https://twitter.com/EUinmyRegion",
     "linkedin": "https://www.linkedin.com/showcase/european-commission-dg-regio/", "youtube": "https://www.youtube.com/user/RegioNetwork"},
    {"slug": "dg-rtd", "code": "RTD", "name": "DG Research and Innovation", "type": "policy_dg",
     "website": "https://research-and-innovation.ec.europa.eu", "twitter": "https://twitter.com/EUScienceInnov",
     "linkedin": "https://www.linkedin.com/showcase/european-commission-dg-research-and-innovation/", "youtube": "https://www.youtube.com/user/researcheu"},
    {"slug": "dg-sante", "code": "SANTE", "name": "DG Health and Food Safety", "type": "policy_dg",
     "website": "https://health.ec.europa.eu", "twitter": "https://twitter.com/EU_Health",
     "linkedin": "https://www.linkedin.com/showcase/european-commission-health-and-food-safety/", "youtube": None},
    {"slug": "dg-trade", "code": "TRADE", "name": "DG Trade", "type": "policy_dg",
     "website": "https://policy.trade.ec.europa.eu", "twitter": "https://twitter.com/Trade_EU",
     "linkedin": "https://www.linkedin.com/showcase/eu-trade/", "youtube": None},
    {"slug": "dg-taxud", "code": "TAXUD", "name": "DG Taxation and Customs Union", "type": "policy_dg",
     "website": "https://taxation-customs.ec.europa.eu", "twitter": "https://twitter.com/EU_Taxud",
     "linkedin": "https://www.linkedin.com/showcase/eu-taxud/", "youtube": None},
    {"slug": "dg-eac", "code": "EAC", "name": "DG Education, Youth, Sport and Culture", "type": "policy_dg",
     "website": "https://education.ec.europa.eu", "twitter": "https://twitter.com/EUErasmusPlus",
     "linkedin": "https://www.linkedin.com/showcase/eu-education-and-culture/", "youtube": None},
    {"slug": "dg-intpa", "code": "INTPA", "name": "DG International Partnerships", "type": "policy_dg",
     "website": "https://international-partnerships.ec.europa.eu", "twitter": "https://twitter.com/EU_partnerships",
     "linkedin": "https://www.linkedin.com/showcase/eu-international-partnerships/", "youtube": "https://www.youtube.com/user/EUDevelopmentCoop"},
    {"slug": "dg-reform", "code": "REFORM", "name": "DG Structural Reform Support", "type": "service_dg",
     "website": "https://reform-support.ec.europa.eu", "twitter": "https://twitter.com/EU_Reforms",
     "linkedin": "https://www.linkedin.com/showcase/dg-structural-reform-support/", "youtube": None},
    {"slug": "dg-sg", "code": "SG", "name": "Secretariat-General", "type": "service_dg",
     "website": "https://commission.europa.eu/about/departments-and-executive-agencies/secretariat-general_en", "twitter": None,
     "linkedin": None, "youtube": None},
    {"slug": "dg-sj", "code": "SJ", "name": "Legal Service", "type": "service_dg",
     "website": "https://commission.europa.eu/about/departments-and-executive-agencies/legal-service_en", "twitter": None,
     "linkedin": None, "youtube": None},
    {"slug": "dg-eppo", "code": "EPPO", "name": "European Public Prosecutor's Office", "type": "service_dg",
     "website": "https://www.eppo.europa.eu", "twitter": "https://twitter.com/EUProsecutor",
     "linkedin": "https://www.linkedin.com/company/european-public-prosecutor-s-office/", "youtube": None},
    {"slug": "dg-olaf", "code": "OLAF", "name": "European Anti-Fraud Office", "type": "service_dg",
     "website": "https://anti-fraud.ec.europa.eu", "twitter": "https://twitter.com/EUAntiFraud",
     "linkedin": "https://www.linkedin.com/showcase/european-anti-fraud-office/", "youtube": None},
    {"slug": "dg-eurostat", "code": "ESTAT", "name": "Eurostat", "type": "service_dg",
     "website": "https://ec.europa.eu/eurostat", "twitter": "https://twitter.com/EU_Eurostat",
     "linkedin": "https://www.linkedin.com/company/eurostat/", "youtube": "https://www.youtube.com/user/eurostat"},
    {"slug": "dg-jrc", "code": "JRC", "name": "Joint Research Centre", "type": "research_dg",
     "website": "https://joint-research-centre.ec.europa.eu", "twitter": "https://twitter.com/EU_ScienceHub",
     "linkedin": "https://www.linkedin.com/showcase/eu-science-hub/", "youtube": "https://www.youtube.com/user/EUScienceHub"},
]


# EP political groups (10th term)
POLITICAL_GROUPS = [
    {"slug": "epp", "code": "EPP", "name": "Group of the European People's Party (Christian Democrats)", "type": "ep_group", "ideology": "centre-right"},
    {"slug": "sd", "code": "S&D", "name": "Group of the Progressive Alliance of Socialists and Democrats", "type": "ep_group", "ideology": "centre-left"},
    {"slug": "renew", "code": "RENEW", "name": "Renew Europe Group", "type": "ep_group", "ideology": "liberal"},
    {"slug": "greens-efa", "code": "VERTS/ALE", "name": "Greens / European Free Alliance", "type": "ep_group", "ideology": "green"},
    {"slug": "ecr", "code": "ECR", "name": "European Conservatives and Reformists Group", "type": "ep_group", "ideology": "conservative"},
    {"slug": "pfe", "code": "PFE", "name": "Patriots for Europe", "type": "ep_group", "ideology": "right"},
    {"slug": "esn", "code": "ESN", "name": "Europe of Sovereign Nations", "type": "ep_group", "ideology": "far-right"},
    {"slug": "left", "code": "GUE/NGL", "name": "The Left in the European Parliament — GUE/NGL", "type": "ep_group", "ideology": "left"},
    {"slug": "ni", "code": "NI", "name": "Non-attached Members", "type": "ep_group", "ideology": "non-attached"},
]


# Procedure types (CODE: COD/NLE/INI/INL/RSP/CNS/APP/BUD/DEC/IMM/COS/REG/AVC)
PROCEDURE_TYPES = [
    {"slug": "cod", "code": "COD", "name": "Ordinary legislative procedure (co-decision)", "binding": True, "trilogue": True},
    {"slug": "nle", "code": "NLE", "name": "Non-legislative enactments (consent)", "binding": True, "trilogue": False},
    {"slug": "cns", "code": "CNS", "name": "Consultation procedure", "binding": True, "trilogue": False},
    {"slug": "ini", "code": "INI", "name": "Own-initiative procedure", "binding": False, "trilogue": False},
    {"slug": "inl", "code": "INL", "name": "Legislative initiative procedure", "binding": False, "trilogue": False},
    {"slug": "rsp", "code": "RSP", "name": "Resolutions on topical, urgent matters", "binding": False, "trilogue": False},
    {"slug": "app", "code": "APP", "name": "Consent procedure", "binding": True, "trilogue": False},
    {"slug": "bud", "code": "BUD", "name": "Budgetary procedure", "binding": True, "trilogue": False},
    {"slug": "dec", "code": "DEC", "name": "Discharge procedure", "binding": True, "trilogue": False},
    {"slug": "cos", "code": "COS", "name": "Procedure on a strategic Commission communication", "binding": False, "trilogue": False},
    {"slug": "imm", "code": "IMM", "name": "MEP immunity procedure", "binding": True, "trilogue": False},
    {"slug": "reg", "code": "REG", "name": "Procedure on EP rules of procedure", "binding": True, "trilogue": False},
]


# Legal bases — TFEU/TEU article tree (selected high-frequency)
LEGAL_BASES = [
    {"slug": "tfeu-art-114", "treaty": "TFEU", "article": "114", "name": "Approximation of laws in internal market", "policy_areas": ["internal_market"]},
    {"slug": "tfeu-art-191", "treaty": "TFEU", "article": "191", "name": "Environment policy", "policy_areas": ["environment"]},
    {"slug": "tfeu-art-192", "treaty": "TFEU", "article": "192", "name": "Environment legislation", "policy_areas": ["environment"]},
    {"slug": "tfeu-art-153", "treaty": "TFEU", "article": "153", "name": "Working conditions, social security", "policy_areas": ["social_policy"]},
    {"slug": "tfeu-art-168", "treaty": "TFEU", "article": "168", "name": "Public health", "policy_areas": ["health"]},
    {"slug": "tfeu-art-43", "treaty": "TFEU", "article": "43", "name": "Common Agricultural Policy", "policy_areas": ["agriculture"]},
    {"slug": "tfeu-art-91", "treaty": "TFEU", "article": "91", "name": "Common transport policy", "policy_areas": ["transport"]},
    {"slug": "tfeu-art-100", "treaty": "TFEU", "article": "100", "name": "Sea / air transport", "policy_areas": ["transport"]},
    {"slug": "tfeu-art-194", "treaty": "TFEU", "article": "194", "name": "Energy policy", "policy_areas": ["energy"]},
    {"slug": "tfeu-art-77", "treaty": "TFEU", "article": "77", "name": "Border checks, asylum and immigration", "policy_areas": ["migration", "justice"]},
    {"slug": "tfeu-art-78", "treaty": "TFEU", "article": "78", "name": "Asylum policy", "policy_areas": ["migration"]},
    {"slug": "tfeu-art-83", "treaty": "TFEU", "article": "83", "name": "Judicial cooperation in criminal matters", "policy_areas": ["justice"]},
    {"slug": "tfeu-art-16", "treaty": "TFEU", "article": "16", "name": "Personal data protection", "policy_areas": ["data_protection", "fundamental_rights"]},
    {"slug": "tfeu-art-207", "treaty": "TFEU", "article": "207", "name": "Common commercial policy", "policy_areas": ["trade"]},
    {"slug": "tfeu-art-352", "treaty": "TFEU", "article": "352", "name": "Flexibility clause", "policy_areas": ["general"]},
    {"slug": "teu-art-31", "treaty": "TEU", "article": "31", "name": "CFSP — Council acting unanimously", "policy_areas": ["foreign_policy"]},
]


PROCEDURE_STATUSES = [
    {"slug": "announced", "name": "Announced", "description": "Procedure announced but not yet tabled"},
    {"slug": "legislative_initiative", "name": "Legislative initiative", "description": "EP own-initiative legislative request"},
    {"slug": "tabled", "name": "Tabled", "description": "Proposal formally tabled by Commission"},
    {"slug": "close_to_adoption", "name": "Close to adoption", "description": "In late-stage trilogue or final reading"},
    {"slug": "completed", "name": "Completed", "description": "Procedure completed (adopted or otherwise terminated)"},
    {"slug": "adopted", "name": "Adopted", "description": "Final act adopted and published"},
    {"slug": "blocked", "name": "Blocked", "description": "9+ months without progress"},
    {"slug": "withdrawn", "name": "Withdrawn", "description": "Proposal withdrawn by the Commission"},
]


EVENT_TYPES = [
    {"slug": "plenary_session", "name": "EP plenary session", "institution": "EP"},
    {"slug": "committee_meeting", "name": "EP committee meeting", "institution": "EP"},
    {"slug": "committee_week", "name": "EP committee week", "institution": "EP"},
    {"slug": "group_week", "name": "EP political group week", "institution": "EP"},
    {"slug": "recess", "name": "EP recess", "institution": "EP"},
    {"slug": "council_meeting", "name": "Council of the EU meeting", "institution": "COUNCIL"},
    {"slug": "informal_meeting", "name": "Informal Council meeting", "institution": "COUNCIL"},
    {"slug": "european_council_summit", "name": "European Council summit", "institution": "EUROPEAN_COUNCIL"},
    {"slug": "eurogroup", "name": "Eurogroup meeting", "institution": "COUNCIL"},
    {"slug": "commission_college_meeting", "name": "Commission College meeting", "institution": "COMMISSION"},
    {"slug": "court_hearing", "name": "CJEU hearing", "institution": "ECJ"},
    {"slug": "ecb_governing_council", "name": "ECB Governing Council meeting", "institution": "ECB"},
    {"slug": "agency_event", "name": "EU agency event", "institution": "AGENCY"},
    {"slug": "comitology_meeting", "name": "Comitology committee meeting", "institution": "COMMISSION"},
    {"slug": "expert_group_meeting", "name": "Expert group meeting", "institution": "COMMISSION"},
    {"slug": "conference", "name": "Third-party conference", "institution": "THIRD_PARTY"},
    {"slug": "webinar", "name": "Third-party webinar", "institution": "THIRD_PARTY"},
    {"slug": "roundtable", "name": "Third-party roundtable", "institution": "THIRD_PARTY"},
    {"slug": "training", "name": "Training session", "institution": "THIRD_PARTY"},
    {"slug": "workshop", "name": "Workshop", "institution": "THIRD_PARTY"},
    {"slug": "special_date", "name": "Special date / observance", "institution": "EU"},
    {"slug": "grant_deadline", "name": "Grant or call deadline", "institution": "COMMISSION"},
]


# ============================================================================
# Pydantic schemas
# ============================================================================


class _GenericListResponse(BaseModel):
    total: int
    data: List[Dict[str, Any]]
    generated_at: datetime = Field(default_factory=datetime.utcnow)


def _shape(items: List[Dict[str, Any]]) -> _GenericListResponse:
    return _GenericListResponse(total=len(items), data=items)


# ============================================================================
# Endpoints
# ============================================================================


@router.get("/institutions", response_model=_GenericListResponse, summary="EU institutions, agencies, and bodies")
async def list_institutions(user: User = Depends(api_user_with_rate_limit)) -> _GenericListResponse:
    return _shape(INSTITUTIONS)


@router.get("/committees", response_model=_GenericListResponse, summary="EP committees with full names")
async def list_committees(user: User = Depends(api_user_with_rate_limit)) -> _GenericListResponse:
    return _shape(EP_COMMITTEES_FULL)


@router.get("/directorates-general", response_model=_GenericListResponse, summary="Commission DGs")
async def list_dgs(user: User = Depends(api_user_with_rate_limit)) -> _GenericListResponse:
    return _shape(DGS)


@router.get("/political-groups", response_model=_GenericListResponse, summary="EP political groups")
async def list_political_groups(user: User = Depends(api_user_with_rate_limit)) -> _GenericListResponse:
    return _shape(POLITICAL_GROUPS)


@router.get("/countries", response_model=_GenericListResponse, summary="EU + EEA countries with ISO codes")
async def list_countries(user: User = Depends(api_user_with_rate_limit)) -> _GenericListResponse:
    return _shape(COUNTRIES)


@router.get("/languages", response_model=_GenericListResponse, summary="24 official EU languages with ISO-639 codes")
async def list_languages(user: User = Depends(api_user_with_rate_limit)) -> _GenericListResponse:
    return _shape(LANGUAGES)


@router.get("/procedure-types", response_model=_GenericListResponse, summary="Legislative procedure types (COD, NLE, INI, ...)")
async def list_procedure_types(user: User = Depends(api_user_with_rate_limit)) -> _GenericListResponse:
    return _shape(PROCEDURE_TYPES)


@router.get("/legal-bases", response_model=_GenericListResponse, summary="TFEU/TEU legal bases (selected)")
async def list_legal_bases(user: User = Depends(api_user_with_rate_limit)) -> _GenericListResponse:
    return _shape(LEGAL_BASES)


@router.get("/procedure-statuses", response_model=_GenericListResponse, summary="Procedure status enumeration")
async def list_procedure_statuses(user: User = Depends(api_user_with_rate_limit)) -> _GenericListResponse:
    return _shape(PROCEDURE_STATUSES)


@router.get("/event-types", response_model=_GenericListResponse, summary="Calendar event types")
async def list_event_types(user: User = Depends(api_user_with_rate_limit)) -> _GenericListResponse:
    return _shape(EVENT_TYPES)


@router.get("/document-types", response_model=_GenericListResponse, summary="OJ document types (live from eu_laws)")
async def list_document_types(
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> _GenericListResponse:
    rows = db.execute(
        select(func.coalesce(EULaw.doc_type_normalized, EULaw.doc_type), func.count())
        .where(func.coalesce(EULaw.doc_type_normalized, EULaw.doc_type).isnot(None))
        .group_by(func.coalesce(EULaw.doc_type_normalized, EULaw.doc_type))
        .order_by(func.count().desc())
    ).all()
    items = [
        {"slug": (r[0] or "unknown").lower().replace(" ", "_"), "name": r[0], "count": int(r[1])}
        for r in rows if r[0]
    ]
    return _shape(items)


@router.get("/policy-areas", response_model=_GenericListResponse, summary="Policy areas (live from eu_laws)")
async def list_policy_areas(
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> _GenericListResponse:
    rows = db.execute(
        select(EULaw.policy_area, func.count())
        .where(EULaw.policy_area.isnot(None))
        .group_by(EULaw.policy_area)
        .order_by(func.count().desc())
    ).all()
    items = [
        {"slug": (r[0] or "unknown").lower().replace(" ", "_").replace("/", "-"), "name": r[0], "count": int(r[1])}
        for r in rows if r[0]
    ]
    return _shape(items)


@router.get("/commissioners", response_model=_GenericListResponse, summary="College of Commissioners (27 members)")
async def list_commissioners(user: User = Depends(api_user_with_rate_limit)) -> _GenericListResponse:
    """List all 27 Commissioners with name, slug, portfolio, country, bio_url,
    and the canonical sources for their meeting agendas:

    - `agenda_url` — HTML calendar page on commission.europa.eu
    - `agenda_pdf_url` — direct PDF agenda when the commissioner publishes one
    - `unified_calendar_url` — single page listing meetings of all 27
    - `transparency_register_meetings_url` — TR meetings register filtered to
      this commissioner's host UUID (when known)

    Reads from commissioners.json via load_commissioner_profiles() — same source
    used by /commissioners/{name}/agenda.
    """
    from services.api_clients.commissioner_agenda_client import (
        load_commissioner_profiles,
    )

    UNIFIED_CALENDAR = (
        "https://commission.europa.eu/about/organisation/college-commissioners/"
        "calendar-items-president-and-commissioners_en"
    )

    profiles = load_commissioner_profiles()
    items = []
    for p in profiles:
        # Per-commissioner agendas are filtered views of the unified calendar.
        # The leader_id (resolved lazily) goes into the `f[0]=commissioner...`
        # filter; bio_url is the always-working entry point that the unified
        # page links from.
        leader_id = getattr(p, "leader_id", None)
        agenda_url = None
        if leader_id:
            agenda_url = (
                "https://commission.europa.eu/about/organisation/college-commissioners/"
                "calendar-items-president-and-commissioners_en"
                "?f%5B0%5D=commissioner_dynamic_commissioner_dynamic%3A"
                f"http%3A//publications.europa.eu/resource/authority/political-leader/{leader_id}"
            )
        items.append({
            "slug": p.slug,
            "name": p.name,
            "portfolio": p.portfolio,
            "country": p.country,
            "bio_url": p.bio_url,
            "agenda_url": agenda_url,            # Filtered unified-calendar URL (when leader_id known)
            "agenda_pdf_url": None,              # Reserved — most commissioners don't publish a PDF
            "unified_calendar_url": UNIFIED_CALENDAR,
            "type": "commissioner",
        })
    return _shape(sorted(items, key=lambda x: x["name"]))
