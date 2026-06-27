"""
Deterministic policy-area classifier (NO Anthropic).

Maps an EU object (news item, legislative carriage, ...) to canonical PI leaf
names from knowledge_base/policy_taxonomy.json, so every MEUB surface shares the
same `policy_areas` join key. Two signals:

  - body code (Commission DG / EP committee / Council config / agency) -> the
    leaves that list it (crosswalk reverse maps). High confidence.
  - curated `keywords` appearing in the title/summary -> those leaves.

Combination (precision first, honest blank last):
  body ∩ text  -> that intersection      (both agree: most precise)
  text only    -> the text leaves        (text-driven)
  one body leaf-> that leaf               (unambiguous body, e.g. DG AGRI)
  many body    -> all body leaves         (broad body remit, e.g. committee ENVI)
  nothing      -> []                      (leave blank, never force)
"""

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from services.tracking.pi_committee_crosswalk import (
    leaves_for_agency,
    leaves_for_committee,
    leaves_for_council_config,
    leaves_for_dg,
)

_TAXONOMY_PATH = (
    Path(__file__).resolve().parents[2] / "knowledge_base" / "policy_taxonomy.json"
)


@lru_cache(maxsize=1)
def _leaf_patterns() -> List[tuple]:
    """Per leaf: list of (kind, pattern). Single-word keywords match on a LEFT
    word boundary (so 'vat' no longer matches 'innovation', while stems like
    'agricultur' still match 'agricultural'); spaced/padded keywords (e.g.
    ' ai ', 'data act') keep precise substring matching."""
    with _TAXONOMY_PATH.open(encoding="utf-8") as fh:
        data = json.load(fh)
    leaves = [pa for c in data.get("categories", []) for pa in c.get("policy_areas", [])]
    out = []
    for pa in leaves:
        pats = []
        for k in pa.get("keywords", []):
            kl = k.lower()
            if " " in k:  # phrase or space-padded token -> substring as-is
                pats.append(("sub", kl))
            else:         # single token -> left word-boundary
                pats.append(("wb", re.compile(r"\b" + re.escape(kl))))
        out.append((pa["name"], pats))
    return out


def _text_leaves(text: str) -> set:
    t = (text or "").lower()
    res = set()
    for name, pats in _leaf_patterns():
        for kind, p in pats:
            if (kind == "sub" and p in t) or (kind == "wb" and p.search(t)):
                res.add(name)
                break
    return res


