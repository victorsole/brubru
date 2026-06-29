"""Phase 4 Wave 2.3 — EU journalist influencers from outlet rosters.

Sources (28 Jun 2026): Politico Europe (Feedspot list, name->X), Sifted newsroom (LinkedIn/X/
Bluesky), Contexte EU newsroom (Bluesky/LinkedIn, role-filtered to journalists). Euractiv
contact-us lists only desks, no individuals -> skipped. entity_type='eu_influencer',
entity_key = accent-folded name slug (cross-source dedup), status='candidate'. No fabrication:
only handles the rosters actually expose.

Run:  python3.12 scripts/load_influencers.py            # dry-run
      python3.12 scripts/load_influencers.py --apply
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import unicodedata
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv  # noqa: E402
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")
logging.disable(logging.INFO)

from sqlalchemy import func  # noqa: E402
from sqlalchemy.dialects.postgresql import insert as pg_insert  # noqa: E402
from core.database import SessionLocal, engine  # noqa: E402
engine.echo = False
from models.social_account import SocialAccount  # noqa: E402

_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
_TRANSLIT = {"ł": "l", "ø": "o", "đ": "d", "þ": "th", "ß": "ss", "æ": "ae", "œ": "oe", "ð": "d", "ı": "i"}
CONTEXTE_CACHE = ("/private/tmp/claude-501/-Users-victorsole-Documents-GitHub-brubru/"
                  "467dde5d-b102-4717-9258-3805a4ea37f8/scratchpad/contexte_cards.json")

# Sifted newsroom (real social URLs only; author-page links dropped). From the roster page.
SIFTED = {
    "Freya Pratty": ["https://www.linkedin.com/in/freyapratty111"],
    "Mimi Billing": ["https://www.linkedin.com/in/mimibilling"],
    "Daphné Leprince-Ringuet": ["https://www.linkedin.com/in/daphne-leprince-ringuet"],
    "Anne Sraders": ["https://www.linkedin.com/in/anne-sraders-54222b95"],
    "Éanna Kelly": ["https://www.linkedin.com/in/eannakelly"],
    "John Thornhill": ["https://www.linkedin.com/in/john-thornhill-5266528"],
    "Amy Lewin": ["https://twitter.com/amyrlewin", "https://bsky.app/profile/amyrlewin.bsky.social"],
    "Martin Coulter": ["https://www.linkedin.com/in/martin-coulter-245056149"],
    "Tom Nugent": ["https://www.linkedin.com/in/tnugent92"],
    "Maya Dharampal-Hornby": ["https://www.linkedin.com/in/maya-dharampal-hornby"],
}
_NEWS = re.compile(r"journalis|r[ée]dac|reporter|editor|correspond|desk|cheffe?\b|news|bureau", re.I)
_EXCL = re.compile(r"account|acquisition|marketing|brand|sales|product|developer|data eng|"
                   r"cto|ceo|coo|cfo|hr|talent|legal|finance|ops|design|growth|revenue|"
                   r"customer|partner manager|proofreader|apprentice", re.I)


def _slug(s):
    s = "".join(_TRANSLIT.get(c, c) for c in (s or "").lower())
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", s)).strip("_")


def _platform(url):
    u = url.lower()
    if "twitter.com" in u or "x.com" in u:
        return "x"
    if "linkedin.com" in u:
        return "linkedin"
    if "bsky.app" in u:
        return "bluesky"
    if "instagram.com" in u:
        return "instagram"
    if "threads.net" in u:
        return "threads"
    return None


def _canon(url):
    return url.split("?")[0].split("#")[0].rstrip("/")


def fetch_politico():
    html = urllib.request.urlopen(urllib.request.Request(
        "https://journalists.feedspot.com/politico_europe_journalists/", headers={"User-Agent": _UA}), timeout=40).read().decode("utf-8", "ignore")
    heads = [(m.start(), re.sub(r"<[^>]+>", "", m.group(1)).strip())
             for m in re.finditer(r"<h\d[^>]*>(\s*\d+\.\s*.*?)</h\d>", html)]
    out = {}
    for i, (pos, head) in enumerate(heads):
        name = re.sub(r"^\d+\.\s*", "", head)
        end = heads[i + 1][0] if i + 1 < len(heads) else len(html)
        seg = html[pos:end]
        m = re.search(r'(?:twitter|x)\.com/([A-Za-z0-9_]+)', seg)
        if m and m.group(1).lower() != "politicoeurope":
            out[name] = [f"https://x.com/{m.group(1)}"]
    return out


def load_contexte_newsroom():
    cards = json.load(open(CONTEXTE_CACHE))
    out = {}
    for c in cards:
        parts = [p.strip() for p in (c["blocks"][0] if c["blocks"] else "").split("\n") if p.strip()]
        if len(parts) < 3:
            continue
        name, role = f"{parts[0]} {parts[1]}", parts[2]
        if _NEWS.search(role) and not _EXCL.search(role):
            socials = [s for s in c["socials"] if _platform(s)]
            if socials:
                out[name] = socials
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    sources = {"politico": fetch_politico(), "sifted": SIFTED, "contexte": load_contexte_newsroom()}
    for s, d in sources.items():
        print(f"  {s}: {len(d)} journalists")
    db = SessionLocal()
    seen = set()
    stats = {"written": 0, "by_platform": {}, "by_source": {}, "people": set()}
    for source, people in sources.items():
        for name, urls in people.items():
            for url in urls:
                plat = _platform(url)
                cu = _canon(url)
                if not plat or cu in seen:
                    continue
                seen.add(cu)
                stats["written"] += 1
                stats["people"].add(_slug(name))
                stats["by_platform"][plat] = stats["by_platform"].get(plat, 0) + 1
                stats["by_source"][source] = stats["by_source"].get(source, 0) + 1
                if args.apply:
                    row = {"entity_type": "eu_influencer", "entity_key": _slug(name), "entity_name": name,
                           "platform": plat, "scope": "personal", "handle": cu.split("/")[-1].lstrip("@"),
                           "account_url": cu, "status": "candidate", "verified": False,
                           "discovery_source": source, "content_fetch_enabled": False,
                           "extra": {"outlet": source}}
                    stmt = pg_insert(SocialAccount).values(**row)
                    stmt = stmt.on_conflict_do_update(
                        constraint="social_accounts_url_uq",
                        set_={c: getattr(stmt.excluded, c) for c in
                              ["entity_type", "entity_key", "entity_name", "platform", "scope",
                               "handle", "discovery_source", "extra"]} | {"updated_at": func.now()})
                    db.execute(stmt)
    if args.apply:
        db.commit()
    print(f"[{'APPLIED' if args.apply else 'DRY-RUN'}] accounts={stats['written']} distinct_people={len(stats['people'])}")
    print("by_platform:", stats["by_platform"])
    print("by_source:", stats["by_source"])
    db.close()


if __name__ == "__main__":
    main()
