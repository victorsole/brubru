"""Phase 4.1 — load the official EU social-media directory (WebTools WBQL) into social_accounts.

Source backend: https://webtools.europa.eu/rest/wbase/wbql/9HmRO2UdOH/5/sheet1?limit&offset
(see docs/api/eu_social_media_directory.md). Account MAPPING only: content_fetch_enabled stays
false. Idempotent UPSERT on account_url (the source repeats urls). Mapping decisions (28 Jun
2026): entity_key = stable slug; multi-institution = owner is first key + full list in extra;
empty scope = 'unspecified'; person rows route to Wave 2 (skipped here).
"""
from __future__ import annotations

import json
import logging
import re
import time
import urllib.request
from urllib.parse import urlparse

from sqlalchemy.dialects.postgresql import insert as pg_insert

from models.social_account import SocialAccount

logger = logging.getLogger("eu-social-directory")

_WBQL = "https://webtools.europa.eu/rest/wbase/wbql/9HmRO2UdOH/5/sheet1"
_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://european-union.europa.eu/contact-eu/social-media-channels_en",
}

# --- mapping tables (audited 28 Jun 2026) ------------------------------------- #
NETWORK_MAP = {"twitter": "x"}   # else identity; empty -> skip

SCOPE_MAP = {
    "central_account": "central", "local_office": "office", "subdivision": "subdivision",
    "specialised_department": "department",
    # "person" handled separately (routes to Wave 2); "" -> 'unspecified'
}

# Agency name -> economy_bodies code resolution (D2: reuse the existing agency registry).
# ALIAS_AC: extracted-acronym aliases for renamed agencies (directory lags the rename).
ALIAS_AC = {"emcdda": "euda"}
# NAME_ALIAS: normalised directory NAME -> code, for the handful with no extractable acronym
# or an outdated name (curated + audited 28 Jun 2026; explicit beats fuzzy to avoid mis-maps).
NAME_ALIAS = {
    "euinstituteforsecuritystudies": "euiss",
    "europeaninstituteofinnovationtechnology": "eit",
    "europeanresearchcouncil": "ercea",
    "europeanaviationsafetyagency": "easa",   # directory uses the pre-2018 name (no "Union")
    ("europeanunionagencyfortheoperationalmanagementoflargescaleit"
     "systemsintheareaoffreedomsecurityandjustice"): "eu_lisa",
    "researchexecutiveagency": "rea",
    "europeanjointundertakingforiterandthedevelopmentoffusionenergy": "f4e",
}

# single clean institution_keys -> (entity_type, entity_key slug)
INSTITUTION_MAP = {
    "european_commission": ("institution", "european_commission"),
    "european_external_action_service": ("institution", "eeas"),
    "european_parliament": ("institution", "european_parliament"),
    "european_economic_and_social_committee": ("institution", "eesc"),
    "committee_of_the_regions": ("institution", "cor"),
    "council_of_the_european_union": ("institution", "council"),
    "european_council": ("institution", "european_council"),
    "publications_office": ("institution", "publications_office"),
    "european_court_of_auditors": ("institution", "eca"),
    "european_investment_bank": ("institution", "eib"),
    "european_personnel_selection_office": ("institution", "epso"),
    "court_of_justice_of_the_european_union": ("institution", "cjeu"),
    "european_data_protection_supervisor": ("institution", "edps"),
    "european_ombudsman": ("institution", "ombudsman"),
    "european_central_bank": ("institution", "ecb"),
}

_REFRESH = ["entity_type", "entity_key", "entity_name", "platform", "scope", "handle",
            "platform_account_id", "discovery_source", "extra"]


def fetch_directory(pace: float = 2.0, page: int = 300) -> list[dict]:
    """Live paged pull of the whole directory (1,357 rows). Paced + retried (rapid hits 422)."""
    def _get(off):
        for _ in range(4):
            try:
                req = urllib.request.Request(f"{_WBQL}?limit={page}&offset={off}", headers=_HEADERS)
                with urllib.request.urlopen(req, timeout=60) as r:
                    return json.loads(r.read().decode())
            except Exception:
                time.sleep(pace + 1)
        return {}
    first = _get(0)
    total = first.get("count", 0)
    rows = list(first.get("data", []))
    off = page
    while off < total:
        time.sleep(pace)
        rows += _get(off).get("data", [])
        off += page
    for r in rows:
        r.pop("_id", None)
    return rows


