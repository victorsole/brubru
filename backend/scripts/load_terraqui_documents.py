"""Load the LIFE DPP-TEX project documents into My Documents.

Applies to both Joana's real account and the demo clone.

Each row carries the extracted text in `content`, which is what Chat reads, and
include_in_ai_context is TRUE. Her existing upload had it FALSE, so her own
compliance document was sitting in My Documents without ever reaching an answer.

The PDFs themselves live in backend/data/terraqui_docs/ (gitignored, since the
directory is data/). Two were published as PDFs; two are Playwright renders of
the project pages, because Victor asked for PDF versions of them.

Idempotent on (user_id, title).
"""

from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "backend"))

from dotenv import load_dotenv

load_dotenv(project_root / ".env")

from sqlalchemy import text

from core.database import SessionLocal

DOCS_DIR = project_root / "backend/data/terraqui_docs"

ACCOUNTS = {
    "jcastella@terraqui.com": "e6337400-6c0c-4842-9007-26db3f59a3fb",
    "joana-demo@demo.invalid": "96788e72-5890-4b2f-bd35-00bedc98e721",
}

# stem -> (title, source_url, why it is in her Documents)
DOCUMENTS = {
    "life_2025_sap_env_call_fiche": (
        "LIFE 2025 SAP-ENV call fiche (the call LIFE DPP-TEX was funded under)",
        "https://ec.europa.eu/info/funding-tenders/opportunities/docs/2021-2027/"
        "life/wp-call/2025/call-fiche_life-2025-sap-env_en.pdf",
        "The call conditions, award criteria and reporting obligations the "
        "project is bound by.",
    ),
    "blueroom_life_dpp_tex": (
        "LIFE DPP-TEX project page (Blue Room Innovation, coordinator)",
        "https://www.blueroominnovation.com/en/life-dpp-tex/",
        "The coordinator's own description of the project, its consortium and "
        "the CircularPass platform.",
    ),
    "terraqui_life_dpp_tex": (
        "LIFE DPP-TEX: passaport digital de producte per al sector textil (Terraqui)",
        "https://www.terraqui.com/ca/actualidad/"
        "life-dpp-tex-passaport-digital-de-producte-per-al-sector-textil/",
        "Terraqui's own article on the project, in Catalan, including its "
        "regulatory role.",
    ),
}

_INSERT = text("""
    INSERT INTO user_documents (
        id, user_id, document_type, title, content, doc_metadata, tags,
        original_filename, file_content_type, file_size_bytes,
        is_private, include_in_ai_context, created_at, updated_at
    ) VALUES (
        :id, :user_id, 'uploaded', :title, :content, CAST(:meta AS jsonb), :tags,
        :filename, 'application/pdf', :size,
        true, true, now(), now()
    )
""")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    payloads = []
    for stem, (title, url, why) in DOCUMENTS.items():
        txt_file = DOCS_DIR / f"{stem}.txt"
        pdf_file = DOCS_DIR / f"{stem}.pdf"
        if not txt_file.exists():
            print(f"[WARN] {stem}: no extracted text, skipped")
            continue
        body = txt_file.read_text(encoding="utf-8").strip()
        header = f"{title}\n\nSource: {url}\nWhy this is here: {why}\n\n---\n\n"
        payloads.append({
            "stem": stem, "title": title, "url": url,
            "content": header + body,
            "filename": pdf_file.name if pdf_file.exists() else f"{stem}.txt",
            "pdf_bytes": pdf_file.stat().st_size if pdf_file.exists() else 0,
        })

    print(f"=== {len(payloads)} document(s) ready ===")
    for p in payloads:
        print(f"  {p['title'][:62]}")
        print(f"     {len(p['content']):>8,} chars of text | PDF {p['pdf_bytes']:>9,} bytes")

    db = SessionLocal()
    rc = 0
    try:
        for email, uid in ACCOUNTS.items():
            print(f"\n=== {email} ===")
            for p in payloads:
                exists = db.execute(
                    text("SELECT count(*) FROM user_documents "
                         "WHERE user_id = :u AND title = :t"),
                    {"u": uid, "t": p["title"]},
                ).scalar()
                if exists:
                    print(f"  [OK] already present: {p['title'][:52]}")
                    continue
                print(f"  [ADD] {p['title'][:58]}")
                if args.apply:
                    db.execute(_INSERT, {
                        "id": str(uuid.uuid4()), "user_id": uid,
                        "title": p["title"], "content": p["content"],
                        # there is no source_url column; the provenance lives in
                        # doc_metadata and is repeated in the content header so a
                        # reader (and Chat) always sees where it came from
                        "meta": __import__("json").dumps(
                            {"source_url": p["url"], "project": "LIFE DPP-TEX",
                             "added_by": "load_terraqui_documents.py"}),
                        "tags": ["LIFE DPP-TEX", "ecodesign", "textiles"],
                        "filename": p["filename"], "size": p["pdf_bytes"],
                    })

            # her existing upload was invisible to Chat; turn it on
            n = db.execute(
                text("SELECT count(*) FROM user_documents "
                     "WHERE user_id = :u AND include_in_ai_context = false"),
                {"u": uid},
            ).scalar()
            if n:
                print(f"  [FIX] {n} existing document(s) had include_in_ai_context=false")
                if args.apply:
                    db.execute(
                        text("UPDATE user_documents SET include_in_ai_context = true, "
                             "updated_at = now() WHERE user_id = :u "
                             "AND include_in_ai_context = false"),
                        {"u": uid},
                    )

        if args.apply:
            db.commit()
            print("\n=== verification ===")
            for email, uid in ACCOUNTS.items():
                rows = db.execute(
                    text("SELECT title, length(content) AS n, include_in_ai_context "
                         "FROM user_documents WHERE user_id = :u ORDER BY created_at"),
                    {"u": uid},
                ).fetchall()
                print(f"  {email}: {len(rows)} document(s)")
                for r in rows:
                    flag = "in AI context" if r.include_in_ai_context else "NOT in AI context"
                    print(f"     {r.title[:56]:<58} {r.n or 0:>8,} ch  {flag}")
                if any(not r.include_in_ai_context for r in rows):
                    rc = 1
        else:
            print("\n[DRY-RUN] nothing written")
        return rc
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