# --- Semantic fallback (added 27 Jun 2026) -------------------------------------- #
# The keyword pass above misses meaning-only titles ("Situation in Cuba",
# "Recent proposals to fight poverty", "AI continent action plan"). These ordered,
# high-precision rules encode the patterns learned from hand-classifying the carriage
# backlog, so new procedures don't land unclassified. They run ONLY when the primary
# pass returns nothing, so they can never disturb an existing classification.
# Topical rules are checked BEFORE geography (so "Ukraine Facility" -> Economic, not
# Foreign). Each rule: (PI leaf name, [substring triggers]). First hit wins.
_FALLBACK_TOPICAL = [
    ("Economic and Financial Affairs", ["recovery and resilience", "resilience plan", "excessive deficit", "discharge", "own resources", "capital requirements", "solvency", "securitis", "insolvency", "prudential", "crypto", "mica", "prospectus", "covered bond", "single resolution", "resolution fund", "resolution mechanism", "deposit insurance", "macroeconomic", "macro-prudential", "european semester", " banking", "venture capital", "crowdfunding", "shareholder", "market abuse", "derivativ", "ukraine facility", "ukraine support loan", "loan for ukraine", "ukrainian financ", "amending budget", "general budget", "fund-of-funds", "green bond", "retail invest", "retail payment", "six- and two-pack", "six-pack", "two-pack", "imbalance procedure", "bank recovery", "credit servicer", "non-performing", "npl", "supervisory mechanism", "central bank", "court of auditors", "auditors", "sustainable finance", "transparency requirements", "debt management", "stability instrument financ"]),
    ("Taxation", ["transfer pricing", "country-by-country", "debra", "debt-equity bias", " vat ", "taxation", "tax avoidance", "tax fraud"]),
    ("Migration and Home Affairs", ["asylum", "migrant", "migration", "return directive", "return of third-country", "action plan on return", "action plan against migrant", "dublin", "frontex", "eurodac", "blue card", "resettlement", "reception condition", "qualification directive", "safe countr", "smuggling", "unauthorised entry", "single permit", "talent pool", "relocation mechanism", "long-term resident", "long term resident", "third-country nationals", "third country nationals", "european travel document", "solidarity pool", "integration of migrants"]),
    ("Justice and Fundamental Rights", ["corruption", "money laundering", "europol", "eurojust", "eppo", "public prosecutor", "criminal matter", "criminal proceed", "criminal law", "confiscation", "victims", "radicalis", "petition", "small claims", "service of documents", "taking of evidence", "investigation order", "child sexual abuse", "slapp", "abusive litigation", "firearms", "non-cash", "counterfeiting", "non-conviction", "restrictive measures directive", "violation of union restrictive", "e-evidence", "electronic evidence", "internal security", "security union", "europol", "law enforcement"]),
    ("Human Rights and Democracy", ["political prisoner", "death penalty", "genocide", "human rights", "arbitrary detention", "oppression", "conversion practices", "political parties", "antisemitism", "suppression of ethnic", "imminent death", "executions", "repression", "democratic resilience", "democratic accountability", "rule of law"]),
    ("Women's Rights and Gender Equality", ["abortion", "gender equality", "women's rights", "proxy voting during pregnancy"]),
    ("Employment and Social Affairs", ["poverty", "housing", "social security", "disabilit", "globalisation adjustment", "globalisation fund", "work-life", "working parent", "social fund", "talent pool", "social affairs", "social security number", "housing exclusion"]),
    ("Digital Policy and Digital Economy", [" ai ", "artificial intelligence", "ai continent", "digital", "cyber", "interoperab", "quantum", "e-government", "data act", "non-personal data", "business wallet", "high performance computing", "information security", "managed security services", "digital identity"]),
    ("Energy", ["repower", "biofuel", "heating and cooling", "decarbonisation", "alternative fuels", "gas storage", "gas supply", "electricity market", "electrification", "security of gas", "natural gas", "renewable"]),
    ("Climate Action", ["cbam", "carbon border", "emission", "effort-sharing", "decarbonisation fund", "just transition", "climate", "global warming", "market stability reserve", "ets ", "emissions trading"]),
    ("Health", ["tobacco", "obesity", "cardiovascular", "medicinal product", "medical device", "rare disease", "implantable", "human organs", "nitrous oxide", "drugs agency", "marketing authorisation", "pharmaceutical", "health data space"]),
    ("Agriculture", ["reproductive material", "plant protection", "genomic techniques", "coffee agreement", "cocoa", "geographical indication", "organic", "forest reproductive", "plant reproductive", "common organisation of the market", "agricultur"]),
    ("Food Safety", ["food law", "food information", "food safety"]),
    ("Maritime Affairs and Fisheries", ["fisher", "maritime", "passenger ship", "ro-ro", "ferries", "sailing on board", "passenger craft", "fishery products"]),
    ("Transport", ["tachograph", "airworthiness", "hyperloop", "tolling", "multimodal", "rail passenger", "railway", "bus services", "weights and dimensions", "alternative fuels infrastructure", "seasonal changes of time", "driving times", "electronic toll"]),
    ("Trade and Economic Security", ["ttip", "procurement instrument", "anti-coercion", "trade defence", "international procurement"]),
    ("Single Market", ["public procurement", "procurement", "standardis", "geo-blocking", "services e-card", "service e-card", "professional qualif", "regulation of professions", "designs", "notification procedure", "thresholds for", "postal services", "delivery act", "new legislative framework", "market surveillance", "solvit", "internal market"]),
    ("Consumer Protection", ["toy safety", "package travel", "product liability", "product safety", "alternative dispute resolution", "consumer"]),
    ("Defence and Security", ["defence", "critical infrastructure", "security sector reform", "naval", "atalanta", "military"]),
    ("Development and Cooperation", ["sustainable development", "development fund", "development cooperation"]),
    ("Humanitarian Aid and Civil Protection", ["solidarity fund", "civil protection", "humanitarian", "disaster", "floods", "extreme weather", "readiness"]),
    ("Education, Training and Youth", ["erasmus", "europass", "solidarity corps", "right to play", "youth", "education", "training"]),
    ("Culture", ["copyright", "marrakesh", "videogame", "cultural", "tourism"]),
    ("Regional Policy", ["committee of the regions", "cohesion", "regional development"]),
    ("Statistics", ["statistics", "classification of products", "statistical"]),
    ("Customs", ["customs", "cash entering or leaving", "cash controls"]),
    ("Business and Industry", ["28th regime", "eu inc", "biotech act", "advanced materials", "start-up", "scale-up", "secondary raw materials", "bioeconomy", "industrial", "raw materials", "red tape", "sustainability reporting", "corporate sustainability", "due diligence", "insolvency law"]),
    ("Communication Networks, Content and Technology", ["electronic communications", "berec", "roaming", "broadband", "connectivity"]),
    ("Research and Innovation", ["research", "innovation", "horizon europe"]),
    ("Space Policy", ["space programme", "satellite", "galileo", "copernicus"]),
    ("Environment", ["landfill", " soil", "groundwater", "nature restoration", "environmental impact", "inspire directive", "batteries", "waste", "biocidal", "environment through criminal", "circular economy"]),
]
# Non-EU country / region names -> Foreign and Security Policy (checked last). EU member
# states are deliberately absent (they appear in RRF / appointment contexts, not foreign
# policy). Kept to clear, unambiguous foreign-affairs signals.
_FALLBACK_GEO = [
    "cuba", "iran", "iranian", "syria", "niger", "belarus", "nicaragua", "venezuela",
    "georgia", "georgian", "armenia", "azerbaijan", "russia", "russian", "lebanon",
    "china", "chinese", "congo", "gibraltar", "sudan", "myanmar", "libya", "somalia",
    "ukraine", "ukrainian", "great lakes", "northeast syria", "pontos", "belarus",
]


