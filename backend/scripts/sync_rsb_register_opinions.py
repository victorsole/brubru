#!/usr/bin/env python3.12
"""Every Regulatory Scrutiny Board opinion the Commission's document register lists (15 Oct 2026).

Why: /api/v2/commission/rsb-opinions held 44 opinions, the latest dated 8 August 2022, so
GovClipping's backfill since July 2024 got none. ingest_rsb_opinions.py reads the Board's
page of opinions on evaluations and fitness checks only; the opinions on impact
assessments, most of the Board's output, are SEC documents filed in the Commission's
register under the type OPIN_IMPACT_ASSESS (859 listed on 15 Oct 2026), each with its PDF:

    19.06.2026 / SEC(2026) 780 / REGULATORY SCRUTINY BOARD OPINION / {COM(2026) 780}
    Title: Impact assessment / European Product Act - update on the rules on standardisation
    Overall opinion: POSITIVE

The register lists a document on the day it is made public (usually with the proposal);
the opinion date is the date the Board printed on it, which is the row's opinion_date.
One row per SEC reference; a held opinion with its text is not read again, and a write
changes only values that differ, so last_updated moves only when something did.

    python3.12 scripts/sync_rsb_register_opinions.py --limit 5             # dry run
    python3.12 scripts/sync_rsb_register_opinions.py --all --apply         # every listed opinion
    python3.12 scripts/sync_rsb_register_opinions.py --apply               # newest 60 days (cron)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from sqlalchemy import create_engine, text  # noqa: E402

BASE = "https://ec.europa.eu/transparency/documents-register"
SEARCH = f"{BASE}/api/groupSearch"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36")
PAGE_SIZE = 50
# The payload the register UI posts; the register is strict about its shape (see
# sync_college_tentative_agendas.py), so only `types` differs.
QUERY = {"categories": [], "types": ["OPIN_IMPACT_ASSESS"], "departments": [], "language": "en",
         "keywordsSearchType": "AT_LEAST_ONE", "target": "TITLE_AND_CONTENT",
         "sortBy": "DOCUMENT_DATE_DESC", "isRegular": True}

_DATE = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b")
# The title runs to the verdict line; an opinion without a verdict (the 2025 MFF opinions,
# issued "without qualification") goes straight on to "(A) Policy context".
_TITLE = re.compile(r"Title:\s*(.+?)\s*(?:Overall\s+(?:\w+\s+)?opinion|\(A\))", re.S | re.I)
_HEAD_TITLE = re.compile(r"REGULATORY SCRUTINY BOARD OPINION\s*(.+?)\s*(?:\{|_{5,}|This opinion concerns)", re.S)
# "Overall opinion: NEGATIVE", and on a resubmission "Overall 2nd opinion: POSITIVE".
_VERDICT = re.compile(r"Overall\s+(?:\w+\s+)?opinion[^:\n]*:\s*([A-Z][A-Z ]+?)\s*(?:\n|\(|$)", re.I)
_COM = re.compile(r"COM\((\d{4})\)\s*(\d+)")
_KEY_ISSUES = re.compile(r"\(B\)\s*Key issues(?: and recommendations)?\s*(.+?)(?:\(C\)\s|\Z)", re.S | re.I)
_CONTEXT = re.compile(r"\(A\)\s*(?:Policy )?context\s*(.+?)(?:\(B\)\s|\Z)", re.S | re.I)

UPSERT = text("""
    INSERT INTO rsb_opinions (opinion_reference, title, target_initiative, target_dg, procedure_ref,
                              opinion_type, verdict, opinion_date, summary, full_text, pdf_url,
                              source_url, scraped_at, first_seen, last_updated)
    VALUES (:ref, :title, :initiative, :dg, :proc, :kind, CAST(:verdict AS rsb_verdict_enum), :day,
            :summary, :txt, :pdf, :src, now(), now(), now())
    ON CONFLICT (opinion_reference) DO UPDATE SET
        title = EXCLUDED.title, target_initiative = EXCLUDED.target_initiative,
        target_dg = EXCLUDED.target_dg,
        procedure_ref = coalesce(EXCLUDED.procedure_ref, rsb_opinions.procedure_ref),
        opinion_type = EXCLUDED.opinion_type, verdict = EXCLUDED.verdict,
        opinion_date = EXCLUDED.opinion_date, summary = EXCLUDED.summary,
        full_text = EXCLUDED.full_text, pdf_url = EXCLUDED.pdf_url, source_url = EXCLUDED.source_url
    RETURNING (xmax = 0) AS inserted""")
HELD = text("SELECT opinion_reference FROM rsb_opinions WHERE coalesce(length(full_text), 0) >= 500")
# The procedure whose OEIL file lists the proposal ("Legislative proposal published",
# reference COM(2026)0990); else the carriage holding the proposal's CELEX (a proposal's
# COM number is its CELEX number: 5 + year + PC + 4 digits).
PROCEDURE = text("""
    SELECT procedure_ref FROM (
        SELECT procedure_ref, 1 AS rank FROM oeil_procedures
         WHERE key_events @> CAST(:event AS jsonb)
        UNION ALL
        SELECT oeil_procedure_ref, 2 FROM legislative_carriages
         WHERE :celex = ANY(celex_numbers) AND oeil_procedure_ref IS NOT NULL
    ) found ORDER BY rank LIMIT 1""")


def procedure_params(com: tuple[int, int]) -> dict:
    year, number = com
    return {"event": json.dumps([{"reference": f"COM({year}){number:04d}"}]),
            "celex": f"5{year}PC{number:04d}"}


def _ctx():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:  # noqa: BLE001
        return None


def post(page: int, size: int = PAGE_SIZE, attempts: int = 4) -> dict:
    body = json.dumps(dict(QUERY, page=page)).encode()
    for n in range(attempts):
        try:
            req = urllib.request.Request(f"{SEARCH}?size={size}&page={page}", data=body, method="POST",
                                         headers={"Content-Type": "application/json",
                                                  "Accept": "application/json", "User-Agent": UA})
            with urllib.request.urlopen(req, timeout=90, context=_ctx()) as r:
                return json.load(r)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            if n == attempts - 1:
                raise
            time.sleep(10 * 2 ** n)  # the register answers 503 to quick successive pages
    return {}


def file_url(reference: str, ers_id: str) -> str:
    # Served as an attachment named <reference>.pdf (the Content-Type says JSON; the bytes are a PDF).
    return f"{BASE}/api/files/{reference}?ersIds={ers_id}"


def pdf_text(url: str) -> str | None:
    import fitz  # PyMuPDF
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}),
                                    timeout=120, context=_ctx()) as r:
            raw = r.read()
    except (urllib.error.URLError, TimeoutError):
        return None
    if raw[:4] != b"%PDF":
        return None
    with fitz.open(stream=raw, filetype="pdf") as d:
        txt = "\n".join(p.get_text() for p in d)
    return txt.replace("\x00", "").encode("utf-8", "ignore").decode("utf-8", "ignore").strip() or None


def _one_line(s: str) -> str:
    return " ".join((s or "").split())


def kind_of(title: str) -> str:
    t = (title or "").lower()
    if t.startswith("fitness check"):
        return "fitness_check"
    if t.startswith("evaluation") or "evaluation" in t.split("/")[0]:
        return "evaluation"
    return "impact_assessment"


def _verdict(v: str) -> str:
    v = _one_line(v).upper()
    if v.startswith("POSITIVE WITH RESERVATION"):
        return "positive_with_reservations"
    if v.startswith("POSITIVE"):
        return "positive"
    if v.startswith("NEGATIVE"):
        return "negative"
    return "unknown"


def verdicts_of(txt: str) -> list[str]:
    """Every verdict in the document, latest first.

    A resubmitted impact assessment's SEC document carries the Board's second opinion
    first and its first opinion after it: SEC(2026)70 opens with "Overall 2nd opinion:
    POSITIVE WITH RESERVATIONS" and ends with "Overall opinion: NEGATIVE". The first
    version of this job read only the label "Overall opinion" and so stored the superseded
    NEGATIVE on 106 opinions.
    """
    return [_verdict(m.group(1)) for m in _VERDICT.finditer(txt or "")]


def verdict_of(txt: str) -> str:
    """The Board's latest verdict on the file (the first one the document prints)."""
    found = verdicts_of(txt)
    return found[0] if found else "unknown"


