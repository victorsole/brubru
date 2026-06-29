"""Phase 4 Wave 2.2 — load the EU directory `person` rows (official EU-declared accounts) as
Commissioners / EC officials.

Source: the cached EU social-media directory (person rows we skipped in the org waves). The
27-member von der Leyen II college roster (from Wikipedia, 28 Jun 2026) classifies each person
as 'commissioner' vs 'ec_official' (spokespersons + institution presidents). entity_key =
accent-folded name slug (merges the "Suica"/"Šuica" duplicate). Official -> verified.

Run:  python3.12 scripts/load_directory_persons.py            # dry-run
      python3.12 scripts/load_directory_persons.py --apply
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import unicodedata
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

CACHE = ("/private/tmp/claude-501/-Users-victorsole-Documents-GitHub-brubru/"
         "467dde5d-b102-4717-9258-3805a4ea37f8/scratchpad/eu_social_directory_raw.json")

NETWORK_MAP = {"twitter": "x"}
_TRANSLIT = {"ł": "l", "ø": "o", "đ": "d", "þ": "th", "ß": "ss", "æ": "ae", "œ": "oe", "ð": "d", "ı": "i"}

# von der Leyen Commission II (2024-2029), 27 members (Wikipedia, 28 Jun 2026).
COMMISSIONERS = [
    "Ursula von der Leyen", "Kaja Kallas", "Teresa Ribera", "Henna Virkkunen",
    "Stéphane Séjourné", "Roxana Mînzatu", "Raffaele Fitto", "Maroš Šefčovič",
    "Valdis Dombrovskis", "Apostolos Tzitzikostas", "Magnus Brunner", "Ekaterina Zaharieva",
    "Christophe Hansen", "Wopke Hoekstra", "Piotr Serafin", "Jessika Roswall",
    "Maria Luís Albuquerque", "Costas Kadis", "Hadja Lahbib", "Glenn Micallef",
    "Dan Jørgensen", "Marta Kos", "Dubravka Šuica", "Olivér Várhelyi", "Jozef Síkela",
    "Andrius Kubilius", "Michael McGrath",
]


def _toks(s):
    s = "".join(_TRANSLIT.get(c, c) for c in (s or "").lower())
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return set(re.findall(r"[a-z0-9]+", s))


def _slug(s):
    s = "".join(_TRANSLIT.get(c, c) for c in (s or "").lower())
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", s)).strip("_")


_COMM_TOKENS = [( _toks(c), c) for c in COMMISSIONERS]


def is_commissioner(name):
    t = _toks(name)
    if len(t) < 2:
        return None
    for ctoks, cname in _COMM_TOKENS:
        if (ctoks <= t or t <= ctoks) and len(t & ctoks) >= 2:
            return cname
    return None


_REFRESH = ["entity_type", "entity_key", "entity_name", "platform", "scope", "handle",
            "status", "verified", "verification_source", "discovery_source", "extra"]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    rows = [r for r in json.load(open(CACHE)) if (r.get("account_type_keys") or "") == "person"]
    db = SessionLocal()
    stats = {"person_rows": len(rows), "written": 0, "commissioner_accounts": 0,
             "ec_official_accounts": 0, "commissioners_covered": set(), "skipped": 0}
    seen = set()
    for r in rows:
        name = r.get("name") or ""
        net = (r.get("network_keys") or "").strip()
        url = (r.get("url") or "").strip()
        if not net or not url:
            stats["skipped"] += 1; continue
        platform = NETWORK_MAP.get(net, net)
        cname = is_commissioner(name)
        inst = r.get("institution_keys") or ""
        if cname:
            etype = "commissioner"; ekey = _slug(cname)
            stats["commissioners_covered"].add(cname)
        else:
            etype = "ec_official"; ekey = _slug(name)
        is_pres = inst in ("european_council, council_of_the_european_union", "european_parliament",
                           "european_economic_and_social_committee")
        if url in seen:
            continue
        seen.add(url)
        stats["written"] += 1
        stats["commissioner_accounts" if cname else "ec_official_accounts"] += 1
        if args.apply:
            row = {"entity_type": etype, "entity_key": ekey, "entity_name": name,
                   "platform": platform, "scope": "personal", "handle": url.rstrip("/").split("/")[-1].split("?")[0],
                   "account_url": url, "status": "verified", "verified": True,
                   "verification_source": "eu_directory", "discovery_source": "eu_directory",
                   "content_fetch_enabled": False,
                   "extra": {"role": "commissioner" if cname else ("president" if is_pres else "ec_official"),
                             "institution_keys": inst, "portfolio_name": cname}}
            stmt = pg_insert(SocialAccount).values(**row)
            stmt = stmt.on_conflict_do_update(
                constraint="social_accounts_url_uq",
                set_={c: getattr(stmt.excluded, c) for c in _REFRESH} | {"updated_at": func.now()})
            db.execute(stmt)
    if args.apply:
        db.commit()
    print(f"[{'APPLIED' if args.apply else 'DRY-RUN'}] person_rows={stats['person_rows']} written={stats['written']} "
          f"commissioner_accts={stats['commissioner_accounts']} ec_official_accts={stats['ec_official_accounts']} skipped={stats['skipped']}")
    print(f"commissioners covered: {len(stats['commissioners_covered'])}/27")
    missing = [c for c in COMMISSIONERS if c not in stats['commissioners_covered']]
    print("commissioners NOT in directory:", missing)
    db.close()


if __name__ == "__main__":
    main()
