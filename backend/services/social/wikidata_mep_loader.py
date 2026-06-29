"""Phase 4.2.1 — Wikidata MEP bulk: map current MEPs' social handles into social_accounts.

Source: Wikidata SPARQL. Current MEPs = position held (P39) Member of the EP (Q27169) with
parliamentary-term qualifier (P2937) = Tenth EP (Q114425478). entity_type='mep',
entity_key=QID (stable; EP-id reconciled in the EP-API step). discovery_source='wikidata',
status='candidate' (a later official/cross-source confirm promotes to 'verified').
content_fetch_enabled stays false. No fabrication: only handles Wikidata actually holds.
"""
from __future__ import annotations

import json
import logging
import time
import urllib.parse
import urllib.request

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert

from models.social_account import SocialAccount

logger = logging.getLogger("wikidata-mep")

_ENDPOINT = "https://query.wikidata.org/sparql"
_UA = "BrubruBot/1.0 (https://brubru.beresol.eu; hello@beresol.eu)"
MEP_POSITION = "Q27169"
TERM10 = "Q114425478"

# SPARQL var -> (platform code, url template). Mastodon handled specially (user@instance).
PLATFORMS = [
    ("x", "x", "https://x.com/{h}"),
    ("ig", "instagram", "https://www.instagram.com/{h}/"),
    ("fb", "facebook", "https://www.facebook.com/{h}"),
    ("li", "linkedin", "https://www.linkedin.com/in/{h}"),          # P6634 personal
    ("tt", "tiktok", "https://www.tiktok.com/@{h}"),
    ("yt", "youtube", "https://www.youtube.com/channel/{h}"),       # P2397 channel id
    ("bs", "bluesky", "https://bsky.app/profile/{h}"),
]
_PROPS = {"x": "P2002", "ig": "P2003", "fb": "P2013", "li": "P6634",
          "tt": "P7085", "yt": "P2397", "ma": "P4033", "bs": "P12361"}

_REFRESH = ["entity_type", "entity_key", "entity_name", "platform", "scope", "handle",
            "discovery_source", "extra"]


def fetch_mep_socials(position=MEP_POSITION, term=TERM10) -> list[dict]:
    opt = "\n".join(f"  OPTIONAL {{ ?mep wdt:{p} ?{v}. }}" for v, p in _PROPS.items())
    q = (f"SELECT ?mep ?mepLabel " + " ".join(f"?{v}" for v in _PROPS) + " WHERE {\n"
         f"  ?mep p:P39 ?st. ?st ps:P39 wd:{position}. ?st pq:P2937 wd:{term}.\n{opt}\n"
         '  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }\n}')
    url = _ENDPOINT + "?format=json&query=" + urllib.parse.quote(q)
    req = urllib.request.Request(url, headers={"User-Agent": _UA,
                                 "Accept": "application/sparql-results+json"})
    # WDQS aggressively rate-limits (1 req/min during outages) -> backoff + retry on 429.
    for attempt in range(4):
        try:
            data = json.loads(urllib.request.urlopen(req, timeout=120).read().decode())
            return data["results"]["bindings"]
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 3:
                logger.warning("Wikidata 429; waiting 65s (attempt %d)", attempt + 1)
                time.sleep(65)
                continue
            raise


def _rows_from_binding(b: dict) -> list[dict]:
    qid = b["mep"]["value"].split("/")[-1]
    name = b.get("mepLabel", {}).get("value")
    out = []
    for var, platform, tmpl in PLATFORMS:
        if var not in b:
            continue
        h = b[var]["value"].strip()
        if not h:
            continue
        out.append(_row(qid, name, platform, h, tmpl.format(h=urllib.parse.quote(h, safe="@._-"))))
    # mastodon: P4033 stored as user@instance
    if "ma" in b and b["ma"]["value"].strip():
        v = b["ma"]["value"].strip()
        if "@" in v:
            user, inst = v.split("@", 1)
            out.append(_row(qid, name, "mastodon", v, f"https://{inst}/@{user}"))
    return out


def _row(qid, name, platform, handle, url):
    return {"entity_type": "mep", "entity_key": qid, "entity_name": name,
            "platform": platform, "scope": "personal", "handle": handle, "account_url": url,
            "status": "candidate", "verified": False, "discovery_source": "wikidata",
            "content_fetch_enabled": False, "extra": {"wikidata_qid": qid}}


def load(db, bindings: list[dict], *, dry_run: bool = False) -> dict:
    stats = {"meps": len({b["mep"]["value"] for b in bindings}), "written": 0,
             "by_platform": {}, "dry_run": dry_run}
    seen = set()
    for b in bindings:
        for row in _rows_from_binding(b):
            u = row["account_url"]
            if u in seen:
                continue
            seen.add(u)
            stats["by_platform"][row["platform"]] = stats["by_platform"].get(row["platform"], 0) + 1
            stats["written"] += 1
            if not dry_run:
                stmt = pg_insert(SocialAccount).values(**row)
                stmt = stmt.on_conflict_do_update(
                    constraint="social_accounts_url_uq",
                    set_={c: getattr(stmt.excluded, c) for c in _REFRESH} | {"updated_at": func.now()})
                db.execute(stmt)
    if not dry_run:
        db.commit()
    return stats
