"""Law-drop radar: does an important EU law bind today, soon, or did one bind
recently without us marking it?

Run from /news Step 0.7. Three checks, deliberately independent, because each
one alone has a blind spot the others cover.

  A. UPCOMING   -- requirement deadlines we already hold, in the window ahead.
  B. UNMARKED   -- deadlines that have PASSED with no deck and no canon page.
  C. UNCOVERED  -- substantive acts published ~20 days ago (so entering force
                   about now) for which we hold NO compliance cluster at all.

Why B and C exist (found 19 Aug 2026):

  B: PPWR's five critical duties became applicable on 12 August. The radar
     printed that deadline, labelled it "(passed)" and moved on. Nobody
     noticed there was no deck and no post, while ELV -- a far narrower
     regime -- got the full treatment the next day. A passed deadline with
     nothing shipped IS a missed law drop; counting down to the next one is
     only half the job.

  C: OLAF announced on 17 August that a law entering into force that day let
     it receive VAT-fraud reports. Check A could never have seen it, because
     A reads `law_requirements`, so it can only find laws we have ALREADY
     built a package for. It answers "which of our packages has a date
     coming up", not "which law drops today". Social media caught what the
     radar structurally could not.

Usage:
    python3.12 scripts/lawdrop_radar.py                # default windows
    python3.12 scripts/lawdrop_radar.py --ahead 30 --back 60
    python3.12 scripts/lawdrop_radar.py --json
"""
from __future__ import annotations

import argparse
import glob
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

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DECK_DIR = os.path.join(ROOT, "docs", "marketing", "designs")
CANON_DIR = os.path.join(ROOT, "frontend", "public", "eucanon")

# CELEX shapes that are never a "law drop" worth a deck. Kept explicit rather
# than clever: a silent over-filter here would recreate the blind spot this
# script exists to close.
_NOISE_CELEX = re.compile(
    r"R\(\d+\)$"          # corrigenda: 32026R0343R(05)
    r"|^52026AS"          # state aid no-objection notices
    r"|^\d{5}XC"          # C-series notices
    r"|^\d{5}M"           # merger decisions
)
_NOISE_TITLE = re.compile(
    r"euro exchange rates"
    r"|amending for the \d+..? time"          # sanctions list churn
    r"|African swine fever"
    r"|ISIL \(Da'esh\) and Al-Qaida"
    r"|authorisation of .* as a feed additive"
    r"|concerning the authorisation of",
    re.I,
)
# A base act of the kind that carries obligations on business.
_SUBSTANTIVE = re.compile(r"^3\d{4}(R|L)\d{4}$")


_GUIDE_DIR = os.path.join(ROOT, "backend", "knowledge_base", "guides")
_ACT_REF = re.compile(r"\((?:EU|EC|EEC|Euratom)\)\s*(?:No\s*)?(\d{1,4}/\d{2,4})")
_covered_refs_cache: set[str] | None = None


def _covered_refs() -> set[str]:
    """Act numbers ("2020/194", "904/2010") that appear in any knowledge guide.

    An amending act whose parent we already explain is the interesting kind:
    its entry into force silently changes an answer Brubru already gives. That
    is exactly what happened on 17 Aug 2026, when an act amending Reg 2020/194
    changed VAT reporting to OLAF and the EPPO while nothing on our side moved.
    """
    global _covered_refs_cache
    if _covered_refs_cache is not None:
        return _covered_refs_cache
    refs: set[str] = set()
    try:
        for fn in os.listdir(_GUIDE_DIR):
            if not fn.endswith(".md"):
                continue
            with open(os.path.join(_GUIDE_DIR, fn), encoding="utf-8", errors="ignore") as fh:
                for m in _ACT_REF.finditer(fh.read()):
                    refs.add(m.group(1))
    except Exception:  # noqa: BLE001
        pass
    _covered_refs_cache = refs
    return refs


def _touches_covered(title: str) -> list[str]:
    """Which guide-covered act numbers this act's title references."""
    if not title:
        return []
    return sorted({m.group(1) for m in _ACT_REF.finditer(title)} & _covered_refs())