def parse_opinion(txt: str) -> dict:
    """Title, initiative, opinion date, COM reference, verdict and summary from the opinion's text."""
    head = (txt or "")[:600]
    d = _DATE.search(head)
    day = None
    if d:
        try:
            day = dt.date(int(d.group(3)), int(d.group(2)), int(d.group(1)))
        except ValueError:
            day = None
    title_m = _TITLE.search(txt or "") or _HEAD_TITLE.search(txt or "")
    title = _one_line(title_m.group(1)) if title_m else None
    if title and (title.startswith("{") or len(title) < 8):
        title = None
    initiative = re.sub(r"^(impact assessment|ia)\s*/\s*", "", title or "", flags=re.I) or None
    com = _COM.search(head)
    issues = _KEY_ISSUES.search(txt or "") or _CONTEXT.search(txt or "")
    found = verdicts_of(txt)
    summary = _one_line(issues.group(1))[:2000] if issues else None
    subjects = list(dict.fromkeys(_one_line(m.group(1)).lower() for m in _TITLE.finditer(txt or "")))
    if len(subjects) > 1:
        # One SEC document can carry the opinions on several impact assessments
        # (SEC(2021)100: ten European Partnerships).
        note = (f"This document holds the Board's opinions on {len(subjects)} impact assessments; "
                f"the title, verdict and summary given are those of the first.")
    elif len(found) > 1:
        earlier = sorted(set(found[1:]), key=found[1:].index)
        note = (f"Resubmitted: the document also carries the Board's earlier opinion(s) on this file "
                f"({', '.join(v.replace('_', ' ') for v in earlier)}); the verdict given is its latest.")
    else:
        note = None
    if note:
        summary = (note + (" " + summary if summary else ""))[:2000]
    return {"day": day, "title": title, "initiative": initiative[:255] if initiative else None,
            "com": (int(com.group(1)), int(com.group(2))) if com else None,
            "verdict": found[0] if found else "unknown", "summary": summary}


