"""
Multilingual bridge for keyword-based guide retrieval.

Brubru's 544 knowledge guides are indexed by 11,462 keyword triggers, of which
about 2.3% are non-English. Guide retrieval is pure substring matching, so a
question asked in Spanish, Catalan, Italian, Dutch or French matched nothing at
all and the model answered ungrounded. Measured 6 August 2026, before this
module existed:

    "Cual es el estado del Reglamento de Inteligencia Artificial?"   0 guides
    "Quin es l'estat del Reglament d'Intel-ligencia Artificial?"     0 guides
    "Qual e lo stato della direttiva sulla due diligence?"           0 guides
    "Wat is de status van de AI-verordening?"                        0 guides

Zero retrieved guides is the pure hallucination case, in the five languages
Brubru differentiates on.

Approach: APPEND English equivalents of recognised EU-policy vocabulary to the
retrieval query rather than replacing the original text. Appending can only add
candidate matches, never remove one, so an English query is unaffected and a
mixed-language query keeps both halves working. This is a retrieval-time
augmentation only; it never touches what the user sees or what the model is
told the user said.

The vocabulary is grounded in the actual trigger corpus (the most frequent
content words across all 11,462 trigger keys) rather than a general-purpose
dictionary, so it covers the terms that can actually retrieve something.

The principled long-term fix is to embed the guides with the multilingual
bge-m3 model already in the stack and fall back to vector similarity when
keyword matching is thin. This module is the cheap, deterministic, zero-latency
step that stops non-English users getting nothing in the meantime.
"""

import re
import unicodedata
from typing import Dict, List, Set

