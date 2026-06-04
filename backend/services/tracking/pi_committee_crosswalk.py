"""
Policy-Interest -> EP-committee crosswalk.

The single hand-built artifact that lets My Tracked Files auto-populate from a
user's MEUB Policy Interests. Each Brubru PI leaf name (exact strings from
frontend policy_preferences_selector.tsx) maps to one or more EP committee codes.
Tracked files are then filtered by legislative_carriages.lead_committee.

This is the "thin" first piece of the hidden resolver deferred in Section 1. It
deliberately uses the controlled-vocabulary committee codes (clean) rather than
the carriages.policy_areas field (sparse, dirty, free-text). Widen later with the
OEIL-subject half + Victor's EC-department URL harvest.
"""

from typing import Iterable, List, Set

# PI leaf name -> EP committee code(s). Keys MUST match the leaf names in
# frontend/src/components/profile/policy_preferences_selector.tsx exactly.
PI_TO_COMMITTEES: dict[str, List[str]] = {
    # Core Economic and Market Policies
    "Single Market": ["IMCO"],
    "Competition": ["ECON", "IMCO"],
    "Trade and Economic Security": ["INTA"],
    "Economic and Financial Affairs": ["ECON"],
    "Taxation": ["ECON", "FISC"],
    "Customs": ["IMCO", "INTA"],
    "Business and Industry": ["ITRE", "IMCO"],
    # Sustainability and Environmental Policies
    "Climate Action": ["ENVI"],
    "Environment": ["ENVI"],
    "Energy": ["ITRE"],
    "Transport": ["TRAN"],
    # Digital Transformation
    "Digital Policy and Digital Economy": ["ITRE", "IMCO"],
    "Communication Networks, Content and Technology": ["ITRE", "CULT"],
    # Agriculture and Natural Resources
    "Agriculture": ["AGRI"],
    "Maritime Affairs and Fisheries": ["PECH"],
    "Food Safety": ["ENVI", "SANT", "AGRI"],
    # Cohesion and Development
    "Regional Policy": ["REGI"],
    "Research and Innovation": ["ITRE"],
    "Education, Training and Youth": ["CULT"],
    "Culture": ["CULT"],
    # Social Policies
    "Employment and Social Affairs": ["EMPL"],
    "Health": ["SANT", "ENVI"],
    "Consumer Protection": ["IMCO"],
    # Justice and Home Affairs
    "Justice and Fundamental Rights": ["JURI", "LIBE"],
    "Migration and Home Affairs": ["LIBE"],
    "Women's Rights and Gender Equality": ["FEMM"],
    # External Relations
    "Foreign and Security Policy": ["AFET", "SEDE"],
    "Development and Cooperation": ["DEVE"],
    "Neighbourhood and Enlargement": ["AFET"],
    "Human Rights and Democracy": ["AFET", "DROI"],
    "Humanitarian Aid and Civil Protection": ["DEVE"],
    # Emerging Strategic Areas
    "Defence and Security": ["SEDE", "AFET"],
    "Space Policy": ["ITRE", "SEDE"],
    "Statistics": ["ECON"],
}


def committees_for_interests(interests: Iterable[str]) -> Set[str]:
    """Resolve a list of PI leaf names to the union of their EP committee codes."""
    out: Set[str] = set()
    for leaf in interests or []:
        for code in PI_TO_COMMITTEES.get((leaf or "").strip(), []):
            out.add(code)
    return out


