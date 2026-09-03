"""
Seed FerrMed's My EU Bubble Documents tab with their own publications.

Downloads each PDF from ferrmed.com, extracts text with pypdf, and inserts a
user_documents row scoped to bureau@ferrmed.com with include_in_ai_context=True
so Brubru chat can cite the FerrMed publications when answering questions.

Origin pages (per Victor 18 May 2026):
  - /imagining-the-future-of-the-european-great-axis-of-rail-freight/
  - /related-studies/
  - /working-groups/

Usage:
    cd backend && python3.12 scripts/seed_ferrmed_documents.py            # dry-run
    cd backend && python3.12 scripts/seed_ferrmed_documents.py --apply    # write DB

Idempotent: re-runs skip documents whose source_url is already stored on a
row for the FerrMed user.
"""

from __future__ import annotations

import pathlib

# Repo root derived from this file's location, so a repo move cannot break the script.
_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])


import argparse
import io
import logging
import sys
import uuid
from typing import Optional

sys.path.insert(0, f"{_REPO_ROOT}/backend")
sys.path.insert(0, _REPO_ROOT)

import httpx
from pypdf import PdfReader
from sqlalchemy import text

from core.database import SessionLocal, engine

engine.echo = False
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)
for noisy in ("sqlalchemy.engine", "sqlalchemy.engine.Engine", "sqlalchemy.pool"):
    logging.getLogger(noisy).setLevel(logging.WARNING)


FERRMED_USER_EMAIL = "bureau@ferrmed.com"


# Curated FerrMed publications. `source_page` lets us trace each back to the
# /imagining, /related-studies or /working-groups page Victor flagged.
DOCS = [
    # --- /imagining-the-future-of-the-european-great-axis-of-rail-freight/
    {
        "title": "FERRMED — Key Early Conclusions",
        "year": 2019,
        "language": "en",
        "source_url": "http://ferrmed.com/wp-content/uploads/2023/05/Key-early-conclusions.docx_.pdf",
        "source_page": "/imagining-the-future-of-the-european-great-axis-of-rail-freight/",
        "tags": ["ferrmed-publication", "modal-shift", "rail-freight"],
        "policy_areas": ["Transport"],
    },
    {
        "title": "FERRMED Global Study Book",
        "year": 2009,
        "language": "en",
        "source_url": "http://ferrmed.com/wp-content/uploads/2023/05/FERRMED-GLOBAL-STUDY-BOOK.pdf",
        "source_page": "/imagining-the-future-of-the-european-great-axis-of-rail-freight/",
        "tags": ["ferrmed-publication", "great-axis", "rail-freight", "ten-t"],
        "policy_areas": ["Transport"],
    },
    {
        "title": "FERRMED Global Study Book — Version 2",
        "year": 2009,
        "language": "en",
        "source_url": "http://ferrmed.com/wp-content/uploads/2023/05/FERRMED-GLOBAL-STUDY-BOOK_2.pdf",
        "source_page": "/imagining-the-future-of-the-european-great-axis-of-rail-freight/",
        "tags": ["ferrmed-publication", "great-axis", "rail-freight"],
        "policy_areas": ["Transport"],
    },
    {
        "title": "FERRMED Locomotive Concept Study",
        "year": 2018,
        "language": "en",
        "source_url": "http://ferrmed.com/wp-content/uploads/2023/05/FERRMED-LOCOMOTIVE-CONCEPT-STUDY_1_2.pdf",
        "source_page": "/imagining-the-future-of-the-european-great-axis-of-rail-freight/",
        "tags": ["ferrmed-publication", "rolling-stock", "ertms", "interoperability"],
        "policy_areas": ["Transport"],
    },
    {
        "title": "FERRMED EU Wagon Concept — Final Study",
        "year": 2010,
        "language": "en",
        "source_url": "http://ferrmed.com/wp-content/uploads/2023/05/FERRMED_WagonStudy_FINAL_May_2010-Copy_3.pdf",
        "source_page": "/imagining-the-future-of-the-european-great-axis-of-rail-freight/",
        "tags": ["ferrmed-publication", "rolling-stock", "wagons"],
        "policy_areas": ["Transport"],
    },
    # --- /related-studies/
    {
        "title": "FERRMED — Report Regarding the Mediterranean Corridor",
        "year": 2015,
        "language": "en",
        "source_url": "http://ferrmed.com/wp-content/uploads/2023/06/Report-Regarding-Mediterranean-Corridor.pdf",
        "source_page": "/related-studies/",
        "tags": ["ferrmed-publication", "mediterranean-corridor", "ten-t", "infrastructure"],
        "policy_areas": ["Transport"],
    },
    # --- /working-groups/ — the Drupal-era /sites/default/files/* URLs that
    # FerrMed's page still links to all return 404. The CMS migration to
    # WordPress did not bring those PDFs across. Not seeded.
]


def get_user_id(db) -> Optional[str]:
    row = db.execute(
        text("SELECT id::text FROM users WHERE email = :e"), {"e": FERRMED_USER_EMAIL}
    ).first()
    return row[0] if row else None


def already_seeded(db, user_id: str, source_url: str) -> bool:
    row = db.execute(
        text(
            """
            SELECT 1 FROM user_documents
            WHERE user_id = CAST(:u AS uuid)
              AND doc_metadata ->> 'source_url' = :url
            LIMIT 1
            """
        ),
        {"u": user_id, "url": source_url},
    ).first()
    return bool(row)