# Non-English term -> English equivalent(s) used in the trigger corpus.
# Keys are accent-folded and lowercase; matching is word-boundary based.
# Ordered roughly by theme for maintenance, not by priority.
_TERM_MAP: Dict[str, str] = {
    # --- Legal instruments -------------------------------------------------
    "reglamento": "regulation", "reglament": "regulation",
    "reglement": "regulation", "regolamento": "regulation",
    "verordening": "regulation", "verordnung": "regulation",
    "directiva": "directive", "direttiva": "directive",
    "richtlijn": "directive", "richtlinie": "directive",
    "decision": "decision", "decisio": "decision", "decisione": "decision",
    "besluit": "decision", "beschluss": "decision",
    "recomendacion": "recommendation", "recomanacio": "recommendation",
    "raccomandazione": "recommendation", "aanbeveling": "recommendation",
    "dictamen": "opinion", "avis": "opinion", "parere": "opinion",
    "advies": "opinion",
    "comunicacion": "communication", "comunicacio": "communication",
    "comunicazione": "communication", "mededeling": "communication",
    "propuesta": "proposal", "proposta": "proposal",
    "proposition": "proposal", "voorstel": "proposal",
    "tratado": "treaty", "tractat": "treaty", "traite": "treaty",
    "trattato": "treaty", "verdrag": "treaty",
    "sentencia": "judgment", "sentenza": "judgment", "arret": "judgment",
    "arrest": "judgment", "sentencia del tribunal": "judgment",
    "acuerdo": "agreement", "acord": "agreement", "accord": "agreement",
    "accordo": "agreement", "overeenkomst": "agreement",
    "ley": "law", "llei": "law", "loi": "law", "legge": "law", "wet": "law",
    "acto delegado": "delegated act", "acte delegue": "delegated act",
    "atto delegato": "delegated act",
    "acto de ejecucion": "implementing act", "acte d'execution": "implementing act",

    # --- Institutions and actors ------------------------------------------
    "comision": "commission", "comissio": "commission",
    "commissione": "commission", "commissie": "commission",
    "parlamento": "parliament", "parlament": "parliament",
    "parlement": "parliament",
    "consejo": "council", "consell": "council", "conseil": "council",
    "consiglio": "council", "raad": "council",
    "tribunal de justicia": "court of justice", "cour de justice": "court of justice",
    "corte di giustizia": "court of justice", "hof van justitie": "court of justice",
    "comite": "committee", "comita": "committee", "commissione parlamentare": "committee",
    "commissie parlement": "committee",
    "ponente": "rapporteur", "relatore": "rapporteur",
    "rapporteur fictif": "shadow rapporteur", "ponente alternativo": "shadow rapporteur",
    "diputado": "mep", "diputat": "mep", "deputato": "mep",
    "eurodiputado": "mep", "europarlementarier": "mep",
    "presidencia": "presidency", "presidencia del consejo": "council presidency",
    "agencia": "agency", "agencia europea": "european agency",
    "agenzia": "agency", "agentschap": "agency",
    "estados miembros": "member states", "estats membres": "member states",
    "etats membres": "member states", "stati membri": "member states",
    "lidstaten": "member states",

    # --- Procedure and process --------------------------------------------
    "procedimiento": "procedure", "procediment": "procedure",
    "procedure legislative": "legislative procedure",
    "procedura": "procedure", "procedimento": "procedure",
    "votacion": "vote", "votacio": "vote", "vote": "vote",
    "votazione": "vote", "stemming": "vote",
    "enmienda": "amendment", "esmena": "amendment",
    "amendement": "amendment", "emendamento": "amendment",
    "amendementen": "amendment",
    "informe": "report", "informe parlamentario": "report",
    "rapport": "report", "relazione": "report", "verslag": "report",
    "pleno": "plenary", "ple": "plenary", "pleniere": "plenary",
    "plenaria": "plenary", "plenaire": "plenary",
    "entrada en vigor": "entry into force", "entree en vigueur": "entry into force",
    "entrata in vigore": "entry into force", "inwerkingtreding": "entry into force",
    "plazo": "deadline", "termini": "deadline", "delai": "deadline",
    "scadenza": "deadline", "termijn": "deadline",
    "transposicion": "transposition", "transposicio": "transposition",
    "recepimento": "transposition", "omzetting": "transposition",
    "consulta publica": "public consultation",
    "consultation publique": "public consultation",
    "consultazione pubblica": "public consultation",
    "openbare raadpleging": "public consultation",
    "estado": "status", "estat": "status", "statut": "status",
    "stato": "status", "toestand": "status",
    "obligaciones": "obligations", "obligacions": "obligations",
    "obblighi": "obligations", "verplichtingen": "obligations",
    "requisitos": "requirements", "requisits": "requirements",
    "exigences": "requirements", "requisiti": "requirements",
    "vereisten": "requirements",
    "sanciones": "sanctions", "sancions": "sanctions",
    "sanzioni": "sanctions", "sancties": "sanctions",
    "multa": "fine", "amenda": "fine", "amende": "fine", "boete": "fine",

    # --- Policy domains ----------------------------------------------------
    "residuos": "waste", "residus": "waste", "dechets": "waste",
    "rifiuti": "waste", "afval": "waste",
    "energia": "energy", "energie": "energy",
    "clima": "climate", "climat": "climate", "klimaat": "climate",
    "medio ambiente": "environment", "medi ambient": "environment",
    "environnement": "environment", "ambiente": "environment",
    "milieu": "environment",
    "comercio": "trade", "comerc": "trade", "commerce": "trade",
    "commercio": "trade", "handel": "trade",
    "aduanas": "customs", "duanes": "customs", "douane": "customs",
    "dogana": "customs",
    "salud": "health", "salut": "health", "sante": "health",
    "salute": "health", "gezondheid": "health",
    "medicamentos": "medicines", "medicaments": "medicines",
    "medicinali": "medicines", "geneesmiddelen": "medicines",
    "farmaceutico": "pharma", "pharmaceutique": "pharma",
    "agricultura": "agriculture", "agriculture": "agriculture",
    "landbouw": "agriculture",
    "pesca": "fisheries", "peche": "fisheries", "visserij": "fisheries",
    "alimentos": "food", "aliments": "food", "alimentaire": "food",
    "alimenti": "food", "voedsel": "food",
    "sanidad vegetal": "plant health", "sante des vegetaux": "plant health",
    "sanitat vegetal": "plant health",
    "sanidad animal": "animal health", "sante animale": "animal health",
    "indicacion geografica": "geographical indication",
    "indicacio geografica": "geographical indication",
    "indication geographique": "geographical indication",
    "indicazione geografica": "geographical indication",
    "geografische aanduiding": "geographical indication",
    "denominacion de origen": "geographical indication",
    "denominacio d origen": "geographical indication",
    "pinsos": "feed additives", "piensos": "feed additives",
    "mangimi": "feed additives", "diervoeder": "feed additives",
    "additius": "additives", "aditivos": "additives",
    "additifs": "additives", "additivi": "additives",
    "transporte": "transport", "transport": "transport",
    "trasporto": "transport", "vervoer": "transport",
    "digital": "digital", "numerique": "digital", "digitale": "digital",
    "inteligencia artificial": "artificial intelligence ai act",
    "intelligencia artificial": "artificial intelligence ai act",
    "intelligence artificielle": "artificial intelligence ai act",
    "intelligenza artificiale": "artificial intelligence ai act",
    "kunstmatige intelligentie": "artificial intelligence ai act",
    "datos": "data", "dades": "data", "donnees": "data",
    "dati": "data", "gegevens": "data",
    "proteccion de datos": "data protection gdpr",
    "proteccio de dades": "data protection gdpr",
    "protection des donnees": "data protection gdpr",
    "protezione dei dati": "data protection gdpr",
    "gegevensbescherming": "data protection gdpr",
    "ciberseguridad": "cybersecurity", "ciberseguretat": "cybersecurity",
    "cybersecurite": "cybersecurity", "cibersicurezza": "cybersecurity",
    "defensa": "defence", "defense": "defence", "difesa": "defence",
    "defensie": "defence",
    "migracion": "migration", "migracio": "migration",
    "migrazione": "migration", "migratie": "migration",
    "asilo": "asylum", "asile": "asylum", "asiel": "asylum",
    "fiscalidad": "taxation", "fiscalitat": "taxation",
    "fiscalite": "taxation", "fiscalita": "taxation", "belasting": "taxation",
    "competencia": "competition", "competencia deslleial": "competition",
    "concurrence": "competition", "concorrenza": "competition",
    "mededinging": "competition",
    "ayudas de estado": "state aid", "ajuts d'estat": "state aid",
    "aides d'etat": "state aid", "aiuti di stato": "state aid",
    "staatssteun": "state aid",
    "antidumping": "anti-dumping", "antidoumping": "anti-dumping",
    "quimicos": "chemicals", "quimics": "chemicals",
    "produits chimiques": "chemicals", "sostanze chimiche": "chemicals",
    "chemicalien": "chemicals",
    "aditivos para piensos": "feed additives",
    "additifs pour l'alimentation animale": "feed additives",
    "mercado interior": "single market internal market",
    "mercat interior": "single market internal market",
    "marche interieur": "single market internal market",
    "mercato interno": "single market internal market",
    "interne markt": "single market internal market",
    "financiacion": "funding", "finançament": "funding",
    "financement": "funding", "finanziamento": "funding",
    "financiering": "funding",
    "licitacion": "tender procurement", "licitacio": "tender procurement",
    "appel d'offres": "tender procurement", "gara d'appalto": "tender procurement",
    "aanbesteding": "tender procurement",
    "presupuesto": "budget", "pressupost": "budget",
    "bilancio": "budget", "begroting": "budget",
    "empresas": "companies business", "empreses": "companies business",
    "entreprises": "companies business", "imprese": "companies business",
    "bedrijven": "companies business",
    "pyme": "sme", "pime": "sme", "pmi": "sme", "mkb": "sme",
    "consumidores": "consumer protection", "consumidors": "consumer protection",
    "consommateurs": "consumer protection", "consumatori": "consumer protection",
    "consumenten": "consumer protection",
    "derechos": "rights", "drets": "rights", "droits": "rights",
    "diritti": "rights", "rechten": "rights",
    "trabajadores": "workers labour", "treballadors": "workers labour",
    "travailleurs": "workers labour", "lavoratori": "workers labour",
    "werknemers": "workers labour",
    "sostenibilidad": "sustainability", "sostenibilitat": "sustainability",
    "durabilite": "sustainability", "sostenibilita": "sustainability",
    "duurzaamheid": "sustainability",
    "economia circular": "circular economy",
    "economie circulaire": "circular economy",
    "economia circolare": "circular economy",
    "circulaire economie": "circular economy",
    "envases": "packaging", "envasos": "packaging", "emballages": "packaging",
    "imballaggi": "packaging", "verpakkingen": "packaging",
    "textil": "textiles", "textiles": "textiles", "tessile": "textiles",
    "pasaporte digital de producto": "digital product passport",
    "passaport digital de producte": "digital product passport",
    "passeport numerique de produit": "digital product passport",
    "passaporto digitale di prodotto": "digital product passport",
    "responsabilidad ampliada del productor": "extended producer responsibility epr",
    "responsabilitat ampliada del productor": "extended producer responsibility epr",
    "ampliacion": "enlargement", "ampliacio": "enlargement",
    "elargissement": "enlargement", "allargamento": "enlargement",
    "uitbreiding": "enlargement",
}

