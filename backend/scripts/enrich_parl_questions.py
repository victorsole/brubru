"""
Enrich parliamentary_questions with author MEP ids + CELEX/procedure refs.

For each question we resolve the EP Open Data document record (by the id embedded
in its doceo source_url, e.g. E-10-2026-001670) and read `creator` +
`workHadParticipation` -> author MEP ids. The deterministic MEP profile URL is
built later in the API from id + name (the link the doceo page hides). We also
regex CELEX + OEIL procedure refs out of the question text so questions deep-link
to My Tracked Files.

EP Open Data API only (no Anthropic). Idempotent; ordered most-recent first so a
capped run enriches what users see soonest.

    python3.12 -m scripts.enrich_parl_questions --limit 800
    python3.12 -m scripts.enrich_parl_questions --since 2026-01-01
"""

import argparse
import logging
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
logging.disable(logging.INFO)

import httpx
from dotenv import load_dotenv
load_dotenv()

from core.database import SessionLocal
from models.w4_entities import ParliamentaryQuestion

API = "https://data.europarl.europa.eu/api/v2/documents/{doc_id}?format=application/ld%2Bjson&language=en"
_ID_RE = re.compile(r"/document/([A-Z]+-\d+-\d{4}-\d{6})", re.I)
_CELEX_RE = re.compile(r"\b[1-9]\d{4}[A-Z]{1,2}\d{4}\b")
_PROC_RE = re.compile(r"\b\d{4}/\d{4}\([A-Z]{2,4}\)")
_PERSON_RE = re.compile(r"person/(\d+)")
_UA = "Brubru/1.0 (EU Policy Assistant; https://brubru.beresol.eu)"


def _doc_id(source_url: str):
    m = _ID_RE.search(source_url or "")
    return m.group(1) if m else None


def _person_ids(obj) -> list:
    """All person ids referenced in creator + workHadParticipation (lead + co-authors)."""
    ids = []
    for v in (_PERSON_RE.findall(str(obj.get("creator", "")))
              + _PERSON_RE.findall(str(obj.get("workHadParticipation", "")))):
        if v not in ids:
            ids.append(v)
    return ids


def run(limit, since):
    db = SessionLocal()
    q = db.query(ParliamentaryQuestion)
    if since:
        q = q.filter(ParliamentaryQuestion.submitted_date >= since)
    q = q.order_by(ParliamentaryQuestion.submitted_date.desc().nullslast())
    if limit:
        q = q.limit(limit)
    rows = q.all()
    print(f"[enrich] {len(rows)} questions to process")

    mep_ok = celex_ok = miss = err = 0
    with httpx.Client(headers={"User-Agent": _UA, "Accept": "application/ld+json"},
                      timeout=30, follow_redirects=True) as client:
        for i, r in enumerate(rows, 1):
            # CELEX / procedure from text (free, no API)
            text = f"{r.subject or ''}\n{r.text_question or ''}\n{r.text_answer or ''}"
            celex = sorted(set(_CELEX_RE.findall(text)))
            procs = _PROC_RE.findall(text)
            if celex and not (r.related_celex or []):
                r.related_celex = celex; celex_ok += 1
            if procs and not r.procedure_ref:
                r.procedure_ref = procs[0]

            # Author MEP ids from Open Data (only if missing)
            if not (r.asking_mep_ids or []):
                doc_id = _doc_id(r.source_url)
                if doc_id:
                    try:
                        resp = client.get(API.format(doc_id=doc_id))
                        if resp.status_code == 200:
                            data = resp.json().get("data") or [{}]
                            ids = _person_ids(data[0])
                            if ids:
                                r.asking_mep_ids = ids; mep_ok += 1
                            else:
                                miss += 1
                        else:
                            miss += 1
                    except Exception:
                        err += 1
                    time.sleep(0.05)
            if i % 100 == 0:
                db.commit()
                print(f"  {i}/{len(rows)}  mep_ids+={mep_ok} celex+={celex_ok} miss={miss} err={err}")
        db.commit()
    print(f"[enrich] DONE mep_ids+={mep_ok} celex+={celex_ok} miss={miss} err={err}")
    db.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=800)
    ap.add_argument("--since")
    a = ap.parse_args()
    run(a.limit, a.since)
