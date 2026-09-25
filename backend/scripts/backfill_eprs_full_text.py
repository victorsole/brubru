"""Fill `eprs_publications.full_text` from the publication's own page.

920 European Parliamentary Research Service studies held an average of **53 characters** of
text: the table has carried titles and summaries and almost no documents since it was created.
It is not only an API gap, because the MCP `search_eprs` tool reads this table too, so the
hole reaches the chat as well.

The fetching itself is `fetch_institutional_news_bodies.fetch()`, which by now refuses a bot
challenge, refuses page furniture, refuses a listing, parses a PDF instead of storing its
bytes, routes a wall through Scrape.do and retries a rate limit. None of that is worth writing
twice.

    python3.12 scripts/backfill_eprs_full_text.py --limit 20            # dry run
    python3.12 scripts/backfill_eprs_full_text.py --limit 2000 --apply
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import pathlib
import sys
import time

_BACKEND = pathlib.Path(__file__).resolve().parents[1]
for _p in (str(_BACKEND), str(_BACKEND / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import re  # noqa: E402

from sqlalchemy import text  # noqa: E402

from core.database import SessionLocal  # noqa: E402
from fetch_institutional_news_bodies import (  # noqa: E402
    _commit, _read, fetch, is_institutional)

WHOLE = 1200

# The blog post is a SUMMARY of the study, not the study. Measured on EPRS_BRI(2026)782664:
# the epthinktank post gives 1,115 characters, the Think Tank record page 1,388, and the PDF
# behind them 29,491. Storing the first would be the same mistake this whole backfill exists
# to correct, one level further up: a summary is not a body.
_THINKTANK_LINK = re.compile(
    r'href="(https?://www\.europarl\.europa\.eu/thinktank/[^"]*/document/[^"]+)"', re.I)
_REGDATA_PDF = re.compile(r'href="([^"]*RegData/etudes/[^"]+\.pdf[^"]*)"', re.I)


def _pick_english(html: str) -> str | None:
    """The EN PDF, not simply the first one.

    A Think Tank record lists every language it was published in, and taking the first match
    stored a Spanish study ("ES ESTUDIO ... Servicio de Estudios del Parlamento Europeo") for
    an English-language row. Same trap as the Cellar expressions, where 0001/0002/0003 are
    EN/FR/DE and the first one is not the one you want.
    """
    links = _REGDATA_PDF.findall(html)
    if not links:
        return None
    for link in links:
        if link.upper().endswith("_EN.PDF"):
            return link
    # No English version. Take what there is: some EPRS studies are published only in one
    # language, and the row IS that publication -- a comparative-law study titled "La libertad
    # de pensamiento, de conciencia y de religion" is not served by refusing its Spanish PDF.
    # Preferring EN was right; refusing everything else was over-correcting.
    return links[0]


def _follow_to_the_document(page_url: str, timeout: int = 40) -> str | None:
    """The PDF the page points at: blog post -> Think Tank record -> RegData PDF."""
    try:
        html = _read(page_url, timeout, accept="text/html,*/*").decode("utf-8", "replace")
    except Exception:  # noqa: BLE001
        return None

    pdf = _pick_english(html)
    if pdf:
        return pdf

    record = _THINKTANK_LINK.search(html)
    if not record:
        return None
    try:
        record_html = _read(record.group(1), timeout, accept="text/html,*/*").decode("utf-8", "replace")
    except Exception:  # noqa: BLE001
        return None
    return _pick_english(record_html)


def best_body(row, render: bool) -> tuple[str | None, str | None]:
    """(text, reason). The document when we can reach it, the page when we cannot."""
    page_url = row.html_url or row.pdf_url
    if row.pdf_url:
        body, _html, reason = fetch(row.pdf_url, render=render)
        if body:
            return body, None

    document_url = _follow_to_the_document(page_url)
    if document_url:
        body, _html, reason = fetch(document_url, render=render)
        if body:
            return body, None

    # No document reachable: the page itself is still far better than 53 characters.
    body, _html, reason = fetch(page_url, render=render)
    return body, (None if body else reason)


def clean(value: str | None) -> str | None:
    """NUL and lone surrogates. Postgres rejects the first; the second cannot be encoded."""
    if not value:
        return None
    value = value.replace("\x00", "").encode("utf-8", "ignore").decode("utf-8", "ignore")
    return value or None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--render", action="store_true",
                    help="Route a wall through Scrape.do. Costs credits, so it is opt-in.")
    ap.add_argument("--throttle", type=float, default=0.5)
    ap.add_argument("--workers", type=int, default=5)
    args = ap.parse_args()

    db = SessionLocal()
    rows = db.execute(text(
        "SELECT id, html_url, pdf_url, coalesce(length(full_text), 0) AS have, "
        "       left(coalesce(title, ''), 60) AS title "
        "FROM eprs_publications "
        # Resume: only rows still short of a whole document, and only rows with somewhere to go.
        "WHERE coalesce(length(full_text), 0) < :whole "
        "  AND (html_url IS NOT NULL OR pdf_url IS NOT NULL) "
        "ORDER BY publication_date DESC NULLS LAST, id "
        "LIMIT :n"), {"whole": WHOLE, "n": args.limit}).fetchall()

    targets = [r for r in rows if is_institutional(r.html_url or r.pdf_url or "")]
    skipped = len(rows) - len(targets)
    print(f"[INFO] {len(rows)} row(s) below {WHOLE} chars; {len(targets)} on institutional "
          f"hosts, {skipped} skipped as third-party", flush=True)

    applied = failed = 0
    reasons: dict[str, int] = {}
    gained: list[int] = []

    for start in range(0, len(targets), 20):
        chunk = targets[start:start + 20]
        with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
            done = list(ex.map(lambda r: (r, *best_body(r, args.render)), chunk))

        for row, body_txt, err in done:
            body_txt = clean(body_txt)
            if err or not body_txt:
                failed += 1
                why = err or "no text in the page"
                reasons[why] = reasons.get(why, 0) + 1
                continue
            # Never shorten. The listing text is sometimes richer than the page behind it.
            if len(body_txt) <= (row.have or 0):
                failed += 1
                reasons["fetched body is shorter than the stored one"] = \
                    reasons.get("fetched body is shorter than the stored one", 0) + 1
                continue
            applied += 1
            gained.append(len(body_txt))
            if args.apply:
                db.execute(text(
                    "UPDATE eprs_publications SET full_text = :t, word_count = :w, "
                    "  has_full_text = TRUE, extraction_quality = 'fetched', "
                    "  last_updated = now() WHERE id = :id"),
                    {"t": body_txt, "w": len(body_txt.split()), "id": row.id})
        if args.apply:
            db = _commit(db)
        avg = sum(gained) // len(gained) if gained else 0
        tally = ", ".join(f"{k} x{v}" for k, v in sorted(reasons.items(), key=lambda kv: -kv[1])[:5])
        print(f"  [{min(start + 20, len(targets)):5}/{len(targets)}] ok {applied}, failed {failed}, "
              f"avg {avg:,} chars  |  {tally}", flush=True)
        time.sleep(args.throttle)

    avg = sum(gained) // len(gained) if gained else 0
    label = "APPLIED" if args.apply else "DRY-RUN"
    print(f"[{label}] full text for {applied}, failed {failed}; average {avg:,} characters",
          flush=True)
    db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
