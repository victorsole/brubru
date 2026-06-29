"""Phase 4.2.1 step 2 — reconcile EP Open Data API official MEP accounts with the Wikidata wave.

Three effects (decisions locked 28 Jun 2026):
  1. entity_key unification: re-key existing Wikidata MEP rows from QID -> official EP id
     (match by normalised name; QID kept in extra). MEPs join Brubru EP data.
  2. verification: where the EP API confirms the SAME (MEP, platform, handle), flip the row
     candidate -> verified (official MEP-declared = highest trust).
  3. EP-only inserts: official accounts the Wikidata wave missed (incl. the ~100 MEPs with no
     Wikidata socials) -> new verified rows.
Matched at (EP-id, platform, normalised-handle) to avoid false merges; differing handles on the
same platform are both kept (honest: could be a handle change or a 2nd account).
"""
from __future__ import annotations

import json
import logging
import re
import unicodedata

from sqlalchemy import func, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from models.social_account import SocialAccount

logger = logging.getLogger("ep-mep-reconcile")

TYPE_MAP = {"TWT": "x", "IST": "instagram", "FBW": "facebook", "FBP": "facebook",
            "LNK": "linkedin", "YTB": "youtube", "BLG": "blogs", "TLG": "telegram", "MST": "mastodon"}
_REFRESH = ["entity_type", "entity_key", "entity_name", "platform", "scope", "handle",
            "status", "verified", "verification_source", "discovery_source", "extra"]


# Latin letters that NFKD does NOT decompose to ASCII (would be dropped otherwise).
_TRANSLIT = {"ł": "l", "ø": "o", "đ": "d", "þ": "th", "ß": "ss", "æ": "ae", "œ": "oe", "ð": "d", "ı": "i"}


def _norm_tokens(s: str) -> set:
    s = "".join(_TRANSLIT.get(c, c) for c in (s or "").lower())
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return set(re.findall(r"[a-z0-9]+", s))


def _norm_name(s: str) -> str:
    return " ".join(sorted(_norm_tokens(s)))


def _match_ep(name: str, ep_exact: dict, ep_tokens: list):
    """Exact normalised-name match, else guarded subset (one name's tokens fully contained in
    the other, >=2 shared incl. the longest token as a surname proxy) with a UNIQUE candidate."""
    nn = _norm_name(name)
    if nn in ep_exact:
        return ep_exact[nn]
    t = _norm_tokens(name)
    if len(t) < 2:
        return None
    surname = max(t, key=len)
    cands = []
    for etoks, eid in ep_tokens:
        if surname in etoks and (t <= etoks or etoks <= t) and len(t & etoks) >= 2:
            cands.append(eid)
    return cands[0] if len(set(cands)) == 1 else None  # unique match only (no ambiguity)


def _canon_url(u: str) -> str:
    u = (u or "").split("?")[0].split("#")[0].rstrip("/")
    return u


def _handle(platform: str, url: str) -> str:
    """Normalised handle for matching: last path segment, lower, strip @. FB share-links and
    other handle-less urls fall back to the canonical url itself."""
    segs = [s for s in _canon_url(url).split("/")[3:] if s]
    if not segs:
        return _canon_url(url).lower()
    h = segs[-1].lstrip("@").lower()
    if platform == "facebook" and (segs[0] in ("share", "profile.php") or h.isdigit()):
        return _canon_url(url).lower()
    return h