def entry(doc: dict) -> dict | None:
    """The register's own fields for one listed opinion."""
    ref = (doc.get("reference") or "").replace(" ", "")
    att = next((a for a in doc.get("attachments") or [] if a.get("main")), None) or \
        next(iter(doc.get("attachments") or []), None)
    langs = (att or {}).get("linguisticVersions") or {}
    version = langs.get("en") or langs.get((att or {}).get("original")) or next(iter(langs.values()), None)
    if not ref or not version or not version.get("ersId"):
        return None
    try:
        listed = dt.date.fromisoformat(str(doc.get("date") or "")[:10])
    except ValueError:
        listed = None
    return {"ref": ref, "dg": doc.get("responsibleDepartment"), "listed": listed,
            "pdf": file_url(ref, version["ersId"]), "src": doc.get("url") or f"{BASE}/detail?ref={ref}",
            "register_title": _one_line(version.get("title") or "")}


REPARSE_ROWS = text("""SELECT opinion_reference, full_text, title, target_dg, opinion_date, pdf_url,
                              source_url, procedure_ref FROM rsb_opinions
                        WHERE opinion_reference LIKE 'SEC(%' AND coalesce(length(full_text), 0) >= 500""")


def row_from(ref: str, txt: str, dg, listed, pdf, src, register_title: str = "", conn=None) -> dict:
    """The row for one opinion, from its text and the register's fields."""
    p = parse_opinion(txt)
    title = p["title"] or register_title or f"Opinion of the Regulatory Scrutiny Board {ref}"
    proc = None
    if p["com"] and conn is not None:
        proc = conn.execute(PROCEDURE, procedure_params(p["com"])).scalar()
    return {"ref": ref, "title": title, "initiative": p["initiative"], "dg": (dg or "")[:20] or None,
            "proc": proc, "kind": kind_of(title), "verdict": p["verdict"], "day": p["day"] or listed,
            "summary": p["summary"], "txt": txt, "pdf": pdf, "src": src}


