"""DPP watch: has anything moved, anywhere in the EU estate, that LIFE DPP-TEX,
Blue Room Innovation or Terraqui would want to know about today?

Run from /news (after the law-drop radar) to decide whether an URGENT
`/dpp-brief` is warranted, rather than deciding it by reading and hoping.

Three scopes, derived from the three source pages on 24 Aug 2026, not guessed:

  A. DPP-TEX CORE  -- the project's own subject matter: digital product
     passports, ESPR, ecodesign, textiles and fibres, the Waste Framework
     Directive, recycled content, EPR, traceability, LCA. Plus the eight
     consortium partners by name.
  B. BLUE ROOM     -- the coordinator sells far beyond textiles: packaging,
     construction products, batteries and the battery passport, ports and
     MARPOL, plastics, mass balance, waste shipment, public administration
     circularity.
  C. TERRAQUI      -- the regulatory partner's eight practice areas: climate
     and energy transition, biodiversity, water, circular economy and waste,
     sustainable activities, sustainable consumption and products, spatial
     planning, pollution and environmental liability.

Why it sweeps every body rather than the obvious ones: the point is to catch
what the consortium itself would miss. A Horizon project on ecodesign
parameters for home textiles (STEPH, 30 Jun 2026) sits in a Commission feed
nobody at the consortium reads, and it is the exact domain of their Bulgarian
pilot. The Court of Auditors, the EIB, CINEA, the EEA and the EESC all publish
into this space and none of them is on anyone's reading list.

THE ZERO IS NOT A VERDICT ON ITS OWN. Every watchlist body is freshness-checked
first, and a scope with no hits whose bodies are stale reports UNPROVEN, not
NOTHING. Reporting "nothing happened" when the answer is "nothing was ingested"
is the failure this file is written to avoid
(see memory/feedback_zero_denominator_is_not_a_pass).

Usage:
    python3.12 scripts/dpp_watch.py                  # last 7 days
    python3.12 scripts/dpp_watch.py --days 30
    python3.12 scripts/dpp_watch.py --scope A        # one scope only
    python3.12 scripts/dpp_watch.py --json
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from datetime import date, timedelta

logging.disable(logging.WARNING)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import SessionLocal  # noqa: E402
from sqlalchemy import text  # noqa: E402

# --------------------------------------------------------------------------
# Vocabulary. Each scope is (label, regex, urgent_regex).
#
# `urgent` is a NARROWER pattern: a hit on it means the item is a candidate for
# an out-of-cycle brief, not merely relevant. Everything else is ROUTINE. The
# two are kept separate so that widening coverage never widens the alarm.
# --------------------------------------------------------------------------

# The eight consortium partners plus the project and platform names. A mention
# of any of these ANYWHERE in the EU estate is urgent by definition -- it means
# an EU body has named the client's own project or a partner in it.
_PARTNERS = (
    r"LIFE[\s\-]?DPP[\s\-]?TEX|LIFE-2025-SAP-ENV|CircularPass|WasteTrace|CircularPort"
    r"|Blue\s?Room\s+Innovation|Terraqui|Alsico|TexCycle|Eurotex|Kalinel"
    r"|bAwear|Eco\s+Intelligent\s+Growth|T[eè]xtils\.?CAT"
)

SCOPES: dict[str, dict] = {
    "A": {
        "label": "DPP-TEX CORE (project subject matter + consortium partners)",
        "rx": (
            r"digital product passport|\bDPP\b|product passport"
            r"|ecodesign|eco-design|\bESPR\b|Ecodesign for Sustainable Products"
            r"|textile|apparel|garment|clothing|\bfibre|\bfiber"
            r"|waste framework|recycled content|extended producer responsibility"
            r"|separate collection|upcycl|circularity|traceabilit"
            r"|life cycle assessment|\bLCA\b|verifiable credential"
            rf"|{_PARTNERS}"
        ),
        # Urgent: the law or the standard moved, the registry moved, or a
        # partner was named. Not: someone ran a webinar about textiles.
        "urgent_rx": (
            rf"{_PARTNERS}"
            r"|digital product passport registry|DPP registry"
            r"|EN 1821[0-9]|EN 1822[0-9]"
            r"|harmonised standard.{0,40}(product passport|ecodesign)"
            r"|(implementing|delegated) (regulation|decision|act).{0,60}"
            r"(product passport|ecodesign|textile)"
            r"|ESPR working plan|ecodesign working plan"
            r"|textile.{0,30}(delegated act|implementing act|EPR|extended producer)"
            r"|Circular Economy Act"
        ),
    },
    "B": {
        "label": "BLUE ROOM sectors (packaging, construction, batteries, ports, plastics, waste)",
        "rx": (
            r"packaging|\bPPWR\b|construction product|\bCPR\b"
            r"|batter(y|ies)|battery passport"
            r"|\bMARPOL\b|port reception facilit|ship-generated waste"
            r"|plastic|mass balance|chain of custody"
            r"|waste shipment|circular econom|secondary raw material"
        ),
        "urgent_rx": (
            r"(implementing|delegated) (regulation|decision|act).{0,60}"
            r"(packaging|batter|construction product|port reception)"
            r"|battery passport.{0,40}(appl|force|registry|standard)"
            r"|PPWR.{0,40}(appl|suspend|amend|delay)"
            r"|authorised representative.{0,40}(suspend|delay|packaging)"
        ),
    },
    "C": {
        "label": "TERRAQUI practice areas (climate, biodiversity, water, waste, planning, liability)",
        "rx": (
            r"climate law|energy transition|emissions trading|\bETS\b|\bCBAM\b"
            r"|biodiversit|nature restoration|habitats directive|birds directive"
            r"|water framework|urban waste water|drinking water|water resilience"
            r"|circular econom|waste management|landfill"
            r"|sustainable consumption|green claims|empowering consumers"
            r"|environmental liabilit|environmental crime|industrial emission"
            r"|soil monitoring|spatial planning|environmental impact assessment|\bEIA\b"
        ),
        "urgent_rx": (
            r"(regulation|directive).{0,50}(enters into force|starts applying|applies from)"
            r"|environmental liabilit.{0,40}(revis|propos|amend)"
            r"|green claims.{0,40}(withdraw|adopt|agree|trilogue)"
            r"|water resilience strateg"
        ),
    },
}

# Bodies whose freshness decides whether a zero is NOTHING or UNPROVEN. Chosen
# because each one demonstrably publishes into these scopes; the list is not
# "the bodies we like", it is "the bodies whose silence would be misread".
WATCHLIST_BODIES = {
    "cinea": "CINEA (LIFE granting authority -- funds DPP-TEX itself)",
    "eea": "European Environment Agency",
    "echa": "ECHA",
    "eca": "European Court of Auditors",
    "eib": "European Investment Bank",
    "euipo": "EUIPO",
    "commission": "European Commission (economy store)",
}
STALE_AFTER_DAYS = 10
# TRIS publishes most working days; a week without a new notification means the
# feed is broken, not that Member States went quiet (23 Sep 2026: it had been
# frozen for six and a half months and a client found a Spanish textile decree
# before we did).
TRIS_STALE_AFTER_DAYS = 7
# An open standstill ending this soon is a deadline, so the hit is urgent.
TRIS_URGENT_WITHIN_DAYS = 30
# Terraqui's ground: a matching Spanish notification is always urgent while its
# standstill runs (Catalan rules are notified by Spain, as ES).
TRIS_HOME_COUNTRIES = {"ES"}
# How far ahead an open consultation still counts as actionable.
CONSULTATION_HORIZON_DAYS = 30


def _norm(title: str) -> str:
    """Dedup key. The same item lands in both news stores -- the DPP Registry
    launch is held three times -- so titles are compared on letters only."""
    return re.sub(r"[^a-z0-9]+", "", (title or "").lower())[:90]


def body_freshness(db) -> list[dict]:
    """How stale is each watchlist body? Read BEFORE any zero is interpreted.

    Reports three states, not two. `newest is None` means the body holds news
    rows with no date at all (EIB, 233 rows, every one undated as of 24 Aug
    2026) -- those can never surface in a date-ordered watch, which is a
    different failure from being merely behind.
    """
    out = []
    for code, name in WATCHLIST_BODIES.items():
        row = db.execute(text("""
            SELECT count(*) FILTER (WHERE item_type IN ('news','press_release')) AS n,
                   max(document_date) FILTER (WHERE item_type IN ('news','press_release')) AS newest
            FROM economy_items WHERE body_code = :c"""), {"c": code}).mappings().first()
        n = (row or {}).get("n") or 0
        newest = (row or {}).get("newest")
        if n == 0:
            state, age = "NO-NEWS-ROWS", None
        elif newest is None:
            state, age = "UNDATED", None
        else:
            age = (date.today() - newest.date()).days
            state = "OK" if age <= STALE_AFTER_DAYS else "STALE"
        out.append({"body": code, "name": name, "news_rows": int(n),
                    "newest": newest.date().isoformat() if newest else None,
                    "age_days": age, "state": state})

    # TRIS: national draft technical rules notified to the Commission. Checked
    # on its own table, because it was never in economy_items and so this check
    # could not report it missing while it was dead.
    row = db.execute(text(
        "SELECT count(*) AS n, max(notification_date) AS newest FROM tris_notifications"
    )).mappings().first()
    n, newest = int((row or {}).get("n") or 0), (row or {}).get("newest")
    if n == 0:
        state, age = "NO-NEWS-ROWS", None
    else:
        age = (date.today() - newest).days
        state = "OK" if age <= TRIS_STALE_AFTER_DAYS else "STALE"
    out.append({"body": "tris", "name": "TRIS (national draft technical rules, Directive (EU) 2015/1535)",
                "news_rows": n, "newest": newest.isoformat() if newest else None,
                "age_days": age, "state": state})
    return out


def sweep(db, scope_key: str, days: int) -> list[dict]:
    """Every source, one scope, deduplicated.

    Four stores are queried because no one of them is complete: the Commission
    publishes news into `eu_news_items` and research/standards/laws into
    `economy_items`, and the actors that talk about this earliest (the Circular
    Economy Stakeholder Platform, DG GROW, the Environment Commissioner) reach
    us only through `social_posts`.
    """
    scope = SCOPES[scope_key]
    # The scope patterns are written for Python, where \b is a word boundary.
    # In PostgreSQL regular expressions \b is a BACKSPACE (the boundary is \y),
    # so until 23 Sep 2026 every SQL sweep silently failed on \bDPP\b,
    # \bESPR\b, \bLCA\b, \bPPWR\b, \bCPR\b, \bETS\b, \bCBAM\b and \bEIA\b:
    # an item naming only "DPP" or "ESPR" never reached the watch. The Python
    # form stays for the urgent test, which runs in re.
    rx = scope["rx"].replace("\\b", "\\y")
    urgent_rx = scope["urgent_rx"]
    since = date.today() - timedelta(days=days)
    hits: list[dict] = []

    hits += [dict(r) | {"source": "economy_items"} for r in db.execute(text("""
        SELECT body_code AS body, item_type, document_date::date AS d,
               title, public_url AS url, coalesce(summary,'') AS summary
        FROM economy_items
        WHERE document_date >= :since AND document_date <= current_date
          AND item_type <> 'tariff_ruling'
          -- body_code 'dpp' is Brubru's OWN DPP reference corpus (the 13 acts,
          -- the EN 182xx standards, the battery-passport data points), not a
          -- news feed. Left in, it floods every run with our own static
          -- reference rows and fires the urgent pattern on them -- the watch
          -- would report our own library back to us as breaking news.
          AND body_code <> 'dpp'
          AND (title || ' ' || coalesce(summary,'')) ~* :rx
        ORDER BY document_date DESC LIMIT 400"""),
        {"since": since, "rx": rx}).mappings().all()]

    hits += [dict(r) | {"source": "eu_news_items"} for r in db.execute(text("""
        SELECT institution AS body, 'news' AS item_type, news_date::date AS d,
               title, source_url AS url, coalesce(summary,'') AS summary
        FROM eu_news_items
        WHERE news_date >= :since
          AND (title || ' ' || coalesce(summary,'')) ~* :rx
        ORDER BY news_date DESC LIMIT 400"""),
        {"since": since, "rx": rx}).mappings().all()]

    hits += [dict(r) | {"source": "social_posts"} for r in db.execute(text("""
        SELECT a.entity_name AS body, a.entity_type AS item_type,
               p.posted_at::date AS d,
               left(replace(p.content, chr(10), ' '), 200) AS title,
               p.post_url AS url, '' AS summary
        FROM social_posts p JOIN social_accounts a ON a.id = p.account_id
        WHERE p.posted_at >= :since AND p.content ~* :rx
        ORDER BY p.posted_at DESC LIMIT 200"""),
        {"since": since, "rx": rx}).mappings().all()]

    # Open consultations are a SOURCE, not a nice-to-have. The /dpp-brief
    # send-gate names them explicitly ("a consultation opened or closes within
    # 30 days"), so a watch that cannot see them cannot answer the question it
    # exists to answer. Found the hard way on 24 Aug 2026: the first version of
    # this script returned ROUTINE while four feedback periods on recycled
    # content and waste shipments sat open, three closing inside three weeks.
    # An open consultation with a near deadline is urgent by construction --
    # the deadline is the whole point -- so it is marked urgent directly rather
    # than run past `urgent_rx`, which tests wording, not time.
    hits += [dict(r) | {"source": "consultations"} for r in db.execute(text("""
        SELECT coalesce(source_body, 'European Commission') AS body,
               'consultation' AS item_type, end_date::date AS d,
               title, portal_url AS url, coalesce(description,'') AS summary
        FROM public_consultations
        WHERE status = 'open' AND end_date >= current_date
          AND end_date <= current_date + :horizon
          AND (title || ' ' || coalesce(description,'')) ~* :rx
        ORDER BY end_date LIMIT 60"""),
        {"rx": rx, "horizon": CONSULTATION_HORIZON_DAYS}).mappings().all()]

    # JRC Product Bureau (23 Sep 2026). Its rows live in the DPP corpus
    # (body_code 'dpp'), which the economy_items query above excludes as our own
    # library, so they are read here explicitly: a document first seen inside
    # the window is news, and a consultation workshop in the next 30 days is a
    # deadline (registration and the questionnaire hang off it).
    hits += [dict(r) | {"source": "jrc_product_bureau"} for r in db.execute(text("""
        SELECT 'JRC Product Bureau' AS body,
               CASE WHEN item_type = 'event' THEN 'jrc_workshop' ELSE item_type END AS item_type,
               CASE WHEN item_type = 'event' THEN document_date::date ELSE creation_date::date END AS d,
               title, public_url AS url, coalesce(summary,'') AS summary
        FROM economy_items
        WHERE body_code = 'dpp' AND guid LIKE 'jrc-pb-%'
          -- News = PUBLISHED inside the window (its own date), or, for an
          -- undated report, first seen after the source's initial load. The
          -- first ingest on 23 Sep 2026 otherwise made 70 items, some from
          -- 2023, "new today".
          AND (((item_type = 'jrc_study_document') AND document_date >= :since)
               OR (item_type = 'jrc_report' AND creation_date >= :since
                   AND creation_date::date > (SELECT min(creation_date)::date FROM economy_items
                                              WHERE body_code = 'dpp' AND guid LIKE 'jrc-pb-%'))
               -- ::date on both sides: a timestamptz compared with a bare date
               -- shifts by the session time zone and dropped the workshop that
               -- sits exactly on day 30.
               OR (item_type = 'event' AND document_date::date >= current_date
                   AND document_date::date <= current_date + 30
                   AND title !~* 'day not yet fixed'))
          AND (title || ' ' || coalesce(summary,'')) ~* :rx
        ORDER BY 3 DESC LIMIT 60"""),
        {"since": since, "rx": rx}).mappings().all()]

    # TRIS notifications. Actionable for their whole standstill (the window in
    # which the Commission and other Member States can object before the rule
    # may be adopted), so an open standstill counts regardless of `days`, like
    # an open consultation. `d` is the standstill end: the deadline.
    for r in db.execute(text("""
        SELECT notifying_country AS country, notification_number AS ref,
               notification_date AS notified, standstill_until AS standstill,
               title, source_url AS url,
               coalesce(products_or_services,'') || ' ' || coalesce(main_content,'') || ' '
                 || coalesce(full_text_summary,'') AS summary,
               coalesce(member_state_observations, '[]'::jsonb) AS comments_by,
               coalesce(detailed_opinions, '[]'::jsonb) AS opinions
        FROM tris_notifications
        WHERE (standstill_until >= current_date OR notification_date >= :since)
          AND (title || ' ' || coalesce(products_or_services,'') || ' ' || coalesce(main_content,'')
               || ' ' || coalesce(full_text_summary,'')) ~* :rx
        ORDER BY standstill_until NULLS LAST LIMIT 120"""),
        {"since": since, "rx": rx}).mappings().all():
        extra = []
        if r["opinions"]:
            extra.append("detailed opinion: " + ", ".join(r["opinions"]))
        elif r["comments_by"]:
            extra.append("comments: " + ", ".join(r["comments_by"]))
        open_ = r["standstill"] is not None and r["standstill"] >= date.today()
        tail = (f" (standstill to {r['standstill']}" + ("; " + "; ".join(extra) if extra else "") + ")"
                if open_ else " (standstill ended)")
        hits.append({
            "source": "tris", "body": f"TRIS {r['country']}", "item_type": "tris_notification",
            "d": r["standstill"] if open_ else r["notified"],
            "title": f"[{r['ref']}] {r['title']}{tail}", "url": r["url"], "summary": r["summary"],
            "tris_open": open_, "tris_country": r["country"],
        })

    seen, out = set(), []
    for h in hits:
        k = _norm(h["title"])
        if not k or k in seen:
            continue
        seen.add(k)
        blob = f"{h['title']} {h.get('summary','')}"
        h["urgent"] = (h["item_type"] in ("consultation", "jrc_workshop")
                       or bool(re.search(urgent_rx, blob, re.I))
                       or (h["item_type"] == "tris_notification" and h.get("tris_open") and (
                           h.get("tris_country") in TRIS_HOME_COUNTRIES
                           or (h["d"] - date.today()).days <= TRIS_URGENT_WITHIN_DAYS)))
        h.pop("tris_open", None)
        h.pop("tris_country", None)
        h["scope"] = scope_key
        h.pop("summary", None)
        out.append(h)
    out.sort(key=lambda r: (r["urgent"], r["d"] or date.min), reverse=True)
    return out


def verdict(results: dict[str, list[dict]], fresh: list[dict]) -> tuple[str, str]:
    """URGENT / ROUTINE / NOTHING / UNPROVEN, and why in one line."""
    urgent = [h for hs in results.values() for h in hs if h["urgent"]]
    total = sum(len(hs) for hs in results.values())
    bad = [f for f in fresh if f["state"] in ("STALE", "UNDATED", "NO-NEWS-ROWS")]

    if urgent:
        return "URGENT", (f"{len(urgent)} item(s) matched an urgent pattern "
                          f"across {len({h['scope'] for h in urgent})} scope(s).")
    if total:
        return "ROUTINE", (f"{total} relevant item(s), none urgent. "
                           f"Fold into the monthly brief.")
    if bad:
        return "UNPROVEN", (f"No hits, but {len(bad)} of {len(fresh)} watchlist bodies are "
                            f"stale/undated ({', '.join(b['body'] for b in bad)}). "
                            f"A zero here is not evidence of quiet.")
    return "NOTHING", "No hits, and every watchlist body is fresh. Genuinely quiet."


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--scope", choices=sorted(SCOPES), action="append",
                    help="repeatable; default = all three")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--limit", type=int, default=15, help="rows printed per scope")
    args = ap.parse_args()
    keys = args.scope or sorted(SCOPES)

    db = SessionLocal()
    try:
        fresh = body_freshness(db)
        results = {k: sweep(db, k, args.days) for k in keys}
    finally:
        db.close()

    vkey, why = verdict(results, fresh)

    if args.json:
        print(json.dumps({
            "date": date.today().isoformat(), "days": args.days,
            "verdict": vkey, "why": why, "freshness": fresh,
            "hits": {k: [dict(h, d=h["d"].isoformat() if h["d"] else None)
                         for h in v] for k, v in results.items()},
        }, indent=2, default=str))
        return 0

    print(f"DPP WATCH  {date.today()}   (last {args.days}d, scopes {'+'.join(keys)})")
    print("=" * 78)
    print("\nWATCHLIST BODY FRESHNESS  (read this before reading any zero)")
    for f in fresh:
        age = f"{f['age_days']}d old" if f["age_days"] is not None else "--"
        flag = {"OK": "     ", "STALE": "STALE", "UNDATED": "UNDAT",
                "NO-NEWS-ROWS": "NOROW"}[f["state"]]
        print(f"   [{flag}] {f['body']:<11} {f['news_rows']:>5} news rows  "
              f"newest {str(f['newest'] or '(none)'):<12} {age:<9} {f['name']}")

    for k in keys:
        hs = results[k]
        nu = sum(1 for h in hs if h["urgent"])
        print(f"\n{k}. {SCOPES[k]['label']}")
        print(f"   {len(hs)} item(s), {nu} urgent")
        if not hs:
            print("   (none)")
        for h in hs[:args.limit]:
            mark = "URGENT" if h["urgent"] else "      "
            print(f"   [{mark}] {str(h['d']):<11} {str(h['body'])[:22]:<22} "
                  f"{h['source']:<14} {str(h['title'])[:80]}")
        if len(hs) > args.limit:
            print(f"   ... and {len(hs) - args.limit} more (--limit / --json for the rest)")

    print("\n" + "=" * 78)
    print(f"VERDICT: {vkey}")
    print(f"  {why}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