def _slug(s: str) -> str:
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", (s or "").lower())).strip("_")


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _extract_acronym(name: str):
    m = re.search(r"\(([^)]{2,40})\)\s*$", name) or re.search(r"[-–]\s*([A-Za-z][A-Za-z0-9]{1,13})\s*$", name)
    if m:
        return m.group(1).strip()
    return name.strip() if re.fullmatch(r"[A-Z][A-Za-z]+", name.strip()) else None


def build_agency_index(db) -> dict:
    """{normalised acronym/name -> economy_bodies.code} for agency resolution. Reuses the
    existing registry (D2) so agency accounts get a canonical entity_key, not a fresh slug."""
    from sqlalchemy import text
    rows = db.execute(text("SELECT code, acronym, name FROM economy_bodies")).fetchall()
    by_ac = {_norm(r.acronym): r.code for r in rows if r.acronym}
    by_nm = {_norm(r.name): r.code for r in rows}
    return {"ac": by_ac, "nm": by_nm}


def resolve_agency(name: str, idx: dict | None):
    """-> (entity_key, resolved_to_registry: bool). EASME (defunct) and any miss fall back to a
    flagged slug — never a wrong canonical code (no fabrication)."""
    nn = _norm(name)
    if "(easme)" in name.lower() or "easme" in nn:
        return "easme", False          # dissolved 2021; group under one slug, flag defunct
    if not idx:
        return _slug(name), False
    if nn in NAME_ALIAS:
        return NAME_ALIAS[nn], True
    ac = _extract_acronym(name)
    nac = _norm(ac) if ac else ""
    if nac in ALIAS_AC:
        return ALIAS_AC[nac], True
    if nac and nac in idx["ac"]:
        return idx["ac"][nac], True
    if nn in idx["nm"]:
        return idx["nm"][nn], True
    return _slug(name), False           # real agency, just not in our registry -> flagged slug


# Trailing URL path segments that are VIEWS of an account, not the account.
# `segs[-1]` used to take them literally, so the European Parliament in the UK,
# Manon Aubry and 47 others were stored with handle "featured", "videos",
# "photo" or "about" (audit, 25 Aug 2026). Fetching still worked because it goes
# through platform_account_id, so nothing failed loudly -- but every surface
# keyed on handle (MEP Watch, Stakeholder Mapping, the social API, dedup) saw
# eight different accounts all called "@featured".
_VIEW_SEGMENTS = frozenset({
    "featured", "videos", "about", "feed", "posts", "photo", "photos",
    "profile", "albums", "sets", "info", "timeline", "blog", "playlists",
    "channels", "community", "home", "media", "likes", "with_replies",
    "shorts", "streams", "reels", "highlights", "tagged", "events",
})

# Path segments that introduce the identifier rather than being it:
# /user/EpinUk/featured, /channel/UCxxxx/featured, /c/Name, /in/person.
_CONTAINER_SEGMENTS = frozenset({"user", "channel", "c", "in", "company",
                                 "pages", "groups", "people", "photos"})


def _handle(url: str) -> str | None:
    """Last MEANINGFUL path segment of an account URL.

    Walks back from the end past view segments ("/featured", "/videos") and
    refuses to return a container word ("user", "channel", "in") on its own.
    Returns None rather than a wrong handle -- an empty handle is honest, a
    handle of "featured" is a fabricated identity.
    """
    try:
        segs = [s for s in urlparse(url).path.split("/") if s]
        while segs and segs[-1].lower() in _VIEW_SEGMENTS:
            segs.pop()
        if not segs:
            return None
        candidate = segs[-1].lstrip("@")
        if candidate.lower() in _CONTAINER_SEGMENTS:
            return None
        return candidate or None
    except Exception:
        return None


