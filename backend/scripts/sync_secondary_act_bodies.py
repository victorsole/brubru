#!/usr/bin/env python3.12
"""Give every delegated and implementing act the text it has, every day (14 Oct 2026).

Two gaps found auditing GovClipping's /legislative/delegated-acts request:

  * No scheduled job fetched these acts' text. The last bodies were written by hand on
    1-2 October, so an act published after that stayed without text.
  * 88 delegated acts adopted by the Commission but not in the Official Journal (43
    adopted, the ones whose objection period may still run; 24 objected; 12 scrutiny
    finished; 8 withdrawn; 1 notified) had no text at all, and the endpoint composed a
    "body" from their metadata. The Commission's document register serves the text it
    adopted: C(2026)5161 gave 15 pages, about 41,000 characters.

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
SPARQL = "https://publications.europa.eu/webapi/rdf/sparql"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) BrubruIngest/1.0",
           "Referer": f"{REGISTER}/", "Accept": "application/json"}
C_NUMBER = re.compile(r"C\(\d{4}\)\s?\d{1,5}")
# Stages at which the Commission has adopted the act, so the document exists.
ADOPTED_STAGES = ("adopted", "objected", "scrutiny_finished", "withdrawn", "notified", "published")

# An act's own CELEX, in either form ('32026R1536', '32014D0029(01)', '52021XC0922(01)'),
# never a corrigendum's ('32014R1014R(03)'). Nine rows with a CELEX were matched by
# neither query until 14 Oct 2026 and counted nowhere.
OWN_CELEX = "'^[35][0-9]{4}[A-Z]{1,2}[0-9]{4}([(][0-9]{2}[)])?$'"

DUE_OJ = text(f"""
    SELECT id, celex FROM secondary_acts
     WHERE act_type IN ('delegated', 'implementing') AND celex ~ {OWN_CELEX}
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
# Dates and the PDF link only fill empty cells; the Commission document's link goes when
# the Official Journal's text replaces it, so pdf_url always points at the text served.
STORE = text("""
    UPDATE secondary_acts
       SET text_body = :txt, body_html = :html, body_source = :src, body_fetched_at = now(),
           adoption_date = coalesce(adoption_date, :adopt),
           publication_date = coalesce(publication_date, :pub),
           pdf_url = CASE WHEN :src = 'official_journal' AND body_source = 'commission_document'
                          THEN NULL ELSE coalesce(pdf_url, :pdf) END
     WHERE id = :id AND (coalesce(text_body, '') = '' OR body_source = 'commission_document')""")

# Acts we hold without a CELEX at a stage where one may exist. The register can lag the
# Official Journal by years: C(2025)885 is Regulation 2025/1190, published 18 Jun 2025,
# and RegDel still gave it no CELEX on 14 Oct 2026. Cellar records each act's C-number
# (cdm:resource_legal_manuscript_ref), so it answers that question for us.
UNRESOLVED = text("""
    SELECT id, reference, merged_from FROM secondary_acts
     WHERE act_type IN ('delegated', 'implementing') AND coalesce(celex, '') = ''
       AND status::text = ANY(:stages)""")
ASSIGN = text("""
    UPDATE secondary_acts SET celex = :celex, status = 'published', body_fetched_at = NULL
     WHERE id = :id AND coalesce(celex, '') = ''
       AND NOT EXISTS (SELECT 1 FROM secondary_acts o WHERE o.celex = :celex)""")

# Answers that settle the question for a week. Anything else (a 403, 429 or 5xx, a
# timeout, a cut connection) is a fault: it is retried on the next run, never parked for
# seven days, and enough of them make the run degraded.
SETTLED = ("not_in_register", "no_english_file", "too_short", "wrong_document", "no_c_number",
           "http_404", "register_http_404", "file_http_404")
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
    # "EN 3 EN" is the page furniture of a Commission document, not its text.
    return clean(re.sub(r"\bEN(?: \d{1,3})? EN\b", " ", clean(" ".join((p.extract_text() or "") for p in pages))))


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
    pdf = f"{REGISTER}/api/files/{q}?ersIds={files[0]}"
    for ers in files:
        try:
            parts.append(pdf_text(_get(f"{REGISTER}/api/files/{q}?ersIds={ers}", timeout=120)))
        except urllib.error.HTTPError as e:
            return f"file_http_{e.code}"
        except Exception as e:
            return f"file_{type(e).__name__}"
        time.sleep(0.3)
    # One running text: separate blocks per file left the API's paragraph split with two
    # blocks, so an act with annexes became two 60,000-character paragraphs.
    body = clean(" ".join(p for p in parts if p))
    if len(body) < MIN_CHARS:
        return f"too_short_{len(body)}"
    # The document prints its own number on its cover ("C(2026) 7021 final"): a file that
    # does not is not this act's, whatever the register filed it under.
    if not names_itself(body, ref):
        return "wrong_document"
    return body, pdf


