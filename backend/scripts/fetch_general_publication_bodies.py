"""Give `eu_general_publications` the actual publication, and its actual date.

Measured 25 September 2026, and the shape is the whole point: all 4,854 rows have a
non-null `body_txt` AND a non-null `body_html`, so by the old measure the table was 100%
backfilled. The longest body_txt in the table is 590 characters. Every one is the title
plus "EU general publication (Publications Office of the European Union)". Not one is a
publication.

`publication_date` is wrong too, in the same way the delegated acts were: it holds OUR
import date. A 1997 Eurostat title is stored as 2026-06-04, and the dates cluster on the
days the import ran (1,524 on 28 May, 1,439 on 4 June). Cellar has the real one as
cdm:work_date_document, 1997-11-14 for that publication.

The route to the text, verified before this was written:

    work (cellar_uri)
      -> cdm:expression_belongs_to_work, filtered to the ENGLISH expression
         (0001/0002/0003 here are EN/FR/DE: taking the first would have stored German)
      -> cdm:manifestation_manifests_expression with manifestation_type "pdfa1b"
      -> the manifestation's RDF gives cdm:manifestation_has_item, the .../DOC_1 file
      -> fetch that with Accept: */* and it returns application/pdf

For the sample publication that yields 16,141 characters of real text from 4 pages,
against the 275-character stub we serve.

`body_html` is deliberately left NULL. These are PDFs: there is no HTML document, and
synthesising one is exactly what produced the stubs. The text goes in body_txt,
`body_source` records that it came from a PDF, and the absence of HTML is honest and
machine-readable rather than padded.

Usage (from backend/):
    python3.12 scripts/fetch_general_publication_bodies.py --limit 5
    python3.12 scripts/fetch_general_publication_bodies.py --limit 5 --apply
    python3.12 scripts/fetch_general_publication_bodies.py --all --apply
"""
from __future__ import annotations

import argparse
import asyncio
import concurrent.futures as cf
import io
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from sqlalchemy import text  # noqa: E402

