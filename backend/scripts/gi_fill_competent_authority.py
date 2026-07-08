"""
Fill gi_details.competent_authority from the GIView technical documents.

The authority is stated in the tech doc, but the FORMAT varies and it lives in more than
one attachment:
  - spirit drinks: a "Contact details / Applicant name and title" block,
  - food PDO/PGI: the control body ("Consorzio ...", "Consejo Regulador ...", "Groupement
    ...", "autorité compétente ...", "zuständige Behörde ..."),
  - wine single-documents: usually OMIT it (nothing to extract).

So we fetch BOTH the summary sheet AND the first publications attachment, run pdftotext,
and try a set of multilingual anchors. Idempotent: only fills NULL rows; self-resuming.
competent_authority is jsonb (a scalar string).

  python3.12 scripts/gi_fill_competent_authority.py --dry-run --limit 60
  python3.12 scripts/gi_fill_competent_authority.py            # full crawl (background)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import psycopg2
import requests
from core.config import settings
from gi_geo_annex_fetch import ROSTER, Browser, pdf_text

# ordered anchors; the first clean capture wins
_ANCHORS = [
    re.compile(r"Applicant name and title\s*\n\s*Applicant name and title\s+([^\n]{3,90})", re.I),
    re.compile(r"name and address of the (?:competent authorit\w+|applicant|group)[^\n]*\n+\s*([A-ZÀ-Ú][^\n]{3,90})", re.I),
    re.compile(r"\b(Consorzio\s+(?:di\s+)?[Tt]utela[^\n,;.]{2,70})"),
    re.compile(r"\b(Consejo\s+Regulador[^\n,;.]{2,70})"),
    re.compile(r"\b(Agrupaci[óo]n[^\n,;.]{2,70})"),
    re.compile(r"\b(Groupement[^\n,;.]{2,70})"),
    re.compile(r"autorit[ée]s?\s+comp[ée]tentes?\s*:?\s*\n?\s*([A-ZÀ-Ú][^\n]{3,90})", re.I),
    re.compile(r"autoridad(?:es)?\s+competentes?\s*:?\s*\n?\s*([A-ZÀ-Ú][^\n]{3,90})", re.I),
    re.compile(r"autorit[àa]\s+competente\s*:?\s*\n?\s*([A-ZÀ-Ú][^\n]{3,90})", re.I),
    re.compile(r"zust[äa]ndige\s+Beh[öo]rde\s*:?\s*\n?\s*([A-ZÀ-Ú][^\n]{3,90})", re.I),
]
_JUNK = re.compile(r"^(the|le|la|el|il|der|die|das|n/?a|none|\W+)$", re.I)


def extract_authority(txt: str) -> str | None:
    for pat in _ANCHORS:
        m = pat.search(txt)
        if not m:
            continue
        val = " ".join(m.group(1).split()).strip(" .,:;-")
        if len(val) >= 4 and not _JUNK.match(val):
            return val[:200]
    return None


def attachments(entry) -> list[str]:
    """summary sheet first, then numeric publications attachments (the fuller docs)."""
    out = []
    s = (entry.get("summarySheets") or [{}])[0].get("uri")
    if s:
        out.append(str(s))
    for p in (entry.get("publications") or []):
        u = str(p.get("uri", ""))
        if u.isdigit():
            out.append(u)
    return out[:3]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    roster = requests.get(ROSTER, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"}, timeout=120).json()
    by_fn = {x["fileNumber"]: x for x in roster if x.get("fileNumber")}

    c = psycopg2.connect(settings.DATABASE_URL, connect_timeout=20); c.autocommit = True
    cur = c.cursor()
    cur.execute("""SELECT file_number, protected_name FROM gi_details
        WHERE competent_authority IS NULL ORDER BY protected_name"""
        + (f" LIMIT {a.limit}" if a.limit else ""))
    rows = cur.fetchall()
    print(f"[ca] targets: {len(rows)}", flush=True)

    stats = {"filled": 0, "no_attach": 0, "no_pdf": 0, "no_anchor": 0}
    with Browser() as br:
        for fn, nm in rows:
            atts = attachments(by_fn.get(fn, {}))
            if not atts:
                stats["no_attach"] += 1; continue
            authority = None
            fetched = False
            for aid in atts:
                data = br.pdf(aid)
                if not data:
                    continue
                fetched = True
                authority = extract_authority(pdf_text(data))
                if authority:
                    break
            if not fetched:
                stats["no_pdf"] += 1; continue
            if not authority:
                stats["no_anchor"] += 1; continue
            stats["filled"] += 1
            if a.dry_run:
                print(f"  [{','.join(str(x) for x in [])}] {nm[:30]:30} -> {authority}")
            else:
                cur.execute("UPDATE gi_details SET competent_authority=%s::jsonb WHERE file_number=%s",
                            (json.dumps(authority), fn))
                if stats["filled"] % 25 == 0:
                    print(f"  ...{stats['filled']} filled", flush=True)
    print(f"[ca] {stats}")
    c.close()


if __name__ == "__main__":
    main()