# Interrogatives and framing words worth folding so a short foreign question
# still carries its topic words into matching.
_STOPWORDS: Set[str] = {
    "que", "quin", "quina", "quins", "quines", "cual", "cuales", "quel",
    "quelle", "quali", "quale", "welke", "wat", "com", "como", "comment",
    "come", "hoe", "cuando", "quan", "quand", "quando", "wanneer",
    "donde", "on", "ou", "dove", "waar", "por", "per", "pour", "voor",
    "del", "della", "des", "van", "een", "het", "els", "les", "los", "las",
    "sobre", "su", "sur", "over", "amb", "con", "avec", "met", "und",
    "est", "es", "son", "sont", "sono", "zijn", "is", "the", "and", "for",
}

# Apostrophes SEPARATE tokens rather than joining them. Catalan and French
# elide constantly ("d'intel·ligència", "l'energie", "aides d'etat"), and
# treating "d'intelligencia" as one token meant the Catalan AI Act question
# matched nothing at all.
_WORD_RE = re.compile(r"[a-z0-9]+")


def _fold(text: str) -> str:
    """Lowercase, strip diacritics, and neutralise Catalan/French orthography.

    The interpunct is Catalan's signature character and it is NOT a combining
    mark, so NFD leaves it in place: "intel·ligencia" then tokenised as "intel"
    + "ligencia" and the Catalan AI Act question matched nothing. Apostrophes
    are elision marks in Catalan and French ("d'intel·ligència", "aides
    d'etat") and must separate tokens, not join them.
    """
    lowered = text.lower().replace("·", "").replace("‧", "")
    lowered = lowered.replace("'", " ").replace("’", " ")
    return "".join(
        c for c in unicodedata.normalize("NFD", lowered)
        if unicodedata.category(c) != "Mn"
    )


