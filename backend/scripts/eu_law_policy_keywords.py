"""Title keyword map for EU law policy areas (the eu_laws taxonomy).

Moved out of scripts/final_classification.py on 15 Sep 2026 so the recurring
Cellar ingest (scripts/sync_eu_laws_from_cellar.py) can import it in production,
where the backend runs from /app with no `backend` package and
final_classification's module-level `from backend.core...` imports would fail.
No imports beyond typing, on purpose.
"""

from typing import Dict, List, Tuple

AGGRESSIVE_KEYWORDS: Dict[str, List[Tuple[str, float]]] = {
    "Climate Action": [
        ("climate", 3.0), ("emission", 3.0), ("carbon", 3.0), ("greenhouse", 3.0),
        ("ets", 3.0), ("co2", 3.0), ("decarbonisation", 3.0), ("net zero", 2.0),
        ("ozone", 2.0), ("fluorinated", 2.0),
    ],
    "Environment": [
        ("environment", 3.0), ("environmental", 3.0), ("pollution", 3.0), ("waste", 3.0),
        ("water", 2.0), ("air quality", 2.0), ("biodiversity", 2.0), ("nature", 2.0),
        ("habitat", 2.0), ("species", 2.0), ("conservation", 2.0), ("recycling", 2.0),
        ("hazardous", 1.5), ("chemical", 1.5), ("pesticide", 2.0),
    ],
    "Digital Policy and Digital Economy": [
        ("digital", 3.0), ("platform", 2.0), ("data", 1.5), ("online", 2.0),
        ("internet", 2.0), ("e-commerce", 3.0), ("artificial intelligence", 3.0),
        ("algorithm", 2.0), ("cybersecurity", 2.0), ("electronic signature", 2.0),
        ("software", 2.0),
    ],
    "Energy": [
        ("energy", 3.0), ("renewable", 3.0), ("electricity", 3.0), ("gas", 2.0),
        ("nuclear", 2.5), ("power plant", 2.0), ("solar", 2.0), ("wind energy", 2.0),
        ("hydropower", 2.0), ("energy efficiency", 3.0), ("atomic", 2.0),
        ("euratom", 3.0), ("radioactive", 2.0), ("reactor", 2.0),
    ],
    "Transport": [
        ("transport", 3.0), ("aviation", 3.0), ("maritime", 2.5), ("railway", 3.0),
        ("road", 2.0), ("vehicle", 2.5), ("shipping", 2.0), ("aircraft", 2.5),
        ("mobility", 2.0), ("traffic", 2.0), ("airport", 2.5), ("aerospace", 2.5),
        ("motor", 2.0), ("driver", 2.0), ("tyre", 2.0), ("airline", 3.0),
        ("inland waterway", 3.0), ("navigation", 1.5), ("rail", 2.0),
    ],
    "Competition": [
        ("competition", 3.0), ("antitrust", 3.0), ("merger", 3.0), ("state aid", 3.0),
        ("cartel", 3.0), ("dominant position", 2.0), ("concentration", 1.5),
    ],
    "Single Market": [
        ("single market", 3.0), ("internal market", 3.0), ("free movement", 3.0),
        ("harmonisation", 2.0), ("mutual recognition", 2.0), ("establishment", 1.5),
        ("textile", 2.0), ("cosmetic", 2.0), ("toy", 2.0), ("machinery", 2.0),
        ("labelling", 1.5), ("packaging", 1.5), ("marking", 1.0),
        ("type-approval", 2.5), ("standardisation", 2.0), ("conformity", 2.0),
    ],
    "Trade and Economic Security": [
        ("trade", 3.0), ("tariff", 3.0), ("import", 2.0), ("export", 2.0),
        ("trade agreement", 3.0), ("anti-dumping", 3.0), ("trade defence", 3.0),
        ("quota", 2.0), ("countervailing", 3.0), ("safeguard measure", 2.0),
        ("generalised scheme of preferences", 3.0), ("originating product", 2.0),
        ("third country", 1.5),
    ],
    "Agriculture": [
        ("agriculture", 3.0), ("agricultural", 3.0), ("farming", 3.0), ("rural", 3.0),
        ("common agricultural policy", 3.0), ("crop", 2.0), ("livestock", 2.0),
        ("wine", 2.0), ("olive", 2.0), ("sugar", 2.0), ("cereal", 2.0),
        ("fruit", 1.5), ("vegetable", 1.5), ("tobacco", 2.0), ("seed", 1.5),
        ("plant health", 2.5), ("phytosanitary", 3.0), ("plant protection", 2.5),
        ("organic farming", 3.0), ("geographical indication", 2.5),
        ("designation of origin", 2.5), ("beef", 2.0), ("pork", 2.0),
        ("poultry", 2.0), ("milk", 2.0), ("dairy", 2.0), ("cotton", 2.0),
        ("hops", 2.0), ("flax", 2.0), ("hemp", 2.0),
    ],
    "Maritime Affairs and Fisheries": [
        ("fisheries", 3.0), ("fishing", 3.0), ("fish", 2.0), ("aquaculture", 3.0),
        ("common fisheries policy", 3.0), ("catch", 1.5), ("vessel", 2.0),
        ("tuna", 2.0), ("cod", 2.0), ("herring", 2.0), ("mackerel", 2.0),
        ("total allowable catch", 3.0),
    ],
    "Food Safety": [
        ("food safety", 3.0), ("food", 2.0), ("hygiene", 3.0), ("foodstuff", 3.0),
        ("nutrition", 2.0), ("food additive", 3.0), ("efsa", 2.0), ("novel food", 3.0),
        ("veterinary", 3.0), ("animal health", 3.0), ("zoonoses", 3.0),
        ("feed", 1.5), ("slaughter", 2.0), ("animal welfare", 2.5),
        ("animal by-product", 3.0), ("contaminant", 2.0), ("residue", 1.5),
        ("maximum residue", 3.0), ("flavouring", 2.0), ("sweetener", 2.0),
    ],
    "Health": [
        ("health", 2.5), ("medicine", 3.0), ("pharmaceutical", 3.0), ("medical", 3.0),
        ("medicinal product", 3.0), ("medical device", 3.0), ("public health", 3.0),
        ("disease", 2.0), ("vaccine", 3.0), ("clinical trial", 3.0),
        ("orphan medicinal", 3.0), ("blood", 2.0), ("tissue", 2.0), ("organ", 2.0),
    ],
    "Employment and Social Affairs": [
        ("employment", 3.0), ("worker", 3.0), ("labour", 3.0), ("social", 2.0),
        ("working conditions", 3.0), ("workplace", 2.0), ("employee", 2.0),
        ("social security", 3.0), ("posted worker", 3.0), ("occupational safety", 3.0),
        ("collective redundancy", 3.0), ("working time", 3.0), ("equal pay", 3.0),
    ],
    "Consumer Protection": [
        ("consumer", 3.0), ("product safety", 3.0), ("consumer rights", 3.0),
        ("consumer protection", 3.0), ("unfair commercial", 3.0),
        ("product liability", 2.0), ("warranty", 2.0),
    ],
    "Justice and Fundamental Rights": [
        ("justice", 3.0), ("fundamental rights", 3.0), ("data protection", 3.0),
        ("privacy", 3.0), ("gdpr", 3.0), ("personal data", 3.0),
        ("judicial cooperation", 3.0), ("rule of law", 2.0), ("charter", 2.0),
        ("drug", 2.0), ("narcotic", 3.0), ("precursor", 2.0),
        ("criminal", 2.5), ("prosecution", 2.5), ("victim", 2.0),
        ("money laundering", 3.0), ("terrorist", 2.0), ("fraud", 2.0),
        ("mutual legal assistance", 3.0), ("extradition", 3.0),
    ],
    "Migration and Home Affairs": [
        ("migration", 3.0), ("asylum", 3.0), ("border", 3.0), ("visa", 3.0),
        ("schengen", 3.0), ("refugee", 2.0), ("immigration", 3.0),
        ("frontex", 2.0), ("residence permit", 3.0), ("third-country national", 3.0),
    ],
    "Research and Innovation": [
        ("research", 3.0), ("innovation", 3.0), ("horizon", 3.0), ("r&d", 3.0),
        ("science", 2.0), ("framework programme", 3.0), ("laboratory", 2.0),
    ],
    "Education, Training and Youth": [
        ("education", 3.0), ("training", 2.0), ("erasmus", 3.0), ("student", 2.0),
        ("youth", 3.0), ("learning", 2.0), ("vocational", 2.5), ("diploma", 2.5),
        ("qualification", 2.0),
    ],
    "Regional Policy": [
        ("regional", 3.0), ("cohesion", 3.0), ("structural funds", 3.0),
        ("regional development", 3.0), ("erdf", 3.0), ("cohesion fund", 3.0),
        ("outermost region", 3.0), ("interreg", 3.0),
    ],
    "Taxation": [
        ("tax", 3.0), ("taxation", 3.0), ("vat", 3.0), ("excise", 3.0),
        ("fiscal", 2.0), ("tax avoidance", 3.0), ("tax evasion", 3.0),
        ("duty", 1.5), ("stamp duty", 2.0),
    ],
    "Economic and Financial Affairs": [
        ("financial", 3.0), ("banking", 3.0), ("finance", 3.0), ("capital markets", 3.0),
        ("payment", 2.0), ("financial services", 3.0), ("monetary", 2.0),
        ("accounting", 2.5), ("audit", 2.0), ("insurance", 3.0), ("credit", 2.0),
        ("bank", 2.5), ("securities", 2.5), ("investment fund", 3.0), ("euro", 2.0),
        ("exchange rate", 2.5), ("central bank", 3.0), ("ecb", 3.0),
        ("prudential", 3.0), ("solvency", 3.0),
    ],
    "Defence and Security": [
        ("defence", 3.0), ("defense", 3.0), ("military", 3.0), ("armament", 3.0),
        ("defence industry", 3.0), ("arms", 2.0), ("dual-use", 2.5),
        ("weapon", 2.5), ("explosive", 2.0), ("firearm", 3.0),
    ],
    "Foreign and Security Policy": [
        ("foreign policy", 3.0), ("external action", 3.0), ("cfsp", 3.0),
        ("eeas", 2.0), ("sanctions", 3.0), ("restrictive measure", 3.0),
        ("embargo", 3.0), ("common position", 2.0), ("joint action", 2.0),
        ("association agreement", 3.0), ("partnership agreement", 2.0),
    ],
    "Communication Networks, Content and Technology": [
        ("telecommunication", 3.0), ("spectrum", 3.0), ("broadband", 3.0),
        ("5g", 3.0), ("telecom", 3.0), ("electronic communications", 3.0),
        ("roaming", 3.0), ("frequency", 2.0), ("postal", 2.0),
    ],
    "Customs": [
        ("customs", 3.0), ("customs union", 3.0), ("customs code", 3.0),
        ("customs procedure", 3.0), ("customs duty", 3.0), ("customs tariff", 3.0),
        ("combined nomenclature", 3.0), ("tariff classification", 3.0),
        ("inward processing", 3.0), ("outward processing", 3.0),
    ],
    "Business and Industry": [
        ("industry", 3.0), ("industrial", 3.0), ("sme", 2.0),
        ("small and medium", 2.0), ("manufacturing", 2.0), ("company law", 3.0),
        ("corporate governance", 3.0), ("insolvency", 2.5), ("patent", 2.5),
        ("trademark", 2.5), ("intellectual property", 3.0), ("copyright", 2.5),
        ("design protection", 2.5),
    ],
    "Culture": [
        ("culture", 3.0), ("cultural", 3.0), ("heritage", 3.0), ("creative", 2.0),
        ("audiovisual", 3.0), ("media", 2.0), ("broadcasting", 2.5), ("film", 2.0),
        ("sport", 2.0),
    ],
    "Space Policy": [
        ("space", 3.0), ("satellite", 3.0), ("galileo", 3.0), ("copernicus", 3.0),
        ("space programme", 3.0), ("orbit", 2.0),
    ],
    "Statistics": [
        ("statistics", 3.0), ("statistical", 3.0), ("eurostat", 3.0),
        ("census", 2.0), ("nomenclature", 1.5), ("nace", 2.5),
    ],
    "Development and Cooperation": [
        ("development cooperation", 3.0), ("development aid", 3.0),
        ("developing countries", 3.0), ("acp", 2.0), ("overseas", 2.0),
    ],
    "Neighbourhood and Enlargement": [
        ("enlargement", 3.0), ("neighbourhood", 3.0), ("candidate country", 3.0),
        ("accession", 3.0), ("pre-accession", 3.0), ("stabilisation", 2.0),
    ],
    "Human Rights and Democracy": [
        ("human rights", 3.0), ("democracy", 3.0), ("civil society", 2.0),
        ("fundamental freedom", 3.0), ("non-discrimination", 2.5), ("equality", 2.0),
    ],
    "Humanitarian Aid and Civil Protection": [
        ("humanitarian", 3.0), ("civil protection", 3.0), ("disaster", 2.0),
        ("emergency", 2.0), ("relief", 2.0),
    ],
    "Budget and Financial Management": [
        ("budget", 3.0), ("budgetary", 3.0), ("financial regulation", 3.0),
        ("revenue", 2.0), ("expenditure", 2.0), ("own resources", 3.0),
        ("multiannual financial framework", 3.0), ("appropriation", 2.0),
        ("court of auditors", 3.0), ("discharge", 2.0),
    ],
    "Institutional Affairs": [
        ("institutional", 2.5), ("interinstitutional", 3.0), ("staff regulation", 3.0),
        ("official", 1.5), ("seat", 1.5), ("protocol", 1.0),
        ("privileges and immunities", 3.0), ("rules of procedure", 3.0),
    ],
}