def reparse(apply: bool) -> int:
    engine = create_engine(os.environ["DATABASE_URL"].replace("postgres://", "postgresql://", 1),
                           pool_pre_ping=True)
    changed = 0
    with engine.connect() as c:
        rows = c.execute(REPARSE_ROWS).fetchall()
        new_rows = [row_from(r.opinion_reference, r.full_text, r.target_dg, r.opinion_date, r.pdf_url,
                             r.source_url, conn=c) for r in rows]
    for r, n in zip(rows, new_rows):
        n["proc"] = n["proc"] or r.procedure_ref
        if apply:
            with engine.begin() as c:
                c.execute(UPSERT, n)
        changed += 1
    print(f"[DONE] {changed} stored opinion(s) re-derived from their text" + ("" if apply else " (DRY RUN)"))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--all", action="store_true", help="every opinion the register lists")
    ap.add_argument("--days", type=int, default=60, help="register dates this far back (default 60)")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--max-seconds", type=float, default=0)
    ap.add_argument("--pause", type=float, default=0.5)
    ap.add_argument("--reparse", action="store_true",
                    help="re-derive title, verdict, date, summary and procedure from the stored text")
    args = ap.parse_args(argv)
    if args.reparse:
        return reparse(args.apply)
    since = None if args.all else dt.date.today() - dt.timedelta(days=args.days)
    deadline = time.monotonic() + args.max_seconds if args.max_seconds else None

    listed: list[dict] = []
    total = None
    skipped_pages: list[str] = []
    private = 0
    for page in range(1, 200):
        try:
            d = post(page)
            docs = d.get("documents") or []
        except urllib.error.HTTPError:
            # One page of 50 (items 351-400 on 15 Oct 2026) answers 503 every time while its
            # neighbours answer: read it as five pages of 10 and skip only the one that fails.
            d, docs = {}, []
            per = PAGE_SIZE // 10
            for sub in range((page - 1) * per + 1, page * per + 1):
                try:
                    docs += post(sub, size=10, attempts=2).get("documents") or []
                except urllib.error.HTTPError:
                    skipped_pages.append(f"items {(sub - 1) * 10 + 1}-{sub * 10}")
                time.sleep(1.5)
            if not docs:
                raise
        total = d.get("totalResults", total) if total is None else total
        entries = [entry(x) for x in docs]
        # An opinion whose file the register keeps private has no ersId: nothing to read or link.
        private += entries.count(None)
        listed += [e for e in entries if e]
        oldest = min((e["listed"] for e in listed if e["listed"]), default=None)
        if not docs or (total and page * PAGE_SIZE >= total) or (since and oldest and oldest < since):
            break
        time.sleep(1.5)
    if since:
        listed = [e for e in listed if e["listed"] is None or e["listed"] >= since]
    print(f"[INFO] register lists {total} RSB opinion(s); {len(listed)} in this run's window "
          f"({private} read had no public file)")
    if skipped_pages:
        print(f"[SYNC_STATUS] degraded: the register would not list {', '.join(skipped_pages)}")
    if not listed:
        if total:
            print("[INFO] none listed in the window")
            return 0
        print("[ERROR] the register listed no RSB opinion")
        return 1

    engine = create_engine(os.environ["DATABASE_URL"].replace("postgres://", "postgresql://", 1),
                           pool_pre_ping=True)
    with engine.connect() as c:
        held = {r[0] for r in c.execute(HELD)}
    todo = [e for e in listed if e["ref"] not in held]
    print(f"[INFO] {len(todo)} to read ({len(listed) - len(todo)} held with text)")
    if args.limit:
        todo = todo[:args.limit]
    added = updated = unread = 0
    for n, e in enumerate(todo, 1):
        if deadline and time.monotonic() > deadline:
            print(f"[INFO] time budget reached; {len(todo) - n + 1} left for the next run")
            break
        txt = pdf_text(e["pdf"])
        if not txt:
            unread += 1
            print(f"  [{e['ref']}] PDF unreadable")
            continue
        with engine.connect() as c:
            row = row_from(e["ref"], txt, e["dg"], e["listed"], e["pdf"], e["src"], e["register_title"], conn=c)
        title = row["title"]
        if not args.apply:
            if n <= 5:
                print(f"  {row['ref']} {row['day']} {row['dg']} {row['verdict']} {row['proc']} | {title[:70]}")
            continue
        with engine.begin() as c:
            ins = c.execute(UPSERT, row).scalar()
        added += bool(ins)
        updated += not ins
        time.sleep(args.pause)
    print(f"[DONE] added {added}, updated {updated}; PDF unreadable {unread}"
          + ("" if args.apply else " (DRY RUN)"))
    if todo and unread == len(todo):
        print("[ERROR] no opinion PDF could be read")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
