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
import re
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

_REFRESH = ["entity_type", "entity_key", "platform", "scope", "handle",
             "discovery_source", "extra"]

# Label fallback order. Wikidata moved many people's names from per-language labels to the
# language-neutral `mul` label, so an "en"-only label service returns the bare QID as the
# label for them (Bernd Lange Q65437 holds ONLY a `mul` label). That is how 18 rows / 8 MEPs
# ended up named 'Q65437' etc. on 29 Jun 2026. en, then mul, then every EU language.
_EU_LANGS = ["fr", "de", "es", "it", "nl", "pl", "pt", "hu", "cs", "sk", "sl", "hr", "ro",
             "bg", "el", "sv", "da", "fi", "et", "lv", "lt", "ga", "mt"]
LABEL_LANGS = ["en", "mul"] + _EU_LANGS
# EP country-of-representation -> the MEP's own label language (tried right after en, mul).
COUNTRY_LANG = {"AT": "de", "BE": "nl", "BG": "bg", "HR": "hr", "CY": "el", "CZ": "cs",
                "DK": "da", "EE": "et", "FI": "fi", "FR": "fr", "DE": "de", "GR": "el",
                "HU": "hu", "IE": "ga", "IT": "it", "LV": "lv", "LT": "lt", "LU": "fr",
                "MT": "mt", "NL": "nl", "PL": "pl", "PT": "pt", "RO": "ro", "SK": "sk",
                "SI": "sl", "ES": "es", "SE": "sv"}
_BARE_QID = re.compile(r"^Q\d+$")
_EP_MEPS = ("https://data.europarl.europa.eu/api/v2/meps/show-current"
            "?format=application%2Fld%2Bjson")


def is_bare_qid(name) -> bool:
    return bool(name) and bool(_BARE_QID.match(str(name).strip()))


def clean_name(name):
    """A usable display name, or None. Never a bare QID, never blank."""
    n = (name or "").strip()
    return None if not n or is_bare_qid(n) else n


def pick_label(labels: dict, own_lang: str | None = None):
    """First usable label from a Wikidata EntityData `labels` dict: en, mul, the MEP's own
    language, the other EU languages, then any label at all."""
    order = ["en", "mul"] + ([own_lang] if own_lang else []) + _EU_LANGS
    for lang in order:
        v = clean_name((labels.get(lang) or {}).get("value"))
        if v:
            return v, lang
    for lang, lv in sorted(labels.items()):
        v = clean_name((lv or {}).get("value"))
        if v:
            return v, lang
    return None, None


def ep_display_name(m: dict):
    """'Bernd Lange' from an EP show-current record (its `label` is 'Bernd LANGE')."""
    gn, fn = (m.get("givenName") or "").strip(), (m.get("familyName") or "").strip()
    return clean_name(f"{gn} {fn}".strip()) or clean_name(m.get("label"))


def fetch_ep_current() -> dict:
    """EP Open Data current-MEP directory: {ep_id: record}. Raises on failure (callers decide)."""
    req = urllib.request.Request(_EP_MEPS, headers={"User-Agent": _UA,
                                                    "Accept": "application/ld+json"})
    data = json.loads(urllib.request.urlopen(req, timeout=60).read().decode())
    return {m["identifier"]: m for m in data.get("data", [])}


def fetch_entity(qid: str) -> dict:
    url = f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"
    req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept": "application/json"})
    data = json.loads(urllib.request.urlopen(req, timeout=30).read().decode())
    ents = data.get("entities", {})
    return ents.get(qid) or (next(iter(ents.values())) if ents else {})


def entity_ep_ids(entity: dict) -> list[str]:
    """P1186 (MEP directory ID) values on a Wikidata entity."""
    out = []
    for c in entity.get("claims", {}).get("P1186", []):
        v = c.get("mainsnak", {}).get("datavalue", {}).get("value")
        if v:
            out.append(str(v))
    return out


def fetch_mep_socials(position=MEP_POSITION, term=TERM10) -> list[dict]:
    opt = "\n".join(f"  OPTIONAL {{ ?mep wdt:{p} ?{v}. }}" for v, p in _PROPS.items())
    opt += "\n  OPTIONAL { ?mep wdt:P1186 ?epid. }"
    langs = ",".join(LABEL_LANGS)
    q = (f"SELECT ?mep ?mepLabel ?epid " + " ".join(f"?{v}" for v in _PROPS) + " WHERE {\n"
         f"  ?mep p:P39 ?st. ?st ps:P39 wd:{position}. ?st pq:P2937 wd:{term}.\n{opt}\n"
         f'  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "{langs}". }}\n}}')
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


def binding_name(b: dict, ep_names: dict | None = None):
    """Display name for a binding: the Wikidata label, else the EP directory name via P1186,
    else None. The WDQS label service returns the QID itself when no label exists in the
    requested languages, so a bare QID is treated as "no label", never stored as a name."""
    name = clean_name(b.get("mepLabel", {}).get("value"))
    if name:
        return name
    epid = (b.get("epid") or {}).get("value")
    if epid and ep_names:
        return clean_name(ep_names.get(str(epid)))
    return None


def needs_name_fallback(bindings: list[dict]) -> bool:
    return any(not clean_name(b.get("mepLabel", {}).get("value")) for b in bindings)


def _rows_from_binding(b: dict, ep_names: dict | None = None) -> list[dict]:
    qid = b["mep"]["value"].split("/")[-1]
    name = binding_name(b, ep_names)
    if name is None:
        logger.warning("no label for %s in any language or the EP directory; entity_name left NULL", qid)
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


def load(db, bindings: list[dict], *, dry_run: bool = False,
         ep_names: dict | None = None) -> dict:
    stats = {"meps": len({b["mep"]["value"] for b in bindings}), "written": 0,
             "by_platform": {}, "dry_run": dry_run, "unnamed_meps": set()}
    seen = set()
    for b in bindings:
        rows = _rows_from_binding(b, ep_names)
        if rows and rows[0]["entity_name"] is None:
            stats["unnamed_meps"].add(rows[0]["entity_key"])
        for row in rows:
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
                    set_={c: getattr(stmt.excluded, c) for c in _REFRESH}
                    # A missing label this run must not wipe a name we already hold.
                    | {"entity_name": func.coalesce(stmt.excluded.entity_name,
                                                    SocialAccount.__table__.c.entity_name),
                       "updated_at": func.now()})
                db.execute(stmt)
    if not dry_run:
        db.commit()
    stats["unnamed_meps"] = sorted(stats["unnamed_meps"])
    return stats
