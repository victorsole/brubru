#!/usr/bin/env python3.12
"""
Build + publish the single "Brubru API v2" Postman collection.

ONE collection, with one folder per institutional DOMAIN, each domain holding
its source sub-folders (and EUR-Lex its own sub-sub-folders):

    Brubru API v2
    ├── Legislative data
    │   ├── EUR-Lex
    │   │   ├── Identifiers & resolution
    │   │   ├── Documents
    │   │   ├── Search & summaries
    │   │   ├── Relationships & lifecycle
    │   │   └── Official Journal
    │   ├── Legislative Observatory (OEIL)
    │   ├── Legislative Train
    │   └── EuroVoc & vocabularies
    └── Proprietary Databases
        ├── Knowledge Guides
        ├── Catalan Translations
        └── Canon & Deep-Dives

Generated FROM the live FastAPI OpenAPI spec so descriptions stay in sync with
the code. Supersedes the two split builders (build_v2_legislative_postman.py +
build_v2_proprietary_postman.py): there is now ONE published v2 collection, not
two top-level ones.

Usage:
    python3.12 -m scripts.build_v2_postman            # build + save JSON only
    python3.12 -m scripts.build_v2_postman --publish  # publish + delete the old split collections
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from main import app  # noqa: E402

PROD_BASE = "https://brubru-production.up.railway.app"
COLLECTION_NAME = "Brubru API v2"
OUT_PATH = _BACKEND / "data" / "postman_v2_collection.json"
# Old split collections to retire on --publish (folded into this one).
_RETIRE_NAMES = {"Brubru API v2: Legislative data", "Brubru API v2: Proprietary Databases"}

# --------------------------------------------------------------------------- #
# Routing                                                                     #
# --------------------------------------------------------------------------- #
# Legislative: (path-tail matcher, source folder, sub-folder|None). First match wins.
_LEG_ROUTING = [
    ("eur-lex/identify", "EUR-Lex", "Identifiers & resolution"),
    ("eur-lex/laws/resolve", "EUR-Lex", "Identifiers & resolution"),
    ("eur-lex/xref", "EUR-Lex", "Identifiers & resolution"),
    ("eur-lex/laws/{celex}/xref", "EUR-Lex", "Identifiers & resolution"),
    ("eur-lex/laws/{celex}/views", "EUR-Lex", "Identifiers & resolution"),
    ("eur-lex/verify-citation", "EUR-Lex", "Identifiers & resolution"),
    ("eur-lex/laws/summaries", "EUR-Lex", "Search & summaries"),
    ("eur-lex/resolve-aliases", "EUR-Lex", "Search & summaries"),
    ("eur-lex/resolve-references", "EUR-Lex", "Search & summaries"),
    ("eur-lex/laws/{celex}/relationships", "EUR-Lex", "Relationships & lifecycle"),
    ("eur-lex/laws/{celex}/lifecycle", "EUR-Lex", "Relationships & lifecycle"),
    ("eur-lex/laws/{celex}/consolidated", "EUR-Lex", "Relationships & lifecycle"),
    ("eur-lex/laws/{celex}/languages", "EUR-Lex", "Relationships & lifecycle"),
    ("eur-lex/laws/{celex}/cellar", "EUR-Lex", "Relationships & lifecycle"),
    ("eur-lex/recent", "EUR-Lex", "Relationships & lifecycle"),
    ("eur-lex/oj/", "EUR-Lex", "Official Journal"),
    ("eur-lex/laws/{celex}/text", "EUR-Lex", "Documents"),
    ("eur-lex/laws/{celex}/recital-article-map", "EUR-Lex", "Documents"),
    ("eur-lex/laws/{celex}/defined-terms", "EUR-Lex", "Documents"),
    ("eur-lex/laws/{celex}", "EUR-Lex", "Documents"),
    ("eur-lex/laws", "EUR-Lex", "Documents"),
    ("oeil/", "Legislative Observatory (OEIL)", None),
    ("legislative-train/", "Legislative Train", None),
    ("eurovoc/", "EuroVoc & vocabularies", None),
    ("delegated-acts", "Legislative Documents", None),
    ("implementing-acts", "Legislative Documents", None),
]
_LEG_SOURCE_ORDER = ["EUR-Lex", "Legislative Observatory (OEIL)", "Legislative Train", "EuroVoc & vocabularies", "Legislative Documents"]
_EURLEX_SUBORDER = ["Identifiers & resolution", "Documents", "Search & summaries", "Relationships & lifecycle", "Official Journal"]

# Proprietary: (path-tail prefix, source folder). Flat — no sub-sub-folders.
_PROP_ROUTING = [("guides", "Knowledge Guides"), ("catalan", "Catalan Translations"), ("canon", "Canon & Deep-Dives"), ("brussels-lobbies", "Brussels Lobbies")]
_PROP_SOURCE_ORDER = ["Knowledge Guides", "Catalan Translations", "Canon & Deep-Dives", "Brussels Lobbies"]

# Parliament: (path-tail prefix, source folder). Flat — no sub-sub-folders.
_PARL_ROUTING = [
    ("meps", "MEPs"),
    ("amendments", "Amendments"),
    ("votes", "Votes"),
    ("ep-documents", "EP Documents"),
    ("reports", "Reports"),
    ("opinions", "Opinions"),
    ("committees", "Committees"),
    ("texts-adopted", "Texts Adopted"),
    ("texts-submitted", "Texts Submitted"),
    ("resolutions", "Resolutions"),
    ("eprs", "EPRS"),
    ("webstreams", "Webstreams"),
    ("parliamentary-questions", "Parliamentary Questions"),
    ("emeeting-documents", "eMeeting Documents"),
    ("emeeting", "eMeeting"),
    ("committee-transcripts", "Committee Transcripts"),
    ("committee-agendas", "Committee Agendas"),
    ("mep-declarations", "MEP Declarations of Financial Interests"),
    ("mep-assistants", "Parliamentary Assistants Register"),
    ("supporting-analyses", "Committee Supporting Analyses"),
]
_PARL_SOURCE_ORDER = [
    "MEPs", "Amendments", "Votes", "EP Documents", "Reports", "Opinions",
    "Committees", "Texts Adopted", "Texts Submitted", "Resolutions", "EPRS",
    "Webstreams", "Parliamentary Questions", "eMeeting", "eMeeting Documents",
    "Committee Transcripts", "Committee Agendas",
    "MEP Declarations of Financial Interests", "Parliamentary Assistants Register",
    "Committee Supporting Analyses",
]

# Commission: (path-tail prefix, source folder). Flat — no sub-sub-folders.
_COMM_ROUTING = [
    ("commissioners", "Commissioners"),
    ("commission-register-documents", "Commission Register"),
    ("meetings", "Meetings"),
    ("rsb-opinions", "RSB Opinions"),
    ("infringements", "Infringements"),
    ("consultations", "Consultations"),
    ("tris-notifications", "TRIS Notifications"),
    ("financial-sanctions", "Financial Sanctions"),
    ("research-projects", "Research Projects"),
    ("tariff-rulings", "Tariff Rulings"),
    ("taric-tariffs", "TARIC / Combined Nomenclature"),
    ("agridata", "Agridata"),
    ("cap-beneficiaries", "Common Agricultural Policy Beneficiaries"),
    ("trade-defence", "Trade Defence"),
    ("comitology", "Comitology"),
    ("expert-groups", "Expert Groups"),
    ("dma-cases", "Digital Markets Act Cases"),
    ("state-aid", "State Aid"),
    ("rasff", "RASFF Food & Feed Safety"),
]
_COMM_SOURCE_ORDER = [
    "Commissioners", "Commission Register", "Meetings", "RSB Opinions",
    "Infringements", "Consultations", "TRIS Notifications",
    "Financial Sanctions", "Research Projects", "Tariff Rulings",
    "TARIC / Combined Nomenclature", "Agridata",
    "Common Agricultural Policy Beneficiaries", "Trade Defence",
    "Comitology", "Expert Groups", "Digital Markets Act Cases", "State Aid",
    "RASFF Food & Feed Safety",
]

# Council: (path-tail prefix, source folder). Flat — no sub-sub-folders.
_COUNCIL_ROUTING = [
    ("council-documents", "Council Documents"),
    ("council-configurations", "Council Configurations"),
    ("council-meetings", "Council Meetings"),
    ("council-voting-results", "Council Voting Results"),
    ("council-register", "Council Register"),
    ("council-oj-agendas", "Council OJ Agendas"),
    ("council-preparatory-bodies", "Council Preparatory Bodies"),
    ("council-press-releases", "Council Press Releases"),
    ("council-research-papers", "Council Research Papers"),
    ("council-treaties-agreements", "Council Treaties & Agreements"),
    ("sanctions-regimes", "EU Sanctions Regimes"),
]
_COUNCIL_SOURCE_ORDER = [
    "Council Documents", "Council Configurations", "Council Meetings",
    "Council Voting Results", "Council Register", "Council OJ Agendas",
    "Council Preparatory Bodies", "Council Press Releases",
    "Council Research Papers", "Council Treaties & Agreements",
    "EU Sanctions Regimes",
]

# European Council: (path-tail prefix, source folder).
_EUCO_ROUTING = [
    ("euco-conclusions", "Conclusions"),
    ("euco-meetings", "Meetings"),
    ("euco-euro-summit", "Euro Summit"),
    ("euco-strategic-agenda", "Strategic Agenda"),
    ("euco-members", "Members"),
    ("euco-about", "About"),
]
_EUCO_SOURCE_ORDER = ["Conclusions", "Meetings", "Euro Summit", "Strategic Agenda", "Members", "About"]

# Eurogroup: (path-tail prefix, source folder).
_EUROGROUP_ROUTING = [
    ("eurogroup-meetings", "Meetings"),
    ("eurogroup-documents", "Documents"),
    ("eurogroup-work-programme", "Work Programme"),
    ("eurogroup-members", "Members"),
    ("eurogroup-about", "About"),
]
_EUROGROUP_SOURCE_ORDER = ["Meetings", "Documents", "Work Programme", "Members", "About"]

# Funding & Tenders: (path-tail prefix, source folder).
_FUNDING_ROUTING = [
    ("funding-opportunities", "Funding Opportunities"),
    ("ft-calls-for-proposals", "Calls for Proposals"),
    ("ft-calls-for-tenders", "Calls for Tenders"),
    ("ft-funded-projects", "Funded Projects"),
    ("eu-funding-recipients", "Funded Projects"),
    ("tenders", "TED Tenders"),
]
_FUNDING_SOURCE_ORDER = ["Funding Opportunities", "Calls for Proposals", "Calls for Tenders",
                         "Funded Projects", "TED Tenders"]

# Open Data: (path-tail prefix, source folder).
_OPENDATA_ROUTING = [
    ("datasets", "Datasets"),
    ("high-value-datasets", "High-Value Datasets"),
    ("catalogues", "Catalogues"),
]
_OPENDATA_SOURCE_ORDER = ["Datasets", "High-Value Datasets", "Catalogues"]

# Who is Who: (path-tail prefix, source folder).
_WIW_ROUTING = [("departments", "Departments"), ("officials", "Officials")]
_WIW_SOURCE_ORDER = ["Departments", "Officials"]

_PARAM_DEFAULTS = {
    "celex": "32016R0679", "ref": "32016R0679", "reference": "2022/0047(COD)",
    "concept_id": "3030", "table": "corporate-bodies", "summary_id": "32016R0679",
    "carriage_id": "2022/0047(COD)", "series": "L", "year": "2016", "number": "119",
    "guide_id": "ai_act_regulation", "slug": "2024-1689_aiact",
    # European Parliament domain path variables
    "mep_id": "197488", "ta_reference": "P10_TA(2025)0042",
    "question_reference": "E-001234/2026", "code": "LIBE",
    "procedure_ref": "2025/2125(INI)",
    # European Commission domain path variables
    "name": "ribera", "initiative_id": "13693", "notification_number": "2026/0123/FR",
}
_QUERY_FALLBACKS = {
    "q": "data protection", "id": "GDPR", "date": "2026-05-01", "published_from": "2026-05-01",
    "limit": "10", "page": "1", "days": "7", "lang": "en", "language": "en", "series": "L",
    "text": "See Regulation (EU) 2016/679 and the AI Act.",
    "detail_level": "Summary", "report_type": "canon", "legal_family": "eu_pharmaceutical",
    "include_body": "false", "body": "html",
}


def _match_template(tail: str, needle: str) -> bool:
    t, n = tail.split("/"), needle.split("/")
    if len(t) < len(n):
        return False
    return all(b.startswith("{") or a == b for a, b in zip(t, n))


def _leg_route(tail: str):
    for needle, source, sub in _LEG_ROUTING:
        if tail == needle or tail.startswith(needle) or _match_template(tail, needle):
            return source, sub
    return "EUR-Lex", "Documents"


def _prop_route(tail: str) -> str:
    for needle, source in _PROP_ROUTING:
        if tail == needle or tail.startswith(needle):
            return source
    return "Knowledge Guides"


def _parl_route(tail: str) -> str:
    for needle, source in _PARL_ROUTING:
        if tail == needle or tail.startswith(needle + "/") or tail.startswith(needle + "?"):
            return source
    return "MEPs"


def _comm_route(tail: str) -> str:
    for needle, source in _COMM_ROUTING:
        if tail == needle or tail.startswith(needle + "/") or tail.startswith(needle + "?"):
            return source
    return "Commissioners"


def _council_route(tail: str) -> str:
    for needle, source in _COUNCIL_ROUTING:
        if tail == needle or tail.startswith(needle + "/") or tail.startswith(needle + "?"):
            return source
    return "Council Documents"


def _euco_route(tail: str) -> str:
    for needle, source in _EUCO_ROUTING:
        if tail == needle or tail.startswith(needle + "/") or tail.startswith(needle + "?"):
            return source
    return "Conclusions"


def _eurogroup_route(tail: str) -> str:
    for needle, source in _EUROGROUP_ROUTING:
        if tail == needle or tail.startswith(needle + "/") or tail.startswith(needle + "?"):
            return source
    return "Meetings"


def _funding_route(tail: str) -> str:
    for needle, source in _FUNDING_ROUTING:
        if tail == needle or tail.startswith(needle + "/") or tail.startswith(needle + "?"):
            return source
    return "Funding Opportunities"


def _opendata_route(tail: str) -> str:
    for needle, source in _OPENDATA_ROUTING:
        if tail == needle or tail.startswith(needle + "/") or tail.startswith(needle + "?"):
            return source
    return "Datasets"


def _wiw_route(tail: str) -> str:
    for needle, source in _WIW_ROUTING:
        if tail == needle or tail.startswith(needle + "/") or tail.startswith(needle + "?"):
            return source
    return "Departments"


def _clean_path(path: str) -> str:
    return re.sub(r"\{(\w+):[^}]+\}", r"{\1}", path)


def _query_value(param: dict) -> str:
    if param.get("example") is not None:
        return str(param["example"])
    sch = param.get("schema", {})
    if sch.get("example") is not None:
        return str(sch["example"])
    if sch.get("default") is not None:
        return str(sch["default"])
    return _QUERY_FALLBACKS.get(param["name"], "")


def _to_postman_url(path: str, query_params: list) -> dict:
    clean = _clean_path(path)
    pm_path = re.sub(r"\{(\w+)\}", r":\1", clean)  # Postman path vars use :name
    raw = "{{baseUrl}}" + pm_path
    url = {"raw": raw, "host": ["{{baseUrl}}"], "path": pm_path.strip("/").split("/")}

    variables = [
        {"key": m.group(1), "value": _PARAM_DEFAULTS.get(m.group(1), ""), "description": "(path variable)"}
        for m in re.finditer(r"\{(\w+)\}", clean)
    ]
    if variables:
        url["variable"] = variables

    query = [{"key": p["name"], "value": _query_value(p), "disabled": not p.get("required", False)} for p in query_params]
    if query:
        url["query"] = query
        enabled = [q for q in query if not q["disabled"]]
        if enabled:
            url["raw"] = raw + "?" + "&".join(f"{q['key']}={q['value']}" for q in enabled)
    return url


def _build_request(path: str, method: str, op: dict) -> dict:
    query_params = [p for p in op.get("parameters", []) if p.get("in") == "query"]
    req = {
        "name": op.get("summary") or f"{method.upper()} {path}",
        "request": {
            "method": method.upper(),
            "header": [{"key": "X-API-Key", "value": "{{api_key}}", "type": "text"}],
            "url": _to_postman_url(path, query_params),
            "description": op.get("description") or "",
        },
        "response": [],
    }
    if method.lower() == "post":
        req["request"]["body"] = {
            "mode": "raw",
            "raw": json.dumps({"text": "Article 5 of Regulation (EU) 2022/2065 and the GDPR apply."}, indent=2),
            "options": {"raw": {"language": "json"}},
        }
        req["request"]["header"].append({"key": "Content-Type", "value": "application/json", "type": "text"})
    return req


def _prop_sort_key(item: dict) -> tuple:
    """Within a proprietary folder: list-everything first, then literal sub-routes, then detail."""
    after = item["request"]["url"]["path"][3:]  # drop api/v2/proprietary
    rank = 0 if len(after) == 1 else (2 if any(s.startswith(":") for s in after) else 1)
    return (rank, item["name"])


def _build_legislative_domain(paths: dict) -> dict:
    tree: dict = {}
    for path, methods in paths.items():
        if "/api/v2/legislative/" not in path:
            continue
        tail = path.split("/api/v2/legislative/", 1)[1]
        source, sub = _leg_route(tail)
        for method, op in methods.items():
            if method.lower() not in ("get", "post"):
                continue
            tree.setdefault(source, {}).setdefault(sub or "_root", []).append(_build_request(path, method, op))

    sources = []
    for source in _LEG_SOURCE_ORDER:
        if source not in tree:
            continue
        sub_map = tree[source]
        if list(sub_map.keys()) == ["_root"]:
            sources.append({"name": source, "item": sorted(sub_map["_root"], key=lambda i: i["name"])})
        else:
            sub_keys = _EURLEX_SUBORDER if source == "EUR-Lex" else sorted(sub_map.keys())
            sub_folders = [{"name": s, "item": sorted(sub_map[s], key=lambda i: i["name"])} for s in sub_keys if s in sub_map]
            sources.append({"name": source, "item": sub_folders})
    return {"name": "Legislative data", "item": sources}


def _build_proprietary_domain(paths: dict) -> dict:
    tree: dict[str, list] = {}
    for path, methods in paths.items():
        if "/api/v2/proprietary/" not in path:
            continue
        tail = path.split("/api/v2/proprietary/", 1)[1]
        source = _prop_route(tail)
        for method, op in methods.items():
            if method.lower() not in ("get", "post"):
                continue
            tree.setdefault(source, []).append(_build_request(path, method, op))
    sources = [{"name": s, "item": sorted(tree[s], key=_prop_sort_key)} for s in _PROP_SOURCE_ORDER if s in tree]
    return {"name": "Proprietary Databases", "item": sources}


def _build_parliament_domain(paths: dict) -> dict:
    tree: dict[str, list] = {}
    for path, methods in paths.items():
        if "/api/v2/parliament/" not in path:
            continue
        tail = path.split("/api/v2/parliament/", 1)[1]
        source = _parl_route(tail)
        for method, op in methods.items():
            if method.lower() not in ("get", "post"):
                continue
            tree.setdefault(source, []).append(_build_request(path, method, op))
    sources = [{"name": s, "item": sorted(tree[s], key=_prop_sort_key)} for s in _PARL_SOURCE_ORDER if s in tree]
    return {"name": "European Parliament", "item": sources}


def _build_commission_domain(paths: dict) -> dict:
    tree: dict[str, list] = {}
    for path, methods in paths.items():
        if "/api/v2/commission/" not in path:
            continue
        tail = path.split("/api/v2/commission/", 1)[1]
        source = _comm_route(tail)
        for method, op in methods.items():
            if method.lower() not in ("get", "post"):
                continue
            tree.setdefault(source, []).append(_build_request(path, method, op))
    sources = [{"name": s, "item": sorted(tree[s], key=_prop_sort_key)} for s in _COMM_SOURCE_ORDER if s in tree]
    return {"name": "European Commission", "item": sources}


def _build_council_domain(paths: dict) -> dict:
    tree: dict[str, list] = {}
    for path, methods in paths.items():
        if "/api/v2/council/" not in path:
            continue
        tail = path.split("/api/v2/council/", 1)[1]
        source = _council_route(tail)
        for method, op in methods.items():
            if method.lower() not in ("get", "post"):
                continue
            tree.setdefault(source, []).append(_build_request(path, method, op))
    sources = [{"name": s, "item": sorted(tree[s], key=_prop_sort_key)} for s in _COUNCIL_SOURCE_ORDER if s in tree]
    return {"name": "Council of the EU", "item": sources}


def _build_european_council_domain(paths: dict) -> dict:
    tree: dict[str, list] = {}
    for path, methods in paths.items():
        if "/api/v2/european-council/" not in path:
            continue
        tail = path.split("/api/v2/european-council/", 1)[1]
        source = _euco_route(tail)
        for method, op in methods.items():
            if method.lower() not in ("get", "post"):
                continue
            tree.setdefault(source, []).append(_build_request(path, method, op))
    sources = [{"name": s, "item": sorted(tree[s], key=_prop_sort_key)} for s in _EUCO_SOURCE_ORDER if s in tree]
    return {"name": "European Council", "item": sources}


def _build_eurogroup_domain(paths: dict) -> dict:
    tree: dict[str, list] = {}
    for path, methods in paths.items():
        if "/api/v2/eurogroup/" not in path:
            continue
        tail = path.split("/api/v2/eurogroup/", 1)[1]
        source = _eurogroup_route(tail)
        for method, op in methods.items():
            if method.lower() not in ("get", "post"):
                continue
            tree.setdefault(source, []).append(_build_request(path, method, op))
    sources = [{"name": s, "item": sorted(tree[s], key=_prop_sort_key)} for s in _EUROGROUP_SOURCE_ORDER if s in tree]
    return {"name": "Eurogroup", "item": sources}


def _build_funding_domain(paths: dict) -> dict:
    tree: dict[str, list] = {}
    for path, methods in paths.items():
        if "/api/v2/funding/" not in path:
            continue
        tail = path.split("/api/v2/funding/", 1)[1]
        source = _funding_route(tail)
        for method, op in methods.items():
            if method.lower() not in ("get", "post"):
                continue
            tree.setdefault(source, []).append(_build_request(path, method, op))
    sources = [{"name": s, "item": sorted(tree[s], key=_prop_sort_key)} for s in _FUNDING_SOURCE_ORDER if s in tree]
    return {"name": "Funding & Tenders", "item": sources}


def _build_open_data_domain(paths: dict) -> dict:
    tree: dict[str, list] = {}
    for path, methods in paths.items():
        if "/api/v2/open-data/" not in path:
            continue
        tail = path.split("/api/v2/open-data/", 1)[1]
        source = _opendata_route(tail)
        for method, op in methods.items():
            if method.lower() not in ("get", "post"):
                continue
            tree.setdefault(source, []).append(_build_request(path, method, op))
    sources = [{"name": s, "item": sorted(tree[s], key=_prop_sort_key)} for s in _OPENDATA_SOURCE_ORDER if s in tree]
    return {"name": "Open Data", "item": sources}


def _build_general_publications_domain(paths: dict) -> dict:
    items = []
    for path, methods in paths.items():
        if "/api/v2/general-publications" not in path:
            continue
        for method, op in methods.items():
            if method.lower() not in ("get", "post"):
                continue
            items.append(_build_request(path, method, op))
    items.sort(key=_prop_sort_key)
    return {"name": "General Publications", "item": [{"name": "Publications", "item": items}]}


def _build_who_is_who_domain(paths: dict) -> dict:
    tree: dict[str, list] = {}
    for path, methods in paths.items():
        if "/api/v2/who-is-who/" not in path:
            continue
        tail = path.split("/api/v2/who-is-who/", 1)[1]
        source = _wiw_route(tail)
        for method, op in methods.items():
            if method.lower() not in ("get", "post"):
                continue
            tree.setdefault(source, []).append(_build_request(path, method, op))
    sources = [{"name": s, "item": sorted(tree[s], key=_prop_sort_key)} for s in _WIW_SOURCE_ORDER if s in tree]
    return {"name": "Who is Who", "item": sources}


# Economy & Finance — ECB folder. Two sub-folders: ECB proper + Banking Supervision.
_ECB_SOURCE_ORDER = ["ECB", "Banking Supervision (SSM)"]


def _build_ecb_domain(paths: dict) -> dict:
    tree: dict[str, list] = {}
    for path, methods in paths.items():
        if path != "/api/v2/ecb" and "/api/v2/ecb/" not in path:
            continue
        tail = path.split("/api/v2/ecb", 1)[1].lstrip("/")
        source = "Banking Supervision (SSM)" if tail.startswith("banking-supervision") else "ECB"
        for method, op in methods.items():
            if method.lower() not in ("get", "post"):
                continue
            tree.setdefault(source, []).append(_build_request(path, method, op))
    sources = [{"name": s, "item": sorted(tree[s], key=_prop_sort_key)} for s in _ECB_SOURCE_ORDER if s in tree]
    return {"name": "European Central Bank", "item": sources}


# Economic & Financial Institutions of the EU — one sub-folder per body (acronym).
_EU_FIN_ORDER = ["Directory", "EBA", "ESMA", "EIOPA", "ESRB", "SRB", "EIB", "AMLA", "EPPO"]


def _build_eu_fin_domain(paths: dict) -> dict:
    tree: dict[str, list] = {}
    for path, methods in paths.items():
        if path != "/api/v2/eu-financial-institutions" and "/api/v2/eu-financial-institutions/" not in path:
            continue
        tail = path.split("/api/v2/eu-financial-institutions", 1)[1].lstrip("/")
        seg = tail.split("/")[0] if tail else ""
        source = seg.upper() if seg else "Directory"
        for method, op in methods.items():
            if method.lower() not in ("get", "post"):
                continue
            tree.setdefault(source, []).append(_build_request(path, method, op))
    sources = [{"name": s, "item": sorted(tree[s], key=_prop_sort_key)} for s in _EU_FIN_ORDER if s in tree]
    sources += [{"name": s, "item": sorted(tree[s], key=_prop_sort_key)}
                for s in tree if s not in _EU_FIN_ORDER]
    return {"name": "Economic & Financial Institutions of the EU", "item": sources}


def _build_flat_domain(paths: dict, prefix: str, name: str) -> dict:
    """A single-body own-folder domain (ESM and the single-market agencies):
    all requests under /api/v2/<prefix> sit directly under one domain folder."""
    items = []
    root = f"/api/v2/{prefix}"
    for path, methods in paths.items():
        if path != root and f"{root}/" not in path:
            continue
        for method, op in methods.items():
            if method.lower() not in ("get", "post"):
                continue
            items.append(_build_request(path, method, op))
    return {"name": name, "item": sorted(items, key=_prop_sort_key)}


def _build_esm_domain(paths: dict) -> dict:
    return _build_flat_domain(paths, "esm", "European Stability Mechanism")


# Single-market / digital EU agencies (api_market.md) — one flat folder each.
_AGENCY_DOMAINS = [
    ("berec", "BEREC — Electronic Communications"),
    ("acer", "ACER — Energy Regulators"),
    ("eit", "EIT — Innovation & Technology"),
    ("enisa", "ENISA — Cybersecurity"),
    ("eu-lisa", "eu-LISA — Large-Scale IT Systems"),
    ("euipo", "EUIPO — Intellectual Property"),
    ("cpvo", "CPVO — Plant Variety Rights"),
    # Health agencies (api_health.md), one flat folder each.
    ("ema", "EMA — Medicines"),
    ("ecdc", "ECDC — Disease Prevention & Control"),
    ("efsa", "EFSA — Food Safety"),
    ("eu-osha", "EU-OSHA — Safety & Health at Work"),
    ("eea", "EEA — Environment"),
    ("echa", "ECHA — Chemicals"),
    ("euda", "EUDA — Drugs"),
    ("eige", "EIGE — Gender Equality"),
]


def _count(folder: dict) -> int:
    items = folder.get("item", [])
    if items and "request" in items[0]:
        return len(items)
    return sum(_count(sub) for sub in items)


def build_collection() -> dict:
    paths = app.openapi().get("paths", {})
    domains = [
        _build_legislative_domain(paths),
        _build_parliament_domain(paths),
        _build_commission_domain(paths),
        _build_flat_domain(paths, "geographical-indications", "Geographical Indications"),
        _build_council_domain(paths),
        _build_european_council_domain(paths),
        _build_eurogroup_domain(paths),
        _build_funding_domain(paths),
        _build_open_data_domain(paths),
        _build_who_is_who_domain(paths),
        _build_general_publications_domain(paths),
        _build_ecb_domain(paths),
        _build_eu_fin_domain(paths),
        _build_esm_domain(paths),
        *(_build_flat_domain(paths, prefix, name) for prefix, name in _AGENCY_DOMAINS),
        _build_proprietary_domain(paths),
    ]
    # Drop agency domains that have no built endpoints yet.
    domains = [d for d in domains if d.get("item")]
    n_requests = sum(_count(d) for d in domains)
    return {
        "info": {
            "name": COLLECTION_NAME,
            "description": (
                "Brubru's institution-/source-based public API, **v2**. One collection, one folder "
                "per domain, each domain holding its source sub-folders.\n\n"
                "- **Legislative data** — mirrored EU institutional sources: EUR-Lex / Legislative "
                "Observatory (OEIL) / Legislative Train / EuroVoc / Legislative Documents.\n"
                "- **European Parliament** — the EP surface: MEPs, amendments, votes, committee output, "
                "reports, opinions, committees, texts adopted/submitted, resolutions, EPRS, webstreams "
                "and parliamentary questions.\n"
                "- **European Commission** — the EC surface: College of Commissioners, Commission Register "
                "documents, Transparency Initiative meetings, Regulatory Scrutiny Board opinions, "
                "infringements, Have Your Say consultations and TRIS notifications.\n"
                "- **Council of the EU** — Council documents: press releases, conclusions, meeting "
                "agendas and summits.\n"
                "- **Proprietary Databases** — Brubru's own data products: Knowledge Guides / Catalan "
                "Translations / Canon & Deep-Dives.\n\n"
                "Domain-rooted `/api/v2/{domain}/{source}/...` URLs. Same auth, envelope, error shapes "
                "and documentation contract as v1. Each source folder leads with a 'show everything' "
                "list request; detail requests are pre-filled with a working example.\n\n"
                "Set the `api_key` collection variable to a `brubru_live_...` key (mint one at "
                "brubru.beresol.eu/api). Scopes used: `read:laws`, `read:procedures`, "
                "`read:publications`, `read:knowledge`, `read:commission`, `read:ep`, `read:calendar`. "
                "`baseUrl` defaults to production.\n\n"
                f"{n_requests} requests across {len(domains)} domains."
            ),
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "item": domains,
        "variable": [
            {"key": "baseUrl", "value": PROD_BASE, "type": "string"},
            {"key": "api_key", "value": "", "type": "string"},
        ],
    }


def _postman_key() -> str:
    env_path = _BACKEND.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("POSTMAN_API_KEY="):
                return line.split("=", 1)[1].strip()
    key = os.environ.get("POSTMAN_API_KEY")
    if not key:
        print("[ERROR] POSTMAN_API_KEY not found in .env")
        sys.exit(1)
    return key


def publish(collection: dict) -> None:
    api_key = _postman_key()
    req = urllib.request.Request("https://api.getpostman.com/workspaces", headers={"X-Api-Key": api_key})
    ws = json.load(urllib.request.urlopen(req))["workspaces"]
    ws_id = next(w["id"] for w in ws if w["name"] == "Brubru EU Data API")

    list_req = urllib.request.Request(
        f"https://api.getpostman.com/collections?workspace={ws_id}", headers={"X-Api-Key": api_key}
    )
    existing = json.load(urllib.request.urlopen(list_req)).get("collections", [])

    match = next((c for c in existing if c.get("name") == COLLECTION_NAME), None)
    body = json.dumps({"collection": collection}).encode()
    if match:
        url, method = f"https://api.getpostman.com/collections/{match['uid']}", "PUT"
    else:
        url, method = f"https://api.getpostman.com/collections?workspace={ws_id}", "POST"
    req = urllib.request.Request(
        url, data=body, method=method, headers={"X-Api-Key": api_key, "Content-Type": "application/json"}
    )
    info = json.load(urllib.request.urlopen(req)).get("collection", {})
    print(f"[OK] {'Updated' if match else 'Created'} collection: {info.get('name')}  (uid {info.get('uid')})")

    # Retire the two old split collections now folded into this one.
    for c in existing:
        if c.get("name") in _RETIRE_NAMES:
            del_req = urllib.request.Request(
                f"https://api.getpostman.com/collections/{c['uid']}", method="DELETE",
                headers={"X-Api-Key": api_key},
            )
            urllib.request.urlopen(del_req)
            print(f"[OK] Deleted old split collection: {c['name']}")
    print("     Open: https://www.postman.com/beresol-565660/workspace/brubru-eu-data-api/")


if __name__ == "__main__":
    coll = build_collection()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(coll, indent=2))
    print(f"[OK] Built '{COLLECTION_NAME}' -> {OUT_PATH} ({sum(_count(d) for d in coll['item'])} requests)")
    for domain in coll["item"]:
        print(f"  {domain['name']} ({_count(domain)} requests)")
        for src in domain["item"]:
            if "request" in src:
                # flat domain (single body): requests sit directly under it.
                continue
            if src.get("item") and "request" in src["item"][0]:
                print(f"    {src['name']}: {len(src['item'])}")
            else:
                print(f"    {src['name']}:")
                for sub in src["item"]:
                    print(f"      {sub['name']}: {len(sub['item'])}")
    if "--publish" in sys.argv:
        publish(coll)
    else:
        print("     Re-run with --publish to push it (and retire the two old split collections).")
