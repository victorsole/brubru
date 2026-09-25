"""Fetch the ACTUAL article for institutional news, instead of composing one.

GovClipping need the whole text in `body_txt` and the whole HTML in `body_html`,
especially on news and publications (Victor, 25 September 2026).

Today every one of the 11,387 `eu_news_items` rows carries a body composed at backfill
time from the title and the RSS summary: `body_source` is `composed:title+summary` (7,995)
or `composed:title` (3,392), averaging 379 characters. That was a deliberate decision on
8 September, taken so the five-datapoint contract would have no nulls, and
`backfill_eu_news_bodies.py` says plainly that it "does NOT fetch the article". It met the
letter of the contract and defeated its purpose, and it made the gap harder to see: a
plausible 379-character body reads as populated where a null would have shouted.

This fetches the page and stores what is actually there. Scope is EU INSTITUTIONAL sources
only. The other 4,320 rows come from Politico, Euractiv and EUobserver, whose article text
is theirs and is not ours to store or serve; those keep title, summary and the link.

Guards, reusing the economy scraper's own helpers so this behaves like the rest of the
corpus: `extract_html()` strips nav/header/footer/script and keeps <main>/<article>, and
`error_body_reason()` refuses to store a cookie wall, a 404 page or anything too short to
be an article. A row that cannot be fetched keeps the body it has.

Usage (from backend/):
    python3.12 scripts/fetch_institutional_news_bodies.py --institution EEA
    python3.12 scripts/fetch_institutional_news_bodies.py --institution EEA --apply
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from sqlalchemy import text  # noqa: E402

from core.database import SessionLocal  # noqa: E402
from services.scrapers.economy_common import error_body_reason, extract_html  # noqa: E402

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
# Anything on these hosts is an EU institution or agency: a public document.
INSTITUTIONAL = ("europa.eu", "europarl.europa.eu", "consilium.europa.eu", "ecb.int")


def is_institutional(url: str) -> bool:
    return any(h in (url or "") for h in INSTITUTIONAL)


def fetch(url: str, timeout: int = 40) -> tuple[str | None, str | None, str | None]:
    """(body_txt, body_html, error). Never raises: a failure leaves the row alone."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            html = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return None, None, f"HTTP {exc.code}"
    except Exception as exc:  # noqa: BLE001
        return None, None, f"{type(exc).__name__}"
    body_txt, body_html = extract_html(html)
    reason = error_body_reason(body_txt)
    if reason:
        return None, None, f"rejected:{reason}"
    return body_txt, body_html, None



