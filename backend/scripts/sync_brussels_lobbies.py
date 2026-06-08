"""
Brussels lobbies — populate brussels_lobby_profiles + brussels_lobby_news_items.

Two phases (run --seed first, then --detect repeatedly / via cron):

  # 1. Seed the directory from the register (instant, no crawl)
  python3.12 scripts/sync_brussels_lobbies.py --seed

  # 2. Detect news per org (network crawl, tiered — run in batches)
  python3.12 scripts/sync_brussels_lobbies.py --detect --limit 300
  python3.12 scripts/sync_brussels_lobbies.py --detect --limit 300 --type trade_association
  python3.12 scripts/sync_brussels_lobbies.py --detect --limit 500 --recheck   # refresh stale rows

"Brussels-based" = EU office OR head office in Brussels/Bruxelles. Classification +
news detection live in services/scrapers/brussels_lobby_news.py. No Anthropic API.
"""

from __future__ import annotations

import argparse
import html as _html
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _specialised_helpers import ChunkedDb  # noqa: E402
from services.scrapers.brussels_lobby_news import (  # noqa: E402
    classify, is_global_corp, detect_and_fetch, normalise_category,
)

BRUSSELS_WHERE = (
    "eu_office_city ILIKE '%brux%' OR eu_office_city ILIKE '%brussel%' "
    "OR head_office_city ILIKE '%brux%' OR head_office_city ILIKE '%brussel%'"
)


def _is_brussels(city: str | None) -> bool:
    c = (city or "").lower()
    return "brux" in c or "brussel" in c


# ─────────────────────── body composition ────────────────────────────────

_TYPE_LABEL = {
    "ngo": "Non-governmental organisation", "trade_association": "Trade / business association",
    "company": "Company or group", "think_tank": "Think tank / research institution",
    "consultancy": "Professional consultancy", "law_firm": "Law firm",
    "trade_union": "Trade union / professional association", "academic": "Academic institution",
    "religious": "Religious organisation", "public_authority": "Public / mixed entity",
    "third_country": "Third-country entity", "self_employed": "Self-employed", "other": "Other",
}


def _profile_body(p: dict) -> tuple[str, str]:
    name = p["original_name"] or p["identification_code"]
    pairs = [
        ("Type", _TYPE_LABEL.get(p["org_type"], p["org_type"])),
        ("EUTR section", p["eutr_section"]),
        ("For-profit", {True: "Yes", False: "No"}.get(p["for_profit"])),
        ("Brussels presence", p["office_basis"]),
        ("Head office", ", ".join(x for x in (p["head_office_city"], p["head_office_country"]) if x)),
        ("Website", p["website_url"]),
        ("News status", p["news_status"]),
        ("News source", p["news_source_kind"]),
        ("Latest item", p["last_item_date"]),
        ("News items stored", p["item_count"]),
        ("EP-accredited", p["ep_accredited_number"]),
        ("Lobbyists (FTE)", p["members_fte"]),
        ("Max declared costs (EUR)", p["costs_max"]),
        ("Policy interests", ", ".join(p["interests"]) if p["interests"] else None),
    ]
    lines = [name]
    html = [f"<h2>{_html.escape(name)}</h2>"]
    for k, v in pairs:
        if v in (None, "", []):
            continue
        lines.append(f"{k}: {v}")
        html.append(f"<p><strong>{_html.escape(k)}:</strong> {_html.escape(str(v))}</p>")
    return "\n".join(lines), "<article>" + "".join(html) + "</article>"


# ─────────────────────── seed ────────────────────────────────────────────

