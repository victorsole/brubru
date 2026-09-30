#!/usr/bin/env python3.12
"""Write the files attached to agency procurement procedures into procurement_documents.

API audit, 30 Sep 2026 (Victor approved "Part A"): the procurement routes under
/api/v2/funding carried no document. Each procedure page lists its files (terms of
reference, forms, Q&A, corrigenda, award notices); this script reads that list, downloads
each file ONCE, extracts its text (services/documents/text_extract.py) and stores the text,
not the binary. A file inside a ZIP is its own row (file_url = archive + "#" + path).

Which procedures
----------------
  default   the live and recent ones: status open/forthcoming, or a deadline or
            publication date within --recent-days (365). That is where files are added
            (clarifications, corrigenda, the award notice months after closing).
  --all     every procedure of the body (the backfill).
A file already stored is not downloaded again (its title, date and size still refresh);
--refresh re-downloads and re-extracts.

Bodies (SOURCES):
  cedefop   procedure pages, "Downloads" block, plain HTTP
  echa      procedure pages and files through the WAF browser (403 to plain HTTP)
  eea, efsa Funding & Tenders notices: cftDocuments (title, type, language, date) from
            SEDIA, each file from its own portal address

Usage
-----
    python3.12 scripts/sync_procurement_documents.py --body cedefop --dry-run --limit 20
    python3.12 scripts/sync_procurement_documents.py --body cedefop --all --apply
    python3.12 scripts/sync_procurement_documents.py --body cedefop --apply      # daily
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time
from collections import Counter
from datetime import datetime, timedelta, timezone

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_BACKEND = pathlib.Path(__file__).resolve().parents[1]
for _p in (str(_REPO_ROOT), str(_BACKEND)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import requests  # noqa: E402
from sqlalchemy import text  # noqa: E402

from services.documents.text_extract import MAX_BYTES, extract, to_html  # noqa: E402
from services.scrapers import agency_procurement as ap  # noqa: E402

PACE_SECONDS = 0.5


class _Source:
    """Lists a procedure's files and downloads them. A context manager, because some
    sources hold a session (ECHA's browser) for the whole run."""
    source_kinds: tuple[str, ...] = ()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return None

    def list(self, page_url: str, ref: str | None) -> list[dict]:
        raise NotImplementedError

    def download(self, url: str) -> tuple[bytes | None, str | None]:
        return _download(url)


class _Cedefop(_Source):
    """Cedefop procedure pages, "Downloads" block; plain HTTP."""
    source_kinds = ("cedefop_procurement",)

    def list(self, page_url, ref):
        return ap._cedefop_documents(ap._get_ok(page_url.split("#")[0]))


class _Echa(_Source):
    """ECHA procedure pages and their files sit behind a WAF (403 + a challenge page to
    plain HTTP, 30 Sep 2026): one browser session reads both."""
    source_kinds = ("echa_procurement",)

    def __enter__(self):
        from services.scrapers.waf_browser_fetcher import WafBrowserFetcher
        self._f = WafBrowserFetcher().__enter__()
        return self

    def __exit__(self, *exc):
        self._f.__exit__(*exc)

    def list(self, page_url, ref):
        html = self._f.fetch(page_url, strip_chrome=False).html or ""
        if "single-procurement" not in html:
            # A challenge or error page must not read as "this procedure has no files".
            raise RuntimeError("no procedure block on the page (wall or error page)")
        return ap._echa_detail(html)["documents"]

    def download(self, url):
        status, body, err = self._f.fetch_bytes(url, warm_url=ap._ECHA_PROCUREMENT_URL)
        if err or status != 200:
            return None, f"no-text:download-failed:{status or err.split(':')[0]}"
        if len(body) > MAX_BYTES:
            return None, "no-text:too-large"
        if body[:200].lstrip().lower().startswith((b"<!doctype", b"<html")):
            return None, "no-text:served-html"
        return body, None


class _Portal(_Source):
    """Funding & Tenders notices of one buyer: each notice's documents (title, type,
    language, date) from SEDIA's cftDocuments, each file from its own portal address."""

    def __init__(self, body_code: str, buyer_id: str, source_kind: str):
        self.body_code, self.buyer_id = body_code, buyer_id
        self.source_kinds = (source_kind,)

    def __enter__(self):
        self._docs: dict[str, list[dict]] = {}
        for res in ap._ft_buyer_results(self.body_code, self.buyer_id):
            ident = ((res.get("metadata") or {}).get("identifier") or [None])[0]
            if ident and ident not in self._docs:
                self._docs[ident] = ap._ft_notice_documents(res)
        return self

    def list(self, page_url, ref):
        if (ref or "") not in self._docs:
            # Not "no files": the portal no longer returns this notice at all.
            raise RuntimeError(f"notice {ref} not returned by SEDIA for buyer {self.buyer_id}")
        return [dict(d) for d in self._docs[ref]]


# body_code -> the source of its procurement files
SOURCES = {
    "cedefop": lambda: _Cedefop(),
    "echa": lambda: _Echa(),
    "eea": lambda: _Portal("eea", ap._EEA_FT_BUYER_ID, "eea_ft_notice"),
    "efsa": lambda: _Portal("efsa", ap._EFSA_FT_BUYER_ID, "efsa_ft_notice"),
}
LISTERS = SOURCES   # the API registers /documents for exactly these bodies


_PROCEDURES = text("""
    SELECT id, public_url, tender_reference
      FROM economy_items
     WHERE body_code = :body AND source_kind = ANY(:kinds)
       AND (:all OR status IN ('open', 'forthcoming')
            OR deadline >= :since OR document_date >= :since)
     ORDER BY id
""")

_KNOWN = text("""
    SELECT file_url, parent_file_url, body_source FROM procurement_documents
     WHERE economy_item_id = :item
""")

# Never regress: a NULL leaves the stored value; the longer text wins; body_source moves
# with the text it describes.
_UPSERT = text("""
    INSERT INTO procurement_documents
        (economy_item_id, body_code, tender_reference, title, file_url, parent_file_url,
         file_name, file_format, file_size, language, document_date, public_url,
         body_txt, body_html, body_source)
    VALUES (:item, :body, :ref, :title, :file_url, :parent, :name, :fmt, :size, :lang,
            :date, :public_url, :body_txt, :body_html, :body_source)
    ON CONFLICT (economy_item_id, file_url) DO UPDATE SET
        tender_reference = COALESCE(EXCLUDED.tender_reference, procurement_documents.tender_reference),
        title            = COALESCE(EXCLUDED.title, procurement_documents.title),
        parent_file_url  = COALESCE(EXCLUDED.parent_file_url, procurement_documents.parent_file_url),
        file_name        = COALESCE(EXCLUDED.file_name, procurement_documents.file_name),
        file_format      = COALESCE(EXCLUDED.file_format, procurement_documents.file_format),
        file_size        = COALESCE(EXCLUDED.file_size, procurement_documents.file_size),
        language         = COALESCE(EXCLUDED.language, procurement_documents.language),
        document_date    = COALESCE(EXCLUDED.document_date, procurement_documents.document_date),
        public_url       = COALESCE(EXCLUDED.public_url, procurement_documents.public_url),
        body_source      = CASE
            WHEN EXCLUDED.body_source IS NULL THEN procurement_documents.body_source
            WHEN procurement_documents.body_txt IS NULL THEN EXCLUDED.body_source
            WHEN length(EXCLUDED.body_txt) >= length(procurement_documents.body_txt)
                THEN EXCLUDED.body_source
            ELSE procurement_documents.body_source END,
        body_txt         = CASE
            WHEN EXCLUDED.body_txt IS NULL THEN procurement_documents.body_txt
            WHEN procurement_documents.body_txt IS NULL
              OR length(EXCLUDED.body_txt) >= length(procurement_documents.body_txt)
                THEN EXCLUDED.body_txt
            ELSE procurement_documents.body_txt END,
        body_html        = CASE
            WHEN EXCLUDED.body_html IS NULL THEN procurement_documents.body_html
            WHEN procurement_documents.body_html IS NULL
              OR length(EXCLUDED.body_html) >= length(procurement_documents.body_html)
                THEN EXCLUDED.body_html
            ELSE procurement_documents.body_html END,
        scraped_at       = NOW()
""")


def _download(url: str) -> tuple[bytes | None, str | None]:
    """(bytes, None) or (None, reason). Refuses a file over MAX_BYTES without reading it."""
    try:
        r = requests.get(url, headers=ap._HEADERS, timeout=90, stream=True)
        r.raise_for_status()
        size = int(r.headers.get("Content-Length") or 0)
        if size > MAX_BYTES:
            r.close()
            return None, "no-text:too-large"
        buf = bytearray()
        for chunk in r.iter_content(1 << 16):
            buf += chunk
            if len(buf) > MAX_BYTES:
                r.close()
                return None, "no-text:too-large"
        ctype = (r.headers.get("Content-Type") or "").lower()
        if "text/html" in ctype and not url.lower().endswith((".htm", ".html")):
            return None, "no-text:served-html"   # an error or challenge page, never a body
        return bytes(buf), None
    except requests.RequestException as exc:
        code = getattr(getattr(exc, "response", None), "status_code", None)
        return None, f"no-text:download-failed:{code or type(exc).__name__}"


def _rows_for(doc: dict, data: bytes | None, reason: str | None) -> list[dict]:
    """One row per file; a ZIP becomes one row per file inside it."""
    base = {"title": doc["title"], "lang": doc.get("language"), "date": doc.get("document_date"),
            "public_url": doc.get("public_url")}
    if data is None:
        return [{**base, "file_url": doc["file_url"], "parent": None, "name": doc["file_name"],
                 "fmt": doc.get("file_format"), "size": doc.get("file_size"),
                 "body_txt": None, "body_html": None, "body_source": reason}]
    rows = []
    for e in extract(data, doc["file_name"]):
        inner = e.inner
        rows.append({**base,
                     "file_url": f"{doc['file_url']}#{e.name}" if inner else doc["file_url"],
                     "parent": doc["file_url"] if inner else None,
                     "name": e.name, "fmt": e.fmt,
                     "size": e.size if inner else (doc.get("file_size") or e.size),
                     "body_txt": e.text, "body_html": to_html(e.text), "body_source": e.source})
    return rows


def _run(args, source, procs, has_table, stats, by_source, report) -> None:
    from core.database import SessionLocal
    for n, (item_id, page_url, ref) in enumerate(procs, 1):
        try:
            docs = source.list(page_url, ref)
        except Exception as exc:  # noqa: BLE001 - one page must not stop the run
            stats["pages_failed"] += 1
            print(f"[WARN] page {page_url}: {type(exc).__name__}: {exc}", flush=True)
            continue
        stats["pages_read"] += 1
        stats["files_listed"] += len(docs)
        if docs:
            stats["procedures_with_files"] += 1
        stored = []
        if has_table:
            s = SessionLocal()
            try:
                stored = s.execute(_KNOWN, {"item": item_id}).all()
            finally:
                s.close()
        # rows keyed on the file itself; a failed download is retried on the next run
        own = {r[0] for r in stored if not (r[2] or "").startswith("no-text:download-failed")}
        archives = {r[1] for r in stored if r[1]}         # ZIPs stored as their members
        rows: list[dict] = []
        for doc in docs:
            doc["public_url"] = page_url.split("#")[0]
            if doc["file_url"] in archives and not args.refresh:
                stats["files_already_stored"] += 1     # its members carry the metadata
                continue
            if doc["file_url"] in own and not args.refresh:
                stats["files_already_stored"] += 1
                # Metadata only: NULL body fields leave the stored text untouched.
                rows.append({"title": doc["title"], "lang": doc.get("language"),
                             "date": doc.get("document_date"), "public_url": doc["public_url"],
                             "file_url": doc["file_url"], "parent": None,
                             "name": doc["file_name"], "fmt": None,   # the bytes decided it
                             "size": doc.get("file_size"), "body_txt": None,
                             "body_html": None, "body_source": None})
                continue
            try:
                data, reason = source.download(doc["file_url"])
                stats["files_downloaded" if data is not None else "files_not_downloaded"] += 1
                new = _rows_for(doc, data, reason)
            except Exception as exc:  # noqa: BLE001 - one file must not stop the run
                stats["files_failed"] += 1
                print(f"[WARN] file {doc['file_url'][-80:]}: {type(exc).__name__}: {exc}", flush=True)
                new = _rows_for(doc, None, f"no-text:extract-failed:{type(exc).__name__}")
            for r in new:
                by_source[":".join((r["body_source"] or "none").split(":")[:2])] += 1
            rows.extend(new)
            time.sleep(PACE_SECONDS)
        if args.dry_run:
            report.append({"item": item_id, "page": page_url, "ref": ref, "files": [
                {k: (str(v) if k == "date" and v else v) for k, v in r.items()
                 if k not in ("body_txt", "body_html")}
                | {"chars": len(r["body_txt"] or "")} for r in rows]})
        elif rows:
            s = SessionLocal()
            try:
                for r in rows:
                    s.execute(_UPSERT, {**r, "item": item_id, "body": args.body, "ref": ref})
                s.commit()
                stats["rows_written"] += len(rows)
            finally:
                s.close()
        if n % 25 == 0:
            print(f"    {n}/{len(procs)} procedures, {dict(stats)}", flush=True)
            print(f"    text by source: {dict(by_source)}", flush=True)
            if args.dry_run and args.report:   # written as it goes: a killed run keeps its report
                pathlib.Path(args.report).write_text(json.dumps(
                    {"stats": stats, "by_source": dict(by_source), "procedures": report,
                     "partial": True}, indent=1, default=str))
        time.sleep(PACE_SECONDS)


def main() -> int:
    ap_ = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap_.add_argument("--body", required=True, choices=sorted(SOURCES))
    ap_.add_argument("--all", action="store_true", help="every procedure (backfill)")
    ap_.add_argument("--recent-days", type=int, default=365)
    ap_.add_argument("--limit", type=int, default=0, help="stop after N procedures")
    ap_.add_argument("--refresh", action="store_true", help="re-download files already stored")
    mode = ap_.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    ap_.add_argument("--report", help="dry run: write a JSON report here")
    args = ap_.parse_args()

    import logging
    from core.database import SessionLocal
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    started = datetime.now(timezone.utc)
    source = SOURCES[args.body]()
    since = (started - timedelta(days=args.recent_days)).date()
    stats: Counter = Counter()
    by_source: Counter = Counter()
    report: list[dict] = []
    error = None
    try:
        s = SessionLocal()
        try:
            procs = s.execute(_PROCEDURES, {"body": args.body, "kinds": list(source.source_kinds),
                                            "all": args.all, "since": since}).all()
        finally:
            s.close()
        if args.limit:
            procs = procs[:args.limit]
        s = SessionLocal()
        try:
            has_table = s.execute(text("SELECT to_regclass('public.procurement_documents')")).scalar()
        finally:
            s.close()
        if not has_table and args.apply:
            raise RuntimeError("procurement_documents does not exist: apply migration 263 first")
        print(f"[INFO] {args.body}: {len(procs)} procedure(s) to read", flush=True)
        with source:
            _run(args, source, procs, has_table, stats, by_source, report)
        print(f"[INFO] {dict(stats)}", flush=True)
        print(f"[INFO] text by source: {dict(by_source)}", flush=True)
        if procs and stats["pages_read"] == 0:
            raise RuntimeError("no procedure page could be read")
        if stats["pages_failed"] > max(3, len(procs) // 5):
            raise RuntimeError(f"{stats['pages_failed']} of {len(procs)} procedure pages failed")
        if args.dry_run:
            if args.report:
                pathlib.Path(args.report).write_text(json.dumps(
                    {"stats": stats, "by_source": {k: v for k, v in by_source.items()},
                     "procedures": report}, indent=1, default=str))
                print(f"[DRY-RUN] report: {args.report}")
            print("[DRY-RUN] nothing written")
        return 0
    except Exception as exc:  # recorded, then a failing exit
        error = f"{type(exc).__name__}: {exc}"
        print(f"[ERROR] {error}", flush=True)
        return 1
    finally:
        if args.apply:
            try:
                from services.sync.freshness import record_run
                s = SessionLocal()
                record_run(s, source_key=f"procurement_documents_{args.body}", tier="daily",
                           status="failed" if error else "success",
                           items_added=stats.get("rows_written"), error=error,
                           started_at=started, finished_at=datetime.now(timezone.utc))
                s.close()
            except Exception as exc:  # noqa: BLE001
                print(f"[WARN] could not record the run: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    sys.exit(main())