def _semantic_fallback(text: str) -> List[str]:
    t = f" {(text or '').lower()} "
    for leaf, triggers in _FALLBACK_TOPICAL:
        if any(trig in t for trig in triggers):
            return [leaf]
    for geo in _FALLBACK_GEO:
        if f" {geo}" in t or f"{geo} " in t:
            return ["Foreign and Security Policy"]
    return []


def classify(
    title: str,
    summary: str = "",
    *,
    dg: Optional[str] = None,
    committee: Optional[str] = None,
    council_config: Optional[str] = None,
    agency: Optional[str] = None,
) -> List[str]:
    """Return canonical PI leaf names for this object (possibly empty)."""
    text_leaves = _text_leaves(f"{title or ''} {summary or ''}")

    body: set = set()
    for code, fn in (
        (dg, leaves_for_dg),
        (committee, leaves_for_committee),
        (council_config, leaves_for_council_config),
        (agency, leaves_for_agency),
    ):
        if code:
            body |= set(fn(code))

    inter = text_leaves & body
    if inter:
        return sorted(inter)
    if text_leaves:
        return sorted(text_leaves)
    if len(body) == 1:
        return list(body)
    if body:
        return sorted(body)
    # nothing from keyword/body pass -> try the semantic fallback before giving up.
    return _semantic_fallback(f"{title or ''} {summary or ''}")