# Secondary match path for committee-less procedures (plenary RSP, some INI):
# PI leaf -> the carriages.policy_areas values it should also catch. The
# policy_areas field is AI-generated free text, so this is a best-effort overlap
# (committee matching remains the primary, reliable path).
PI_TO_POLICY_AREAS: dict[str, List[str]] = {
    "Single Market": ["Internal Market", "Single Market"],
    "Competition": ["Competition"],
    "Trade and Economic Security": ["International Trade", "Trade and Economic Security"],
    "Economic and Financial Affairs": ["Economic governance", "Economic and Financial Affairs"],
    "Taxation": ["Taxation"],
    "Customs": ["Customs"],
    "Business and Industry": ["Industry", "Business and Industry"],
    "Climate Action": ["Climate Action", "Environment"],
    "Environment": ["Environment"],
    "Energy": ["Energy"],
    "Transport": ["Transport"],
    "Digital Policy and Digital Economy": ["Digital single market", "Artificial intelligence", "Cybersecurity"],
    "Communication Networks, Content and Technology": ["Telecommunications", "5G/6G networks", "Digital infrastructure"],
    "Agriculture": ["Agriculture"],
    "Maritime Affairs and Fisheries": ["Fisheries", "Maritime Affairs and Fisheries"],
    "Food Safety": ["Food Safety"],
    "Regional Policy": ["Regional policy"],
    "Research and Innovation": ["Research", "New technologies"],
    "Education, Training and Youth": ["Education"],
    "Culture": ["Culture"],
    "Employment and Social Affairs": ["Employment", "Social affairs"],
    "Health": ["Health", "Public health"],
    "Consumer Protection": ["Consumer Protection", "Consumer protection"],
    "Justice and Fundamental Rights": ["Legal Affairs", "Justice", "Fundamental rights"],
    "Migration and Home Affairs": ["Security", "Migration"],
    "Women's Rights and Gender Equality": ["gender_equality", "Democracy"],
    "Foreign and Security Policy": ["Foreign affairs", "External action"],
    "Development and Cooperation": ["Development", "International Cooperation"],
    "Neighbourhood and Enlargement": ["External action"],
    "Human Rights and Democracy": ["Human rights", "Democracy"],
    "Humanitarian Aid and Civil Protection": ["Development"],
    "Defence and Security": ["Defence", "Security", "SAFE programme"],
    "Space Policy": ["Space"],
    "Statistics": ["Statistics"],
}


def policy_areas_for_interests(interests: Iterable[str]) -> Set[str]:
    """Resolve PI leaf names to the union of carriage policy_area strings to also match."""
    out: Set[str] = set()
    for leaf in interests or []:
        for pa in PI_TO_POLICY_AREAS.get((leaf or "").strip(), []):
            out.add(pa)
    return out


# Topic-relevance keywords (lowercase substrings) per PI leaf. A committee is a
# coarse proxy for a topic (ENVI = environment + health + food safety), so after
# committee/policy matching we require the file's title/summary to actually mention
# the user's topic. This filters out, e.g., ENVI's climate/transport/chemicals files
# for a user who only cares about food safety. Empty -> no keyword gate for that leaf.
PI_TO_KEYWORDS: dict[str, List[str]] = {
    "Single Market": ["single market", "internal market", "free movement", "mutual recognition", "services directive"],
    "Competition": ["competition", "antitrust", "state aid", "merger", "cartel", "foreign subsid"],
    "Trade and Economic Security": ["trade", "tariff", "anti-dumping", "anti-subsidy", "export control", "customs duties", "economic security", "free trade"],
    "Economic and Financial Affairs": ["economic", "financial", "banking", "capital market", "fiscal", "monetary", "euro area", "investment"],
    "Taxation": ["tax", "vat", "excise", "minimum tax", "pillar two"],
    "Customs": ["customs", "union customs code", "import", "tariff classification"],
    "Business and Industry": ["industr", "manufactur", "sme", "competitiveness", "steel", "critical raw material", "net zero industry"],
    "Climate Action": ["climate", "emission", "carbon", "net zero", "ets", "cbam", "greenhouse gas", "f-gas", "methane"],
    "Environment": ["environment", "biodiversity", "nature", "pollution", "water", "air quality", "waste", "circular economy", "chemical", "reach", "deforestation", "ecolabel"],
    "Energy": ["energy", "renewable", "electricity", "hydrogen", "nuclear", "grid", "gas market", "energy efficiency"],
    "Transport": ["transport", "mobility", "aviation", "rail", "maritime transport", "road", "vehicle", "drone", "shipping"],
    "Digital Policy and Digital Economy": ["digital", "artificial intelligence", " ai ", "data act", "platform", "cyber", "e-privacy", "online", "cloud", "chips"],
    "Communication Networks, Content and Technology": ["telecom", "spectrum", "5g", "6g", "broadband", "connectivity", "media", "audiovisual"],
    "Agriculture": ["agricultur", "agri-food", "agrifood", "farm", "livestock", "crop", "rural", "cap ", "common agricultural", "wine", "dairy", "organic", "pesticide", "fertilis", "plant variety", "geographical indication"],
    "Maritime Affairs and Fisheries": ["fish", "fisher", "aquacultur", "maritime", "ocean", "marine", "vessel", "seafood", "baltic sea", "mediterranean", "blue economy"],
    "Food Safety": ["food", "feed", "gmo", "genetically modified", "biocid", "pesticide", "novel food", "additive", "contaminant", "hygiene", "efsa", "plant health", "animal health", "veterinary", "labelling of"],
    "Regional Policy": ["cohesion", "regional", "structural fund", "interreg", "erdf", "outermost region"],
    "Research and Innovation": ["research", "innovation", "horizon europe", "deep tech", "patent"],
    "Education, Training and Youth": ["education", "training", "youth", "erasmus", "skills", "vocational"],
    "Culture": ["culture", "creative", "heritage", "audiovisual", "media literacy"],
    "Employment and Social Affairs": ["employment", "labour", "worker", "social", "pension", "platform work", "minimum wage", "working conditions"],
    "Health": ["health", "medicine", "pharmaceutic", "medical device", "cancer", "vaccine", "patient", "ema"],
    "Consumer Protection": ["consumer", "product safety", "warrant", "unfair commercial", "greenwashing"],
    "Justice and Fundamental Rights": ["justice", "rule of law", "fundamental rights", "data protection", "privacy", "judicial", "company law", "anti-corruption"],
    "Migration and Home Affairs": ["migration", "asylum", "border", "schengen", "visa", "police", "terrorism", "organised crime", "trafficking"],
    "Women's Rights and Gender Equality": ["gender", "women", "equality", "violence against women", "lgbti"],
    "Foreign and Security Policy": ["foreign", "cfsp", "sanction", "diplomacy", "third countr", "external action"],
    "Development and Cooperation": ["development", "cooperation", "global gateway", "humanitarian", "acp", "least developed"],
    "Neighbourhood and Enlargement": ["enlargement", "accession", "candidate", "western balkan", "neighbourhood", "pre-accession"],
    "Human Rights and Democracy": ["human rights", "democracy", "civil society", "press freedom"],
    "Humanitarian Aid and Civil Protection": ["humanitarian", "civil protection", "disaster", "emergency", "rescue"],
    "Defence and Security": ["defence", "defense", "military", "security and defence", "edf", "weapon", "armament"],
    "Space Policy": ["space", "satellite", "galileo", "copernicus", "launcher"],
    "Statistics": ["statistic", "eurostat", "indicator", "census"],
}