def _commit(db):
    """Commit, reopening the session if the server has dropped it.

    These runs hold one Session across hours of network work, and Supabase closes an idle
    connection from its side. `pool_pre_ping` cannot help: it validates on CHECKOUT, and
    the connection is checked out for the whole run. The EESC backfill died at 652 rows
    with "server closed the connection unexpectedly" after fetching them all.

    Returns the session to keep using, which may be a new one.
    """
    from sqlalchemy.exc import OperationalError
    try:
        db.commit()
        return db
    except OperationalError as exc:
        print(f"  [db] {type(exc).__name__}: reopening the session", flush=True)
        try:
            db.rollback()
            db.close()
        except Exception:  # noqa: BLE001
            pass
        return SessionLocal()

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--institution", help="eu_news_items.institution, e.g. EEA")
    ap.add_argument("--body-code", help="economy_items.body_code, e.g. eea. This is the "
                                        "table /api/v2/news/all actually serves when an "
                                        "article exists in both.")
    ap.add_argument("--item-type", action="append",
                    help="economy_items.item_type; repeatable. Default: news.")
    ap.add_argument("--limit", type=int, default=500)
    ap.add_argument("--throttle", type=float, default=1.0)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        if args.body_code:
            types = args.item_type or ["news"]
            rows = db.execute(text(
                "SELECT id, public_url AS source_url, coalesce(length(body_txt),0) AS blen, "
                "       '' AS src, left(coalesce(title,''),70) AS title "
                "FROM economy_items WHERE body_code = :code AND item_type = ANY(:types) "
                "  AND public_url IS NOT NULL "
                "ORDER BY document_date DESC NULLS LAST, id LIMIT :n"),
                {"code": args.body_code, "types": types, "n": args.limit}).fetchall()
            label = f"{args.body_code}/{','.join(types)}"
        else:
            rows = db.execute(text(
                "SELECT id, source_url, coalesce(length(body_txt),0) AS blen, "
                "       coalesce(body_source,'') AS src, left(coalesce(title,''),70) AS title "
                # Skip what is already fetched. Without this the job re-downloads every
                # article on every run: a restart began COMMISSION again from the top,
                # 1,051 rows already done, and 47 institutions would have paid that twice.
                "FROM eu_news_items WHERE institution = :inst "
                "  AND coalesce(body_source, '') <> 'fetched:article' "
                "ORDER BY news_date DESC NULLS LAST, id LIMIT :n"),
                {"inst": args.institution, "n": args.limit}).fetchall()
            label = args.institution
        targets = [r for r in rows if is_institutional(r.source_url)]
        skipped = len(rows) - len(targets)
        print(f"[INFO] {len(rows)} {label} row(s); {len(targets)} on institutional "
              f"hosts, {skipped} skipped as third-party")
        if not targets:
            return 0

        before = sum(r.blen for r in targets) / len(targets)
        print(f"[INFO] average body now: {before:,.0f} characters")

        ok = failed = 0
        gained = []
        reasons: dict[str, int] = {}
        # Fetched in parallel and committed per batch: 7,050 institutional news rows one at
        # a time is hours, and a single commit at the end means a run that dies writes
        # nothing.
        BATCH = 40
        i = 0
        for start in range(0, len(targets), BATCH):
            chunk = targets[start:start + BATCH]
            with cf.ThreadPoolExecutor(max_workers=6) as ex:
                fetched = list(ex.map(lambda row: (row, *fetch(row.source_url)), chunk))
            for r, body_txt, body_html, err in fetched:
                i += 1
                # extract_html() returns (None, None) for a page with no <main>/<article>
                # text, and error_body_reason(None) is None because "absent" is not
                # "invalid". So a clean fetch can still carry no body, and len(None) then
                # killed the whole run.
                if err or not body_txt:
                    failed += 1
                    why = err or "no text in page"
                    # Tallied, not just the first ten printed: with 159 failures in a
                    # batch the first ten say nothing about the shape of the problem.
                    reasons[why] = reasons.get(why, 0) + 1
                    if failed <= 5:
                        print(f"  [{i:5}] {why:22} {r.title[:50]}", flush=True)
                    continue
                body_txt = body_txt.replace("\x00", "")
                body_html = (body_html or "").replace("\x00", "") or None
                ok += 1
                gained.append(len(body_txt))
                if args.apply:
                    if args.body_code:
                        db.execute(text(
                            # fetched_at: economy_items has no updated_at either. Both
                            # tables were guessed and both failed the whole batch; the
                            # column list is one query away and worth the query.
                            "UPDATE economy_items SET body_txt = :t, body_html = :h, "
                            "  fetched_at = now() WHERE id = :id"),
                            {"t": body_txt, "h": body_html, "id": r.id})
                    else:
                        db.execute(text(
                            "UPDATE eu_news_items SET body_txt = :t, body_html = :h, "
                            # fetched_at, not last_updated: eu_news_items has no such
                            # column and the whole batch failed on it the first time.
                            "  body_source = 'fetched:article', fetched_at = now() "
                            "WHERE id = :id"),
                            {"t": body_txt, "h": body_html, "id": r.id})
            if args.apply:
                db = _commit(db)
            avg_so_far = sum(gained) / len(gained) if gained else 0
            top = ", ".join(f"{k} x{v}" for k, v in
                            sorted(reasons.items(), key=lambda kv: -kv[1])[:3])
            print(f"  [{min(start + BATCH, len(targets)):5}/{len(targets)}] ok {ok}, "
                  f"failed {failed}, avg {avg_so_far:,.0f} chars"
                  + (f"  |  {top}" if top else ""), flush=True)
            time.sleep(args.throttle)

        if args.apply:
            db = _commit(db)
        avg = sum(gained) / len(gained) if gained else 0
        print(f"\n[{'APPLIED' if args.apply else 'DRY-RUN'}] fetched {ok}, failed {failed}; "
              f"average body {avg:,.0f} characters (was {before:,.0f})")

        if args.apply:
            if args.body_code:
                n, avg_now, full = db.execute(text(
                    "SELECT count(*), coalesce(round(avg(nullif(length(body_txt),0))),0), "
                    "       count(*) FILTER (WHERE length(body_txt) >= 1200) "
                    "FROM economy_items WHERE body_code = :code AND item_type = ANY(:types)"),
                    {"code": args.body_code, "types": args.item_type or ["news"]}).fetchone()
            else:
                n, avg_now, full = db.execute(text(
                    "SELECT count(*), coalesce(round(avg(nullif(length(body_txt),0))),0), "
                    "       count(*) FILTER (WHERE length(body_txt) >= 1200) "
                    "FROM eu_news_items WHERE institution = :inst"),
                    {"inst": args.institution}).fetchone()
            print(f"[VERIFY] {label}: {n} row(s), average {int(avg_now):,} chars, "
                  f"{full} of document length")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