def _slug_tokens(*parts: str) -> set[str]:
    """Lowercase word tokens long enough to identify a law in a filename."""
    out: set[str] = set()
    for p in parts:
        for tok in re.split(r"[^a-z0-9]+", (p or "").lower()):
            if len(tok) >= 3 and not tok.isdigit():
                out.add(tok)
    return out


def _marked(celex: str, cluster_name: str) -> dict:
    """Has this law been marked with a deck and/or a canon page?

    Filesystem-based on purpose: those two artefacts ARE the deliverable of
    /lawdrop, so their absence is the thing worth reporting. Matching is
    token-based and therefore fuzzy -- it reports evidence, it does not
    adjudicate. Ambiguity is surfaced, never silently resolved.
    """
    toks = _slug_tokens(cluster_name)
    number = ""
    m = re.match(r"^3(\d{4})([RL])(\d{4})$", celex or "")
    if m:
        number = f"{m.group(3).lstrip('0')}"          # 0040 -> 40
    decks = [os.path.basename(p) for p in glob.glob(os.path.join(DECK_DIR, "*deck*"))]
    canon = [os.path.basename(p) for p in glob.glob(os.path.join(CANON_DIR, "*"))]

    def hits(names: list[str]) -> list[str]:
        out = []
        for n in names:
            nl = n.lower()
            if number and number in nl:
                out.append(n); continue
            if any(t in nl for t in toks if len(t) >= 4):
                out.append(n)
        return sorted(set(out))

    return {"decks": hits(decks), "canon": hits(canon)}


def check_upcoming(db, ahead: int) -> list[dict]:
    rows = db.execute(text("""
        SELECT r.deadline::date AS deadline, c.id AS cluster_id, c.name, l.celex,
               count(*) AS reqs,
               count(*) FILTER (WHERE COALESCE(r.extra_metadata->>'interpretive','')<>'true') AS binding
          FROM law_requirements r
          JOIN law_clusters c ON c.id = r.cluster_id
          LEFT JOIN eu_laws  l ON l.id = r.law_id
         WHERE r.deadline > CURRENT_DATE
           AND r.deadline <= CURRENT_DATE + make_interval(days => :ahead)
         GROUP BY 1,2,3,4 ORDER BY 1
    """), {"ahead": ahead}).mappings().all()
    return [dict(r) for r in rows]


def check_unmarked(db, back: int) -> list[dict]:
    rows = db.execute(text("""
        SELECT r.deadline::date AS deadline, c.id AS cluster_id, c.name, l.celex,
               count(*) AS reqs,
               count(*) FILTER (WHERE COALESCE(r.extra_metadata->>'interpretive','')<>'true') AS binding
          FROM law_requirements r
          JOIN law_clusters c ON c.id = r.cluster_id
          LEFT JOIN eu_laws  l ON l.id = r.law_id
         WHERE r.deadline <= CURRENT_DATE
           AND r.deadline >= CURRENT_DATE - make_interval(days => :back)
         GROUP BY 1,2,3,4 ORDER BY 1 DESC
    """), {"back": back}).mappings().all()
    out = []
    for r in rows:
        d = dict(r)
        d["marked"] = _marked(d.get("celex") or "", d.get("name") or "")
        d["unmarked"] = not (d["marked"]["decks"] or d["marked"]["canon"])
        out.append(d)
    return out


