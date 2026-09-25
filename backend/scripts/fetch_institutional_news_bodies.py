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
import os
import re
import sys
import pathlib
import urllib.parse
import threading
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


_PRESSCORNER = re.compile(r"^https?://ec\.europa\.eu/commission/presscorner/detail/en/([\w-]+)")


def presscorner_pdf(url: str) -> str | None:
    """The print PDF for a presscorner page, or None if this is not one.

    The page itself is a JavaScript shell: 200, ~22 KB, and zero characters of text, and
    Scrape.do returns the same with render=true, so rendering is not the answer. The
    Commission does serve the document, as a PDF, at a mechanical URL:

        /detail/en/speech_26_911  ->  /api/files/document/print/en/speech_26_911/SPEECH_26_911_EN.pdf

    Checked against speech_, ip_ and statement_ documents: 922 to 5,423 characters each.
    (An older note in memory says this endpoint 404s; it answers 200 today.)
    """
    m = _PRESSCORNER.match(url or "")
    if not m:
        return None
    slug = m.group(1)
    return (f"https://ec.europa.eu/commission/presscorner/api/files/document/print/en/"
            f"{slug}/{slug.upper()}_EN.pdf")


# A 429 is a statement about our request RATE, not about the document. Recording one as a
# failure leaves the row permanently empty and reads later as "this body has no text" --
# the euda slice failed 240 of 400 rows this way. So: every thread shares one backoff
# clock, and a rate limit pauses the whole run rather than burning through the queue.
_RATE_LOCK = threading.Lock()
_BACKOFF_UNTIL = 0.0
_RETRY_STATUS = (429, 503)


def _respect_backoff() -> None:
    while True:
        with _RATE_LOCK:
            wait = _BACKOFF_UNTIL - time.time()
        if wait <= 0:
            return
        time.sleep(min(wait, 5.0))


def _note_rate_limit(exc: urllib.error.HTTPError, attempt: int) -> float:
    """Pause every thread. Honour Retry-After when the server sends one."""
    delay = 0.0
    header = exc.headers.get("Retry-After") if exc.headers else None
    if header:
        try:
            delay = float(header.strip())
        except ValueError:
            delay = 0.0
    if delay <= 0:
        delay = min(60.0, 5.0 * (3 ** attempt))
    with _RATE_LOCK:
        global _BACKOFF_UNTIL
        _BACKOFF_UNTIL = max(_BACKOFF_UNTIL, time.time() + delay)
    return delay


def _read(url: str, timeout: int, accept: str = "*/*") -> bytes:
    """Fetch, retrying a rate limit up to 3 times. Other HTTP errors raise at once."""
    last: Exception | None = None
    for attempt in range(3):
        _respect_backoff()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as exc:
            if exc.code not in _RETRY_STATUS:
                raise
            last = exc
            _note_rate_limit(exc, attempt)
    raise last  # type: ignore[misc]


from services.news.rendered_article import (extract_article, looks_like_chrome,
                                            looks_like_listing)


# What counts as a whole body, matching scripts/api_body_coverage.py.
WHOLE_BODY_CHARS = 1200


def _scrapedo_token() -> str | None:
    """SCRAPEDO_API_KEY lives in the REPO-ROOT .env, not backend/.env.

    Scripts run from backend/ load backend/.env and see it unset, which is why it has read
    as "missing" before. Derive the root from this file, never a hardcoded path.
    """
    token = os.environ.get("SCRAPEDO_API_KEY")
    if token:
        return token
    root_env = Path(__file__).resolve().parents[2] / ".env"
    if root_env.is_file():
        for line in root_env.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("SCRAPEDO_API_KEY="):
                return line.split("=", 1)[1].strip() or None
    return None


def _best_extraction(page_html: str) -> tuple[str | None, str | None, str | None]:
    """Whichever extractor reads this template better, not whichever was written last.

    extract_article knows the Europa component library and refuses consent banners and
    listing pages. extract_html is the economy-store extractor and reads templates the
    other one has no selector for: on an FRA case-law page it finds the whole 2,703-character
    record where extract_article finds 287. Run both, keep the longer body that passes the
    furniture checks, so neither template family loses.
    """
    text_a, html_a, reason_a = extract_article(page_html)

    text_b, html_b = extract_html(page_html)
    if text_b and (error_body_reason(text_b) or looks_like_chrome(text_b)
                   or looks_like_listing(text_b)):
        text_b, html_b = None, None

    if text_a and text_b:
        return (text_a, html_a, None) if len(text_a) >= len(text_b) else (text_b, html_b, None)
    if text_a:
        return text_a, html_a, None
    if text_b:
        return text_b, html_b, None
    return None, None, reason_a


