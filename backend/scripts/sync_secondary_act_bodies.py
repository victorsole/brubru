#!/usr/bin/env python3.12
"""Give every delegated and implementing act the text it has, every day (14 Oct 2026).

Two gaps found auditing GovClipping's /legislative/delegated-acts request:

  * No scheduled job fetched these acts' text. The last bodies were written by hand on
    1-2 October, so an act published after that stayed without text.
  * 88 delegated acts adopted by the Commission but not in the Official Journal (43
    adopted, the ones whose objection period may still run; 24 objected; 12 scrutiny
    finished; 8 withdrawn; 1 notified) had no text at all, and the endpoint composed a
    "body" from their metadata. The Commission's document register serves the text it
    adopted: C(2026)5161 gave 15 pages, 41,797 characters.

So, in order:
  1. an act with a CELEX and no Official Journal text gets it from Cellar (XHTML, then
     PDF), and replaces any Commission document held for it;
  2. an act with a C-number and no text gets the adopted document, main text and
     annexes, in English, from the document register.

Each row records where its text came from (body_source, migration 292). A text under
MIN_CHARS is refused: a short answer is how an error page gets stored. Planned and
cancelled acts have no document anywhere and are left alone.

    python3.12 scripts/sync_secondary_act_bodies.py                  # rehearse
    python3.12 scripts/sync_secondary_act_bodies.py --apply --max-seconds 300

Verdict: exit 1 when acts were due and no source answered at all; `[SYNC_STATUS]
degraded` when the time budget ran out before the queue did.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
for p in (str(BACKEND.parent), str(BACKEND)):
    if p not in sys.path:
        sys.path.insert(0, p)

import certifi  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

from scripts.fetch_secondary_act_bodies_xhtml import MIN_CHARS, _fetch as fetch_from_cellar  # noqa: E402

REGISTER = "https://ec.europa.eu/transparency/documents-register"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) BrubruIngest/1.0",
           "Referer": f"{REGISTER}/", "Accept": "application/json"}
C_NUMBER = re.compile(r"C\(\d{4}\)\s?\d{1,5}")
# Stages at which the Commission has adopted the act, so the document exists.
ADOPTED_STAGES = ("adopted", "objected", "scrutiny_finished", "withdrawn", "notified", "published")

DUE_OJ = text("""
    SELECT id, celex FROM secondary_acts
     WHERE act_type IN ('delegated', 'implementing') AND celex ~ '^3\\d{4}[A-Z]\\d{4}$'
       AND (coalesce(text_body, '') = '' OR body_source = 'commission_document')
       AND (body_fetched_at IS NULL OR body_fetched_at < now() - interval '20 hours')
     ORDER BY publication_date DESC NULLS LAST, celex""")

DUE_DOC = text("""
    SELECT id, reference, merged_from FROM secondary_acts
     WHERE act_type IN ('delegated', 'implementing') AND coalesce(text_body, '') = ''
       AND coalesce(celex, '') = '' AND status::text = ANY(:stages)
       AND (body_fetched_at IS NULL OR body_fetched_at < now() - interval '7 days')
     ORDER BY (act_type = 'delegated') DESC, (status = 'adopted') DESC, first_seen DESC""")

# Only over what was checked: an empty text, or a Commission document the Official
# Journal now replaces. A text another writer stored meanwhile is never overwritten.
STORE = text("""
    UPDATE secondary_acts
       SET text_body = :txt, body_html = :html, body_source = :src, body_fetched_at = now()
     WHERE id = :id AND (coalesce(text_body, '') = '' OR body_source = 'commission_document')""")
TRIED = text("UPDATE secondary_acts SET body_fetched_at = now() WHERE id = :id")


def database_url() -> str:
    """The environment first (the container has no .env), then backend/.env."""
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        env = BACKEND / ".env"
        m = re.search(r"^DATABASE_URL=(.*)$", env.read_text(), re.M) if env.exists() else None
        url = m.group(1).strip() if m else ""
    if not url:
        raise SystemExit("[FATAL] DATABASE_URL not set")
    return url


def c_number(reference: str, merged_from) -> str | None:
    """The act's Commission number: its reference, or one recorded when rows merged."""
    if reference and C_NUMBER.fullmatch(reference.strip()):
        return reference.strip()
    for m in (merged_from if isinstance(merged_from, list) else json.loads(merged_from or "[]")):
        ref = str((m or {}).get("reference") or "").strip()
        if C_NUMBER.fullmatch(ref):
            return ref
    return None


def english_files(record: dict) -> list[str]:
    """The ersIds of the English main document and annexes, in the register's order."""
    out = []
    for a in sorted(record.get("attachments") or [],
                    key=lambda a: (not a.get("main"), a.get("sequence") or 0, a.get("part") or 0)):
        ers = ((a.get("linguisticVersions") or {}).get("en") or {}).get("ersId")
        if ers and ers not in out:
            out.append(ers)
    return out


def _get(url: str, timeout: int = 60) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=timeout,
                                context=ssl.create_default_context(cafile=certifi.where())) as r:
        return r.read()