# Dictionary keys go through the SAME normalisation as queries, so a key
# written "aides d'etat" is stored as "aides d etat" and can actually match.
_TERM_MAP = {_fold(k): v for k, v in _TERM_MAP.items()}

# Multi-word keys must be tried before single words, longest first, so
# "inteligencia artificial" wins over a bare "artificial".
_MULTIWORD = sorted(
    (k for k in _TERM_MAP if " " in k), key=len, reverse=True
)
_SINGLEWORD = {k: v for k, v in _TERM_MAP.items() if " " not in k}


def _singular_forms(word: str) -> List[str]:
    """Candidate singular forms of a Romance/Germanic plural.

    Deliberately light. Over-stemming only costs extra candidate guides, which
    the relevance ranker then sorts, whereas UNDER-stemming costs the user
    every guide: "indicaciones geograficas", "indicazioni geografiche" and
    "geografische aanduidingen" are how people actually write, and none of
    them matched the singular dictionary key.
    """
    forms = [word]
    if len(word) > 4:
        if word.endswith("es"):
            forms.append(word[:-2])          # indicaciones -> indicacion
            forms.append(word[:-1])          # normes -> norme
        elif word.endswith("s"):
            forms.append(word[:-1])          # residus -> residu, dades -> dade
        if word.endswith("en"):
            forms.append(word[:-2])          # aanduidingen -> aanduiding
        if word.endswith("i"):
            forms.append(word[:-1] + "e")    # indicazioni -> indicazione
            forms.append(word[:-1] + "o")    # rifiuti -> rifiuto
        if word.endswith("he"):
            forms.append(word[:-2] + "a")    # geografiche -> geografica
        if word.endswith("ques"):
            forms.append(word[:-4] + "que")  # geographiques -> geographique (FR)
            forms.append(word[:-4] + "ca")   # geografiques  -> geografica   (CA)
        if word.endswith("gues"):
            forms.append(word[:-4] + "ga")   # amigues -> amiga (CA feminine)
    return forms


def english_terms_for(query: str) -> List[str]:
    """Return the English equivalents of EU-policy terms found in `query`.

    Returns an empty list for a query with no recognised foreign vocabulary,
    which is the common case for English input.
    """
    if not query:
        return []
    folded = _fold(query)
    tokens = [w for w in _WORD_RE.findall(folded) if w not in _STOPWORDS]
    # Every surface form we will accept, plurals folded to singular.
    variants: Set[str] = set()
    for tok in tokens:
        variants.update(_singular_forms(tok))

    found: List[str] = []
    seen: Set[str] = set()

    def add(english: str) -> None:
        for term in english.split():
            if term not in seen:
                seen.add(term)
                found.append(term)

    # Multi-word entries match when ALL of their words are present in the
    # query (in any order, singular or plural), not as a literal substring.
    matched_words: Set[str] = set()
    for phrase in _MULTIWORD:
        parts = phrase.split()
        if all(p in variants for p in parts):
            add(_TERM_MAP[phrase])
            matched_words.update(parts)

    for tok in tokens:
        for form in _singular_forms(tok):
            if form in matched_words:
                break
            english = _SINGLEWORD.get(form)
            if english:
                add(english)
                break
    return found


def bridge_query(query: str) -> str:
    """Append English equivalents to a non-English query for retrieval.

    Returns `query` unchanged when nothing is recognised, so English input and
    unrecognised text both behave exactly as before.
    """
    terms = english_terms_for(query)
    if not terms:
        return query
    return f"{query} {' '.join(terms)}"
