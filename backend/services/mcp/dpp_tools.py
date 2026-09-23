"""Tool surface for the "Brubru DPP" MCP server.

The first per-client, on-demand MCP: a scoped server built for Terraqui and the
LIFE DPP-TEX project (Joana Castella), whose remit is the EU Digital Product
Passport and the textile circularity law around it.

Scope, decided with Victor on 11 Aug 2026:
  * the DPP corpus itself   -> economy_items where body_code='dpp' (122 rows,
    9 resources: the 13 acts with full legal text, sector rollout dates, the
    registry, the six harmonised standards, the 71 battery data points,
    guidance, audience guides, news and events)
  * textile EPR             -> Directive (EU) 2025/1892, already one of the acts
  * consultations           -> the ecodesign/textile slice of Have Your Say,
    including initiative 16116, the ESPR delegated act on apparel textiles
  * the Ecodesign Forum     -> ESPR Art. 19 and its Art. 20 Member States
    Expert Group, from the Commission expert-groups register

`search` and `fetch` are NOT optional extras: ChatGPT's connector requires that
exact pair, so they are implemented here scoped to this corpus rather than the
whole of Brubru.

Every tool reads from the database only. Nothing here calls out to EUR-Lex or
the Commission at request time, so an answer never depends on a third party
being up.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text

from services.mcp.tools import COST_LIGHT_MCP, McpTool, _get_db

logger = logging.getLogger(__name__)

BODY = "dpp"

# The consultation slice that matters to a textile/ecodesign watcher. Kept as a
# LIKE list rather than a policy-area filter because Have Your Say's own topic
# codes put the textile delegated act under Environment, next to a great deal
# that has nothing to do with products.
_CONSULT_TERMS = ("ecodesign", "textile", "apparel", "product passport",
                  "circular", "waste")


def _rows(sql: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
    db = _get_db()
    try:
        return [dict(r._mapping) for r in db.execute(text(sql), params).fetchall()]
    finally:
        db.close()


# --------------------------------------------------------------------------- #
# handlers
# --------------------------------------------------------------------------- #

def _items(item_type: str, q: Optional[str] = None, limit: int = 25,
           with_body: bool = False) -> List[Dict[str, Any]]:
    cols = ("id, title, summary, public_url, document_date"
            + (", body_txt" if with_body else ""))
    sql = (f"SELECT {cols} FROM economy_items "
           "WHERE body_code = :b AND item_type = :t")
    params: Dict[str, Any] = {"b": BODY, "t": item_type, "lim": limit}
    if q:
        sql += " AND (title ILIKE :q OR summary ILIKE :q OR body_txt ILIKE :q)"
        params["q"] = f"%{q}%"
    sql += " ORDER BY document_date DESC NULLS LAST, id LIMIT :lim"
    return _rows(sql, params)


# Words that carry no signal in a question. Includes Catalan and Spanish because
# Terraqui works in Catalan and Joana will ask in it.
_STOPWORDS = {
    # English
    "a", "об", "об", "the", "is", "are", "was", "were", "be", "been", "what", "when",
    "which", "who", "whom", "how", "why", "where", "does", "do", "did", "can", "could",
    "should", "would", "will", "shall", "must", "may", "might", "have", "has", "had",
    "of", "for", "to", "in", "on", "at", "by", "with", "from", "about", "into", "and",
    "or", "but", "not", "no", "any", "all", "there", "this", "that", "these", "those",
    "it", "its", "my", "our", "your", "their", "me", "we", "you", "they", "i",
    "please", "tell", "give", "show", "need", "want", "know", "get", "make", "under",
    # Catalan / Spanish
    "el", "la", "els", "les", "un", "una", "uns", "unes", "que", "qui", "quan", "com",
    "on", "per", "amb", "sobre", "des", "del", "dels", "als", "hi", "ha", "es", "son",
    "sera", "seran", "estan", "esta", "aixo", "aquest", "aquesta", "aquests", "meu",
    "nostre", "vull", "vols", "cal", "quins", "quines", "quina", "quin",
    "los", "las", "unos", "unas", "y", "o", "de", "en", "con", "sobre", "cual",
    "cuando", "como", "donde", "porque", "hay", "esta", "estan", "sera", "seran",
    "este", "esta", "estos", "estas", "mi", "nuestro", "quiero", "necesito",
}


# Domain vocabulary the general query bridge does not carry. The bridge knows
# broad EU-policy words; it does not know that "normes harmonitzades" is
# "harmonised standards" or that "ecodisseny" is "ecodesign". Terraqui works in
# Catalan and this server is entirely about this vocabulary, so the gap is the
# normal case here rather than an edge case. Longest phrases first so
# "passaport digital de producte" wins over "passaport".
_DOMAIN_TERMS: List[Tuple[str, str]] = [
    ("passaport digital de producte", "digital product passport"),
    ("pasaporte digital de producto", "digital product passport"),
    ("passaport digital", "digital product passport"),
    ("pasaporte digital", "digital product passport"),
    ("normes harmonitzades", "harmonised standards"),
    ("normas armonizadas", "harmonised standards"),
    ("actes delegats", "delegated act"),
    ("actos delegados", "delegated act"),
    ("consulta publica", "consultation"),
    ("punts de dades", "data points"),
    ("puntos de datos", "data points"),
    ("residus textils", "textile waste"),
    ("residuos textiles", "textile waste"),
    ("passaport", "passport"),
    ("pasaporte", "passport"),
    ("ecodisseny", "ecodesign"),
    ("ecodiseno", "ecodesign"),
    ("registre", "registry"),
    ("registro", "registry"),
    ("reglament", "regulation"),
    ("reglamento", "regulation"),
    ("directiva", "directive"),
    ("bateries", "batteries"),
    ("baterias", "batteries"),
    ("textils", "textiles"),
    ("textil", "textile"),
    ("residus", "waste"),
    ("residuos", "waste"),
    ("obligatori", "mandatory"),
    ("obligatorio", "mandatory"),
    ("termini", "deadline"),
    ("plazo", "deadline"),
    ("duana", "customs"),
    ("aduana", "customs"),
    ("fabricant", "manufacturer"),
    ("fabricante", "manufacturer"),
    ("etiquetatge", "labelling"),
    ("etiquetado", "labelling"),
    ("empremta de carboni", "carbon footprint"),
    ("huella de carbono", "carbon footprint"),
]


def _domain_bridge(question: str) -> str:
    """Append English domain terms for any Catalan/Spanish phrase recognised."""
    import unicodedata as _ud

    folded = "".join(c for c in _ud.normalize("NFD", (question or "").lower())
                     if _ud.category(c) != "Mn")
    extra, used = [], set()
    for src, en in _DOMAIN_TERMS:
        if src in folded and en not in used:
            used.add(en)
            extra.append(en)
    return f"{question} {' '.join(extra)}" if extra else question


def _terms(question: str) -> List[str]:
    """The words worth searching for in a question.

    Matching the RAW question with ILIKE was the original behaviour and it meant
    every natural question returned nothing: no row contains the literal string
    "When is the textile passport mandatory?". Only bare keywords worked, which
    is exactly what the first tests used, so it passed.
    """
    import re as _re

    words = _re.split(r"[^0-9a-zA-ZàáâäçèéêëíïîòóôöùúûüñÀÁÂÄÇÈÉÊËÍÏÎÒÓÔÖÙÚÛÜÑ/·-]+",
                      (question or "").lower())
    out, seen = [], set()
    for w in words:
        w = w.strip("-·/")
        if len(w) < 3 or w in _STOPWORDS or w in seen:
            continue
        seen.add(w)
        out.append(w)
    return out[:8]


def handle_ask_dpp(question: str) -> Dict[str, Any]:
    """Front door: search every DPP resource at once and say what was found.

    ONE query across all nine resource types, grouped in Python. Running a query
    per type meant a single call opened ten database sessions, and twelve
    concurrent calls exhausted the pool.

    The question is reduced to its significant terms and rows are ranked by how
    many of them they match, so a real sentence works, not just a keyword.
    """
    q = (question or "").strip()
    if not q:
        return {"error": "Ask a question about the digital product passport."}

    # Bridge non-English questions into English before extracting terms. The
    # corpus is English, so a Catalan question scored 1 for "digital" and nothing
    # else, and the relevance floor then discarded it entirely. Terraqui works in
    # Catalan, so this is not an edge case for this client. Same helper the chat
    # knowledge base uses.
    bridged = q
    try:
        from knowledge_base.query_language_bridge import bridge_query

        bridged = bridge_query(q) or q
    except Exception:  # noqa: BLE001 - retrieval must not depend on the bridge
        pass
    bridged = _domain_bridge(bridged)

    terms = _terms(bridged) or [q]
    # score = how many of the question's terms this row matches
    score = " + ".join(
        f"(CASE WHEN title ILIKE :t{i} OR summary ILIKE :t{i} OR body_txt ILIKE :t{i}"
        f" THEN 1 ELSE 0 END)" for i in range(len(terms))
    )
    where = " OR ".join(
        f"title ILIKE :t{i} OR summary ILIKE :t{i} OR body_txt ILIKE :t{i}"
        for i in range(len(terms))
    )
    params: Dict[str, Any] = {f"t{i}": f"%{t}%" for i, t in enumerate(terms)}
    params["b"] = BODY
    # A relevance floor. OR-ing the terms alone meant "zzzz nothing at all here"
    # returned 13 rows, because one common word matched a lot of legal text. With
    # three or more terms, insist on at least two of them.
    params["floor"] = 2 if len(terms) >= 3 else 1

    rows = _rows(
        "SELECT id, item_type, title, summary, public_url, document_date, hits FROM ("
        f"  SELECT id, item_type, title, summary, public_url, document_date, ({score}) AS hits,"
        f"         row_number() OVER (PARTITION BY item_type ORDER BY ({score}) DESC,"
        "                            document_date DESC NULLS LAST, id) AS rn"
        "  FROM economy_items"
        f"  WHERE body_code = :b AND ({where})"
        ") t WHERE rn <= 4 AND hits >= :floor ORDER BY item_type, hits DESC, rn",
        params,
    )
    found: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        r.pop("hits", None)
        found.setdefault(r.pop("item_type"), []).append(r)

    consultations = handle_dpp_consultations(
        query=terms[0] if terms else q, limit=4).get("consultations", [])

    # National draft rules (TRIS) in the passport's domain, ranked by how many
    # of the question's (English-mapped) terms they match; a named country is
    # a filter, not a hint. Open standstills first among equals.
    tterms, tcountry = _tris_query(q)
    tris: List[Dict[str, Any]] = []
    if tterms or tcountry:
        blob = ("(title || ' ' || coalesce(products_or_services,'') || ' ' || coalesce(main_content,'') "
                "|| ' ' || coalesce(full_text_summary,''))")
        tparams: Dict[str, Any] = {f"t{i}": f"%{t}%" for i, t in enumerate(tterms)}
        tparams["rx"] = _TRIS_DPP_RX
        hits = " + ".join(f"(CASE WHEN {blob} ILIKE :t{i} THEN 1 ELSE 0 END)"
                          for i in range(len(tterms))) or "0"
        cond = [f"{blob} ~* :rx"]
        if tterms:
            cond.append("(" + " OR ".join(f"{blob} ILIKE :t{i}" for i in range(len(tterms))) + ")")
        if tcountry:
            cond.append("notifying_country = :c")
            tparams["c"] = tcountry
        tris = _rows(
            "SELECT notification_number AS reference, notifying_country AS country, title, "
            "notification_date AS notified, standstill_until, "
            "(standstill_until >= current_date) AS standstill_open, source_url "
            f"FROM tris_notifications WHERE {' AND '.join(cond)} "
            f"ORDER BY ({hits}) DESC, (standstill_until >= current_date) DESC NULLS LAST, "
            "notification_date DESC LIMIT 4", tparams)

    if not found and not consultations and not tris:
        return {
            "question": q,
            "found": False,
            "message": (
                "Nothing in the Digital Product Passport corpus matches that. This "
                "server covers the DPP regime, textile extended producer "
                "responsibility, ecodesign consultations and the Ecodesign Forum. "
                "For the wider EU corpus use the main Brubru MCP."
            ),
        }
    return {
        "question": q,
        "found": True,
        "matches": found,
        "consultations": consultations,
        "national_draft_rules_tris": tris,
        "note": ("Call dpp_law with full_text=true to read an act in full, "
                 "dpp_when for the date a sector's passport becomes mandatory, dpp_tris for "
                 "national draft rules and their standstill deadlines, or dpp_jrc for the JRC "
                 "methodology consultation and the textile preparatory study."),
    }


# An MCP tool result is fed straight into a model's context. The ESPR alone is
# 364,000 characters, about 91,000 tokens, and asking for "textile" with
# full_text returned six acts at once: 285,000 tokens, which no host will accept
# and which would cost more than the answer is worth. Full text is therefore
# capped, and only ever for ONE act at a time.
# 24,000 characters is ~6,000 tokens in the handler and ~12,000 on the wire,
# because the result is serialised twice. 40,000 looked fine measured on the
# handler and was 20,000 tokens by the time the client saw it.
_TEXT_CAP = 24_000
_EXCERPT_WINDOW = 1_200     # characters either side of a `contains` hit
_MAX_EXCERPTS = 12


def _excerpts(body: str, needle: str) -> List[str]:
    """Windows of an act around each mention of `needle`.

    This is what a regulatory lawyer actually asks for: not the whole regulation
    but "what does it say about granularity". Returning windows keeps the answer
    inside a sane context budget and is more useful than the first 40,000
    characters, which is almost always the preamble.
    """
    out: List[str] = []
    low, n = body.lower(), needle.lower()
    start = 0
    while len(out) < _MAX_EXCERPTS:
        i = low.find(n, start)
        if i < 0:
            break
        a = max(0, i - _EXCERPT_WINDOW)
        b = min(len(body), i + len(needle) + _EXCERPT_WINDOW)
        out.append(("..." if a > 0 else "") + body[a:b].strip() + ("..." if b < len(body) else ""))
        start = b
    return out


def handle_dpp_law(query: Optional[str] = None, celex: Optional[str] = None,
                   full_text: bool = False, contains: Optional[str] = None
                   ) -> Dict[str, Any]:
    """The acts that create passport obligations, optionally with their text."""
    want_body = bool(full_text or contains)

    if celex:
        rows = _items("law", celex, limit=3, with_body=want_body)
    elif query:
        rows = _items("law", query, limit=6, with_body=want_body)
    else:
        rows = _items("law", None, limit=25, with_body=False)

    if not want_body:
        for r in rows:
            r.pop("body_txt", None)
        return {
            "count": len(rows), "acts": rows,
            "note": ("Pass celex plus full_text=true to read one act, or "
                     "contains='...' to get only the passages that mention a term."),
        }

    # Body requested. Refuse to return several acts of full text at once.
    if len(rows) > 1:
        for r in rows:
            r.pop("body_txt", None)
        return {
            "count": len(rows), "acts": rows,
            "needs_choice": True,
            "note": (f"{len(rows)} acts match. Full text is returned for one act at "
                     "a time because a single regulation can exceed 90,000 tokens. "
                     "Call again with the celex of the one you want."),
        }
    if not rows:
        return {"count": 0, "acts": [], "note": "No act matches."}

    act = rows[0]
    body = act.pop("body_txt", "") or ""

    if contains:
        windows = _excerpts(body, contains)
        act["excerpts"] = windows
        act["excerpt_count"] = len(windows)
        return {
            "count": 1, "acts": [act],
            "note": (f"{len(windows)} passage(s) of this act mention {contains!r}. "
                     "These are windows around each mention, not the whole act."
                     if windows else
                     f"This act does not mention {contains!r}."),
        }

    truncated = len(body) > _TEXT_CAP
    act["body_txt"] = body[:_TEXT_CAP]
    act["truncated"] = truncated
    act["full_length_chars"] = len(body)
    return {
        "count": 1, "acts": [act],
        "note": (
            f"Showing the first {_TEXT_CAP:,} of {len(body):,} characters. Call again "
            f"with contains='<term>' to get the passages about a specific point "
            "instead of the opening of the act."
            if truncated else "Full legal text of the act."
        ),
    }


def handle_dpp_when(sector: Optional[str] = None) -> Dict[str, Any]:
    rows = _items("sector", sector, limit=25, with_body=True)
    return {
        "count": len(rows),
        "sectors": rows,
        "note": ("Dates are the Commission's indicative rollout unless the summary "
                 "names an article. The only hard deadline in force is 18 February "
                 "2027 for certain large batteries."),
    }


# A tool result is serialised TWICE on the wire: once as content text and once
# as structuredContent, because different hosts read different ones. So the wire
# payload is about double the handler's output, and a cap measured on the handler
# is half the cap that actually applies. 30,000 characters here means roughly
# 60,000 on the wire.
_LIST_BODY_MAX_ROWS = 15


def handle_dpp_data_points(query: Optional[str] = None,
                           battery_type: Optional[str] = None) -> Dict[str, Any]:
    rows = _items("data_point", query, limit=80, with_body=True)
    if battery_type:
        # Filter on the APPLICABILITY for that battery type, not on the type
        # being mentioned: every composed body names all three types, so
        # matching the name returned all 71 rows and the filter did nothing.
        bt = battery_type.strip().lower()
        label = {"ev": "Electric vehicle batteries",
                 "electric vehicle": "Electric vehicle batteries",
                 "lmt": "Light means of transport batteries",
                 "light means of transport": "Light means of transport batteries",
                 "industrial": "Industrial batteries"}.get(bt)
        if label:
            keep = []
            for r in rows:
                body = r.get("body_txt") or ""
                i = body.find(label + ":")
                if i < 0:
                    continue
                value = body[i + len(label) + 1: i + len(label) + 60].strip().lower()
                if value.startswith("not to be filled"):
                    continue
                keep.append(r)
            rows = keep

    # Drop the prose body when many rows come back: 71 composed bodies was
    # 147,000 characters on the wire. The summary already names the field and its
    # legal source, which is what a list is for; narrow the query to read detail.
    trimmed = len(rows) > _LIST_BODY_MAX_ROWS
    if trimmed:
        for r in rows:
            r.pop("body_txt", None)
            # summary repeats the title, and document_date is identical on all
            # 71 rows. Dropping both keeps the list inside the wire budget.
            r.pop("summary", None)
            r.pop("document_date", None)
    return {
        "count": len(rows),
        "data_points": rows,
        "detail_omitted": trimmed,
        "note": (("Showing all data points without their detail. Narrow with query= "
                  f"or battery_type= to get fewer than {_LIST_BODY_MAX_ROWS} with "
                  "their full applicability text. " if trimmed else "")
                 + "The battery passport data points from the Commission guidance of "
                 "28 July 2026. Each body states its legal source in Regulation (EU) "
                 "2023/1542 and its applicability per battery type. Where the source "
                 "PDF layout could not be read unambiguously the body says so: treat "
                 "those as needing a check against the guidance document."),
    }


def handle_dpp_standards() -> Dict[str, Any]:
    rows = _items("standard", None, limit=20, with_body=True)
    return {
        "count": len(rows),
        "standards": rows,
        "note": ("Published by Commission Implementing Decision (EU) 2026/1736. A "
                 "harmonised standard carries a presumption of conformity for the "
                 "requirements it covers."),
    }


def handle_dpp_registry() -> Dict[str, Any]:
    rows = _items("registry", None, limit=20, with_body=True)
    return {
        "count": len(rows),
        "registry": rows,
        "note": ("The registry went live on 20 July 2026. Note that the unique "
                 "registration identifier it returns is explicitly NOT proof of "
                 "compliance (ESPR Article 13(5))."),
    }


def handle_dpp_updates(limit: int = 15) -> Dict[str, Any]:
    news = _items("news", None, limit=limit)
    # Upcoming first, SOONEST first, then the most recent past ones. Sorting
    # every event newest-date-first put the far-future JRC workshops (to
    # January 2028) above the passport webinar due next week (23 Sep 2026).
    events = _rows(
        "SELECT id, title, summary, public_url, document_date, "
        "(document_date::date >= current_date) AS upcoming FROM economy_items "
        "WHERE body_code = :b AND item_type = 'event' "
        "ORDER BY (document_date::date >= current_date) DESC, "
        "CASE WHEN document_date::date >= current_date THEN document_date END ASC, "
        "document_date DESC NULLS LAST LIMIT :lim", {"b": BODY, "lim": limit})
    return {"news": news, "events": events,
            "note": "Commission announcements and events on the passport."}


def handle_dpp_consultations(query: Optional[str] = None,
                             status: Optional[str] = None,
                             limit: int = 20) -> Dict[str, Any]:
    """Have Your Say initiatives relevant to ecodesign and textiles."""
    where = ["(" + " OR ".join(f"title ILIKE :t{i}" for i in range(len(_CONSULT_TERMS))) + ")"]
    params: Dict[str, Any] = {f"t{i}": f"%{t}%" for i, t in enumerate(_CONSULT_TERMS)}
    params["lim"] = limit
    if query:
        where.append("(title ILIKE :q OR description ILIKE :q)")
        params["q"] = f"%{query}%"
    if status:
        where.append("status::text = :st")
        params["st"] = status.strip().lower()
    # Order by what a regulatory watcher can still act on: open first, then
    # upcoming, then closed. Sorting on end_date alone buried initiative 16116 --
    # the apparel-textiles delegated act, whose feedback window has no dates yet --
    # below a decade of closed refrigerator measures.
    sql = ("SELECT initiative_id, title, consultation_type::text AS type, "
           "status::text AS status, dg_responsible, start_date, end_date, portal_url "
           "FROM public_consultations WHERE " + " AND ".join(where) +
           " ORDER BY CASE status::text WHEN 'open' THEN 0 WHEN 'upcoming' THEN 1"
           " ELSE 2 END, end_date DESC NULLS LAST, initiative_id DESC LIMIT :lim")
    rows = _rows(sql, params)
    return {
        "count": len(rows),
        "consultations": rows,
        "note": ("Initiative 16116 is the ESPR delegated act on ecodesign "
                 "requirements for sustainable and circular apparel textiles. Its "
                 "feedback period is upcoming, so no dates are set yet."),
    }


def handle_dpp_forum() -> Dict[str, Any]:
    """The Ecodesign Forum and its Member States Expert Group."""
    sql = ("SELECT title, summary, public_url FROM economy_items "
           "WHERE item_type = 'expert_group' AND ("
           "title ILIKE '%ecodesign%' OR title ILIKE '%sustainable product%' "
           "OR title ILIKE '%circular economy%') ORDER BY title LIMIT 15")
    rows = _rows(sql, {})
    return {
        "count": len(rows),
        "groups": rows,
        "note": ("The Ecodesign Forum is the statutory expert group under ESPR "
                 "Article 19; the Member States Expert Group is its subgroup under "
                 "Article 20. This is the channel through which delegated acts are "
                 "prepared, so it is where a sector first sees its future "
                 "requirements."),
    }


# ---- TRIS: national draft rules in the passport's domain ------------------- #

# Added 23 Sep 2026. Member States must notify draft technical rules to the
# Commission (Directive (EU) 2015/1535) and wait out a standstill during which
# the Commission and other Member States can comment or issue a detailed
# opinion. A client found the Spanish textile and footwear decree there before
# Brubru did, because the feed was frozen and this server could not see TRIS at
# all. Domain filter kept tight on purpose: TRIS is mostly food, telecoms and
# vehicles, and "label" alone would drown the passport in food labelling.
# Bare "traceab", "repair" and "circular" were dropped after the first review
# of real matches (23 Sep 2026): "traceability" matched a Spanish animal-rights
# decree (dogs and cats). Product-context forms only.
_TRIS_DPP_RX = (r"textil|footwear|apparel|garment|clothing|packag|waste|recycl|ecodesign|"
                r"eco-design|product passport|digital product|product traceab|"
                r"supply.chain traceab|extended producer|unsold|batter|circular econom|"
                r"repairab|reparab|right to repair|durabilit")


# TRIS texts are in English; Terraqui asks in Catalan and Spanish. The generic
# term extraction keeps the question's own words (and only eight of them), so a
# Catalan question about the "Reial Decret espanyol de productes tèxtils i
# calçat" matched an Estonian regulation (23 Sep 2026). These map the domain
# nouns and country names that matter for TRIS in the six Brubru languages.
_TRIS_WORDS = {
    "textile": ("tèxtil", "textil", "textile", "tessil", "textiel"),
    "footwear": ("calçat", "calzado", "chaussure", "calzatur", "schoeisel", "footwear", "shoe"),
    "packaging": ("envàs", "envasos", "envase", "embalaj", "emballage", "imballagg", "verpakking", "packag"),
    "waste": ("residu", "déchet", "dechet", "rifiut", "afval", "waste"),
    "decree": ("decret", "decreto", "décret", "decreet", "decree"),
    "battery": ("bateri", "batteri", "battery"),
    "recycl": ("reciclat", "reciclaj", "recycl", "riciclag"),
    "extended producer": ("responsabilitat ampliada", "responsabilidad ampliada", "responsabilité élargie",
                          "responsabilità estesa", "uitgebreide producentenverantwoordelijkheid",
                          "extended producer"),
}
_TRIS_COUNTRIES = {
    "ES": ("espany", "españ", "espagn", "spagn", "spaans", "spanje", "spain", "spanish"),
    "FR": ("frança", "francia", "francès", "francés", "français", "frankrijk", "france", "french"),
    "IT": ("itàlia", "itali", "italie", "italy"),
    "NL": ("holanda", "països baixos", "países bajos", "pays-bas", "paesi bassi", "nederland", "netherlands", "dutch"),
    "DE": ("alemany", "aleman", "allemagne", "germania", "duitsland", "germany", "german"),
    "PT": ("portugal", "portogallo", "portugu"),
    "BE": ("bèlgica", "bélgica", "belgique", "belgio", "belgi", "belgium"),
}


def _tris_query(question: str) -> Tuple[List[str], Optional[str]]:
    """(English TRIS terms, ISO country or None) for a question in any of six languages."""
    ql = (question or "").lower()
    terms = [en for en, forms in _TRIS_WORDS.items() if any(f in ql for f in forms)]
    country = next((c for c, forms in _TRIS_COUNTRIES.items() if any(f in ql for f in forms)), None)
    return terms, country


def handle_dpp_tris(query: Optional[str] = None, country: Optional[str] = None,
                    open_only: bool = False, limit: int = 20) -> Dict[str, Any]:
    """National draft technical rules in the DPP domain, deadline first."""
    where = ["(title || ' ' || coalesce(products_or_services,'') || ' ' || coalesce(main_content,'') "
             "|| ' ' || coalesce(full_text_summary,'')) ~* :rx"]
    params: Dict[str, Any] = {"rx": _TRIS_DPP_RX, "lim": max(1, min(int(limit or 20), 50))}
    if query:
        where.append("(title ILIKE :q OR main_content ILIKE :q OR products_or_services ILIKE :q "
                     "OR full_text_summary ILIKE :q)")
        params["q"] = f"%{query}%"
    if country:
        where.append("notifying_country = :c")
        params["c"] = country.strip().upper()[:2]
    if open_only:
        where.append("standstill_until >= current_date")
    rows = _rows(
        "SELECT notification_number AS reference, notifying_country AS country, title, "
        "notification_date AS notified, standstill_until, "
        "(standstill_until >= current_date) AS standstill_open, "
        "coalesce(member_state_observations, '[]'::jsonb) AS comments_by, "
        "coalesce(detailed_opinions, '[]'::jsonb) AS detailed_opinions_by, "
        "left(main_content, 600) AS main_content, left(products_or_services, 400) AS products, "
        "source_url FROM tris_notifications WHERE " + " AND ".join(where) +
        " ORDER BY (standstill_until >= current_date) DESC NULLS LAST, "
        "CASE WHEN standstill_until >= current_date THEN standstill_until END ASC, "
        "notification_date DESC LIMIT :lim", params)
    fresh = _rows("SELECT max(notification_date) AS newest, count(*) AS total FROM tris_notifications", {})
    return {
        "count": len(rows),
        "notifications": rows,
        "feed": fresh[0] if fresh else {},
        "note": ("TRIS lists draft national technical rules notified to the Commission under "
                 "Directive (EU) 2015/1535. While the standstill runs the Member State may not "
                 "adopt the rule, and the Commission or other Member States can issue comments "
                 "or a detailed opinion; a detailed opinion extends the standstill. An open "
                 "standstill is the window to react. 'comments_by' and 'detailed_opinions_by' "
                 "name who issued them; the texts are on the TRIS page."),
    }


# ---- JRC Product Bureau: methodology consultation + textile study ---------- #

def handle_dpp_jrc(kind: Optional[str] = None, query: Optional[str] = None,
                   limit: int = 12) -> Dict[str, Any]:
    """The JRC Product Bureau's ESPR methodology consultation and textile study."""
    kinds = {"workshops": "event", "reports": "jrc_report", "textiles": "jrc_study_document"}
    types = [kinds[kind]] if kind in kinds else list(kinds.values())
    params: Dict[str, Any] = {"b": BODY, "lim": max(1, min(int(limit or 12), 60))}
    ph = ", ".join(f":ty{i}" for i in range(len(types)))
    params.update({f"ty{i}": t for i, t in enumerate(types)})
    extra = ""
    if query:
        extra = " AND (title ILIKE :q OR summary ILIKE :q)"
        params["q"] = f"%{query}%"
    # The limit applies PER KIND: one shared limit let 12 workshops and 10
    # reports crowd the textile study down to three rows.
    rows = _rows(
        "SELECT item_type, title, summary, document_date, public_url FROM ("
        "  SELECT item_type, title, summary, document_date, public_url, row_number() OVER ("
        "    PARTITION BY item_type ORDER BY CASE WHEN item_type = 'event' THEN document_date END ASC,"
        "    document_date DESC NULLS LAST) AS rn FROM economy_items "
        f"  WHERE body_code = :b AND guid LIKE 'jrc-pb-%' AND item_type IN ({ph}){extra}"
        ") t WHERE rn <= :lim "
        "ORDER BY CASE item_type WHEN 'event' THEN 0 WHEN 'jrc_report' THEN 1 ELSE 2 END, rn", params)
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    back = {v: k for k, v in kinds.items()}
    for r in rows:
        grouped.setdefault(back[r.pop("item_type")], []).append(r)
    return {
        "results": grouped,
        "note": ("JRC Product Bureau (unit B.5, Circular Economy and Industrial Sustainability). "
                 "The ESPR methodology consultation runs one online workshop per pair of reports, "
                 "then a questionnaire open about 1.5 months; the links go only to registered "
                 "stakeholders, so register once for the whole project at "
                 "https://susproc.jrc.ec.europa.eu/product-bureau/product-groups/654/home . "
                 "The Digital Product Passport method is in the April 2027 round. Dates the page "
                 "gives only as a month are marked 'day not yet fixed'."),
    }