def keywords_for_interests(interests: Iterable[str]) -> Set[str]:
    """Lowercase relevance keywords for the user's interests (union)."""
    out: Set[str] = set()
    for leaf in interests or []:
        for kw in PI_TO_KEYWORDS.get((leaf or "").strip(), []):
            out.add(kw.lower())
    return out


# PI leaf name -> Commission Directorate-General code(s). Used to PI-filter the
# Commission Documents tab: those documents carry dg_responsible (not an EP
# committee), so the DG is the natural interest anchor. Codes match the
# `commission_documents.dg_responsible` values (e.g. AGRI, MARE, SANTE).
PI_TO_DGS: dict[str, List[str]] = {
    "Single Market": ["GROW"],
    "Competition": ["COMP"],
    "Trade and Economic Security": ["TRADE"],
    "Economic and Financial Affairs": ["ECFIN"],
    "Taxation": ["TAXUD"],
    "Customs": ["TAXUD"],
    "Business and Industry": ["GROW"],
    "Climate Action": ["CLIMA"],
    "Environment": ["ENV"],
    "Energy": ["ENER"],
    "Transport": ["MOVE"],
    "Digital Policy and Digital Economy": ["CNECT"],
    "Communication Networks, Content and Technology": ["CNECT"],
    "Agriculture": ["AGRI"],
    "Maritime Affairs and Fisheries": ["MARE"],
    "Food Safety": ["SANTE"],
    "Regional Policy": ["REGIO"],
    "Research and Innovation": ["RTD"],
    "Education, Training and Youth": ["EAC"],
    "Culture": ["EAC"],
    "Employment and Social Affairs": ["EMPL"],
    "Health": ["SANTE"],
    "Consumer Protection": ["JUST"],
    "Justice and Fundamental Rights": ["JUST"],
    "Migration and Home Affairs": ["HOME"],
    "Women's Rights and Gender Equality": ["JUST"],
    "Foreign and Security Policy": ["EEAS", "FPI"],
    "Development and Cooperation": ["INTPA"],
    "Neighbourhood and Enlargement": ["ENEST", "NEAR"],
    "Human Rights and Democracy": ["EEAS"],
    "Humanitarian Aid and Civil Protection": ["ECHO"],
    "Defence and Security": ["DEFIS"],
    "Space Policy": ["DEFIS"],
    "Statistics": ["ESTAT"],
}


def dgs_for_interests(interests: Iterable[str]) -> Set[str]:
    """Resolve PI leaf names to the union of their Commission DG codes."""
    out: Set[str] = set()
    for leaf in interests or []:
        for code in PI_TO_DGS.get((leaf or "").strip(), []):
            out.add(code)
    return out


