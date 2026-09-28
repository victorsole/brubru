"""Ingest Commission follow-up to EP adopted texts (EP Open Data /external-documents).

What this is: ACT_FOLLOWUP records, identifiers like SP-2026-04-14-TA-10-2025-0343, saying
what the Commission intends to do about a resolution Parliament adopted. No other source we
ingest carries that link.

Two behaviours of the source shape this script, both measured on 28 Sep 2026:

* **Deep offsets time out.** offset 1,000 and 3,000 answer; 4,000 and 6,000 do not (EP's own
  open issue #28). So the corpus is walked YEAR BY YEAR, never paged to the end.
* **A 200 can carry an error.** The gateway answers 200 with `{"error": "..."}` and no
  `data` key when its backend fails, and 429 with `Retry-After` when it throttles, which is
  intermittent rather than a rate ceiling. Both are retried; neither is ever recorded as
  "this year has no documents".

Nothing is derived. document_date comes from the EP record and stays NULL when EP does not
state one; the identifier is not parsed into a date. Body text is read from the EN DOCX the
API lists, and a document whose body we could not read keeps NULL rather than its title.

Run:
    python3.12 scripts/ingest_ep_external_documents.py --years 2026            # dry-run
    python3.12 scripts/ingest_ep_external_documents.py --apply --years 2026
    python3.12 scripts/ingest_ep_external_documents.py --apply                 # every year
"""
from __future__ import annotations