# ---- the pair ChatGPT requires -------------------------------------------- #

def handle_search(query: str) -> Dict[str, Any]:
    q = (query or "").strip()
    if not q:
        return {"results": []}
    rows = _rows(
        "SELECT id, item_type, title, public_url FROM economy_items "
        "WHERE body_code = :b AND (title ILIKE :q OR summary ILIKE :q OR body_txt ILIKE :q) "
        "ORDER BY document_date DESC NULLS LAST, id LIMIT 25",
        {"b": BODY, "q": f"%{q}%"},
    )
    return {"results": [
        {"id": f"dpp:{r['id']}", "title": r["title"], "url": r["public_url"]}
        for r in rows
    ]}


def handle_fetch(id: str) -> Dict[str, Any]:  # noqa: A002 - name fixed by the spec
    raw = (id or "").strip()
    if raw.startswith("dpp:"):
        raw = raw[4:]
    if not raw.isdigit():
        return {"error": f"Unknown id {id!r}. Use an id returned by search."}
    rows = _rows(
        "SELECT id, title, body_txt, public_url, item_type, document_date "
        "FROM economy_items WHERE body_code = :b AND id = :i",
        {"b": BODY, "i": int(raw)},
    )
    if not rows:
        return {"error": f"No DPP item with id {id!r}."}
    r = rows[0]
    body = r["body_txt"] or ""
    # Same cap as dpp_law: fetch on an act was returning 91,000 tokens, which is
    # more than most hosts will accept in a single tool result.
    text_out = body[:_TEXT_CAP]
    meta = {"item_type": r["item_type"],
            "document_date": str(r["document_date"] or "")}
    if len(body) > _TEXT_CAP:
        meta["truncated"] = True
        meta["full_length_chars"] = len(body)
        meta["how_to_read_more"] = (
            "Use dpp_law with this act's celex and contains='<term>' to get the "
            "passages on a specific point rather than the opening of the act."
        )
    return {
        "id": f"dpp:{r['id']}",
        "title": r["title"],
        "text": text_out,
        "url": r["public_url"],
        "metadata": meta,
    }