SEED_UPSERT = """
INSERT INTO brussels_lobby_profiles (
    identification_code, original_name, acronym, registration_category,
    org_type, eutr_section, for_profit, is_global_corp, office_basis,
    head_office_city, head_office_country, website_url,
    ep_accredited_number, members_fte, costs_max, interests,
    public_url, body_txt, body_html, has_org_data, has_news_data, updated_at
) VALUES (
    %(identification_code)s, %(original_name)s, %(acronym)s, %(registration_category)s,
    %(org_type)s, %(eutr_section)s, %(for_profit)s, %(is_global_corp)s, %(office_basis)s,
    %(head_office_city)s, %(head_office_country)s, %(website_url)s,
    %(ep_accredited_number)s, %(members_fte)s, %(costs_max)s, %(interests)s,
    %(public_url)s, %(body_txt)s, %(body_html)s, true, false, NOW()
)
ON CONFLICT (identification_code) DO UPDATE SET
    original_name = EXCLUDED.original_name,
    acronym = EXCLUDED.acronym,
    registration_category = EXCLUDED.registration_category,
    org_type = EXCLUDED.org_type,
    eutr_section = EXCLUDED.eutr_section,
    for_profit = EXCLUDED.for_profit,
    is_global_corp = EXCLUDED.is_global_corp,
    office_basis = EXCLUDED.office_basis,
    head_office_city = EXCLUDED.head_office_city,
    head_office_country = EXCLUDED.head_office_country,
    website_url = EXCLUDED.website_url,
    ep_accredited_number = EXCLUDED.ep_accredited_number,
    members_fte = EXCLUDED.members_fte,
    costs_max = EXCLUDED.costs_max,
    interests = EXCLUDED.interests,
    public_url = EXCLUDED.public_url,
    body_txt = EXCLUDED.body_txt,
    body_html = EXCLUDED.body_html,
    updated_at = NOW();
"""


def seed(db: ChunkedDb) -> None:
    db.execute(f"""
        SELECT identification_code, original_name, acronym, registration_category,
               eu_office_city, head_office_city, head_office_country, website_url,
               ep_accredited_number, members_fte, costs_max, interests, public_url
          FROM eu_transparency_register
         WHERE {BRUSSELS_WHERE}
    """)
    rows = db.fetchall()
    cols = ["identification_code", "original_name", "acronym", "registration_category",
            "eu_office_city", "head_office_city", "head_office_country", "website_url",
            "ep_accredited_number", "members_fte", "costs_max", "interests", "public_url"]
    n = 0
    for r in rows:
        d = dict(zip(cols, r))
        org_type, section, for_profit = classify(d["registration_category"])
        eu_b, head_b = _is_brussels(d["eu_office_city"]), _is_brussels(d["head_office_city"])
        basis = "both" if eu_b and head_b else ("eu_office" if eu_b else "head_office")
        p = {
            "identification_code": d["identification_code"],
            "original_name": d["original_name"],
            "acronym": d["acronym"],
            "registration_category": normalise_category(d["registration_category"]),
            "org_type": org_type, "eutr_section": section, "for_profit": for_profit,
            "is_global_corp": is_global_corp(org_type, d["head_office_country"]),
            "office_basis": basis,
            "head_office_city": d["head_office_city"], "head_office_country": d["head_office_country"],
            "website_url": d["website_url"],
            "ep_accredited_number": d["ep_accredited_number"],
            "members_fte": d["members_fte"], "costs_max": d["costs_max"],
            "interests": d["interests"] or [],
            "public_url": d["public_url"],
            "news_status": "unknown", "news_source_kind": None, "last_item_date": None, "item_count": 0,
        }
        bt, bh = _profile_body(p)
        p["body_txt"], p["body_html"] = bt, bh
        db.execute(SEED_UPSERT, p)
        n += 1
        if n % 500 == 0:
            db.commit(); print(f"  seeded {n}/{len(rows)}", flush=True)
    db.commit()
    print(f"[DONE] seeded {n} Brussels profiles", flush=True)


# ─────────────────────── detect ──────────────────────────────────────────

ITEM_UPSERT = """
INSERT INTO brussels_lobby_news_items (
    identification_code, guid, item_url, title, summary, published_at,
    source_kind, public_url, body_txt, body_html, fetched_at
) VALUES (
    %(code)s, %(guid)s, %(url)s, %(title)s, %(summary)s, %(published_at)s,
    %(source_kind)s, %(url)s, %(body_txt)s, %(body_html)s, NOW()
)
ON CONFLICT (identification_code, guid) DO UPDATE SET
    item_url = EXCLUDED.item_url, title = EXCLUDED.title, summary = EXCLUDED.summary,
    published_at = EXCLUDED.published_at, source_kind = EXCLUDED.source_kind,
    body_txt = EXCLUDED.body_txt, body_html = EXCLUDED.body_html, fetched_at = NOW();
"""