# PI leaf name -> Council configuration code(s). Used to PI-filter My EU Calendar
# Council meetings (which carry `council_configuration`, not an EP committee).
# Codes match COUNCIL_CONFIGURATIONS in knowledge_base/eu_calendar_institutions.py.
PI_TO_COUNCIL_CONFIGS: dict[str, List[str]] = {
    "Single Market": ["COMPET"],
    "Competition": ["COMPET"],
    "Trade and Economic Security": ["FAC"],
    "Economic and Financial Affairs": ["ECOFIN", "EUROGROUP"],
    "Taxation": ["ECOFIN"],
    "Customs": ["COMPET", "ECOFIN"],
    "Business and Industry": ["COMPET"],
    "Climate Action": ["ENVI"],
    "Environment": ["ENVI"],
    "Energy": ["TTE"],
    "Transport": ["TTE"],
    "Digital Policy and Digital Economy": ["TTE", "COMPET"],
    "Communication Networks, Content and Technology": ["TTE"],
    "Agriculture": ["AGRIFISH"],
    "Maritime Affairs and Fisheries": ["AGRIFISH"],
    "Food Safety": ["AGRIFISH", "EPSCO"],
    "Regional Policy": ["GAC"],
    "Research and Innovation": ["COMPET"],
    "Education, Training and Youth": ["EDUC"],
    "Culture": ["EDUC"],
    "Employment and Social Affairs": ["EPSCO"],
    "Health": ["EPSCO"],
    "Consumer Protection": ["COMPET"],
    "Justice and Fundamental Rights": ["JHA"],
    "Migration and Home Affairs": ["JHA"],
    "Women's Rights and Gender Equality": ["EPSCO"],
    "Foreign and Security Policy": ["FAC"],
    "Development and Cooperation": ["FAC"],
    "Neighbourhood and Enlargement": ["GAC", "FAC"],
    "Human Rights and Democracy": ["FAC"],
    "Humanitarian Aid and Civil Protection": ["FAC"],
    "Defence and Security": ["FAC"],
    "Space Policy": ["COMPET"],
    "Statistics": ["ECOFIN"],
}


def council_configs_for_interests(interests: Iterable[str]) -> Set[str]:
    """Resolve PI leaf names to the union of their Council configuration codes."""
    out: Set[str] = set()
    for leaf in interests or []:
        for code in PI_TO_COUNCIL_CONFIGS.get((leaf or "").strip(), []):
            out.add(code)
    return out


# PI leaf name -> EU agency / body institution code(s) currently modelled in the
# calendar (EMA, ECB, ESMA, EBA, EIOPA). Sparse on purpose: many topical agencies
# (EFSA, ECHA, EEA, EMSA, EFCA, ENISA...) are not yet calendar institutions — widen
# this as the body registry grows (Phase B). Empty leaf -> no agency match.
PI_TO_AGENCIES: dict[str, List[str]] = {
    # Codes MUST be valid calendar institution_enum values (migration 102).
    "Economic and Financial Affairs": ["ECB", "EBA", "ESMA", "EIOPA", "AMLA", "EIB"],
    "Health": ["EMA", "ECDC"],
    "Food Safety": ["ECHA"],
    "Environment": ["ECHA"],
    "Energy": ["ACER"],
    "Transport": ["EMSA"],
    "Maritime Affairs and Fisheries": ["EMSA"],
    "Agriculture": ["CPVO"],
    "Justice and Fundamental Rights": ["FRA", "EUROJUST", "EDPS"],
    "Migration and Home Affairs": ["EUAA", "CEPOL", "EUROJUST"],
    "Employment and Social Affairs": ["EU_OSHA", "EUROFOUND"],
    "Research and Innovation": ["EIT"],
    "Digital Policy and Digital Economy": ["ENISA", "EUIPO"],
    "Communication Networks, Content and Technology": ["ENISA"],
    "Single Market": ["EUIPO"],
    "Foreign and Security Policy": ["EEAS"],
    "Defence and Security": ["EEAS"],
    "Human Rights and Democracy": ["FRA", "EEAS"],
}


def agencies_for_interests(interests: Iterable[str]) -> Set[str]:
    """Resolve PI leaf names to the union of their EU agency institution codes."""
    out: Set[str] = set()
    for leaf in interests or []:
        for code in PI_TO_AGENCIES.get((leaf or "").strip(), []):
            out.add(code)
    return out