def check_calendar_only(db, ahead: int) -> list[dict]:
    """D. CALENDAR-ONLY -- dated legal milestones Brubru ALREADY HOLDS in
    `eu_calendar_events` that no cluster requirement covers.

    Why this check exists (found 4 September 2026). Check A reads
    `law_requirements`, so it can only see a date somebody has entered into a
    cluster. Brubru holds dated legal milestones in a SECOND store,
    `eu_calendar_events` (`event_type='special_date'`), and the radar never read
    it. On 4 September check A reported exactly one upcoming deadline, the Cyber
    Resilience Act, while the calendar held three more inside ten days:

        06 Sep  Rail interoperability standards: partial application
        12 Sep  Data Act: partial application
        14 Sep  Vehicle circularity: delegated-act empowerments start applying
                (Regulation (EU) 2026/1738 -- the acts that will define
                 recyclability, recycled content, THE PASSPORT and fee modulation)

    The ELV one was surfaced by a hand sweep of /api/v2/events/all, not by the
    radar. A radar that reads one of the two stores holding the answer will keep
    reporting a quiet window while the product knows otherwise.

    A milestone is reported here when NO `law_requirements` row shares its date.
    Same-date is deliberately coarse: the point is to raise a candidate for a
    human, not to assert that the cluster is wrong.
    """
    rows = db.execute(text("""
        SELECT e.start_date::date AS milestone, e.title, e.source,
               e.description, e.institution::text AS institution
          FROM eu_calendar_events e
         WHERE e.event_type = 'special_date'
           AND e.start_date > CURRENT_DATE
           AND e.start_date <= CURRENT_DATE + make_interval(days => :ahead)
           AND NOT EXISTS (
                 SELECT 1 FROM law_requirements r
                  WHERE r.deadline = e.start_date::date)
         ORDER BY e.start_date
    """), {"ahead": ahead}).mappings().all()
    return [dict(r) for r in rows]