def names_itself(body: str, ref: str) -> bool:
    """The cover reads "C(2026) 7021 final", and no "draft" comes before it.

    A number cited further down (an act amending Decision C(2021) 1051) is not the cover,
    and a draft that quotes the number is not the adopted act.
    """
    m = re.fullmatch(r"C\((\d{4})\)\s?(\d{1,5})", ref.strip())
    if not m:
        return False
    head = body[:3000]
    cover = re.search(rf"C\s?\(\s?{m.group(1)}\s?\)\s?0*{int(m.group(2))}\s+final\b", head)
    return bool(cover) and not re.search(r"\bdraft\b", head[:cover.start()], re.I)


_COVER_DATE = re.compile(r"Brussels,\s+(\d{1,2})\.(\d{1,2})\.(\d{4})")
_OJ_HEADER = re.compile(r"L series \d{4}/\d+ (\d{1,2})\.(\d{1,2})\.(\d{4})")


def dated(pattern: re.Pattern, txt: str):
    """The first date the pattern finds in the opening of a text, or None."""
    from datetime import date
    m = pattern.search(txt[:600])
    try:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1))) if m else None
    except ValueError:
        return None


def resolve_celex(engine) -> dict:
    """Give acts held without a CELEX the one Cellar records for their C-number.

    One query per year of the C-numbers in question (about a second each). A CELEX
    another row already holds is not assigned: the act is held twice, and that is
    reported for a person to merge, never resolved by deleting a row here.
    """
    with engine.connect() as conn:
        rows = conn.execute(UNRESOLVED, {"stages": list(ADOPTED_STAGES)}).fetchall()
    wanted: dict = {}
    for r in rows:
        ref = c_number(r.reference, r.merged_from)
        m = re.fullmatch(r"C\((\d{4})\)\s?(\d{1,5})", ref or "")
        if m:
            wanted.setdefault((m.group(1), int(m.group(2))), []).append(r.id)
    found: dict = {}
    failed_years: list[str] = []
    for year in sorted({y for y, _ in wanted}):
        q = ("PREFIX cdm: <http://publications.europa.eu/ontology/cdm#> SELECT ?m ?celex WHERE { "
             "?w cdm:resource_legal_manuscript_ref ?m . "
             f'FILTER(STRSTARTS(STR(?m), "C({year})")) ?w cdm:resource_legal_id_celex ?celex . '
             'FILTER(REGEX(STR(?celex), "^3[0-9]{4}[A-Z][0-9]{4}$")) }')
        req = urllib.request.Request(SPARQL, data=urllib.parse.urlencode({"query": q}).encode(),
                                     headers={"Accept": "application/sparql-results+json"})
        # One slow year (Cellar timed out on one on 14 Oct 2026) skips that year, not all.
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                bindings = json.loads(resp.read())["results"]["bindings"]
        except Exception as exc:
            failed_years.append(f"{year} ({type(exc).__name__})")
            wanted = {k: v for k, v in wanted.items() if k[0] != year}
            continue
        for b in bindings:
            m = re.match(r"C\((\d{4})\)\s?0*(\d{1,5})\s*(/|$)", b["m"]["value"])
            if m:
                found.setdefault((m.group(1), int(m.group(2))), set()).add(b["celex"]["value"])
    out = {"asked": len(wanted), "assigned": 0, "ambiguous": 0, "held_twice": [],
           "failed_years": failed_years}
    with engine.begin() as conn:
        for key, ids in wanted.items():
            celexes = found.get(key, set())
            if len(celexes) != 1 or len(ids) != 1:
                out["ambiguous"] += int(len(celexes) > 1 or len(ids) > 1)
                continue
            celex = celexes.pop()
            if conn.execute(ASSIGN, {"id": ids[0], "celex": celex}).rowcount:
                out["assigned"] += 1
            else:
                out["held_twice"].append(f"C({key[0]}){key[1]}={celex}")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--max-seconds", type=float, default=300)
    ap.add_argument("--pause", type=float, default=0.3)
    args = ap.parse_args(argv)

    engine = create_engine(database_url(), pool_pre_ping=True, pool_recycle=300)
    resolved = None
    if args.apply:
        try:
            resolved = resolve_celex(engine)
            print(f"[INFO] Cellar: {resolved['assigned']} act(s) held without a CELEX are in the Official "
                  f"Journal and took theirs ({resolved['asked']} asked, {resolved['ambiguous']} ambiguous)")
            if resolved["held_twice"]:
                print(f"[WARN] {len(resolved['held_twice'])} act(s) held twice, under a C-number and a CELEX: "
                      + ", ".join(resolved["held_twice"][:20]))
        except Exception as exc:
            resolved = {"error": f"{type(exc).__name__}: {exc}"}
            print(f"[WARN] Cellar lookup failed: {resolved['error']}")
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
    answered = attempted = faults = 0
    out_of_time = False
    for kind, rows in (("official_journal", due_oj), ("commission_document", due_doc)):
        for r in rows:
            if time.monotonic() - start > args.max_seconds:
                out_of_time = True
                break
            if kind == "official_journal":
                got = fetch_from_cellar(r.celex, ssl.create_default_context(cafile=certifi.where()))
                if not isinstance(got, str):
                    txt = clean(got[1])
                    got = {"txt": txt, "html": (got[0] or "").replace("\x00", "") or None,
                           "pub": dated(_OJ_HEADER, txt), "adopt": None, "pdf": None}
            else:
                ref = c_number(r.reference, r.merged_from)
                got = fetch_commission_document(ref) if ref else "no_c_number"
                if not isinstance(got, str):
                    got = {"txt": got[0], "html": None, "pub": None,
                           "adopt": dated(_COVER_DATE, got[0]), "pdf": got[1]}
            attempted += 1
            try:
                with engine.begin() as conn:
                    if isinstance(got, str):
                        marker = re.sub(r"_[0-9]+$", "", got) if got.startswith("too_short") else got
                        why[f"{kind}:{marker}"] += 1
                        if marker in SETTLED:
                            answered += 1
                            conn.execute(TRIED, {"id": r.id})
                        else:
                            faults += 1
                    else:
                        answered += 1
                        stored[kind] += conn.execute(STORE, {"id": r.id, "src": kind, **got}).rowcount
            except Exception as exc:  # one row's write: counted, the run goes on
                why[f"{kind}:store_{type(exc).__name__}"] += 1
                print(f"  [ERR] storing {getattr(r, 'celex', None) or r.reference}: {exc}"[:300])
            time.sleep(args.pause)

    print(f"[DONE] stored {dict(stored)}; not stored {dict(why)}; {attempted} attempted in "
          f"{time.monotonic() - start:.0f}s")
    if attempted and not answered:
        print("[FATAL] no source answered: Cellar and the document register were unreachable")
        return 1
    reasons = []
    if out_of_time:
        reasons.append(f"{len(due_oj) + len(due_doc) - attempted} act(s) left for the next run (time budget)")
    if faults and faults > 0.2 * attempted:
        reasons.append(f"{faults} of {attempted} fetch(es) failed (blocked, rate-limited or cut); retried next run")
    if resolved and resolved.get("error"):
        reasons.append(f"Cellar CELEX lookup failed ({resolved['error']})")
    if resolved and resolved.get("failed_years"):
        reasons.append(f"Cellar did not answer for C-numbers of {', '.join(resolved['failed_years'])}")
    if resolved and resolved.get("held_twice"):
        reasons.append(f"{len(resolved['held_twice'])} act(s) held twice, to merge")
    if reasons:
        print(f"[SYNC_STATUS] degraded: {'; '.join(reasons)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
