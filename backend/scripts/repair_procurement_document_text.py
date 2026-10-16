#!/usr/bin/env python3.12
"""Two repairs on procurement_documents (API audit, 16 Oct 2026, step 2 on ECHA):

1. Non-breaking spaces in the extracted text: 540 files across the seven bodies carried
   U+00A0, and 23 pypdf's "Â\\xa0" rendering of it ("NUTS code Â  FI181"). The extractor's
   _clean now turns both into spaces; the stored texts are cleaned the same way, and
   body_html rebuilt from the cleaned text, without re-downloading anything.
2. ECHA file language: 589 of 625 ECHA files are named "<name>_en.pdf" and carried no
   language. The lister now reads the suffix; the stored rows get it here.

Backup first; one row per transaction. Dry run by default; --apply writes.

    python3.12 -m backend.scripts.repair_procurement_document_text [--apply]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from datetime import datetime, timezone

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "backend"))
sys.path.insert(0, str(_REPO_ROOT))

from sqlalchemy import text  # noqa: E402

from core.database import engine  # noqa: E402
from services.documents import text_extract as te  # noqa: E402
from services.scrapers.agency_procurement import _EU_LANGS  # noqa: E402

BACKUPS = _REPO_ROOT / "backend" / "data" / "backups"

_TEXT_ROWS = text("SELECT id, body_code, file_name, body_txt FROM procurement_documents "
                  "WHERE body_txt LIKE '%' || chr(160) || '%' OR body_txt LIKE '%Â%' ORDER BY id")
_LANG_ROWS = text("SELECT id, file_name FROM procurement_documents WHERE body_code = 'echa' "
                  "AND language IS NULL AND file_name ~ '_[a-z]{2}\\.[A-Za-z0-9]+$' ORDER BY id")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true", help="write (default: dry run)")
    a = p.parse_args()
    with engine.connect() as c:
        trows = [dict(r._mapping) for r in c.execute(_TEXT_ROWS)]
        lrows = [dict(r._mapping) for r in c.execute(_LANG_ROWS)]
    text_plan = []
    for r in trows:
        new = te._clean(r["body_txt"])
        if new != r["body_txt"]:
            text_plan.append((r["id"], new))
    lang_plan = []
    for r in lrows:
        m = re.search(r"_([a-z]{2})\.[A-Za-z0-9]{2,5}$", (r["file_name"] or "").lower())
        if m and m.group(1) in _EU_LANGS:
            lang_plan.append((r["id"], m.group(1)))
    bodies = {}
    for r in trows:
        bodies[r["body_code"]] = bodies.get(r["body_code"], 0) + 1
    print(f"[INFO] text: {len(trows)} rows carry a non-breaking space or Â ({bodies}); {len(text_plan)} change")
    print(f"[INFO] language: {len(lrows)} ECHA rows have a language suffix; {len(lang_plan)} get a language "
          f"({dict((l, sum(1 for _i, x in lang_plan if x == l)) for l in {x for _i, x in lang_plan})})")
    if not text_plan and not lang_plan:
        return 0
    BACKUPS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y_%m_%d_%H%M")
    backup = BACKUPS / f"procurement_documents_before_text_repair_{stamp}.json"
    backup.write_text(json.dumps({"text": [{"id": i, "body_txt": t} for i, t in
                                           ((r["id"], r["body_txt"]) for r in trows)],
                                  "language": [str(r["id"]) for r in lrows]}, default=str))
    print(f"[INFO] backup: {backup}")
    if not a.apply:
        print("[INFO] dry run; re-run with --apply to write")
        return 0
    w_text = w_lang = 0
    for i, new in text_plan:
        with engine.begin() as c:   # one row per transaction
            w_text += c.execute(text("UPDATE procurement_documents SET body_txt = :t, body_html = :h "
                                     "WHERE id = :id"), {"t": new, "h": te.to_html(new), "id": i}).rowcount
    for i, lang in lang_plan:
        with engine.begin() as c:
            w_lang += c.execute(text("UPDATE procurement_documents SET language = :l "
                                     "WHERE id = :id AND language IS NULL"), {"l": lang, "id": i}).rowcount
    with engine.connect() as c:
        left_t = c.execute(_TEXT_ROWS).fetchall()
        left_l = c.execute(_LANG_ROWS).fetchall()
    print(f"[OK] text: {w_text} of {len(text_plan)} rewritten, still flagged {len(left_t)}; "
          f"language: {w_lang} of {len(lang_plan)} set, still missing with a suffix {len(left_l)}")
    return 0 if w_text == len(text_plan) and w_lang == len(lang_plan) else 1


if __name__ == "__main__":
    sys.exit(main())