# --------------------------------------------------------------------------- #
# registry
# --------------------------------------------------------------------------- #

DPP_TOOLS: List[McpTool] = [
    McpTool(
        name="ask_dpp",
        description=(
            "PRIMARY TOOL: ask anything about the EU Digital Product Passport, the "
            "Ecodesign for Sustainable Products Regulation, textile extended "
            "producer responsibility or the ecodesign delegated acts. One "
            "free-text question in, a combined answer out across the acts, the "
            "sector timetable, the registry, the harmonised standards, the battery "
            "data points and the open consultations. Prefer this over the narrower "
            "dpp_* tools unless the user wants one specific list."
        ),
        input_schema={
            "type": "object",
            "properties": {"question": {
                "type": "string",
                "description": "E.g. 'When does the textile passport become mandatory?'",
            }},
            "required": ["question"],
        },
        scope="read:knowledge", cost_micro=COST_LIGHT_MCP,
        handler=lambda question, **_: handle_ask_dpp(question),
    ),
    McpTool(
        name="dpp_law",
        description=(
            "The EU acts that create digital product passport obligations: the ESPR "
            "framework, the implementing regulation for the registry, the "
            "harmonised-standards decision, and the sectoral laws (batteries, "
            "construction products, toys, detergents), plus textile EPR and textile "
            "labelling. For a specific question use contains='<term>' to get just "
            "the passages that address it; use celex + full_text=true to read one "
            "act from the beginning."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Free text, e.g. 'registry' or 'textile'."},
                "celex": {"type": "string", "description": "A CELEX number, e.g. 32024R1781."},
                "full_text": {"type": "boolean", "description": "Return the act's text (one act at a time, capped)."},
                "contains": {"type": "string", "description": "Return only the passages of the act that mention this term, e.g. 'granularity' or 'customs'. Preferred over full_text for a specific question."},
            },
        },
        scope="read:laws", cost_micro=COST_LIGHT_MCP,
        handler=lambda query=None, celex=None, full_text=False, contains=None, **_:
            handle_dpp_law(query, celex, bool(full_text), contains),
    ),
    McpTool(
        name="dpp_when",
        description=(
            "When the digital product passport becomes mandatory for a product "
            "group, and under which act. Covers batteries, textiles and apparel, "
            "iron and steel, aluminium, tyres, construction products, furniture, "
            "mattresses, toys, detergents and ICT."
        ),
        input_schema={"type": "object", "properties": {
            "sector": {"type": "string", "description": "E.g. 'textiles', 'batteries'. Omit for all."}}},
        scope="read:knowledge", cost_micro=COST_LIGHT_MCP,
        handler=lambda sector=None, **_: handle_dpp_when(sector),
    ),
    McpTool(
        name="dpp_data_points",
        description=(
            "The concrete fields a battery passport must carry: 71 data points, each "
            "with its legal source in Regulation (EU) 2023/1542 and whether it is "
            "mandatory for electric-vehicle, light-means-of-transport or industrial "
            "batteries. This is the schema a passport platform builds against."
        ),
        input_schema={"type": "object", "properties": {
            "query": {"type": "string", "description": "Filter by field name, e.g. 'carbon footprint'."},
            "battery_type": {"type": "string", "description": "ev | lmt | industrial"}}},
        scope="read:knowledge", cost_micro=COST_LIGHT_MCP,
        handler=lambda query=None, battery_type=None, **_:
            handle_dpp_data_points(query, battery_type),
    ),
    McpTool(
        name="dpp_standards",
        description=(
            "The six harmonised EN standards for digital product passports whose "
            "references are published in the Official Journal, and which therefore "
            "carry a presumption of conformity: data exchange, unique identifiers, "
            "data carriers, storage and persistence, APIs, and interoperability."
        ),
        input_schema={"type": "object", "properties": {}},
        scope="read:knowledge", cost_micro=COST_LIGHT_MCP,
        handler=lambda **_: handle_dpp_standards(),
    ),
    McpTool(
        name="dpp_registry",
        description=(
            "How registration in the central DPP registry works: the production and "
            "testing environments, the two registration pathways, what the unique "
            "registration identifier is and is not, and the customs check at release "
            "for free circulation."
        ),
        input_schema={"type": "object", "properties": {}},
        scope="read:knowledge", cost_micro=COST_LIGHT_MCP,
        handler=lambda **_: handle_dpp_registry(),
    ),
    McpTool(
        name="dpp_updates",
        description=(
            "Commission news and events on the digital product passport: what has "
            "moved recently and which webinars are coming."
        ),
        input_schema={"type": "object", "properties": {
            "limit": {"type": "integer", "description": "Max items per list (default 15)."}}},
        scope="read:knowledge", cost_micro=COST_LIGHT_MCP,
        handler=lambda limit=15, **_: handle_dpp_updates(int(limit or 15)),
    ),
    McpTool(
        name="dpp_consultations",
        description=(
            "EU public consultations and Have Your Say initiatives on ecodesign, "
            "textiles and circularity, including the ESPR delegated acts. Use this "
            "to answer 'can I still give feedback' and 'what is coming'. Initiative "
            "16116 is the apparel-textiles delegated act."
        ),
        input_schema={"type": "object", "properties": {
            "query": {"type": "string", "description": "Free text filter."},
            "status": {"type": "string", "description": "open | upcoming | closed"}}},
        scope="read:knowledge", cost_micro=COST_LIGHT_MCP,
        handler=lambda query=None, status=None, **_:
            handle_dpp_consultations(query, status),
    ),
    McpTool(
        name="dpp_forum",
        description=(
            "The Commission expert groups that prepare ecodesign delegated acts: the "
            "Ecodesign Forum (ESPR Article 19) and its Member States Expert Group "
            "(Article 20). This is where a sector first sees its future requirements."
        ),
        input_schema={"type": "object", "properties": {}},
        scope="read:knowledge", cost_micro=COST_LIGHT_MCP,
        handler=lambda **_: handle_dpp_forum(),
    ),
    McpTool(
        name="dpp_tris",
        description=(
            "National draft technical rules that Member States have notified to the "
            "Commission (TRIS, Directive (EU) 2015/1535) in the passport's domain: "
            "textiles and footwear, packaging, waste and recycling, ecodesign, "
            "traceability, extended producer responsibility, batteries. Each has its "
            "standstill end date (the window to react before adoption) and who issued "
            "comments or detailed opinions. Open standstills come first, soonest "
            "deadline first. Example: the Spanish draft Royal Decree on textile and "
            "footwear products and their waste."
        ),
        input_schema={"type": "object", "properties": {
            "query": {"type": "string", "description": "Free text filter, e.g. 'textile'."},
            "country": {"type": "string", "description": "ISO code of the notifying country, e.g. ES."},
            "open_only": {"type": "boolean", "description": "Only notifications whose standstill is still running."},
            "limit": {"type": "integer", "description": "Max results (default 20, max 50)."}}},
        scope="read:knowledge", cost_micro=COST_LIGHT_MCP,
        handler=lambda query=None, country=None, open_only=False, limit=20, **_:
            handle_dpp_tris(query, country, bool(open_only), limit),
    ),
    McpTool(
        name="dpp_jrc",
        description=(
            "The JRC Product Bureau: the ESPR methodology consultation (workshop "
            "calendar and the methodological reports open for comment, including the "
            "method for Digital Product Passport data requirements) and the textile "
            "products preparatory study (its documents, including the study on DPP "
            "content for textile apparel)."
        ),
        input_schema={"type": "object", "properties": {
            "kind": {"type": "string", "description": "workshops | reports | textiles (default: all)"},
            "query": {"type": "string", "description": "Free text filter."},
            "limit": {"type": "integer", "description": "Max results per kind (default 12)."}}},
        scope="read:knowledge", cost_micro=COST_LIGHT_MCP,
        handler=lambda kind=None, query=None, limit=12, **_: handle_dpp_jrc(kind, query, limit),
    ),
    McpTool(
        name="search",
        description=(
            "Search the Digital Product Passport corpus and return ids, titles and "
            "links. Pair with `fetch` to read an item in full. Required by hosts "
            "that expect the OpenAI search/fetch convention."
        ),
        input_schema={"type": "object",
                      "properties": {"query": {"type": "string"}},
                      "required": ["query"]},
        scope="read:knowledge", cost_micro=COST_LIGHT_MCP,
        handler=lambda query, **_: handle_search(query),
    ),
    McpTool(
        name="fetch",
        description=(
            "Fetch one Digital Product Passport item in full by the id returned from "
            "`search`. For an act this returns its complete legal text."
        ),
        input_schema={"type": "object",
                      "properties": {"id": {"type": "string"}},
                      "required": ["id"]},
        scope="read:knowledge", cost_micro=COST_LIGHT_MCP,
        handler=lambda id, **_: handle_fetch(id),  # noqa: A002
    ),
]

_BY_NAME = {t.name: t for t in DPP_TOOLS}


def list_dpp_tools_for_mcp() -> List[Dict[str, Any]]:
    return [{"name": t.name, "description": t.description, "inputSchema": t.input_schema}
            for t in DPP_TOOLS]


def find_dpp_tool(name: str) -> Optional[McpTool]:
    return _BY_NAME.get(name)