def pdf_text(data: bytes) -> str:
    from pypdf import PdfReader
    pages = PdfReader(io.BytesIO(data)).pages
    return clean(" ".join((p.extract_text() or "") for p in pages))


def clean(txt: str) -> str:
    """Whitespace collapsed and NUL removed: PostgreSQL refuses a text holding \\x00, and one
    PDF that extracted one stopped the first run (14 Oct 2026)."""
    return re.sub(r"\s+", " ", (txt or "").replace("\x00", "")).strip()


def fetch_commission_document(ref: str):
    """(text, None) for the adopted document, or a marker saying why not."""
    q = urllib.parse.quote(ref.replace(" ", ""))
    try:
        found = json.loads(_get(f"{REGISTER}/api/search/{q}?lang=en"))
    except urllib.error.HTTPError as e:
        return f"register_http_{e.code}"
    except Exception as e:
        return f"register_{type(e).__name__}"
    record = found[0] if isinstance(found, list) and found else found
    if not isinstance(record, dict) or not record:
        return "not_in_register"
    files = english_files(record)
    if not files:
        return "no_english_file"
    parts = []
    for ers in files:
        try:
            parts.append(pdf_text(_get(f"{REGISTER}/api/files/{q}?ersIds={ers}", timeout=120)))
        except urllib.error.HTTPError as e:
            return f"file_http_{e.code}"
        except Exception as e:
            return f"file_{type(e).__name__}"
        time.sleep(0.3)
    body = "\n\n".join(p for p in parts if p)
    if len(body) < MIN_CHARS:
        return f"too_short_{len(body)}"
    # The document prints its own number on its cover ("C(2026) 7021 final"): a file that
    # does not is not this act's, whatever the register filed it under.
    if not names_itself(body, ref):
        return "wrong_document"
    return body, None


def names_itself(body: str, ref: str) -> bool:
    m = re.fullmatch(r"C\((\d{4})\)\s?(\d{1,5})", ref.strip())
    return bool(m) and re.search(rf"C\(\s?{m.group(1)}\s?\)\s?0*{int(m.group(2))}\b", body[:5000]) is not None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--max-seconds", type=float, default=300)
    ap.add_argument("--pause", type=float, default=0.3)
    args = ap.parse_args(argv)

    engine = create_engine(database_url(), pool_pre_ping=True, pool_recycle=300)
    with engine.connect() as conn:
        due_oj = conn.execute(DUE_OJ).fetchall()
        due_doc = conn.execute(DUE_DOC, {"stages": list(ADOPTED_STAGES)}).fetchall()
    print(f"[INFO] due: {len(due_oj)} act(s) for their Official Journal text, "
          f"{len(due_doc)} for the Commission's adopted document")
    if not args.apply:
        print(f"[INFO] e.g. {[r.celex for r in due_oj[:5]]} {[r.reference for r in due_doc[:5]]}")
        print("[INFO] rehearsal: nothing fetched or written")
        return 0

    start, why = time.monotonic(), Counter()
    stored = Counter()
    answered = attempted = 0
    out_of_time = False
    for kind, rows in (("official_journal", due_oj), ("commission_document", due_doc)):
        for r in rows:
            if time.monotonic() - start > args.max_seconds:
                out_of_time = True
                break
            if kind == "official_journal":
                got = fetch_from_cellar(r.celex, ssl.create_default_context(cafile=certifi.where()))
                got = (clean(got[1]), (got[0] or "").replace("\x00", "") or None) if not isinstance(got, str) else got
            else:
                ref = c_number(r.reference, r.merged_from)
                got = fetch_commission_document(ref) if ref else "no_c_number"
            attempted += 1
            try:
                with engine.begin() as conn:
                    if isinstance(got, str):
                        why[f"{kind}:{re.sub(r'_[0-9]+$', '', got)}"] += 1
                        # An answer that says "no text" is an answer; a network fault is not.
                        answered += int(not re.search(r"Error|Timeout|URLError|Remote", got))
                        conn.execute(TRIED, {"id": r.id})
                    else:
                        answered += 1
                        txt, html = got
                        stored[kind] += conn.execute(STORE, {"id": r.id, "txt": txt, "html": html,
                                                             "src": kind}).rowcount
            except Exception as exc:  # one row's write: counted, the run goes on
                why[f"{kind}:store_{type(exc).__name__}"] += 1
                print(f"  [ERR] storing {getattr(r, 'celex', None) or r.reference}: {exc}"[:300])
            time.sleep(args.pause)

    print(f"[DONE] stored {dict(stored)}; not stored {dict(why)}; {attempted} attempted in "
          f"{time.monotonic() - start:.0f}s")
    if attempted and not answered:
        print("[FATAL] no source answered: Cellar and the document register were unreachable")
        return 1
    if out_of_time:
        left = len(due_oj) + len(due_doc) - attempted
        print(f"[SYNC_STATUS] degraded: {left} act(s) left for the next run (time budget)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