def transform(rec: dict, agency_index: dict | None = None) -> dict | None:
    """One directory record -> a social_accounts row dict, or None to skip (no fabrication)."""
    url = (rec.get("url") or "").strip()
    net = (rec.get("network_keys") or "").strip()
    if not url or not net:
        return None
    platform = NETWORK_MAP.get(net, net)

    atype = (rec.get("account_type_keys") or "").strip()
    if atype == "person":
        return None  # individuals -> Wave 2, not the org waves
    scope = SCOPE_MAP.get(atype, "unspecified")

    inst_raw = (rec.get("institution_keys") or "").strip()
    keys = [k.strip() for k in inst_raw.split(",") if k.strip()]
    shared = keys if len(keys) > 1 else []
    owner = keys[0] if keys else ""
    agency_unresolved = False
    if owner in INSTITUTION_MAP:
        entity_type, entity_key = INSTITUTION_MAP[owner]
    elif owner == "agency":
        entity_type = "eu_agency"
        entity_key, resolved = resolve_agency(rec.get("name", ""), agency_index)
        agency_unresolved = not resolved
    elif owner in ("other_body", ""):
        # other_body / untyped: try the registry (SRB->srb, F4E->f4e) before slugging.
        code, resolved = resolve_agency(rec.get("name", "") or "unknown", agency_index)
        if resolved:
            entity_type, entity_key = "eu_agency", code
        else:
            entity_type, entity_key = "institution", _slug(rec.get("name", "") or "unknown")
    else:
        entity_type, entity_key = "institution", _slug(owner)

    extra = {"institution_keys_raw": inst_raw, "account_type_keys": atype,
             "role_keys": rec.get("role_keys"), "topic_keys": rec.get("topic_keys"),
             "picture": rec.get("picture")}
    if shared:
        extra["shared_institutions"] = shared
    if agency_unresolved:
        extra["agency_unresolved"] = True   # real agency, not matched to economy_bodies (e.g. defunct)

    return {
        "entity_type": entity_type, "entity_key": entity_key, "entity_name": rec.get("name"),
        "platform": platform, "scope": scope, "handle": _handle(url), "account_url": url,
        "status": "candidate", "verified": False, "discovery_source": "eu_directory",
        "content_fetch_enabled": False, "extra": extra,
    }


def load(db, records: list[dict], *, only_central_clean: bool = False, only_agency: bool = False,
         account_types: set | None = None, dry_run: bool = False) -> dict:
    """Transform + UPSERT records. Subsets: only_central_clean = D5 step-1; only_agency = the
    125 lumped agency rows; account_types = include only these account_type_keys (e.g. the
    office wave {local_office, subdivision}), resolving across ALL institutions."""
    stats = {"input": len(records), "skipped": 0, "person": 0, "written": 0,
             "dry_run": dry_run, "by_platform": {}, "by_entity": {}, "unresolved_agency": 0}
    agency_index = build_agency_index(db)
    seen = set()
    for rec in records:
        inst = (rec.get("institution_keys") or "")
        if only_central_clean:
            if rec.get("account_type_keys") != "central_account":
                continue
            if "," in inst or inst in ("agency", "other_body", ""):
                continue
        if only_agency and inst != "agency":
            continue
        if account_types is not None and (rec.get("account_type_keys") or "") not in account_types:
            continue
        if (rec.get("account_type_keys") or "") == "person":
            stats["person"] += 1
        row = transform(rec, agency_index)
        if row is None:
            stats["skipped"] += 1
            continue
        if row["account_url"] in seen:   # in-batch dedup (source repeats urls)
            continue
        seen.add(row["account_url"])
        stats["by_platform"][row["platform"]] = stats["by_platform"].get(row["platform"], 0) + 1
        stats["by_entity"][row["entity_key"]] = stats["by_entity"].get(row["entity_key"], 0) + 1
        if row["extra"].get("agency_unresolved"):
            stats["unresolved_agency"] += 1
        if not dry_run:
            stmt = pg_insert(SocialAccount).values(**row)
            stmt = stmt.on_conflict_do_update(
                constraint="social_accounts_url_uq",
                set_={c: getattr(stmt.excluded, c) for c in _REFRESH} | {"updated_at": __import__("sqlalchemy").func.now()},
            )
            db.execute(stmt)
        stats["written"] += 1
    if not dry_run:
        db.commit()
    return stats