from core.database import SessionLocal  # noqa: E402
from services.api_clients.cellar_sparql_client import CellarSPARQLClient  # noqa: E402

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)", "Accept": "*/*"}

# Corpora whose rows carry a Cellar work URI, so the same route reaches all of them.
# Column names differ per table, which is why they are declared rather than assumed:
# guessing a column name aborted two whole batches earlier today.
TABLES = {
    "eu_general_publications": {
        "uri": "cellar_uri", "txt": "body_txt", "html": "body_html",
        "date": "publication_date", "source": None, "flag": None,
    },
    "eu_eesc_opinions": {
        "uri": "work_uri", "txt": "body_text", "html": "body_html",
        "date": "document_date", "source": "body_source", "flag": "has_body",
    },
    "eu_cor_opinions": {
        "uri": "work_uri", "txt": "body_text", "html": "body_html",
        "date": "document_date", "source": "body_source", "flag": "has_body",
    },
}
ENG = "<http://publications.europa.eu/resource/authority/language/ENG>"
MIN_BODY = 500          # below this a PDF extraction is a cover page, not a publication
BODY_CAP = 800_000      # the same ceiling economy_common uses, so bodies stay comparable
# What counts as ALREADY DONE when resuming. It must sit above the composed stubs this
# replaces, which run to 590 characters: resuming on MIN_BODY (500) would have silently
# skipped the 14 longest stubs and called the corpus complete.
HAVE_REAL_BODY = 1_200
_ITEM = re.compile(r'manifestation_has_item rdf:resource="([^"]+)"')


def _q_batch(uris: list[str]) -> str:
    """One query for many works. A query per work spent ~7s per row, which is 9 hours for
    this corpus alone; batching the lookup and downloading in parallel brings it to well
    under one."""
    values = " ".join(f"<{u}>" for u in uris)
    return f"""
PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
SELECT ?w ?manif ?type ?doc_date WHERE {{
  VALUES ?w {{ {values} }}
  ?expr cdm:expression_belongs_to_work ?w ;
        cdm:expression_uses_language {ENG} .
  ?manif cdm:manifestation_manifests_expression ?expr ;
         cdm:manifestation_type ?type .
  OPTIONAL {{ ?w cdm:work_date_document ?doc_date . }}
}}
"""


def pick(entries: list[tuple[str, str]]) -> tuple[str | None, str | None]:
    """(manifestation, type): HTML first so body_html can be the real document, then any
    PDF variant. print/leaflet are paper and carry no text."""
    by_type = {}
    for t, m in entries:
        by_type.setdefault((t or "").lower(), m)
    for t, m in by_type.items():
        if t.startswith(("html", "xhtml")):
            return m, t
    for t, m in by_type.items():
        if t.startswith("pdf"):
            return m, t
    return None, None


def fetch_one(manif: str, mtype: str):
    """(body_txt, body_html, reason). `reason` is None on success.

    It returns WHY it failed, because a download that timed out and a publication that
    genuinely has no text are different facts and were being counted as one. 29 of 40 rows
    in a batch were filed as "no usable PDF" with no way to tell which they were.
    """
    try:
        rdf = _get(manif).decode("utf-8", "replace")
    except Exception as exc:  # noqa: BLE001
        return None, None, f"manifest {type(exc).__name__}"
    items = _ITEM.findall(rdf)
    if not items:
        return None, None, "no item in manifestation"
    # A manifestation holds several items and the RDF does not list them document-first:
    # DOC_2 (a cover JPEG) came before DOC_1 (the publication), so taking the first item
    # downloaded an image and reported "not a pdf" for 24 of 40 rows. DOC_1 first, then
    # the rest, and stop at whichever actually yields text.
    items.sort(key=lambda u: (not u.rstrip("/").endswith("DOC_1"), u))
    last = "no usable item"
    for item in items[:4]:
        try:
            raw = _get(item)
        except Exception as exc:  # noqa: BLE001
            last = f"download {type(exc).__name__}"
            continue
        if (mtype or "").startswith(("html", "xhtml")) or raw[:15].lstrip()[:1] == b"<":
            from services.scrapers.economy_common import extract_html
            txt, html = extract_html(raw.decode("utf-8", "replace"))
            if txt:
                return txt, html, None
            last = "html had no text"
            continue
        txt = pdf_text(raw)
        if txt:
            return txt, None, None
        last = "not a pdf" if raw[:4] != b"%PDF" else "pdf unreadable"
    return None, None, last


def _q(cellar_uri: str) -> str:
    """Every English manifestation, with its type, plus the work's real date.

    NOT filtered to one type. The first publication inspected offered "pdfa1b" and that
    was hardcoded; across a random dozen the types are pdf (9), pdfx (7), pdfa1b (3),
    pdfx4 (1), plus print/leaflet and occasionally html. Asking for pdfa1b alone found a
    manifestation for a quarter of them and reported the rest as having no text.
    """
    return f"""
PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
SELECT ?manif ?type ?doc_date WHERE {{
  ?expr cdm:expression_belongs_to_work <{cellar_uri}> ;
        cdm:expression_uses_language {ENG} .
  ?manif cdm:manifestation_manifests_expression ?expr ;
         cdm:manifestation_type ?type .
  OPTIONAL {{ <{cellar_uri}> cdm:work_date_document ?doc_date . }}
}} LIMIT 40
"""


def _val(row, key):
    v = row.get(key)
    if isinstance(v, dict):
        v = v.get("value")
    return str(v) if v else None


def clean_text(value: str | None) -> str | None:
    """PDF extraction yields NUL bytes and PostgreSQL refuses them outright:
    "A string literal cannot contain NUL (0x00) characters" killed all three corpora on
    their first commit. The same strip is in backfill_eu_trade_defence.py."""
    if value is None:
        return None
    return value.replace("\x00", "") or None


def _get(url: str, timeout: int = 60) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read()


def pdf_text(data: bytes, max_pages: int = 60) -> str | None:
    if data[:4] != b"%PDF":
        return None
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        return "\n".join((p.extract_text() or "")
                          for p in reader.pages[:max_pages]).strip()[:BODY_CAP]
    except Exception:
        return None


async def resolve(client, cellar_uri: str) -> tuple[str | None, str | None, str | None]:
    """(manifestation uri, its type, work_date_document) for the best English rendering.

    HTML first when the publication has one, because then body_html can be the real
    document rather than nothing; otherwise any PDF variant. print/leaflet manifestations
    are paper and carry no text to fetch.
    """
    rows = await client.select(_q(cellar_uri))
    if not rows:
        return None, None, None
    doc_date = next((_val(r, "doc_date") for r in rows if _val(r, "doc_date")), None)
    by_type = {}
    for r in rows:
        t, m = _val(r, "type"), _val(r, "manif")
        if t and m:
            by_type.setdefault(t.lower(), m)
    for t, m in by_type.items():
        if t.startswith("html") or t.startswith("xhtml"):
            return m, t, doc_date
    for t, m in by_type.items():
        if t.startswith("pdf"):
            return m, t, doc_date
    return None, None, doc_date


async def _run(args) -> int:
    db = SessionLocal()
    client = CellarSPARQLClient()
    try:
        limit = 100000 if args.all else args.limit
        cfg = TABLES[args.table]
        rows = db.execute(text(
            f"SELECT id, {cfg['uri']} AS cellar_uri, "
            f"       coalesce(length({cfg['txt']}),0) AS blen, "
            f"       left(coalesce(title,''),58) AS title "
            f"FROM {args.table} WHERE {cfg['uri']} IS NOT NULL "
            f"  AND coalesce(length({cfg['txt']}), 0) < :min "
            f"ORDER BY id LIMIT :n"), {"n": limit, "min": HAVE_REAL_BODY}).fetchall()
        print(f"[INFO] {len(rows):,} publication(s); average body now "
              f"{sum(r.blen for r in rows)/max(len(rows),1):,.0f} characters")

        ok = no_pdf = failed = 0
        reasons: dict[str, int] = {}
        dated = 0
        lengths = []
        BATCH = 40
        for start_i in range(0, len(rows), BATCH):
            chunk = rows[start_i:start_i + BATCH]
            by_uri = {r.cellar_uri: r for r in chunk}
            # Retry a timed-out batch before giving up on it. Cellar times out
            # occasionally and a bare `continue` drops all 40 rows: resumability means
            # they come back on a later run, but only if someone runs one, and the batch
            # line then reports 40 failures that were never really tried.
            sparql_rows = None
            for attempt in range(3):
                try:
                    sparql_rows = await client.select(_q_batch(list(by_uri)))
                    break
                except Exception as exc:  # noqa: BLE001
                    if attempt == 2:
                        failed += len(chunk)
                        print(f"  [batch {start_i // BATCH + 1}] sparql "
                              f"{type(exc).__name__} after 3 tries: {str(exc)[:60]}",
                              flush=True)
                    else:
                        await asyncio.sleep(3 * (attempt + 1))
            if sparql_rows is None:
                continue

            manifs: dict[str, list] = {}
            dates: dict[str, str] = {}
            for sr in sparql_rows:
                w = _val(sr, "w")
                if not w:
                    continue
                manifs.setdefault(w, []).append((_val(sr, "type"), _val(sr, "manif")))
                d = _val(sr, "doc_date")
                if d:
                    dates.setdefault(w, d)

            jobs = {}
            for uri in by_uri:
                manif, mtype = pick(manifs.get(uri, []))
                if manif:
                    jobs[uri] = (manif, mtype)
                else:
                    no_pdf += 1

            results = {}
            if jobs:
                with cf.ThreadPoolExecutor(max_workers=6) as ex:
                    futures = {ex.submit(fetch_one, m, t): u for u, (m, t) in jobs.items()}
                    for fut in cf.as_completed(futures):
                        results[futures[fut]] = fut.result()

            for uri, (_b, _h, why) in results.items():
                if why:
                    reasons[why] = reasons.get(why, 0) + 1

            for uri, r in by_uri.items():
                body, body_html, _why = results.get(uri, (None, None, 'no manifestation'))
                doc_date = dates.get(uri)
                body, body_html = clean_text(body), clean_text(body_html)
                if body and len(body) >= MIN_BODY:
                    ok += 1
                    lengths.append(len(body))
                    if args.apply:
                        sets = [f"{cfg['txt']} = :t", f"{cfg['html']} = :h", "fetched_at = now()"]
                        if cfg["source"]:
                            sets.append(f"{cfg['source']} = "
                                        f"'fetched:{'html' if body_html else 'pdf'}'")
                        if cfg["flag"]:
                            sets.append(f"{cfg['flag']} = true")
                        db.execute(text(f"UPDATE {args.table} SET {', '.join(sets)} "
                                        f"WHERE id = :id"),
                                   {"t": body[:BODY_CAP], "h": body_html, "id": r.id})
                elif uri in jobs:
                    no_pdf += 1
                if doc_date and args.apply:
                    dated += db.execute(text(
                        f"UPDATE {args.table} SET {cfg['date']} = CAST(:d AS date) "
                        f"WHERE id = :id AND ({cfg['date']} IS NULL "
                        f"     OR {cfg['date']} <> CAST(:d AS date))"),
                        {"d": doc_date[:10], "id": r.id}).rowcount
            if args.apply:
                db.commit()
            done = min(start_i + BATCH, len(rows))
            avg_so_far = sum(lengths) / len(lengths) if lengths else 0
            top = ", ".join(f"{k} x{v}" for k, v in
                            sorted(reasons.items(), key=lambda kv: -kv[1])[:3])
            print(f"  [{done:5}/{len(rows)}] full text {ok}, none {no_pdf}, "
                  f"avg {avg_so_far:,.0f} chars" + (f"  |  {top}" if top else ""), flush=True)
            time.sleep(args.throttle)

        if args.apply:
            db.commit()
        avg = sum(lengths) / len(lengths) if lengths else 0
        print(f"\n[{'APPLIED' if args.apply else 'DRY-RUN'}] full text for {ok}, "
              f"no usable PDF for {no_pdf}, errors {failed}; average {avg:,.0f} characters"
              + (f"; {dated:,} date(s) corrected" if args.apply else ""))
        return 0
    finally:
        db.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", default="eu_general_publications", choices=sorted(TABLES),
                    help="which Cellar-backed corpus to fill")
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--throttle", type=float, default=0.5)
    ap.add_argument("--apply", action="store_true")
    return asyncio.run(_run(ap.parse_args()))


if __name__ == "__main__":
    sys.exit(main())