def check_uncovered(db, lo: int, hi: int) -> list[dict]:
    """Substantive acts published lo..hi days ago (so entering force about now,
    on the standard twentieth-day clause) that we hold no cluster for.

    Reads the OJ from CELLAR, not from `eu_laws`. The first version of this
    check read `eu_laws` and returned "none" on 19 Aug 2026 -- while the very
    act that motivated it, Commission Implementing Regulation (EU) 2026/1869
    of 27 July (VAT administrative cooperation, the OLAF/EPPO reporting
    change), was absent from `eu_laws` entirely. A check that can only see
    acts we already ingested cannot find the acts we missed. That is the same
    failure it exists to catch, one layer down.

    Deliberately does NOT read `law_requirements`: that is the other blind
    spot. Deferred application dates are NOT derivable from the publication
    date, so this is a candidate list for a human to read, never a verdict.
    Read the act's own final article before acting on any row.
    """
    import asyncio
    from services.api_clients.cellar_sparql_client import CellarSPARQLClient

    lo_d = date.today() - timedelta(days=hi)
    hi_d = date.today() - timedelta(days=lo)

    async def _fetch():
        async with CellarSPARQLClient() as client:
            return await client.discover_by_date_range(
                lo_d, hi_d, sectors=["3"], limit=500)

    try:
        acts = asyncio.run(_fetch())
    except Exception as exc:  # noqa: BLE001
        # Loud, not silent: an unreachable Cellar must not read as "no drops".
        return [{"celex": "", "title": f"CELLAR UNREACHABLE ({type(exc).__name__}) "
                                       f"-- check C did NOT run", "date": None,
                 "error": True}]

    covered = {c for (c,) in db.execute(text(
        "SELECT DISTINCT l.celex FROM law_requirements r "
        "JOIN eu_laws l ON l.id = r.law_id WHERE l.celex IS NOT NULL")).all()}

    out = []
    for a in acts:
        celex = (a.get("celex") or "")
        title = (a.get("title") or "")
        d = a.get("date")
        if isinstance(d, str):
            try:
                d = date.fromisoformat(d[:10])
            except ValueError:
                d = None
        if not d or not (lo_d <= d <= hi_d):
            continue
        if celex in covered:
            continue
        if _NOISE_CELEX.search(celex) or _NOISE_TITLE.search(title):
            continue
        if not _SUBSTANTIVE.match(celex):
            continue
        out.append({"celex": celex, "title": (title or "(title not yet in Cellar)")[:150],
                    "date": d, "touches": _touches_covered(title)})
    # Rank rather than filter. A month of OJ legislation is ~70 substantive
    # acts; that is the real volume, not noise to be suppressed. Suppressing it
    # would rebuild the blind spot. Instead, surface FIRST the acts that amend
    # an instrument we already write about, because those are the ones whose
    # drop changes an answer Brubru already gives.
    out.sort(key=lambda r: (bool(r["touches"]), r["date"]), reverse=True)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ahead", type=int, default=30)
    ap.add_argument("--back", type=int, default=60)
    ap.add_argument("--force-lo", type=int, default=15)
    ap.add_argument("--force-hi", type=int, default=35)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    db = SessionLocal()
    try:
        up = check_upcoming(db, a.ahead)
        un = check_unmarked(db, a.back)
        unc = check_uncovered(db, a.force_lo, a.force_hi)
        cal = check_calendar_only(db, a.ahead)
    finally:
        db.close()

    if a.json:
        print(json.dumps({"upcoming": up, "unmarked": un, "uncovered": unc,
                          "calendar_only": cal},
                         default=str, indent=2))
        return 0

    today = date.today()
    print(f"LAW-DROP RADAR  {today}   (ahead {a.ahead}d / back {a.back}d)")
    print("=" * 78)

    print(f"\nA. UPCOMING -- deadlines we hold, next {a.ahead} days")
    if not up:
        print("   none.")
    for r in up:
        days = (r["deadline"] - today).days
        print(f"   {r['deadline']}  (+{days:>3}d)  cluster {r['cluster_id']:<3} "
              f"{(r['name'] or '')[:44]:44s} {r['celex'] or '':12s} "
              f"{r['binding']}/{r['reqs']} binding")

    print(f"\nB. UNMARKED -- deadlines PASSED in the last {a.back} days with no deck and no canon page")
    flagged = [r for r in un if r["unmarked"]]
    if not flagged:
        print("   none. Every passed deadline has a deck or a canon page.")
    for r in flagged:
        days = (today - r["deadline"]).days
        print(f"   {r['deadline']}  ({days:>3}d ago) cluster {r['cluster_id']:<3} "
              f"{(r['name'] or '')[:44]:44s} {r['celex'] or '':12s} "
              f"{r['binding']}/{r['reqs']} binding   <-- NOTHING SHIPPED")
    for r in [x for x in un if not x["unmarked"]]:
        ev = (r["marked"]["decks"] + r["marked"]["canon"])[:2]
        print(f"   {r['deadline']}  marked: {', '.join(ev)}")

    print(f"\nC. UNCOVERED -- substantive acts published {a.force_lo}-{a.force_hi}d ago with NO cluster")
    print("   (twentieth-day clause puts these in force about now; deferred")
    print("    application dates are NOT derivable -- read the final article)")
    if not unc:
        print("   none.")
    touching = [r for r in unc if r.get("touches")]
    if touching:
        print(f"   -- {len(touching)} amend an act a guide already covers (read these first) --")
        for r in touching:
            print(f"   {r['date']}  {r['celex']:14s} [amends {', '.join(r['touches'])}] {r['title'][:70]}")
        print("   -- the rest --")
    rest = [r for r in unc if not r.get("touches")]
    for r in rest[:15]:
        print(f"   {r['date']}  {r['celex']:14s} {r['title'][:96]}")
    if len(rest) > 15:
        print(f"   ... and {len(rest)-15} more (use --json for the full list)")

    print(f"\nD. CALENDAR-ONLY -- dated milestones we HOLD in the calendar that no cluster covers")
    print("   (check A reads law_requirements only; these live in eu_calendar_events)")
    if not cal:
        print("   none. Every calendar milestone in the window has a matching requirement.")
    for r in cal:
        days = (r["milestone"] - today).days
        print(f"   {r['milestone']}  (+{days:>3}d)  [{(r['source'] or '')[:22]:22s}] {(r['title'] or '')[:62]}")

    print("\nVERDICT")
    if flagged:
        print(f"  {len(flagged)} MISSED law drop(s) -- a passed deadline with nothing shipped.")
    if up:
        print(f"  {len(up)} upcoming deadline(s) inside {a.ahead} days.")
    if unc:
        print(f"  {len(unc)} uncovered act(s) to triage by hand.")
    if cal:
        print(f"  {len(cal)} dated milestone(s) in the calendar with NO cluster requirement "
              f"-- check A cannot see these.")
    if not (flagged or up or unc or cal):
        print("  No law drop in the window.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