def fetch_via_scrapedo(url: str, timeout: int = 150, render: bool = True
                       ) -> tuple[str | None, str | None, str | None]:
    """A page Brubru cannot fetch directly, via Scrape.do.

    Two distinct jobs. `render=False` is one credit and defeats an IP-reputation block or a
    rate limit, which is what a 403 or a persistent 429 from an agency site means. `render=True`
    additionally runs the page

    customWait is not optional: without it the service returns the Angular shell with a 200,
    which is a failure carried in the body. 5s was enough on every page tested; 10s added
    nothing.
    """
    token = _scrapedo_token()
    if not token:
        return None, None, "no SCRAPEDO_API_KEY"
    api = ("https://api.scrape.do/?token=" + token
           + "&url=" + urllib.parse.quote(url, safe=""))
    if render:
        api += "&render=true&customWait=5000"
    # The render can come back unrendered: the same URL returned the Angular shell once and
    # the full 101 KB page on the next two calls, all with HTTP 200. A transient must be
    # retried, not filed as "this page has no text".
    last: tuple[str | None, str | None, str | None] = (None, None, "scrapedo not attempted")
    for attempt in range(3):
        try:
            raw = _read(api, timeout, accept="text/html,*/*")
        except urllib.error.HTTPError as exc:
            return None, None, f"scrapedo HTTP {exc.code}"
        except Exception as exc:  # noqa: BLE001
            return None, None, f"scrapedo {type(exc).__name__}"
        last = _best_extraction(raw.decode("utf-8", "replace"))
        if last[0] or not render or "did not render" not in (last[2] or ""):
            return last
        time.sleep(2 * (attempt + 1))
    return last


def fetch(url: str, timeout: int = 40, render: bool = False) -> tuple[str | None, str | None, str | None]:
    """(body_txt, body_html, error). Never raises: a failure leaves the row alone."""
    pdf_url = presscorner_pdf(url)
    if pdf_url:
        try:
            raw = _read(pdf_url, timeout)
            import io

            from pypdf import PdfReader

            txt = "\n".join((pg.extract_text() or "")
                             for pg in PdfReader(io.BytesIO(raw)).pages).strip()
            # No body_html: this is a PDF, and inventing HTML from one is what produced
            # the composed stubs in the first place.
            return (txt or None), None, None if txt else "presscorner pdf had no text"
        except urllib.error.HTTPError as exc:
            return None, None, f"presscorner HTTP {exc.code}"
        except Exception as exc:  # noqa: BLE001
            return None, None, f"presscorner {type(exc).__name__}"

    try:
        html = _read(url, timeout, accept="text/html,*/*").decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        # A wall is not an absence of text. 403 means our address is blocked and a 429 that
        # survived three backoffs means the same in practice; Scrape.do fetches from
        # elsewhere for one credit. Without this the row is filed as having no body.
        if render and exc.code in (403, 429, 503):
            text_, html_, reason = fetch_via_scrapedo(url, render=False)
            if text_:
                return text_, html_, None
            if reason and "did not render" in reason:
                return fetch_via_scrapedo(url, render=True)
            return None, None, f"HTTP {exc.code}; scrapedo: {reason}"
        return None, None, f"HTTP {exc.code}"
    except Exception as exc:  # noqa: BLE001
        return None, None, f"{type(exc).__name__}"
    body_txt, body_html = extract_html(html)
    reason = error_body_reason(body_txt)
    if reason or not body_txt:
        if render:
            # The page carried no prose of its own. On Europa that usually means an Angular
            # shell, so ask for it rendered rather than recording "no text available".
            return fetch_via_scrapedo(url, render=True)
        return None, None, f"rejected:{reason or 'no text in the page'}"
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
    ap.add_argument("--render", action="store_true",
                    help="Fall back to a rendered fetch (Scrape.do) when a page carries no prose. "
                         "Costs credits, so it is opt-in.")
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
                # The same resume filter the eu_news_items branch has had all along, which
                # this one never got: without it the job re-downloads rows that ALREADY hold
                # a whole body. It is why a euda slice spent 400 requests to earn 240 rate
                # limits, and why a sample of fra/case_law came back holding 16,215
                # characters on every row. Thin rows are the work; full rows are done.
                "  AND coalesce(length(body_txt), 0) < :whole "
                "ORDER BY document_date DESC NULLS LAST, id LIMIT :n"),
                {"code": args.body_code, "types": types, "n": args.limit,
                 "whole": WHOLE_BODY_CHARS}).fetchall()
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
                fetched = list(ex.map(lambda row: (row, *fetch(row.source_url, render=args.render)), chunk))
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
                # NUL and lone surrogates: PostgreSQL rejects the first outright and the
                # second cannot be encoded to UTF-8 at all. Both have killed a run.
                def _clean(v):
                    if not v:
                        return None
                    v = v.replace("\x00", "").encode("utf-8", "ignore").decode("utf-8", "ignore")
                    return v or None

                body_txt = _clean(body_txt)
                body_html = _clean(body_html)
                if not body_txt:
                    failed += 1
                    reasons["nothing left after cleaning"] = reasons.get("nothing left after cleaning", 0) + 1
                    continue

                # Never shorten a body. A dry run on cedefop/news offered 309 characters for
                # rows already holding 2,796, and euda/publication 5,282 for rows holding
                # 10,600: the listing page is sometimes richer than the article page behind
                # it. Overwriting on "we fetched something" would have degraded 55 slices.
                if len(body_txt) <= (getattr(r, "blen", 0) or 0):
                    failed += 1
                    why = "fetched body is shorter than the stored one"
                    reasons[why] = reasons.get(why, 0) + 1
                    continue
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