PROFILE_NEWS_UPDATE = """
UPDATE brussels_lobby_profiles SET
    news_status = %(status)s, news_source_kind = %(kind)s, news_feed_url = %(feed)s,
    last_item_date = %(last)s, item_count = %(count)s,
    has_news_data = %(has)s, last_checked_at = NOW(), updated_at = NOW()
WHERE identification_code = %(code)s;
"""


def _item_body(it) -> tuple[str, str]:
    t = it.title or ""
    s = it.summary or ""
    txt = (t + ("\n\n" + s if s else "")).strip()
    html = "<article>" + (f"<h2>{_html.escape(t)}</h2>" if t else "")
    html += (f"<p>{_html.escape(s)}</p>" if s else "") + "</article>"
    return txt, html


def detect(db: ChunkedDb, limit: int, org_type: str | None, recheck: bool, workers: int) -> None:
    cond = ["website_url IS NOT NULL", "website_url <> ''"]
    if not recheck:
        cond.append("last_checked_at IS NULL")
    if org_type:
        cond.append("org_type = %(org_type)s")
    sql = f"""
        SELECT identification_code, original_name, website_url
          FROM brussels_lobby_profiles p
         WHERE {' AND '.join(cond)}
         ORDER BY costs_max DESC NULLS LAST, last_checked_at NULLS FIRST
         LIMIT %(limit)s
    """
    db.execute(sql, {"limit": limit, "org_type": org_type})
    targets = [(r[0], r[1], r[2]) for r in db.fetchall()]
    print(f"[INFO] detecting news for {len(targets)} orgs (workers={workers})", flush=True)

    done = active = items_total = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(detect_and_fetch, url, 20): (code, name) for code, name, url in targets}
        for fut in as_completed(futs):
            code, name = futs[fut]
            try:
                res = fut.result()
            except Exception as exc:
                res = None
                print(f"  [ERR] {name[:40]}: {exc}", flush=True)
            done += 1
            if res is None:
                db.execute(PROFILE_NEWS_UPDATE, {"code": code, "status": "error", "kind": None,
                           "feed": None, "last": None, "count": 0, "has": False})
                continue
            stored = 0
            for it in res.items:
                bt, bh = _item_body(it)
                try:
                    db.execute(ITEM_UPSERT, {"code": code, "guid": it.guid[:2000], "url": it.url,
                               "title": it.title, "summary": it.summary,
                               "published_at": it.published_at, "source_kind": res.source_kind,
                               "body_txt": bt, "body_html": bh})
                    stored += 1
                except Exception as exc:
                    db.rollback()
                    print(f"  [item-err] {name[:30]}: {exc}", flush=True)
            has_news = res.status == "active"
            db.execute(PROFILE_NEWS_UPDATE, {"code": code, "status": res.status,
                       "kind": res.source_kind, "feed": res.feed_url,
                       "last": res.last_item_date, "count": stored, "has": has_news})
            if has_news:
                active += 1
            items_total += stored
            if done % 25 == 0:
                db.commit()
                print(f"  {done}/{len(targets)} | active={active} items={items_total}", flush=True)
    db.commit()
    print(f"[DONE] checked={done} active={active} items_stored={items_total}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", action="store_true", help="(re)build profiles from the register")
    ap.add_argument("--detect", action="store_true", help="run news detection")
    ap.add_argument("--limit", type=int, default=300)
    ap.add_argument("--type", type=str, default=None, help="filter org_type (detect only)")
    ap.add_argument("--recheck", action="store_true", help="re-check already-checked rows")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()

    db = ChunkedDb()
    try:
        if args.seed:
            seed(db)
        if args.detect:
            detect(db, args.limit, args.type, args.recheck, args.workers)
        if not args.seed and not args.detect:
            ap.error("pass --seed and/or --detect")
    finally:
        db.close()


if __name__ == "__main__":
    main()