def download_and_extract(source_url: str, timeout: float = 60.0) -> tuple[bytes, str]:
    """Return (raw_bytes, extracted_text). Raises on failure."""
    with httpx.Client(timeout=timeout, follow_redirects=True, headers={"User-Agent": "Brubru/1.0"}) as client:
        r = client.get(source_url)
        r.raise_for_status()
        raw = r.content

    text_parts: list[str] = []
    # First attempt: pypdf in lenient (strict=False) mode.
    try:
        reader = PdfReader(io.BytesIO(raw), strict=False)
        for page in reader.pages:
            try:
                t = page.extract_text() or ""
            except Exception:
                t = ""
            if t.strip():
                text_parts.append(t)
    except Exception as e:
        logger.warning(f"  pypdf lenient failed on {source_url}: {e}")

    extracted = "\n\n".join(text_parts).strip()
    if extracted:
        return raw, extracted

    # Fallback: pdfminer.six is much more forgiving with malformed PDFs
    # (older FerrMed scans hit "startxref not found" on pypdf).
    try:
        from pdfminer.high_level import extract_text as pdfminer_extract  # type: ignore
        extracted = (pdfminer_extract(io.BytesIO(raw)) or "").strip()
        if extracted:
            logger.info("  (extracted via pdfminer fallback)")
            return raw, extracted
    except ImportError:
        logger.debug("  pdfminer.six not installed; skipping fallback")
    except Exception as e:
        logger.warning(f"  pdfminer fallback failed: {e}")

    return raw, ""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Write to DB. Default is dry-run.")
    parser.add_argument("--limit", type=int, default=0, help="Only process the first N docs (testing).")
    args = parser.parse_args()

    mode = "APPLY" if args.apply else "DRY-RUN (use --apply to write)"
    logger.info("=" * 80)
    logger.info(f"FerrMed Documents seed — {mode}")
    logger.info("=" * 80)

    db = SessionLocal()
    try:
        user_id = get_user_id(db)
        if not user_id:
            logger.error(f"[FAIL] User {FERRMED_USER_EMAIL} not found. Run seed_ferrmed_demo.py --apply first.")
            sys.exit(1)
        logger.info(f"FerrMed user_id: {user_id}\n")

        targets = DOCS[: args.limit] if args.limit else DOCS
        created = 0
        skipped = 0
        failed: list[str] = []

        for i, spec in enumerate(targets, 1):
            label = f"[{i:2}/{len(targets)}] {spec['title']}"
            logger.info(label)

            if already_seeded(db, user_id, spec["source_url"]):
                logger.info(f"  [SKIP] Already in DB for this user.")
                skipped += 1
                continue

            try:
                raw, extracted = download_and_extract(spec["source_url"])
            except Exception as e:
                logger.warning(f"  [FAIL] {type(e).__name__}: {e}")
                failed.append(spec["source_url"])
                continue

            words = len(extracted.split())
            logger.info(f"  fetched {len(raw):>9,} bytes  extracted {words:>6,} words")

            if not args.apply:
                logger.info(f"  [DRY] would insert user_documents row.")
                created += 1
                continue

            # Truncate to schema limit (column allows full text but cap at 100k as the
            # /api/documents/upload path does — also bounds AI-context size).
            content_for_db = extracted[:100_000] if extracted else None
            original_filename = spec["source_url"].rsplit("/", 1)[-1]

            db.execute(
                text(
                    """
                    INSERT INTO user_documents (
                        id, user_id, document_type, title, content,
                        original_filename, file_content_type, file_size_bytes,
                        include_in_ai_context, is_private,
                        policy_areas, tags, doc_metadata,
                        version, view_count, is_featured,
                        created_at, updated_at
                    ) VALUES (
                        CAST(:id AS uuid), CAST(:u AS uuid), 'uploaded', :title, :content,
                        :fn, 'application/pdf', :size,
                        TRUE, TRUE,
                        :policy_areas, :tags, CAST(:meta AS jsonb),
                        1, 0, FALSE,
                        NOW(), NOW()
                    )
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "u": user_id,
                    "title": spec["title"],
                    "content": content_for_db,
                    "fn": original_filename,
                    "size": len(raw),
                    "policy_areas": spec.get("policy_areas") or [],
                    "tags": spec.get("tags") or [],
                    "meta": (
                        '{"source_url":' + repr(spec["source_url"]).replace("'", '"')
                        + ',"source_page":' + repr(spec["source_page"]).replace("'", '"')
                        + ',"organisation":"FERRMED ASBL"'
                        + f',"year":{spec.get("year") or "null"}'
                        + ',"language":' + repr(spec.get("language", "en")).replace("'", '"')
                        + '}'
                    ),
                },
            )
            db.commit()
            created += 1
            logger.info(f"  [OK]  inserted user_documents row.")

        logger.info("\n" + "=" * 80)
        logger.info(f"Done. created={created}  skipped={skipped}  failed={len(failed)}")
        if failed:
            logger.info("Failed URLs:")
            for u in failed:
                logger.info(f"  - {u}")
        logger.info("=" * 80)

        # Pydantic round-trip smoke test. Fails loudly if a row would 500
        # /api/documents. See memory/feedback_raw_insert_orm_defaults.md.
        if created > 0:
            from scripts._validate_user_documents import validate_user_documents_for
            n = validate_user_documents_for(db, user_id)
            logger.info(f"[validate] {n} user_documents rows round-trip cleanly for user_id={user_id}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