def load_ep(cache_path: str):
    data = json.load(open(cache_path))
    ep_name_to_id, ep_meta, ep_accounts = {}, {}, {}
    for m in data:
        eid = m["ep_id"]
        nm = _norm_name(f"{m.get('givenName','')} {m.get('familyName','')}") or _norm_name(m.get("label", ""))
        if nm:
            ep_name_to_id.setdefault(nm, eid)
        ep_meta[eid] = {"label": m.get("label"), "country": m.get("country"), "group": m.get("group")}
        accs = []
        for a in m["accounts"]:
            plat = TYPE_MAP.get(a.get("type"))
            url = a.get("url")
            if plat and url:
                accs.append({"platform": plat, "url": _canon_url(url), "handle": _handle(plat, url)})
        ep_accounts[eid] = accs
    ep_tokens = [(_norm_tokens(f"{m.get('givenName','')} {m.get('familyName','')}") or _norm_tokens(m.get("label", "")), m["ep_id"]) for m in data]
    return ep_name_to_id, ep_meta, ep_accounts, ep_tokens


def reconcile(db, cache_path: str, *, dry_run: bool = False) -> dict:
    ep_name_to_id, ep_meta, ep_accounts, ep_tokens = load_ep(cache_path)
    rows = db.execute(text("SELECT id, entity_key, entity_name, platform, handle, account_url "
                           "FROM social_accounts WHERE entity_type='mep'")).mappings().all()
    # group existing rows by QID
    by_qid = {}
    for r in rows:
        by_qid.setdefault(r["entity_key"], []).append(r)

    st = {"wikidata_qids": len(by_qid), "matched_to_ep": 0, "unmatched_qids": 0,
          "rows_rekeyed": 0, "rows_verified": 0, "ep_only_inserted": 0, "dry_run": dry_run}
    # existing (ep_id, platform, handle) set after rekey, to know what EP accounts are new
    existing_keyed = set()
    qid_to_ep = {}
    for qid, qrows in by_qid.items():
        eid = _match_ep(qrows[0]["entity_name"], ep_name_to_id, ep_tokens)
        if not eid:
            st["unmatched_qids"] += 1
            continue
        st["matched_to_ep"] += 1
        qid_to_ep[qid] = eid
        ep_handles = {(a["platform"], a["handle"]) for a in ep_accounts.get(eid, [])}
        for r in qrows:
            hl = _handle(r["platform"], r["account_url"])
            confirmed = (r["platform"], hl) in ep_handles
            existing_keyed.add((eid, r["platform"], hl))
            st["rows_rekeyed"] += 1
            if confirmed:
                st["rows_verified"] += 1
            if not dry_run:
                ex = {"wikidata_qid": qid}
                stmt = text("UPDATE social_accounts SET entity_key=:e, status=:s, verified=:v, "
                            "verification_source=:vs, extra=extra||CAST(:ex AS jsonb), updated_at=now() WHERE id=:i")
                db.execute(stmt, {"e": eid, "s": "verified" if confirmed else "candidate",
                                  "v": confirmed, "vs": "ep_open_data" if confirmed else None,
                                  "ex": json.dumps(ex), "i": r["id"]})
    # EP-only accounts: official accounts not present (by ep_id,platform,handle) in the rekeyed set
    for eid, accs in ep_accounts.items():
        for a in accs:
            key = (eid, a["platform"], a["handle"])
            if key in existing_keyed:
                continue
            existing_keyed.add(key)
            st["ep_only_inserted"] += 1
            if not dry_run:
                row = {"entity_type": "mep", "entity_key": eid, "entity_name": ep_meta[eid]["label"],
                       "platform": a["platform"], "scope": "personal", "handle": a["handle"],
                       "account_url": a["url"], "status": "verified", "verified": True,
                       "verification_source": "ep_open_data", "discovery_source": "ep_api",
                       "content_fetch_enabled": False,
                       "extra": {"ep_mep_id": eid, "country": ep_meta[eid]["country"], "group": ep_meta[eid]["group"]}}
                stmt = pg_insert(SocialAccount).values(**row)
                stmt = stmt.on_conflict_do_update(
                    constraint="social_accounts_url_uq",
                    set_={c: getattr(stmt.excluded, c) for c in _REFRESH} | {"updated_at": func.now()})
                db.execute(stmt)
    if not dry_run:
        db.commit()
    return st
