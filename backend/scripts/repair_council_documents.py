"""Repair the Council register rows that the 14 Oct 2026 audit found wrong. One-off.

What it corrects, each read again from the document itself:
  * the date: 47 rows carried a later date than the one printed on them (a meeting date
    taken from the old listing), 4 carried none;
  * the title: 22 rows were titled with their bare reference (CM-4604-2026-INIT): lists
    of 'A' items, agendas and summary records, which carry no "Subject:" line; and
    subject lines that ran on into the page footer or the first paragraph ("Use of
    Pyrotechnics by Criminals 5003/25 2 JAI.1 LIMITE EN 1. Introduction") are cut back
    to the subject, only where the cut falls between two words;
  * the text: 21 working documents were stored letter by letter ("B r u s s e l s"), and
    31 texts stopped at the 200,000-character cap of the old fetcher.

Only a row still holding the value that was checked is written. `--rehearse` (the
default) prints every change and writes nothing; `--apply` writes them and saves the
rows' previous values to backend/data/backups/ first.

    python3.12 scripts/repair_council_documents.py              # rehearse
    python3.12 scripts/repair_council_documents.py --apply
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import date
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(BACKEND / ".env")

from sqlalchemy import text  # noqa: E402

from scripts.discover_council_documents import MAX_TEXT, parse, url_of  # noqa: E402
from scripts.ingest_council_documents import SOURCE_REGISTER, _clean, _engine  # noqa: E402
from services.scrapers.council_register import CouncilDoc, fetch_document_text  # noqa: E402

OLD_CAP = 200_000
SELECT = text("""
    SELECT id, external_id, title, published_date::date AS published, html_content,
           extra_metadata->>'meeting_date' AS meeting_date
    FROM institutional_publications WHERE source_slug = :s ORDER BY external_id""")
UPDATE = text("""
    UPDATE institutional_publications
       SET title = :title, published_date = :published, html_content = :body, summary = :summary,
           extra_metadata = coalesce(extra_metadata, '{}'::jsonb) || CAST(:meta AS jsonb)
     WHERE id = :id AND title = :old_title AND published_date::date IS NOT DISTINCT FROM :old_published
       AND md5(coalesce(html_content, '')) = md5(:old_body)""")


def spaced_share(body: str) -> float:
    words = (body or "")[:6000].split()
    return sum(len(w) == 1 for w in words) / len(words) if words else 0.0


def needs_new_text(body: str) -> str | None:
    # Exactly the old cap: the old fetcher cut at it. A longer text was read under the new
    # cap and is whole; `>=` sent 1,623 of them to be read again (15 Oct 2026).
    if len(body or "") == OLD_CAP:
        return "cut at 200,000 characters"
    if spaced_share(body) > 0.15:
        return "letter-spaced"
    return None


def plan_row(row, fetch) -> dict | None:
    """The corrections for one row, or None. `fetch` reads the document's text again."""
    body, why = row.html_content or "", needs_new_text(row.html_content or "")
    new_body = body
    if why:
        fresh = fetch(row.external_id)
        if fresh and len(fresh) >= len(body) * 0.5 and spaced_share(fresh) < spaced_share(body) + 0.01:
            new_body = fresh
        else:
            why = None
    meta = parse(row.external_id, new_body)
    parsed, title = meta["title"], row.title
    if row.title == row.external_id and parsed != row.external_id:
        title = parsed
    elif (len(parsed) < 400 and len(parsed) < len(row.title) and row.title.startswith(parsed)
          and row.title[len(parsed)].isspace()):
        # A subject line that ran on into the page footer or the first paragraph.
        title = parsed
    published = meta["published"] or row.published
    extra = {}
    if meta["meeting_date"] and not row.meeting_date:
        extra["meeting_date"] = meta["meeting_date"].isoformat()
    changes = {k: v for k, v in (
        ("title", title if title != row.title else None),
        ("published", published if published != row.published else None),
        ("text", why if new_body != body else None),
        ("meeting_date", extra.get("meeting_date"))) if v}
    if not changes:
        return None
    return {"id": row.id, "ref": row.external_id, "changes": changes, "title": title, "published": published,
            "body": new_body, "meta": extra, "old_title": row.title, "old_published": row.published,
            "old_body": body}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--rehearse", action="store_true", help="the default: print, write nothing")
    args = ap.parse_args(argv)

    def fetch(ref):
        time.sleep(0.25)
        doc = CouncilDoc(external_id=ref, title=ref, url=url_of(ref), published=None,
                         subject_matters=[], category="document")
        return _clean(fetch_document_text(doc, max_chars=MAX_TEXT))

    engine = _engine()
    # Streamed: 33,669 rows hold 1.1 GB of text (15 Oct 2026); only the rows to correct are kept.
    read, plans = 0, []
    with engine.connect() as conn:
        result = conn.execution_options(stream_results=True, max_row_buffer=500).execute(
            SELECT, {"s": SOURCE_REGISTER})
        for r in result:
            read += 1
            p = plan_row(r, fetch)
            if p:
                plans.append(p)
    tally = {}
    for p in plans:
        for k in p["changes"]:
            tally[k] = tally.get(k, 0) + 1
        print(f"  {p['ref']}: " + "; ".join(
            f"{k} {p['old_published']} -> {v}" if k == "published" else
            f"{k}: {p['old_title'][:40]!r} -> {v[:70]!r}" if k == "title" else f"{k} ({v})"
            for k, v in p["changes"].items()))
    print(f"[repair] {read} rows read, {len(plans)} to correct: {tally}")
    if not args.apply:
        print("[repair] rehearsal: nothing written")
        return 0

    backup = BACKEND / "data" / "backups" / f"council_documents_before_repair_{date.today().isoformat()}.csv"
    backup.parent.mkdir(parents=True, exist_ok=True)
    with backup.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "external_id", "title", "published_date", "html_content"])
        for p in plans:
            w.writerow([p["id"], p["ref"], p["old_title"], p["old_published"], p["old_body"]])
    written = 0
    with engine.begin() as conn:
        for p in plans:
            written += conn.execute(UPDATE, {
                "id": p["id"], "title": p["title"], "published": p["published"], "body": p["body"],
                "summary": p["body"][:900] if p["body"] else None, "meta": json.dumps(p["meta"]),
                "old_title": p["old_title"], "old_published": p["old_published"],
                "old_body": p["old_body"]}).rowcount
    print(f"[repair] written {written} of {len(plans)}; previous values in {backup}")
    return 0 if written == len(plans) else 1


if __name__ == "__main__":
    sys.exit(main())