import argparse
import datetime as dt
import io
import re
import sys
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO_ROOT = str(Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402
from sqlalchemy import text  # noqa: E402

from core.database import SessionLocal  # noqa: E402

API = "https://data.europarl.europa.eu/api/v2/external-documents"
BASE = "https://data.europarl.europa.eu/"
UA = "Brubru/1.0 (EU policy intelligence; +https://brubru.beresol.eu)"
HEADERS = {"Accept": "application/ld+json", "User-Agent": UA}
MIN_BODY = 200


class EPBlocked(RuntimeError):
    """EP refused us. Not the same as the year being empty."""


def _get(client: httpx.Client, url: str, params: Dict[str, Any],
         attempts: int = 4) -> Optional[Dict[str, Any]]:
    """A parsed payload, or None when EP genuinely has no record. Raises when refused."""
    last = ""
    for attempt in range(1, attempts + 1):
        try:
            r = client.get(url, params=params)
        except Exception as exc:  # noqa: BLE001  (ReadTimeout is normal here)
            last = type(exc).__name__
            time.sleep(4.0 * attempt)
            continue
        if r.status_code in (429, 503):
            try:
                wait = int(r.headers.get("Retry-After") or 60)
            except (TypeError, ValueError):
                wait = 60
            last = f"HTTP {r.status_code}"
            time.sleep(min(max(wait, 5), 180))
            continue
        if r.status_code == 404:
            return None
        try:
            payload = r.json()
        except Exception:  # noqa: BLE001
            last = f"unparseable HTTP {r.status_code}"
            time.sleep(3.0 * attempt)
            continue
        if "data" not in payload and payload.get("error"):
            last = str(payload["error"])[:90]
            time.sleep(3.0 * attempt)
            continue
        return payload
    raise EPBlocked(f"{url} {params}: {last}")


def _docx_text(blob: bytes) -> Optional[str]:
    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            xml = z.open("word/document.xml").read().decode("utf-8", "replace")
    except Exception:  # noqa: BLE001
        return None
    # <w:cr/> and <w:br/> are line breaks: dropping them fuses the words either side.
    t = re.sub(r"<w:(br|cr)\b[^>]*/?>", "\n", xml)
    t = re.sub(r"<w:tab\b[^>]*/?>", " ", t)
    t = re.sub(r"</w:(p|tr)>", "\n", t)
    t = re.sub(r"</w:tc>", " ", t)
    t = re.sub(r"<[^>]+>", "", t)
    t = (t.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
          .replace("&quot;", '"').replace("&apos;", "'"))
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip() or None


def _first(value):
    if isinstance(value, list):
        return value[0] if value else None
    return value


def _en_docx(record: Dict[str, Any]) -> Optional[str]:
    """The English DOCX manifestation path, if the record lists one."""
    import json
    blob = json.dumps(record)
    paths = re.findall(r'"is_exemplified_by"\s*:\s*"([^"]+)"', blob)
    for p in paths:
        if p.endswith("_en.docx"):
            return BASE + p.lstrip("/")
    return None


def _label(value) -> Optional[str]:
    """EP labels are language maps; take English, else any."""
    if isinstance(value, dict):
        return value.get("en") or next(iter(value.values()), None)
    if isinstance(value, list):
        for v in value:
            got = _label(v)
            if got:
                return got
        return None
    return value


_UPSERT = text("""
INSERT INTO ep_external_documents
    (identifier, work_type, document_date, identifier_year, title, answers_to,
     creator, public_url, file_url, body_txt, body_html, body_source, scraped_at)
VALUES
    (:identifier, :work_type, CAST(:document_date AS DATE), :identifier_year, :title,
     :answers_to, :creator, :public_url, :file_url, :body_txt, NULL, :body_source, now())
ON CONFLICT (identifier) DO UPDATE SET
    work_type       = EXCLUDED.work_type,
    document_date   = COALESCE(EXCLUDED.document_date, ep_external_documents.document_date),
    identifier_year = EXCLUDED.identifier_year,
    title           = COALESCE(EXCLUDED.title, ep_external_documents.title),
    answers_to      = COALESCE(EXCLUDED.answers_to, ep_external_documents.answers_to),
    creator         = COALESCE(EXCLUDED.creator, ep_external_documents.creator),
    public_url      = COALESCE(EXCLUDED.public_url, ep_external_documents.public_url),
    file_url        = COALESCE(EXCLUDED.file_url, ep_external_documents.file_url),
    -- Never shorten a body we already hold: a run that could not read the file must not
    -- erase one that could.
    body_txt        = CASE WHEN length(COALESCE(EXCLUDED.body_txt, '')) >
                                length(COALESCE(ep_external_documents.body_txt, ''))
                           THEN EXCLUDED.body_txt ELSE ep_external_documents.body_txt END,
    body_source     = CASE WHEN length(COALESCE(EXCLUDED.body_txt, '')) >
                                length(COALESCE(ep_external_documents.body_txt, ''))
                           THEN EXCLUDED.body_source ELSE ep_external_documents.body_source END,
    scraped_at      = now()
""")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--years", help="Comma-separated, e.g. 2025,2026. Default: 2004..this year")
    ap.add_argument("--limit", type=int, default=100, help="Page size")
    ap.add_argument("--max-seconds", type=int, default=3000)
    ap.add_argument("--bodies", action="store_true", default=True,
                    help="Fetch the EN DOCX body (default on)")
    ap.add_argument("--no-bodies", dest="bodies", action="store_false")
    args = ap.parse_args()

    this_year = dt.date.today().year
    years = ([int(y) for y in args.years.split(",")] if args.years
             else list(range(this_year, 2003, -1)))

    db = SessionLocal()
    started = time.time()
    seen = stored = bodies = no_body = skipped_body = 0
    # Identifiers whose body we already hold. A scheduled run walks newest-first every
    # day, and without this it would re-download every DOCX it has ever read: ~140 files
    # for the current year alone, to store nothing new.
    already = {r[0] for r in db.execute(text(
        "SELECT identifier FROM ep_external_documents "
        "WHERE length(COALESCE(body_txt, '')) >= :min"), {"min": MIN_BODY})}
    print(f"[INFO] {len(already)} document(s) already carry a body and will not be re-fetched")
    blocked_years: List[int] = []
    try:
        with httpx.Client(headers=HEADERS, timeout=90.0, follow_redirects=True) as client:
            for year in years:
                if time.time() - started > args.max_seconds:
                    print(f"[INFO] budget reached before year {year}")
                    break
                offset = 0
                year_count = 0
                while True:
                    try:
                        payload = _get(client, API, {"year": year, "limit": args.limit,
                                                     "offset": offset})
                    except EPBlocked as exc:
                        print(f"  [{year}] REFUSED at offset {offset}: {exc}", flush=True)
                        blocked_years.append(year)
                        break
                    items = (payload or {}).get("data") or []
                    if not items:
                        break
                    for it in items:
                        seen += 1
                        ident = it.get("identifier")
                        if not ident:
                            continue
                        detail = None
                        try:
                            d = _get(client, f"{API}/{ident}", {"format": "application/ld+json"})
                            detail = (d or {}).get("data", [{}])[0] if d else None
                        except EPBlocked:
                            detail = None
                        rec = detail or it
                        # The date comes from EP. It is NOT parsed out of the identifier.
                        raw_date = _first(rec.get("document_date"))
                        doc_date = str(raw_date)[:10] if raw_date else None
                        body_txt = None
                        file_url = _en_docx(rec) if detail else None
                        if ident in already:
                            skipped_body += 1
                        elif args.bodies and file_url:
                            try:
                                blob = client.get(file_url, timeout=90.0).content
                                if blob[:2] == b"PK":
                                    body_txt = _docx_text(blob)
                            except Exception:  # noqa: BLE001
                                body_txt = None
                        if body_txt and len(body_txt) < MIN_BODY:
                            body_txt = None
                        if ident not in already:
                            bodies += bool(body_txt)
                            no_body += (not body_txt)
                        answers = rec.get("answers_to")
                        if isinstance(answers, str):
                            answers = [answers]
                        row = {
                            "identifier": ident,
                            "work_type": (_first(rec.get("work_type")) or "").rsplit("/", 1)[-1] or None,
                            "document_date": doc_date,
                            "identifier_year": rec.get("identifierYear") or None,
                            "title": _label(rec.get("title_dcterms")) or _label(rec.get("label")),
                            "answers_to": answers or None,
                            "creator": _first(rec.get("creator")),
                            "public_url": f"https://data.europarl.europa.eu/eli/dl/doc/{ident}",
                            "file_url": file_url,
                            "body_txt": body_txt,
                            "body_source": "fetched:docx" if body_txt else None,
                        }
                        if args.apply:
                            db.execute(_UPSERT, row)
                            stored += 1
                        year_count += 1
                    if args.apply:
                        db.commit()
                    if len(items) < args.limit:
                        break
                    offset += args.limit
                    time.sleep(0.4)
                print(f"  [{year}] {year_count} document(s)", flush=True)
                time.sleep(0.5)

        print(f"\n[DONE] seen={seen} stored={stored} with_body={bodies} "
              f"without_body={no_body} body_already_held={skipped_body}"
              f"{'' if args.apply else '  (DRY-RUN)'}")
        if blocked_years:
            print(f"[SYNC_STATUS] degraded: EP refused these years, they are NOT empty: "
                  f"{sorted(set(blocked_years))}")
        if seen == 0:
            print("[ERROR] no documents read at all: the endpoint or its parameters changed")
            return 1
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
